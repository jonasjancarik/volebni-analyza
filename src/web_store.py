#!/usr/bin/env python3
"""
Data layer of the web app: reads the result files written by the scrapers and
shapes them into the JSON the frontend works with.
"""

import hashlib
import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from election_comparison import (
    FLOW_MODEL_VERSION,
    NON_VOTERS,
    OTHER_LISTS,
    estimate_flows,
    group_columns,
    match_precincts,
    precinct_table,
    precinct_type_labels,
)
from election_config import ELECTIONS, ElectionConfig, get_election_config

# Thresholds come from comparing the estimate with a Bayesian model
# (research/bayesian_flows_check.py)
MIN_PRECINCTS_FOR_FLOWS = 50
ROUGH_FLOWS_BELOW = 100

# Lists that ran under another name in the previous election, matched by hand:
# (election, council code) -> name now -> name before
RENAMED_LISTS: Dict[Tuple[str, str], Dict[str, str]] = {
    ("kv2026", "500054"): {"Piráti a nezávislí pro Prahu 1": "Piráti a občané z Prahy 1"},
}

RAW_INPUT_DIR = Path("input/raw")
BOUNDARIES_2022 = "electoral_districts_boundaries.geojson"
BOUNDARIES_2025 = "electoral_districts_boundaries_2025_municipal.geojson"
# Written by src/address_points.py
ADDRESS_POINTS = "address_points.npy"
ADDRESSES_PER_PRECINCT = 48

REGIONS = {
    "1100": "Praha",
    "2100": "Středočeský kraj",
    "3100": "Jihočeský kraj",
    "3200": "Plzeňský kraj",
    "4100": "Karlovarský kraj",
    "4200": "Ústecký kraj",
    "5100": "Liberecký kraj",
    "5200": "Královéhradecký kraj",
    "5300": "Pardubický kraj",
    "6100": "Kraj Vysočina",
    "6200": "Jihomoravský kraj",
    "7100": "Olomoucký kraj",
    "7200": "Zlínský kraj",
    "8100": "Moravskoslezský kraj",
}

# ČSÚ district (okres) codes as used in kvcoco.xml
OKRESY = {
    "1100": "Praha",
    "2101": "Benešov", "2102": "Beroun", "2103": "Kladno", "2104": "Kolín",
    "2105": "Kutná Hora", "2106": "Mělník", "2107": "Mladá Boleslav",
    "2108": "Nymburk", "2109": "Praha-východ", "210A": "Praha-západ",
    "210B": "Příbram", "210C": "Rakovník",
    "3101": "České Budějovice", "3102": "Český Krumlov",
    "3103": "Jindřichův Hradec", "3104": "Písek", "3105": "Prachatice",
    "3106": "Strakonice", "3107": "Tábor",
    "3201": "Domažlice", "3202": "Klatovy", "3203": "Plzeň-město",
    "3204": "Plzeň-jih", "3205": "Plzeň-sever", "3206": "Rokycany",
    "3207": "Tachov",
    "4101": "Cheb", "4102": "Karlovy Vary", "4103": "Sokolov",
    "4201": "Děčín", "4202": "Chomutov", "4203": "Litoměřice", "4204": "Louny",
    "4205": "Most", "4206": "Teplice", "4207": "Ústí nad Labem",
    "5101": "Česká Lípa", "5102": "Jablonec nad Nisou", "5103": "Liberec",
    "5104": "Semily",
    "5201": "Hradec Králové", "5202": "Jičín", "5203": "Náchod",
    "5204": "Rychnov nad Kněžnou", "5205": "Trutnov",
    "5301": "Chrudim", "5302": "Pardubice", "5303": "Svitavy",
    "5304": "Ústí nad Orlicí",
    "6101": "Havlíčkův Brod", "6102": "Jihlava", "6103": "Pelhřimov",
    "6104": "Třebíč", "6105": "Žďár nad Sázavou",
    "6201": "Blansko", "6202": "Brno-město", "6203": "Brno-venkov",
    "6204": "Břeclav", "6205": "Hodonín", "6206": "Vyškov", "6207": "Znojmo",
    "7101": "Jeseník", "7102": "Olomouc", "7103": "Prostějov", "7104": "Přerov",
    "7105": "Šumperk",
    "7201": "Kroměříž", "7202": "Uherské Hradiště", "7203": "Vsetín",
    "7204": "Zlín",
    "8101": "Bruntál", "8102": "Frýdek-Místek", "8103": "Karviná",
    "8104": "Nový Jičín", "8105": "Opava", "8106": "Ostrava-město",
}

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_file_cache: Dict[Tuple[str, float], object] = {}
_comparison_cache: Dict[tuple, Optional[dict]] = {}


class NotFound(Exception):
    """The requested election, council or data file does not exist."""


def _read_json(path: Path):
    """Parse a JSON file once per modification time; the files are tens of MB."""
    key = (str(path), path.stat().st_mtime)
    with _lock:
        if key not in _file_cache:
            for stale in [k for k in _file_cache if k[0] == key[0]]:
                del _file_cache[stale]
            with open(path, "r", encoding="utf-8") as f:
                _file_cache[key] = json.load(f)
        return _file_cache[key]


def _config(election_id: str) -> ElectionConfig:
    if election_id not in ELECTIONS:
        raise NotFound(f"Neznámé volby: {election_id}")
    return get_election_config(election_id)


def _is_parliamentary(config: ElectionConfig) -> bool:
    return config.election_type == "parliamentary"


def _results_file(config: ElectionConfig) -> Path:
    name = (
        "parliamentary_election_results.json"
        if _is_parliamentary(config)
        else "all_municipalities_comprehensive.json"
    )
    return config.results_dir / name


def _data_version(election_id: str) -> float:
    try:
        return _results_file(_config(election_id)).stat().st_mtime
    except FileNotFoundError:
        return 0


def _data_fingerprint(election_id: str) -> str:
    """Hash of the results file. Unlike the modification time it is the same
    on every machine, so a stored estimate stays valid after the data are copied."""
    path = _results_file(_config(election_id))
    key = (f"sha1:{path}", path.stat().st_mtime)
    with _lock:
        if key in _file_cache:
            return _file_cache[key]
    digest = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    with _lock:
        _file_cache[key] = digest.hexdigest()
    return _file_cache[key]


def _results(election_id: str) -> dict:
    path = _results_file(_config(election_id))
    if not path.exists():
        raise NotFound(f"Pro volby {election_id} nejsou stažená data.")
    return _read_json(path)


def _year(config: ElectionConfig) -> str:
    return config.election_date[:4]


def previous_election_id(election_id: str) -> Optional[str]:
    """Closest earlier election of the same type that has data on disk."""
    current = _config(election_id)
    earlier = sorted(
        (
            (config.election_date, other_id)
            for other_id, config in ELECTIONS.items()
            if config.election_type == current.election_type
            and config.election_date < current.election_date
        ),
        reverse=True,
    )
    for _, other_id in earlier:
        if _data_version(other_id) > 0:
            return other_id
    return None


def list_elections() -> List[dict]:
    elections = []
    for election_id, config in ELECTIONS.items():
        has_data = _data_version(election_id) > 0
        previous = previous_election_id(election_id) if has_data else None
        elections.append(
            {
                "id": election_id,
                "name": config.election_name,
                "type": config.election_type,
                "year": _year(config),
                "hasData": has_data,
                "previousId": previous,
                "previousYear": _year(_config(previous)) if previous else None,
            }
        )
    return elections


# ---------------------------------------------------------------------------
# Municipal elections
# ---------------------------------------------------------------------------


def _registry(election_id: str) -> Dict[str, dict]:
    path = _config(election_id).processed_dir / "municipality_registry.json"
    if not path.exists():
        return {}
    municipalities = _read_json(path).get("municipalities", [])
    if isinstance(municipalities, dict):
        municipalities = list(municipalities.values())
    return {str(m.get("municipality_code")): m for m in municipalities}


def _council_type(municipality: dict) -> str:
    districts = municipality.get("district_data") or []
    return districts[0].get("type", "OBEC") if districts else "OBEC"


def _party_key(name) -> str:
    return re.sub(r"\s+", " ", str(name or "")).strip().lower()


def _lists(municipality: dict) -> List[dict]:
    """Lists ordered by votes, with the share of all valid votes.

    ČSÚ's own percentage is recalculated for lists with fewer candidates than
    seats, so it does not add up to 100 and can rank a list above one with
    more votes. It is kept as `officialShare`.
    """
    parties = municipality.get("party_results") or []
    total = sum(p.get("votes_absolute", 0) or 0 for p in parties)
    lists = [
        {
            "number": str(p.get("list_number", p.get("party_code", ""))),
            "name": p.get("party_name") or "",
            "fullName": p.get("party_name_full") or p.get("party_name") or "",
            "votes": int(p.get("votes_absolute", 0) or 0),
            "share": (p.get("votes_absolute", 0) or 0) / total * 100 if total else 0.0,
            "officialShare": float(p.get("votes_percentage", 0) or 0),
            "seats": int(p.get("mandates_won", p.get("mandates", 0)) or 0),
        }
        for p in parties
    ]
    lists.sort(key=lambda item: -item["votes"])
    return lists


def _summary(municipality: dict) -> dict:
    stats = municipality.get("summary_statistics") or {}
    districts = municipality.get("district_data") or []
    ballots = sum(d.get("turnout", {}).get("returned_ballots", 0) for d in districts)
    return {
        "registered": int(stats.get("registered_voters") or 0),
        "ballots": int(stats.get("returned_ballots") or ballots),
        "turnout": float(stats.get("turnout_percentage") or 0),
        "validVotes": int(stats.get("valid_votes") or 0),
        "precincts": len(districts) or int(stats.get("polling_stations") or 0),
    }


def _municipality(election_id: str, code: str) -> dict:
    municipality = _results(election_id).get("municipalities", {}).get(code)
    if not municipality:
        raise NotFound(f"Zastupitelstvo {code} v datech není.")
    return municipality


def list_councils(election_id: str) -> List[dict]:
    """Everything the search box needs, for all councils of an election."""
    config = _config(election_id)
    results = _results(election_id)
    if _is_parliamentary(config):
        return [
            {
                "code": code,
                "name": district["metadata"].get("district_name", code),
                "note": "volební kraj",
                "registered": district["summary_statistics"].get("registered_voters", 0),
            }
            for code, district in results.get("electoral_districts", {}).items()
        ]

    registry = _registry(election_id)
    municipalities = results.get("municipalities", {})
    councils = []
    for code, municipality in municipalities.items():
        entry = registry.get(code, {})
        parent = entry.get("parent_municipality")
        if _council_type(municipality) == "MCMO" and parent in municipalities:
            parent_name = municipalities[parent]["metadata"].get("municipality_name", "")
            note = f"městská část · {parent_name}"
        else:
            note = OKRESY.get(str(entry.get("district_code")), "")
            if note:
                note = "hlavní město" if note == "Praha" else f"okres {note}"
        councils.append(
            {
                "code": code,
                "name": municipality.get("metadata", {}).get("municipality_name", code),
                "note": note,
                "registered": _summary(municipality)["registered"],
            }
        )
    councils.sort(key=lambda council: -council["registered"])
    return councils


def _winner(lists: List[dict]) -> Optional[dict]:
    if not lists:
        return None
    return {"name": lists[0]["name"], "share": lists[0]["share"]}


def election_overview(election_id: str, cities: int = 12) -> dict:
    """Numbers for the landing page of an election."""
    config = _config(election_id)
    results = _results(election_id)
    previous_id = previous_election_id(election_id)

    if _is_parliamentary(config):
        regions, national = [], {}
        registered = ballots = 0
        for code, district in results.get("electoral_districts", {}).items():
            lists = _lists(district)
            stats = _summary(district)
            registered += stats["registered"]
            ballots += stats["ballots"]
            for item in lists:
                national[item["name"]] = national.get(item["name"], 0) + item["votes"]
            regions.append(
                {
                    "code": code,
                    "name": district["metadata"].get("district_name", code),
                    "registered": stats["registered"],
                    "turnout": stats["turnout"],
                    "previousTurnout": None,
                    "winner": _winner(lists),
                }
            )
        total = sum(national.values()) or 1
        return {
            "kind": "parliamentary",
            "councils": len(regions),
            "registered": registered,
            "turnout": ballots / registered * 100 if registered else 0,
            "previousTurnout": None,
            "places": regions,
            "lists": [
                {"name": name, "votes": votes, "share": votes / total * 100}
                for name, votes in sorted(national.items(), key=lambda kv: -kv[1])
            ],
        }

    municipalities = results.get("municipalities", {})
    previous = (
        _results(previous_id).get("municipalities", {}) if previous_id else {}
    )

    def national_turnout(data):
        registered = ballots = 0
        for municipality in data.values():
            # City districts would count their voters a second time
            if _council_type(municipality) != "OBEC":
                continue
            stats = _summary(municipality)
            registered += stats["registered"]
            ballots += stats["ballots"]
        return registered, ballots / registered * 100 if registered else 0

    registered, turnout = national_turnout(municipalities)
    largest = sorted(
        (
            (code, municipality)
            for code, municipality in municipalities.items()
            if _council_type(municipality) == "OBEC" and municipality.get("party_results")
        ),
        key=lambda item: -_summary(item[1])["registered"],
    )[:cities]
    places = []
    for code, municipality in largest:
        stats = _summary(municipality)
        places.append(
            {
                "code": code,
                "name": municipality["metadata"].get("municipality_name", code),
                "registered": stats["registered"],
                "turnout": stats["turnout"],
                "previousTurnout": _summary(previous[code])["turnout"]
                if code in previous
                else None,
                "winner": _winner(_lists(municipality)),
            }
        )
    return {
        "kind": "municipal",
        "councils": len(municipalities),
        "registered": registered,
        "turnout": turnout,
        "previousTurnout": national_turnout(previous)[1] if previous else None,
        "places": places,
        "lists": [],
    }


def _municipal_council(election_id: str, code: str) -> dict:
    config = _config(election_id)
    municipality = _municipality(election_id, code)
    index = _read_json(config.results_dir / "municipality_index.json")
    registry = _registry(election_id).get(code, {})

    lists = _lists(municipality)
    position = {item["number"]: i for i, item in enumerate(lists)}

    previous_id = previous_election_id(election_id)
    previous_summary = None
    if previous_id:
        previous = _results(previous_id).get("municipalities", {}).get(code)
        if previous:
            previous_summary = _summary(previous)
            lookup = {}
            for item in _lists(previous):
                for name in (item["fullName"], item["name"]):
                    lookup.setdefault(_party_key(name), item)
            renamed = RENAMED_LISTS.get((election_id, code), {})
            for item in lists:
                match = (
                    lookup.get(_party_key(renamed.get(item["name"], "")))
                    or lookup.get(_party_key(item["fullName"]))
                    or lookup.get(_party_key(item["name"]))
                )
                item["previous"] = (
                    {"share": match["share"], "seats": match["seats"]} if match else None
                )

    precincts, area_sizes = [], {}
    for district in municipality.get("district_data") or []:
        turnout = district.get("turnout", {})
        votes = [0] * len(lists)
        for vote in district.get("party_votes") or []:
            slot = position.get(str(vote.get("party_list_number")))
            if slot is not None:
                votes[slot] = int(vote.get("votes", 0) or 0)
        area = str(district.get("municipality_code") or code)
        area_sizes[area] = area_sizes.get(area, 0) + 1
        precincts.append(
            {
                "id": str(district.get("district_code")),
                "number": str(district.get("district_code")),
                "area": area,
                "registered": int(turnout.get("registered_voters", 0) or 0),
                "ballots": int(turnout.get("returned_ballots", 0) or 0),
                "turnout": float(turnout.get("turnout_percentage", 0) or 0),
                "votes": votes,
            }
        )

    areas = []
    if len(area_sizes) > 1:
        areas = sorted(
            (
                {
                    "code": area,
                    "name": (index.get(area) or {}).get("name", area),
                    "precincts": size,
                }
                for area, size in area_sizes.items()
            ),
            key=lambda area: area["name"],
        )

    council_type = _council_type(municipality)
    parent = registry.get("parent_municipality")
    parent_entry = index.get(parent) if parent and parent != code else None
    return {
        "code": code,
        "name": municipality.get("metadata", {}).get("municipality_name", code),
        "kind": "Zastupitelstvo městské části"
        if council_type == "MCMO"
        else "Zastupitelstvo obce",
        "parent": {"code": parent, "name": parent_entry.get("name", parent)}
        if parent_entry and council_type == "MCMO"
        else None,
        "seats": sum(item["seats"] for item in lists),
        "summary": _summary(municipality),
        "previousSummary": previous_summary,
        "lists": lists,
        "precincts": precincts,
        "areas": areas,
        "hasCandidates": False,
    }


# ---------------------------------------------------------------------------
# Parliamentary elections
# ---------------------------------------------------------------------------


def _region(election_id: str, code: str) -> dict:
    region = _results(election_id).get("electoral_districts", {}).get(code)
    if not region:
        raise NotFound(f"Volební kraj {code} v datech není.")
    return region


def _region_stations(election_id: str, code: str) -> List[dict]:
    stations = _results(election_id).get("raw_data", {}).get("polling_stations", [])
    return [s for s in stations if str(s.get("electoral_district")) == str(code)]


def _parliamentary_council(election_id: str, code: str) -> dict:
    region = _region(election_id, code)
    lists = _lists(region)
    position = {item["number"]: i for i, item in enumerate(lists)}

    precincts, areas = [], {}
    for station in _region_stations(election_id, code):
        votes = [0] * len(lists)
        for vote in station.get("party_votes") or []:
            slot = position.get(str(vote.get("party_code", vote.get("party_list_number"))))
            if slot is not None:
                votes[slot] = int(vote.get("votes", 0) or 0)
        area = str(station.get("municipality_code"))
        entry = areas.setdefault(
            area, {"code": area, "name": station.get("municipality_name") or area, "precincts": 0}
        )
        entry["precincts"] += 1
        precincts.append(
            {
                # Precinct numbers repeat in every municipality of a region
                "id": f"{area}-{station.get('station_number')}",
                "number": str(station.get("station_number")),
                "area": area,
                "registered": int(station.get("registered_voters", 0) or 0),
                "ballots": int(station.get("returned_ballots", 0) or 0),
                "turnout": float(station.get("turnout_percentage", 0) or 0),
                "votes": votes,
            }
        )

    return {
        "code": code,
        "name": region["metadata"].get("district_name", code),
        "kind": "Volební kraj",
        "parent": None,
        "seats": 0,
        "summary": _summary(region),
        "previousSummary": None,
        "lists": lists,
        "precincts": precincts,
        "areas": sorted(areas.values(), key=lambda area: area["name"]),
        "hasCandidates": bool(region.get("candidates")),
    }


def council(election_id: str, code: str) -> dict:
    config = _config(election_id)
    if _is_parliamentary(config):
        data = _parliamentary_council(election_id, code)
    else:
        data = _municipal_council(election_id, code)
    previous_id = previous_election_id(election_id)
    data["election"] = {
        "id": election_id,
        "name": config.election_name,
        "type": config.election_type,
        "year": _year(config),
    }
    data["previous"] = (
        {"id": previous_id, "year": _year(_config(previous_id))}
        if previous_id and data["previousSummary"]
        else None
    )
    data["minPrecinctsForFlows"] = MIN_PRECINCTS_FOR_FLOWS
    return data


def candidates(election_id: str, code: str) -> List[dict]:
    region = _region(election_id, code)
    names = {
        p.get("party_code"): p.get("party_name", "") for p in region.get("party_results") or []
    }
    return [
        {
            "name": f"{c.get('first_name', '')} {c.get('surname', '')}".strip(),
            "list": names.get(c.get("party_code"), ""),
            "position": c.get("position_on_list"),
            "age": c.get("age"),
            "occupation": c.get("occupation") or "",
            "residence": c.get("residence") or "",
            "votes": c.get("preferential_votes", 0),
            "share": c.get("preferential_percentage", 0),
            "elected": bool(c.get("mandate_won")),
        }
        for c in region.get("candidates") or []
        if c.get("validity", "A") == "A"
    ]


# ---------------------------------------------------------------------------
# Precinct boundaries
# ---------------------------------------------------------------------------


def _boundaries_file(config: ElectionConfig) -> Optional[Path]:
    if _is_parliamentary(config):
        names = [BOUNDARIES_2025]
    else:
        names = [config.boundaries_file, BOUNDARIES_2022]
    for name in names:
        if name and (RAW_INPUT_DIR / name).exists():
            return RAW_INPUT_DIR / name
    return None


def _round_coordinates(coordinates):
    """Five decimals are about a metre; halves the size of the response."""
    if isinstance(coordinates[0], (int, float)):
        return [round(coordinates[0], 5), round(coordinates[1], 5)]
    return [_round_coordinates(part) for part in coordinates]


def _boundary_index(path: Path) -> Tuple[dict, dict]:
    """Geometries keyed by (municipality, precinct) and (city district, precinct)."""
    key = (f"index:{path}", path.stat().st_mtime)
    with _lock:
        cached = _file_cache.get(key)
    if cached:
        return cached

    by_municipality, by_city_district = {}, {}
    for feature in _read_json(path).get("features", []):
        properties = feature.get("properties", {})
        number = properties.get("CISLO", properties.get("cislo"))
        geometry = feature.get("geometry")
        if number is None or not geometry:
            continue
        geometry = {
            "type": geometry["type"],
            "coordinates": _round_coordinates(geometry["coordinates"]),
        }
        municipality = properties.get("OBEC", properties.get("kod_obec"))
        city_district = properties.get("MOMC", properties.get("kod_mco"))
        if municipality:
            by_municipality[(str(municipality), str(number))] = geometry
        if city_district:
            by_city_district[(str(city_district), str(number))] = geometry

    with _lock:
        _file_cache[key] = (by_municipality, by_city_district)
        # The parsed source file is no longer needed
        for stale in [k for k in _file_cache if k[0] == str(path)]:
            del _file_cache[stale]
    return by_municipality, by_city_district


def boundaries(election_id: str, code: str) -> dict:
    """GeoJSON of a council's precincts; `id` matches the precinct ids of council()."""
    config = _config(election_id)
    path = _boundaries_file(config)
    if not path:
        raise NotFound("Hranice okrsků nejsou k dispozici.")
    by_municipality, by_city_district = _boundary_index(path)

    if _is_parliamentary(config):
        keys = [
            (
                f"{s.get('municipality_code')}-{s.get('station_number')}",
                str(s.get("station_number")),
                [str(s.get("municipality_code")), str(s.get("obec_geojson_code"))],
            )
            for s in _region_stations(election_id, code)
        ]
    else:
        keys = [
            (
                str(d.get("district_code")),
                str(d.get("district_code")),
                [str(d.get("municipality_code")), code],
            )
            for d in _municipality(election_id, code).get("district_data") or []
        ]

    features, missing = [], 0
    for precinct_id, number, places in keys:
        geometry = None
        for place in places:
            geometry = by_city_district.get((place, number)) or by_municipality.get(
                (place, number)
            )
            if geometry:
                break
        if not geometry:
            missing += 1
            continue
        features.append(
            {"type": "Feature", "properties": {"id": precinct_id}, "geometry": geometry}
        )

    year = "2025" if path.name == BOUNDARIES_2025 else "2022"
    return {
        "type": "FeatureCollection",
        "features": features,
        "missing": missing,
        "boundariesYear": year,
    }


# ---------------------------------------------------------------------------
# Comparison with the previous election
# ---------------------------------------------------------------------------


def _precinct_frames(
    municipality: dict, area_precincts: Optional[set]
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    names = {
        str(p.get("list_number")): p.get("party_name", "")
        for p in municipality.get("party_results") or []
    }
    turnout_rows, vote_rows = [], []
    for district in municipality.get("district_data") or []:
        precinct = str(district.get("district_code"))
        if area_precincts is not None and precinct not in area_precincts:
            continue
        turnout = district.get("turnout", {})
        turnout_rows.append(
            {
                "district_code": precinct,
                "registered_voters": turnout.get("registered_voters", 0),
                "returned_ballots": turnout.get("returned_ballots", 0),
            }
        )
        for vote in district.get("party_votes") or []:
            number = str(vote.get("party_list_number"))
            vote_rows.append(
                {
                    "district_code": precinct,
                    "party_name": names.get(number, f"Kandidátka {number}"),
                    "votes": vote.get("votes", 0),
                }
            )
    return pd.DataFrame(turnout_rows), pd.DataFrame(vote_rows)


def _percent(frame: pd.DataFrame) -> List[List[float]]:
    return np.round(frame.to_numpy(dtype=float) * 100, 2).tolist()


def _flows_payload(flows: dict) -> dict:
    electorate = flows["electorate_flows"]
    sources, targets = list(electorate.index), list(electorate.columns)
    row, column = sources.index(NON_VOTERS), targets.index(NON_VOTERS)
    tail = (1 - flows["interval"]) / 2 * 100
    draws = flows["electorate_flow_draws"] * 100
    values = electorate.to_numpy() * 100

    def with_range(point, samples):
        low, high = np.percentile(samples, [tail, 100 - tail])
        return {"value": float(point), "low": float(min(low, point)), "high": float(max(high, point))}

    stayed_home = values[row, column]
    # Where the voters of each current group came from, as shares of that group
    origin = values / values.sum(axis=0, keepdims=True)
    origin_draws = draws / draws.sum(axis=1, keepdims=True)
    origin_low, origin_high = np.percentile(origin_draws, [tail, 100 - tail], axis=0)

    return {
        "sources": sources,
        "targets": targets,
        "transitions": _percent(flows["transitions"]),
        "transitionsLow": _percent(flows["transitions_low"]),
        "transitionsHigh": _percent(flows["transitions_high"]),
        "electorate": _percent(electorate),
        "origin": np.round(origin * 100, 2).tolist(),
        "originLow": np.round(np.minimum(origin_low, origin) * 100, 2).tolist(),
        "originHigh": np.round(np.maximum(origin_high, origin) * 100, 2).tolist(),
        "sourceSize": np.round(flows["source_size"].to_numpy() * 100, 2).tolist(),
        "targetSize": np.round(flows["target_size"].to_numpy() * 100, 2).tolist(),
        "stayedHome": float(stayed_home),
        "newlyVoted": with_range(
            values[row].sum() - stayed_home, draws[:, row, :].sum(axis=1) - draws[:, row, column]
        ),
        "stoppedVoting": with_range(
            values[:, column].sum() - stayed_home,
            draws[:, :, column].sum(axis=1) - draws[:, row, column],
        ),
        "explained": flows["explained_variation"] * 100,
        "precinctTypes": flows["precinct_types"],
        "interval": flows["interval"] * 100,
    }


def _stored_comparison_file(election_id: str, code: str, area: Optional[str]) -> Path:
    # VOLBY_CACHE_DIR is for deployments where output/ is mounted read-only
    base = os.environ.get("VOLBY_CACHE_DIR")
    directory = Path(base) / election_id if base else _config(election_id).output_dir / "cache"
    name = re.sub(r"[^0-9A-Za-z]", "", f"{code}{'_' + area if area else ''}".replace("_", "x"))
    return directory / f"comparison_{name}.json"


def _stored_comparison_key(election_id: str, previous_id: str, code: str) -> dict:
    """What a stored comparison was computed from; any change makes it stale."""
    return {
        "renamed_lists": RENAMED_LISTS.get((election_id, code), {}),
        "flow_model_version": FLOW_MODEL_VERSION,
        "min_precincts": MIN_PRECINCTS_FOR_FLOWS,
        "rough_below": ROUGH_FLOWS_BELOW,
        "data": _data_fingerprint(election_id),
        "previous_data": _data_fingerprint(previous_id),
    }


def _read_stored_comparison(path: Path, key: dict) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            stored = json.load(f)
    except (OSError, ValueError):
        return None
    return stored.get("result") if stored.get("key") == key else None


def _write_stored_comparison(path: Path, key: dict, result: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
        with open(temporary, "w", encoding="utf-8") as f:
            json.dump({"key": key, "result": result}, f, ensure_ascii=False)
        os.replace(temporary, path)
    except OSError as error:
        # The comparison still works, it is only computed again after a restart
        logger.warning("Could not store the comparison in %s: %s", path, error)


def _matched_tables(
    current: dict, previous: dict, area: Optional[str], renamed: Optional[Dict[str, str]] = None
) -> Tuple[pd.DataFrame, pd.DataFrame, int]:
    """Precinct tables of both elections for the precincts that can be compared.

    Also returns how many precincts the current election has, matched or not.
    `renamed` maps names of lists now to the names they had before, so that
    they count as the same list.
    """
    area_precincts = None
    if area:
        area_precincts = {
            str(d.get("district_code"))
            for d in current.get("district_data") or []
            if str(d.get("municipality_code")) == area
        }

    tables = []
    for municipality in (previous, current):
        turnout_df, votes_df = _precinct_frames(municipality, area_precincts)
        tables.append(
            precinct_table(turnout_df, votes_df)
            if not turnout_df.empty and not votes_df.empty
            else pd.DataFrame()
        )

    if tables[0].empty or tables[1].empty:
        return pd.DataFrame(), pd.DataFrame(), len(tables[1])
    if renamed:
        before = {old: new for new, old in renamed.items() if new not in tables[0].columns}
        tables[0] = tables[0].rename(columns=before)
    return (*match_precincts(*tables), len(tables[1]))


def comparison(election_id: str, code: str, area: Optional[str] = None) -> dict:
    """Matched precincts of this and the previous election and the voter flows.

    `area` limits a city-wide election to the precincts of one city district.
    """
    config = _config(election_id)
    previous_id = previous_election_id(election_id)
    if _is_parliamentary(config) or not previous_id:
        raise NotFound("Pro tyto volby není s čím srovnávat.")

    key = (
        election_id, previous_id, code, area or "",
        _data_version(election_id), _data_version(previous_id), FLOW_MODEL_VERSION,
    )
    with _lock:
        if key in _comparison_cache:
            return _comparison_cache[key]

    current = _municipality(election_id, code)
    previous = _results(previous_id).get("municipalities", {}).get(code)
    if not previous:
        raise NotFound("Toto zastupitelstvo se v minulých volbách nevolilo.")

    # The estimate takes seconds, so it is kept on disk across restarts
    stored_file = _stored_comparison_file(election_id, code, area)
    stored_key = _stored_comparison_key(election_id, previous_id, code)
    stored = _read_stored_comparison(stored_file, stored_key)
    if stored is not None:
        with _lock:
            _comparison_cache[key] = stored
        return stored

    previous_table, current_table, all_precincts = _matched_tables(
        current, previous, area, RENAMED_LISTS.get((election_id, code))
    )
    matched = len(current_table)

    flows = None
    if matched >= MIN_PRECINCTS_FOR_FLOWS:
        flows = _flows_payload(estimate_flows(previous_table, current_table))

    same_lists, precincts = [], []
    if matched:
        same_lists = [
            group
            for group in group_columns(current_table)
            if group in previous_table.columns and group not in (NON_VOTERS, OTHER_LISTS)
        ]

        def shares(table):
            voted = (table["registered"] - table[NON_VOTERS]).replace(0, np.nan)
            return (table[same_lists].div(voted, axis=0) * 100).fillna(0).round(2)

        previous_shares, current_shares = shares(previous_table), shares(current_table)
        for precinct in current_table.index:
            precincts.append(
                {
                    "id": precinct,
                    "registered": int(current_table.at[precinct, "registered"]),
                    "turnout": [
                        round(float(previous_table.at[precinct, "turnout"]), 2),
                        round(float(current_table.at[precinct, "turnout"]), 2),
                    ],
                    "previous": previous_shares.loc[precinct].tolist(),
                    "current": current_shares.loc[precinct].tolist(),
                }
            )

    result = {
        "previousYear": _year(_config(previous_id)),
        "currentYear": _year(config),
        "matched": matched,
        "skipped": all_precincts - matched,
        "minPrecincts": MIN_PRECINCTS_FOR_FLOWS,
        "rough": matched < ROUGH_FLOWS_BELOW,
        "nonVoters": NON_VOTERS,
        "otherLists": OTHER_LISTS,
        "flows": flows,
        "sameLists": same_lists,
        "precincts": precincts,
    }
    with _lock:
        _comparison_cache[key] = result
    _write_stored_comparison(stored_file, stored_key, result)
    return result


def flow_inputs(election_id: str, code: str, area: Optional[str] = None) -> dict:
    """What the voter-flow estimate is computed from, precinct by precinct.

    The page that explains the method repeats the estimate in the browser, so
    it gets the same shares, weights and precinct types as `estimate_flows`.
    """
    flows = comparison(election_id, code, area)["flows"]
    if not flows:
        raise NotFound("Pro toto zastupitelstvo se přesuny voličů neodhadují.")

    current = _municipality(election_id, code)
    previous = _results(previous_election_id(election_id))["municipalities"][code]
    previous_table, current_table, _ = _matched_tables(
        current, previous, area, RENAMED_LISTS.get((election_id, code))
    )

    sources, targets = flows["sources"], flows["targets"]
    x = previous_table[sources].div(previous_table["registered"], axis=0)
    y = current_table[targets].div(current_table["registered"], axis=0)
    labels = precinct_type_labels(x.to_numpy(), flows["precinctTypes"])
    return {
        "sources": sources,
        "targets": targets,
        "precincts": [
            {
                "id": precinct,
                "registered": int(current_table.at[precinct, "registered"]),
                "registeredPrevious": int(previous_table.at[precinct, "registered"]),
                "type": int(labels[position]),
                "previous": (x.iloc[position] * 100).round(3).tolist(),
                "current": (y.iloc[position] * 100).round(3).tolist(),
            }
            for position, precinct in enumerate(current_table.index)
        ],
    }


def precompute_comparisons() -> int:
    """Compute and store every voter-flow estimate the app can show.

    Covers councils with enough precincts for an estimate and, for city-wide
    councils, each city district that is large enough on its own. Comparisons
    already stored for the current data and model are only read. Returns how
    many comparisons are ready.
    """
    ready = 0
    for election in list_elections():
        if election["type"] != "municipal" or not election["previousId"]:
            continue
        election_id = election["id"]
        previous = _results(election["previousId"]).get("municipalities", {})
        for code, municipality in _results(election_id).get("municipalities", {}).items():
            districts = municipality.get("district_data") or []
            if len(districts) < MIN_PRECINCTS_FOR_FLOWS or code not in previous:
                continue
            sizes: Dict[str, int] = {}
            for district in districts:
                area = str(district.get("municipality_code"))
                sizes[area] = sizes.get(area, 0) + 1
            areas = [a for a, size in sizes.items() if size >= MIN_PRECINCTS_FOR_FLOWS]
            for area in [None] + (areas if len(sizes) > 1 else []):
                try:
                    comparison(election_id, code, area)
                    ready += 1
                except Exception:  # one broken council must not stop the rest
                    logger.exception("Comparison failed for %s %s %s", election_id, code, area)
    return ready


def addresses(election_id: str, code: str) -> dict:
    """
    A random handful of addresses in every precinct, as flat [lng, lat, ...]
    lists. The map draws its dots there, which keeps them out of forests,
    parks and fields. Empty when the address file has not been built.
    """
    path = RAW_INPUT_DIR / ADDRESS_POINTS
    if not path.exists():
        return {"points": {}}
    key = (f"addresses:{election_id}:{code}", path.stat().st_mtime)
    with _lock:
        if key in _file_cache:
            return _file_cache[key]

    import shapely
    from shapely.geometry import shape

    features = boundaries(election_id, code)["features"]
    shapes = shapely.make_valid(np.array([shape(f["geometry"]) for f in features]))
    points: Dict[str, List[float]] = {}
    if len(shapes):
        everything = np.load(path, mmap_mode="r")
        west, south, east, north = shapely.total_bounds(shapes)
        longitude, latitude = everything[:, 0], everything[:, 1]
        nearby = np.asarray(
            everything[
                (longitude >= west)
                & (longitude <= east)
                & (latitude >= south)
                & (latitude <= north)
            ],
            dtype="float64",
        )
        address, precinct = shapely.STRtree(shapes).query(
            shapely.points(nearby), predicate="within"
        )
        order = np.argsort(precinct, kind="stable")
        address, precinct = address[order], precinct[order]
        starts = np.flatnonzero(np.diff(precinct, prepend=-1))
        # Seeded, so that the dots do not move between restarts of the server
        rng = np.random.default_rng(0)
        for start, end in zip(starts, [*starts[1:], len(precinct)]):
            chosen = rng.permutation(address[start:end])[:ADDRESSES_PER_PRECINCT]
            points[features[precinct[start]]["properties"]["id"]] = (
                np.round(nearby[chosen], 5).ravel().tolist()
            )

    result = {"points": points}
    with _lock:
        _file_cache[key] = result
    return result

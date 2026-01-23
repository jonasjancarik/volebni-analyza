#!/usr/bin/env python3
"""Parliamentary election XML parsing helpers."""

import logging
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

PS_NAMESPACE = "http://www.volby.cz/ps/"
NS = {"ps": PS_NAMESPACE}


def parse_xml_with_encoding(
    xml_file: Path, encoding: str = "windows-1250"
) -> Optional[ET.ElementTree]:
    """Parse XML file with fallback encoding handling."""
    try:
        return ET.parse(xml_file)
    except ET.ParseError as e:
        try:
            logger.warning(f"Parsing issue, retrying with {encoding}: {e}")
            with open(xml_file, "r", encoding=encoding, errors="replace") as f:
                return ET.parse(f)
        except Exception as e2:
            logger.error(f"Error parsing {xml_file}: {e2}")
            return None
    except Exception as e:
        logger.error(f"Error parsing {xml_file} with encoding {encoding}: {e}")
        return None


def _get_text(element, path: str, namespace: dict = NS) -> Optional[str]:
    elem = element.find(path, namespace)
    return elem.text.strip() if elem is not None and elem.text else None


def _get_int(element, path: str, namespace: dict = NS) -> Optional[int]:
    text = _get_text(element, path, namespace)
    try:
        return int(text) if text else None
    except (ValueError, TypeError):
        return None


def _get_float(element, path: str, namespace: dict = NS) -> Optional[float]:
    text = _get_text(element, path, namespace)
    try:
        return float(text) if text else None
    except (ValueError, TypeError):
        return None


def parse_party_list(xml_file: Path) -> Dict[int, Dict]:
    """Parse psrkl.xml (party/coalition list)."""
    tree = parse_xml_with_encoding(xml_file)
    if not tree:
        return {}

    root = tree.getroot()
    party_list = {}

    for row in root.findall(".//ps:PS_RKL_ROW", NS):
        party_code = _get_int(row, "ps:KSTRANA", NS)
        if party_code is None:
            continue
        party_list[party_code] = {
            "party_code": party_code,
            "party_id": _get_int(row, "ps:VSTRANA", NS),
            "party_name": _get_text(row, "ps:NAZEVCELK", NS),
            "party_name_short": _get_text(row, "ps:NAZEV_STRK", NS),
            "abbreviation_30": _get_text(row, "ps:ZKRATKAK30", NS),
            "abbreviation_8": _get_text(row, "ps:ZKRATKAK8", NS),
            "num_parties_in_coalition": _get_int(row, "ps:POCSTRVKO", NS),
            "registration_status": _get_text(row, "ps:STAVREG", NS),
            "validity": _get_text(row, "ps:PLAT_STR", NS),
            "mandates_won": _get_int(row, "ps:POCMANDCR", NS) or 0,
        }

    logger.info(f"Loaded {len(party_list)} parties/coalitions")
    return party_list


def parse_candidate_registry(xml_file: Path) -> Dict[int, List[Dict]]:
    """Parse psrk.xml (candidate registry)."""
    tree = parse_xml_with_encoding(xml_file)
    if not tree:
        return {}

    root = tree.getroot()
    candidates_by_district: Dict[int, List[Dict]] = defaultdict(list)

    for row in root.findall(".//ps:PS_REGKAND_ROW", NS):
        district = _get_int(row, "ps:VOLKRAJ", NS)
        if district is None:
            continue
        candidate = {
            "electoral_district": district,
            "party_code": _get_int(row, "ps:KSTRANA", NS),
            "position_on_list": _get_int(row, "ps:PORCISLO", NS),
            "first_name": _get_text(row, "ps:JMENO", NS),
            "surname": _get_text(row, "ps:PRIJMENI", NS),
            "age": _get_int(row, "ps:VEK", NS),
            "occupation": _get_text(row, "ps:POVOLANI", NS),
            "residence": _get_text(row, "ps:BYDLISTEN", NS),
            "running_party": _get_int(row, "ps:PSTRANA", NS),
            "nominating_party": _get_int(row, "ps:NSTRANA", NS),
            "validity": _get_text(row, "ps:PLATNOST", NS),
            "preferential_votes": _get_int(row, "ps:POCHLASU", NS) or 0,
            "preferential_percentage": _get_float(row, "ps:POCPROC", NS) or 0.0,
            "mandate_won": _get_text(row, "ps:MANDAT", NS) == "Y",
            "mandate_ranking": _get_int(row, "ps:PORADIMAND", NS) or 0,
        }
        candidates_by_district[district].append(candidate)

    total_candidates = sum(len(candidates) for candidates in candidates_by_district.values())
    logger.info(
        "Loaded %s candidates across %s electoral districts",
        total_candidates,
        len(candidates_by_district),
    )

    return dict(candidates_by_district)


def parse_municipality_registry(xml_file: Path) -> Dict[str, Dict]:
    """Parse pscoco.xml (municipality registry with VOLKRAJ mapping)."""
    tree = parse_xml_with_encoding(xml_file)
    if not tree:
        return {}

    root = tree.getroot()
    obec_registry = {}

    for row in root.findall(".//ps:PS_COCO_ROW", NS):
        obec_code = _get_text(row, "ps:OBEC", NS)
        if not obec_code:
            continue
        obec_registry[obec_code] = {
            "obec_code": obec_code,
            "obec_name": _get_text(row, "ps:NAZEVOBCE", NS),
            "obec_geojson_code": _get_text(row, "ps:OBEC_PREZ", NS),
            "electoral_district": _get_int(row, "ps:VOLKRAJ", NS),
            "kraj_code": _get_text(row, "ps:KRAJ", NS),
            "okres_code": _get_text(row, "ps:OKRES", NS),
        }

    logger.info(f"Loaded {len(obec_registry)} municipalities from pscoco.xml")
    return obec_registry


def parse_polling_stations(
    xml_file: Path, obec_registry: Optional[Dict[str, Dict]] = None
) -> Tuple[List[Dict], Dict[int, Dict]]:
    """Parse pst4.xml (polling station results)."""
    tree = parse_xml_with_encoding(xml_file)
    if not tree:
        return [], {}

    root = tree.getroot()
    polling_stations: List[Dict] = []

    for row in root.findall(".//ps:PS_T4_ROW", NS):
        station = {
            "station_id": _get_int(row, "ps:ID_OKRSKY", NS),
            "district_code": _get_text(row, "ps:OKRES", NS),
            "municipality_code": _get_text(row, "ps:OBEC", NS),
            "station_number": _get_text(row, "ps:OKRSEK", NS),
            "registered_voters": _get_int(row, "ps:VOL_SEZNAM", NS) or 0,
            "issued_ballots": _get_int(row, "ps:VYD_OBALKY", NS) or 0,
            "returned_ballots": _get_int(row, "ps:ODEVZ_OBAL", NS) or 0,
            "valid_votes": _get_int(row, "ps:PL_HL_CELK", NS) or 0,
            "parties_running": _get_text(row, "ps:ZAKRSTRANA", NS),
        }

        if obec_registry and station["municipality_code"]:
            obec_info = obec_registry.get(station["municipality_code"])
            if obec_info:
                station["electoral_district"] = obec_info.get("electoral_district")
                station["municipality_name"] = obec_info.get("obec_name")
                station["obec_geojson_code"] = obec_info.get("obec_geojson_code")

        if station["registered_voters"] > 0:
            station["turnout_percentage"] = round(
                (station["returned_ballots"] / station["registered_voters"]) * 100,
                2,
            )
        else:
            station["turnout_percentage"] = 0.0

        polling_stations.append(station)

    logger.info(f"Parsed {len(polling_stations)} polling stations")

    district_turnout = defaultdict(
        lambda: {
            "polling_stations": 0,
            "registered_voters": 0,
            "returned_ballots": 0,
            "valid_votes": 0,
            "turnout_percentage": 0.0,
        }
    )

    for station in polling_stations:
        district_num = station.get("electoral_district")
        if district_num is None:
            continue
        summary = district_turnout[district_num]
        summary["polling_stations"] += 1
        summary["registered_voters"] += station.get("registered_voters", 0)
        summary["returned_ballots"] += station.get("returned_ballots", 0)
        summary["valid_votes"] += station.get("valid_votes", 0)

    for summary in district_turnout.values():
        if summary["registered_voters"] > 0:
            summary["turnout_percentage"] = round(
                (summary["returned_ballots"] / summary["registered_voters"]) * 100,
                2,
            )

    return polling_stations, dict(district_turnout)


def parse_party_votes(
    xml_file: Path, obec_registry: Optional[Dict[str, Dict]] = None
) -> Tuple[Dict[int, List[Dict]], Dict[int, Dict], int]:
    """Parse pst4p.xml (party votes by polling station)."""
    row_tag = f"{{{PS_NAMESPACE}}}PS_T4P_ROW"

    obec_to_district = {}
    if obec_registry:
        obec_to_district = {
            obec: info.get("electoral_district") for obec, info in obec_registry.items()
        }

    party_votes_by_station: Dict[int, List[Dict]] = defaultdict(list)
    party_votes_by_district: Dict[int, Dict] = defaultdict(lambda: defaultdict(int))
    rows_parsed = 0

    with open(xml_file, "rb") as xml_handle:
        for _, elem in ET.iterparse(xml_handle, events=("end",)):
            if elem.tag != row_tag:
                continue

            station_id = _get_int(elem, "ps:ID_OKRSKY", NS)
            party_code = _get_int(elem, "ps:KSTRANA", NS)
            votes = _get_int(elem, "ps:POC_HLASU", NS) or 0
            obec_code = _get_text(elem, "ps:OBEC", NS)

            if station_id is not None and party_code is not None:
                party_votes_by_station[station_id].append(
                    {
                        "party_list_number": party_code,
                        "party_code": party_code,
                        "votes": votes,
                    }
                )

            if obec_code and party_code is not None:
                district_num = obec_to_district.get(obec_code)
                if district_num is not None:
                    party_votes_by_district[district_num][party_code] += votes

            rows_parsed += 1
            elem.clear()

    return (
        dict(party_votes_by_station),
        {district: dict(votes) for district, votes in party_votes_by_district.items()},
        rows_parsed,
    )

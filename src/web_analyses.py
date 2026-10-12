#!/usr/bin/env python3
"""
Figures behind the written analyses of the web app (its "Analýzy" section).

An analysis is an article about one result. Its text lives in the frontend
(web/src/analyses); this module computes every number the text, tables and
charts show, so that the article cannot drift from the data.
"""

import logging
import math
import threading
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import web_store as store
from election_comparison import (
    FLOW_MODEL_VERSION,
    MAX_ELECTORATE_CHANGE,
    NON_VOTERS,
    OTHER_LISTS,
    estimate_flows,
    group_columns,
    match_precincts,
    precinct_table,
    precinct_type_options,
)

# Bump when the figures of an analysis change, so that stored ones are recomputed
ANALYSIS_VERSION = 1

PRAGUE = "554782"
PRAGUE_REGION = "1"

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_cache: Dict[tuple, dict] = {}


def group_key(name: str) -> Optional[str]:
    """Short name of a list the Prague analysis follows across elections,
    where the same party runs under a different name each time."""
    if name == NON_VOTERS:
        return "nevolici"
    if name == OTHER_LISTS:
        return "ostatni"
    upper = name.upper()
    if "PIRÁT" in upper:
        return "pirati"
    if upper.startswith("PRAHA SOBĚ"):
        return "prahaSobe"
    if upper.startswith("STAROSTOVÉ"):
        return "stan"
    if upper.startswith("SPOLU"):
        return "spolu"
    if upper.startswith("ANO 2011"):
        return "ano"
    if upper.startswith("SPD") or "SVOBODA A PŘÍMÁ DEMOKRACIE" in upper:
        return "spd"
    if upper.startswith("MOTORISTÉ"):
        return "motoriste"
    if upper.startswith("SEN PRO PRAHU"):
        return "sen"
    return None


# ---------------------------------------------------------------------------
# Seats
# ---------------------------------------------------------------------------


def seat_order(
    votes: Dict[str, float], seats: int, threshold: float = 0.05
) -> List[Tuple[float, str, int]]:
    """D'Hondt quotients from the largest: (quotient, list, which seat of that list).

    Only lists with at least `threshold` of all votes take part. The first
    `seats` entries win a seat, the ones after them are next in line.
    """
    total = sum(votes.values())
    order = [
        (count / divisor, name, divisor)
        for name, count in votes.items()
        if total > 0 and count / total >= threshold
        for divisor in range(1, seats + 1)
    ]
    order.sort(key=lambda entry: -entry[0])
    return order


def seat_allocation(votes: Dict[str, float], seats: int, threshold: float = 0.05) -> Dict[str, int]:
    allocation: Dict[str, int] = {}
    for _, name, _ in seat_order(votes, seats, threshold)[:seats]:
        allocation[name] = allocation.get(name, 0) + 1
    return allocation


def smallest_shift(
    move: Callable[[float], Dict[str, float]],
    done: Callable[[Dict[str, float]], bool],
    limit: float,
    step: int = 1000,
) -> Optional[int]:
    """Fewest votes, in multiples of `step`, for which `move(votes)` gives a
    result that `done` accepts; None when not even `limit` votes are enough."""
    for votes in range(step, int(limit) + 1, step):
        if done(move(votes)):
            return votes
    return None


def _scenarios(council: dict) -> dict:
    """What would have left STAN and Spolu without a majority of their own."""
    seats = council["seats"]
    majority = seats // 2 + 1
    votes = {
        group_key(item["name"]) or item["name"]: float(item["votes"]) for item in council["lists"]
    }
    per_ballot = sum(votes.values()) / council["summary"]["ballots"]

    def changed(**changes: float) -> Dict[str, float]:
        result = dict(votes)
        for key, change in changes.items():
            result[key] = result.get(key, 0) + change
        return result

    def joint(result: Dict[str, float]) -> Dict[str, float]:
        result = dict(result)
        result["joint"] = result.pop("pirati") + result.pop("prahaSobe")
        return result

    def outcome(key: str, result: Dict[str, float], moved: Optional[int] = None) -> dict:
        allocation = seat_allocation(result, seats)
        return {
            "key": key,
            "seats": {
                name: allocation.get(name, 0)
                for name in ("stan", "spolu", "prahaSobe", "pirati", "joint", "ano")
                if name in result
            },
            "stanSpolu": allocation.get("stan", 0) + allocation.get("spolu", 0),
            "votes": moved,
            "voters": round(moved / per_ballot) if moved else None,
        }

    def without_majority(result: Dict[str, float]) -> bool:
        allocation = seat_allocation(result, seats)
        return allocation.get("stan", 0) + allocation.get("spolu", 0) < majority

    sen = votes.get("sen", 0)
    scenarios = [
        outcome("actual", votes),
        outcome("joint", joint(votes)),
        outcome("sen-pirati", changed(sen=-sen, pirati=sen)),
        outcome("sen-praha-sobe", changed(sen=-sen, prahaSobe=sen)),
        outcome("joint-sen", joint(changed(sen=-sen, pirati=sen))),
    ]
    shifts: Dict[str, Callable[[float], Dict[str, float]]] = {
        "stan-to-praha-sobe": lambda count: changed(stan=-count, prahaSobe=count),
        "stan-to-pirati": lambda count: changed(stan=-count, pirati=count),
        "new-pirati": lambda count: changed(pirati=count),
    }
    for key, move in shifts.items():
        moved = smallest_shift(move, without_majority, limit=votes["stan"])
        if moved is not None:
            scenarios.append(outcome(key, move(moved), moved))

    order = seat_order(votes, seats)
    last_quotient, last_list, _ = order[seats - 1]
    return {
        "seats": seats,
        "majority": majority,
        "votesPerBallot": per_ballot,
        "lastSeat": last_list,
        # Lists that were closest to taking the last seat
        "nextInLine": [
            {
                "key": name,
                "seat": seat,
                "missingVotes": math.ceil(last_quotient * seat - votes[name]),
                "missingVoters": round((last_quotient * seat - votes[name]) / per_ballot),
            }
            for _, name, seat in order[seats : seats + 3]
        ],
        "scenarios": scenarios,
    }


# ---------------------------------------------------------------------------
# Results by list, precinct and city district
# ---------------------------------------------------------------------------


def _lists(council: dict, before: dict, minimum_share: float = 2.0) -> List[dict]:
    earlier = {group_key(item["name"]): item for item in before["lists"]}
    ballots, earlier_ballots = council["summary"]["ballots"], before["summary"]["ballots"]
    rows = []
    for item in council["lists"]:
        key = group_key(item["name"])
        if not key or item["share"] < minimum_share:
            continue
        old = earlier.get(key)
        rows.append(
            {
                "key": key,
                "name": item["name"],
                "votes": item["votes"],
                "share": item["share"],
                "seats": item["seats"],
                # Voters cast up to as many votes as there are seats
                "voters": round(item["share"] / 100 * ballots),
                "previousShare": old["share"] if old else None,
                "previousSeats": old["seats"] if old else None,
                "previousVoters": round(old["share"] / 100 * earlier_ballots) if old else None,
            }
        )
    return rows


def _precinct_frame(council: dict) -> pd.DataFrame:
    """One row per precinct with the votes of the followed lists."""
    keys = [group_key(item["name"]) for item in council["lists"]]
    rows = []
    for precinct in council["precincts"]:
        row = {
            "id": precinct["id"],
            "area": precinct["area"],
            "registered": precinct["registered"],
            "ballots": precinct["ballots"],
            "votes": sum(precinct["votes"]),
        }
        for key, votes in zip(keys, precinct["votes"]):
            if key:
                row[key] = votes
        rows.append(row)
    return pd.DataFrame(rows).set_index("id").fillna(0)


def _share(frame: pd.DataFrame, key: str) -> Optional[float]:
    if key not in frame.columns or frame["votes"].sum() == 0:
        return None
    return float(frame[key].sum() / frame["votes"].sum() * 100)


FOLLOWED = ("stan", "spolu", "prahaSobe", "ano", "pirati")


def _districts(council: dict, now: pd.DataFrame, then: pd.DataFrame) -> List[dict]:
    """How the city-wide vote went in each city district, largest first."""
    names = {area["code"]: area["name"] for area in council["areas"]}
    rows = []
    for code, current in now.groupby("area"):
        earlier = then[then["area"] == code]
        registered = int(current["registered"].sum())
        if registered == 0:
            continue
        rows.append(
            {
                "code": code,
                "name": names.get(code, code),
                "registered": registered,
                "turnout": float(current["ballots"].sum() / registered * 100),
                "shares": {key: _share(current, key) for key in (*FOLLOWED, "sen")},
                "previousShares": {key: _share(earlier, key) for key in FOLLOWED},
            }
        )
    rows.sort(key=lambda row: -row["registered"])
    return rows


def _precincts(now: pd.DataFrame, then: pd.DataFrame) -> dict:
    """Precinct counts the text quotes, and the vote by fifths of precincts
    ordered by how strong the Pirates were last time."""

    def winners(frame: pd.DataFrame) -> Dict[str, int]:
        counted = frame[list(FOLLOWED)].idxmax(axis=1).value_counts()
        return {key: int(counted.get(key, 0)) for key in FOLLOWED}

    both = then.join(now, lsuffix="_then", rsuffix="_now", how="inner")
    change = (both["registered_now"] - both["registered_then"]).abs() / both["registered_then"]
    both = both[(change <= MAX_ELECTORATE_CHANGE) & (both["votes_then"] > 0) & (both["votes_now"] > 0)]

    def shares(key: str, suffix: str) -> pd.Series:
        return both[f"{key}_{suffix}"] / both[f"votes_{suffix}"] * 100

    moved = {key: shares(key, "now") - shares(key, "then") for key in FOLLOWED}

    fifth = pd.qcut(shares("pirati", "then"), 5, labels=False)
    fifths = []
    for index in range(5):
        part = both[fifth == index]
        fifths.append(
            {
                "precincts": len(part),
                "shares": {
                    key: float(part[f"{key}_now"].sum() / part["votes_now"].sum() * 100)
                    for key in FOLLOWED
                },
                "previousShares": {
                    key: float(part[f"{key}_then"].sum() / part["votes_then"].sum() * 100)
                    for key in FOLLOWED
                },
            }
        )

    return {
        "compared": len(both),
        "fell": {key: int((moved[key] < 0).sum()) for key in FOLLOWED},
        "rose": {key: int((moved[key] > 0).sum()) for key in FOLLOWED},
        "piratiAhead": {
            "now": int((now["pirati"] > now["prahaSobe"]).sum()),
            "then": int((then["pirati"] > then["prahaSobe"]).sum()),
        },
        "precincts": {"now": len(now), "then": len(then)},
        "winners": {"now": winners(now), "then": winners(then)},
        # From the weakest fifth for the Pirates to the strongest
        "fifths": fifths,
    }


# ---------------------------------------------------------------------------
# Voter flows
# ---------------------------------------------------------------------------


def _keyed(flows: dict, matched: int, registered: int, previous_registered: int) -> dict:
    """Flows with lists under their short names, and the sizes of both
    electorates for turning percentages into people."""
    result = dict(flows)
    result["sources"] = [group_key(name) or name for name in flows["sources"]]
    result["targets"] = [group_key(name) or name for name in flows["targets"]]
    result["matched"] = matched
    result["registered"] = registered
    result["previousRegistered"] = previous_registered
    return result


def _flows_with_small_lists(current: dict, previous: dict, min_share: float = 0.025) -> Tuple[dict, int]:
    """The app's estimate with lists down to `min_share` kept apart; the app
    itself merges lists under 3 % into the other lists."""
    tables = [
        precinct_table(*store._precinct_frames(municipality, None), min_share=min_share, max_lists=10)
        for municipality in (previous, current)
    ]
    before, after = match_precincts(*tables)
    return store._flows_payload(estimate_flows(before, after)), len(after)


def _parliamentary_table(election_id: str, region: str) -> pd.DataFrame:
    names = {
        str(party.get("party_code")): party.get("party_name", "")
        for party in store._region(election_id, region).get("party_results") or []
    }
    turnout, votes = [], []
    for station in store._region_stations(election_id, region):
        precinct = f"{station.get('municipality_code')}-{station.get('station_number')}"
        turnout.append(
            {
                "district_code": precinct,
                "registered_voters": station.get("registered_voters", 0),
                "returned_ballots": station.get("returned_ballots", 0),
            }
        )
        for vote in station.get("party_votes") or []:
            code = str(vote.get("party_code", vote.get("party_list_number")))
            votes.append(
                {
                    "district_code": precinct,
                    "party_name": names.get(code, f"Strana {code}"),
                    "votes": vote.get("votes", 0),
                }
            )
    return precinct_table(pd.DataFrame(turnout), pd.DataFrame(votes))


def _municipal_table(municipality: dict) -> pd.DataFrame:
    """The city's precincts under the names parliamentary results use for
    them: city district and precinct number."""
    turnout, votes = store._precinct_frames(municipality, None)
    area = {
        str(district.get("district_code")): str(district.get("municipality_code"))
        for district in municipality.get("district_data") or []
    }
    for frame in (turnout, votes):
        frame["district_code"] = frame["district_code"].map(lambda code: f"{area[code]}-{code}")
    return precinct_table(turnout, votes)


def flows_across_settings(before: pd.DataFrame, after: pd.DataFrame) -> dict:
    """The estimate with ranges that also cover every number of precinct
    types the data allow.

    Between two different kinds of election the estimate depends on that
    choice more than on which precincts are in the data, so the usual range
    alone would look more certain than it is.
    """
    flows = store._flows_payload(estimate_flows(before, after))
    options = precinct_type_options(len(before), len(group_columns(before)))
    ranges = {
        name: (np.array(flows[f"{name}Low"]), np.array(flows[f"{name}High"]))
        for name in ("transitions", "origin")
    }
    for types in options:
        if types == flows["precinctTypes"]:
            continue
        other = estimate_flows(before, after, resamples=0, precinct_types=types)
        electorate = other["electorate_flows"].to_numpy()
        values = {
            "transitions": other["transitions"].to_numpy() * 100,
            "origin": electorate / electorate.sum(axis=0, keepdims=True) * 100,
        }
        for name, (low, high) in ranges.items():
            ranges[name] = (np.minimum(low, values[name]), np.maximum(high, values[name]))
    for name, (low, high) in ranges.items():
        flows[f"{name}Low"] = np.round(low, 2).tolist()
        flows[f"{name}High"] = np.round(high, 2).tolist()
    flows["settings"] = options
    return flows


# ---------------------------------------------------------------------------
# The analyses
# ---------------------------------------------------------------------------


def _prague_2026() -> dict:
    """Pirates and Praha Sobě in the 2026 Prague election."""
    election, previous, parliamentary = "kv2026", "kv2022", "ps2025"
    council = store.council(election, PRAGUE)
    before = store.council(previous, PRAGUE)
    current = store._municipality(election, PRAGUE)
    earlier = store._municipality(previous, PRAGUE)
    now, then = _precinct_frame(council), _precinct_frame(before)
    registered = council["summary"]["registered"]
    previous_registered = before["summary"]["registered"]

    comparison = store.comparison(election, PRAGUE)
    small_lists, small_lists_matched = _flows_with_small_lists(current, earlier)

    region = store._region(parliamentary, PRAGUE_REGION)
    region_summary = store._summary(region)
    parliament_before, parliament_after = match_precincts(
        _parliamentary_table(parliamentary, PRAGUE_REGION), _municipal_table(current)
    )

    return {
        "council": {"election": election, "code": PRAGUE, "name": council["name"]},
        "years": {"current": "2026", "previous": "2022", "parliamentary": "2025"},
        "summary": council["summary"],
        "previousSummary": before["summary"],
        "lists": _lists(council, before),
        "belowThreshold": sum(item["share"] for item in council["lists"] if item["share"] < 5),
        **_scenarios(council),
        "flows": _keyed(comparison["flows"], comparison["matched"], registered, previous_registered),
        "flowsSmallLists": _keyed(small_lists, small_lists_matched, registered, previous_registered),
        "precincts": _precincts(now, then),
        "districts": _districts(council, now, then),
        "parliamentary": {
            "summary": region_summary,
            "lists": [
                {
                    "key": group_key(item["name"]),
                    "name": item["name"],
                    "votes": item["votes"],
                    "share": item["share"],
                }
                for item in store._lists(region)
                if group_key(item["name"])
            ],
            "flows": _keyed(
                flows_across_settings(parliament_before, parliament_after),
                len(parliament_after),
                registered,
                region_summary["registered"],
            ),
        },
    }


ANALYSES: Dict[str, dict] = {
    "praha-2026-pirati-praha-sobe": {
        "build": _prague_2026,
        "elections": ("kv2026", "kv2022", "ps2025"),
    },
}


def _stored_file(slug: str, election_id: str):
    return store._stored_comparison_file(election_id, slug, None).with_name(f"analysis_{slug}.json")


def analysis(slug: str) -> dict:
    """Figures of one analysis; computed once and kept on disk like the
    voter-flow estimates, because they take several seconds."""
    definition = ANALYSES.get(slug)
    if not definition:
        raise store.NotFound("Taková analýza tu není.")
    elections = definition["elections"]
    for election_id in elections:
        store._results(election_id)  # NotFound when its data are not downloaded

    key = {
        "analysis_version": ANALYSIS_VERSION,
        "flow_model_version": FLOW_MODEL_VERSION,
        "data": {election_id: store._data_fingerprint(election_id) for election_id in elections},
    }
    cache_key = (slug, str(key))
    with _lock:
        if cache_key in _cache:
            return _cache[cache_key]

    path = _stored_file(slug, elections[0])
    result = store._read_stored_comparison(path, key)
    if result is None:
        result = definition["build"]()
        store._write_stored_comparison(path, key, result)
    with _lock:
        _cache[cache_key] = result
    return result


def precompute() -> int:
    """Compute and store every analysis whose data are on disk. Returns how many are ready."""
    ready = 0
    for slug in ANALYSES:
        try:
            analysis(slug)
            ready += 1
        except store.NotFound:
            pass  # an election it needs is not downloaded
        except Exception:
            logger.exception("Analysis %s failed", slug)
    return ready

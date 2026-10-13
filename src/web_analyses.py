#!/usr/bin/env python3
"""
Figures behind the written analyses of the web app (its "Analýzy" section).

An analysis is an article about one result. Its text lives in the frontend
(web/src/analyses); this module computes every number the text, tables and
charts show, so that the article cannot drift from the data.
"""

import logging
import math
import re
import threading
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import places
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
ANALYSIS_VERSION = 5

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


class _SeatMath:
    """Seats of one council under changed votes: what a scenario would give
    and how many votes a change needs."""

    def __init__(
        self,
        council: dict,
        key_of: Callable[[str], Optional[str]] = group_key,
        rivals: Tuple[str, ...] = ("stan", "spolu"),
        step: int = 1000,
    ):
        self.seats = council["seats"]
        self.majority = self.seats // 2 + 1
        # The lists whose majority the scenarios try to end
        self.rivals = rivals
        # Votes are moved in multiples of this; a small council needs finer steps
        self.step = step
        self.votes = {key_of(item["name"]) or item["name"]: float(item["votes"]) for item in council["lists"]}
        self.per_ballot = sum(self.votes.values()) / council["summary"]["ballots"]

    def changed(self, **changes: float) -> Dict[str, float]:
        result = dict(self.votes)
        for key, change in changes.items():
            result[key] = result.get(key, 0) + change
        return result

    @staticmethod
    def joint(result: Dict[str, float]) -> Dict[str, float]:
        """Pirates and Praha Sobě on one list."""
        result = dict(result)
        result["joint"] = result.pop("pirati") + result.pop("prahaSobe")
        return result

    def outcome(self, key: str, result: Dict[str, float], moved: Optional[int] = None) -> dict:
        allocation = seat_allocation(result, self.seats)
        return {
            "key": key,
            "seats": {
                name: allocation.get(name, 0)
                for name in ("stan", "spolu", "prahaSobe", "pirati", "joint", "ano")
                if name in result
            },
            "stanSpolu": sum(allocation.get(name, 0) for name in self.rivals),
            "votes": moved,
            "voters": round(moved / self.per_ballot) if moved is not None else None,
        }

    def rival_seats(self, result: Dict[str, float]) -> int:
        allocation = seat_allocation(result, self.seats)
        return sum(allocation.get(name, 0) for name in self.rivals)

    def without_majority(self, result: Dict[str, float]) -> bool:
        return self.rival_seats(result) < self.majority

    def fewest(
        self, key: str, move: Callable[[float], Dict[str, float]], at_most: int
    ) -> Optional[dict]:
        """The outcome of the fewest moved votes that leave the rivals with
        `at_most` seats; None when no number of votes does."""
        if self.rival_seats(move(0)) <= at_most:
            return self.outcome(key, move(0), 0)
        moved = smallest_shift(
            move, lambda result: self.rival_seats(result) <= at_most, limit=self.votes["stan"], step=self.step
        )
        return None if moved is None else self.outcome(key, move(moved), moved)

    def shifts(self, moves: Dict[str, Callable[[float], Dict[str, float]]]) -> List[dict]:
        """For each way of moving votes, the fewest that leave the rivals
        without a majority of their own."""
        outcomes = []
        for key, move in moves.items():
            moved = smallest_shift(move, self.without_majority, limit=self.votes["stan"], step=self.step)
            if moved is not None:
                outcomes.append(self.outcome(key, move(moved), moved))
        return outcomes

    def summary(self) -> dict:
        return {"seats": self.seats, "majority": self.majority, "votesPerBallot": self.per_ballot}


def _scenarios(council: dict) -> dict:
    """What would have left STAN and Spolu without a majority of their own."""
    math_ = _SeatMath(council)
    votes, changed = math_.votes, math_.changed
    sen = votes.get("sen", 0)
    scenarios = [
        math_.outcome("actual", votes),
        math_.outcome("joint", math_.joint(votes)),
        math_.outcome("sen-pirati", changed(sen=-sen, pirati=sen)),
        math_.outcome("sen-praha-sobe", changed(sen=-sen, prahaSobe=sen)),
        math_.outcome("joint-sen", math_.joint(changed(sen=-sen, pirati=sen))),
        *math_.shifts(
            {
                "stan-to-praha-sobe": lambda count: changed(stan=-count, prahaSobe=count),
                "stan-to-pirati": lambda count: changed(stan=-count, pirati=count),
                "new-pirati": lambda count: changed(pirati=count),
            }
        ),
    ]

    order = seat_order(votes, math_.seats)
    last_quotient, last_list, _ = order[math_.seats - 1]
    return {
        **math_.summary(),
        "lastSeat": last_list,
        # Lists that were closest to taking the last seat
        "nextInLine": [
            {
                "key": name,
                "seat": seat,
                "missingVotes": math.ceil(last_quotient * seat - votes[name]),
                "missingVoters": round((last_quotient * seat - votes[name]) / math_.per_ballot),
            }
            for _, name, seat in order[math_.seats : math_.seats + 3]
        ],
        "scenarios": scenarios,
    }


# ---------------------------------------------------------------------------
# Results by list, precinct and city district
# ---------------------------------------------------------------------------


def _lists(
    council: dict,
    before: dict,
    minimum_share: float = 2.0,
    key_of: Callable[[str], Optional[str]] = group_key,
) -> List[dict]:
    earlier = {key_of(item["name"]): item for item in before["lists"]}
    ballots, earlier_ballots = council["summary"]["ballots"], before["summary"]["ballots"]
    rows = []
    for item in council["lists"]:
        key = key_of(item["name"])
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


def _precinct_frame(council: dict, key_of: Callable[[str], Optional[str]] = group_key) -> pd.DataFrame:
    """One row per precinct with the votes of the followed lists."""
    keys = [key_of(item["name"]) for item in council["lists"]]
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
                row[key] = row.get(key, 0) + votes
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


WHEN = ("then", "mid", "now")


def _precinct_voters(earlier: dict, current: dict, parliamentary: str, region: str) -> pd.DataFrame:
    """Voters of every group in every precinct in three elections: the
    previous municipal one ("then"), the parliamentary one between them
    ("mid") and the current municipal one ("now")."""
    tables = (_municipal_table(earlier), _parliamentary_table(parliamentary, region), _municipal_table(current))
    frames = []
    for when, table in zip(WHEN, tables):
        table = table.rename(columns=lambda name: group_key(name) or name)
        table["voted"] = table["registered"] - table["nevolici"]
        frames.append(table.add_suffix(f"_{when}"))
    return frames[0].join(frames[1:], how="outer").fillna(0)


def _voter_group(part: pd.DataFrame) -> dict:
    """How many people voted for each followed list in a set of precincts."""
    return {
        "precincts": len(part),
        "registered": int(part["registered_now"].sum()),
        "voted": {when: float(part[f"voted_{when}"].sum()) for when in WHEN},
        "voters": {
            key: {
                when: float(part[f"{key}_{when}"].sum())
                for when in WHEN
                if f"{key}_{when}" in part.columns
            }
            for key in FOLLOWED
        },
    }


def _fifths_by_kept(voters: pd.DataFrame, key: str) -> List[dict]:
    """Precincts in fifths by how many of a list's parliamentary voters it
    kept in the municipal election a year later, from the fewest."""
    present = (
        (voters["registered_then"] > 0)
        & (voters["registered_mid"] > 0)
        & (voters["registered_now"] > 0)
        & (voters[f"{key}_mid"] > 0)
    )
    part = voters[present]
    change = (part["registered_now"] - part["registered_then"]).abs() / part["registered_then"]
    part = part[change <= MAX_ELECTORATE_CHANGE]
    fifth = pd.qcut(part[f"{key}_now"] / part[f"{key}_mid"], 5, labels=False)
    return [_voter_group(part[fifth == index]) for index in range(5)]


def _district_voters(voters: pd.DataFrame, names: Dict[str, str]) -> List[dict]:
    rows = []
    for code, part in voters.groupby(voters.index.str.split("-").str[0]):
        group = _voter_group(part)
        if group["registered"] > 0:
            rows.append({"code": code, "name": names.get(code, code), **group})
    rows.sort(key=lambda row: -row["registered"])
    return rows


def _district_flows(election: str, code: str, council: dict, then: pd.DataFrame) -> List[dict]:
    """The app's estimate of the city-wide vote narrowed to each city
    district that is large enough for one."""
    rows = []
    for area in council["areas"]:
        if area["precincts"] < store.MIN_PRECINCTS_FOR_FLOWS:
            continue
        comparison = store.comparison(election, code, area["code"])
        if not comparison["flows"]:
            continue
        registered = int(then[then["area"] == area["code"]]["registered"].sum())
        rows.append(
            {
                "code": area["code"],
                "name": area["name"],
                "rough": comparison["rough"],
                "flows": _keyed(comparison["flows"], comparison["matched"], registered, registered),
            }
        )
    rows.sort(key=lambda row: -row["flows"]["registered"])
    return rows


def _prague_2026_spolu_stan() -> dict:
    """Where the voters of Spolu and STAN in Prague are least firmly theirs."""
    election, previous, parliamentary = "kv2026", "kv2022", "ps2025"
    first = analysis("praha-2026-pirati-praha-sobe")
    council = store.council(election, PRAGUE)
    then = _precinct_frame(store.council(previous, PRAGUE))
    voters = _precinct_voters(
        store._municipality(previous, PRAGUE),
        store._municipality(election, PRAGUE),
        parliamentary,
        PRAGUE_REGION,
    )

    seats = _SeatMath(council)
    changed = seats.changed
    scenarios = [
        seats.outcome("actual", seats.votes),
        *seats.shifts(
            {
                "spolu-to-praha-sobe": lambda count: changed(spolu=-count, prahaSobe=count),
                "spolu-to-pirati": lambda count: changed(spolu=-count, pirati=count),
                "stan-to-praha-sobe": lambda count: changed(stan=-count, prahaSobe=count),
                "stan-to-pirati": lambda count: changed(stan=-count, pirati=count),
            }
        ),
    ]

    return {
        **{name: first[name] for name in ("council", "years", "summary", "previousSummary", "lists")},
        **seats.summary(),
        "scenarios": scenarios,
        "flows": first["flows"],
        "parliamentary": first["parliamentary"],
        "city": _voter_group(voters),
        "fifths": _fifths_by_kept(voters, "spolu"),
        "districts": _district_voters(voters, {area["code"]: area["name"] for area in council["areas"]}),
        "districtFlows": _district_flows(election, PRAGUE, council, then),
    }


def _prague_2026_next_time() -> dict:
    """What would have changed the result: the votes of SEN on another
    list, more voters, voters coming back from STAN, alone and together."""
    first = analysis("praha-2026-pirati-praha-sobe")
    seats = _SeatMath(store.council("kv2026", PRAGUE))
    changed, votes = seats.changed, seats.votes
    sen = votes.get("sen", 0)
    voters = lambda count: count * seats.per_ballot  # noqa: E731

    # Where the votes of SEN could go, by the share of them that follows
    with_sen = {
        "pirati": lambda share: changed(sen=-sen * share, pirati=sen * share),
        "prahaSobe": lambda share: changed(sen=-sen * share, prahaSobe=sen * share),
        "joint": lambda share: seats.joint(changed(sen=-sen * share, pirati=sen * share)),
    }
    transfers = []
    for recipient, move in with_sen.items():
        steps, before = [], None
        for percent in range(0, 101):
            outcome = seats.outcome(recipient, move(percent / 100))
            if outcome["seats"] != before:
                steps.append({"share": percent, **outcome})
                before = outcome["seats"]
        transfers.append({"recipient": recipient, "steps": steps})

    # Each way on its own: the first seat STAN and Spolu lose and the second,
    # which is the one that ends their majority
    alone = {
        "new-pirati": lambda count: changed(pirati=count),
        "new-praha-sobe": lambda count: changed(prahaSobe=count),
        "stan-to-pirati": lambda count: changed(stan=-count, pirati=count),
        "stan-to-praha-sobe": lambda count: changed(stan=-count, prahaSobe=count),
    }
    levers = [
        {
            "key": key,
            "first": seats.fewest(key, move, seats.majority),
            "second": seats.fewest(key, move, seats.majority - 1),
        }
        for key, move in alone.items()
    ]

    # Together with a share of SEN's voters on the Pirates' list
    shares = [0, 25, 50, 75, 100]
    new_voters = [0, 3000, 6000, 9000, 12000, 15000, 18000]
    back_from_stan = [0, 2000, 4000, 6000, 8000, 10000]

    def with_pirati(share: float, new: float = 0, back: float = 0) -> Dict[str, float]:
        return changed(sen=-sen * share, pirati=sen * share + new + back, stan=-back)

    combined = {
        "shares": shares,
        "new": {
            "columns": new_voters,
            "cells": [
                [seats.rival_seats(with_pirati(share / 100, new=voters(count))) for count in new_voters]
                for share in shares
            ],
        },
        "back": {
            "columns": back_from_stan,
            "cells": [
                [seats.rival_seats(with_pirati(share / 100, back=voters(count))) for count in back_from_stan]
                for share in shares
            ],
        },
        # What is still missing for STAN and Spolu to lose the majority
        "remaining": [
            {
                "share": share,
                "new": seats.fewest(
                    "new-pirati",
                    lambda count, share=share: with_pirati(share / 100, new=count),
                    seats.majority - 1,
                ),
                "back": seats.fewest(
                    "stan-to-pirati",
                    lambda count, share=share: with_pirati(share / 100, back=count),
                    seats.majority - 1,
                ),
            }
            for share in (0, 50, 100)
        ],
    }

    strongholds = sorted(
        first["districts"][:15], key=lambda district: -(district["shares"].get("sen") or 0)
    )[:3]
    return {
        **{name: first[name] for name in ("council", "years", "summary", "lists")},
        **seats.summary(),
        "actual": seats.outcome("actual", votes),
        "joint": seats.outcome("joint", seats.joint(votes)),
        "sen": {
            "votes": sen,
            "voters": round(sen / seats.per_ballot),
            "strongholds": [
                {"name": district["name"], "share": district["shares"]["sen"]} for district in strongholds
            ],
        },
        "transfers": transfers,
        "levers": levers,
        "combined": combined,
        "flows": first["flows"],
        "flowsSmallLists": first["flowsSmallLists"],
        "parliamentary": first["parliamentary"],
    }


# Minutes to the centre by public transport, the edges of the bands
TIME_BANDS = (0, 10, 15, 20, 25, 30, 35, 40)
# A coarser split for looking at kinds of housing at a similar travel time
TIME_RINGS = (0, 20, 30)
# Kinds of precincts in the order the article shows them
KIND_ORDER = ("older", "panel", "newer", "houses", places.MIXED)
# Fewer precincts than this say too little about a combination
FEWEST_PRECINCTS = 10


def _precinct_places(election: str, code: str, municipality: Optional[str] = None) -> pd.DataFrame:
    """Travel time and kind of housing of every precinct, from the files the
    scripts prepare. `municipality` is the city a city district belongs to;
    the buildings are stored for the whole city."""
    buildings = places.buildings_file(municipality or code)
    if not buildings.exists():
        raise store.NotFound("Pro tuto analýzu chybí data o budovách. Připraví je skript src/buildings.py.")
    if not places.TRANSIT_MINUTES_FILE.exists():
        raise store.NotFound("Pro tuto analýzu chybí jízdní řády. Připraví je skript src/transit_times.py.")
    return places.precinct_places(
        store.boundaries(election, code)["features"],
        np.load(buildings),
        np.load(places.TRANSIT_MINUTES_FILE),
    )


def _place_group(part: pd.DataFrame) -> dict:
    """A voter group with the turnout of each election and where its
    precincts are; an average voter's minutes and kilometres."""
    group = _voter_group(part)
    group["turnout"] = {
        when: float(part[f"voted_{when}"].sum() / part[f"registered_{when}"].sum() * 100)
        for when in WHEN
        if part[f"registered_{when}"].sum() > 0
    }
    weights = part["registered_now"]
    group["minutes"] = float(np.average(part["minutes"], weights=weights))
    group["km"] = float(np.average(part["km"], weights=weights))
    group["homes"] = {
        kind: float(np.average(part[kind], weights=part["flats"])) * 100 for kind in places.KINDS
    }
    return group


# A district council list of Praha Sobě alone, such as "PRAHA 7 SOBĚ"
OWN_LOCAL_LIST = re.compile(r"^PRAHA \d+ SOBĚ$", re.IGNORECASE)
# From this share of the district council vote the local list counts as strong
STRONG_LOCAL_SHARE = 20


def _strong_local_lists(election: str, council: dict) -> List[dict]:
    """City districts where Praha Sobě ran alone for the district council
    and got a strong result, with that result."""
    rows = []
    for area in council["areas"]:
        try:
            lists = store.council(election, area["code"])["lists"]
        except store.NotFound:
            continue
        share = max((item["share"] for item in lists if OWN_LOCAL_LIST.match(item["name"].strip())), default=0)
        if share >= STRONG_LOCAL_SHARE:
            rows.append({"code": area["code"], "name": area["name"], "share": share})
    rows.sort(key=lambda row: -row["share"])
    return rows


def _bands(values: pd.Series, edges: Tuple[int, ...]) -> List[Tuple[int, Optional[int], pd.Series]]:
    """Which rows fall between each pair of edges; the last band is open."""
    upper = [*edges[1:], None]
    return [
        (low, high, (values >= low) & (values < (math.inf if high is None else high)))
        for low, high in zip(edges, upper)
    ]


def _prague_2026_centre() -> dict:
    """Support by travel time to the centre and by what people live in."""
    election, previous, parliamentary = "kv2026", "kv2022", "ps2025"
    first = analysis("praha-2026-pirati-praha-sobe")
    voters = _precinct_voters(
        store._municipality(previous, PRAGUE),
        store._municipality(election, PRAGUE),
        parliamentary,
        PRAGUE_REGION,
    )
    voters = voters[voters["registered_now"] > 0]
    where = _precinct_places(election, PRAGUE)
    precinct = voters.index.str.split("-").str[1]
    voters = voters.assign(
        precinct=precinct,
        **{column: where[column].reindex(precinct).to_numpy() for column in where.columns},
    )
    voters = voters[voters["minutes"].notna()]

    kinds = []
    for kind in KIND_ORDER:
        part = voters[voters["kind"] == kind]
        if len(part):
            kinds.append({"kind": kind, **_place_group(part)})

    # Every kind of housing at a similar travel time, where there is enough of it
    combined = []
    for kind in KIND_ORDER:
        for low, high, inside in _bands(voters["minutes"], TIME_RINGS):
            part = voters[inside & (voters["kind"] == kind)]
            if len(part) >= FEWEST_PRECINCTS:
                combined.append({"kind": kind, "from": low, "to": high, **_place_group(part)})

    def share(key: str, when: str = "now") -> pd.Series:
        return (voters[f"{key}_{when}"] / voters[f"voted_{when}"].where(voters[f"voted_{when}"] > 0) * 100).round(2)

    # The same bands in the districts where Praha Sobě is strong locally and in the rest
    strong = _strong_local_lists(election, store.council(election, PRAGUE))
    in_strong = pd.Series(voters.index.str.split("-").str[0].isin([row["code"] for row in strong]), index=voters.index)
    local = []
    for low, high, inside in _bands(voters["minutes"], TIME_BANDS):
        if not inside.any():
            continue
        parts = {"strong": voters[inside & in_strong], "rest": voters[inside & ~in_strong]}
        local.append(
            {
                "from": low,
                "to": high,
                **{
                    name: _voter_group(part) if len(part) >= FEWEST_PRECINCTS else None
                    for name, part in parts.items()
                },
            }
        )

    points = pd.DataFrame(
        {
            "id": voters["precinct"],
            "kind": voters["kind"],
            "minutes": voters["minutes"].round(1),
            "km": voters["km"].round(2),
            "registered": voters["registered_now"].astype(int),
            "turnout": (voters["voted_now"] / voters["registered_now"] * 100).round(2),
            **{key: share(key) for key in FOLLOWED},
            "piratiMid": share("pirati", "mid"),
        }
    )
    points = points.astype(object).where(points.notna(), None)

    return {
        **{name: first[name] for name in ("council", "years", "summary", "lists")},
        "city": _place_group(voters),
        "times": [
            {"from": low, "to": high, **_place_group(voters[inside])}
            for low, high, inside in _bands(voters["minutes"], TIME_BANDS)
            if inside.any()
        ],
        "kinds": kinds,
        "kindsByTime": combined,
        "localBase": {
            "districts": strong,
            "strong": _voter_group(voters[in_strong]),
            "rest": _voter_group(voters[~in_strong]),
            "times": local,
        },
        "precincts": points.to_dict("records"),
    }


def _district(builder: str) -> Callable[[], dict]:
    """A builder from the analyses of city districts. That module builds on
    this one, so it is loaded only when one of its analyses is asked for."""

    def build() -> dict:
        import web_districts

        return getattr(web_districts, builder)()

    return build


def _records_2026() -> dict:
    import web_anomalies

    return web_anomalies.records_2026()


ANALYSES: Dict[str, dict] = {
    "praha-2026-pirati-praha-sobe": {
        "build": _prague_2026,
        "elections": ("kv2026", "kv2022", "ps2025"),
    },
    "praha-2026-volici-spolu-a-stan": {
        "build": _prague_2026_spolu_stan,
        "elections": ("kv2026", "kv2022", "ps2025"),
    },
    "praha-2026-co-by-zmenilo-vysledek": {
        "build": _prague_2026_next_time,
        "elections": ("kv2026", "kv2022", "ps2025"),
    },
    "praha-2026-centrum-sidliste-predmesti": {
        "build": _prague_2026_centre,
        "elections": ("kv2026", "kv2022", "ps2025"),
    },
    "praha-5-2026-okrsky-a-bloky": {
        "build": _district("prague_5_2026"),
        "elections": ("kv2026", "kv2022", "ps2025"),
    },
    "praha-1-2026-okrsky": {
        "build": _district("prague_1_2026"),
        "elections": ("kv2026", "kv2022", "ps2025"),
    },
    "chyby-v-zapisech-okrsku-2026": {
        "build": _records_2026,
        "elections": ("kv2026",),
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

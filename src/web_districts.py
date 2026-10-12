#!/usr/bin/env python3
"""
Figures behind the analyses of single city districts of Prague.

A city district has too few precincts for a voter-flow estimate worth an
article, so these analyses read the precincts directly: how the same voters
filled in the ballot for the council of the district and the one for the
council of the city, how that compares with the previous election and with
the parliamentary one, and how it differs between neighbourhoods.

The shared seat maths and precinct helpers live in web_analyses.py, which
also lists these analyses and stores their figures.
"""

import math
from typing import Callable, Dict, List, Optional, Tuple

import pandas as pd

import places
import web_store as store
from election_comparison import MAX_ELECTORATE_CHANGE
from web_analyses import (
    FEWEST_PRECINCTS,
    KIND_ORDER,
    PRAGUE,
    PRAGUE_REGION,
    _lists,
    _precinct_frame,
    _precinct_places,
    _SeatMath,
    _share,
    group_key,
    seat_allocation,
    seat_order,
    smallest_shift,
)

# Which ballot gives the turnout of each election
TURNOUT_OF = {"then": "previousLocal", "mid": "parliamentary", "now": "local"}
# Columns of a precinct frame that are not lists
COUNTS = ["area", "registered", "ballots", "votes"]
# A precinct whose turnout is under this share of the council's says nothing
# about the place. In Praha 5 it is the precinct with the address of the town
# hall, where people with no other permanent address are registered
LOW_TURNOUT = 0.5

# Neighbourhoods are lists of precinct numbers: the part of the municipality
# most of a precinct's addresses are in (address register of 30 September
# 2026; research/praha5_neighbourhoods.py prints the table for a district).
# Each row is a name, the group the article shows it in and the first and
# last number of each run of precincts.
Parts = Tuple[Tuple[str, str, Tuple[Tuple[int, int], ...]], ...]


def part_of(precinct: str, parts: Parts) -> Tuple[Optional[str], Optional[str]]:
    """Neighbourhood of a precinct and the group it is shown in."""
    number = int(precinct) if precinct.isdigit() else -1
    for name, group, runs in parts:
        if any(first <= number <= last for first, last in runs):
            return name, group
    return None, None


def _on_ballots(frames: Dict[str, pd.DataFrame], ids=None, unusual=()) -> dict:
    """How a set of precincts voted on every ballot: the shares of the
    followed lists, and the turnout of the three elections. The turnout leaves
    out the `unusual` precincts, which would pull it down for no reason of the place."""
    parts = {name: frame if ids is None else frame[frame.index.isin(ids)] for name, frame in frames.items()}
    result: dict = {
        "precincts": len(parts["local"]),
        "registered": int(parts["local"]["registered"].sum()),
        "ballots": {},
        "turnout": {},
    }
    for when, name in TURNOUT_OF.items():
        part = parts[name]
        result["ballots"][when] = int(part["ballots"].sum())
        counted = part[~part.index.isin(unusual)]
        registered = counted["registered"].sum()
        result["turnout"][when] = float(counted["ballots"].sum() / registered * 100) if registered else None
    for name, part in parts.items():
        result[name] = {key: _share(part, key) for key in part.columns.difference(COUNTS)}
    return result


def _rounded(value, digits: int = 2):
    """A nested result with its numbers rounded; a precinct needs no more."""
    if isinstance(value, float):
        return round(value, digits)
    if isinstance(value, dict):
        return {key: _rounded(item, digits) for key, item in value.items()}
    if isinstance(value, list):
        return [_rounded(item, digits) for item in value]
    return value


def _shares(frame: pd.DataFrame) -> pd.DataFrame:
    """Percent of votes of every followed list in every precinct."""
    return frame.drop(columns=COUNTS).div(frame["votes"].where(frame["votes"] > 0), axis=0) * 100


def _bloc_totals(council: dict, before: dict, blocs: Dict[str, Tuple[str, ...]], key_of: Callable) -> List[dict]:
    """Seats and votes of each bloc in both elections."""

    def total(lists: List[dict], keys: Tuple[str, ...], field: str) -> float:
        return sum(item[field] for item in lists if key_of(item["name"]) in keys)

    return [
        {
            "key": name,
            "seats": {"then": total(before["lists"], keys, "seats"), "now": total(council["lists"], keys, "seats")},
            "share": {"then": total(before["lists"], keys, "share"), "now": total(council["lists"], keys, "share")},
        }
        for name, keys in blocs.items()
    ]


def _last_seat(seats: _SeatMath) -> dict:
    """Who took the last seat and which three were next in line for it."""
    order = seat_order(seats.votes, seats.seats)
    last_quotient, last_list, last_seat = order[seats.seats - 1]
    return {
        "lastSeat": {"key": last_list, "seat": last_seat},
        "nextInLine": [
            {
                "key": name,
                "seat": seat,
                "missingVotes": math.ceil(last_quotient * seat - seats.votes[name]),
                "missingVoters": round((last_quotient * seat - seats.votes[name]) / seats.per_ballot),
            }
            for _, name, seat in order[seats.seats : seats.seats + 3]
        ],
    }


class _District:
    """The ballots the voters of one city district saw, and the figures every
    analysis of a district shows."""

    election, previous, parliamentary = "kv2026", "kv2022", "ps2025"

    def __init__(self, code: str, key_of: Callable[[str], Optional[str]], parts: Parts, groups: Dict[str, str]):
        self.code, self.key_of, self.groups = code, key_of, groups
        self.council, self.before = store.council(self.election, code), store.council(self.previous, code)
        self.city, self.city_before = store.council(self.election, PRAGUE), store.council(self.previous, PRAGUE)

        def of_district(frame: pd.DataFrame) -> pd.DataFrame:
            """The precincts of the district on a ballot the whole city votes on."""
            return frame[frame["area"] == code]

        mid = of_district(_precinct_frame(store.council(self.parliamentary, PRAGUE_REGION)))
        self.frames = {
            "local": _precinct_frame(self.council, key_of),
            "previousLocal": _precinct_frame(self.before, key_of),
            "city": of_district(_precinct_frame(self.city)),
            "previousCity": of_district(_precinct_frame(self.city_before)),
            "parliamentary": mid.set_axis(mid.index.str.split("-").str[1]),
        }
        local = self.frames["local"]

        self.turnout = local["ballots"] / local["registered"].where(local["registered"] > 0)
        whole = local["ballots"].sum() / local["registered"].sum()
        self.unusual = self.turnout[self.turnout < whole * LOW_TURNOUT].index

        # Kinds of housing, where the files with buildings and timetables are at hand
        try:
            kind = _precinct_places(self.election, code, PRAGUE)["kind"].reindex(local.index)
            # Too few precincts of one kind say little; they join the mixed ones
            few = kind.map(kind.value_counts()) < FEWEST_PRECINCTS
            self.kind = kind.mask(few, places.MIXED)
        except store.NotFound:
            self.kind = pd.Series(index=local.index, dtype=object)

        self.parts = {precinct: part_of(precinct, parts) for precinct in local.index}
        self.group = pd.Series({precinct: self.parts[precinct][1] for precinct in local.index})

    def on(self, ids) -> dict:
        return _on_ballots(self.frames, ids, self.unusual)

    def counts(self) -> dict:
        """Precinct counts the text quotes."""
        now, before, city = (_shares(self.frames[name]) for name in ("local", "previousLocal", "city"))
        both = now.index.intersection(before.index)
        # The ballots list the same precincts in a different order
        city = city.reindex(now.index)
        same = now.columns.intersection(before.columns)

        def winners(table: pd.DataFrame) -> Dict[str, int]:
            return {key: int(count) for key, count in table.idxmax(axis=1).value_counts().items()}

        return {
            "fell": {key: int((now.loc[both, key] < before.loc[both, key]).sum()) for key in same},
            "rose": {key: int((now.loc[both, key] > before.loc[both, key]).sum()) for key in same},
            "compared": len(both),
            # Precincts in which each list had the most votes
            "winners": {"then": winners(before), "now": winners(now)},
            # Precincts in which a list got less for the council of the district than for that of the city
            "lowerLocally": {
                key: int((now[key] < city[key]).sum()) for key in now.columns.intersection(city.columns)
            },
        }

    def bloc_ahead(self, first: Tuple[str, ...], second: Tuple[str, ...]) -> Dict[str, int]:
        """Precincts in which the lists of `first` had more votes together than those of `second`."""

        def ahead(table: pd.DataFrame) -> int:
            one, other = (table[[key for key in keys if key in table.columns]].sum(axis=1) for keys in (first, second))
            return int((one > other).sum())

        return {"then": ahead(_shares(self.frames["previousLocal"])), "now": ahead(_shares(self.frames["local"]))}

    def turnout_figures(self) -> dict:
        """Whether turnout goes with the result: precincts in thirds by how much
        their turnout rose since the previous election and by how high it is,
        and how closely the two move together across precincts."""
        local, then, mid = (self.frames[name] for name in ("local", "previousLocal", "parliamentary"))
        ids = local.index.intersection(then.index).intersection(mid.index).difference(self.unusual)
        ids = ids[(local.loc[ids, "votes"] > 0) & (then.loc[ids, "votes"] > 0) & (mid.loc[ids, "registered"] > 0)]

        def turnout(frame: pd.DataFrame) -> pd.Series:
            return frame.loc[ids, "ballots"] / frame.loc[ids, "registered"] * 100

        def share(frame: pd.DataFrame, key: str) -> pd.Series:
            return frame.loc[ids, key] / frame.loc[ids, "votes"] * 100

        now, rise = turnout(local), turnout(local) - turnout(then)

        def thirds(values: pd.Series) -> List[dict]:
            third = pd.qcut(values, 3, labels=False)
            return [self.on(third.index[third == index]) for index in range(3)]

        lists = local.columns.difference(COUNTS)
        return {
            "compared": len(ids),
            "rose": int((rise > 0).sum()),
            # From the precincts where turnout rose least to those where it rose most
            "byRise": thirds(rise),
            # From the lowest turnout to the highest
            "byLevel": thirds(now),
            # Correlation across precincts, from -1 to 1
            "together": {
                "rise": {
                    key: float((share(local, key) - share(then, key)).corr(rise))
                    for key in lists.intersection(then.columns)
                },
                "level": {key: float(share(local, key).corr(now)) for key in lists},
                # The fall of turnout since the parliamentary election against the Pirates' share in it
                "fallAndPirati": float((turnout(mid) - now).corr(share(mid, "pirati"))),
            },
        }

    def fifths(self, key: str) -> List[dict]:
        """Precincts in fifths by how strong a list was last time, from the weakest."""
        local, then = self.frames["local"], self.frames["previousLocal"]
        both = then.join(local, lsuffix="_then", rsuffix="_now", how="inner")
        change = (both["registered_now"] - both["registered_then"]).abs() / both["registered_then"]
        both = both[(change <= MAX_ELECTORATE_CHANGE) & (both["votes_then"] > 0) & (both["votes_now"] > 0)]
        fifth = pd.qcut(both[f"{key}_then"] / both["votes_then"], 5, labels=False)
        return [self.on(fifth.index[fifth == index]) for index in range(5)]

    def figures(self) -> dict:
        council, before, city, key_of = self.council, self.before, self.city, self.key_of
        local, mid, kind, group = self.frames["local"], self.frames["parliamentary"], self.kind, self.group
        return {
            "council": {"election": self.election, "code": self.code, "name": council["name"]},
            "city": {"election": self.election, "code": PRAGUE, "name": city["name"]},
            "years": {"current": "2026", "previous": "2022", "parliamentary": "2025"},
            "summary": council["summary"],
            "previousSummary": before["summary"],
            "lists": _lists(council, before, key_of=key_of),
            "previousLists": [
                {"key": key_of(item["name"]), "name": item["name"], "share": item["share"], "seats": item["seats"]}
                for item in before["lists"]
                if key_of(item["name"]) and item["share"] >= 2
            ],
            # Percent of votes for lists that won no seat
            "withoutSeats": sum(item["share"] for item in council["lists"] if item["seats"] == 0),
            "previousWithoutSeats": sum(item["share"] for item in before["lists"] if item["seats"] == 0),
            "district": self.on(None),
            "parliamentaryVotes": {key: int(mid[key].sum()) for key in mid.columns.difference(COUNTS)},
            # The city-wide ballot in the whole city, for comparison with its result in the district
            "cityWide": {
                when: {group_key(item["name"]): item["share"] for item in result["lists"] if group_key(item["name"])}
                for when, result in (("then", self.city_before), ("now", city))
            },
            "groups": [
                {"key": key, "name": name, **self.on(group.index[group == key])}
                for key, name in self.groups.items()
                if (group == key).any()
            ],
            "kinds": [
                {"kind": name, **self.on(kind.index[kind == name])} for name in KIND_ORDER if (kind == name).any()
            ],
            "counts": self.counts(),
            "turnout": self.turnout_figures(),
            "unusual": [
                {
                    "id": precinct,
                    "registered": int(local.at[precinct, "registered"]),
                    "turnout": float(self.turnout[precinct] * 100),
                }
                for precinct in self.unusual
            ],
            "precincts": [
                _rounded(
                    {
                        "id": precinct,
                        "part": self.parts[precinct][0],
                        "group": self.parts[precinct][1],
                        "kind": kind[precinct] if isinstance(kind[precinct], str) else None,
                        **_on_ballots(self.frames, [precinct]),
                    }
                )
                for precinct in sorted(local.index)
            ],
        }


# ---------------------------------------------------------------------------
# Praha 5
# ---------------------------------------------------------------------------

PRAGUE_5 = "500143"

# The lists of Praha 5 in two camps. Praha 5 Sobě, the Pirates and SEN 21 ran
# the district after the 2022 election with 21 of 41 votes; in December 2024
# the council replaced them with ODS, TOP 09, ANO and STAN.
PRAGUE_5_BLOCS = {
    "coalition2022": ("praha5Sobe", "pirati", "sen"),
    "townHall": ("ods", "top", "odsTop", "stan", "ano"),
}

# Barrandov is not a part of the municipality: it is the precincts of
# Hlubočepy up on the plateau, picked by hand.
PRAGUE_5_PARTS: Parts = (
    ("Malá Strana", "smichov", ((5001, 5002),)),
    ("Smíchov", "smichov", ((5003, 5019), (5021, 5040), (5043, 5043))),
    ("Košíře", "kosire", ((5041, 5042), (5045, 5045), (5048, 5059))),
    ("Motol", "kosire", ((5044, 5044), (5046, 5047))),
    ("Radlice", "jinonice", ((5020, 5020), (5060, 5060))),
    ("Jinonice", "jinonice", ((5061, 5063),)),
    ("Hlubočepy", "jinonice", ((5064, 5065), (5067, 5067))),
    ("Barrandov", "barrandov", ((5066, 5066), (5068, 5081))),
)
PRAGUE_5_GROUPS = {
    "smichov": "Smíchov a Malá Strana",
    "kosire": "Košíře a Motol",
    "jinonice": "Jinonice, Radlice a Hlubočepy",
    "barrandov": "Barrandov",
}


def prague_5_key(name: str) -> Optional[str]:
    """Short name of a list on the ballot for the council of Praha 5."""
    upper = name.upper()
    if upper.startswith("PRAHA 5 SOBĚ"):
        return "praha5Sobe"
    if upper.startswith("OBČANSKÁ DEMOKRATICKÁ"):
        return "ods"
    if upper.startswith("TOP LIDOVCI"):
        return "top"
    if upper.startswith("SPOLEČNĚ PRO PRAHU 5"):
        return "odsTop"  # ODS and TOP 09 on one list in 2022
    if upper.startswith("KDU-ČSL"):
        return "kduZeleni"
    if upper.startswith("KOALICE SEN 21"):
        return "sen"
    if upper.startswith("NAŠE PRAHA 5"):
        return "nasePraha5"
    return group_key(name)


def prague_5_part(precinct: str) -> Tuple[Optional[str], Optional[str]]:
    """Neighbourhood of a precinct of Praha 5 and the group it is shown in."""
    return part_of(precinct, PRAGUE_5_PARTS)


class _Prague5Seats(_SeatMath):
    """Seats of the council of Praha 5, counted by its two blocs."""

    def __init__(self, council: dict):
        super().__init__(council, key_of=prague_5_key, rivals=PRAGUE_5_BLOCS["townHall"], step=100)
        self.shown = list(seat_allocation(self.votes, self.seats))

    @staticmethod
    def merged(result: Dict[str, float], keys: Tuple[str, ...]) -> Dict[str, float]:
        """Several lists as one."""
        result = dict(result)
        result["joint"] = sum(result.pop(key) for key in keys)
        return result

    def outcome(self, key: str, result: Dict[str, float], moved: Optional[int] = None) -> dict:
        allocation = seat_allocation(result, self.seats)
        coalition = PRAGUE_5_BLOCS["coalition2022"]
        return {
            "key": key,
            "seats": {name: allocation.get(name, 0) for name in (*self.shown, "joint") if name in result},
            "blocs": {
                # A joint list in these scenarios is always one of the 2022 coalition
                "coalition2022": sum(allocation.get(name, 0) for name in (*coalition, "joint")),
                "townHall": self.rival_seats(result),
            },
            "votes": moved,
            "voters": round(moved / self.per_ballot) if moved is not None else None,
        }


def _prague_5_seats(council: dict) -> dict:
    """How close the last seats were and what would have changed the blocs."""
    seats = _Prague5Seats(council)
    votes, changed = seats.votes, seats.changed
    coalition = PRAGUE_5_BLOCS["coalition2022"]
    current = seat_allocation(votes, seats.seats)

    # The fewest votes that give the Pirates one more seat
    one_more = smallest_shift(
        lambda count: changed(pirati=count),
        lambda result: seat_allocation(result, seats.seats).get("pirati", 0) > current.get("pirati", 0),
        limit=votes["pirati"],
        step=10,
    )
    scenarios = [
        seats.outcome("actual", votes),
        *([seats.outcome("pirati-one-more", changed(pirati=one_more), one_more)] if one_more else []),
        seats.outcome("joint-two", seats.merged(votes, ("praha5Sobe", "pirati"))),
        seats.outcome("joint-three", seats.merged(votes, coalition)),
        *seats.shifts(
            {
                "new-pirati": lambda count: changed(pirati=count),
                "stan-to-pirati": lambda count: changed(stan=-count, pirati=count),
            }
        ),
    ]
    return {**seats.summary(), **_last_seat(seats), "scenarios": scenarios}


def prague_5_2026() -> dict:
    """The council of Praha 5: seats and blocs, precincts and neighbourhoods,
    and the same voters on the ballots of three elections."""
    district = _District(PRAGUE_5, prague_5_key, PRAGUE_5_PARTS, PRAGUE_5_GROUPS)
    figures = district.figures()
    return {
        **figures,
        "blocs": _bloc_totals(district.council, district.before, PRAGUE_5_BLOCS, prague_5_key),
        **_prague_5_seats(district.council),
        # From the weakest fifth for the Pirates in the previous election to the strongest
        "fifths": district.fifths("pirati"),
        "counts": {
            **figures["counts"],
            # Precincts in which the 2022 coalition had more votes than the other bloc
            "coalitionAhead": district.bloc_ahead(*PRAGUE_5_BLOCS.values()),
        },
    }


# ---------------------------------------------------------------------------
# Praha 1
# ---------------------------------------------------------------------------

PRAGUE_1 = "500054"

# After the 2022 election the council of Praha 1 was run by ODS, TOP 09, Naše
# Praha 1 (ANO), Rezidenti 1 and the councillors elected for the Pirates'
# list. In 2026 two deputy mayors of that coalition, one elected for Rezidenti
# 1 and one for the Pirates' list, ran on a list of their own (Nezávislí
# z Jedničky), which is counted with the coalition. The Pirates' own list is
# kept apart: the list of 2022 was in the coalition, but its leader left it.
PRAGUE_1_BLOCS = {
    "townHall": ("ods", "top09", "nasePraha1", "rezidenti", "nezavisli"),
    "pirati": ("pirati",),
    "others": ("praha1Sobe", "stanKdu"),
}

PRAGUE_1_PARTS: Parts = (
    ("Hradčany", "malaStrana", ((1001, 1001),)),
    ("Malá Strana", "malaStrana", ((1002, 1005),)),
    ("Staré Město", "stareMesto", ((1007, 1008), (1010, 1012))),
    ("Josefov", "stareMesto", ((1009, 1009), (1013, 1013))),
    ("Nové Město", "noveMesto", ((1006, 1006), (1014, 1021))),
)
PRAGUE_1_GROUPS = {
    "malaStrana": "Malá Strana a Hradčany",
    "stareMesto": "Staré Město a Josefov",
    "noveMesto": "Nové Město",
}


def prague_1_key(name: str) -> Optional[str]:
    """Short name of a list on the ballot for the council of Praha 1."""
    upper = name.upper()
    if upper.startswith("PRAHA 1 SOBĚ"):
        return "praha1Sobe"
    if upper.startswith("OBČANSKÁ DEMOKRATICKÁ"):
        return "ods"
    if upper.startswith("TOP 09"):
        return "top09"
    # STAN and KDU-ČSL ran together both times, in 2022 as "My, co tady žijeme"
    if upper.startswith("MY, CO TADY ŽIJEME") or upper.startswith("STAROSTOVÉ, KDU-ČSL"):
        return "stanKdu"
    if upper.startswith("NAŠE PRAHA 1"):
        return "nasePraha1"  # ANO with local independents
    if upper.startswith("NEZÁVISLÍ Z JEDNIČKY"):
        return "nezavisli"
    if upper.startswith("MODRÁ PRO JEDNIČKU"):
        return "modra"
    if upper.startswith("REZIDENTI 1"):
        return "rezidenti"
    return group_key(name)


def _one_more_seat(seats: _SeatMath, key: str) -> Optional[dict]:
    """The fewest extra votes that give a list one more seat, and who would lose it."""
    current = seat_allocation(seats.votes, seats.seats)

    def with_more(count: float) -> Dict[str, float]:
        return seats.changed(**{key: count})

    moved = smallest_shift(
        with_more,
        lambda result: seat_allocation(result, seats.seats).get(key, 0) > current.get(key, 0),
        limit=max(seats.votes.values()),
        step=10,
    )
    if moved is None:
        return None
    after = seat_allocation(with_more(moved), seats.seats)
    return {
        "key": key,
        "seats": current.get(key, 0),
        "votes": moved,
        "voters": round(moved / seats.per_ballot),
        "from": next(name for name, count in current.items() if after.get(name, 0) < count),
    }


def prague_1_2026() -> dict:
    """The council of Praha 1: seats, how close each list was to one more,
    the two ballots of the same voters, precincts and neighbourhoods."""
    district = _District(PRAGUE_1, prague_1_key, PRAGUE_1_PARTS, PRAGUE_1_GROUPS)
    figures = district.figures()
    seats = _SeatMath(district.council, key_of=prague_1_key, rivals=PRAGUE_1_BLOCS["townHall"], step=10)
    margins = [_one_more_seat(seats, item["key"]) for item in figures["lists"]]
    return {
        **figures,
        "blocs": _bloc_totals(district.council, district.before, PRAGUE_1_BLOCS, prague_1_key),
        **seats.summary(),
        **_last_seat(seats),
        # For every list, the fewest extra votes for one more seat; from the closest
        "margins": sorted((item for item in margins if item), key=lambda item: item["votes"]),
    }

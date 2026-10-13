"""
Possible counting errors in the precinct results of municipal elections, for every list.

Reads the official results with the votes of every candidate in every precinct
(ČSÚ open data, downloaded on the first run) and writes six tables to
output/<election>/anomalies/ (a run for one council or one city writes to a
folder of its own there):

  prehled.csv    every council: how close its closest seat is, what was found
                 there, and whether putting the clear errors right would change
                 the seats or the people who hold them.
  mandaty.csv    how many votes each list was from winning or losing a seat
                 and from the five-percent threshold, next to the votes its
                 clear candidate errors add up to and the seats it would have
                 with those errors put right.
  poradi.csv     who holds the seats of each list, how few votes at one
                 candidate would seat somebody else, and the same with the
                 clear errors at candidates put right.
  kandidati.csv  single candidates whose votes in a precinct break the pattern
                 of their list there: a zero or a fraction among neighbours with
                 dozens of votes, or a multiple of them. These are visible in
                 the data as they are and need no estimate.
  okrsky.csv     precincts with unusually many or few votes counted per returned
                 envelope, and those whose valid ballots left almost no vote
                 unused, which is what too many votes or too few valid ballots
                 in the record look like.
  listky.csv     in cities with districts, where a voter gets two ballots: lists
                 that got far more or fewer votes on one ballot than the other
                 ballot of the same voters suggests.

The seats and the order of candidates are plain arithmetic and are computed for
every council. Looking for errors at candidates needs a pattern to break: most
voters marking a whole list, so that its candidates have nearly the same votes
in a precinct. That holds in cities and not in villages and small towns, where
people vote for names; councils where it does not hold, or which have too few
precincts to compare, are left out of that part and marked in prehled.csv.

kandidati.csv is evidence, okrsky.csv and listky.csv are hints: a precinct may
differ for a reason of the place, and only a recount of the ballots can tell.

Run from the repository root:

    uv run python research/precinct_anomalies.py                    # every council
    uv run python research/precinct_anomalies.py --city 554782      # Prague and its districts
    uv run python research/precinct_anomalies.py --council 500143   # Praha 5, with the findings printed
"""

import argparse
import io
import math
import re
import sys
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests

OPENDATA = "https://volby.gov.cz/opendata/{election}/{name}"
# Archives of the final results; ČSÚ puts the day of publication in the name
ARCHIVES = {"kv2026": {"data": "KV2026_data_20261011_xml.zip", "reg": "KV2026reg20261011_xml.zip"}}
VOTES = [f"HLASY_{number:02d}" for number in range(1, 71)]
TAG = re.compile(r"<([A-Z_0-9]+)>([^<]*)</\1>")

# A list shorter than this has no pattern to break
FEWEST_CANDIDATES = 9
# Fewer ballots marked for a whole list than this say nothing about one candidate
SMALLEST_PILE = 5
# Candidates are checked where a list's candidates have nearly the same votes
# in a precinct (this share of them within a quarter of the usual vote), which
# is what voting for whole lists looks like. Under it people vote for names,
# and a zero or a multiple of the neighbours is a result, not an error
EVEN_VOTES = 0.9
# A candidate's usual place against the neighbours is learned across precincts
PRECINCTS_FOR_CANDIDATES = 10
# A list under this share of the votes joins the others when ballots are compared
SMALL_LIST = 0.02
# Precincts a council needs for its two ballots to be compared, and for its
# precincts to be measured against each other
FEWEST_PRECINCTS = 16


def rows(archive: Path, member: str, row_tag: str, keep: Optional[List[str]] = None) -> pd.DataFrame:
    """Rows of one XML file inside an archive, read line by line; the files have hundreds of MB."""
    found, row = [], None
    wanted = set(keep) if keep else None
    with zipfile.ZipFile(archive) as content, content.open(member) as raw:
        for line in io.TextIOWrapper(raw, encoding="utf-8"):
            line = line.strip()
            if line == f"<{row_tag}>":
                row = {}
            elif line == f"</{row_tag}>":
                found.append(row)
                row = None
            elif row is not None:
                match = TAG.match(line)
                if match and (wanted is None or match.group(1) in wanted):
                    row[match.group(1)] = match.group(2)
    return pd.DataFrame(found)


def load(election: str) -> Dict[str, pd.DataFrame]:
    """Precinct forms, candidate votes, candidates, lists and councils of the whole country."""
    folder = Path("input") / election / "official"
    # The number goes up whenever what is kept changes, so that an older file is not read
    stored = folder / "republic-1.pkl"
    if stored.exists():
        return pd.read_pickle(stored)
    folder.mkdir(parents=True, exist_ok=True)
    paths = {}
    for kind, name in ARCHIVES[election].items():
        paths[kind] = folder / name
        if not paths[kind].exists():
            url = OPENDATA.format(election=election, name=name)
            print(f"Stahuji {url}")
            with requests.get(url, stream=True, timeout=300) as response:
                response.raise_for_status()
                with open(paths[kind], "wb") as target:
                    for chunk in response.iter_content(chunk_size=1 << 20):
                        target.write(chunk)

    print("Čtu výsledky okrsků a hlasy kandidátů (pár minut, jen poprvé)")
    numbers = {
        "forms": ["VYD_OBALKY", "ODEVZ_OBAL", "PLAT_LISTKY", "PL_HL_CELK"],
        "votes": VOTES + ["POC_HLASU", "POR_STR_HL"],
        "candidates": ["POR_STR_HL", "PORCISLO", "POCHLASU", "PORADIMAND", "PORADINAHR"],
        "lists": ["POR_STR_HL", "HLASY_STR", "MAND_STR"],
        "councils": ["MANDATY", "OBVODY"],
    }
    data = {
        "forms": rows(paths["data"], "kvt3.xml", "KV_T3_ROW", numbers["forms"] + ["OBEC", "OKRSEK", "TYPZASTUP", "KODZASTUP"]),
        "votes": rows(paths["data"], "kvhl.xml", "KV_HL_ROW", numbers["votes"] + ["OBEC", "OKRSEK", "TYPZASTUP"]),
        "candidates": rows(
            paths["reg"], "kvrk.xml", "KV_REGKAND_ROW", numbers["candidates"] + ["KODZASTUP", "JMENO", "PRIJMENI", "PLATNOST", "MANDAT"]
        ),
        "lists": rows(paths["reg"], "kvros.xml", "KV_ROS_ROW", numbers["lists"] + ["KODZASTUP", "ZKRATKAO30", "PROCHLSTR"]),
        "councils": rows(paths["reg"], "kvrzcoco.xml", "KV_RZCOCO_ROW", numbers["councils"] + ["KODZASTUP", "NAZEVZAST"]).drop_duplicates("KODZASTUP"),
    }
    for name, columns in numbers.items():
        # A precinct that did not vote, or a council with no election, leaves fields empty
        data[name][columns] = data[name][columns].apply(pd.to_numeric, errors="coerce").fillna(0).astype(int)
    data["lists"]["PROCHLSTR"] = pd.to_numeric(data["lists"]["PROCHLSTR"], errors="coerce").fillna(0.0)
    # Candidate votes do not say which council they are for; the precinct form does
    key = ["OBEC", "OKRSEK", "TYPZASTUP"]
    data["votes"] = data["votes"].merge(data["forms"][key + ["KODZASTUP"]], on=key, how="left")
    for name in ("forms", "votes"):
        data[name]["precinct"] = data[name].OBEC + "-" + data[name].OKRSEK
    pd.to_pickle(data, stored)
    return data


class Results:
    """The country's results, cut by council once so that each council is at hand."""

    def __init__(self, data: Dict[str, pd.DataFrame]):
        self.councils = data["councils"].set_index("KODZASTUP")
        self.forms = dict(tuple(data["forms"].groupby("KODZASTUP")))
        self.votes = dict(tuple(data["votes"].groupby("KODZASTUP")))
        self.lists = dict(tuple(data["lists"].groupby("KODZASTUP")))
        self.candidates = dict(tuple(data["candidates"].groupby("KODZASTUP")))
        # A district of a city: all its precincts also vote for one other council
        places = data["forms"].groupby("precinct").KODZASTUP.agg(list)
        both = places[places.str.len() == 2]
        self.city_of: Dict[str, str] = {}
        sizes = data["forms"].groupby("KODZASTUP").size()
        for first, second in both:
            district, city = (first, second) if sizes[first] < sizes[second] else (second, first)
            self.city_of[district] = city

    def name(self, code: str) -> str:
        return self.councils.at[code, "NAZEVZAST"] if code in self.councils.index else code

    def ballot(self, code: str, within: Optional[str] = None) -> "Ballot":
        return Ballot(self, code, within)


class Ballot:
    """The ballot of one council, in all its precincts or only in those of one
    of the city's districts (`within`)."""

    def __init__(self, results: Results, code: str, within: Optional[str] = None):
        self.council, self.within = code, within
        self.name = results.name(code)
        self.seats = int(results.councils.at[code, "MANDATY"])
        forms = results.forms[code].set_index("precinct").sort_index()
        votes = results.votes.get(code, pd.DataFrame(columns=["precinct", "POR_STR_HL", "POC_HLASU"] + VOTES))
        if within:
            inside = set(results.forms[within].precinct)
            forms = forms[forms.index.isin(inside)]
        self.forms = forms[(forms.ODEVZ_OBAL > 0) & (forms.PLAT_LISTKY > 0)]
        self.votes = votes[votes.precinct.isin(self.forms.index)]
        self.lists = results.lists[code].set_index("POR_STR_HL").sort_index()
        candidates = results.candidates[code]
        # Places on the ballot, and candidates still standing: a withdrawn one
        # keeps the place but cannot take a seat and does not count for the threshold
        self.places = candidates.groupby("POR_STR_HL").PORCISLO.max()
        self.lengths = candidates[candidates.PLATNOST == "A"].groupby("POR_STR_HL").size().reindex(self.places.index).fillna(0).astype(int)

    def by_list(self) -> pd.DataFrame:
        """Votes of every list in every precinct."""
        return self.votes.pivot(index="precinct", columns="POR_STR_HL", values="POC_HLASU").reindex(self.forms.index).fillna(0)

    def list_name(self, number: int) -> str:
        return self.lists.at[number, "ZKRATKAO30"] if number in self.lists.index else f"Kandidátka {number}"


# ---------------------------------------------------------------------------
# Single candidates
# ---------------------------------------------------------------------------


def piles(matrix: np.ndarray) -> np.ndarray:
    """Ballots marked for the whole list in each precinct: the usual vote of
    its candidates, leaving out those with next to none."""
    # Candidates with any votes are the measure: a record may leave most of a
    # list empty and fill in only those who also got votes of their own
    voted = np.where(matrix > 0, matrix, np.nan)
    with np.errstate(all="ignore"):
        upper = np.where((matrix > 0).sum(axis=1) >= SMALLEST_PILE, np.nanmedian(voted, axis=1), 0.0)
        usual = np.where(matrix >= 0.5 * upper[:, None], matrix, np.nan)
        return np.nan_to_num(np.nanmedian(usual, axis=1))


def neighbours(matrix: np.ndarray, pile: np.ndarray, reach: int = 4) -> np.ndarray:
    """Median vote of the candidates next to each one on the list, without the
    candidate and without neighbours that have next to no votes themselves."""
    usual = np.where(matrix >= 0.5 * pile[:, None], matrix, np.nan)
    width = matrix.shape[1]
    shifted = np.full((2 * reach, *matrix.shape), np.nan)
    for layer, step in enumerate(step for step in range(-reach, reach + 1) if step != 0):
        source = slice(max(0, step), width + min(0, step))
        target = slice(max(0, -step), width + min(0, -step))
        shifted[layer][:, target] = usual[:, source]
    with np.errstate(all="ignore"):
        around = np.nanmedian(shifted, axis=0)
    return np.where(np.isnan(around), pile[:, None], around)


def breaks_of_pattern(matrix: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Candidates of one list (columns) far from the pattern of their list in
    a precinct (rows): (missing, extra, expected votes, list mostly empty).

    The list is taken across all its precincts, so that a candidate who is
    usually ahead of the neighbours, or behind them at the end of the list, is
    not flagged."""
    count = matrix.shape[1]
    pile = piles(matrix)
    around = neighbours(matrix, pile)
    whole = (pile >= SMALLEST_PILE) & ((matrix >= 0.5 * pile[:, None]).mean(axis=1) > 0.95)
    relative = matrix / np.maximum(around, 1)
    if whole.sum() >= 10:
        # Where the candidate usually stands against the neighbours, and how much that varies
        usual = np.median(relative[whole], axis=0)
        spread = 1.4826 * np.median(np.abs(relative[whole] - usual), axis=0)
    else:
        usual, spread = np.ones(count), np.full(count, 0.1)
    expected = around * usual
    standing = (relative - usual) / np.maximum(spread, 0.03)
    enough = (pile >= SMALLEST_PILE)[:, None]
    missing = enough & (matrix <= 0.5 * expected) & (expected - matrix >= 5)
    extra = enough & (matrix - expected >= np.maximum(10, 0.4 * pile[:, None])) & (standing >= 6)
    mostly_empty = (matrix < 0.5 * pile[:, None]).mean(axis=1) > 0.5
    return missing, extra, expected, mostly_empty


def candidate_findings(results: Results, codes: List[str]) -> pd.DataFrame:
    """Candidates with far fewer or far more votes in a precinct than the
    pattern of their list there, in the councils given."""
    found = []
    for code in codes:
        votes, candidates = results.votes.get(code), results.candidates.get(code)
        if votes is None or candidates is None:
            continue
        names = {
            (number, order): (f"{first} {last}", valid)
            for number, order, first, last, valid in zip(candidates.POR_STR_HL, candidates.PORCISLO, candidates.JMENO, candidates.PRIJMENI, candidates.PLATNOST)
        }
        length = candidates.groupby("POR_STR_HL").PORCISLO.max()
        list_names = results.lists[code].set_index("POR_STR_HL").ZKRATKAO30
        for number, part in votes.groupby("POR_STR_HL"):
            count = int(length.get(number, 0))
            if count < FEWEST_CANDIDATES:
                continue
            matrix = part[VOTES].to_numpy(dtype=float)[:, :count]
            missing, extra, expected, mostly_empty = breaks_of_pattern(matrix)
            for kind, mask in (("chybí", missing), ("navíc", extra)):
                for row, column in zip(*np.nonzero(mask)):
                    name, valid = names.get((number, column + 1), ("?", "A"))
                    if valid != "A":  # a withdrawn candidate has no votes anywhere
                        continue
                    record = part.iloc[row]
                    window = range(max(0, column - 3), min(count, column + 4))
                    found.append(
                        {
                            "zastupitelstvo": code,
                            "obec": record.OBEC,
                            "okrsek": record.OKRSEK,
                            "cislo_kandidatky": number,
                            "kandidatka": list_names.get(number, ""),
                            "poradi": column + 1,
                            "kandidat": name,
                            "hlasy": int(matrix[row, column]),
                            "obvykle": round(float(expected[row, column])),
                            "rozdil": round(float(matrix[row, column] - expected[row, column])),
                            "druh": kind,
                            # Then the pile is read from the few candidates who have votes, which is less certain
                            "vetsina_kandidatky_prazdna": bool(mostly_empty[row]),
                            "okoli": " ".join(f"[{int(matrix[row, i])}]" if i == column else str(int(matrix[row, i])) for i in window),
                        }
                    )
    columns = ["zastupitelstvo", "obec", "okrsek", "cislo_kandidatky", "kandidatka", "poradi", "kandidat", "hlasy", "obvykle", "rozdil", "druh"]
    result = pd.DataFrame(found, columns=columns + ["vetsina_kandidatky_prazdna", "okoli"])
    # A candidate ahead of the neighbours in several precincts is popular there, not mistyped
    result["stejny_kandidat_v_okrscich"] = result.groupby(["zastupitelstvo", "cislo_kandidatky", "poradi", "druh"]).okrsek.transform("size")
    # Several times the neighbours in a single precinct is a slip of the pen rather than a local favourite
    result["zjevny_preklep"] = (result.druh == "navíc") & (result.stejny_kandidat_v_okrscich == 1) & (result.hlasy >= 3 * result.obvykle)
    return result.sort_values(["zastupitelstvo", "obec", "okrsek", "cislo_kandidatky", "poradi"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Whole precincts
# ---------------------------------------------------------------------------


def robust(values: pd.Series) -> pd.Series:
    """Distance from the median in robust standard deviations."""
    middle = values.median()
    spread = 1.4826 * (values - middle).abs().median()
    return (values - middle) / spread if spread > 0 else values * 0


def precinct_table(ballot: Ballot) -> pd.DataFrame:
    """Votes counted per returned envelope, and whole-list ballots against valid ballots."""
    forms = ballot.forms
    pile_sum = pd.Series(0.0, index=forms.index)
    near = weight = 0.0
    for number, part in ballot.votes.groupby("POR_STR_HL"):
        count = int(ballot.places.get(number, 0))
        if count < FEWEST_CANDIDATES:
            continue
        matrix = part[VOTES].to_numpy(dtype=float)[:, :count]
        pile = piles(matrix)
        counted = pile >= SMALLEST_PILE
        if counted.any():
            close = (np.abs(matrix[counted] - pile[counted, None]) <= np.maximum(2, 0.25 * pile[counted, None])).mean(axis=1)
            near += float((close * pile[counted]).sum() * count)
            weight += float(pile[counted].sum() * count)
        # A short list fills only a part of a ballot
        pile_sum = pile_sum.add(pd.Series(piles(matrix) * min(count, ballot.seats) / ballot.seats, index=part.precinct.to_numpy()), fill_value=0)
    table = pd.DataFrame(
        {
            "zastupitelstvo": ballot.council,
            "nazev": ballot.name,
            "obec": forms.OBEC,
            "okrsek": forms.OKRSEK,
            "obalky": forms.ODEVZ_OBAL,
            "nevracene_obalky": forms.VYD_OBALKY - forms.ODEVZ_OBAL,
            "platne_listky": forms.PLAT_LISTKY,
            "neplatne_procent": ((forms.ODEVZ_OBAL - forms.PLAT_LISTKY) / forms.ODEVZ_OBAL * 100).round(2),
            "hlasy": forms.PL_HL_CELK,
            # 1 would mean every envelope held a ballot with all its votes used
            "vyuziti_hlasu": (forms.PL_HL_CELK / ballot.seats / forms.ODEVZ_OBAL).round(3),
            # 1 would mean no valid ballot left a single vote unused
            "vyuziti_platnych_listku": (forms.PL_HL_CELK / ballot.seats / forms.PLAT_LISTKY).round(3),
            "hromadky": pile_sum.reindex(forms.index).round(1),
        }
    ).reset_index(drop=True)
    table["hromadky_na_platny_listek"] = (table.hromadky / table.platne_listky).round(3)
    # Precincts are measured against the others of the same council, where there are enough of them
    measured = len(table) >= FEWEST_PRECINCTS
    table["odchylka"] = robust(table.vyuziti_hlasu).round(1) if measured else np.nan
    table["listku_navic"] = ((table.vyuziti_hlasu - table.vyuziti_hlasu.median()) * table.obalky).round(1) if measured else np.nan
    reasons = []
    for row in table.itertuples():
        reason = []
        if row.odchylka >= 2:
            reason.append("mnoho hlasů na obálku")
        if row.odchylka <= -3:
            reason.append("málo hlasů na obálku")
        if row.hromadky_na_platny_listek > 1:
            reason.append("víc lístků pro celé kandidátky než platných lístků")
        elif measured and row.vyuziti_platnych_listku >= 0.995 and row.platne_listky >= 150:
            reason.append("platné lístky skoro bez nevyužitého hlasu")
        if row.nevracene_obalky >= 10:
            reason.append("nevrácené obálky")
        reasons.append("; ".join(reason))
    table["proc"] = reasons
    # How alike the votes of a list's candidates are in a precinct, from 0 to 1.
    # Near 1 voters mark whole lists; lower, they vote for names
    table.attrs["evenness"] = near / weight if weight else 0.0
    return table


# ---------------------------------------------------------------------------
# One ballot against the other
# ---------------------------------------------------------------------------


def ballots_of_lists(ballot: Ballot, most: int) -> pd.DataFrame:
    """Ballots' worth of votes of the larger lists per valid ballot; the rest together."""
    table = ballot.by_list() / ballot.seats
    share = table.sum() / table.sum().sum()
    large = share[share >= SMALL_LIST].sort_values(ascending=False).index[:most]
    grouped = table[large].copy()
    grouped["ostatní"] = table.drop(columns=large).sum(axis=1)
    return grouped.div(ballot.forms.PLAT_LISTKY, axis=0)


def left_out(target: np.ndarray, known: np.ndarray, weight: np.ndarray) -> np.ndarray:
    """What the other precincts predict for each one, by weighted least squares."""
    design = np.column_stack([np.ones(len(known)), known]) * np.sqrt(weight)[:, None]
    with np.errstate(all="ignore"):
        inverse = np.linalg.pinv(design.T @ design)
        fitted = design @ (inverse @ design.T @ (target * np.sqrt(weight)))
        leverage = np.einsum("ij,jk,ik->i", design, inverse, design)
    residual = (target * np.sqrt(weight) - fitted) / np.clip(1 - leverage, 0.05, None)
    return target - residual / np.sqrt(weight)


def ballot_findings(district: Ballot, city: Ballot) -> pd.DataFrame:
    """Lists with far more or fewer ballots than the other ballot of the same
    precinct suggests. Both ballots go into one envelope, so the voters are the same."""
    precincts = district.forms.index.intersection(city.forms.index)
    if len(precincts) < FEWEST_PRECINCTS:
        return pd.DataFrame()
    most = max(2, len(precincts) // 5 - 1)
    found = []
    for ballot, other in ((district, city), (city, district)):
        own = ballots_of_lists(ballot, 30).loc[precincts]
        known = ballots_of_lists(other, most).loc[precincts]
        valid = ballot.forms.PLAT_LISTKY.loc[precincts].to_numpy(dtype=float)
        for number in own.columns:
            if number == "ostatní":
                continue
            share = own[number].to_numpy()
            expected = left_out(share, known.to_numpy(), valid)
            scaled = (share - expected) * np.sqrt(valid)
            spread = 1.4826 * np.median(np.abs(scaled - np.median(scaled)))
            if spread == 0:
                continue
            found.append(
                pd.DataFrame(
                    {
                        "zastupitelstvo": ballot.council,
                        "nazev": ballot.name,
                        "obec": ballot.forms.OBEC.loc[precincts].to_numpy(),
                        "okrsek": ballot.forms.OKRSEK.loc[precincts].to_numpy(),
                        "cislo_kandidatky": number,
                        "kandidatka": ballot.list_name(number),
                        "listku": (share * valid).round(1),
                        "cekano_listku": (expected * valid).round(1),
                        "rozdil_listku": ((share - expected) * valid).round(1),
                        "rozdil_hlasu": ((share - expected) * valid * ballot.seats).round(),
                        "odchylka": (scaled / spread).round(1),
                    }
                )
            )
    if not found:
        return pd.DataFrame()
    table = pd.concat(found, ignore_index=True)
    return table[(table.odchylka.abs() >= 3.5) & (table.rozdil_listku.abs() >= 6)]


# ---------------------------------------------------------------------------
# Seats
# ---------------------------------------------------------------------------


def threshold(votes: pd.Series, lengths: pd.Series, seats: int) -> pd.Series:
    """Votes each list needs to take part in the division of seats.

    It is five percent of all votes; a list with fewer candidates than there
    are seats is measured against a total smaller in that proportion. When
    fewer than two lists pass, or the lists that pass have too few candidates
    to fill more than half of the seats, the bar goes down a percent at a time."""
    length = lengths.reindex(votes.index).fillna(seats).clip(upper=seats)
    base = votes.sum() * length / seats
    for percent in (5, 4, 3, 2, 1, 0):
        needed = percent / 100 * base
        passing = votes >= needed
        if passing.sum() >= min(2, len(votes)) and length[passing].sum() >= seats // 2 + 1:
            break
    return needed


def seat_order(votes: pd.Series, lengths: pd.Series, seats: int) -> list:
    """D'Hondt quotients of the lists over the threshold, from the largest. A
    list cannot win more seats than it has candidates."""
    over = votes[votes >= threshold(votes, lengths, seats)]
    return sorted(
        ((count / divisor, number, divisor) for number, count in over.items() for divisor in range(1, min(seats, int(lengths.get(number, seats))) + 1)),
        key=lambda entry: (-entry[0], -over[entry[1]], entry[1]),
    )


def seats_of(votes: pd.Series, lengths: pd.Series, seats: int) -> pd.Series:
    won = pd.Series([number for _, number, _ in seat_order(votes, lengths, seats)[:seats]], dtype=int).value_counts()
    return won.reindex(votes.index).fillna(0).astype(int)


def seat_margins(ballot: Ballot) -> pd.DataFrame:
    """Votes each list was from one more seat, from one fewer and from the threshold."""
    lists, seats, lengths = ballot.lists, ballot.seats, ballot.lengths
    votes = lists.HLASY_STR.astype(float)
    order = seat_order(votes, lengths, seats)
    last = order[min(seats, len(order)) - 1][0] if order else 0.0
    first_out = order[seats][0] if len(order) > seats else 0.0
    mine = seats_of(votes, lengths, seats)
    above = votes - threshold(votes, lengths, seats)
    table = pd.DataFrame(
        {
            "zastupitelstvo": ballot.council,
            "nazev": ballot.name,
            "cislo_kandidatky": lists.index,
            "kandidatka": lists.ZKRATKAO30,
            "hlasy": lists.HLASY_STR,
            "procent": lists.PROCHLSTR,
            "mandaty": lists.MAND_STR,
            # Below zero: votes the list was short of the threshold
            "nad_hranici": np.floor(above).astype(int),
        }
    )
    full = mine.to_numpy() >= lengths.reindex(lists.index).fillna(seats).to_numpy()
    table["k_dalsimu_mandatu"] = np.where((above >= 0) & ~full, np.ceil(last * (mine + 1) - votes), np.nan)
    table["ke_ztrate_mandatu"] = np.where((mine > 0) & (first_out > 0), np.ceil(votes - first_out * mine), np.nan)
    # A list just over the threshold loses all its seats at once by falling under it
    table["ke_ztrate_mandatu"] = np.where(mine > 0, np.fmin(table.ke_ztrate_mandatu, np.floor(above) + 1), table.ke_ztrate_mandatu)
    table["mandaty_souhlasi_s_csu"] = bool((mine.to_numpy() == lists.MAND_STR.to_numpy()).all())
    # Equal quotients at the last seat are decided by lot, which no arithmetic can repeat
    table["o_mandatu_rozhodl_los"] = len(order) > seats and math.isclose(order[seats - 1][0], order[seats][0])
    return table.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Order of candidates within a list
# ---------------------------------------------------------------------------


def candidate_order(votes: np.ndarray) -> List[int]:
    """Candidates of one list, as positions in `votes` (the order on the
    ballot), in the order they take the list's seats: those with at least a
    tenth more votes than the list's average by their votes, then the rest as
    printed on the ballot.

    The average is cut to a whole number. The law does not say so, but it is
    what gives the official order; the exact average gets some lists wrong."""
    # In whole numbers: 1.1 * 90 is a hair over 99 in floating point
    average = math.floor(votes.sum() / len(votes))
    ahead = [place for place in range(len(votes)) if 10 * votes[place] >= 11 * average]
    ahead.sort(key=lambda place: (-votes[place], place))
    taken = set(ahead)
    return ahead + [place for place in range(len(votes)) if place not in taken]


def closest_change(votes: np.ndarray, seats: int) -> Tuple[float, Optional[int], int]:
    """Fewest votes one candidate would have to gain or lose for the list's
    seats to go to other people: (votes, position of that candidate, +1 or -1)."""
    best: Tuple[float, Optional[int], int] = (np.nan, None, 0)
    if seats <= 0 or seats >= len(votes):
        return best
    now = set(candidate_order(votes)[:seats])

    def changes(place: int, shift: float) -> bool:
        moved = votes.copy()
        moved[place] += shift
        return set(candidate_order(moved)[:seats]) != now

    for place in range(len(votes)):
        sign = -1 if place in now else 1
        most = int(votes[place]) if sign < 0 else int(votes.max()) + 1
        if most < 1 or not changes(place, sign * most):
            continue
        low, high = 1, most
        while low < high:
            middle = (low + high) // 2
            low, high = (low, middle) if changes(place, sign * middle) else (middle + 1, high)
        if not best[0] <= low:
            best = (low, place, sign)
    return best


def order_table(results: Results, findings: pd.DataFrame, margins: pd.DataFrame) -> pd.DataFrame:
    """For every list with a seat: how few votes would seat other people, and
    who would sit with the clear errors at candidates put right."""
    corrections: Dict[tuple, float] = {}
    clear = findings[(findings.druh == "chybí") | findings.zjevny_preklep]
    for code, number, place, difference in zip(clear.zastupitelstvo, clear.cislo_kandidatky, clear.poradi, clear.rozdil):
        corrections[(code, number, place)] = corrections.get((code, number, place), 0) - difference
    found = []
    for row in margins.itertuples():
        if row.mandaty == 0 and row.mandaty_po_oprave == 0:
            continue
        part = results.candidates[row.zastupitelstvo]
        part = part[(part.POR_STR_HL == row.cislo_kandidatky) & (part.PLATNOST == "A")].sort_values("PORCISLO")
        if part.empty:
            continue
        names = (part.JMENO + " " + part.PRIJMENI).to_numpy()
        places = part.PORCISLO.to_numpy()
        votes = part.POCHLASU.to_numpy(dtype=float)
        official = list(part[part.MANDAT == "A"].sort_values("PORADIMAND").PORCISLO) + list(part[part.MANDAT != "A"].sort_values("PORADINAHR").PORCISLO)
        fixed = votes + np.array([corrections.get((row.zastupitelstvo, row.cislo_kandidatky, place), 0.0) for place in places])

        def described(count: float, place: Optional[int], sign: int) -> str:
            return "" if place is None else f"{names[place]} {'+' if sign > 0 else '−'}{int(count)}"

        before, after = set(candidate_order(votes)[: row.mandaty]), set(candidate_order(fixed)[: row.mandaty_po_oprave])
        margin, margin_fixed = closest_change(votes, row.mandaty), closest_change(fixed, row.mandaty_po_oprave)
        found.append(
            {
                "zastupitelstvo": row.zastupitelstvo,
                "nazev": row.nazev,
                "cislo_kandidatky": row.cislo_kandidatky,
                "kandidatka": row.kandidatka,
                "mandaty": row.mandaty,
                # A list without a seat has no official order to compare with
                "poradi_souhlasi_s_csu": row.mandaty == 0 or [places[place] for place in candidate_order(votes)] == official,
                # The fewest votes at one candidate that would seat other people
                "nejmensi_zmena_hlasu": margin[0],
                "nejmensi_zmena_u": described(*margin),
                "opraveno_hlasu": int(np.abs(fixed - votes).sum()),
                "mandaty_po_oprave": row.mandaty_po_oprave,
                "po_oprave_nove_zvoleni": ", ".join(names[place] for place in sorted(after - before)),
                "po_oprave_nezvoleni": ", ".join(names[place] for place in sorted(before - after)),
                "nejmensi_zmena_po_oprave": margin_fixed[0],
                "nejmensi_zmena_po_oprave_u": described(*margin_fixed),
            }
        )
    return pd.DataFrame(found)


# ---------------------------------------------------------------------------
# All together
# ---------------------------------------------------------------------------


def analyse(results: Results, codes: List[str]) -> Dict[str, pd.DataFrame]:
    """The six tables for the councils given."""
    skipped = [code for code in codes if results.councils.at[code, "OBVODY"] > 0 or code not in results.votes or code not in results.candidates]
    codes = [code for code in codes if code not in skipped]
    ballots = {code: results.ballot(code) for code in codes}
    precincts = {code: precinct_table(ballot) for code, ballot in ballots.items()}
    shares = {code: table.attrs["evenness"] for code, table in precincts.items()}
    # Candidates are checked only where voters mark whole lists and there are precincts to compare
    patterned = [code for code in codes if shares[code] >= EVEN_VOTES and len(precincts[code]) >= PRECINCTS_FOR_CANDIDATES]
    candidates = candidate_findings(results, patterned)

    margins = pd.concat([seat_margins(ballot) for ballot in ballots.values()], ignore_index=True)
    pairs = list(zip(margins.zastupitelstvo, margins.cislo_kandidatky))
    for column, chosen in (("chybi_u_kandidatu", candidates.druh == "chybí"), ("navic_preklepem", candidates.zjevny_preklep)):
        total = candidates[chosen].groupby(["zastupitelstvo", "cislo_kandidatky"]).rozdil.sum().abs()
        margins[column] = [int(total.get(pair, 0)) for pair in pairs]
    # Seats once the missing votes are added and the slips of the pen taken away
    margins["mandaty_po_oprave"] = margins.mandaty
    corrected = margins[(margins.chybi_u_kandidatu > 0) | (margins.navic_preklepem > 0)].zastupitelstvo.unique()
    for code in corrected:
        own = margins[margins.zastupitelstvo == code]
        votes = pd.Series((own.hlasy + own.chybi_u_kandidatu - own.navic_preklepem).to_numpy(dtype=float), index=own.cislo_kandidatky.to_numpy())
        margins.loc[own.index, "mandaty_po_oprave"] = seats_of(votes, ballots[code].lengths, ballots[code].seats).to_numpy()
    order = order_table(results, candidates, margins)

    between = []
    for code in codes:
        city = results.city_of.get(code)
        if city and city in results.votes:
            between.append(ballot_findings(ballots[code], results.ballot(city, within=code)))
    between = [part for part in between if len(part)]
    columns = ["zastupitelstvo", "nazev", "obec", "okrsek", "cislo_kandidatky", "kandidatka", "listku", "cekano_listku", "rozdil_listku", "rozdil_hlasu", "odchylka"]
    between = pd.concat(between, ignore_index=True) if between else pd.DataFrame(columns=columns)

    by_council = {name: dict(tuple(table.groupby("zastupitelstvo"))) for name, table in (("margins", margins), ("order", order), ("candidates", candidates), ("between", between))}
    summary = []
    for code in codes:
        own = by_council["margins"][code]
        lists_order = by_council["order"].get(code, order.iloc[:0])
        # A list just under the threshold is as close to seats as one just short of a quotient
        under = -own.nad_hranici[own.nad_hranici < 0]
        closest = min(own[["k_dalsimu_mandatu", "ke_ztrate_mandatu"]].min().min(), under.min() if len(under) else np.inf)
        found = by_council["candidates"].get(code, candidates.iloc[:0])
        lists = by_council["between"].get(code, between.iloc[:0])
        flagged = precincts[code][precincts[code].proc != ""]
        largest = max(
            float(own.chybi_u_kandidatu.max()),
            float(own.navic_preklepem.max()),
            float(lists.rozdil_hlasu.abs().max()) if len(lists) else 0.0,
            float((flagged.listku_navic.abs() * ballots[code].seats).max()) if flagged.listku_navic.notna().any() else 0.0,
        )
        moved = own[own.mandaty_po_oprave != own.mandaty]
        people = lists_order[(lists_order.po_oprave_nove_zvoleni != "") | (lists_order.po_oprave_nezvoleni != "")] if len(lists_order) else lists_order
        tight = lists_order.sort_values("nejmensi_zmena_po_oprave").head(1) if len(lists_order) else lists_order
        summary.append(
            {
                "zastupitelstvo": code,
                "nazev": results.name(code),
                "mesto": results.name(results.city_of[code]) if code in results.city_of else "",
                "mandatu": ballots[code].seats,
                "okrsku": len(precincts[code]),
                "rovnomernost_hlasu_kandidatu": round(shares[code], 2),
                "kandidati_kontrolovani": code in patterned,
                "mandaty_souhlasi_s_csu": bool(own.mandaty_souhlasi_s_csu.all()),
                "o_mandatu_rozhodl_los": bool(own.o_mandatu_rozhodl_los.all()),
                "poradi_souhlasi_s_csu": bool(lists_order.poradi_souhlasi_s_csu.all()) if len(lists_order) else True,
                "nejtesnejsi_mandat_hlasu": closest if np.isfinite(closest) else np.nan,
                "nejtesnejsi_poradi_hlasu": lists_order.nejmensi_zmena_po_oprave.min() if len(lists_order) else np.nan,
                "nejtesnejsi_poradi_u": "" if not len(tight) or tight.nejmensi_zmena_po_oprave_u.iloc[0] == "" else f"{tight.kandidatka.iloc[0]}: {tight.nejmensi_zmena_po_oprave_u.iloc[0]}",
                "kandidatu_s_chybou": len(found),
                "nejvic_chybi_jedne_kandidatce": int(own.chybi_u_kandidatu.max()),
                "kandidatek_mimo_druhy_listek": len(lists),
                "okrsku_s_priznakem": len(flagged),
                "nejvetsi_nalez_hlasu": round(largest),
                "nalez_k_mandatu": round(largest / closest, 2) if np.isfinite(closest) and closest > 0 else np.nan,
                # What adding the missing votes and undoing the slips of the pen would do
                "zmena_mandatu_po_oprave": ", ".join(f"{row.kandidatka} {row.mandaty_po_oprave - row.mandaty:+d}" for row in moved.itertuples()),
                "jini_zvoleni_po_oprave": "; ".join(f"{row.kandidatka}: +{row.po_oprave_nove_zvoleni} / −{row.po_oprave_nezvoleni}" for row in people.itertuples()),
            }
        )
    summary = pd.DataFrame(summary).sort_values(
        ["zmena_mandatu_po_oprave", "jini_zvoleni_po_oprave", "nalez_k_mandatu"], key=lambda column: column != "" if column.dtype == object else column, ascending=False
    )
    return {
        "prehled": summary,
        "mandaty": margins,
        "poradi": order,
        "kandidati": candidates,
        "okrsky": pd.concat(precincts.values(), ignore_index=True) if precincts else pd.DataFrame(),
        "listky": between,
        "vynechano": pd.DataFrame({"zastupitelstvo": skipped, "nazev": [results.name(code) for code in skipped]}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--council", help="Kód zastupitelstva (obce nebo městské části); vypíše i jednotlivé nálezy")
    parser.add_argument("--city", help="Kód členěného města: projde město a jeho části")
    parser.add_argument("--election", default="kv2026", choices=sorted(ARCHIVES))
    args = parser.parse_args()
    pd.set_option("display.width", 250, "display.max_columns", 30, "display.max_rows", 200, "display.max_colwidth", 70)

    results = Results(load(args.election))
    codes = sorted(results.councils.index)
    if args.council:
        codes = [args.council]
    elif args.city:
        codes = [args.city] + sorted(code for code, city in results.city_of.items() if city == args.city)
    missing = [code for code in codes if code not in results.councils.index]
    if missing:
        print(f"Zastupitelstvo {missing[0]} v datech není.")
        return 1

    tables = analyse(results, codes)
    folder = Path("output") / args.election / "anomalies" / (args.council or args.city or "")
    folder.mkdir(parents=True, exist_ok=True)
    for name, table in tables.items():
        table.to_csv(folder / f"{name}.csv", index=False)

    summary, margins, order = tables["prehled"], tables["mandaty"], tables["poradi"]
    if len(tables["vynechano"]):
        print(f"Vynecháno (více volebních obvodů nebo bez hlasování): {', '.join(tables['vynechano'].nazev)}")
    print(f"\nZastupitelstev: {len(summary)}, z toho s kontrolou kandidátů: {int(summary.kandidati_kontrolovani.sum())}")
    differ = summary[~summary.mandaty_souhlasi_s_csu]
    print(
        f"Výpočet mandátů se neshoduje s ČSÚ u {len(differ)} zastupitelstev (z toho u {int(differ.o_mandatu_rozhodl_los.sum())} rozhodl o posledním mandátu los), "
        f"pořadí kandidátů u {int((~summary.poradi_souhlasi_s_csu).sum())}."
    )
    shown = ["nazev", "mesto", "nejtesnejsi_mandat_hlasu", "kandidatu_s_chybou", "nejvetsi_nalez_hlasu", "zmena_mandatu_po_oprave", "jini_zvoleni_po_oprave"]
    changed = summary[(summary.zmena_mandatu_po_oprave != "") | (summary.jini_zvoleni_po_oprave != "")]
    print("\nKde by oprava zjevných chyb u kandidátů změnila mandáty nebo zvolené:")
    print(changed[shown].to_string(index=False) if len(changed) else "nikde")
    if not args.council:
        rest = summary[summary.kandidati_kontrolovani & ~summary.index.isin(changed.index)]
        print("\nDalší zastupitelstva podle největšího nálezu proti nejtěsnějšímu mandátu:")
        print(rest[shown[:5] + ["nalez_k_mandatu"]].head(20).to_string(index=False))
    else:
        print("\nMandáty a kolik hlasů chybí u kandidátů každé kandidátky:")
        print(margins[["kandidatka", "hlasy", "mandaty", "nad_hranici", "k_dalsimu_mandatu", "ke_ztrate_mandatu", "chybi_u_kandidatu", "navic_preklepem", "mandaty_po_oprave"]].to_string(index=False))
        print("\nPořadí uvnitř kandidátek: nejmenší změna hlasů jednoho kandidáta, která by zvolila někoho jiného:")
        columns = ["kandidatka", "mandaty", "nejmensi_zmena_u", "opraveno_hlasu", "po_oprave_nove_zvoleni", "po_oprave_nezvoleni", "nejmensi_zmena_po_oprave_u"]
        print(order[columns].to_string(index=False) if len(order) else "nic")
        okrsky = tables["okrsky"]
        for title, table, columns in (
            ("Kandidáti mimo vzor své kandidátky", tables["kandidati"], ["okrsek", "kandidatka", "poradi", "kandidat", "hlasy", "obvykle", "druh", "okoli"]),
            ("Kandidátky mimo to, co odpovídá druhému lístku", tables["listky"], ["okrsek", "nazev", "kandidatka", "listku", "cekano_listku", "rozdil_hlasu", "odchylka"]),
            ("Okrsky s příznakem", okrsky[okrsky.proc != ""], ["okrsek", "obalky", "nevracene_obalky", "neplatne_procent", "vyuziti_hlasu", "listku_navic", "proc"]),
        ):
            print(f"\n{title}:")
            print(table[columns].to_string(index=False) if len(table) else "nic")
    print(f"\nTabulky jsou v {folder}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())

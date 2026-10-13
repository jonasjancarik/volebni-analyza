"""
Possible counting errors in the precinct results of Prague, for every list.

Reads the official results with the votes of every candidate in every precinct
(ČSÚ open data, downloaded on the first run) and looks at both ballots a voter
in Prague gets: the one for the council of the city district and the one for
the council of the city. Four things come out, each as a table in
output/<election>/anomalies/ (a run for one district writes to a folder of
its own there):

  kandidati.csv  single candidates whose votes in a precinct break the pattern
                 of their list there: a zero or a fraction among neighbours with
                 dozens of votes, or a multiple of them. These are visible in
                 the data as they are and need no estimate.
  okrsky.csv     precincts with unusually many or few votes counted per returned
                 envelope, and those whose valid ballots left almost no vote
                 unused, which is what too many votes or too few valid ballots
                 in the record look like.
  listky.csv     lists that got far more or fewer votes on one ballot than the
                 other ballot of the same voters suggests.
  mandaty.csv    how many votes each list was from winning or losing a seat,
                 next to the votes its clear candidate errors add up to.

The first table is evidence, the next two are hints: a precinct may differ for
a reason of the place, and only a recount of the ballots can tell.

Run from the repository root:

    uv run python research/precinct_anomalies.py                    # all districts
    uv run python research/precinct_anomalies.py --council 500143   # Praha 5
"""

import argparse
import io
import re
import sys
import zipfile
from pathlib import Path
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd
import requests

PRAGUE = "554782"
PRAGUE_OKRES = "1100"
OPENDATA = "https://volby.gov.cz/opendata/{election}/{name}"
# Archives of the final results; ČSÚ puts the day of publication in the name
ARCHIVES = {"kv2026": {"data": "KV2026_data_20261011_xml.zip", "reg": "KV2026reg20261011_xml.zip"}}
VOTES = [f"HLASY_{number:02d}" for number in range(1, 71)]
TAG = re.compile(r"<([A-Z_0-9]+)>([^<]*)</\1>")

# A list shorter than this has no pattern to break
FEWEST_CANDIDATES = 9
# Fewer ballots marked for a whole list than this say nothing about one candidate
SMALLEST_PILE = 5
# A list under this share of the votes joins the others when ballots are compared
SMALL_LIST = 0.02
# Precincts a district needs for its two ballots to be compared
FEWEST_PRECINCTS = 16


def rows(archive: Path, member: str, row_tag: str, keep: Callable[[dict], bool]) -> pd.DataFrame:
    """Rows of one XML file inside an archive, read line by line; the files have hundreds of MB."""
    found, row = [], None
    with zipfile.ZipFile(archive) as content, content.open(member) as raw:
        for line in io.TextIOWrapper(raw, encoding="utf-8"):
            line = line.strip()
            if line == f"<{row_tag}>":
                row = {}
            elif line == f"</{row_tag}>":
                if keep(row):
                    found.append(row)
                row = None
            elif row is not None:
                match = TAG.match(line)
                if match:
                    row[match.group(1)] = match.group(2)
    return pd.DataFrame(found)


def load(election: str) -> Dict[str, pd.DataFrame]:
    """Precinct forms, candidate votes, candidates, lists and councils of Prague."""
    folder = Path("input") / election / "official"
    stored = folder / "prague.pkl"
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

    def in_prague(row: dict) -> bool:
        return row.get("OKRES") == PRAGUE_OKRES

    print("Čtu výsledky okrsků a hlasy kandidátů (pár minut, jen poprvé)")
    data = {
        "forms": rows(paths["data"], "kvt3.xml", "KV_T3_ROW", in_prague),
        "votes": rows(paths["data"], "kvhl.xml", "KV_HL_ROW", in_prague),
        "candidates": rows(paths["reg"], "kvrk.xml", "KV_REGKAND_ROW", in_prague),
        "lists": rows(paths["reg"], "kvros.xml", "KV_ROS_ROW", in_prague),
        "councils": rows(paths["reg"], "kvrzcoco.xml", "KV_RZCOCO_ROW", in_prague),
    }
    for name, columns in {
        "forms": ["VOL_SEZNAM", "VYD_OBALKY", "ODEVZ_OBAL", "PLAT_LISTKY", "PL_HL_CELK"],
        "votes": VOTES + ["POC_HLASU", "POR_STR_HL"],
        "candidates": ["POR_STR_HL", "PORCISLO", "POCHLASU"],
        "lists": ["POR_STR_HL", "HLASY_STR", "MAND_STR"],
        "councils": ["MANDATY"],
    }.items():
        data[name][columns] = data[name][columns].astype(int)
    data["lists"]["PROCHLSTR"] = data["lists"]["PROCHLSTR"].astype(float)
    pd.to_pickle(data, stored)
    return data


class Ballot:
    """One ballot in the precincts of one city district: the district's own, or the city's."""

    def __init__(self, data: Dict[str, pd.DataFrame], area: str, city: bool):
        self.area, self.city = area, city
        self.council = PRAGUE if city else area
        kind = "1" if city else "2"
        forms, votes = data["forms"], data["votes"]
        self.forms = forms[(forms.OBEC == area) & (forms.TYPZASTUP == kind)].set_index("OKRSEK").sort_index()
        self.forms = self.forms[(self.forms.ODEVZ_OBAL > 0) & (self.forms.PLAT_LISTKY > 0)]
        self.votes = votes[(votes.OBEC == area) & (votes.TYPZASTUP == kind) & votes.OKRSEK.isin(self.forms.index)]
        councils = data["councils"].drop_duplicates("KODZASTUP").set_index("KODZASTUP")
        self.seats = int(councils.at[self.council, "MANDATY"])
        self.name = "ZHMP" if city else "ZMČ"
        lists = data["lists"]
        self.lists = lists[lists.KODZASTUP == self.council].set_index("POR_STR_HL").sort_index()
        candidates = data["candidates"]
        self.lengths = candidates[candidates.KODZASTUP == self.council].groupby("POR_STR_HL").PORCISLO.max()

    def by_list(self) -> pd.DataFrame:
        """Votes of every list in every precinct."""
        return self.votes.pivot(index="OKRSEK", columns="POR_STR_HL", values="POC_HLASU").reindex(self.forms.index).fillna(0)

    def list_name(self, number: int) -> str:
        return self.lists.at[number, "ZKRATKAO30"] if number in self.lists.index else f"Kandidátka {number}"


# ---------------------------------------------------------------------------
# Single candidates
# ---------------------------------------------------------------------------


def piles(matrix: np.ndarray) -> np.ndarray:
    """Ballots marked for the whole list in each precinct: the usual vote of
    its candidates, leaving out those with next to none."""
    upper = np.median(np.sort(matrix, axis=1)[:, matrix.shape[1] // 2 :], axis=1)
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


def candidate_findings(data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Candidates with far fewer or far more votes in a precinct than the
    pattern of their list there. Each list is taken across all its precincts,
    so that a candidate who is usually ahead of the neighbours is not flagged."""
    votes, candidates, lists = data["votes"], data["candidates"], data["lists"]
    council = np.where(votes.TYPZASTUP == "1", PRAGUE, votes.OBEC)
    names = {
        (code, number, order): (f"{first} {last}", valid)
        for code, number, order, first, last, valid in zip(
            candidates.KODZASTUP, candidates.POR_STR_HL, candidates.PORCISLO, candidates.JMENO, candidates.PRIJMENI, candidates.PLATNOST
        )
    }
    length = candidates.groupby(["KODZASTUP", "POR_STR_HL"]).PORCISLO.max()
    list_names = lists.set_index(["KODZASTUP", "POR_STR_HL"]).ZKRATKAO30
    found = []
    for (code, number), part in votes.groupby([council, "POR_STR_HL"]):
        count = int(length.get((code, number), 0))
        if count < FEWEST_CANDIDATES:
            continue
        matrix = part[VOTES].to_numpy(dtype=float)[:, :count]
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
        for kind, mask in (("chybí", missing), ("navíc", extra)):
            for row, column in zip(*np.nonzero(mask)):
                name, valid = names.get((code, number, column + 1), ("?", "A"))
                if valid != "A":  # a withdrawn candidate has no votes anywhere
                    continue
                record = part.iloc[row]
                window = range(max(0, column - 3), min(count, column + 4))
                found.append(
                    {
                        "cast": record.OBEC,
                        "okrsek": record.OKRSEK,
                        "listek": "ZHMP" if code == PRAGUE else "ZMČ",
                        "cislo_kandidatky": number,
                        "kandidatka": list_names.get((code, number), ""),
                        "poradi": column + 1,
                        "kandidat": name,
                        "hlasy": int(matrix[row, column]),
                        "obvykle": round(float(expected[row, column])),
                        "rozdil": round(float(matrix[row, column] - expected[row, column])),
                        "druh": kind,
                        "okoli": " ".join(f"[{int(matrix[row, i])}]" if i == column else str(int(matrix[row, i])) for i in window),
                    }
                )
    result = pd.DataFrame(found)
    if result.empty:
        return result
    # A candidate ahead of the neighbours in several precincts is popular there, not mistyped
    result["stejny_kandidat_v_okrscich"] = result.groupby(["listek", "cislo_kandidatky", "poradi", "druh", "kandidatka"]).okrsek.transform("size")
    return result.sort_values(["cast", "listek", "okrsek", "cislo_kandidatky", "poradi"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Whole precincts
# ---------------------------------------------------------------------------


def robust(values: pd.Series, reference: Optional[pd.Series] = None) -> pd.Series:
    """Distance from the median in robust standard deviations of `reference`."""
    reference = values if reference is None else reference
    middle = reference.median()
    spread = 1.4826 * (reference - middle).abs().median()
    return (values - middle) / spread if spread > 0 else values * 0


def precinct_table(ballots: List[Ballot], data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Votes counted per returned envelope, and whole-list ballots against valid ballots."""
    length = data["candidates"].groupby(["KODZASTUP", "POR_STR_HL"]).PORCISLO.max()
    parts = []
    for ballot in ballots:
        forms = ballot.forms
        pile_sum = pd.Series(0.0, index=forms.index)
        for number, part in ballot.votes.groupby("POR_STR_HL"):
            count = int(length.get((ballot.council, number), 0))
            if count < FEWEST_CANDIDATES:
                continue
            matrix = part[VOTES].to_numpy(dtype=float)[:, :count]
            # A short list fills only a part of a ballot
            pile_sum = pile_sum.add(pd.Series(piles(matrix) * min(count, ballot.seats) / ballot.seats, index=part.OKRSEK.to_numpy()), fill_value=0)
        parts.append(
            pd.DataFrame(
                {
                    "cast": ballot.area,
                    "listek": ballot.name,
                    "obalky": forms.ODEVZ_OBAL,
                    "nevracene_obalky": forms.VYD_OBALKY - forms.ODEVZ_OBAL,
                    "platne_listky": forms.PLAT_LISTKY,
                    "neplatne_procent": ((forms.ODEVZ_OBAL - forms.PLAT_LISTKY) / forms.ODEVZ_OBAL * 100).round(2),
                    "hlasy": forms.PL_HL_CELK,
                    # 1 would mean every envelope held a ballot with all its votes used
                    "vyuziti_hlasu": (forms.PL_HL_CELK / ballot.seats / forms.ODEVZ_OBAL).round(3),
                    "hromadky": pile_sum.reindex(forms.index).round(1),
                    # 1 would mean no valid ballot left a single vote unused
                    "vyuziti_platnych_listku": (forms.PL_HL_CELK / ballot.seats / forms.PLAT_LISTKY).round(3),
                }
            ).rename_axis("okrsek").reset_index()
        )
    table = pd.concat(parts, ignore_index=True)
    table["hromadky_na_platny_listek"] = (table.hromadky / table.platne_listky).round(3)
    table["odchylka"] = 0.0
    for name, same in table.groupby("listek"):
        # District ballots differ in what is on them; a district with enough precincts is its own measure
        for area, part in same.groupby("cast"):
            reference = part.vyuziti_hlasu if len(part) >= 20 else same.vyuziti_hlasu
            table.loc[part.index, "odchylka"] = robust(part.vyuziti_hlasu, reference).round(1)
    median = table.groupby("listek").vyuziti_hlasu.transform("median")
    table["listku_navic"] = ((table.vyuziti_hlasu - median) * table.obalky).round(1)
    reasons = []
    for row in table.itertuples():
        reason = []
        if row.odchylka >= 2:
            reason.append("mnoho hlasů na obálku")
        if row.odchylka <= -3:
            reason.append("málo hlasů na obálku")
        if row.hromadky_na_platny_listek > 1:
            reason.append("víc lístků pro celé kandidátky než platných lístků")
        elif row.vyuziti_platnych_listku >= 0.995 and row.platne_listky >= 150:
            reason.append("platné lístky skoro bez nevyužitého hlasu")
        if row.nevracene_obalky >= 10:
            reason.append("nevrácené obálky")
        reasons.append("; ".join(reason))
    table["proc"] = reasons
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
                        "cast": ballot.area,
                        "okrsek": precincts,
                        "listek": ballot.name,
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
    table = pd.concat(found, ignore_index=True)
    return table[(table.odchylka.abs() >= 3.5) & (table.rozdil_listku.abs() >= 6)]


# ---------------------------------------------------------------------------
# Seats
# ---------------------------------------------------------------------------


def seat_margins(ballot: Ballot) -> pd.DataFrame:
    """Votes each list was from one more seat and from one fewer (d'Hondt
    among the lists the official result counts as over five percent)."""
    lists = ballot.lists
    over = lists[lists.PROCHLSTR >= 5]
    # A list cannot win more seats than it has candidates
    order = sorted(
        (
            (votes / divisor, number, divisor)
            for number, votes in over.HLASY_STR.items()
            for divisor in range(1, min(ballot.seats, int(ballot.lengths.get(number, ballot.seats))) + 1)
        ),
        reverse=True,
    )
    last = order[min(ballot.seats, len(order)) - 1][0]
    first_out = order[ballot.seats][0] if len(order) > ballot.seats else 0.0
    seats = pd.Series([number for _, number, _ in order[: ballot.seats]]).value_counts()
    table = pd.DataFrame(
        {
            "listek": ballot.name,
            "cislo_kandidatky": lists.index,
            "kandidatka": lists.ZKRATKAO30,
            "hlasy": lists.HLASY_STR,
            "procent": lists.PROCHLSTR,
            "mandaty": lists.MAND_STR,
        }
    )
    mine = seats.reindex(lists.index).fillna(0)
    full = mine.to_numpy() >= ballot.lengths.reindex(lists.index).fillna(ballot.seats).to_numpy()
    table["k_dalsimu_mandatu"] = np.where((lists.PROCHLSTR >= 5) & ~full, np.ceil(last * (mine + 1) - lists.HLASY_STR), np.nan)
    table["ke_ztrate_mandatu"] = np.where((mine > 0) & (first_out > 0), np.ceil(lists.HLASY_STR - first_out * mine), np.nan)
    # Whoever is first in line gains the seat as soon as the holder of the last one loses it
    table["souhlasi_s_csu"] = (mine == lists.MAND_STR).all()
    return table.reset_index(drop=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--council", help="Kód městské části; bez něj se projdou všechny")
    parser.add_argument("--election", default="kv2026", choices=sorted(ARCHIVES))
    args = parser.parse_args()
    pd.set_option("display.width", 250, "display.max_columns", 30, "display.max_rows", 200)

    data = load(args.election)
    councils = data["councils"]
    names = councils.drop_duplicates("KODZASTUP").set_index("KODZASTUP").NAZEVZAST
    areas = sorted(set(councils.KODZASTUP) - {PRAGUE})
    if args.council:
        if args.council not in areas:
            print(f"Městská část {args.council} v datech není.")
            return 1
        areas = [args.council]

    candidates = candidate_findings(data)
    ballots, between, margins = [], [], []
    for area in areas:
        district, city = Ballot(data, area, city=False), Ballot(data, area, city=True)
        ballots += [district, city]
        between.append(ballot_findings(district, city))
        margins.append(seat_margins(district).assign(cast=area))
    precincts = precinct_table(ballots, data)
    between = pd.concat(between, ignore_index=True) if any(len(part) for part in between) else pd.DataFrame()
    margins = pd.concat(margins + [seat_margins(Ballot(data, areas[0], city=True)).assign(cast=PRAGUE)], ignore_index=True)

    # Clear candidate errors of each list, next to how close the list was to a seat
    clear = candidates[candidates.druh == "chybí"] if len(candidates) else candidates
    if len(clear):
        key = np.where(clear.listek == "ZHMP", PRAGUE, clear.cast)
        missing = (-clear.rozdil).groupby([key, clear.cislo_kandidatky]).sum()
        margins["chybi_u_kandidatu"] = [int(missing.get((area, number), 0)) for area, number in zip(margins.cast, margins.cislo_kandidatky)]
    else:
        margins["chybi_u_kandidatu"] = 0
    margins["nazev"] = margins.cast.map(names)

    # A run for one district keeps its tables apart from those of all districts
    folder = Path("output") / args.election / "anomalies" / (args.council or "")
    folder.mkdir(parents=True, exist_ok=True)
    in_areas = candidates[candidates.cast.isin(areas)] if len(candidates) else candidates
    for name, table in (("kandidati", in_areas), ("okrsky", precincts), ("listky", between), ("mandaty", margins)):
        table.to_csv(folder / f"{name}.csv", index=False)

    # Districts by how small the closest seat is against what was found there
    summary = []
    for area in areas:
        own = margins[(margins.cast == area)]
        closest = own[["k_dalsimu_mandatu", "ke_ztrate_mandatu"]].min().min()
        found = in_areas[(in_areas.cast == area) & (in_areas.listek == "ZMČ")] if len(in_areas) else in_areas
        lists = between[(between.cast == area) & (between.listek == "ZMČ")] if len(between) else between
        flagged = precincts[(precincts.cast == area) & (precincts.listek == "ZMČ") & (precincts.proc != "")]
        largest = max(
            float(own.chybi_u_kandidatu.max()),
            float(lists.rozdil_hlasu.abs().max()) if len(lists) else 0.0,
            float((flagged.listku_navic.abs() * Ballot(data, area, city=False).seats).max()) if len(flagged) else 0.0,
        )
        summary.append(
            {
                "kod": area,
                "cast": names[area],
                "nejtesnejsi_mandat_hlasu": closest,
                "kandidatu_s_chybou": len(found),
                "nejvic_chybi_jedne_kandidatce": int(own.chybi_u_kandidatu.max()),
                "kandidatek_mimo_druhy_listek": len(lists),
                "okrsku_s_priznakem": len(flagged),
                "nejvetsi_nalez_hlasu": round(largest),
                "nalez_k_mandatu": round(largest / closest, 2) if closest and closest > 0 else np.nan,
            }
        )
    summary = pd.DataFrame(summary).sort_values("nalez_k_mandatu", ascending=False)
    summary.to_csv(folder / "prehled.csv", index=False)

    print("\nMěstské části podle toho, jak velký je největší nález proti nejtěsnějšímu mandátu (lístek do zastupitelstva části):")
    print(summary.head(25 if not args.council else 1).to_string(index=False))
    if args.council:
        own = margins[margins.cast == args.council]
        print("\nMandáty a kolik hlasů chybí u kandidátů každé kandidátky:")
        print(own[["kandidatka", "hlasy", "mandaty", "k_dalsimu_mandatu", "ke_ztrate_mandatu", "chybi_u_kandidatu"]].to_string(index=False))
        for title, table, columns in (
            ("Kandidáti mimo vzor své kandidátky", in_areas, ["okrsek", "listek", "kandidatka", "poradi", "kandidat", "hlasy", "obvykle", "druh", "okoli"]),
            ("Kandidátky mimo to, co odpovídá druhému lístku", between, ["okrsek", "listek", "kandidatka", "listku", "cekano_listku", "rozdil_hlasu", "odchylka"]),
            ("Okrsky s příznakem", precincts[precincts.proc != ""], ["okrsek", "listek", "obalky", "nevracene_obalky", "neplatne_procent", "vyuziti_hlasu", "listku_navic", "proc"]),
        ):
            print(f"\n{title}:")
            print(table[columns].to_string(index=False) if len(table) else "nic")
    print(f"\nTabulky jsou v {folder}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())

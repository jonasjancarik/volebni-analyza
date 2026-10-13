#!/usr/bin/env python3
"""
Figures behind the analysis of errors in precinct records.

precinct_anomalies.py finds them in the official results with the votes of
every candidate; this turns its tables into what the article shows: where
putting the clear errors right would change seats or the people who hold
them, the records that show it, and where a few votes decide.
"""

from typing import Dict, List

import numpy as np
import pandas as pd
import requests

import precinct_anomalies as anomalies
import web_store as store

ELECTION = "kv2026"
# Findings shown for one council, the largest first
MOST_EVIDENCE = 8


def _number(value):
    """A number for JSON; nothing where there is none."""
    return None if value is None or not np.isfinite(value) else int(value)


def _evidence(found: pd.DataFrame, limit: int = MOST_EVIDENCE) -> List[dict]:
    """Findings of one council by precinct and list, with the candidate that shows each best."""
    groups = []
    for (precinct, number, kind), part in found.groupby(["okrsek", "cislo_kandidatky", "druh"]):
        # Missing votes show best at the first candidate left out, next to those counted;
        # a count above the neighbours at the one furthest from them
        worst = part.sort_values("poradi").iloc[0] if kind == "chybí" else part.loc[part.rozdil.abs().idxmax()]
        groups.append(
            {
                "precinct": str(precinct),
                "list": worst.kandidatka,
                "listNumber": int(number),
                "kind": "missing" if kind == "chybí" else "extra",
                "candidates": len(part),
                "votes": int(part.rozdil.sum()),
                "mostlyEmpty": bool(part.vetsina_kandidatky_prazdna.any()),
                # Counted as an error when the seats are recomputed; a single
                # count above the neighbours that is not may be a local favourite
                "counted": bool(kind == "chybí" or part.zjevny_preklep.any()),
                "example": {
                    "place": int(worst.poradi),
                    "name": worst.kandidat,
                    "votes": int(worst.hlasy),
                    "usual": int(worst.obvykle),
                    "around": worst.okoli,
                },
            }
        )
    groups.sort(key=lambda group: (-group["counted"], -abs(group["votes"])))
    return groups[:limit]


def _lists(own: pd.DataFrame) -> List[dict]:
    return [
        {
            "number": int(row.cislo_kandidatky),
            "name": row.kandidatka,
            "votes": int(row.hlasy),
            "share": float(row.procent),
            "seats": int(row.mandaty),
            "seatsAfter": int(row.mandaty_po_oprave),
            "overThreshold": int(row.nad_hranici),
            "toNextSeat": _number(row.k_dalsimu_mandatu),
            "toLoseSeat": _number(row.ke_ztrate_mandatu),
            "missing": int(row.chybi_u_kandidatu),
            "slips": int(row.navic_preklepem),
        }
        for row in own.sort_values("hlasy", ascending=False).itertuples()
    ]


def records_2026() -> dict:
    try:
        results = anomalies.Results(anomalies.load(ELECTION))
    except (requests.RequestException, OSError) as error:
        raise store.NotFound("Pro tuto analýzu chybí oficiální výsledky s hlasy jednotlivých kandidátů.") from error
    tables = anomalies.analyse(results, sorted(results.councils.index))
    summary, margins, order, candidates = (tables[name] for name in ("prehled", "mandaty", "poradi", "kandidati"))
    by_council: Dict[str, Dict[str, pd.DataFrame]] = {
        name: dict(tuple(table.groupby("zastupitelstvo"))) for name, table in (("margins", margins), ("order", order), ("candidates", candidates))
    }
    checked = summary[summary.kandidati_kontrolovani]

    def council(row) -> dict:
        code = row.zastupitelstvo
        lists_order = by_council["order"].get(code, order.iloc[:0])
        people = lists_order[(lists_order.po_oprave_nove_zvoleni != "") | (lists_order.po_oprave_nezvoleni != "")]
        return {
            "code": code,
            "name": row.nazev,
            "city": row.mesto or None,
            "seats": int(row.mandatu),
            "precincts": int(row.okrsku),
            "closestSeat": _number(row.nejtesnejsi_mandat_hlasu),
            "candidatesWithErrors": int(row.kandidatu_s_chybou),
            "seatsChange": row.zmena_mandatu_po_oprave != "",
            "lists": _lists(by_council["margins"][code]),
            "people": [
                {
                    "list": item.kandidatka,
                    "seated": [name for name in item.po_oprave_nove_zvoleni.split(", ") if name],
                    "unseated": [name for name in item.po_oprave_nezvoleni.split(", ") if name],
                    "corrected": int(item.opraveno_hlasu),
                }
                for item in people.itertuples()
            ],
            "evidence": _evidence(by_council["candidates"].get(code, candidates.iloc[:0])),
        }

    changed = summary[(summary.zmena_mandatu_po_oprave != "") | (summary.jini_zvoleni_po_oprave != "")]
    changed = changed.sort_values(["zmena_mandatu_po_oprave", "nejtesnejsi_mandat_hlasu"], key=lambda column: column == "" if column.dtype == object else column)

    # Lists whose seats would go to other people for a handful of votes once the errors are put right
    corrected = order[order.zastupitelstvo.isin(checked.zastupitelstvo) & (order.opraveno_hlasu > 0) & (order.nejmensi_zmena_po_oprave_u != "")]
    tight = corrected[~corrected.zastupitelstvo.isin(changed.zastupitelstvo)].sort_values("nejmensi_zmena_po_oprave").head(12)

    slips = candidates[candidates.zjevny_preklep].sort_values("rozdil", ascending=False).head(12)
    pirates = margins[margins.zastupitelstvo.isin(checked.zastupitelstvo) & margins.kandidatka.str.contains("irát") & (margins.mandaty + margins.mandaty_po_oprave > 0)]
    order_of = order.set_index(["zastupitelstvo", "cislo_kandidatky"])

    def pirate(row) -> dict:
        own = order_of.loc[(row.zastupitelstvo, row.cislo_kandidatky)] if (row.zastupitelstvo, row.cislo_kandidatky) in order_of.index else None
        return {
            "council": row.nazev,
            "list": row.kandidatka,
            "seats": int(row.mandaty),
            "seatsAfter": int(row.mandaty_po_oprave),
            "toNextSeat": _number(row.k_dalsimu_mandatu),
            "toLoseSeat": _number(row.ke_ztrate_mandatu),
            "missing": int(row.chybi_u_kandidatu),
            "slips": int(row.navic_preklepem),
            "closestPerson": own.nejmensi_zmena_po_oprave_u if own is not None else "",
            "closestPersonVotes": _number(own.nejmensi_zmena_po_oprave) if own is not None else None,
            "seated": own.po_oprave_nove_zvoleni if own is not None else "",
            "unseated": own.po_oprave_nezvoleni if own is not None else "",
        }

    return {
        "election": ELECTION,
        "totals": {
            "councils": len(summary),
            "checked": len(checked),
            "decidedByLot": int((~summary.mandaty_souhlasi_s_csu & summary.o_mandatu_rozhodl_los).sum()),
            "seatsDiffer": int((~summary.mandaty_souhlasi_s_csu & ~summary.o_mandatu_rozhodl_los).sum()),
            "orderDiffers": int((~summary.poradi_souhlasi_s_csu).sum()),
            "missing": int((candidates.druh == "chybí").sum()),
            "missingVotes": int(-candidates[candidates.druh == "chybí"].rozdil.sum()),
            "slips": int(candidates.zjevny_preklep.sum()),
            "slipVotes": int(candidates[candidates.zjevny_preklep].rozdil.sum()),
            "councilsWithErrors": int(candidates[(candidates.druh == "chybí") | candidates.zjevny_preklep].zastupitelstvo.nunique()),
            "precinctsWithErrors": int(candidates[(candidates.druh == "chybí") | candidates.zjevny_preklep].groupby(["zastupitelstvo", "obec", "okrsek"]).ngroups),
        },
        "changed": [council(row) for row in changed.itertuples()],
        "tight": [
            {
                "council": row.nazev,
                "list": row.kandidatka,
                "seats": int(row.mandaty),
                "before": row.nejmensi_zmena_u,
                "after": row.nejmensi_zmena_po_oprave_u,
                "votes": int(row.nejmensi_zmena_po_oprave),
                "corrected": int(row.opraveno_hlasu),
            }
            for row in tight.itertuples()
        ],
        "slips": [
            {
                "council": results.name(row.zastupitelstvo),
                "precinct": str(row.okrsek),
                "list": row.kandidatka,
                "place": int(row.poradi),
                "name": row.kandidat,
                "votes": int(row.hlasy),
                "usual": int(row.obvykle),
                "around": row.okoli,
                "reason": row.duvod_preklepu,
            }
            for row in slips.itertuples()
        ],
        "pirates": sorted((pirate(row) for row in pirates.itertuples()), key=lambda item: item["council"]),
        "checked": sorted(
            ({"name": row.nazev, "city": row.mesto or None, "precincts": int(row.okrsku), "errors": int(row.kandidatu_s_chybou)} for row in checked.itertuples()),
            key=lambda item: (item["city"] or item["name"], item["name"]),
        ),
    }

#!/usr/bin/env python3
"""
Ecological inference for Prague 5 split-ticket voting (OBEC -> MCMO).
"""

import argparse
import json
import logging
import re
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

from election_config import get_election_config
from ei_models import duncan_davis_bounds, goodman_estimates

logger = logging.getLogger(__name__)

DEFAULT_ELECTION_ID = "kv2022"
DEFAULT_MUNICIPALITY_CODE = "500143"  # Prague 5
DEFAULT_OBEC_CODE = "554782"  # Prague city council
DEFAULT_OBEC_SEATS = 65
DEFAULT_MCMO_SEATS = 41

PARTY_FAMILY_RULES = {
    "Praha Sobě": ["praha 5 sobe", "praha sobe"],
}
def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag
def _child_text(elem: ET.Element, tag_name: str) -> str:
    for child in elem:
        if _strip_ns(child.tag) == tag_name:
            return child.text or ""
    return ""
def normalize_text(value: str) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", value)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()
def party_family_from_name(party_name: str) -> str:
    normalized = normalize_text(party_name)
    for family_label, aliases in PARTY_FAMILY_RULES.items():
        if any(alias in normalized for alias in aliases):
            return family_label
    return ""
def load_party_mappings(
    register_path: Path, target_codes: Iterable[str]
) -> Dict[str, Dict[int, str]]:
    mappings: Dict[str, Dict[int, str]] = {code: {} for code in target_codes}
    if not register_path.exists():
        raise FileNotFoundError(f"Party register not found: {register_path}")

    for _, elem in ET.iterparse(register_path, events=("end",)):
        if _strip_ns(elem.tag) != "KV_ROS_ROW":
            continue

        code = _child_text(elem, "KODZASTUP")
        if code not in mappings:
            elem.clear()
            continue

        list_num_text = _child_text(elem, "POR_STR_HL")
        if not list_num_text:
            elem.clear()
            continue

        try:
            list_num = int(list_num_text)
        except ValueError:
            elem.clear()
            continue

        full_name = _child_text(elem, "NAZEVCELK").strip()
        short_name = _child_text(elem, "ZKRATKAO30").strip()
        party_name = full_name or short_name
        if short_name and short_name != "SNK" and len(short_name) < len(full_name):
            party_name = short_name

        if party_name:
            mappings[code][list_num] = party_name

        elem.clear()

    return mappings
def find_list_number(
    mapping: Dict[int, str], aliases: Iterable[str]
) -> Optional[int]:
    normalized_aliases = [normalize_text(alias) for alias in aliases if alias]
    for list_num, name in mapping.items():
        name_norm = normalize_text(name)
        if any(alias and alias in name_norm for alias in normalized_aliases):
            return list_num
    return None
def _to_int(value: Optional[str]) -> int:
    try:
        return int(value or 0)
    except ValueError:
        return 0
def parse_district_results(
    raw_dir: Path, municipality_code: str
) -> Dict[str, Dict[str, dict]]:
    districts: Dict[str, Dict[str, dict]] = {}
    xml_files = sorted(raw_dir.glob("electoral_districts_batch_*.xml"))

    for xml_file in xml_files:
        try:
            content = xml_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        if municipality_code not in content:
            continue

        for _, elem in ET.iterparse(xml_file, events=("end",)):
            if _strip_ns(elem.tag) != "OKRSEK":
                continue

            if elem.attrib.get("CIS_OBEC") != municipality_code:
                elem.clear()
                continue

            district_code = elem.attrib.get("CIS_OKRSEK", "").strip()
            district_type = elem.attrib.get("OZNAC_TYPU", "").strip()
            zastupitelstvo_code = elem.attrib.get("KODZASTUP", "").strip()
            obvod_number = elem.attrib.get("CIS_OBVODU", "").strip()

            turnout = {}
            party_votes: Dict[int, int] = {}
            for child in elem:
                tag = _strip_ns(child.tag)
                if tag == "UCAST_OKRSEK":
                    turnout = {
                        "registered_voters": _to_int(
                            child.attrib.get("ZAPSANI_VOLICI")
                        ),
                        "issued_ballots": _to_int(child.attrib.get("VYDANE_OBALKY")),
                        "returned_ballots": _to_int(
                            child.attrib.get("ODEVZDANE_OBALKY")
                        ),
                        "valid_votes": _to_int(child.attrib.get("PLATNE_HLASY")),
                    }
                elif tag == "HLASY_OKRSEK":
                    list_num = _to_int(child.attrib.get("POR_STR_HLAS_LIST"))
                    votes = _to_int(child.attrib.get("HLASY"))
                    if list_num > 0:
                        party_votes[list_num] = votes

            district_payload = {
                "district_code": district_code,
                "district_type": district_type,
                "zastupitelstvo_code": zastupitelstvo_code,
                "obvod_number": obvod_number,
                "turnout": turnout,
                "party_votes": party_votes,
            }

            districts.setdefault(district_code, {})[district_type] = district_payload
            elem.clear()

    return districts
def _total_votes(payload: dict) -> int:
    turnout_votes = payload.get("turnout", {}).get("valid_votes")
    if turnout_votes:
        return int(turnout_votes)
    return sum(payload.get("party_votes", {}).values())
def build_ei_dataset(
    districts: Dict[str, Dict[str, dict]],
    pirate_list_number: int,
    mcmo_mapping: Dict[int, str],
    share_mode: str,
    seats_obec: int,
    seats_mcmo: int,
) -> Tuple[pd.DataFrame, List[int]]:
    mcmo_parties = set()
    for district in districts.values():
        mcmo = district.get("MCMO")
        if not mcmo:
            continue
        mcmo_parties.update(mcmo.get("party_votes", {}).keys())
    party_list_numbers = sorted(mcmo_parties)
    rows = []
    for district_code, by_type in districts.items():
        obec = by_type.get("OBEC")
        mcmo = by_type.get("MCMO")
        if not obec or not mcmo:
            continue
        obec_total_votes = _total_votes(obec)
        mcmo_total_votes = _total_votes(mcmo)
        returned_ballots = obec.get("turnout", {}).get("returned_ballots", 0)
        if obec_total_votes <= 0 or mcmo_total_votes <= 0:
            continue
        pirate_votes = obec.get("party_votes", {}).get(pirate_list_number, 0)
        if share_mode == "ballots":
            if returned_ballots <= 0 or seats_obec <= 0 or seats_mcmo <= 0:
                continue
            pirate_share = (pirate_votes / seats_obec) / returned_ballots
        else:
            pirate_share = pirate_votes / obec_total_votes
        base_weight = returned_ballots if share_mode == "ballots" else obec_total_votes
        pirate_weight = pirate_share * base_weight
        row = {
            "district_code": district_code,
            "pirate_votes": pirate_votes,
            "pirate_share": pirate_share,
            "obec_total_votes": obec_total_votes,
            "mcmo_total_votes": mcmo_total_votes,
            "returned_ballots": returned_ballots,
            "base_weight": base_weight,
            "pirate_weight": pirate_weight,
        }
        for list_num in party_list_numbers:
            votes = mcmo.get("party_votes", {}).get(list_num, 0)
            if share_mode == "ballots":
                share = (votes / seats_mcmo) / returned_ballots if returned_ballots else 0
            else:
                share = votes / mcmo_total_votes if mcmo_total_votes else 0
            row[f"mcmo_{list_num}"] = share
        rows.append(row)
    df = pd.DataFrame(rows)
    if df.empty:
        return df, party_list_numbers
    df = df[df["pirate_share"].notna()]
    df = df[df["pirate_share"] > 0]
    df = df.reset_index(drop=True)
    return df, party_list_numbers
def run_ei(
    election_id: str,
    municipality_code: str,
    obec_code: str,
    share_mode: str,
    seats_obec: int,
    seats_mcmo: int,
    pirate_aliases: List[str],
    pirate_list_number_override: Optional[int],
    pirate_mcmo_list_number_override: Optional[int],
    raw_dir_override: Optional[Path],
    output_dir_override: Optional[Path],
) -> Tuple[pd.DataFrame, Path, Path]:
    config = get_election_config(election_id, base_dir=Path("."))
    raw_dir = raw_dir_override or config.raw_input_dir
    if not raw_dir.exists():
        fallback = Path("input") / "raw"
        if fallback.exists():
            raw_dir = fallback

    register_path = raw_dir / "kvros_electoral_parties_register.xml"
    mappings = load_party_mappings(register_path, {municipality_code, obec_code})

    obec_mapping = mappings.get(obec_code, {})
    mcmo_mapping = mappings.get(municipality_code, {})

    pirate_list_number = pirate_list_number_override
    if pirate_list_number is None:
        pirate_list_number = find_list_number(obec_mapping, pirate_aliases)

    if pirate_list_number is None:
        raise ValueError("Pirate list number not found; use --obec-list-number.")

    pirate_mcmo_list_number = pirate_mcmo_list_number_override
    if pirate_mcmo_list_number is None:
        pirate_mcmo_list_number = find_list_number(mcmo_mapping, pirate_aliases)
    if pirate_mcmo_list_number is None and pirate_list_number in mcmo_mapping:
        pirate_mcmo_list_number = pirate_list_number

    logger.info("Parsing district results from %s", raw_dir)
    districts = parse_district_results(raw_dir, municipality_code)
    if not districts:
        raise ValueError("No district data found for municipality code.")

    df, party_list_numbers = build_ei_dataset(
        districts,
        pirate_list_number,
        mcmo_mapping,
        share_mode,
        seats_obec,
        seats_mcmo,
    )

    if df.empty:
        raise ValueError("No usable districts after filtering.")

    party_columns = [f"mcmo_{list_num}" for list_num in party_list_numbers]
    estimates = goodman_estimates(df, party_columns, "pirate_share")
    bounds = duncan_davis_bounds(df, party_columns, "pirate_share", "base_weight")

    rows = []
    for list_num in party_list_numbers:
        col = f"mcmo_{list_num}"
        pirate_estimate = estimates[col]["pirate_estimate"]
        rows.append(
            {
                "mcmo_list_number": list_num,
                "party_name": mcmo_mapping.get(list_num, f"List {list_num}"),
                "goodman_estimate": pirate_estimate,
                "goodman_estimate_clipped": min(max(pirate_estimate, 0), 1),
                "bounds_lower": bounds[col][0],
                "bounds_upper": bounds[col][1],
            }
        )

    results_df = pd.DataFrame(rows)
    if results_df.empty:
        raise ValueError("No EI results generated.")

    results_df["party_family"] = results_df["party_name"].apply(party_family_from_name)

    total = results_df["goodman_estimate_clipped"].sum()
    if total > 0:
        results_df["goodman_estimate_normalized"] = (
            results_df["goodman_estimate_clipped"] / total
        )
    else:
        results_df["goodman_estimate_normalized"] = 0.0

    results_df = results_df.sort_values(
        "goodman_estimate_normalized", ascending=False
    ).reset_index(drop=True)

    output_dir = output_dir_override or config.reports_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    detailed_dir = config.detailed_dir
    detailed_dir.mkdir(parents=True, exist_ok=True)

    output_csv = output_dir / f"ei_prague5_pirates_mcmo_{share_mode}.csv"
    detailed_csv = detailed_dir / f"ei_prague5_inputs_{share_mode}.csv"
    results_df.to_csv(output_csv, index=False)
    df.to_csv(detailed_csv, index=False)

    family_df = results_df[results_df["party_family"] != ""].copy()
    family_csv = None
    if not family_df.empty:
        family_df = (
            family_df.groupby("party_family", as_index=False)
            .agg(
                {
                    "goodman_estimate": "sum",
                    "goodman_estimate_clipped": "sum",
                    "goodman_estimate_normalized": "sum",
                    "bounds_lower": "sum",
                    "bounds_upper": "sum",
                    "party_name": lambda x: " | ".join(sorted(set(x))),
                }
            )
            .rename(columns={"party_name": "family_members"})
            .sort_values("goodman_estimate_normalized", ascending=False)
        )
        family_csv = output_dir / f"ei_prague5_pirates_mcmo_{share_mode}_by_family.csv"
        family_df.to_csv(family_csv, index=False)

    logger.info("Saved EI results: %s", output_csv)
    logger.info("Saved EI inputs: %s", detailed_csv)
    if family_csv:
        logger.info("Saved EI family results: %s", family_csv)

    summary_path = None
    if pirate_mcmo_list_number is not None:
        pirate_row = results_df[
            results_df["mcmo_list_number"] == pirate_mcmo_list_number
        ]
        if not pirate_row.empty:
            district_codes = set(df["district_code"].astype(str))
            totals = {
                "obec_votes_total": 0,
                "obec_pirate_votes": 0,
                "mcmo_votes_total": 0,
                "mcmo_pirate_votes": 0,
            }
            for district_code in district_codes:
                by_type = districts.get(str(district_code), {})
                obec = by_type.get("OBEC")
                mcmo = by_type.get("MCMO")
                if not obec or not mcmo:
                    continue
                totals["obec_votes_total"] += _total_votes(obec)
                totals["obec_pirate_votes"] += obec.get("party_votes", {}).get(
                    pirate_list_number, 0
                )
                totals["mcmo_votes_total"] += _total_votes(mcmo)
                totals["mcmo_pirate_votes"] += mcmo.get("party_votes", {}).get(
                    pirate_mcmo_list_number, 0
                )

            pirate_obec_share = (
                totals["obec_pirate_votes"] / totals["obec_votes_total"]
                if totals["obec_votes_total"] > 0
                else 0
            )
            pirate_mcmo_share = (
                totals["mcmo_pirate_votes"] / totals["mcmo_votes_total"]
                if totals["mcmo_votes_total"] > 0
                else 0
            )
            retention = float(pirate_row["goodman_estimate"].iloc[0])
            retention_clipped = float(pirate_row["goodman_estimate_clipped"].iloc[0])
            retention_normalized = float(
                pirate_row["goodman_estimate_normalized"].iloc[0]
            )
            expected_from_obec = retention_normalized * pirate_obec_share
            implied_inflow = pirate_mcmo_share - expected_from_obec
            implied_inflow_fraction = (
                implied_inflow / pirate_mcmo_share if pirate_mcmo_share > 0 else 0
            )

            summary = {
                "share_mode": share_mode,
                "districts_used": len(district_codes),
                "pirate_obec_list_number": pirate_list_number,
                "pirate_mcmo_list_number": pirate_mcmo_list_number,
                "pirate_obec_name": obec_mapping.get(pirate_list_number, ""),
                "pirate_mcmo_name": mcmo_mapping.get(pirate_mcmo_list_number, ""),
                "pirate_obec_share": pirate_obec_share,
                "pirate_mcmo_share": pirate_mcmo_share,
                "pirate_share_gap": pirate_mcmo_share - pirate_obec_share,
                "pirate_retention_goodman": retention,
                "pirate_retention_clipped": retention_clipped,
                "pirate_retention_normalized": retention_normalized,
                "expected_mcmo_from_obec": expected_from_obec,
                "implied_inflow_share": implied_inflow,
                "implied_inflow_fraction_of_mcmo": implied_inflow_fraction,
            }

            summary_path = (
                output_dir
                / f"ei_prague5_pirates_mcmo_{share_mode}_summary.json"
            )
            with open(summary_path, "w", encoding="utf-8") as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)

    if summary_path:
        logger.info("Saved EI summary: %s", summary_path)

    return results_df, output_csv, detailed_csv
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ecological inference for Prague 5 split-ticket voting."
    )
    parser.add_argument("--election", default=DEFAULT_ELECTION_ID)
    parser.add_argument("--municipality-code", default=DEFAULT_MUNICIPALITY_CODE)
    parser.add_argument("--obec-code", default=DEFAULT_OBEC_CODE)
    parser.add_argument(
        "--share-mode", choices=["votes", "ballots"], default="votes"
    )
    parser.add_argument("--obec-seats", type=int, default=DEFAULT_OBEC_SEATS)
    parser.add_argument("--mcmo-seats", type=int, default=DEFAULT_MCMO_SEATS)
    parser.add_argument("--obec-list-number", type=int, default=None)
    parser.add_argument("--mcmo-list-number", type=int, default=None)
    parser.add_argument(
        "--pirate-alias",
        action="append",
        default=["pirat", "piratska strana", "ceska piratska strana"],
    )
    parser.add_argument("--raw-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser
def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args()

    run_ei(
        election_id=args.election,
        municipality_code=args.municipality_code,
        obec_code=args.obec_code,
        share_mode=args.share_mode,
        seats_obec=args.obec_seats,
        seats_mcmo=args.mcmo_seats,
        pirate_aliases=args.pirate_alias,
        pirate_list_number_override=args.obec_list_number,
        pirate_mcmo_list_number_override=args.mcmo_list_number,
        raw_dir_override=args.raw_dir,
        output_dir_override=args.output_dir,
    )
if __name__ == "__main__":
    main()

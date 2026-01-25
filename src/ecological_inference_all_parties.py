#!/usr/bin/env python3
"""
Ecological inference for all OBEC parties (Prague 5, OBEC -> MCMO).
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd

from election_config import get_election_config
from ei_models import duncan_davis_bounds, goodman_estimates
from ecological_inference import (
    DEFAULT_ELECTION_ID,
    DEFAULT_MCMO_SEATS,
    DEFAULT_MUNICIPALITY_CODE,
    DEFAULT_OBEC_CODE,
    DEFAULT_OBEC_SEATS,
    build_ei_dataset,
    load_party_mappings,
    parse_district_results,
    party_family_from_name,
)

logger = logging.getLogger(__name__)


def list_numbers_for_type(
    districts: Dict[str, Dict[str, dict]], district_type: str
) -> List[int]:
    list_numbers = set()
    for district in districts.values():
        payload = district.get(district_type)
        if not payload:
            continue
        list_numbers.update(payload.get("party_votes", {}).keys())
    return sorted(list_numbers)


def _total_votes(payload: dict) -> int:
    turnout_votes = payload.get("turnout", {}).get("valid_votes")
    if turnout_votes:
        return int(turnout_votes)
    return sum(payload.get("party_votes", {}).values())


def aggregate_party_votes(
    districts: Dict[str, Dict[str, dict]], district_type: str
) -> Dict[int, int]:
    totals: Dict[int, int] = {}
    for district in districts.values():
        payload = district.get(district_type)
        if not payload:
            continue
        for list_num, votes in payload.get("party_votes", {}).items():
            totals[list_num] = totals.get(list_num, 0) + votes
    return totals


def run_all_parties(
    election_id: str,
    municipality_code: str,
    obec_code: str,
    share_mode: str,
    seats_obec: int,
    seats_mcmo: int,
    raw_dir_override: Optional[Path],
    output_dir_override: Optional[Path],
) -> None:
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

    logger.info("Parsing district results from %s", raw_dir)
    districts = parse_district_results(raw_dir, municipality_code)
    if not districts:
        raise ValueError("No district data found for municipality code.")

    obec_list_numbers = list_numbers_for_type(districts, "OBEC")
    mcmo_list_numbers = list_numbers_for_type(districts, "MCMO")

    obec_totals = aggregate_party_votes(districts, "OBEC")
    mcmo_totals = aggregate_party_votes(districts, "MCMO")
    total_obec_votes = sum(obec_totals.values()) or 0
    total_mcmo_votes = sum(mcmo_totals.values()) or 0
    obec_shares = {
        list_num: votes / total_obec_votes
        for list_num, votes in obec_totals.items()
        if total_obec_votes > 0
    }
    mcmo_shares = {
        list_num: votes / total_mcmo_votes
        for list_num, votes in mcmo_totals.items()
        if total_mcmo_votes > 0
    }

    rows: List[dict] = []
    summaries: List[dict] = []

    for source_list_num in obec_list_numbers:
        df, target_list_numbers = build_ei_dataset(
            districts,
            source_list_num,
            mcmo_mapping,
            share_mode,
            seats_obec,
            seats_mcmo,
        )
        if df.empty:
            continue

        party_columns = [f"mcmo_{num}" for num in target_list_numbers]
        estimates = goodman_estimates(df, party_columns, "pirate_share")
        bounds = duncan_davis_bounds(df, party_columns, "pirate_share", "base_weight")

        clipped_values = [
            min(max(estimates[col]["pirate_estimate"], 0), 1) for col in party_columns
        ]
        clipped_sum = sum(clipped_values)

        source_share = obec_shares.get(source_list_num, 0.0)
        source_name = obec_mapping.get(source_list_num, f"List {source_list_num}")
        source_family = party_family_from_name(source_name)

        summary_retention = None
        if source_list_num in mcmo_mapping:
            summary_retention = None
            target_index = (
                target_list_numbers.index(source_list_num)
                if source_list_num in target_list_numbers
                else None
            )
            if target_index is not None:
                summary_retention = clipped_values[target_index]

        for target_list_num, col, clipped in zip(
            target_list_numbers, party_columns, clipped_values
        ):
            estimate = estimates[col]["pirate_estimate"]
            normalized = clipped / clipped_sum if clipped_sum > 0 else 0
            target_name = mcmo_mapping.get(target_list_num, f"List {target_list_num}")
            target_family = party_family_from_name(target_name)
            outside_bounds = (
                estimate < bounds[col][0] or estimate > bounds[col][1]
            )

            rows.append(
                {
                    "share_mode": share_mode,
                    "source_list_number": source_list_num,
                    "source_party_name": source_name,
                    "source_family": source_family,
                    "source_districts_used": len(df),
                    "source_share": source_share,
                    "target_list_number": target_list_num,
                    "target_party_name": target_name,
                    "target_family": target_family,
                    "target_share": mcmo_shares.get(target_list_num, 0.0),
                    "goodman_estimate": estimate,
                    "goodman_estimate_clipped": clipped,
                    "goodman_estimate_normalized": normalized,
                    "weighted_flow_share": source_share * normalized,
                    "bounds_lower": bounds[col][0],
                    "bounds_upper": bounds[col][1],
                    "outside_bounds": outside_bounds,
                    "same_list_number": source_list_num == target_list_num,
                }
            )

        summaries.append(
            {
                "share_mode": share_mode,
                "source_list_number": source_list_num,
                "source_party_name": source_name,
                "source_family": source_family,
                "source_districts_used": len(df),
                "source_share": source_share,
                "retention_clipped": summary_retention,
            }
        )

    output_dir = output_dir_override or config.reports_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    flows_df = pd.DataFrame(rows)
    flows_path = output_dir / f"ei_prague5_all_parties_{share_mode}.csv"
    flows_df.to_csv(flows_path, index=False)

    summary_df = pd.DataFrame(summaries)
    summary_path = output_dir / f"ei_prague5_all_parties_{share_mode}_summary.csv"
    summary_df.to_csv(summary_path, index=False)

    family_df = flows_df.copy()
    family_df = family_df[
        (family_df["source_family"] != "") | (family_df["target_family"] != "")
    ]
    family_path = None
    if not family_df.empty:
        family_agg = (
            family_df.groupby(["source_family", "target_family"], as_index=False)
            .agg({"weighted_flow_share": "sum"})
            .sort_values("weighted_flow_share", ascending=False)
        )
        family_path = (
            output_dir / f"ei_prague5_all_parties_{share_mode}_by_family.csv"
        )
        family_agg.to_csv(family_path, index=False)

    meta = {
        "election_id": election_id,
        "share_mode": share_mode,
        "obec_total_votes": total_obec_votes,
        "mcmo_total_votes": total_mcmo_votes,
        "obec_parties": len(obec_list_numbers),
        "mcmo_parties": len(mcmo_list_numbers),
        "districts_total": len(districts),
        "flows_csv": str(flows_path),
        "summary_csv": str(summary_path),
        "family_csv": str(family_path) if family_path else "",
    }
    meta_path = output_dir / f"ei_prague5_all_parties_{share_mode}_meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    logger.info("Saved flows: %s", flows_path)
    logger.info("Saved summaries: %s", summary_path)
    if family_path:
        logger.info("Saved family flows: %s", family_path)
    logger.info("Saved meta: %s", meta_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ecological inference for all parties (Prague 5)."
    )
    parser.add_argument("--election", default=DEFAULT_ELECTION_ID)
    parser.add_argument("--municipality-code", default=DEFAULT_MUNICIPALITY_CODE)
    parser.add_argument("--obec-code", default=DEFAULT_OBEC_CODE)
    parser.add_argument(
        "--share-mode", choices=["votes", "ballots"], default="ballots"
    )
    parser.add_argument("--obec-seats", type=int, default=DEFAULT_OBEC_SEATS)
    parser.add_argument("--mcmo-seats", type=int, default=DEFAULT_MCMO_SEATS)
    parser.add_argument("--raw-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = build_parser().parse_args()

    run_all_parties(
        election_id=args.election,
        municipality_code=args.municipality_code,
        obec_code=args.obec_code,
        share_mode=args.share_mode,
        seats_obec=args.obec_seats,
        seats_mcmo=args.mcmo_seats,
        raw_dir_override=args.raw_dir,
        output_dir_override=args.output_dir,
    )


if __name__ == "__main__":
    main()

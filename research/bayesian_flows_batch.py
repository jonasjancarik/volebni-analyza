#!/usr/bin/env python3
"""
Run the simple Bayesian flow model for every council with enough precincts
and compare each result with the fast estimate used by the app.

    PYTENSOR_FLAGS='cxx=' uv run --with pymc --with nutpie python research/bayesian_flows_batch.py

Councils that already have a result are skipped, so the run can be repeated.
Progress of running fits: python3 research/bayesian_progress.py
Summary: output/<election>/reports/bayesian_simple_summary.csv
"""

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).parent.parent / "src"))
sys.path.append(str(Path(__file__).parent))

from bayesian_flows_check import load_precinct_table  # noqa: E402
from election_comparison import estimate_flows, match_precincts  # noqa: E402


def eligible_councils(election: str, previous: str, min_precincts: int) -> pd.DataFrame:
    """Councils with at least `min_precincts` precincts matched in both elections."""
    results = lambda e: json.loads(  # noqa: E731
        Path(f"output/{e}/results/all_municipalities_comprehensive.json").read_text(encoding="utf-8")
    )["municipalities"]
    current, earlier = results(election), results(previous)
    rows = []
    for code, municipality in current.items():
        districts = municipality.get("district_data") or []
        if len(districts) < min_precincts or code not in earlier:
            continue
        matched = len(
            match_precincts(
                load_precinct_table(previous, code), load_precinct_table(election, code)
            )[0]
        )
        if matched >= min_precincts:
            rows.append(
                {
                    "code": code,
                    "name": municipality["metadata"]["municipality_name"],
                    "council": "město" if districts[0]["type"] == "OBEC" else "městská část",
                    "precincts": matched,
                }
            )
    return pd.DataFrame(rows).sort_values("precincts", ascending=False)


def compare(code: str, election: str, previous: str, reports: Path) -> dict:
    """Agreement between the Bayesian result and the app's fast estimate."""
    bayes = pd.read_csv(reports / f"bayesian_flows_{code}_simple.csv")
    diagnostics = json.loads(
        (reports / f"bayesian_flows_{code}_simple_diagnostics.json").read_text(encoding="utf-8")
    )
    flows = estimate_flows(
        *match_precincts(load_precinct_table(previous, code), load_precinct_table(election, code))
    )
    fast = flows["transitions"].stack().rename("fast").reset_index()
    fast.columns = ["source", "target", "fast"]
    fast["fast_low"] = flows["transitions_low"].stack().to_numpy()
    fast["fast_high"] = flows["transitions_high"].stack().to_numpy()
    both = bayes.merge(fast, on=["source", "target"])
    difference = (both["bayes_mean"] - both["fast"]).abs() * 100
    # Half a point of slack: both intervals are rounded when shown
    fast_inside = both["fast"].between(both["bayes_p05"] - 0.005, both["bayes_p95"] + 0.005)
    bayes_inside = both["bayes_mean"].between(both["fast_low"] - 0.005, both["fast_high"] + 0.005)
    return {
        "rhat": round(diagnostics["max_rhat_citywide_rates"], 3),
        "minutes": diagnostics["minutes"],
        "precinct_types_fast": flows["precinct_types"],
        "mean_difference_pp": round(difference.mean(), 1),
        "max_difference_pp": round(difference.max(), 1),
        "fast_inside_bayes_interval": round(fast_inside.mean(), 2),
        "bayes_inside_fast_interval": round(bayes_inside.mean(), 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--election", default="kv2026")
    parser.add_argument("--previous", default="kv2022")
    parser.add_argument("--min-precincts", type=int, default=50)
    parser.add_argument("--parallel", type=int, default=2, help="fits at once (4 chains each)")
    args = parser.parse_args()

    reports = Path(f"output/{args.election}/reports")
    councils = eligible_councils(args.election, args.previous, args.min_precincts)
    print(f"{len(councils)} councils with {args.min_precincts}+ matched precincts", flush=True)

    def fit(code: str) -> None:
        if (reports / f"bayesian_flows_{code}_simple_diagnostics.json").exists():
            return
        subprocess.run(
            [
                sys.executable,
                str(Path(__file__).parent / "bayesian_flows_check.py"),
                "--code", code,
                "--election", args.election,
                "--previous", args.previous,
                "--model", "simple",
                "--draws", "2000",
                "--tune", "2000",
                "--chains", "4",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

    with ThreadPoolExecutor(args.parallel) as pool:
        list(pool.map(fit, councils["code"]))

    summary = []
    for council in councils.to_dict("records"):
        try:
            summary.append({**council, **compare(council["code"], args.election, args.previous, reports)})
        except FileNotFoundError:
            summary.append({**council, "rhat": None})
    table = pd.DataFrame(summary)
    table.to_csv(reports / "bayesian_simple_summary.csv", index=False)
    pd.set_option("display.width", 220)
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()

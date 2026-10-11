#!/usr/bin/env python3
"""
Cross-check of the voter flow estimate with a Bayesian hierarchical model.

The app estimates flows with a fast constrained regression
(src/election_comparison.py). This script fits the multinomial-Dirichlet
ecological inference model of Rosen, Jiang, King and Tanner (2001) to the same
matched precincts, where every precinct has its own transition rates drawn
around city-wide means. It is slow, so it is a one-off check, not part of the app.

    uv run --with pymc --with nutpie python research/bayesian_flows_check.py --code 554782

PyMC and nutpie are deliberately not project dependencies.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).parent.parent / "src"))

from election_comparison import (  # noqa: E402
    estimate_flows,
    group_columns,
    match_precincts,
    precinct_table,
)


def load_precinct_table(election_id: str, code: str) -> pd.DataFrame:
    path = Path(f"output/{election_id}/results/all_municipalities_comprehensive.json")
    municipality = json.loads(path.read_text(encoding="utf-8"))["municipalities"][code]
    names = {int(p["list_number"]): p["party_name"] for p in municipality["party_results"]}
    districts = pd.DataFrame(
        {
            "district_code": d["district_code"],
            "registered_voters": d["turnout"]["registered_voters"],
            "returned_ballots": d["turnout"]["returned_ballots"],
        }
        for d in municipality["district_data"]
    )
    votes = pd.DataFrame(
        {
            "district_code": d["district_code"],
            "party_name": names.get(v["party_list_number"], str(v["party_list_number"])),
            "votes": v["votes"],
        }
        for d in municipality["district_data"]
        for v in d["party_votes"]
    )
    return precinct_table(districts, votes)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--code", default="554782", help="council code (default: Prague)")
    parser.add_argument("--election", default="kv2026")
    parser.add_argument("--previous", default="kv2022")
    parser.add_argument("--draws", type=int, default=500)
    parser.add_argument("--tune", type=int, default=700)
    parser.add_argument("--chains", type=int, default=4)
    parser.add_argument(
        "--max-precincts", type=int, default=0, help="random subsample for a faster run"
    )
    args = parser.parse_args()

    import arviz as az
    import pymc as pm

    previous, current = match_precincts(
        load_precinct_table(args.previous, args.code),
        load_precinct_table(args.election, args.code),
    )
    if args.max_precincts and len(previous) > args.max_precincts:
        keep = np.random.default_rng(0).choice(len(previous), args.max_precincts, replace=False)
        previous, current = previous.iloc[keep], current.iloc[keep]

    sources, targets = group_columns(previous), group_columns(current)
    x = previous[sources].div(previous["registered"], axis=0).to_numpy()
    x = x / x.sum(axis=1, keepdims=True)
    counts = np.rint(current[targets].to_numpy()).astype(int)
    totals = counts.sum(axis=1)
    n, rows, cols = len(x), len(sources), len(targets)
    print(f"{n} precincts, {rows} x {cols} groups")

    with pm.Model() as model:
        mean_rates = pm.Dirichlet("mean_rates", a=np.ones((rows, cols)), shape=(rows, cols))
        concentration = pm.Gamma("concentration", alpha=2.0, beta=0.05, shape=rows)
        precinct_rates = pm.Dirichlet(
            "precinct_rates",
            a=(mean_rates * concentration[:, None])[None, :, :],
            shape=(n, rows, cols),
        )
        expected = (x[:, :, None] * precinct_rates).sum(axis=1)
        pm.Multinomial("observed", n=totals, p=expected, observed=counts)

        started = time.time()
        trace = pm.sample(
            draws=args.draws,
            tune=args.tune,
            chains=args.chains,
            nuts_sampler="nutpie",
            random_seed=1,
            progressbar=False,
        )
    print(f"sampled in {(time.time() - started) / 60:.1f} min")

    # City-wide rate of a group = precinct rates weighted by the group's voters there
    weights = previous[sources].to_numpy()
    weights = weights / weights.sum(axis=0, keepdims=True)
    draws = trace.posterior["precinct_rates"].stack(sample=("chain", "draw")).to_numpy()
    citywide = np.einsum("ir,ircs->rcs", weights, draws)

    regression = estimate_flows(previous, current)["transitions"]
    table = pd.DataFrame(
        {
            "source": np.repeat(sources, cols),
            "target": np.tile(targets, rows),
            "bayes_mean": citywide.mean(axis=2).ravel(),
            "bayes_p05": np.percentile(citywide, 5, axis=2).ravel(),
            "bayes_p95": np.percentile(citywide, 95, axis=2).ravel(),
            "regression": regression.to_numpy().ravel(),
        }
    )
    summary = az.summary(trace, var_names=["mean_rates", "concentration"])
    diagnostics = {
        "precincts": n,
        "divergences": int(trace.sample_stats["diverging"].sum()),
        "max_rhat": float(summary["r_hat"].max()),
        "min_ess_bulk": float(summary["ess_bulk"].min()),
        "minutes": round((time.time() - started) / 60, 1),
    }
    print(diagnostics)

    out_dir = Path(f"output/{args.election}/reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(out_dir / f"bayesian_flows_{args.code}.csv", index=False)
    (out_dir / f"bayesian_flows_{args.code}_diagnostics.json").write_text(
        json.dumps(diagnostics, indent=2), encoding="utf-8"
    )

    pd.set_option("display.width", 220)
    pivot = lambda column: (table.pivot(index="source", columns="target", values=column) * 100).round(0)  # noqa: E731
    print("\nBayes (posterior mean, %)\n", pivot("bayes_mean").loc[sources, targets].to_string())
    print("\nRegression (%)\n", pivot("regression").loc[sources, targets].to_string())
    difference = (table["bayes_mean"] - table["regression"]).abs()
    print(f"\nMean absolute difference: {difference.mean() * 100:.1f} p. p., max {difference.max() * 100:.1f}")


if __name__ == "__main__":
    main()

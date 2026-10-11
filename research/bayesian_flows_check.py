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
        "--model",
        choices=["hierarchical", "simple"],
        default="hierarchical",
        help="hierarchical: every precinct has its own rates (slow, needs many precincts); "
        "simple: one set of rates plus noise (minutes, for district councils)",
    )
    parser.add_argument(
        "--progress-seconds", type=int, default=60, help="how often to report progress"
    )
    parser.add_argument(
        "--max-precincts", type=int, default=0, help="random subsample for a faster run"
    )
    args = parser.parse_args()

    import arviz as az
    import nutpie
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

    with pm.Model() as model:  # noqa: F841 - used below
        mean_rates = pm.Dirichlet("mean_rates", a=np.ones((rows, cols)), shape=(rows, cols))
        if args.model == "simple":
            # One set of rates for the whole council. Precincts differ from it
            # only by noise, whose size is estimated (Dirichlet-multinomial).
            # rows x cols + 1 parameters instead of precincts x rows x cols.
            concentration = pm.LogNormal("concentration", mu=np.log(500.0), sigma=1.5)
            pm.DirichletMultinomial(
                "observed", n=totals, a=concentration * (x @ mean_rates), observed=counts
            )
        else:
            concentration = pm.Gamma("concentration", alpha=2.0, beta=0.05, shape=rows)
            precinct_rates = pm.Dirichlet(
                "precinct_rates",
                a=(mean_rates * concentration[:, None])[None, :, :],
                shape=(n, rows, cols),
            )
            expected = (x[:, :, None] * precinct_rates).sum(axis=1)
            pm.Multinomial("observed", n=totals, p=expected, observed=counts)

        started = time.time()
        out_dir = Path(f"output/{args.election}/reports")
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = f"bayesian_flows_{args.code}" + ("_simple" if args.model == "simple" else "")
        progress_file = out_dir / f"{stem}_progress.txt"

        def report_progress(chains):
            """One status line per call, on stdout and in the progress file.

            The terminal progress bar prints nothing when output goes to a
            log, and a run takes minutes to hours.
            """
            done = sum(chain.finished_draws for chain in chains)
            total = sum(chain.total_draws for chain in chains)
            minutes = (time.time() - started) / 60
            remaining = minutes * (total - done) / done if done else float("nan")
            line = (
                f"{time.strftime('%H:%M')}  {done / total * 100:5.1f} %  "
                f"({done}/{total} draws, "
                f"{sum(chain.tuning for chain in chains)} of {len(chains)} chains still tuning)  "
                f"running {minutes:.0f} min, about {remaining:.0f} min left"
            )
            print(line, flush=True)
            progress_file.write_text(line + "\n", encoding="utf-8")

        # nutpie directly: pm.sample() does not let us pass a progress callback
        trace = nutpie.sample(
            nutpie.compile_pymc_model(model),
            draws=args.draws,
            tune=args.tune,
            chains=args.chains,
            seed=1,
            progress_bar=False,
            progress_callback=report_progress,
            progress_rate=args.progress_seconds * 1000,
        )
        posterior, sample_stats = trace["posterior"], trace["sample_stats"]
        progress_file.write_text(
            f"{time.strftime('%H:%M')}  finished in {(time.time() - started) / 60:.0f} min\n",
            encoding="utf-8",
        )
    print(f"sampled in {(time.time() - started) / 60:.1f} min")

    if args.model == "simple":
        per_chain = posterior["mean_rates"].to_numpy()
    else:
        # City-wide rate of a group = precinct rates weighted by the group's voters there
        weights = previous[sources].to_numpy()
        weights = weights / weights.sum(axis=0, keepdims=True)
        per_chain = np.einsum(
            "ir,kdirc->kdrc", weights, posterior["precinct_rates"].to_numpy()
        )
    citywide = per_chain.reshape(-1, rows, cols).transpose(1, 2, 0)

    # The hyperparameters often mix poorly even when the city-wide rates, which
    # are what we report, agree between chains. Check those directly.
    np.save(out_dir / f"{stem}_citywide_draws.npy", per_chain)
    chain_means = per_chain.mean(axis=1)
    chain_spread = chain_means.max(axis=0) - chain_means.min(axis=0)
    citywide_rhat = az.rhat(az.convert_to_dataset({"rate": per_chain}))["rate"].to_numpy()

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
    hyperparameters = az.convert_to_dataset(
        {name: posterior[name].to_numpy() for name in ("mean_rates", "concentration")}
    )
    hyper_rhat = max(float(v.max()) for v in az.rhat(hyperparameters).data_vars.values())
    hyper_ess = min(float(v.min()) for v in az.ess(hyperparameters).data_vars.values())
    diagnostics = {
        "model": args.model,
        "precincts": n,
        "divergences": int(sample_stats["diverging"].sum()),
        "max_rhat_hyperparameters": hyper_rhat,
        "min_ess_bulk_hyperparameters": hyper_ess,
        "max_rhat_citywide_rates": float(citywide_rhat.max()),
        "max_difference_between_chains_pp": float(chain_spread.max() * 100),
        "mean_difference_between_chains_pp": float(chain_spread.mean() * 100),
        "minutes": round((time.time() - started) / 60, 1),
    }
    print(diagnostics)

    table.to_csv(out_dir / f"{stem}.csv", index=False)
    (out_dir / f"{stem}_diagnostics.json").write_text(
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

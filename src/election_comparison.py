#!/usr/bin/env python3
"""
Comparison of two elections for the same council at precinct level.

Builds matched precinct tables and estimates how voters moved between the
elections (ecological regression in the spirit of Goodman, like ei_models.py,
but for all groups at once and with the estimates constrained to valid shares).
"""

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

NON_VOTERS = "Nevoliči"
OTHER_LISTS = "Ostatní kandidátky"

# Precincts whose electorate changed more than this are most likely redrawn
MAX_ELECTORATE_CHANGE = 0.35


def precinct_table(
    district_df: pd.DataFrame,
    district_party_df: pd.DataFrame,
    min_share: float = 0.03,
    max_lists: int = 8,
) -> pd.DataFrame:
    """One row per precinct: registered voters and voters of each group.

    Municipal voters cast as many votes as there are seats, so votes are first
    converted to voters: a list's share of the precinct's votes times the
    number of returned envelopes. Lists below `min_share` of all votes (or
    beyond the `max_lists` strongest) are merged into OTHER_LISTS, and people
    who did not vote form NON_VOTERS. Group columns add up to `registered`.
    """
    turnout = (
        district_df.assign(district_code=district_df["district_code"].astype(str))
        .groupby("district_code")[["registered_voters", "returned_ballots"]]
        .sum()
    )
    turnout = turnout[turnout["registered_voters"] > 0]

    votes = district_party_df.assign(
        district_code=district_party_df["district_code"].astype(str)
    ).pivot_table(
        index="district_code",
        columns="party_name",
        values="votes",
        aggfunc="sum",
        fill_value=0,
    )
    votes = votes.reindex(turnout.index, fill_value=0)

    totals = votes.sum().sort_values(ascending=False)
    all_votes = totals.sum()
    kept = [
        name
        for name in totals.index[:max_lists]
        if all_votes > 0 and totals[name] / all_votes >= min_share
    ]

    precinct_votes = votes.sum(axis=1).replace(0, np.nan)
    ballots = turnout["returned_ballots"].clip(upper=turnout["registered_voters"])

    table = pd.DataFrame(index=turnout.index)
    table["registered"] = turnout["registered_voters"]
    table["turnout"] = ballots / turnout["registered_voters"] * 100
    for name in kept:
        table[name] = (votes[name] / precinct_votes * ballots).fillna(0)
    if len(kept) < len(totals):
        others = votes.drop(columns=kept).sum(axis=1)
        table[OTHER_LISTS] = (others / precinct_votes * ballots).fillna(0)
    voted = table.drop(columns=["registered", "turnout"]).sum(axis=1)
    table[NON_VOTERS] = (table["registered"] - voted).clip(lower=0)
    return table


def group_columns(table: pd.DataFrame) -> List[str]:
    return [column for column in table.columns if column not in ("registered", "turnout")]


def match_precincts(
    previous: pd.DataFrame, current: pd.DataFrame
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Keep precincts present in both elections with a comparable electorate."""
    common = previous.index.intersection(current.index)
    previous, current = previous.loc[common], current.loc[common]
    change = (current["registered"] - previous["registered"]).abs() / previous[
        "registered"
    ]
    stable = change <= MAX_ELECTORATE_CHANGE
    return previous[stable], current[stable]


def _project_rows_to_simplex(matrix: np.ndarray) -> np.ndarray:
    """Euclidean projection of every row onto {b >= 0, sum(b) = 1}."""
    sorted_rows = np.sort(matrix, axis=1)[:, ::-1]
    cumulative = np.cumsum(sorted_rows, axis=1) - 1
    positions = np.arange(1, matrix.shape[1] + 1)
    feasible = sorted_rows - cumulative / positions > 0
    last = feasible.shape[1] - 1 - np.argmax(feasible[:, ::-1], axis=1)
    theta = cumulative[np.arange(matrix.shape[0]), last] / (last + 1)
    return np.maximum(matrix - theta[:, None], 0)


def estimate_transition_matrix(
    source_shares: np.ndarray,
    target_shares: np.ndarray,
    weights: np.ndarray,
    iterations: int = 20000,
) -> np.ndarray:
    """Share of each source group that ended up in each target group.

    Assumes the same transition rates in every precinct and finds the matrix B
    (rows: source groups, non-negative, summing to 1) that minimises the
    weighted squared error of `source_shares @ B` against `target_shares`.
    Solved by accelerated projected gradient, so no solver dependency.
    """
    x = np.asarray(source_shares, dtype=float)
    y = np.asarray(target_shares, dtype=float)
    w = np.asarray(weights, dtype=float)
    w = w / w.sum()

    # numpy on macOS (Accelerate) reports spurious floating point warnings in matmul
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        gram = x.T @ (x * w[:, None])
        cross = x.T @ (y * w[:, None])
    step = 1.0 / max(np.linalg.eigvalsh(gram)[-1], 1e-12)

    estimate = np.full((x.shape[1], y.shape[1]), 1.0 / y.shape[1])
    momentum = estimate.copy()
    t = 1.0
    for _ in range(iterations):
        with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
            gradient = gram @ momentum - cross
        updated = _project_rows_to_simplex(momentum - step * gradient)
        t_next = (1 + np.sqrt(1 + 4 * t * t)) / 2
        momentum = updated + (t - 1) / t_next * (updated - estimate)
        if np.abs(updated - estimate).max() < 1e-10:
            estimate = updated
            break
        estimate, t = updated, t_next
    return estimate


def estimate_flows(previous: pd.DataFrame, current: pd.DataFrame) -> Dict:
    """Voter flows between two matched precinct tables.

    Returns the transition matrix (rows: groups of the previous election,
    values: share of that group), the same flows as shares of the whole
    electorate, and how well the model reproduces the current results.
    """
    sources, targets = group_columns(previous), group_columns(current)
    x = previous[sources].div(previous["registered"], axis=0).to_numpy()
    y = current[targets].div(current["registered"], axis=0).to_numpy()
    weights = current["registered"].to_numpy(dtype=float)

    matrix = estimate_transition_matrix(x, y, weights)

    source_size = previous[sources].sum() / previous["registered"].sum()
    transitions = pd.DataFrame(matrix, index=sources, columns=targets)
    electorate_flows = transitions.mul(source_size, axis=0)

    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        predicted = x @ matrix
    actual_total = current[targets].sum() / current["registered"].sum()
    residual = ((y - predicted) ** 2 * weights[:, None]).sum()
    spread = ((y - actual_total.to_numpy()) ** 2 * weights[:, None]).sum()

    return {
        "transitions": transitions,
        "electorate_flows": electorate_flows,
        "source_size": source_size,
        "target_size": actual_total,
        "predicted_target_size": electorate_flows.sum(),
        "explained_variation": float(1 - residual / spread) if spread > 0 else 0.0,
        "precincts": len(previous),
    }

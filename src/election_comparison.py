#!/usr/bin/env python3
"""
Comparison of two elections for the same council at precinct level.

Builds matched precinct tables and estimates how voters moved between the
elections (ecological regression in the spirit of Goodman, like ei_models.py,
but for all groups at once and with the estimates constrained to valid shares).
"""

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Bump when the estimate changes, so that cached results are recomputed
FLOW_MODEL_VERSION = 4

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
    start: Optional[np.ndarray] = None,
    tolerance: float = 1e-10,
) -> np.ndarray:
    """Share of each source group that ended up in each target group.

    Assumes the same transition rates in every precinct and finds the matrix B
    (rows: source groups, non-negative, summing to 1) that minimises the
    weighted squared error of `source_shares @ B` against `target_shares`.
    Solved by accelerated projected gradient with restarts, so no solver
    dependency.
    `start` is an initial guess (a previous solution speeds up refits).
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

    if start is None:
        estimate = np.full((x.shape[1], y.shape[1]), 1.0 / y.shape[1])
    else:
        estimate = np.array(start, dtype=float)
    momentum = estimate.copy()
    t = 1.0
    for _ in range(iterations):
        with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
            gradient = gram @ momentum - cross
        updated = _project_rows_to_simplex(momentum - step * gradient)
        # Restart the momentum when it points uphill; about 20x fewer iterations
        if ((momentum - updated) * (updated - estimate)).sum() > 0:
            t = 1.0
        t_next = (1 + np.sqrt(1 + 4 * t * t)) / 2
        momentum = updated + (t - 1) / t_next * (updated - estimate)
        if np.abs(updated - estimate).max() < tolerance:
            estimate = updated
            break
        estimate, t = updated, t_next
    return estimate


def _cluster_precincts(
    features: np.ndarray, clusters: int, seed: int = 0
) -> Tuple[np.ndarray, np.ndarray]:
    """Plain k-means; returns the label of every precinct and the centres."""
    rng = np.random.default_rng(seed)
    centres = features[rng.choice(len(features), clusters, replace=False)]
    labels = np.zeros(len(features), dtype=int)
    for _ in range(100):
        distances = ((features[:, None, :] - centres[None, :, :]) ** 2).sum(axis=2)
        new_labels = distances.argmin(axis=1)
        if (new_labels == labels).all() and _ > 0:
            break
        labels = new_labels
        for cluster in range(clusters):
            if (labels == cluster).any():
                centres[cluster] = features[labels == cluster].mean(axis=0)
    return labels, centres


def _nearest_centre(features: np.ndarray, centres: np.ndarray) -> np.ndarray:
    return ((features[:, None, :] - centres[None, :, :]) ** 2).sum(axis=2).argmin(axis=1)


def _standardise(x: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean, spread = x.mean(axis=0), x.std(axis=0)
    spread[spread == 0] = 1
    return (x - mean) / spread, mean, spread


def precinct_type_labels(x: np.ndarray, precinct_types: int) -> np.ndarray:
    """Which type every precinct belongs to, for a given number of types."""
    if precinct_types > 1:
        return _cluster_precincts(_standardise(x)[0], precinct_types)[0]
    return np.zeros(len(x), dtype=int)


def _fit_by_type(x, y, weights, labels, starts=None, quick=False) -> List[np.ndarray]:
    """One transition matrix per precinct type.

    `quick` trades the last decimals for speed; it is used for the many refits
    behind the choice of precinct types and the intervals, where an error of
    a tenth of a percentage point does not matter.
    """
    matrices = []
    for precinct_type in range(labels.max() + 1):
        mask = labels == precinct_type
        matrices.append(
            estimate_transition_matrix(
                x[mask],
                y[mask],
                weights[mask],
                start=None if starts is None else starts[precinct_type],
                iterations=600 if quick else 20000,
                tolerance=1e-6 if quick else 1e-10,
            )
        )
    return matrices


def choose_precinct_types(
    x: np.ndarray, y: np.ndarray, weights: np.ndarray, folds: int = 5
) -> int:
    """How many types of precincts to estimate separately.

    Voters of the same list need not behave alike in a city centre and on a
    housing estate. Precincts are therefore grouped by how they voted last
    time, and the number of groups is the one that best predicts the current
    result in precincts left out of the fit. More groups must improve the
    error by at least 2 % to be preferred, and every group needs enough
    precincts to estimate a full transition matrix.
    """
    groups = x.shape[1]
    min_size = max(60, 6 * groups)
    candidates = [k for k in (1, 2, 3, 4, 6) if len(x) // k >= min_size]
    if len(candidates) < 2:
        return 1

    rng = np.random.default_rng(0)
    fold_of = rng.permutation(len(x)) % folds
    errors = {}
    for k in candidates:
        error = 0.0
        for fold in range(folds):
            train, test = fold_of != fold, fold_of == fold
            features, mean, spread = _standardise(x[train])
            if k == 1:
                train_labels = np.zeros(train.sum(), dtype=int)
                test_labels = np.zeros(test.sum(), dtype=int)
            else:
                train_labels, centres = _cluster_precincts(features, k)
                test_labels = _nearest_centre((x[test] - mean) / spread, centres)
            if np.bincount(train_labels, minlength=k).min() < groups * 3:
                error = np.inf
                break
            matrices = _fit_by_type(
                x[train], y[train], weights[train], train_labels, quick=True
            )
            with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
                predicted = np.einsum(
                    "ir,irc->ic", x[test], np.array(matrices)[test_labels]
                )
            error += (((y[test] - predicted) ** 2) * weights[test][:, None]).sum()
        errors[k] = error

    best = candidates[0]
    for k in candidates[1:]:
        if errors[k] < errors[best] * 0.98:
            best = k
    return best


def _aggregate(matrices, labels, source_voters) -> np.ndarray:
    """City-wide transition matrix from per-type matrices.

    Each type's matrix is weighted by how many voters of the source group
    live in that type of precinct.
    """
    by_type = np.array(
        [source_voters[labels == t].sum(axis=0) for t in range(len(matrices))]
    )
    flows = (by_type[:, :, None] * np.array(matrices)).sum(axis=0)
    totals = by_type.sum(axis=0)
    totals[totals == 0] = 1
    return flows / totals[:, None]


def estimate_flows(
    previous: pd.DataFrame,
    current: pd.DataFrame,
    resamples: int = 100,
    interval: float = 0.9,
) -> Dict:
    """Voter flows between two matched precinct tables.

    Returns the transition matrix (rows: groups of the previous election,
    values: share of that group), the same flows as shares of the whole
    electorate, an interval for both from refitting on resampled precincts,
    and how well the model reproduces the current results.

    The interval shows how much the estimate depends on which precincts are
    in the data. It does not cover the error of the model's assumptions.
    """
    sources, targets = group_columns(previous), group_columns(current)
    x = previous[sources].div(previous["registered"], axis=0).to_numpy()
    y = current[targets].div(current["registered"], axis=0).to_numpy()
    weights = current["registered"].to_numpy(dtype=float)
    source_voters = previous[sources].to_numpy(dtype=float)

    precinct_types = choose_precinct_types(x, y, weights)
    labels = precinct_type_labels(x, precinct_types)

    matrices = _fit_by_type(x, y, weights, labels)
    matrix = _aggregate(matrices, labels, source_voters)

    source_size = previous[sources].sum() / previous["registered"].sum()
    transitions = pd.DataFrame(matrix, index=sources, columns=targets)
    electorate_flows = transitions.mul(source_size, axis=0)

    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        predicted = np.einsum("ir,irc->ic", x, np.array(matrices)[labels])
    actual_total = current[targets].sum() / current["registered"].sum()
    residual = ((y - predicted) ** 2 * weights[:, None]).sum()
    spread = ((y - actual_total.to_numpy()) ** 2 * weights[:, None]).sum()

    result = {
        "transitions": transitions,
        "electorate_flows": electorate_flows,
        "source_size": source_size,
        "target_size": actual_total,
        "predicted_target_size": electorate_flows.sum(),
        "explained_variation": float(1 - residual / spread) if spread > 0 else 0.0,
        "precincts": len(previous),
        "precinct_types": precinct_types,
        "interval": interval,
    }

    if resamples > 0:
        rng = np.random.default_rng(0)
        registered = previous["registered"].to_numpy(dtype=float)
        draws_transitions, draws_flows = [], []
        for _ in range(resamples):
            # Resample within every type so that none of them runs empty
            picked = np.concatenate(
                [
                    rng.choice(np.flatnonzero(labels == t), (labels == t).sum())
                    for t in range(precinct_types)
                ]
            )
            refit = _fit_by_type(
                x[picked],
                y[picked],
                weights[picked],
                labels[picked],
                starts=matrices,
                quick=True,
            )
            resampled = _aggregate(refit, labels[picked], source_voters[picked])
            size = source_voters[picked].sum(axis=0) / registered[picked].sum()
            draws_transitions.append(resampled)
            draws_flows.append(resampled * size[:, None])

        tail = (1 - interval) / 2 * 100
        for key, draws, point in (
            ("transitions", draws_transitions, transitions),
            ("electorate_flows", draws_flows, electorate_flows),
        ):
            low, high = np.percentile(np.array(draws), [tail, 100 - tail], axis=0)
            frame = lambda values: pd.DataFrame(values, index=sources, columns=targets)  # noqa: E731
            result[f"{key}_low"] = frame(np.minimum(low, point.to_numpy()))
            result[f"{key}_high"] = frame(np.maximum(high, point.to_numpy()))
            if key == "electorate_flows":
                result["electorate_flow_draws"] = np.array(draws)

    return result

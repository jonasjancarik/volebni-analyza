#!/usr/bin/env python3
"""
EI model helpers (Goodman regression + Duncan-Davis bounds).
"""

from typing import Dict, List

import numpy as np
import pandas as pd


def goodman_estimates(
    df: pd.DataFrame, party_columns: List[str], pirate_share_col: str
) -> Dict[str, Dict[str, float]]:
    results: Dict[str, Dict[str, float]] = {}
    x = df[pirate_share_col].to_numpy()
    x_mean = x.mean()
    x_var = np.var(x)
    if x_var == 0:
        raise ValueError("Pirate share variance is zero; cannot run regression.")

    for col in party_columns:
        y = df[col].to_numpy()
        cov = np.mean((x - x_mean) * (y - y.mean()))
        slope = cov / x_var
        intercept = y.mean() - slope * x_mean
        pirate_estimate = intercept + slope
        results[col] = {
            "intercept": float(intercept),
            "slope": float(slope),
            "pirate_estimate": float(pirate_estimate),
        }

    return results


def duncan_davis_bounds(
    df: pd.DataFrame,
    party_columns: List[str],
    pirate_share_col: str,
    weight_col: str,
) -> Dict[str, tuple[float, float]]:
    bounds: Dict[str, tuple[float, float]] = {}
    p = df[pirate_share_col].to_numpy()
    weights = df[weight_col].to_numpy()

    for col in party_columns:
        m = df[col].to_numpy()
        lower = np.zeros_like(m)
        upper = np.ones_like(m)

        mask = p > 0
        lower[mask] = np.maximum(0, (m[mask] - (1 - p[mask])) / p[mask])
        upper[mask] = np.minimum(1, m[mask] / p[mask])

        weight = weights * p
        weight_sum = weight.sum()
        if weight_sum <= 0:
            bounds[col] = (0.0, 1.0)
            continue

        lower_avg = float(np.sum(weight * lower) / weight_sum)
        upper_avg = float(np.sum(weight * upper) / weight_sum)
        bounds[col] = (lower_avg, upper_avg)

    return bounds

"""Run with: uv run --with pytest pytest tests/"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).parent.parent / "src"))

from election_comparison import (  # noqa: E402
    NON_VOTERS,
    OTHER_LISTS,
    estimate_flows,
    estimate_transition_matrix,
    match_precincts,
    precinct_table,
)


def test_transition_matrix_is_recovered_from_synthetic_precincts():
    rng = np.random.default_rng(1)
    truth = np.array(
        [
            [0.70, 0.20, 0.10],
            [0.10, 0.60, 0.30],
            [0.05, 0.05, 0.90],
        ]
    )
    source = rng.dirichlet([2, 2, 4], size=400)
    target = source @ truth + rng.normal(0, 0.005, size=(400, 3))
    weights = rng.integers(300, 1200, size=400)

    estimate = estimate_transition_matrix(source, target, weights)

    assert np.allclose(estimate.sum(axis=1), 1)
    assert (estimate >= 0).all()
    assert np.abs(estimate - truth).max() < 0.03


def test_precinct_table_converts_votes_to_voters():
    districts = pd.DataFrame(
        {
            "district_code": ["1", "2"],
            "registered_voters": [1000, 500],
            "returned_ballots": [400, 250],
        }
    )
    # 10 votes per voter; list C is below the 3 % threshold
    party_votes = pd.DataFrame(
        {
            "district_code": ["1", "1", "1", "2", "2", "2"],
            "party_name": ["A", "B", "C", "A", "B", "C"],
            "votes": [3000, 950, 50, 1500, 990, 10],
        }
    )

    table = precinct_table(districts, party_votes)

    assert list(table.columns) == ["registered", "turnout", "A", "B", OTHER_LISTS, NON_VOTERS]
    assert table.loc["1", "A"] == 300  # 75 % of 400 envelopes
    assert table.loc["1", NON_VOTERS] == 600
    groups = table.drop(columns=["registered", "turnout"]).sum(axis=1)
    assert np.allclose(groups, table["registered"])


def test_redrawn_precincts_are_left_out():
    previous = pd.DataFrame(
        {"registered": [1000, 1000, 800], "turnout": [40.0, 40.0, 40.0]},
        index=["1", "2", "3"],
    )
    current = pd.DataFrame(
        {"registered": [1050, 1600, 800], "turnout": [45.0, 45.0, 45.0]},
        index=["1", "2", "4"],
    )

    matched_previous, matched_current = match_precincts(previous, current)

    assert list(matched_previous.index) == ["1"]
    assert list(matched_current.index) == ["1"]


def test_flows_add_up_to_the_previous_electorate():
    rng = np.random.default_rng(2)
    registered = rng.integers(400, 1500, size=120)
    shares = rng.dirichlet([3, 2, 5], size=120)
    previous = pd.DataFrame(shares * registered[:, None], columns=["A", "B", NON_VOTERS])
    previous.insert(0, "turnout", 50.0)
    previous.insert(0, "registered", registered)
    moved = shares @ np.array([[0.8, 0.1, 0.1], [0.2, 0.6, 0.2], [0.05, 0.05, 0.9]])
    current = pd.DataFrame(moved * registered[:, None], columns=["A", "B", NON_VOTERS])
    current.insert(0, "turnout", 50.0)
    current.insert(0, "registered", registered)

    result = estimate_flows(previous, current)

    assert np.isclose(result["electorate_flows"].to_numpy().sum(), 1)
    assert abs(result["transitions"].loc["A", "A"] - 0.8) < 0.02
    assert result["explained_variation"] > 0.99

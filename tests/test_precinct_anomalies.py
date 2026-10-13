"""
The arithmetic of research/precinct_anomalies.py on results of the 2026
municipal elections that were checked by hand against the official ones.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "research"))

from precinct_anomalies import (  # noqa: E402
    breaks_of_pattern,
    candidate_order,
    closest_change,
    piles,
    seats_of,
    threshold,
)

# Council of Praha 10: votes and candidates of the ten lists, 45 seats
PRAHA_10 = pd.Series({1: 115075, 2: 111154, 3: 46, 4: 86305, 5: 182684, 6: 72222, 7: 165488, 8: 243590, 9: 289136, 10: 176752}, dtype=float)
PRAHA_10_CANDIDATES = pd.Series({number: 2 if number == 3 else 45 for number in PRAHA_10.index})

# Pirates in Praha 2: the first twelve of 35 candidates as counted, the rest
# evened out to the list's 50 122 votes (none of them is near the threshold)
PRAHA_2_PIRATES = np.array([2017, 1649, 1576, 1547, 1565, 1468, 1467, 1469, 1484, 1435, 1530, 1449] + [1368] * 22 + [1370], dtype=float)


def test_seats_of_praha_10_equal_the_official_ones():
    seats = seats_of(PRAHA_10, PRAHA_10_CANDIDATES, 45)

    assert seats.to_dict() == {1: 3, 2: 3, 3: 0, 4: 2, 5: 6, 6: 2, 7: 5, 8: 8, 9: 10, 10: 6}


def test_list_of_praha_10_is_99_votes_over_the_threshold():
    over = PRAHA_10 - threshold(PRAHA_10, PRAHA_10_CANDIDATES, 45)

    assert int(over[6]) == 99
    # A list of two candidates is measured against 2/45 of the votes
    assert over[3] < 0 and over[3] > -3200


def test_one_mistyped_count_moves_two_seats_in_praha_10():
    """A candidate of list 6 has 165 votes among neighbours with 15."""
    corrected = PRAHA_10.copy()
    corrected[6] -= 150

    seats = seats_of(corrected, PRAHA_10_CANDIDATES, 45)

    assert seats[6] == 0
    assert seats[1] == 4 and seats[4] == 3


def test_a_single_list_takes_part_whatever_its_share():
    votes = pd.Series({1: 418.0})

    assert seats_of(votes, pd.Series({1: 6}), 5).to_dict() == {1: 5}


def test_threshold_goes_down_when_one_list_alone_would_pass():
    votes = pd.Series({1: 960.0, 2: 40.0})
    candidates = pd.Series({1: 9, 2: 9})

    # 40 votes are 4 percent: under five, but a second list has to take part
    assert (votes >= threshold(votes, candidates, 9)).all()


def test_order_uses_the_average_cut_to_a_whole_number():
    """Praha-Královice: the average is 99.83, a tenth over it 109.82. The
    official order puts the candidate with 109 votes ahead of the one with
    106, which only the average cut to 99 gives."""
    votes = np.array([116, 118, 106, 112, 109, 38], dtype=float)

    assert candidate_order(votes) == [1, 0, 3, 4, 2, 5]


def test_exactly_a_tenth_over_the_average_is_enough():
    """Štítina: the average cut to a whole number is 90 and a tenth over it
    99, which the candidate with 99 votes reaches. In floating point 1.1 * 90
    is a hair more than 99."""
    votes = np.array([91, 148, 99, 100, 108, 66, 46, 108, 51], dtype=float)

    assert candidate_order(votes) == [1, 4, 7, 3, 2, 0, 5, 6, 8]


def test_order_keeps_the_ballot_for_those_under_the_threshold():
    order = candidate_order(PRAHA_2_PIRATES)

    # Three candidates are a tenth over the average; the fourth seat goes down the ballot
    assert order[:5] == [0, 1, 2, 3, 4]


def test_fifth_pirate_of_praha_2_is_eleven_votes_short():
    votes, place, sign = closest_change(PRAHA_2_PIRATES, 4)

    assert (votes, place, sign) == (11, 4, 1)


def test_a_mistyped_leader_holds_the_threshold_up_for_the_rest():
    """The leader has 340 votes in one precinct where 34 belong. Taking them
    away lowers the list's average, and the fifth candidate is a vote short."""
    corrected = PRAHA_2_PIRATES.copy()
    corrected[0] -= 306

    assert candidate_order(corrected)[:4] == [0, 1, 2, 3]
    assert closest_change(corrected, 4) == (1, 4, 1)


def test_no_change_is_possible_when_every_candidate_has_a_seat():
    assert closest_change(np.array([10.0, 12.0]), 2)[1] is None


def usual_precincts(candidates: int = 45, precincts: int = 12) -> np.ndarray:
    """Precincts counted as they should be: the leader a little ahead, the
    last candidates a little behind, the rest at the pile."""
    rows = []
    for index in range(precincts):
        pile = 20 + index
        row = np.full(candidates, float(pile))
        row[0] += 4
        row[-2:] -= 2
        rows.append(row)
    return np.array(rows)


def test_candidate_with_a_fraction_of_the_neighbours_is_missing_votes():
    matrix = usual_precincts()
    matrix[3, 8] = 2

    missing, extra, expected, _ = breaks_of_pattern(matrix)

    assert list(zip(*np.nonzero(missing))) == [(3, 8)]
    assert not extra.any()
    assert expected[3, 8] == 23


def test_usual_lead_and_usual_tail_are_not_flagged():
    missing, extra, _, mostly_empty = breaks_of_pattern(usual_precincts())

    assert not missing.any() and not extra.any() and not mostly_empty.any()


def test_empty_end_of_a_list_is_missing_votes():
    matrix = usual_precincts()
    matrix[5, -5:] = 0

    missing, _, _, mostly_empty = breaks_of_pattern(matrix)

    assert missing[5, -5:].all() and missing.sum() == 5
    assert not mostly_empty[5]


def test_ten_times_the_neighbours_is_extra():
    matrix = usual_precincts()
    matrix[7, 23] = 165

    missing, extra, _, _ = breaks_of_pattern(matrix)

    assert list(zip(*np.nonzero(extra))) == [(7, 23)]
    assert not missing.any()


def test_list_filled_in_only_for_candidates_with_own_votes():
    """Praha 10, precinct 10082: ten candidates have their votes, the other 35 none."""
    matrix = usual_precincts()
    matrix[2] = [11, 12, 12, 10, 10, 10, 9, 9, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 8, 0, 0, 0, 8] + [0] * 21

    missing, _, _, mostly_empty = breaks_of_pattern(matrix)

    assert piles(matrix)[2] == 10
    assert mostly_empty[2]
    assert missing[2].sum() == 35


def test_few_scattered_votes_are_not_a_pile():
    matrix = np.zeros((1, 20))
    matrix[0, :3] = [4, 2, 1]

    assert piles(matrix)[0] == 0
    assert not breaks_of_pattern(matrix)[0].any()

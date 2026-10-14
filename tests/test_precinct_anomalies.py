"""
The arithmetic of src/precinct_anomalies.py on results of the 2026
municipal elections that were checked by hand against the official ones.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from precinct_anomalies import (  # noqa: E402
    breaks_of_pattern,
    candidate_order,
    closest_change,
    piles,
    seats_of,
    slip_of_the_pen,
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

    breaks = breaks_of_pattern(matrix)

    assert list(zip(*np.nonzero(breaks.missing))) == [(3, 8)]
    assert not breaks.extra.any()
    assert breaks.expected[3, 8] == 23


def test_usual_lead_and_usual_tail_are_not_flagged():
    breaks = breaks_of_pattern(usual_precincts())

    assert not breaks.missing.any() and not breaks.extra.any() and not breaks.mostly_empty.any()


def test_empty_end_of_a_list_is_missing_votes():
    matrix = usual_precincts()
    matrix[5, -5:] = 0

    breaks = breaks_of_pattern(matrix)

    assert breaks.missing[5, -5:].all() and breaks.missing.sum() == 5
    assert not breaks.mostly_empty[5]


def test_low_end_of_a_list_with_some_votes_is_only_possibly_missing():
    matrix = usual_precincts()
    matrix[5, -6:] = 2

    breaks = breaks_of_pattern(matrix)

    assert not breaks.missing[5].any()
    assert breaks.possible[5, -6:].all()


def test_ten_times_the_neighbours_is_extra():
    matrix = usual_precincts()
    matrix[7, 23] = 165

    breaks = breaks_of_pattern(matrix)

    assert list(zip(*np.nonzero(breaks.extra))) == [(7, 23)]
    assert not breaks.missing.any()


# Whole-list ballots a list with a tenth of the votes would be expected to
# have in the twelve precincts of usual_precincts()
USUAL = np.array([20.0 + index for index in range(12)])
# The same for a list with a fraction of a percent
RARE = np.full(12, 2.0)


def small_list(candidates: int = 41) -> np.ndarray:
    """A list with next to no whole-list ballots: a vote for its leader here and there."""
    matrix = np.zeros((12, candidates))
    matrix[:, 0] = 1
    return matrix


def test_list_filled_in_only_for_candidates_with_own_votes():
    """Praha 10, precinct 10082: ten candidates have their votes, the other 35 none."""
    matrix = usual_precincts()
    matrix[2] = [11, 12, 12, 10, 10, 10, 9, 9, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 8, 0, 0, 0, 8] + [0] * 21

    breaks = breaks_of_pattern(matrix, USUAL)

    assert breaks.pile[2] == 10
    assert breaks.mostly_empty[2]
    assert breaks.missing[2].sum() == 35


def test_few_scattered_votes_are_not_a_pile():
    matrix = np.zeros((1, 20))
    matrix[0, :3] = [4, 2, 1]

    assert piles(matrix)[0] == 0
    assert not breaks_of_pattern(matrix, np.array([10.0])).missing.any()


def test_four_candidates_with_the_expected_pile_are_a_list_left_empty():
    """Praha 5, precinct 5029: four candidates of SPD have 13 votes each and
    the other 37 none, where the list would be expected to have about as many
    whole-list ballots."""
    matrix = usual_precincts(candidates=41)
    matrix[4] = 0
    matrix[4, [1, 2, 8, 27]] = 13

    breaks = breaks_of_pattern(matrix, USUAL)

    assert breaks.mostly_empty[4] and breaks.pile[4] == 13
    assert breaks.missing[4].sum() == 37


def test_leaders_voted_for_by_name_are_left_alone():
    """Praha 5, precinct 5036: the first three candidates of a list with a
    fraction of a percent have 8, 6 and 8 votes, the rest none. With next to
    no whole-list ballots expected, these may be votes for names."""
    matrix = small_list()
    matrix[3, :3] = [8, 6, 8]

    breaks = breaks_of_pattern(matrix, RARE)

    assert not breaks.missing.any() and not breaks.possible.any()


def test_three_leaders_far_under_the_expected_pile_are_left_alone():
    """The leaders may have been named by a few voters where the list happened
    to have no whole-list ballots; only a count near the expected one says otherwise."""
    matrix = usual_precincts()
    matrix[4] = 0
    matrix[4, :3] = [6, 5, 6]

    assert not breaks_of_pattern(matrix, USUAL).missing[4].any()


def test_same_small_count_all_over_a_list_needs_other_lists_left_incomplete():
    """Praha 5, precinct 5053: eleven candidates all over a small list have 4
    or 5 votes, the other thirty none. A few voters may have named the same
    people; it counts where the commission left another list empty for certain."""
    matrix = small_list()
    matrix[6, [0, 2, 3, 5, 6, 7, 9, 16, 18, 19, 28]] = [5, 4, 5, 4, 4, 5, 4, 4, 4, 4, 5]

    breaks = breaks_of_pattern(matrix, RARE)

    assert not breaks.missing.any()
    assert breaks.possible[6].sum() == 30 and breaks.possible.sum() == 30


def test_twelve_candidates_with_fourteen_votes_are_no_group_of_friends():
    """Praha 6, precinct 6078: a dozen candidates all over a list have 14 to
    16 votes each and the other 53 none. Fourteen voters do not name the same
    twelve people; the list had about that many whole-list ballots."""
    matrix = small_list(candidates=65)
    matrix[6, [0, 1, 2, 4, 6, 9, 15, 22, 30, 41, 50, 60]] = [16, 15, 14, 14, 14, 15, 14, 14, 16, 14, 14, 15]

    breaks = breaks_of_pattern(matrix, RARE)

    assert breaks.missing[6].sum() == 53


def test_the_first_ten_with_the_same_small_count_may_be_votes_for_names():
    """Voters who mark the first ten names give exactly this, with no error in the record."""
    matrix = small_list(candidates=65)
    matrix[6, :10] = 4

    breaks = breaks_of_pattern(matrix, RARE)

    assert not breaks.missing.any() and not breaks.possible.any()


def test_half_a_list_empty_is_an_error_even_far_under_the_expected_pile():
    """Brno, precinct 13009: the first 25 candidates of a list have 25 votes
    each and the other 30 none, where it would be expected to have about 70
    whole-list ballots. What the true count is cannot be said; the empty half is an error."""
    matrix = usual_precincts(candidates=55) * 3
    matrix[9] = 0
    matrix[9, :25] = 25

    breaks = breaks_of_pattern(matrix, USUAL * 3)

    assert breaks.missing[9].sum() == 30


def test_slips_of_the_pen_are_told_from_local_favourites():
    # A digit typed twice or one too many
    assert slip_of_the_pen(22, usual=2, pile=2, place=12, share=0.06) == ("zdvojená číslice", True)
    assert slip_of_the_pen(165, usual=15, pile=15, place=24, share=0.37) == ("číslice navíc", True)
    assert slip_of_the_pen(150, usual=16, pile=16, place=1, share=0.4) == ("číslice navíc", True)
    assert slip_of_the_pen(81, usual=18, pile=18, place=57, share=0.17) == ("přehozené číslice", True)
    assert slip_of_the_pen(35, usual=2, pile=2, place=35, share=0.14) == ("číslo kandidáta místo hlasů", True)
    # More than every seventh voter of the precinct would have had to name the candidate
    assert slip_of_the_pen(89, usual=20, pile=20, place=7, share=0.3) == ("příliš mnoho hlasů na jeden okrsek", True)


def test_counts_that_may_be_a_local_favourite_are_not_counted_as_slips():
    # Thrice the neighbours, but nothing says it is not a candidate people there know
    assert slip_of_the_pen(38, usual=11, pile=11, place=11, share=0.09) == ("", False)
    assert slip_of_the_pen(70, usual=20, pile=18, place=7, share=0.115) == ("", False)
    # A digit before a small count happens by accident often enough
    assert slip_of_the_pen(54, usual=4, pile=4, place=22, share=0.12) == ("možná číslice navíc", False)
    # Ten votes of one's own are common; 11 among ones need not be a doubled digit
    assert slip_of_the_pen(11, usual=1, pile=1, place=37, share=0.076) == ("možná číslice navíc", False)
    # A fifth of a hundred voters knowing one candidate is a village, not an error
    assert slip_of_the_pen(32, usual=7, pile=7, place=16, share=0.22) == ("", False)


def test_evidence_shows_the_first_candidate_left_out():
    from web_anomalies import _evidence

    row = {"okrsek": "29", "cislo_kandidatky": 3, "kandidatka": "List", "druh": "chybí", "vetsina_kandidatky_prazdna": False, "zjevny_preklep": False}
    found = pd.DataFrame(
        [
            {**row, "poradi": 41, "kandidat": "Last", "hlasy": 0, "obvykle": 11, "rozdil": -11, "okoli": "3 3 3 [0]"},
            {**row, "poradi": 34, "kandidat": "First", "hlasy": 4, "obvykle": 12, "rozdil": -8, "okoli": "12 12 12 [4] 4 4 3"},
            {**row, "okrsek": "6", "druh": "navíc", "poradi": 4, "kandidat": "Liked", "hlasy": 46, "obvykle": 30, "rozdil": 16, "okoli": "28 [46] 25"},
        ]
    )

    missing, extra = _evidence(found)

    assert (missing["candidates"], missing["votes"], missing["example"]["name"]) == (2, -19, "First")
    assert missing["counted"]
    # A count above the neighbours that is not several times theirs is shown, not counted
    assert extra["kind"] == "extra" and not extra["counted"]

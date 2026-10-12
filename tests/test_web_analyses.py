"""Run with: uv run --with pytest pytest tests/"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent / "src"))

from web_analyses import group_key, seat_allocation, seat_order, smallest_shift  # noqa: E402


def test_seats_are_divided_by_dhondt():
    votes = {"A": 100_000, "B": 81_000, "C": 30_000, "D": 19_000}

    assert seat_allocation(votes, 8) == {"A": 4, "B": 3, "C": 1}
    # The first quotient without a seat is the list that was closest to one
    assert seat_order(votes, 8)[8][1:] == ("B", 4)


def test_lists_under_the_threshold_get_no_seats():
    # 4 % of the votes would be worth a seat out of 30, were it not under 5 %
    allocation = seat_allocation({"A": 60, "B": 36, "C": 4}, 30)

    assert "C" not in allocation
    assert sum(allocation.values()) == 30


def test_smallest_shift_finds_the_first_step_that_is_enough():
    votes = {"A": 52_000, "B": 48_000}

    def move(count):
        return {"A": votes["A"] - count, "B": votes["B"] + count}

    def b_leads(result):
        return result["B"] > result["A"]

    assert smallest_shift(move, b_leads, limit=10_000) == 3000
    assert smallest_shift(move, b_leads, limit=2000) is None


def test_a_party_keeps_its_key_under_the_names_of_different_elections():
    assert group_key("SPD,Trik.,PES a nez. pro Prahu") == "spd"
    assert group_key("SPD pro Prahu s podp. Trikolory, PRO, Přísahy a NK") == "spd"
    assert group_key("Svoboda a přímá demokracie (SPD)") == "spd"
    assert group_key("SPOLU (ODS, KDU-ČSL, TOP 09)") == group_key("SPOLU pro Prahu") == "spolu"
    assert group_key("Česká pirátská strana") == "pirati"
    assert group_key("JSME PRAHA") is None

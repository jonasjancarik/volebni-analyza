"""Run with: uv run --with pytest pytest tests/"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent / "src"))

import pandas as pd  # noqa: E402

from web_analyses import (  # noqa: E402
    _SeatMath,
    group_key,
    seat_allocation,
    seat_order,
    smallest_shift,
)
from web_districts import (  # noqa: E402
    _on_ballots,
    _one_more_seat,
    _Prague5Seats,
    prague_1_key,
    prague_5_key,
    prague_5_part,
)


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


def test_shift_scenarios_find_the_fewest_voters_that_end_the_majority():
    # 11 seats, so a majority is 6; STAN and Spolu hold 6 between them
    council = {
        "seats": 11,
        "summary": {"ballots": 10_000},
        "lists": [
            {"name": "STAROSTOVÉ A NEZÁVISLÍ", "votes": 31_000},
            {"name": "SPOLU pro Prahu", "votes": 29_000},
            {"name": "PRAHA SOBĚ", "votes": 24_000},
            {"name": "Česká pirátská strana", "votes": 26_000},
        ],
    }
    seats = _SeatMath(council)
    assert seats.outcome("actual", seats.votes)["stanSpolu"] == 6

    [moved] = seats.shifts({"to-pirati": lambda count: seats.changed(spolu=-count, pirati=count)})

    assert moved["stanSpolu"] == 5
    # One step less would not have been enough
    less = seats.changed(spolu=-(moved["votes"] - 1000), pirati=moved["votes"] - 1000)
    assert not seats.without_majority(less)
    # 11 votes per ballot on average here
    assert moved["voters"] == round(moved["votes"] / 11)


def test_fewest_votes_for_a_given_number_of_seats():
    council = {
        "seats": 11,
        "summary": {"ballots": 10_000},
        "lists": [
            {"name": "STAROSTOVÉ A NEZÁVISLÍ", "votes": 31_000},
            {"name": "SPOLU pro Prahu", "votes": 29_000},
            {"name": "PRAHA SOBĚ", "votes": 24_000},
            {"name": "Česká pirátská strana", "votes": 26_000},
        ],
    }
    seats = _SeatMath(council)

    def new_voters(count):
        return seats.changed(pirati=count)

    # They already have six, so nothing has to move for "at most six"
    assert seats.fewest("new", new_voters, 6)["votes"] == 0
    five = seats.fewest("new", new_voters, 5)
    assert five["stanSpolu"] == 5 and five["votes"] > 0
    assert seats.rival_seats(new_voters(five["votes"] - 1000)) == 6



def test_lists_of_praha_5_keep_their_key_in_both_elections():
    assert prague_5_key("PRAHA 5 SOBĚ") == "praha5Sobe"
    assert prague_5_key("Koalice SEN 21 pro Prahu 5") == "sen"
    assert prague_5_key("SEN PRO PRAHU 5 s podporou senátora Lásky a SOPU") == "sen"
    # ODS and TOP 09 ran together in 2022 and apart in 2026
    assert prague_5_key("SPOLEČNĚ PRO PRAHU 5") == "odsTop"
    assert prague_5_key("Občanská demokratická strana") == "ods"
    assert prague_5_key("TOP Lidovci a Nezávislí") == "top"
    # Lists that carry the same name everywhere keep the city-wide key
    assert prague_5_key("Česká pirátská strana") == "pirati"
    assert prague_5_key("REZIDENTI 5P") is None


def test_precincts_of_praha_5_belong_to_neighbourhoods():
    assert prague_5_part("5001") == ("Malá Strana", "smichov")
    assert prague_5_part("5045") == ("Košíře", "kosire")
    # Barrandov is cut out of Hlubočepy by hand
    assert prague_5_part("5066") == ("Barrandov", "barrandov")
    assert prague_5_part("5067") == ("Hlubočepy", "jinonice")
    assert prague_5_part("9999") == (None, None)


def test_seats_of_praha_5_are_counted_by_blocs():
    # 11 seats; SEN's 8 000 votes are the first quotient left without one
    council = {
        "seats": 11,
        "summary": {"ballots": 10_000},
        "lists": [
            {"name": "PRAHA 5 SOBĚ", "votes": 30_000},
            {"name": "Občanská demokratická strana", "votes": 34_000},
            {"name": "STAROSTOVÉ A NEZÁVISLÍ", "votes": 26_000},
            {"name": "Česká pirátská strana", "votes": 12_000},
            {"name": "SEN PRO PRAHU 5 s podporou senátora Lásky a SOPU", "votes": 8_000},
        ],
    }
    seats = _Prague5Seats(council)

    actual = seats.outcome("actual", seats.votes)
    assert actual["seats"] == {"ods": 4, "praha5Sobe": 3, "stan": 3, "pirati": 1}
    assert actual["blocs"] == {"coalition2022": 4, "townHall": 7}

    # One list of the three wins the seat that SEN's votes alone were short of
    joint = seats.outcome("joint", seats.merged(seats.votes, ("praha5Sobe", "pirati", "sen")))
    assert joint["seats"]["joint"] == joint["blocs"]["coalition2022"] == 5
    assert joint["blocs"]["townHall"] == 6
    assert "pirati" not in joint["seats"]


def test_turnout_of_a_group_leaves_out_unusual_precincts():
    def ballot(rows):
        frame = pd.DataFrame(rows, columns=["id", "registered", "ballots", "votes", "pirati"]).set_index("id")
        return frame.assign(area="x")

    local = ballot([("1", 1000, 500, 5000, 500), ("2", 1000, 400, 4000, 800), ("3", 2000, 100, 1000, 100)])
    frames = {name: local for name in ("local", "previousLocal", "city", "previousCity", "parliamentary")}

    group = _on_ballots(frames, ["1", "3"], unusual=["3"])

    assert group["precincts"] == 2
    assert group["registered"] == 3000
    # Precinct 3 counts for the votes, not for the turnout
    assert group["turnout"]["now"] == 50
    assert group["local"]["pirati"] == 10


def test_lists_of_praha_1_keep_their_key_in_both_elections():
    assert prague_1_key("PRAHA 1 SOBĚ") == "praha1Sobe"
    # STAN and KDU-ČSL ran together both times, under another name in 2022
    assert prague_1_key("My, co tady žijeme") == "stanKdu"
    assert prague_1_key("Starostové, KDU-ČSL s podporou Iniciativy občanů") == "stanKdu"
    assert prague_1_key("TOP 09") == prague_1_key("TOP 09 – Srdce Prahy") == "top09"
    assert prague_1_key("Naše PRAHA 1") == "nasePraha1"
    assert prague_1_key("Piráti a občané z Prahy 1") == prague_1_key("Piráti a nezávislí pro Prahu 1") == "pirati"
    assert prague_1_key("Patrioti pro Prahu 1") is None


def test_one_more_seat_counts_the_threshold_too():
    # 30 seats; D has 4.9 % and no seat, though its votes would be worth one
    council = {
        "seats": 30,
        "summary": {"ballots": 10_000},
        "lists": [
            {"name": "A", "votes": 45_100},
            {"name": "B", "votes": 30_000},
            {"name": "C", "votes": 20_000},
            {"name": "D", "votes": 4_900},
        ],
    }
    seats = _SeatMath(council, key_of=lambda name: name, step=10)
    assert seat_allocation(seats.votes, 30) == {"A": 15, "B": 9, "C": 6}

    over = _one_more_seat(seats, "D")

    # 5 % of the votes after they are added: (4 900 + x) / (100 000 + x) >= 0.05
    assert over["votes"] == 110
    assert over["seats"] == 0
    assert over["voters"] == 11
    # The last seat was A's fifteenth
    assert over["from"] == "A"

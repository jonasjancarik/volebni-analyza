"""Run with: uv run --with pytest pytest tests/"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).parent.parent / "src"))

import places  # noqa: E402
import transit_times  # noqa: E402

NAN = float("nan")
LNG, LAT = places.CENTRE
# A degree of longitude and of latitude in metres at the centre
EAST = 111_320 * np.cos(np.radians(LAT))
NORTH = 110_570


def building(east=0.0, north=0.0, flats=NAN, use=7, construction=10, finished=1960):
    return [LNG + east / EAST, LAT + north / NORTH, flats, 2, use, construction, finished]


def square(name, west, east, size=400):
    corners = [(west, -size), (east, -size), (east, size), (west, size), (west, -size)]
    ring = [[LNG + x / EAST, LAT + y / NORTH] for x, y in corners]
    return {"properties": {"id": name}, "geometry": {"type": "Polygon", "coordinates": [ring]}}


def test_homes_are_sorted_into_kinds_by_their_building():
    table = places.homes(
        np.array(
            [
                building(use=7),  # a family house the register has no flats for
                building(use=3, flats=2),  # a small building for housing
                building(use=6, flats=40, construction=places.PANEL, finished=1978),
                building(use=6, flats=30, finished=2005),
                building(use=6, flats=12, finished=1930),
                building(use=3, flats=10, finished=1950),  # too large for a house
                building(use=19, flats=NAN),  # a garage
            ]
        )
    )

    assert list(table["kind"]) == ["houses", "houses", "panel", "newer", "older", "older"]
    assert table["flats"].iloc[0] == 1


def test_door_minutes_add_the_walk_to_the_ride_and_fall_back_to_walking():
    # A stop 500 m east of the first home, 10 minutes from the centre
    stops = np.array([[LNG + 3500 / EAST, LAT, 10.0]])
    homes_east = np.array([3000.0, 600.0, 9000.0])

    minutes = places.door_minutes(LNG + homes_east / EAST, np.full(3, LAT), stops)

    assert abs(minutes[0] - (500 / 60 + 10)) < 0.1
    # No stop near, but the centre is ten minutes on foot
    assert abs(minutes[1] - 10) < 0.1
    # No stop near and too far to walk
    assert np.isnan(minutes[2])


def test_a_precinct_is_of_the_kind_most_of_its_flats_are_in():
    features = [square("estate", 2000, 2800), square("village", 5000, 5800)]
    buildings = np.array(
        [
            building(east=2400, use=6, flats=60, construction=places.PANEL),
            *[building(east=2300 + 10 * i, north=100) for i in range(20)],
            *[building(east=5300 + 10 * i) for i in range(30)],
            building(east=5400, north=100, use=6, flats=8, finished=2010),
        ]
    )
    stops = np.array([[LNG + 2400 / EAST, LAT, 15.0]])

    table = places.precinct_places(features, buildings, stops)

    assert table.loc["estate", "kind"] == "panel"
    assert table.loc["estate", "flats"] == 80
    assert abs(table.loc["estate", "panel"] - 0.75) < 1e-9
    # Half of the flats are in the tower, which stands at the stop
    assert abs(table.loc["estate", "minutes"] - 15) < 0.1
    assert table.loc["village", "kind"] == "houses"
    # The village has no stop within walking distance
    assert np.isnan(table.loc["village", "minutes"])


def test_minutes_to_the_centre_count_waiting_and_changes():
    # A line runs every ten minutes from "far" over "near" to the centre, ten
    # minutes a stop. A feeder reaches "near" five minutes before each departure.
    names = ["far", "near", "centre", "feeder", "nowhere"]
    stops = pd.DataFrame(
        {
            "stop_lon": [LNG + east / EAST for east in (9000, 5000, 0, 5000, 20000)],
            "stop_lat": [LAT, LAT, LAT, LAT + 3000 / NORTH, LAT],
        }
    )
    far, near, centre, feeder = (names.index(name) for name in ("far", "near", "centre", "feeder"))
    rides = []
    for trip, start in enumerate(range(5 * 3600, 9 * 3600 + 1, 600)):
        rides.append((2 * trip, far, near, start, start + 600))
        rides.append((2 * trip, near, centre, start + 600, start + 1200))
        rides.append((2 * trip + 1, feeder, near, start, start + 300))
    connections = pd.DataFrame(rides, columns=["trip", "from_stop", "to_stop", "departure", "arrival"])
    connections = connections.sort_values("departure", ascending=False)

    minutes = transit_times.minutes_to_centre(stops, connections, given={})

    assert minutes[centre] == 0
    assert abs(minutes[near] - 10) < 1e-9
    assert abs(minutes[far] - 20) < 1e-9
    # Five minutes of riding, five of waiting for the line, ten on it
    assert abs(minutes[feeder] - 20) < 1e-9
    assert np.isnan(minutes[names.index("nowhere")])

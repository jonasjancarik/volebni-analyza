"""
How long it takes by public transport to reach the centre of Prague from
every stop, for placing precincts by travel time instead of by distance.

The source is the timetable of Prague Integrated Transport (PID) in GTFS,
published by ROPID. Run once, and again whenever a fresher timetable is
wanted (a 50 MB download, under a minute of computing):

    uv run python src/transit_times.py

It writes input/raw/transit_minutes.npy, an array of [longitude, latitude,
minutes] for every stop the centre can be reached from on a working morning.

The time of a stop is how long before a deadline one has to be at the stop to
reach the centre by that deadline, averaged over deadlines through the morning
peak. It therefore includes waiting, changes and the walk at the end, the way
a commuter would count it.
"""

import argparse
import io
import sys
import tempfile
import zipfile
from datetime import date, datetime, timedelta
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import requests

from places import TRANSIT_MINUTES_FILE, WALK_METRES_PER_SECOND, metres

GTFS_URL = "https://data.pid.cz/PID_GTFS.zip"

# How far one walks between stops when changing, and from the last stop
TRANSFER_WALK_METRES = 250
CENTRE_WALK_METRES = 500
# Time to change between vehicles at one stop when the timetable gives none
CHANGE_SECONDS = 60

FIRST_DEADLINE = 7 * 3600 + 30 * 60
LAST_DEADLINE = 9 * 3600
DEADLINE_STEP = 10 * 60
# Nobody in the city needs longer than this to the centre
LONGEST_TRIP = 3 * 3600

NEVER = -(10**9)


def download(target) -> None:
    print(f"Stahuji {GTFS_URL}")
    with requests.get(GTFS_URL, stream=True, timeout=120) as response:
        response.raise_for_status()
        for chunk in response.iter_content(chunk_size=1 << 20):
            target.write(chunk)
    target.flush()


def _table(archive: zipfile.ZipFile, name: str, **options) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(archive.read(name)), dtype=str, **options)


def working_day(archive: zipfile.ZipFile) -> date:
    """The first Tuesday the timetable covers; a plain working day."""
    feed = _table(archive, "feed_info.txt").iloc[0]
    day = datetime.strptime(feed["feed_start_date"], "%Y%m%d").date()
    while day.weekday() != 1:
        day += timedelta(days=1)
    return day


def services_on(archive: zipfile.ZipFile, day: date) -> set:
    stamp = day.strftime("%Y%m%d")
    weekday = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][day.weekday()]
    calendar = _table(archive, "calendar.txt")
    running = calendar[
        (calendar[weekday] == "1") & (calendar["start_date"] <= stamp) & (calendar["end_date"] >= stamp)
    ]
    services = set(running["service_id"])
    exceptions = _table(archive, "calendar_dates.txt")
    exceptions = exceptions[exceptions["date"] == stamp]
    services |= set(exceptions[exceptions["exception_type"] == "1"]["service_id"])
    services -= set(exceptions[exceptions["exception_type"] == "2"]["service_id"])
    return services


def _seconds(times: pd.Series) -> np.ndarray:
    parts = times.str.split(":", expand=True).astype("int64")
    return (parts[0] * 3600 + parts[1] * 60 + parts[2]).to_numpy()


def read_timetable(archive: zipfile.ZipFile, day: date):
    """Stops and the rides between neighbouring stops ("connections") of one morning."""
    stops = _table(archive, "stops.txt", usecols=["stop_id", "stop_lat", "stop_lon", "location_type"])
    stops = stops[stops["location_type"].fillna("0").isin(["0", ""])].reset_index(drop=True)
    index = pd.Series(np.arange(len(stops)), index=stops["stop_id"])

    trips = _table(archive, "trips.txt", usecols=["trip_id", "service_id"])
    running = set(trips[trips["service_id"].isin(services_on(archive, day))]["trip_id"])

    times = _table(
        archive,
        "stop_times.txt",
        usecols=["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"],
    )
    times = times[times["trip_id"].isin(running) & times["stop_id"].isin(index.index)]
    times = times.assign(
        arrival=_seconds(times["arrival_time"]),
        departure=_seconds(times["departure_time"]),
        sequence=times["stop_sequence"].astype("int64"),
        stop=index.reindex(times["stop_id"]).to_numpy(),
    ).sort_values(["trip_id", "sequence"])

    same_trip = (times["trip_id"].to_numpy()[1:] == times["trip_id"].to_numpy()[:-1])
    connections = pd.DataFrame(
        {
            "trip": pd.factorize(times["trip_id"].to_numpy()[:-1])[0],
            "from_stop": times["stop"].to_numpy()[:-1],
            "to_stop": times["stop"].to_numpy()[1:],
            "departure": times["departure"].to_numpy()[:-1],
            "arrival": times["arrival"].to_numpy()[1:],
        }
    )[same_trip]
    morning = (connections["departure"] >= FIRST_DEADLINE - LONGEST_TRIP) & (connections["arrival"] <= LAST_DEADLINE)
    connections = connections[morning].sort_values("departure", ascending=False)

    transfers = _table(archive, "transfers.txt", usecols=["from_stop_id", "to_stop_id", "min_transfer_time"])
    transfers = transfers[
        transfers["from_stop_id"].isin(index.index) & transfers["to_stop_id"].isin(index.index)
    ].dropna(subset=["min_transfer_time"])
    given = {
        (int(index[row.from_stop_id]), int(index[row.to_stop_id])): int(row.min_transfer_time)
        for row in transfers.itertuples()
    }
    return stops, connections, given


def footpaths(east: np.ndarray, north: np.ndarray, given: Dict[Tuple[int, int], int]) -> List[List[Tuple[int, int]]]:
    """For every stop, the stops one can walk from to change there, with the
    seconds it takes. Times from the timetable win over measured ones."""
    cell = TRANSFER_WALK_METRES
    grid: Dict[Tuple[int, int], List[int]] = {}
    keys = np.column_stack([np.floor(east / cell), np.floor(north / cell)]).astype("int64")
    for stop, key in enumerate(map(tuple, keys)):
        grid.setdefault(key, []).append(stop)

    paths: List[Dict[int, int]] = [{} for _ in range(len(east))]
    for stop, (column, row) in enumerate(map(tuple, keys)):
        for near in (other for dx in (-1, 0, 1) for dy in (-1, 0, 1) for other in grid.get((column + dx, row + dy), ())):
            if near == stop:
                continue
            distance = float(np.hypot(east[stop] - east[near], north[stop] - north[near]))
            if distance <= TRANSFER_WALK_METRES:
                paths[stop][near] = max(CHANGE_SECONDS, round(distance / WALK_METRES_PER_SECOND))
    for (origin, destination), seconds in given.items():
        if origin != destination:
            paths[destination][origin] = seconds
    return [list(walks.items()) for walks in paths]


def minutes_to_centre(stops: pd.DataFrame, connections: pd.DataFrame, given: Dict[Tuple[int, int], int]) -> np.ndarray:
    """Average minutes from every stop to the centre; NaN where it cannot be reached."""
    east, north = metres(stops["stop_lon"].astype(float), stops["stop_lat"].astype(float))
    walks = footpaths(east, north, given)
    change = np.full(len(stops), CHANGE_SECONDS, dtype="int64")
    for (origin, destination), seconds in given.items():
        if origin == destination:
            change[origin] = seconds
    change = change.tolist()

    to_centre = np.hypot(east, north)
    last_stops = [
        (int(stop), round(float(to_centre[stop]) / WALK_METRES_PER_SECOND))
        for stop in np.flatnonzero(to_centre <= CENTRE_WALK_METRES)
    ]
    if not last_stops:
        raise SystemExit("V jízdním řádu není žádná zastávka v centru.")

    trip = connections["trip"].tolist()
    from_stop = connections["from_stop"].tolist()
    to_stop = connections["to_stop"].tolist()
    departure = connections["departure"].tolist()
    arrival = connections["arrival"].tolist()
    trips = max(trip) + 1

    totals = np.zeros(len(stops))
    reached = np.zeros(len(stops), dtype="int64")
    for deadline in range(FIRST_DEADLINE, LAST_DEADLINE + 1, DEADLINE_STEP):
        # The latest moment one can stand at a stop, ready to board, and still make the deadline
        latest = [NEVER] * len(stops)
        for stop, walk in last_stops:
            # Getting off and walking to the centre needs no time to change
            latest[stop] = deadline - walk + change[stop]
        on_time = bytearray(trips)
        # From the last ride of the morning to the first, so that every ride
        # already knows whether what follows it still makes the deadline
        for ride in range(len(trip)):
            if arrival[ride] > deadline:
                continue
            destination = to_stop[ride]
            if on_time[trip[ride]] or arrival[ride] + change[destination] <= latest[destination]:
                on_time[trip[ride]] = 1
                leaves, origin = departure[ride], from_stop[ride]
                if leaves > latest[origin]:
                    latest[origin] = leaves
                    for near, walk in walks[origin]:
                        if leaves - walk > latest[near]:
                            latest[near] = leaves - walk
        for stop, walk in last_stops:
            # From a stop in the centre one simply walks
            latest[stop] = deadline - walk
        times = deadline - np.array(latest, dtype="float64")
        usable = times <= LONGEST_TRIP
        totals[usable] += times[usable]
        reached += usable

    deadlines = len(range(FIRST_DEADLINE, LAST_DEADLINE + 1, DEADLINE_STEP))
    return np.where(reached == deadlines, totals / np.maximum(reached, 1) / 60, np.nan)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--archive", help="Už stažený soubor GTFS; jinak se stáhne")
    parser.add_argument("--day", help="Den jízdního řádu, RRRRMMDD; výchozí je první úterý, které řád pokrývá")
    args = parser.parse_args()

    with tempfile.NamedTemporaryFile(suffix=".zip") as downloaded:
        path = args.archive
        if not path:
            download(downloaded)
            path = downloaded.name
        with zipfile.ZipFile(path) as archive:
            day = datetime.strptime(args.day, "%Y%m%d").date() if args.day else working_day(archive)
            stops, connections, given = read_timetable(archive, day)

    print(f"Jízdní řád na {day:%d. %m. %Y}: {len(stops):,} zastávek, {len(connections):,} úseků jízd".replace(",", " "))
    minutes = minutes_to_centre(stops, connections, given)
    table = np.column_stack(
        [stops["stop_lon"].astype(float), stops["stop_lat"].astype(float), minutes]
    )
    table = table[~np.isnan(minutes)].astype("float32")

    TRANSIT_MINUTES_FILE.parent.mkdir(parents=True, exist_ok=True)
    np.save(TRANSIT_MINUTES_FILE, table)
    print(f"Uloženo {len(table):,} zastávek do {TRANSIT_MINUTES_FILE}".replace(",", " "))
    return 0


if __name__ == "__main__":
    sys.exit(main())

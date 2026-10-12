"""
What kind of place a precinct is: how long it takes to the centre of the city
by public transport and what its people live in.

Both come from files prepared by scripts (src/transit_times.py for the
timetable, src/buildings.py for the buildings); this module only puts them
together with the outlines of the precincts.
"""

from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

RAW_INPUT_DIR = Path("input/raw")
TRANSIT_MINUTES_FILE = RAW_INPUT_DIR / "transit_minutes.npy"

# Můstek, where the three metro lines of the centre meet
CENTRE = (14.4245, 50.0835)

# Walking is measured in a straight line, so the speed is lower than a
# walker's: streets do not run straight and crossings take time
WALK_METRES_PER_SECOND = 1.0
# How far from home a stop is still worth walking to
STOP_WALK_METRES = 1000

BUILDING_COLUMNS = ("longitude", "latitude", "flats", "floors", "use", "construction", "finished")
# Codes of the address register
APARTMENT_BUILDING = 6
HOME_USES = (3, 6, 7)  # a building for housing, an apartment building, a family house
PANEL = 4
# A building for housing with more flats than this is counted with apartment buildings
LARGEST_HOUSE = 3
# Apartment buildings finished from this year on are the newer ones
NEWER_FROM = 1990

# Kinds of homes, by the building they are in
KINDS = ("houses", "older", "panel", "newer")
# A precinct is of the kind that holds at least this share of its flats
MAIN_KIND_SHARE = 0.5
MIXED = "mixed"


def buildings_file(municipality: str) -> Path:
    return RAW_INPUT_DIR / f"buildings_{municipality}.npy"


def metres(longitude, latitude) -> Tuple[np.ndarray, np.ndarray]:
    """Flat coordinates around the centre; good to a metre across the city."""
    east = (np.asarray(longitude, dtype="float64") - CENTRE[0]) * 111_320 * np.cos(np.radians(CENTRE[1]))
    north = (np.asarray(latitude, dtype="float64") - CENTRE[1]) * 110_570
    return east, north


def homes(buildings: np.ndarray) -> pd.DataFrame:
    """Buildings people live in, with the number of flats and the kind of home.

    Family houses and small buildings for housing are "houses". Apartment
    buildings are "panel" when built of panels, which is what housing estates
    are made of, "newer" when finished since 1990 and "older" otherwise:
    tenement blocks and brick housing up to the 1980s.
    """
    table = pd.DataFrame(np.asarray(buildings, dtype="float64"), columns=BUILDING_COLUMNS)
    table = table[table["use"].isin(HOME_USES) | (table["flats"] > 0)].copy()
    # The register does not know the flats of every house; a house is at least one
    table["flats"] = table["flats"].fillna(1).clip(lower=1)
    apartments = (table["use"] == APARTMENT_BUILDING) | (table["flats"] > LARGEST_HOUSE)
    table["kind"] = np.select(
        [~apartments, table["construction"] == PANEL, table["finished"] >= NEWER_FROM],
        ["houses", "panel", "newer"],
        default="older",
    )
    return table


def door_minutes(longitude, latitude, stops: np.ndarray) -> np.ndarray:
    """Minutes from each place to the centre: on foot to the stop that gets
    there soonest and from it by public transport, or on foot all the way
    when that is quicker. NaN where no stop is within walking distance."""
    import shapely

    east, north = metres(longitude, latitude)
    stop_east, stop_north = metres(stops[:, 0], stops[:, 1])
    place, stop = shapely.STRtree(shapely.points(stop_east, stop_north)).query(
        shapely.points(east, north), predicate="dwithin", distance=STOP_WALK_METRES
    )
    walk = np.hypot(east[place] - stop_east[stop], north[place] - stop_north[stop])
    best = np.full(len(east), np.inf)
    np.minimum.at(best, place, walk / WALK_METRES_PER_SECOND / 60 + stops[stop, 2])
    on_foot = np.hypot(east, north) / WALK_METRES_PER_SECOND / 60
    best = np.minimum(best, np.where(on_foot <= 30, on_foot, np.inf))
    return np.where(np.isfinite(best), best, np.nan)


def _middle(values: np.ndarray, weights: np.ndarray) -> float:
    """The value that half of the weight lies below."""
    order = np.argsort(values)
    running = np.cumsum(weights[order])
    return float(values[order][np.searchsorted(running, running[-1] / 2)])


def precinct_places(features: List[dict], buildings: np.ndarray, stops: Optional[np.ndarray]) -> pd.DataFrame:
    """One row per precinct that has homes: flats, the share of each kind of
    home, the kind of the precinct, kilometres from the centre and, with a
    timetable, minutes to it. Distances and times are those of a typical
    flat, so that a tower counts for more than a cottage."""
    import shapely
    from shapely.geometry import shape

    table = homes(buildings)
    table["km"] = np.hypot(*metres(table["longitude"], table["latitude"])) / 1000
    table["minutes"] = (
        door_minutes(table["longitude"], table["latitude"], stops) if stops is not None else np.nan
    )

    ids = np.array([feature["properties"]["id"] for feature in features])
    shapes = shapely.make_valid(np.array([shape(feature["geometry"]) for feature in features]))
    home, precinct = shapely.STRtree(shapes).query(
        shapely.points(table["longitude"].to_numpy(), table["latitude"].to_numpy()), predicate="within"
    )
    table = table.iloc[home].assign(precinct=ids[precinct])

    rows = []
    for name, part in table.groupby("precinct"):
        flats = part["flats"].to_numpy()
        timed = part["minutes"].notna().to_numpy()
        row = {
            "precinct": name,
            "flats": float(flats.sum()),
            "km": float(np.average(part["km"], weights=flats)),
            "minutes": _middle(part["minutes"].to_numpy()[timed], flats[timed]) if timed.any() else np.nan,
        }
        for kind in KINDS:
            row[kind] = float(flats[(part["kind"] == kind).to_numpy()].sum() / flats.sum())
        rows.append(row)
    places = pd.DataFrame(rows).set_index("precinct")
    main = places[list(KINDS)].idxmax(axis=1)
    places["kind"] = main.where(places[list(KINDS)].max(axis=1) >= MAIN_KIND_SHARE, MIXED)
    return places

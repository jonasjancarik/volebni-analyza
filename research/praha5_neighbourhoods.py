"""
Which neighbourhood each precinct of a city district of Prague lies in.

The analyses of city districts group precincts by neighbourhood (PRAGUE_5_PARTS
and PRAGUE_1_PARTS in src/web_districts.py). This prints the table those lists
were made from: for every precinct, the part of the municipality that most of
its addresses are in, according to the address register (RÚIAN). In Praha 5,
Barrandov is not a part of the municipality, so the precincts of Hlubočepy
that lie up on the plateau were moved to it by hand afterwards.

Run from the repository root, again after precincts are redrawn:

    uv run python research/praha5_neighbourhoods.py                    # Praha 5
    uv run python research/praha5_neighbourhoods.py --council 500054   # Praha 1
"""

import argparse
import io
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import shapely
from pyproj import Transformer
from shapely.geometry import shape

sys.path.append(str(Path(__file__).parent.parent / "src"))

import web_store as store  # noqa: E402
from address_points import latest_export_day  # noqa: E402

PRAGUE = "554782"
PRAGUE_5 = "500143"
EXPORT_URL = "https://vdp.cuzk.gov.cz/vymenny_format/csv/{day}_OB_{municipality}_ADR.csv.zip"


def addresses(day: str) -> pd.DataFrame:
    """Address points of Prague with the part of the municipality each belongs to."""
    url = EXPORT_URL.format(day=day, municipality=PRAGUE)
    print(f"Stahuji {url}")
    with tempfile.NamedTemporaryFile(suffix=".zip") as archive:
        with requests.get(url, stream=True, timeout=120) as response:
            response.raise_for_status()
            for chunk in response.iter_content(chunk_size=1 << 20):
                archive.write(chunk)
        archive.flush()
        with zipfile.ZipFile(archive.name) as content:
            table = pd.read_csv(io.BytesIO(content.read(content.namelist()[0])), sep=";", encoding="cp1250")
    table = table.dropna(subset=["Souřadnice Y", "Souřadnice X"])
    # The register gives S-JTSK as positive numbers; EPSG:5514 has both negative
    to_wgs = Transformer.from_crs("EPSG:5514", "EPSG:4326", always_xy=True)
    longitude, latitude = to_wgs.transform(-table["Souřadnice Y"].to_numpy(), -table["Souřadnice X"].to_numpy())
    return table.assign(longitude=longitude, latitude=latitude)


def runs(numbers: list) -> str:
    """5001, 5002, 5003, 5007 → "5001–5003, 5007"."""
    parts, start = [], 0
    for index in range(1, len(numbers) + 1):
        if index == len(numbers) or numbers[index] != numbers[index - 1] + 1:
            first, last = numbers[start], numbers[index - 1]
            parts.append(str(first) if first == last else f"{first}–{last}")
            start = index
    return ", ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--council", default=PRAGUE_5, help="Kód městské části, výchozí je Praha 5")
    parser.add_argument("--election", default="kv2026", help="Volby, jejichž okrsky se mají zařadit")
    parser.add_argument("--day", default=latest_export_day(), help="Den exportu registru, RRRRMMDD")
    args = parser.parse_args()

    features = store.boundaries(args.election, args.council)["features"]
    precincts = np.array([feature["properties"]["id"] for feature in features])
    shapes = shapely.make_valid(np.array([shape(feature["geometry"]) for feature in features]))
    table = addresses(args.day)
    address, precinct = shapely.STRtree(shapes).query(
        shapely.points(table["longitude"].to_numpy(), table["latitude"].to_numpy()), predicate="within"
    )
    counts = (
        table.iloc[address]
        .assign(precinct=precincts[precinct])
        .groupby(["precinct", "Název části obce"])
        .size()
        .unstack(fill_value=0)
    )
    part = counts.idxmax(axis=1)
    share = counts.max(axis=1) / counts.sum(axis=1)

    for name in sorted(part.unique()):
        print(f"{name}: {runs(sorted(int(number) for number in part.index[part == name]))}")
    split = share[share < 0.9]
    if len(split):
        print("\nOkrsky, které leží ve více částech (podíl adres v té hlavní):")
        for number, value in split.sort_index().items():
            print(f"  {number}: {part[number]} {value:.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

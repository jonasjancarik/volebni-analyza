"""
Address points of the whole country, for placing the dots of the precinct map
where people live instead of anywhere inside a precinct.

The source is the monthly CSV export of the address register (RÚIAN) published
by ČÚZK. Run once, and again whenever fresher addresses are wanted:

    uv run python src/address_points.py

It writes input/raw/address_points.npy, an array of [longitude, latitude].
"""

import argparse
import io
import sys
import tempfile
import zipfile
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from pyproj import Transformer

EXPORT_URL = "https://vdp.cuzk.gov.cz/vymenny_format/csv/{day}_OB_ADR_csv.zip"
ADDRESS_POINTS_FILE = Path("input/raw/address_points.npy")


def latest_export_day() -> str:
    """The export is published for the last day of the previous month."""
    return (date.today().replace(day=1) - timedelta(days=1)).strftime("%Y%m%d")


def download(day: str, target) -> None:
    url = EXPORT_URL.format(day=day)
    print(f"Stahuji {url}")
    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        for chunk in response.iter_content(chunk_size=1 << 20):
            target.write(chunk)
    target.flush()


def read_points(archive_path: str) -> np.ndarray:
    """All address points of the export as [longitude, latitude]."""
    parts = []
    with zipfile.ZipFile(archive_path) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        for name in names:
            table = pd.read_csv(
                io.BytesIO(archive.read(name)),
                sep=";",
                encoding="cp1250",
                usecols=["Souřadnice Y", "Souřadnice X"],
                decimal=".",
            ).dropna()
            if len(table):
                parts.append(table.to_numpy(dtype="float64"))
    jtsk = np.concatenate(parts)
    # The register gives S-JTSK as positive numbers; EPSG:5514 has both negative
    to_wgs = Transformer.from_crs("EPSG:5514", "EPSG:4326", always_xy=True)
    longitude, latitude = to_wgs.transform(-jtsk[:, 0], -jtsk[:, 1])
    return np.column_stack([longitude, latitude]).astype("float32")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--day", default=latest_export_day(), help="Den exportu, RRRRMMDD")
    args = parser.parse_args()

    with tempfile.NamedTemporaryFile(suffix=".zip") as archive:
        download(args.day, archive)
        points = read_points(archive.name)

    ADDRESS_POINTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    np.save(ADDRESS_POINTS_FILE, points)
    print(f"Uloženo {len(points):,} adres do {ADDRESS_POINTS_FILE}".replace(",", " "))
    return 0


if __name__ == "__main__":
    sys.exit(main())

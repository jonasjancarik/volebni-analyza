"""
Buildings of one municipality from the address register (RÚIAN): where each
stands, how many flats and floors it has, what it is used for, what it is
built of and when it was finished. The analyses use them to tell family
houses from housing estates.

The source is the monthly export of the register in its exchange format (VFR)
published by ČÚZK, one file per municipality. Run once, and again whenever
fresher data are wanted (Prague is a 48 MB download and takes a few minutes):

    uv run python src/buildings.py --municipality 554782

It writes input/raw/buildings_<municipality>.npy, an array with the columns
of places.BUILDING_COLUMNS. Numbers the register does not hold are stored as NaN.
"""

import argparse
import sys
import tempfile
import zipfile

import numpy as np
import requests
from lxml import etree
from pyproj import Transformer

from address_points import latest_export_day
from places import buildings_file

EXPORT_URL = "https://vdp.cuzk.gov.cz/vymenny_format/soucasna/{day}_OB_{municipality}_UZSZ.xml.zip"

BUILDINGS = "{urn:cz:isvs:ruian:schemas:VymennyFormatTypy:v1}StavebniObjekt"
FIELD = "{urn:cz:isvs:ruian:schemas:StavObjIntTypy:v1}"
POSITION = "{http://www.opengis.net/gml/3.2}pos"


def download(day: str, municipality: str, target) -> None:
    url = EXPORT_URL.format(day=day, municipality=municipality)
    print(f"Stahuji {url}")
    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        for chunk in response.iter_content(chunk_size=1 << 20):
            target.write(chunk)
    target.flush()


def read_buildings(archive_path: str) -> np.ndarray:
    """Every building of the export that has a position, as rows of places.BUILDING_COLUMNS."""

    def number(building, name: str) -> float:
        text = building.findtext(FIELD + name)
        return float(text) if text else np.nan

    rows = []
    with zipfile.ZipFile(archive_path) as archive:
        name = next(item for item in archive.namelist() if item.lower().endswith(".xml"))
        with archive.open(name) as source:
            # The file is over a gigabyte of XML; elements are dropped as they are read
            for _, building in etree.iterparse(source, tag=BUILDINGS):
                position = building.findtext(f".//{POSITION}")
                if position:
                    x, y = position.split()
                    finished = building.findtext(FIELD + "Dokonceni")
                    rows.append(
                        (
                            float(x),
                            float(y),
                            number(building, "PocetBytu"),
                            number(building, "PocetPodlazi"),
                            number(building, "ZpusobVyuzitiKod"),
                            number(building, "DruhKonstrukceKod"),
                            float(finished[:4]) if finished else np.nan,
                        )
                    )
                building.clear()
                while building.getprevious() is not None:
                    del building.getparent()[0]

    table = np.array(rows, dtype="float64")
    to_wgs = Transformer.from_crs("EPSG:5514", "EPSG:4326", always_xy=True)
    table[:, 0], table[:, 1] = to_wgs.transform(table[:, 0], table[:, 1])
    return table.astype("float32")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--municipality", default="554782", help="Kód obce, výchozí je Praha")
    parser.add_argument("--day", default=latest_export_day(), help="Den exportu, RRRRMMDD")
    parser.add_argument("--archive", help="Už stažený soubor exportu; jinak se stáhne")
    args = parser.parse_args()

    if args.archive:
        buildings = read_buildings(args.archive)
    else:
        with tempfile.NamedTemporaryFile(suffix=".zip") as archive:
            download(args.day, args.municipality, archive)
            buildings = read_buildings(archive.name)

    target = buildings_file(args.municipality)
    target.parent.mkdir(parents=True, exist_ok=True)
    np.save(target, buildings)
    print(f"Uloženo {len(buildings):,} budov do {target}".replace(",", " "))
    return 0


if __name__ == "__main__":
    sys.exit(main())

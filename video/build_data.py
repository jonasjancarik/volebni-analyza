"""Prepares what the video is drawn from: the figures of the four Prague 2026
analyses as Rust constants (`src/data.rs`) and the maps of precincts as pictures
(`media/map-*.png`).

Reads the analyses the app has stored in `output/kv2026/cache/` and the precinct
boundaries from the running app (`--api`, by default http://localhost:8600).

    uv run python video/build_data.py
"""
import argparse
import json
import math
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
CACHE = ROOT.parent / "output" / "kv2026" / "cache"
COUNCIL = "554782"

# Colours of the lists and of the kinds of buildings, the same as in the app
COLORS = {"stan": "#2a78d6", "spolu": "#eb6834", "prahaSobe": "#1baf7a", "ano": "#eda100", "pirati": "#e87ba4"}
SHORT = {"stan": "STAN", "spolu": "Spolu", "prahaSobe": "Praha Sobě", "ano": "ANO", "pirati": "Piráti"}
KINDS = {
    "older": ("Starší bytové domy", "#a4573c"),
    "panel": ("Panelové domy", "#62788f"),
    "newer": ("Novější bytové domy", "#b377a6"),
    "houses": ("Rodinné domy", "#7d9a35"),
    "mixed": ("Smíšená zástavba", "#b9b6ab"),
}
PINK = ["#f6e9ee", "#f2cbdb", "#eaa3c0", "#e0749f", "#c94f84", "#a2356a", "#6b1d45"]
GREEN = ["#e9f3ee", "#c5e6d6", "#93d3b6", "#55bb91", "#1f9c6f", "#0f7653", "#084c36"]
# Nearest to the centre is the darkest
BLUE = ["#0d366b", "#184f95", "#256abf", "#3987e5", "#6da7ec", "#93bef2", "#b5d3f6", "#d0e3f9"]
BASE = "#dddcd4"
PAPER = "#f6f5f1"

# The maps are drawn three times larger and reduced, so that edges come out smooth
MAP_WIDTH, SUPERSAMPLE = 1500, 3


def analysis(slug):
    return json.loads((CACHE / f"analysis_{slug}.json").read_text())["result"]


def rgb(color):
    return tuple(int(color[i : i + 2], 16) for i in (1, 3, 5))


def ramp(colors, low, high):
    """A colour for a value: `colors` spread evenly from `low` to `high`."""
    stops = [rgb(color) for color in colors]

    def color(value):
        position = min(max((value - low) / (high - low), 0), 1) * (len(stops) - 1)
        base = min(int(position), len(stops) - 2)
        part = position - base
        return tuple(round(a + (b - a) * part) for a, b in zip(stops[base], stops[base + 1]))

    return color


class Maps:
    def __init__(self, features):
        self.features = features
        latitudes = [point[1] for feature in features for point in self._points(feature)]
        longitudes = [point[0] for feature in features for point in self._points(feature)]
        self.west, self.north = min(longitudes), max(latitudes)
        # A degree of longitude is shorter than a degree of latitude this far north
        self.squeeze = math.cos(math.radians((min(latitudes) + max(latitudes)) / 2))
        width = (max(longitudes) - self.west) * self.squeeze
        height = self.north - min(latitudes)
        self.scale = MAP_WIDTH * SUPERSAMPLE / width
        self.size = (MAP_WIDTH * SUPERSAMPLE, math.ceil(height * self.scale))

    @staticmethod
    def _rings(feature):
        geometry = feature["geometry"]
        polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
        return [polygon[0] for polygon in polygons]

    def _points(self, feature):
        return [point for ring in self._rings(feature) for point in ring]

    def draw(self, name, fill):
        """`fill` gives the colour of a precinct by its id, or None to leave it out."""
        image = Image.new("RGBA", self.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        for feature in self.features:
            color = fill(str(feature["properties"]["id"]))
            if color is None:
                continue
            for ring in self._rings(feature):
                points = [((x - self.west) * self.squeeze * self.scale, (self.north - y) * self.scale) for x, y in ring]
                draw.polygon(points, fill=(*color, 255), outline=(*rgb(PAPER), 255), width=SUPERSAMPLE)
        height = round(self.size[1] / SUPERSAMPLE)
        image.resize((MAP_WIDTH, height), Image.LANCZOS).save(ROOT / "media" / f"map-{name}.png", optimize=True)
        return MAP_WIDTH, height


def share(group, key, when="now"):
    return group["voters"][key][when] / group["voted"][when] * 100


def cell(flows, source, target, table="transitions"):
    return flows[table][flows["sources"].index(source)][flows["targets"].index(target)]


def rust(value):
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, float):
        return repr(round(value, 3)) if value != int(value) else f"{value:.1f}"
    if isinstance(value, (list, tuple)):
        return "(" + ", ".join(rust(item) for item in value) + ")" if isinstance(value, tuple) else "[" + ", ".join(rust(item) for item in value) + "]"
    return str(value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8600")
    api = parser.parse_args().api

    first = analysis("praha-2026-pirati-praha-sobe")
    centre = analysis("praha-2026-centrum-sidliste-predmesti")
    order = ["stan", "spolu", "prahaSobe", "ano", "pirati"]
    lists = {item["key"]: item for item in first["lists"]}
    scenarios = {item["key"]: item for item in first["scenarios"]}
    flows, earlier = first["flows"], first["parliamentary"]["flows"]
    earlier_lists = {item["key"]: item for item in first["parliamentary"]["lists"]}

    out = ["//! Figures of the Prague 2026 analyses. Written by `build_data.py`; do not edit by hand.", ""]

    def const(name, kind, value, note=None):
        if note:
            out.append(f"/// {note}")
        out.append(f"pub const {name}: {kind} = {rust(value)};")

    const("BALLOTS", "f32", float(first["summary"]["ballots"]))
    const("PRECINCTS", "f32", float(first["summary"]["precincts"]))
    const("MAJORITY", "usize", first["majority"])
    const(
        "LISTS",
        "[(&str, &str, f32, f32, usize, usize, f32, f32); 5]",
        [
            (SHORT[key], COLORS[key], float(lists[key]["previousShare"]), float(lists[key]["share"]), lists[key]["previousSeats"], lists[key]["seats"], float(lists[key]["previousVoters"]), float(lists[key]["voters"]))
            for key in order
        ],
        "Name, colour, share in 2022 and 2026, seats in 2022 and 2026, voters in 2022 and 2026",
    )
    const("SPD_SEATS_BEFORE", "usize", lists["spd"]["previousSeats"])

    targets = ["pirati", "prahaSobe", "stan", "spolu"]
    stayed = [(SHORT[key], COLORS[key], float(cell(flows, "pirati", key))) for key in targets]
    stayed.append(("Jinam nebo nepřišli", "#a3a199", round(100 - sum(item[2] for item in stayed), 2)))
    const("PIRATI_2022", "[(&str, &str, f32); 5]", stayed, "Where the Pirates' voters of 2022 went: name, colour, percent of them")
    const("FLOW_PRECINCTS", "f32", float(flows["matched"]))

    const("PIRATI_PARLIAMENT_VOTES", "f32", float(earlier_lists["pirati"]["votes"]))
    const("PIRATI_HOME", "(f32, f32, f32)", tuple(float(cell(earlier, "pirati", "nevolici", table)) for table in ("transitions", "transitionsLow", "transitionsHigh")), "Percent of the Pirates' parliamentary voters who did not vote: estimate, low, high")
    const("NEW_PIRATI_NEEDED", "f32", float(scenarios["new-pirati"]["voters"]))
    const("STAN_TO_PRAHA_SOBE_NEEDED", "f32", float(scenarios["stan-to-praha-sobe"]["voters"]))
    const("STAN_TO_PIRATI_NEEDED", "f32", float(scenarios["stan-to-pirati"]["voters"]))
    const("JOINT_SEATS", "(usize, usize)", (scenarios["joint"]["stanSpolu"], scenarios["joint-sen"]["stanSpolu"]), "Seats of STAN and Spolu had the two lists run together: without and with the votes of SEN")
    const("SEN_VOTERS", "f32", float(lists["sen"]["voters"]))

    city = centre["city"]
    const("CITY_PIRATI", "(f32, f32)", (share(city, "pirati", "mid"), share(city, "pirati")), "The Pirates' share in the parliamentary election and now, in the precincts on the map")
    const("CITY_PRAHA_SOBE", "f32", share(city, "prahaSobe"))
    bands = centre["times"]
    const("BANDS", f"[&str; {len(bands)}]", [f"do {b['to']}" if b["from"] == 0 else f"{b['from']}+" if b["to"] is None else f"{b['from']}–{b['to']}" for b in bands], "Minutes to the centre by public transport")
    const("BAND_SHARES", f"[(&str, &str, [f32; {len(bands)}]); 5]", [(SHORT[key], COLORS[key], [share(band, key) for band in bands]) for key in ["prahaSobe", "pirati", "ano", "stan", "spolu"]])
    const("BAND_COLORS", f"[&str; {len(bands)}]", BLUE[: len(bands)])

    kinds = {item["kind"]: item for item in centre["kinds"]}
    const(
        "KINDS",
        "[(&str, &str, f32, [f32; 5]); 4]",
        [
            (KINDS[kind][0], KINDS[kind][1], kinds[kind]["registered"] / city["registered"] * 100, [share(kinds[kind], "prahaSobe"), share(kinds[kind], "pirati"), share(kinds[kind], "ano"), share(kinds[kind], "stan") + share(kinds[kind], "spolu"), kinds[kind]["turnout"]["now"]])
            for kind in ["older", "panel", "newer", "houses"]
        ],
        "Name, colour, percent of voters living there; shares of Praha Sobě, the Pirates, ANO, STAN with Spolu, and turnout",
    )
    const("MIXED", "(&str, &str)", KINDS["mixed"])

    with urllib.request.urlopen(f"{api}/api/elections/kv2026/councils/{COUNCIL}/boundaries") as response:
        features = json.load(response)["features"]
    precincts = {item["id"]: item for item in centre["precincts"]}
    maps = Maps(features)

    def by(key, colors, low, high):
        color = ramp(colors, low, high)
        return lambda id: color(precincts[id][key]) if id in precincts and precincts[id][key] is not None else rgb(BASE)

    size = maps.draw("base", lambda id: rgb(BASE))
    maps.draw("pirati-2025", by("piratiMid", PINK, 0, 30))
    maps.draw("pirati-2026", by("pirati", PINK, 0, 30))
    maps.draw("praha-sobe", by("prahaSobe", GREEN, 5, 35))
    maps.draw("kinds", lambda id: rgb(KINDS[precincts[id]["kind"]][1]) if id in precincts else rgb(BASE))
    for index, band in enumerate(bands):
        inside = lambda id: id in precincts and precincts[id]["minutes"] >= band["from"] and (band["to"] is None or precincts[id]["minutes"] < band["to"])
        maps.draw(f"band-{index}", lambda id: rgb(BLUE[index]) if inside(id) else None)
    const("MAP_SIZE", "(f32, f32)", (float(size[0]), float(size[1])))
    const("PINK", "[&str; 7]", PINK)
    const("GREEN", "[&str; 7]", GREEN)

    (ROOT / "src" / "data.rs").write_text("\n".join(out) + "\n")
    print(f"src/data.rs and {len(bands) + 5} maps of {size[0]}×{size[1]}")


if __name__ == "__main__":
    main()

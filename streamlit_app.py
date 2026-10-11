#!/usr/bin/env python3
"""
Czech Municipalities Election Analysis - Streamlit Dashboard
Interactive visualization dashboard for electoral analysis of any Czech municipality
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots
import folium
from streamlit_folium import st_folium
import json
import requests
import re
from pathlib import Path
import sys
import os
import numpy as np
import geopandas as gpd
from PIL import Image
from shapely.geometry import Point, Polygon
from shapely.affinity import scale
from itertools import product
import subprocess
import logging
import pydeck as pdk
from typing import Dict, List, Optional

# Add src directory to path
sys.path.append(str(Path(__file__).parent / "src"))

from election_config import (
    get_election_config,
    get_election_info,
    list_available_elections,
)
from election_comparison import (
    NON_VOTERS,
    OTHER_LISTS,
    estimate_flows,
    group_columns,
    match_precincts,
    precinct_table,
)

logger = logging.getLogger(__name__)

# Configure Streamlit page
st.set_page_config(
    page_title="Volební analýza",
    page_icon="🗳️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Czech number format in charts: decimal comma, space between thousands
pio.templates["czech_numbers"] = go.layout.Template(layout=dict(separators=", "))
pio.templates.default = "plotly+czech_numbers"


def fmt_int(value) -> str:
    """1234567 -> '1 234 567' (non-breaking spaces)"""
    if value is None or pd.isna(value):
        return "–"
    return f"{int(round(float(value))):,}".replace(",", "\u00a0")


def fmt_signed_int(value) -> str:
    """Change of a count for st.metric, e.g. '+1 234'"""
    return f"{int(round(float(value))):+,}".replace(",", "\u00a0")


def fmt_pct(value, decimals: int = 1) -> str:
    """45.96 -> '46,0 %'"""
    return f"{float(value):.{decimals}f}".replace(".", ",") + "\u00a0%"


def czech_table(df: pd.DataFrame, decimals: Optional[Dict[str, int]] = None, signed=()):
    """Show numbers in a table the Czech way; sorting still uses the raw values.

    Whole-number columns get a space between thousands, columns listed in
    `decimals` a decimal comma, and columns in `signed` an explicit plus sign.
    """
    decimals = decimals or {}

    def number_format(places: int, show_sign: bool):
        def format_value(value):
            if pd.isna(value):
                return "–"
            text = f"{value:+,.{places}f}" if show_sign else f"{value:,.{places}f}"
            return text.replace(",", "\u00a0").replace(".", ",")

        return format_value

    formats = {}
    for column in df.columns:
        if column in decimals:
            formats[column] = number_format(decimals[column], column in signed)
        elif pd.api.types.is_integer_dtype(df[column]):
            formats[column] = number_format(0, column in signed)
    return df.style.format(formats)


def fmt_pp(value, signed: bool = True) -> str:
    """Difference of two percentages in percentage points, e.g. '+2,1 p. b.'"""
    number = f"{float(value):+.1f}" if signed else f"{float(value):.1f}"
    return number.replace(".", ",") + "\u00a0p.\u00a0b."

# UI labels (internal keys remain English for logic)
VIZ_LABELS = {
    "Turnout": "Účast",
    "Estimated Voters": "Odhad počtu voličů",
    "Valid Votes": "Platné hlasy",
    "Party Results": "Výsledek strany",
    "Valid Votes (dots)": "Platné hlasy (tečky)",
}

MAP_TYPE_LABELS = {
    "Geographic Map": "Geografická mapa",
    "Pydeck (fast)": "Rychlá mapa (Pydeck)",
    "Cartogram": "Kartogram",
    "Dot Density": "Tečková mapa (tečka = počet hlasů)",
}


# Above this number of precincts the map shows values on hover only
MAX_LABELLED_PRECINCTS = 150


def viz_label(viz_type: str) -> str:
    return VIZ_LABELS.get(viz_type, viz_type)


def map_type_label(map_type: str) -> str:
    return MAP_TYPE_LABELS.get(map_type, map_type)


def run_data_collection(election_id="kv2022"):
    """Run the data collection script if data is missing"""
    st.info(f"🔄 Spouštím sběr dat pro {election_id}...")

    # Create a progress bar and output display
    progress_bar = st.progress(0)
    status_text = st.empty()
    output_container = st.expander("📋 Živý výstup", expanded=True)
    output_text = output_container.empty()

    try:
        status_text.text("🚀 Startuji sběr dat...")
        progress_bar.progress(5)

        # Run the data collection script with election parameter
        # Use STDOUT redirection but don't capture stderr (let it show in terminal)
        process = subprocess.Popen(
            [
                "uv",
                "run",
                "python",
                "run_all_municipalities.py",
                "--election",
                election_id,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Merge stderr into stdout
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        # Read output in real-time
        output_lines = []
        progress = 5

        for line in iter(process.stdout.readline, ""):
            if not line:
                break

            output_lines.append(line.rstrip())

            # Keep only last 50 lines for display
            if len(output_lines) > 50:
                output_lines.pop(0)

            # Update output display
            output_text.code("\n".join(output_lines[-30:]), language="log")

            # Update progress based on keywords in output
            if "STEP 1" in line or "Processing" in line:
                progress = max(progress, 20)
            elif "STEP 2" in line or "Collecting" in line or "Downloading" in line:
                progress = max(progress, 40)
            elif "Downloaded" in line or "Loaded" in line:
                progress = min(progress + 2, 80)
            elif "Generating" in line:
                progress = max(progress, 85)
            elif "Saved" in line or "complete" in line.lower():
                progress = min(progress + 5, 95)

            progress_bar.progress(progress)

            # Update status based on current activity
            if "ERROR" in line:
                status_text.text(f"⚠️ {line[:80]}")
            elif "STEP" in line:
                status_text.text(f"📊 {line.split('INFO - ')[-1][:80]}")

        # Wait for process to complete
        process.stdout.close()
        return_code = process.wait()

        # Check if successful
        if return_code == 0:
            progress_bar.progress(100)
            status_text.text("✅ Sběr dat úspěšně dokončen!")
            st.success("✅ Sběr dat dokončen! Stránka se automaticky obnoví.")
            st.balloons()
            import time

            time.sleep(2)
            return True
        else:
            st.error(f"❌ Sběr dat selhal (exit code: {return_code})")
            st.warning(
                "Podrobnosti hledejte ve výpisu výše, nebo v souboru: all_municipalities_analysis.log"
            )
            return False

    except Exception as e:
        st.error(f"❌ Chyba při spuštění sběru dat: {e}")
        st.exception(e)
        return False


@st.cache_resource(show_spinner="Načítám výsledky voleb…")
def _read_results_files(index_file: str, comprehensive_file: str, data_version: float):
    """Parse the result files once per data version; they are tens of MB."""
    with open(index_file, "r", encoding="utf-8") as f:
        index_data = json.load(f)

    with open(comprehensive_file, "r", encoding="utf-8") as f:
        comprehensive_data = json.load(f)

    return index_data, comprehensive_data


def load_all_municipality_data(election_id="kv2022"):
    """Load municipality/district index and comprehensive data for a specific election"""
    try:
        # Get election configuration
        election_config = get_election_config(election_id)

        # Check election type and load appropriate files
        if election_config.election_type == "parliamentary":
            # Parliamentary elections use different file names
            index_file = election_config.results_dir / "district_index.json"
            comprehensive_file = (
                election_config.results_dir / "parliamentary_election_results.json"
            )
        else:
            # Municipal elections
            index_file = election_config.results_dir / "municipality_index.json"
            comprehensive_file = (
                election_config.results_dir / "all_municipalities_comprehensive.json"
            )

        if not index_file.exists() or not comprehensive_file.exists():
            return None, None

        return _read_results_files(
            str(index_file), str(comprehensive_file), comprehensive_file.stat().st_mtime
        )

    except Exception as e:
        logger.error(f"Error loading data for {election_id}: {e}")
        return None, None


def ensure_data_exists(election_id="kv2022"):
    """Ensure data exists, run collection if missing"""
    index_data, comprehensive_data = load_all_municipality_data(election_id)

    if index_data and comprehensive_data:
        return index_data, comprehensive_data

    # Check if user wants to run data collection
    election_config = get_election_config(election_id)
    st.warning(f"⚠️ Chybí data pro {election_config.election_name}!")

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "🚀 Spustit sběr dat", type="primary", key=f"collect_{election_id}"
        ):
            if run_data_collection(election_id):
                st.rerun()  # Refresh the app after data collection

    with col2:
        if election_config.election_type == "parliamentary":
            st.info(
                "Stáhne a zpracuje data parlamentních voleb pro 14 volebních obvodů. Může to chvíli trvat."
            )
        else:
            st.info(
                "Stáhne a zpracuje data pro 6 377+ českých obcí. Může to pár minut trvat."
            )

    return None, None


def get_results_data_version(election_id="kv2022"):
    """Return mtime for results files to bust Streamlit cache when data changes."""
    election_config = get_election_config(election_id)

    if election_config.election_type == "parliamentary":
        results_file = (
            election_config.results_dir / "parliamentary_election_results.json"
        )
    else:
        results_file = (
            election_config.results_dir / "all_municipalities_comprehensive.json"
        )

    try:
        return results_file.stat().st_mtime
    except FileNotFoundError:
        return 0


def create_municipality_selector(
    municipality_index,
    election_id: str,
    is_parliamentary: bool,
    default_code: Optional[str] = None,
):
    """Sidebar select box for the municipality (or region); returns its code or None"""
    names = {str(code): info.get("name", str(code)) for code, info in municipality_index.items()}

    if is_parliamentary:
        label = "Kraj"
        codes = sorted(names, key=lambda code: int(code) if code.isdigit() else 0)
        format_option = lambda code: names[code]
    else:
        label = "Obec nebo městská část"
        codes = sorted(names, key=lambda code: (names[code].lower(), code))
        # Many municipalities share a name, the code tells them apart
        format_option = lambda code: f"{names[code]} ({code})"

    # One widget per election: codes of regions and municipalities differ
    widget_key = f"municipality_select_{election_id}"
    if widget_key not in st.session_state and default_code in names:
        st.session_state[widget_key] = str(default_code)

    return st.sidebar.selectbox(
        label,
        codes,
        format_func=format_option,
        index=None,
        placeholder="Začněte psát název…",
        key=widget_key,
    )


def get_data_by_code(code: str, comprehensive_data) -> Optional[Dict]:
    """
    Get data for a specific municipality or district code.
    Handles both parliamentary (electoral_districts) and municipal (municipalities) structures.
    """
    if not comprehensive_data:
        return None

    # Check which structure we have
    if "electoral_districts" in comprehensive_data:
        # Parliamentary elections - try both string and int versions of the code
        districts = comprehensive_data["electoral_districts"]
        # Try as-is first
        result = districts.get(code)
        if result:
            return result
        # Try converting to string
        result = districts.get(str(code))
        if result:
            return result
        # Try converting to int
        if code.isdigit():
            result = districts.get(int(code))
            if result:
                return result
        return None
    elif "municipalities" in comprehensive_data:
        # Municipal elections
        return comprehensive_data["municipalities"].get(code)

    return None


def get_municipality_data(municipality_code: str, comprehensive_data) -> Optional[Dict]:
    """Get complete data for a specific municipality or district"""
    return get_data_by_code(municipality_code, comprehensive_data)


def get_url_params():
    """Get URL parameters using the appropriate Streamlit method"""
    try:
        # Try newer st.query_params first (Streamlit 1.30+)
        if hasattr(st, "query_params"):
            return dict(st.query_params)
        else:
            # Fallback to experimental method
            return st.experimental_get_query_params()
    except Exception:
        return {}


def update_url_params(**params):
    """Update URL parameters using the appropriate Streamlit method"""
    try:
        # Try newer st.query_params first (Streamlit 1.30+)
        if hasattr(st, "query_params"):
            for key, value in params.items():
                if value is not None:
                    st.query_params[key] = str(value)
                elif key in st.query_params:
                    del st.query_params[key]
        else:
            # Fallback to experimental method
            current_params = st.experimental_get_query_params()
            for key, value in params.items():
                if value is not None:
                    current_params[key] = [str(value)]
                elif key in current_params:
                    del current_params[key]
            st.experimental_set_query_params(**current_params)
    except Exception:
        pass  # Silently fail if URL params not supported


def get_param_value(params, key, default=None):
    """Get a parameter value from URL params dict, handling both list and string formats"""
    if key not in params:
        return default

    value = params[key]
    if isinstance(value, list):
        return value[0] if value else default
    return value


def get_seat_count(electoral_data):
    """Get the number of seats for the current municipality from electoral data"""
    if not electoral_data or "summary_statistics" not in electoral_data:
        return 41  # Default fallback only when no data is available

    summary_stats = electoral_data["summary_statistics"]

    # First try to get num_seats directly
    if "num_seats" in summary_stats and summary_stats["num_seats"]:
        try:
            return int(summary_stats["num_seats"])
        except (ValueError, TypeError):
            pass

    # Fallback to electoral_districts if reasonable seat count
    if "electoral_districts" in summary_stats:
        try:
            districts_count = int(summary_stats.get("electoral_districts", 41))
            if districts_count < 100:  # Reasonable seat count
                return districts_count
        except (ValueError, TypeError):
            pass

    # Final fallback
    return 41


@st.cache_data
def load_geojson_data(election_id: str = "kv2022"):
    """Download and cache GeoJSON data for electoral districts to local disk"""
    # Get election configuration to determine which geojson to load
    election_config = get_election_config(election_id)

    # Determine which geojson file to use based on election type
    if election_config.election_type == "parliamentary":
        # Use 2025 polling station geojson for parliamentary elections
        raw_cache_file = Path("input/raw/electoral_districts_boundaries_2025.geojson")
        cache_file = Path("input/raw/electoral_districts_boundaries_2025_wgs84.geojson")
        # Note: This file should be pre-downloaded (252.6 MB, 14,711 stations)
        # It can be downloaded from: https://geodata.csu.gov.cz/as/data/distribuce/Hosted/Volebni_okrsky_2025_gdb/FeatureServer/0/geojson.zip
        url = None  # Too large to download via HTTP, should be pre-existing
    else:
        # Newer boundaries when the election has them prepared, 2022 otherwise
        cache_file = Path("input/raw/electoral_districts_boundaries.geojson")
        if election_config.boundaries_file:
            newer_file = Path("input/raw") / election_config.boundaries_file
            if newer_file.exists():
                cache_file = newer_file
        url = "https://www.volby.cz/opendata/kv2022/geo/vol_okrsky_2022g100.geojson"

    cache_file.parent.mkdir(parents=True, exist_ok=True)

    # Check if file already exists
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                geojson_data = json.load(f)

            # Validate the cached data
            if (
                isinstance(geojson_data, dict)
                and geojson_data.get("type") == "FeatureCollection"
            ):
                features = geojson_data.get("features", [])
                if features:
                    return geojson_data

            st.warning("⚠️ Cache soubor je poškozený, stahuji znovu...")

        except Exception as e:
            st.warning(f"⚠️ Chyba při čtení cache: {e}. Stahuji znovu...")

    # For parliamentary elections, expect the preprocessed WGS84 file.
    if election_config.election_type == "parliamentary":
        if raw_cache_file.exists():
            st.error(
                f"❌ Předzpracovaný GeoJSON nenalezen: {cache_file}\n\n"
                "Spusťte předzpracování pro převod 2025 GeoJSON do WGS84:\n"
                "  uv run python run_all_municipalities.py --election ps2025 --no-download"
            )
        else:
            st.error(
                f"❌ GeoJSON soubor nenalezen: {raw_cache_file}\n\n"
                "GeoJSON okrsků pro 2025 (252.6 MB) je nutné stáhnout ručně.\n"
                "Stáhněte jej z GIS portálu ČSÚ a uložte do input/raw/."
            )
        return None

    # Download the file (municipal elections only)
    try:
        st.info("🌐 Stahuji hranice okrsků (8MB) — může to chvíli trvat...")
        response = requests.get(url, timeout=120)  # Increased timeout for large file
        response.raise_for_status()

        st.info("📊 Zpracovávám GeoJSON...")
        geojson_data = response.json()

        # Validate the data structure
        if not isinstance(geojson_data, dict):
            raise ValueError("Neplatný formát GeoJSON: není slovník")

        if geojson_data.get("type") != "FeatureCollection":
            raise ValueError(f"Neplatný typ GeoJSON: {geojson_data.get('type')}")

        features = geojson_data.get("features", [])
        if not features:
            raise ValueError("V GeoJSON nejsou žádné prvky")

        # Save to cache
        st.info("💾 Ukládám do lokální cache...")
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(geojson_data, f, ensure_ascii=False)

        st.success(f"✅ Staženo a uloženo {fmt_int(len(features))} okrsků")
        return geojson_data

    except requests.exceptions.Timeout:
        st.error("⏱️ Timeout při stahování. Zkuste to znovu nebo ověřte připojení.")
        return None
    except requests.exceptions.ConnectionError:
        st.error("🔌 Chyba připojení. Ověřte internetové připojení.")
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"🌐 HTTP chyba při stahování GeoJSON: {e}")
        return None
    except ValueError as e:
        st.error(f"📊 Chyba formátu dat: {e}")
        return None
    except Exception as e:
        st.error(f"❌ Neočekávaná chyba při načítání GeoJSON: {e}")
        st.error("💡 Zkuste obnovit stránku, nebo kontaktujte podporu.")
    return None


@st.cache_data
def load_geojson_kod_mco_set(election_id: str):
    """Load cached kod_mco set for parliamentary geojson to speed filtering."""
    election_config = get_election_config(election_id)
    if election_config.election_type != "parliamentary":
        return set()

    kod_mco_file = Path("input/ps2025/processed/geojson_kod_mco_set.json")
    if not kod_mco_file.exists():
        return set()

    try:
        with open(kod_mco_file, "r", encoding="utf-8") as f:
            values = json.load(f)
        return {str(v) for v in values}
    except Exception as e:
        st.warning(f"⚠️ Chyba při načítání kod_mco indexu: {e}")
        return set()


@st.cache_data
def load_pre_split_geojson(election_id: str, municipality_code: str):
    """Load pre-split GeoJSON for a municipality code when available."""
    election_config = get_election_config(election_id)
    if election_config.election_type != "parliamentary":
        return None

    split_file = Path(
        f"input/{election_id}/processed/geojson_by_municipality/{municipality_code}.geojson"
    )
    if not split_file.exists():
        return None

    try:
        with open(split_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("type") != "FeatureCollection":
            return None
        return data
    except Exception as e:
        st.warning(f"⚠️ Chyba při načítání předděleného GeoJSON: {e}")
        return None


@st.cache_data
def load_geojson_subset(
    election_id: str,
    target_mco_codes: List[str],
    target_obec_codes: List[str],
    use_simplified: bool = True,
    use_ram_cache: bool = False,
):
    """Load a filtered parliamentary GeoJSON subset using GeoPackage when available."""
    election_config = get_election_config(election_id)
    if election_config.election_type != "parliamentary":
        return None

    gpkg_file = Path("input/raw/electoral_districts_boundaries_2025_wgs84.gpkg")
    if gpkg_file.exists():
        try:
            layer = "okrsky_simplified" if use_simplified else "okrsky"
            if use_ram_cache:
                gdf = load_parliamentary_gdf(election_id, use_simplified)
                if gdf is not None and not gdf.empty:
                    if target_mco_codes:
                        subset = gdf[gdf["kod_mco"].astype(str).isin(target_mco_codes)]
                    else:
                        subset = gdf[
                            gdf["kod_obec"].astype(str).isin(target_obec_codes)
                        ]
                    if subset.empty:
                        return None
                    return json.loads(subset.to_json())

            if target_mco_codes:
                code_list = ",".join(f"'{code}'" for code in target_mco_codes)
                where = f"kod_mco IN ({code_list})"
            else:
                code_list = ",".join(f"'{code}'" for code in target_obec_codes)
                where = f"kod_obec IN ({code_list})"

            gdf = gpd.read_file(gpkg_file, layer=layer, where=where)
            if gdf.empty:
                return None
            return json.loads(gdf.to_json())
        except Exception as e:
            st.warning(f"⚠️ Načtení GeoPackage výřezu selhalo, pokračuji jinak: {e}")

    geojson_data = load_geojson_data(election_id)
    if not geojson_data or "features" not in geojson_data:
        return None

    filtered = []
    for feature in geojson_data["features"]:
        props = feature.get("properties", {})
        kod_mco = props.get("kod_mco")
        kod_obec = props.get("kod_obec")
        if kod_mco and str(kod_mco) in target_mco_codes:
            filtered.append(feature)
        elif kod_obec and str(kod_obec) in target_obec_codes:
            filtered.append(feature)

    if not filtered:
        return None
    return {"type": "FeatureCollection", "features": filtered}


@st.cache_resource
def load_parliamentary_gdf(election_id: str, use_simplified: bool = True):
    """Load full parliamentary GeoDataFrame into RAM (large)."""
    election_config = get_election_config(election_id)
    if election_config.election_type != "parliamentary":
        return None

    gpkg_file = Path("input/raw/electoral_districts_boundaries_2025_wgs84.gpkg")
    if not gpkg_file.exists():
        return None

    layer = "okrsky_simplified" if use_simplified else "okrsky"
    try:
        return gpd.read_file(gpkg_file, layer=layer)
    except Exception as e:
        st.warning(f"⚠️ Nepodařilo se načíst GeoPackage do RAM: {e}")
        return None


@st.cache_data
def load_obec_mapping(election_id: str):
    """Load OBEC code mapping for parliamentary elections

    Maps PS2025 OBEC codes to GeoJSON kod_obec/naz_mco for district matching.
    Returns empty dict for non-parliamentary elections.
    """
    election_config = get_election_config(election_id)

    # Only load mapping for parliamentary elections
    if election_config.election_type != "parliamentary":
        return {}

    # Load the mapping file
    mapping_file = Path(f"input/{election_id}/processed/obec_to_geojson_mapping.json")

    if not mapping_file.exists():
        st.warning(
            f"⚠️ Soubor mapování OBEC nebyl nalezen: {mapping_file}\n\n"
            "Soubor je potřeba pro párování kódů PS2025 na GeoJSON prvky."
        )
        return {}

    try:
        with open(mapping_file, "r", encoding="utf-8") as f:
            mapping = json.load(f)
        return mapping
    except Exception as e:
        st.error(f"❌ Chyba při načítání mapování OBEC: {e}")
        return {}


@st.cache_data
def load_municipality_data(
    zastupitelstvo_code: str,
    election_id: str = "kv2022",
    data_version: float = 0,
):
    """Load processed election data for a specific zastupitelstvo/district"""
    if not zastupitelstvo_code:
        return {}

    # Load from our all municipalities data using zastupitelstvo_code and election_id
    _, comprehensive_data = load_all_municipality_data(election_id)
    municipality_data = get_municipality_data(zastupitelstvo_code, comprehensive_data)

    if not municipality_data:
        # Check if this is parliamentary or municipal
        election_config = get_election_config(election_id)
        entity_type = (
            "volební obvod"
            if election_config.election_type == "parliamentary"
            else "zastupitelstvo"
        )
        st.error(f"Nebyla nalezena data pro {entity_type} {zastupitelstvo_code}")
        return {}

    # Convert to format expected by visualization functions
    converted_data = {}

    # Check if this is parliamentary or municipal data
    election_config = get_election_config(election_id)
    is_parliamentary = election_config.election_type == "parliamentary"

    # Convert party results
    party_results = municipality_data.get("party_results", [])
    if party_results:
        if is_parliamentary:
            # Parliamentary data conversion
            party_df = pd.DataFrame(party_results)
            # Map parliamentary fields to expected fields
            party_df = party_df.rename(columns={"party_code": "list_number"})
            if (
                "votes_absolute" not in party_df.columns
                and "preferential_votes" in party_df.columns
            ):
                party_df = party_df.rename(
                    columns={"preferential_votes": "votes_absolute"}
                )
            if "votes_percentage" not in party_df.columns:
                total_votes = (
                    party_df["votes_absolute"].sum()
                    if "votes_absolute" in party_df.columns
                    else 0
                )
                if total_votes > 0:
                    party_df["votes_percentage"] = (
                        party_df["votes_absolute"] / total_votes * 100
                    ).round(2)
                else:
                    party_df["votes_percentage"] = 0
            converted_data["party_results"] = party_df
        else:
            # Municipal data conversion (original logic)
            party_df = pd.DataFrame(party_results)
            party_df = party_df.rename(
                columns={
                    "votes_absolute": "votes_absolute",  # Already correct
                    "votes_percentage": "votes_percentage",  # Already correct
                    "party_name": "party_name",  # Already correct
                    "list_number": "list_number",  # Already correct
                }
            )
            converted_data["party_results"] = party_df

    # Convert district data (only for municipal elections)
    district_data = municipality_data.get("district_data", [])
    if not is_parliamentary and district_data:
        districts = []
        for district in district_data:
            district_info = {
                "district_code": district.get("district_code", ""),
                "registered_voters": district.get("turnout", {}).get(
                    "registered_voters", 0
                ),
                "returned_ballots": district.get("turnout", {}).get(
                    "returned_ballots", 0
                ),
                "valid_votes": district.get("turnout", {}).get("valid_votes", 0),
                "turnout_percentage": district.get("turnout", {}).get(
                    "turnout_percentage", 0
                ),
            }
            districts.append(district_info)

        if districts:
            converted_data["district_data"] = pd.DataFrame(districts)

    # Convert summary statistics
    stats = municipality_data.get("summary_statistics", {})
    if is_parliamentary:
        # For parliamentary, map available stats
        summary_stats = {
            "electoral_districts": 0,  # Not applicable for individual district view
            "registered_voters": 0,  # Would need to aggregate from polling stations
            "turnout_percentage": 0,  # Would need to calculate
            "valid_votes": 0,  # Would need to aggregate
            "parties_participating": stats.get("parties_participating", 0),
            "parties_with_mandates": len(
                [p for p in party_results if p.get("mandates", 0) > 0]
            )
            if party_results
            else 0,
        }
        converted_data["summary_statistics"] = summary_stats
    else:
        converted_data["summary_statistics"] = stats

    # Create district party results
    district_party_results = []
    if not is_parliamentary:
        for district in district_data:
            district_code = district.get("district_code", "")
            party_votes = district.get("party_votes", [])
            total_votes = sum(pv.get("votes", 0) for pv in party_votes)

            for party_vote in party_votes:
                party_list_num = party_vote.get("party_list_number")
                votes = party_vote.get("votes", 0)

                # Find party name from party results
                party_name = f"Party List {party_list_num}"
                for party in party_results:
                    if str(party.get("list_number")) == str(party_list_num):
                        party_name = party.get("party_name", party_name)
                        break

                district_party_results.append(
                    {
                        "district_id": f"{district_code}-1",
                        "district_code": district_code,
                        "party_name": party_name,
                        "list_number": party_list_num,
                        "votes": votes,
                        "total_district_votes": total_votes,
                        "percentage": (votes / total_votes * 100)
                        if total_votes > 0
                        else 0,
                    }
                )

    # Add candidates data for parliamentary elections
    if is_parliamentary and "candidates" in municipality_data:
        candidates = municipality_data["candidates"]

        # Enrich candidates with party names from party_results
        if party_results:
            # Create a mapping of party_code to party_name
            party_name_map = {
                p.get("party_code"): p.get("party_name", "Neznámá")
                for p in party_results
            }

            # Add party names to candidates
            for candidate in candidates:
                party_code = candidate.get("party_code")
                candidate["party_name"] = party_name_map.get(
                    party_code, f"Party {party_code}"
                )

        converted_data["candidates"] = candidates

    # Add polling stations for parliamentary elections
    if is_parliamentary and comprehensive_data:
        # Get all polling stations from raw_data
        raw_data = comprehensive_data.get("raw_data", {})
        all_polling_stations = raw_data.get("polling_stations", [])

        # Filter polling stations for this electoral district
        # district_code in polling stations starts with the district number
        # e.g., "1100" for district 1, "2101" for district 2, etc.
        district_polling_stations = [
            station
            for station in all_polling_stations
            if station.get("district_code", "").startswith(str(zastupitelstvo_code))
        ]

        if district_polling_stations:
            converted_data["polling_stations"] = district_polling_stations

            # Convert polling stations to district_data format for map visualization
            # Use station_number as district_code (e.g., "1001", "1002", etc.)
            district_data_list = []
            for station in district_polling_stations:
                district_data_list.append(
                    {
                        "district_code": station.get("station_number", ""),
                        "registered_voters": station.get("registered_voters", 0),
                        "returned_ballots": station.get("returned_ballots", 0),
                        "valid_votes": station.get("valid_votes", 0),
                        "turnout_percentage": station.get("turnout_percentage", 0),
                    }
                )

            converted_data["district_data"] = pd.DataFrame(district_data_list)

            if "summary_statistics" in converted_data:
                registered = sum(
                    station.get("registered_voters", 0)
                    for station in district_polling_stations
                )
                returned = sum(
                    station.get("returned_ballots", 0)
                    for station in district_polling_stations
                )
                valid_votes = sum(
                    station.get("valid_votes", 0)
                    for station in district_polling_stations
                )
                turnout_percentage = (
                    (returned / registered) * 100 if registered > 0 else 0
                )
                converted_data["summary_statistics"].update(
                    {
                        "registered_voters": registered,
                        "turnout_percentage": round(turnout_percentage, 2),
                        "valid_votes": valid_votes,
                    }
                )

            party_name_map = {
                p.get("party_code"): p.get("party_name", "Neznámá")
                for p in party_results
            }

            for station in district_polling_stations:
                district_code = station.get("station_number", "")
                party_votes = station.get("party_votes", [])
                total_votes = sum(pv.get("votes", 0) for pv in party_votes)

                for party_vote in party_votes:
                    party_code = party_vote.get("party_list_number") or party_vote.get(
                        "party_code"
                    )
                    if party_code is None:
                        continue
                    votes = party_vote.get("votes", 0)
                    party_name = party_name_map.get(party_code, f"Strana {party_code}")
                    district_party_results.append(
                        {
                            "district_id": f"{district_code}-1",
                            "district_code": district_code,
                            "party_name": party_name,
                            "list_number": party_code,
                            "votes": votes,
                            "total_district_votes": total_votes,
                            "percentage": (votes / total_votes * 100)
                            if total_votes > 0
                            else 0,
                        }
                    )

    if district_party_results:
        converted_data["district_party_results"] = pd.DataFrame(district_party_results)

    return converted_data


def get_district_code_from_geojson(properties):
    """Extract district code from GeoJSON properties (handles both 2022 and 2025 formats)

    2022 GeoJSON uses uppercase 'CISLO'
    2025 GeoJSON uses lowercase 'cislo'
    """
    # Try both formats
    code = properties.get("cislo") or properties.get("CISLO")
    return str(code) if code is not None else ""


def create_map_with_tiles(location, zoom_start, base_map_style):
    """Create a Folium map with proper tile handling and attribution"""
    if base_map_style == "OpenStreetMap":
        return folium.Map(
            location=location, zoom_start=zoom_start, tiles="OpenStreetMap"
        )
    elif base_map_style == "CartoDB Positron":
        return folium.Map(
            location=location, zoom_start=zoom_start, tiles="CartoDB positron"
        )
    elif base_map_style == "CartoDB Dark Matter":
        return folium.Map(
            location=location, zoom_start=zoom_start, tiles="CartoDB dark_matter"
        )
    elif base_map_style == "CartoDB Voyager":
        return folium.Map(
            location=location, zoom_start=zoom_start, tiles="CartoDB voyager"
        )
    else:
        # Default fallback
        return folium.Map(
            location=location, zoom_start=zoom_start, tiles="OpenStreetMap"
        )


def create_folium_map(
    geojson_data,
    electoral_data=None,
    viz_type="Turnout",
    selected_party=None,
    base_map_style="OpenStreetMap",
):
    """Create an interactive Folium map with electoral districts and optional data overlay"""

    # Calculate map center and bounds from geojson data
    map_center = [50.0755, 14.4378]  # Default to Prague center
    zoom_start = 11  # Fixed zoom level for tabs

    if geojson_data and "features" in geojson_data:
        # Calculate bounding box from districts
        lats = []
        lons = []

        for feature in geojson_data["features"]:
            if feature.get("geometry") and feature["geometry"].get("coordinates"):
                coords = feature["geometry"]["coordinates"]

                # Handle different geometry types
                if feature["geometry"]["type"] == "Polygon":
                    for ring in coords:
                        for coord in ring:
                            lons.append(coord[0])
                            lats.append(coord[1])
                elif feature["geometry"]["type"] == "MultiPolygon":
                    for polygon in coords:
                        for ring in polygon:
                            for coord in ring:
                                lons.append(coord[0])
                                lats.append(coord[1])

        if lats and lons:
            # Calculate center
            center_lat = (min(lats) + max(lats)) / 2
            center_lon = (min(lons) + max(lons)) / 2
            map_center = [center_lat, center_lon]

            # Calculate appropriate zoom based on geographic extent
            lat_range = max(lats) - min(lats)
            lon_range = max(lons) - min(lons)
            max_range = max(lat_range, lon_range)

            # Set zoom based on geographic extent
            if max_range < 0.01:  # Very small area
                zoom_start = 16
            elif max_range < 0.05:  # Small area
                zoom_start = 14
            elif max_range < 0.1:  # Medium area
                zoom_start = 14
            elif max_range < 0.2:  # Large area
                zoom_start = 13
            else:  # Very large area
                zoom_start = 12

    # Create map with initial center and proper tile handling
    m = create_map_with_tiles(map_center, zoom_start, base_map_style)

    # A label on every precinct covers the whole map in a big city
    show_labels = (
        len((geojson_data or {}).get("features", [])) <= MAX_LABELLED_PRECINCTS
    )

    # Calculate bounds for auto-fitting after we add all features - but don't use fit_bounds in tabs
    bounds = None
    if geojson_data and "features" in geojson_data and lats and lons:
        # Calculate bounds with a small padding
        lat_min, lat_max = min(lats), max(lats)
        lon_min, lon_max = min(lons), max(lons)

        # Add 5% padding to ensure districts aren't at the very edge
        lat_padding = (lat_max - lat_min) * 0.05
        lon_padding = (lon_max - lon_min) * 0.05

        bounds = [
            [lat_min - lat_padding, lon_min - lon_padding],  # Southwest corner
            [lat_max + lat_padding, lon_max + lon_padding],  # Northeast corner
        ]

    if geojson_data and "features" in geojson_data:
        # Prepare electoral data lookup based on visualization type
        viz_data = {}
        district_data = None
        party_data = None

        if electoral_data and "district_data" in electoral_data:
            district_data = electoral_data["district_data"]

        if electoral_data and "district_party_results" in electoral_data:
            party_data = electoral_data["district_party_results"]

        # Build data lookup based on visualization type
        if (
            isinstance(district_data, pd.DataFrame)
            and "district_code" in district_data.columns
        ):
            for _, row in district_data.iterrows():
                district_code = str(row.get("district_code", ""))

                if viz_type == "Turnout" and "turnout_percentage" in row:
                    turnout_pct = row.get("turnout_percentage", 0)
                    if pd.notna(turnout_pct):
                        viz_data[district_code] = float(turnout_pct)

                elif viz_type == "Estimated Voters" and "registered_voters" in row:
                    voters = row.get("registered_voters", 0)
                    if pd.notna(voters):
                        viz_data[district_code] = int(voters)

                elif (
                    viz_type == "Valid Votes" or viz_type == "Valid Votes (dots)"
                ) and "valid_votes" in row:
                    valid_votes = row.get("valid_votes", 0)
                    if pd.notna(valid_votes):
                        viz_data[district_code] = int(valid_votes)

        # For party results, use party data
        if (
            viz_type == "Party Results"
            and selected_party
            and isinstance(party_data, pd.DataFrame)
        ):
            # Group party data by district_code and calculate percentages
            party_subset = party_data[party_data["party_name"] == selected_party].copy()
            if not party_subset.empty:
                # Extract district_code from district_id
                party_subset["district_code"] = (
                    party_subset["district_id"].str.split("-").str[0]
                )

                # Group by district_code and calculate total votes and percentage
                for district_code, group in party_subset.groupby("district_code"):
                    total_votes = group["votes"].sum()
                    total_district_votes = group["total_district_votes"].sum()
                    if total_district_votes > 0:
                        percentage = (total_votes / total_district_votes) * 100
                        viz_data[str(district_code)] = percentage

        # Define color scales based on visualization type
        def get_color_for_value(value, viz_type):
            """Get color based on value and visualization type"""
            if viz_type == "Turnout":
                # Turnout percentage color scale
                if value >= 60:
                    return "#2E8B57"  # Dark green
                elif value >= 50:
                    return "#90EE90"  # Light green
                elif value >= 40:
                    return "#FFD700"  # Gold
                elif value >= 30:
                    return "#FFA500"  # Orange
                else:
                    return "#FF6347"  # Red

            elif viz_type == "Estimated Voters":
                # Voters count color scale (adjust ranges as needed)
                if value >= 800:
                    return "#2E8B57"  # Dark green (high)
                elif value >= 600:
                    return "#90EE90"  # Light green
                elif value >= 400:
                    return "#FFD700"  # Gold
                elif value >= 200:
                    return "#FFA500"  # Orange
                else:
                    return "#FF6347"  # Red (low)

            elif viz_type == "Valid Votes" or viz_type == "Valid Votes (dots)":
                # Valid votes color scale
                if value >= 1000:
                    return "#2E8B57"  # Dark green (high)
                elif value >= 800:
                    return "#90EE90"  # Light green
                elif value >= 600:
                    return "#FFD700"  # Gold
                elif value >= 400:
                    return "#FFA500"  # Orange
                else:
                    return "#FF6347"  # Red (low)

            elif viz_type == "Party Results":
                # Party percentage color scale: Green (high support) to Blue (low support)
                if value >= 25:
                    return "#006400"  # Dark green (very strong)
                elif value >= 20:
                    return "#228B22"  # Forest green (strong)
                elif value >= 15:
                    return "#32CD32"  # Lime green (good)
                elif value >= 10:
                    return "#FFD700"  # Gold (moderate)
                elif value >= 5:
                    return "#87CEEB"  # Sky blue (weak)
                else:
                    return "#4169E1"  # Royal blue (very weak)

            return "#CCCCCC"  # Default gray

        def style_function(feature):
            """Style function for GeoJSON features"""
            properties = feature.get("properties", {})
            district_code = get_district_code_from_geojson(properties)

            # Default style
            style = {
                "fillColor": "#CCCCCC",
                "color": "black",
                "weight": 1,
                "fillOpacity": 0.3,
            }

            # Apply data-based coloring if available
            if district_code in viz_data:
                value = viz_data[district_code]
                style["fillColor"] = get_color_for_value(value, viz_type)
                style["fillOpacity"] = 0.7

            return style

        def create_popup_content(feature):
            """Create popup content for a feature"""
            properties = feature.get("properties", {})
            district_code = get_district_code_from_geojson(properties) or "Neznámý"

            popup_html = f"""
            <div style="font-family: Arial; width: 250px;">
                <h4 style="margin-bottom: 10px; color: #1f77b4;">Okrsek {district_code}</h4>
                <hr style="margin: 5px 0;">
            """

            # Get district data for this okrsek
            district_row = None
            if district_data is not None and isinstance(district_data, pd.DataFrame):
                okrsek_rows = district_data[
                    district_data["district_code"] == str(district_code)
                ]
                if not okrsek_rows.empty:
                    district_row = okrsek_rows.iloc[0]

            # Add the main visualization metric first
            if district_code in viz_data:
                value = viz_data[district_code]

                if viz_type == "Turnout":
                    popup_html += f"<p><strong>Účast:</strong> {fmt_pct(value, 1)}</p>"
                elif viz_type == "Estimated Voters":
                    popup_html += (
                        f"<p><strong>Registrovaní voliči:</strong> {fmt_int(int(value))}</p>"
                    )
                elif viz_type == "Valid Votes" or viz_type == "Valid Votes (dots)":
                    popup_html += f"<p><strong>Platné hlasy:</strong> {fmt_int(int(value))}</p>"
                elif viz_type == "Party Results" and selected_party:
                    popup_html += (
                        f"<p><strong>{selected_party}:</strong> {fmt_pct(value, 1)}</p>"
                    )

            # Always add voter estimate and vote share if available
            if district_row is not None:
                if "valid_votes" in district_row and pd.notna(
                    district_row["valid_votes"]
                ):
                    valid_votes = int(district_row["valid_votes"])

                    # Calculate voter estimate (votes ÷ seats available)
                    num_seats = get_seat_count(electoral_data)

                    if num_seats > 0:
                        voter_estimate = round(valid_votes / num_seats)
                        popup_html += f"<p><strong>Odhad voličů:</strong> {fmt_int(voter_estimate)}</p>"

                    popup_html += (
                        f"<p><strong>Platné hlasy:</strong> {fmt_int(valid_votes)}</p>"
                    )

                if "registered_voters" in district_row and pd.notna(
                    district_row["registered_voters"]
                ):
                    registered_voters = int(district_row["registered_voters"])
                    if registered_voters > 0 and "valid_votes" in locals():
                        vote_share = (valid_votes / registered_voters) * 100
                        popup_html += (
                            f"<p><strong>Podíl hlasů:</strong> {fmt_pct(vote_share, 1)} registrovaných voličů</p>"
                        )

                # Add other context data if not already shown
                if (
                    viz_type != "Turnout"
                    and "turnout_percentage" in district_row
                    and pd.notna(district_row["turnout_percentage"])
                ):
                    popup_html += (
                        f"<p><strong>Účast:</strong> {fmt_pct(district_row['turnout_percentage'], 1)}</p>"
                    )

                if (
                    viz_type != "Estimated Voters"
                    and "registered_voters" in district_row
                    and pd.notna(district_row["registered_voters"])
                ):
                    popup_html += (
                        f"<p><strong>Registrovaní voliči:</strong> {fmt_int(int(district_row['registered_voters']))}</p>"
                    )
            else:
                popup_html += (
                    "<p><em>Detailní data pro tento okrsek nejsou k dispozici</em></p>"
                )

            popup_html += f"""
                <hr style="margin: 5px 0;">
                <p style="font-size: 10px; color: #666;">Klikněte pro detail</p>
            </div>
            """

            return popup_html

        # Add GeoJSON layer with data styling
        for feature in geojson_data["features"]:
            popup_content = create_popup_content(feature)

            # Create informative tooltip based on visualization type
            properties = feature.get("properties", {})
            district_code = get_district_code_from_geojson(properties) or "Neznámý"

            tooltip_text = f"Okrsek {district_code}"

            # Add relevant data to tooltip based on visualization type
            if district_code in viz_data:
                value = viz_data[district_code]

                if viz_type == "Turnout":
                    tooltip_text = f"Okrsek {district_code}: {fmt_pct(value, 1)} účast"
                elif viz_type == "Estimated Voters":
                    tooltip_text = (
                        f"Okrsek {district_code}: {fmt_int(int(value))} registrovaných voličů"
                    )
                elif viz_type == "Valid Votes" or viz_type == "Valid Votes (dots)":
                    tooltip_text = (
                        f"Okrsek {district_code}: {fmt_int(int(value))} platných hlasů"
                    )
                elif viz_type == "Party Results" and selected_party:
                    tooltip_text = (
                        f"Okrsek {district_code}: {fmt_pct(value, 1)} {selected_party}"
                    )

            # Add voter estimate if available in district data
            if district_data is not None and isinstance(district_data, pd.DataFrame):
                okrsek_rows = district_data[
                    district_data["district_code"] == str(district_code)
                ]
                if not okrsek_rows.empty:
                    row = okrsek_rows.iloc[0]
                    if "valid_votes" in row and pd.notna(row["valid_votes"]):
                        valid_votes = int(row["valid_votes"])

                        # Calculate voter estimate for tooltip
                        num_seats = get_seat_count(electoral_data)
                        if num_seats > 0:
                            voter_estimate = round(valid_votes / num_seats)
                            # Add voter estimate to tooltip based on visualization type
                            if viz_type == "Party Results":
                                tooltip_text += f" | ~{fmt_int(voter_estimate)} voličů"
                            elif viz_type not in [
                                "Estimated Voters"
                            ]:  # Don't duplicate for estimated voters viz
                                tooltip_text += f" | ~{fmt_int(voter_estimate)} voličů"

            folium.GeoJson(
                feature,
                style_function=style_function,
                popup=folium.Popup(popup_content, max_width=300),
                tooltip=folium.Tooltip(tooltip_text),
            ).add_to(m)

            # Add visible label with key metric for each district
            if feature.get("geometry") and feature["geometry"].get("coordinates"):
                # Calculate polygon centroid for label placement
                if feature["geometry"]["type"] == "Polygon":
                    coords = feature["geometry"]["coordinates"][0]
                elif feature["geometry"]["type"] == "MultiPolygon":
                    coords = feature["geometry"]["coordinates"][0][0]
                else:
                    coords = []

                if coords:
                    # Simple centroid calculation
                    lats = [coord[1] for coord in coords]
                    lons = [coord[0] for coord in coords]
                    center_lat = sum(lats) / len(lats)
                    center_lon = sum(lons) / len(lons)

                    # Create label text based on visualization type - show only the main figure
                    label_text = ""

                    if district_code in viz_data:
                        value = viz_data[district_code]

                        if viz_type == "Turnout":
                            label_text = f"{fmt_pct(value, 0)}"
                        elif viz_type == "Estimated Voters":
                            # Show abbreviated form for large numbers
                            if value >= 1000:
                                label_text = f"{value / 1000:.1f}k"
                            else:
                                label_text = f"{int(value)}"
                        elif (
                            viz_type == "Valid Votes"
                            or viz_type == "Valid Votes (dots)"
                        ):
                            # Show abbreviated form for large numbers
                            if value >= 1000:
                                label_text = f"{value / 1000:.1f}k"
                            else:
                                label_text = f"{int(value)}"
                        elif viz_type == "Party Results" and selected_party:
                            label_text = f"{fmt_pct(value, 0)}"

                    # Add vote count for non-percentage visualizations
                    if district_data is not None and isinstance(
                        district_data, pd.DataFrame
                    ):
                        okrsek_rows = district_data[
                            district_data["district_code"] == str(district_code)
                        ]
                        if not okrsek_rows.empty:
                            row = okrsek_rows.iloc[0]
                            if "valid_votes" in row and pd.notna(row["valid_votes"]):
                                valid_votes = int(row["valid_votes"])
                                if viz_type not in [
                                    "Turnout",
                                    "Party Results",
                                ]:  # Show votes for non-percentage viz
                                    if valid_votes >= 1000:
                                        label_text = f"{valid_votes / 1000:.1f}k"
                                    else:
                                        label_text = f"{valid_votes}"

                    # Add the label marker with larger font
                    if label_text and show_labels:
                        folium.Marker(
                            location=[center_lat, center_lon],
                            icon=folium.DivIcon(
                                html=f'<div style="font-size: 16px; color: black; font-weight: bold; text-shadow: 1px 1px 1px white; text-align: center; line-height: 1.1; background-color: rgba(255,255,255,0.9); padding: 2px 4px; border-radius: 3px;">{label_text}</div>',
                                icon_size=(60, 35),
                                icon_anchor=(30, 17),
                            ),
                        ).add_to(m)

        # Add legend based on visualization type
        if viz_data:
            legend_html = f"""
            <div style="position: fixed; 
                        bottom: 50px; left: 50px; width: 170px; height: auto; min-height: 140px;
                        background-color: white; border:2px solid grey; z-index:9999; 
                        font-size:11px; font-family: Arial; padding: 8px; box-sizing: border-box;">
                <h5 style="margin: 0 0 8px 0; font-size: 13px;">{viz_label(viz_type)}</h5>
            """

            if viz_type == "Turnout":
                legend_html += """
                <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#2E8B57"></i> ≥60% (vysoká)</p>
                <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#90EE90"></i> 50–59% (středně vysoká)</p>
                <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#FFD700"></i> 40–49% (střední)</p>
                <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#FFA500"></i> 30–39% (nižší)</p>
                <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#FF6347"></i> <30% (nízká)</p>
                """
            elif viz_type == "Estimated Voters":
                legend_html += """
                <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#2E8B57"></i> ≥800 (vysoké)</p>
                <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#90EE90"></i> 600–799 (středně vysoké)</p>
                <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#FFD700"></i> 400–599 (střední)</p>
                <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#FFA500"></i> 200–399 (nižší)</p>
                <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#FF6347"></i> <200 (nízké)</p>
                """
            elif viz_type == "Party Results":
                legend_html += f"""
                <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#006400"></i> ≥25% (velmi silné)</p>
                <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#228B22"></i> 20–24% (silné)</p>
                <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#32CD32"></i> 15–19% (dobré)</p>
                <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#FFD700"></i> 10–14% (střední)</p>
                <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#87CEEB"></i> 5–9% (slabé)</p>
                <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#4169E1"></i> <5% (velmi slabé)</p>
                """

            legend_html += '<p style="margin: 3px 0;"><i class="fa fa-square" style="color:#CCCCCC"></i> Bez dat</p></div>'

            m.get_root().html.add_child(folium.Element(legend_html))

    # Don't use auto-fit in tabs - it causes zoom issues
    # The calculated zoom_start should be sufficient

    return m


def create_pydeck_map(
    geojson_data,
    electoral_data=None,
    viz_type="Turnout",
    selected_party=None,
):
    """Create a Pydeck map for faster polygon rendering."""
    if not geojson_data or "features" not in geojson_data:
        return None

    district_data = electoral_data.get("district_data") if electoral_data else None
    party_data = (
        electoral_data.get("district_party_results") if electoral_data else None
    )

    viz_data = {}
    if (
        isinstance(district_data, pd.DataFrame)
        and "district_code" in district_data.columns
    ):
        for _, row in district_data.iterrows():
            district_code = str(row.get("district_code", ""))
            if viz_type == "Turnout" and "turnout_percentage" in row:
                viz_data[district_code] = float(row.get("turnout_percentage", 0))
            elif viz_type == "Estimated Voters" and "registered_voters" in row:
                viz_data[district_code] = float(row.get("registered_voters", 0))
            elif viz_type in ["Valid Votes", "Valid Votes (dots)"] and "valid_votes" in row:
                viz_data[district_code] = float(row.get("valid_votes", 0))

    if (
        viz_type == "Party Results"
        and selected_party
        and isinstance(party_data, pd.DataFrame)
    ):
        party_subset = party_data[party_data["party_name"] == selected_party].copy()
        if not party_subset.empty:
            party_subset["district_code"] = (
                party_subset["district_id"].str.split("-").str[0]
            )
            for district_code, group in party_subset.groupby("district_code"):
                total_votes = group["total_district_votes"].sum()
                party_votes = group["votes"].sum()
                if total_votes > 0:
                    viz_data[str(district_code)] = (party_votes / total_votes) * 100

    def get_color_for_value(value):
        if value is None:
            return [200, 200, 200, 120]
        if viz_type == "Turnout":
            if value >= 60:
                return [46, 125, 50, 170]
            if value >= 50:
                return [102, 187, 106, 170]
            if value >= 40:
                return [255, 235, 59, 170]
            if value >= 30:
                return [255, 152, 0, 170]
            return [244, 67, 54, 170]
        if viz_type == "Estimated Voters":
            if value >= 2000:
                return [63, 81, 181, 170]
            if value >= 1000:
                return [92, 107, 192, 170]
            if value >= 500:
                return [255, 235, 59, 170]
            if value >= 200:
                return [255, 152, 0, 170]
            return [244, 67, 54, 170]
        if viz_type in ["Valid Votes", "Valid Votes (dots)"]:
            if value >= 1500:
                return [63, 81, 181, 170]
            if value >= 800:
                return [92, 107, 192, 170]
            if value >= 400:
                return [255, 235, 59, 170]
            if value >= 200:
                return [255, 152, 0, 170]
            return [244, 67, 54, 170]
        if viz_type == "Party Results":
            if value >= 50:
                return [46, 125, 50, 170]
            if value >= 30:
                return [102, 187, 106, 170]
            if value >= 20:
                return [255, 235, 59, 170]
            if value >= 10:
                return [255, 152, 0, 170]
            return [244, 67, 54, 170]
        return [100, 100, 100, 170]

    polygons = []
    lats = []
    lons = []
    for feature in geojson_data.get("features", []):
        props = feature.get("properties", {})
        district_code = get_district_code_from_geojson(props)
        value = viz_data.get(district_code)
        color = get_color_for_value(value)
        name = props.get("naz_mco") or props.get("naz_obec") or props.get("nazev") or ""

        geometry = feature.get("geometry") or {}
        geom_type = geometry.get("type")
        coords = geometry.get("coordinates") or []
        if geom_type == "Polygon":
            rings = [coords[0]] if coords else []
        elif geom_type == "MultiPolygon":
            rings = [poly[0] for poly in coords if poly]
        else:
            rings = []

        for ring in rings:
            if not ring:
                continue
            for lon, lat in ring:
                lats.append(lat)
                lons.append(lon)
            polygons.append(
                {
                    "polygon": ring,
                    "district_code": district_code,
                    "value": value,
                    "color": color,
                    "name": name,
                }
            )

    if not polygons or not lats or not lons:
        return None

    center_lat = (min(lats) + max(lats)) / 2
    center_lon = (min(lons) + max(lons)) / 2
    lat_range = max(lats) - min(lats)
    lon_range = max(lons) - min(lons)
    max_range = max(lat_range, lon_range)

    if max_range < 0.01:
        zoom = 14
    elif max_range < 0.05:
        zoom = 12
    elif max_range < 0.1:
        zoom = 11
    elif max_range < 0.2:
        zoom = 10
    else:
        zoom = 9

    layer = pdk.Layer(
        "PolygonLayer",
        polygons,
        get_polygon="polygon",
        get_fill_color="color",
        get_line_color=[30, 30, 30, 120],
        line_width_min_pixels=1,
        pickable=True,
        auto_highlight=True,
    )

    tooltip = {
        "text": "{district_code}\\n{value}",
    }

    view_state = pdk.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=zoom,
        bearing=0,
        pitch=0,
    )

    return pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip=tooltip,
        map_style=None,
    )


def _mandates_column(party_df: pd.DataFrame) -> Optional[str]:
    for col in ("mandates_won", "mandates"):
        if col in party_df.columns:
            return col
    return None


def _party_key(name) -> str:
    return re.sub(r"\s+", " ", str(name or "")).strip().lower()


def _with_vote_share(party_df: pd.DataFrame) -> pd.DataFrame:
    """Add `share`: the party's votes as a percentage of all valid votes.

    In municipal elections ČSÚ's own percentage is recalculated for lists with
    fewer candidates than seats, so it does not add up to 100 and can rank a
    list above one with more votes.
    """
    party_df = party_df.copy()
    total_votes = party_df["votes_absolute"].sum() if "votes_absolute" in party_df else 0
    if total_votes > 0:
        party_df["share"] = party_df["votes_absolute"] / total_votes * 100
    else:
        party_df["share"] = party_df["votes_percentage"]
    return party_df


def _previous_party_lookup(previous_data) -> Dict[str, Dict]:
    """Results of the previous election keyed by party name (short and full)."""
    previous_df = (previous_data or {}).get("party_results")
    if not isinstance(previous_df, pd.DataFrame) or previous_df.empty:
        return {}

    previous_df = _with_vote_share(previous_df)
    mandates_col = _mandates_column(previous_df)
    lookup = {}
    for _, row in previous_df.iterrows():
        entry = {
            "share": float(row.get("share", 0) or 0),
            "mandates": int(row.get(mandates_col, 0) or 0) if mandates_col else None,
        }
        for name_col in ("party_name_full", "party_name"):
            key = _party_key(row.get(name_col))
            if key:
                lookup.setdefault(key, entry)
    return lookup


def display_electoral_overview(data, previous_data=None, previous_name=""):
    """Headline numbers and party results, compared with the previous election"""
    stats = data.get("summary_statistics") or {}
    previous_stats = (previous_data or {}).get("summary_statistics") or {}
    party_df = data.get("party_results")
    has_parties = isinstance(party_df, pd.DataFrame) and not party_df.empty

    turnout = float(stats.get("turnout_percentage") or 0)
    registered = int(stats.get("registered_voters") or 0)
    previous_turnout = float(previous_stats.get("turnout_percentage") or 0)
    previous_registered = int(previous_stats.get("registered_voters") or 0)

    if has_parties:
        party_df = _with_vote_share(party_df)
    mandates_col = _mandates_column(party_df) if has_parties else None
    total_mandates = int(party_df[mandates_col].sum()) if mandates_col else 0
    if total_mandates == 0:
        # The data set has no seat allocation (e.g. regions in parliamentary elections)
        mandates_col = None

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        "Volební účast",
        fmt_pct(turnout) if turnout > 0 else "–",
        delta=fmt_pp(turnout - previous_turnout)
        if turnout > 0 and previous_turnout > 0
        else None,
    )
    col2.metric(
        "Zapsaní voliči",
        fmt_int(registered) if registered > 0 else "–",
        delta=fmt_signed_int(registered - previous_registered)
        if registered > 0 and previous_registered > 0
        else None,
        delta_color="off",
    )
    col3.metric("Kandidující strany", fmt_int(len(party_df)) if has_parties else "–")
    col4.metric("Rozdělené mandáty", fmt_int(total_mandates) if total_mandates else "–")

    if previous_data:
        st.caption(f"Změny jsou oproti volbám {previous_name}.")

    if not has_parties:
        st.warning("Pro tento výběr nejsou dostupné výsledky stran.")
        return

    party_sorted = party_df.sort_values("share", ascending=False).reset_index(drop=True)
    previous_lookup = _previous_party_lookup(previous_data)

    def previous_for(row):
        for name_col in ("party_name_full", "party_name"):
            entry = previous_lookup.get(_party_key(row.get(name_col)))
            if entry:
                return entry
        return None

    winner = party_sorted.iloc[0]
    winner_text = (
        f"Nejvíc hlasů získala kandidátka **{winner['party_name']}** "
        f"({fmt_pct(winner['share'])})"
    )
    if len(party_sorted) > 1:
        runner_up = party_sorted.iloc[1]
        margin = float(winner["share"]) - float(runner_up["share"])
        winner_text += (
            f", s náskokem {fmt_pp(margin, signed=False)} "
            f"před **{runner_up['party_name']}**"
        )
    st.markdown(winner_text + ".")

    st.subheader("Výsledky stran")

    max_bars = 12
    chart_df = party_sorted.head(max_bars).copy()
    chart_df["label"] = chart_df["party_name"].apply(
        lambda name: name if len(str(name)) <= 42 else str(name)[:40].rstrip() + "…"
    )
    # Two parties can share a shortened name; the axis needs unique labels
    duplicated = chart_df["label"].duplicated(keep=False)
    chart_df.loc[duplicated, "label"] = (
        chart_df.loc[duplicated, "label"]
        + " ("
        + chart_df.loc[duplicated, "list_number"].astype(str)
        + ")"
    )

    def bar_text(row):
        text = fmt_pct(row["share"])
        if mandates_col and row[mandates_col] > 0:
            text += f" · {int(row[mandates_col])} mand."
        return text

    chart_df["text"] = chart_df.apply(bar_text, axis=1)
    has_seat = (
        chart_df[mandates_col] > 0
        if mandates_col
        else pd.Series(True, index=chart_df.index)
    )

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=chart_df["label"],
            x=chart_df["share"],
            orientation="h",
            text=chart_df["text"],
            textposition="outside",
            cliponaxis=False,
            marker_color=["#2563eb" if seat else "#b6bfcc" for seat in has_seat],
            customdata=chart_df["party_name"],
            hovertemplate="%{customdata}<br>%{x:.2f} % hlasů<extra></extra>",
            showlegend=False,
        )
    )

    previous_points = [
        (row["label"], previous_for(row)["share"])
        for _, row in chart_df.iterrows()
        if previous_for(row)
    ]
    if previous_points:
        fig.add_trace(
            go.Scatter(
                y=[label for label, _ in previous_points],
                x=[share for _, share in previous_points],
                mode="markers",
                marker=dict(symbol="line-ns", size=18, line=dict(width=3, color="#111827")),
                name=f"Výsledek {previous_name}",
                hovertemplate=f"{previous_name}: %{{x:.2f}} %<extra></extra>",
            )
        )

    fig.update_layout(
        height=70 + 34 * len(chart_df),
        margin=dict(l=0, r=90, t=10, b=30),
        xaxis=dict(title="Podíl hlasů (%)", rangemode="tozero"),
        yaxis=dict(autorange="reversed", title=None),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0),
    )
    st.plotly_chart(fig, use_container_width=True)

    notes = []
    if mandates_col and not has_seat.all():
        notes.append("Šedě jsou kandidátky, které nezískaly žádný mandát.")
    if len(party_sorted) > max_bars:
        notes.append(
            f"Graf ukazuje {max_bars} nejsilnějších kandidátek z {len(party_sorted)}, "
            "všechny jsou v tabulce níže."
        )
    if notes:
        st.caption(" ".join(notes))

    table = pd.DataFrame(
        {
            "Č.": party_sorted["list_number"],
            "Kandidátka": party_sorted["party_name"],
            "Hlasy": party_sorted["votes_absolute"],
            "Podíl (%)": party_sorted["share"].round(2),
        }
    )
    # Shown only where it differs, i.e. when some list is shorter than the council
    official_share = party_sorted["votes_percentage"].round(2)
    has_recalculated = bool(((official_share - table["Podíl (%)"]).abs() > 0.05).any())
    decimals = {"Podíl (%)": 2}
    if has_recalculated:
        table["Přepočtený podíl (%)"] = official_share
        decimals["Přepočtený podíl (%)"] = 2
    if mandates_col:
        table["Mandáty"] = party_sorted[mandates_col].astype(int)

    previous_rows = [previous_for(row) for _, row in party_sorted.iterrows()]
    has_comparison = any(previous_rows)
    if has_comparison:
        previous_share = pd.Series(
            [entry["share"] if entry else None for entry in previous_rows], dtype="float"
        )
        table[f"Podíl {previous_name} (%)"] = previous_share.round(2)
        table["Změna (p. b.)"] = (table["Podíl (%)"] - previous_share).round(2)
        decimals[f"Podíl {previous_name} (%)"] = 2
        decimals["Změna (p. b.)"] = 2
        if mandates_col:
            table[f"Mandáty {previous_name}"] = pd.Series(
                [entry["mandates"] if entry else None for entry in previous_rows],
                dtype="Int64",
            )

    st.dataframe(
        czech_table(table, decimals, signed=("Změna (p. b.)",)),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Č.": st.column_config.Column(
                width="small", help="Číslo kandidátky na hlasovacím lístku"
            )
        },
        height=min(38 + 35 * len(table), 600),
    )

    table_notes = []
    if has_recalculated:
        table_notes.append(
            "Přepočtený podíl uvádí ČSÚ: bere ohled na kandidátky, které mají méně "
            "kandidátů, než kolik se volí zastupitelů, a rozhoduje o překročení "
            "pětiprocentní hranice."
        )
    if has_comparison:
        table_notes.append(
            f"Srovnání s rokem {previous_name} je vyplněné jen u kandidátek, "
            "které tehdy kandidovaly pod stejným názvem."
        )
    elif previous_data:
        table_notes.append(
            f"Žádná z kandidátek nekandidovala v roce {previous_name} pod stejným "
            "názvem, proto tabulka neobsahuje srovnání."
        )
    if registered > 0 and party_sorted["votes_absolute"].sum() > registered:
        table_notes.append(
            "Hlasů je víc než voličů, protože každý volič může dát tolik hlasů, "
            "kolik se volí zastupitelů."
        )
    if table_notes:
        st.caption(" ".join(table_notes))


def display_turnout_analysis(data, previous_data=None, previous_name=""):
    """Turnout in the whole municipality and how it differs between precincts"""
    stats = data.get("summary_statistics") or {}
    previous_stats = (previous_data or {}).get("summary_statistics") or {}

    district_df = data.get("district_data")
    if isinstance(district_df, pd.DataFrame) and not district_df.empty:
        district_df = district_df[
            (district_df["district_code"] != "TOTAL")
            & (district_df["registered_voters"] > 0)
        ].copy()
    else:
        district_df = pd.DataFrame()

    turnout = float(stats.get("turnout_percentage") or 0)
    registered = int(stats.get("registered_voters") or 0)
    previous_turnout = float(previous_stats.get("turnout_percentage") or 0)

    if turnout <= 0 and district_df.empty:
        st.info("Pro tento výběr nejsou dostupná data o účasti.")
        return

    returned = int(district_df["returned_ballots"].sum()) if not district_df.empty else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        "Volební účast",
        fmt_pct(turnout) if turnout > 0 else "–",
        delta=fmt_pp(turnout - previous_turnout)
        if turnout > 0 and previous_turnout > 0
        else None,
    )
    col2.metric("Zapsaní voliči", fmt_int(registered) if registered else "–")
    col3.metric("Odevzdané obálky", fmt_int(returned) if returned else "–")
    col4.metric("Okrsky", fmt_int(len(district_df)) if not district_df.empty else "–")

    if previous_turnout > 0:
        st.caption(f"Změna účasti je oproti volbám {previous_name}.")

    if len(district_df) < 2:
        return

    district_df["Okrsek"] = district_df["district_code"].astype(str)
    lowest = district_df.loc[district_df["turnout_percentage"].idxmin()]
    highest = district_df.loc[district_df["turnout_percentage"].idxmax()]
    st.markdown(
        f"Účast v okrscích se pohybuje od **{fmt_pct(lowest['turnout_percentage'])}** "
        f"(okrsek {lowest['Okrsek']}) po **{fmt_pct(highest['turnout_percentage'])}** "
        f"(okrsek {highest['Okrsek']})."
    )

    st.subheader("Účast v okrscích")
    if len(district_df) > 25:
        fig = px.histogram(
            district_df,
            x="turnout_percentage",
            nbins=30,
            labels={"turnout_percentage": "Účast (%)"},
            color_discrete_sequence=["#2563eb"],
        )
        fig.update_traces(
            hovertemplate="Účast %{x} %<br>%{y} okrsků<extra></extra>",
            marker_line_width=1,
            marker_line_color="white",
        )
        fig.update_layout(yaxis_title="Počet okrsků")
    else:
        ordered = district_df.sort_values("turnout_percentage", ascending=False)
        fig = px.bar(
            ordered,
            x="Okrsek",
            y="turnout_percentage",
            labels={"turnout_percentage": "Účast (%)"},
            color_discrete_sequence=["#2563eb"],
        )
        fig.update_xaxes(type="category")
        fig.update_traces(hovertemplate="Okrsek %{x}<br>Účast %{y:.1f} %<extra></extra>")

    if turnout > 0:
        line = dict(line_dash="dash", line_color="#111827", annotation_text="Celkem")
        if len(district_df) > 25:
            fig.add_vline(x=turnout, **line)
        else:
            fig.add_hline(y=turnout, **line)
    fig.update_layout(height=360, margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig, use_container_width=True)

    table = pd.DataFrame(
        {
            "Okrsek": district_df["Okrsek"],
            "Účast (%)": district_df["turnout_percentage"].round(2),
            "Zapsaní voliči": district_df["registered_voters"],
            "Odevzdané obálky": district_df["returned_ballots"],
        }
    ).sort_values("Účast (%)", ascending=False)
    st.dataframe(
        czech_table(table, {"Účast (%)": 2}),
        use_container_width=True,
        hide_index=True,
        height=min(38 + 35 * len(table), 420),
    )
    st.caption(
        "Účast je počet odevzdaných obálek vydělený počtem zapsaných voličů. "
        "Kliknutím na záhlaví sloupce tabulku seřadíte."
    )


def display_geographic_analysis(
    geojson_data, electoral_data=None, election_id: str = "kv2022"
):
    """Display geographic analysis with filtered electoral districts map for the selected municipality"""
    # Removed redundant subheader since it's now handled in main()

    # Get URL parameters
    url_params = get_url_params()

    # Initialize map_data to avoid UnboundLocalError
    map_data = None

    if not geojson_data:
        st.error("GeoJSON se nepodařilo načíst. Ověřte připojení k internetu.")

        # Add cache clearing option
        col1, col2 = st.columns([3, 1])
        with col1:
            st.info("💡 Pokud problém přetrvává, zkuste vyčistit cache map.")
        with col2:
            if st.button(
                "🔄 Vyčistit cache",
                help="Vymaže cache map a zkusí znovu stáhnout data",
            ):
                # Clear the streamlit cache
                load_geojson_data.clear()

                # Clear the local file cache
                election_config = get_election_config(election_id)
                if election_config.election_type == "parliamentary":
                    cache_file = Path(
                        "input/raw/electoral_districts_boundaries_2025_wgs84.geojson"
                    )
                else:
                    cache_file = Path(
                        "input/raw/electoral_districts_boundaries.geojson"
                    )
                if cache_file.exists():
                    cache_file.unlink()
                    st.success("🗑️ Cache soubor byl smazán!")

                st.success("Cache vyčištěna! Obnovte stránku.")
                st.rerun()
        return

    # Check if we have electoral data to overlay
    district_data = None
    party_data = None
    if electoral_data and "district_data" in electoral_data:
        district_data = electoral_data["district_data"]
    if electoral_data and "district_party_results" in electoral_data:
        party_data = electoral_data["district_party_results"]

    # Use the already filtered GeoJSON data (filtered by main function)
    municipality_features = geojson_data.get("features", [])

    map_notes = []
    if len(municipality_features) > MAX_LABELLED_PRECINCTS:
        map_notes.append(
            "Okrsků je tolik, že by se popisky překrývaly. "
            "Hodnotu okrsku uvidíte po najetí myší, podrobnosti po kliknutí."
        )
    boundaries_file = get_election_config(election_id).boundaries_file
    if boundaries_file and (Path("input/raw") / boundaries_file).exists():
        map_notes.append(
            "Hranice okrsků jsou z roku 2025, novější ČSÚ zatím nezveřejnil. "
            "Okrsek, který od té doby vznikl nebo změnil číslo, v mapě chybí."
        )
    if map_notes:
        st.caption(" ".join(map_notes))

    if not municipality_features:
        st.warning("V geografických datech nebyly nalezeny žádné okrsky.")
        return

    # The geojson_data is already filtered for the selected municipality
    filtered_geojson = geojson_data

    # Map visualization controls
    st.subheader("Nastavení mapy")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        # Get default from URL or use first option
        viz_options = ["Turnout", "Estimated Voters", "Valid Votes", "Party Results"]
        default_viz_type = get_param_value(url_params, "viz_type", viz_options[0])
        if default_viz_type == "Valid Votes (dots)":
            default_viz_type = "Valid Votes"
        if default_viz_type not in viz_options:
            default_viz_type = viz_options[0]

        viz_type = st.selectbox(
            "Co zobrazit:",
            viz_options,
            index=viz_options.index(default_viz_type),
            format_func=viz_label,
            help="Vyberte datovou vrstvu pro obarvení mapy.",
            key="viz_type_select",
        )

    with col2:
        map_options = ["Geographic Map", "Dot Density", "Cartogram", "Pydeck (fast)"]
        default_map_type = get_param_value(url_params, "map_type", map_options[0])
        if default_map_type not in map_options:
            default_map_type = map_options[0]

        map_type = st.selectbox(
            "Typ mapy:",
            map_options,
            index=map_options.index(default_map_type),
            format_func=map_type_label,
            help=(
                "Geografická mapa obarví okrsky podle hodnoty. Tečková mapa kreslí "
                "jednu tečku za zvolený počet hlasů. Kartogram zvětší okrsky podle "
                "počtu hlasů. Rychlá mapa se hodí pro velká města."
            ),
            key="map_type_select",
        )

    with col3:
        style_options = [
            "OpenStreetMap",
            "CartoDB Positron",
            "CartoDB Dark Matter",
            "CartoDB Voyager",
        ]
        default_style = get_param_value(url_params, "base_map_style", style_options[0])
        if default_style not in style_options:
            default_style = style_options[0]

        base_map_style_main = st.selectbox(
            "Podkladová mapa:",
            style_options,
            index=style_options.index(default_style),
            help="Zvolte styl podkladu. Tlumené styly lépe zvýrazní vrstvy.",
            key="base_map_style_select",
        )

    selected_party = None
    if viz_type == "Party Results" and party_data is not None:
        with col4:
            # Get available parties
            available_parties = (
                sorted(party_data["party_name"].unique())
                if isinstance(party_data, pd.DataFrame)
                else []
            )
            if available_parties:
                default_party = get_param_value(
                    url_params, "selected_party", available_parties[0]
                )
                if default_party not in available_parties:
                    default_party = available_parties[0]

                selected_party = st.selectbox(
                    "Vyberte stranu:",
                    available_parties,
                    index=available_parties.index(default_party),
                    help="Vyberte stranu pro zobrazení výsledků.",
                    key="selected_party_select",
                )
            else:
                st.warning("Nejsou dostupná data o stranách.")
                viz_type = "Turnout"  # Fallback

    # Update URL parameters when filters change
    update_url_params(
        viz_type=viz_type,
        map_type=map_type,
        base_map_style=base_map_style_main,
        selected_party=selected_party if viz_type == "Party Results" else None,
    )

    # Create and display the map based on type
    if map_type == "Pydeck (fast)":
        st.subheader("Rychlá mapa (Pydeck)")
        st.info(
            "⚡ Pydeck renderuje polygony rychleji než Folium. Podklad je vypnutý kvůli tokenům Mapbox."
        )

        pydeck_map = create_pydeck_map(
            filtered_geojson, electoral_data, viz_type, selected_party
        )
        if pydeck_map:
            st.pydeck_chart(pydeck_map, use_container_width=True)
        else:
            st.error("Nepodařilo se vytvořit Pydeck mapu.")

    elif map_type == "Cartogram":
        st.subheader("Kartogram")
        st.info(
            "📐 **Kartogram**: Plochy jsou škálované podle **počtu hlasů** "
            "(větší plocha = více hlasů). Barvy odpovídají zvolené metrice. "
            "Výchozí režim drží kruhy na geografické pozici; zapněte odsun při překryvu, "
            "pokud je čitelnost důležitější než přesnost polohy."
        )

        # Add base size control
        col_a, col_b, col_c = st.columns([2, 1, 1])
        with col_a:
            st.write("**Velikost kruhů:**")
        with col_b:
            default_base_size = float(
                get_param_value(url_params, "base_size", "0.0015")
            )
            base_size = st.slider(
                "Základní velikost",
                min_value=0.001,
                max_value=0.005,
                value=default_base_size,
                step=0.0001,
                format="%.10f",
                help="Určuje celkovou velikost kruhů. Vyšší hodnota = větší kruhy.",
                key="base_size_slider",
            )
        with col_c:
            default_collision = (
                get_param_value(url_params, "collision_avoidance", "false").lower()
                == "true"
            )
            collision_avoidance = st.checkbox(
                "Odsun při překryvu",
                value=default_collision,
                help="Zapnuto: kruhy se odsouvají, aby se nepřekrývaly. "
                "Vypnuto: kruhy zůstávají na přesné poloze (doporučeno).",
                key="collision_avoidance_checkbox",
            )

        # Update URL parameters for cartogram controls
        update_url_params(base_size=base_size, collision_avoidance=collision_avoidance)

        # Create cartogram
        cartogram_gdf = create_cartogram(
            filtered_geojson,
            electoral_data,
            viz_type,
            selected_party,
            base_size,
            collision_avoidance,
        )

        if cartogram_gdf is not None:
            cartogram_map = create_cartogram_map(
                cartogram_gdf, viz_type, selected_party, electoral_data
            )

            if cartogram_map:
                # Display the cartogram map
                map_data = st_folium(
                    cartogram_map,
                    width="100%",  # Explicit width
                    height=1000,  # Fixed height for tabs
                    returned_objects=["last_clicked", "last_object_clicked"],
                    key=f"cartogram_{viz_type}_{selected_party}_{base_size}_{collision_avoidance}",  # Include collision_avoidance in key
                )
            else:
                st.error("Nepodařilo se vytvořit kartogram.")
        else:
            st.error("Nepodařilo se vytvořit data pro kartogram.")
    elif map_type == "Dot Density":
        st.subheader("Tečková mapa")
        st.caption(
            "Každá tečka představuje zvolený počet hlasů a leží uvnitř okrsku, "
            "ve kterém hlasy padly. Když zapnete barvení podle podílu, barva tečky "
            "ukazuje podíl hlasů v okrsku: červená nízký, žlutá střední, zelená vysoký."
        )

        # Dot density controls
        col_a, col_b, col_c, col_d = st.columns([1, 1, 1, 1])
        with col_a:
            default_votes_per_dot_raw = get_param_value(url_params, "votes_per_dot", "100")
            try:
                default_votes_per_dot = max(1, int(default_votes_per_dot_raw))
            except (TypeError, ValueError):
                default_votes_per_dot = 100

            votes_per_dot = st.number_input(
                "Hlasů na tečku:",
                min_value=1,
                value=default_votes_per_dot,
                step=1,
                help="Kolik hlasů představuje jedna tečka. Menší hodnota = více teček.",
                key="votes_per_dot_select",
            )
        with col_b:
            default_dot_spacing = int(get_param_value(url_params, "dot_spacing", "70"))
            dot_spacing = st.slider(
                "Rozestup teček (m)",
                min_value=30,
                max_value=120,
                value=default_dot_spacing,
                step=10,
                help="Vzdálenost mezi tečkami v metrech.",
                key="dot_spacing_slider",
            )
        with col_c:
            default_dot_size = int(get_param_value(url_params, "dot_size", "2"))
            dot_size = st.slider(
                "Velikost tečky",
                min_value=1,
                max_value=5,
                value=default_dot_size,
                help="Vizuální velikost teček na mapě.",
                key="dot_size_slider",
            )
        with col_d:
            default_color_scale = (
                get_param_value(url_params, "use_color_scale", "true").lower() == "true"
            )
            use_color_scale = st.checkbox(
                "Barvit podle podílu",
                value=default_color_scale,
                help="Barví tečky podle podílu hlasů (červená → zelená).",
                key="use_color_scale_checkbox",
            )

        # Update URL parameters for dot density controls
        update_url_params(
            votes_per_dot=int(votes_per_dot),
            dot_spacing=dot_spacing,
            dot_size=dot_size,
            use_color_scale=use_color_scale,
        )

        # Create dot density map
        if district_data is not None and isinstance(district_data, pd.DataFrame):
            # Build GeoDataFrame
            gdf = gpd.GeoDataFrame.from_features(
                filtered_geojson["features"], crs="EPSG:4326"
            )
            # Handle both 2022 (CISLO) and 2025 (cislo) GeoJSON formats
            if "cislo" in gdf.columns:
                gdf["district_code"] = gdf["cislo"].astype(str)
            elif "CISLO" in gdf.columns:
                gdf["district_code"] = gdf["CISLO"].astype(str)
            else:
                st.error(
                    "V GeoJSON chybí pole s kódem okrsku (CISLO/cislo)."
                )
                return

            # Create vote series based on visualization type
            if viz_type == "Valid Votes (dots)" or viz_type == "Valid Votes":
                # Use valid votes for dot density
                vote_series = district_data.set_index("district_code")[
                    "valid_votes"
                ].fillna(0)
                dot_color = "#de425b"  # Red for votes

                # For color scaling with valid votes, use turnout percentage
                if use_color_scale:
                    color_scale_data = district_data.set_index("district_code")[
                        "turnout_percentage"
                    ].fillna(0)
                else:
                    color_scale_data = None

            elif viz_type == "Party Results" and selected_party:
                # Use party votes for dot density
                if party_data is not None and isinstance(party_data, pd.DataFrame):
                    party_subset = party_data[
                        party_data["party_name"] == selected_party
                    ].copy()
                    if not party_subset.empty:
                        party_subset["district_code"] = (
                            party_subset["district_id"].str.split("-").str[0]
                        )
                        party_votes = party_subset.groupby("district_code")[
                            "votes"
                        ].sum()
                        vote_series = party_votes.reindex(gdf["district_code"]).fillna(
                            0
                        )
                        dot_color = "#2166ac"  # Blue for party votes

                        # For color scaling with party results, use party percentage
                        if use_color_scale:
                            # Calculate party percentage for each district
                            party_percentages = party_subset.groupby("district_code")[
                                "percentage"
                            ].mean()
                            color_scale_data = party_percentages.reindex(
                                gdf["district_code"]
                            ).fillna(0)
                        else:
                            color_scale_data = None
                    else:
                        vote_series = pd.Series(0, index=gdf["district_code"])
                        dot_color = "#de425b"
                        color_scale_data = None
                else:
                    vote_series = pd.Series(0, index=gdf["district_code"])
                    dot_color = "#de425b"
                    color_scale_data = None
            else:
                # Fallback to valid votes
                vote_series = district_data.set_index("district_code")[
                    "valid_votes"
                ].fillna(0)
                dot_color = "#de425b"
                if use_color_scale:
                    color_scale_data = district_data.set_index("district_code")[
                        "turnout_percentage"
                    ].fillna(0)
                else:
                    color_scale_data = None

            # Create the icon fill layer
            try:
                # Calculate center and zoom from GeoDataFrame bounds
                bounds = gdf.total_bounds
                center_lat = (bounds[1] + bounds[3]) / 2
                center_lon = (bounds[0] + bounds[2]) / 2

                # Calculate zoom based on geographic extent
                lat_range = bounds[3] - bounds[1]
                lon_range = bounds[2] - bounds[0]
                max_range = max(lat_range, lon_range)

                # Set zoom based on geographic extent
                if max_range < 0.01:  # Very small area
                    zoom_start = 16
                elif max_range < 0.05:  # Small area
                    zoom_start = 15
                elif max_range < 0.1:  # Medium area
                    zoom_start = 14
                elif max_range < 0.2:  # Large area
                    zoom_start = 14
                else:  # Very large area
                    zoom_start = 13

                dot_map = create_map_with_tiles(
                    [center_lat, center_lon],
                    zoom_start,
                    base_map_style_main,
                )

                # Add district boundaries as background (light gray)
                folium.GeoJson(
                    filtered_geojson,
                    style_function=lambda _: {
                        "fillOpacity": 0.1,
                        "color": "gray",
                        "weight": 1,
                        "fillColor": "#f0f0f0",
                    },
                ).add_to(dot_map)

                # Add dot density layer
                icon_layer = icon_fill_layer(
                    gdf,
                    vote_series,
                    k_votes_per_dot=votes_per_dot,
                    spacing_m=dot_spacing,
                    dot_radius_px=dot_size,
                    dot_color=dot_color,
                    color_scale_data=color_scale_data,
                    use_color_scale=use_color_scale,
                )
                icon_layer.add_to(dot_map)

                # Add layer control
                folium.LayerControl().add_to(dot_map)

                # Add color scale legend when enabled
                if use_color_scale:
                    if viz_type == "Party Results" and selected_party:
                        legend_title = f"{selected_party} – podíl hlasů"
                        legend_type = "výkon strany"
                    else:
                        legend_title = "Účast (%)"
                        legend_type = "účast v okrscích"

                    color_legend_html = f"""
                    <div style="position: fixed; 
                                bottom: 50px; right: 50px; width: 200px; height: auto;
                                background-color: white; border:2px solid grey; z-index:9999; 
                                font-size:11px; font-family: Arial; padding: 8px; box-sizing: border-box;">
                        <h5 style="margin: 0 0 8px 0; font-size: 13px;">Barevná škála teček</h5>
                        <p style="margin: 3px 0; font-weight: bold;">{legend_title}</p>
                        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#00FF00"></i> ≥25% (velmi vysoké)</p>
                        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#32CD32"></i> 20–24% (vysoké)</p>
                        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#228B22"></i> 15–19% (dobré)</p>
                        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#FFD700"></i> 10–14% (střední)</p>
                        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#FF8C00"></i> 5–9% (nízké)</p>
                        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#FF4500"></i> <5% (velmi nízké)</p>
                        <hr style="margin: 5px 0;">
                        <p style="font-size: 10px; color: #666;">
                            🔵 Počet teček = počet hlasů<br>
                            🎨 Barva teček = {legend_type}
                        </p>
                    </div>
                    """
                    dot_map.get_root().html.add_child(folium.Element(color_legend_html))

                # Don't use auto-fit in tabs - the calculated zoom should work
                # Auto-fit causes issues in Streamlit tabs

                # Display the dot density map
                map_data = st_folium(
                    dot_map,
                    width="100%",  # Explicit width
                    height=1000,  # Fixed height for tabs
                    returned_objects=["last_clicked", "last_object_clicked"],
                    key=f"dots_{viz_type}_{selected_party}_{votes_per_dot}_{dot_spacing}_{dot_size}_{use_color_scale}_{base_map_style_main}",
                )

            except Exception as e:
                st.error(f"Chyba při vytváření bodové mapy: {e}")
                st.info("Používám standardní mapu...")
                map_obj = create_folium_map(
                    filtered_geojson,
                    electoral_data,
                    viz_type,
                    selected_party,
                    base_map_style_main,
                )
                map_data = st_folium(
                    map_obj,
                    width="100%",  # Explicit width
                    height=1000,  # Fixed height for tabs
                    returned_objects=["last_clicked", "last_object_clicked"],
                    key=f"fallback_map_{viz_type}_{selected_party}_{base_map_style_main}",
                )
        else:
            st.warning("Pro bodovou mapu nejsou dostupná okrsková data.")
            map_data = None
    else:
        st.subheader("Geografická mapa")
        # Create and display the regular map
        map_obj = create_folium_map(
            filtered_geojson,
            electoral_data,
            viz_type,
            selected_party,
            base_map_style_main,
        )

        # Display the map
        map_data = st_folium(
            map_obj,
            width="100%",  # Explicit width
            height=1000,  # Fixed height for tabs
            returned_objects=["last_clicked", "last_object_clicked"],
            key=f"map_{viz_type}_{selected_party}_{base_map_style_main}",  # Include base map style in key
        )

    # Display information about clicked features
    if map_data and map_data.get("last_object_clicked"):
        st.subheader("Detail okrsku")
        clicked_data = map_data["last_object_clicked"]

        # Extract useful information
        properties = clicked_data.get("properties", {})
        district_code = get_district_code_from_geojson(properties) or "Neznámý"

        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Okrsek:** {district_code}")
            st.write(f"**Kód obce:** {properties.get('OBEC', 'Neznámý')}")
            st.write(f"**Kód okrsku:** {properties.get('KOD', 'Neznámý')}")

        with col2:
            # Try to find electoral data for this okrsek
            okrsek_data = district_data[district_data["district_code"] == district_code]
            if not okrsek_data.empty:
                st.write("**Volební data:**")
                st.metric(
                    "Účast", f"{fmt_pct(okrsek_data['turnout_percentage'].iloc[0], 1)}"
                )
                st.metric(
                    "Registrovaní voliči",
                    f"{fmt_int(okrsek_data['registered_voters'].iloc[0])}",
                )
                st.metric("Platné hlasy", f"{fmt_int(okrsek_data['valid_votes'].iloc[0])}")
            else:
                st.write("*Pro tento okrsek nejsou dostupná data*")

        # Show raw data in expander
        with st.expander("Raw GeoJSON vlastnosti"):
            st.json(properties)

    # Summary statistics
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Okrsky na mapě", len(municipality_features))

    with col2:
        if district_data is not None and isinstance(district_data, pd.DataFrame):
            unique_districts = (
                len(district_data["district_code"].unique())
                if "district_code" in district_data.columns
                else 0
            )
            st.metric("Okrsky s daty", unique_districts)
        else:
            st.metric("Volební data", "Nedostupné")

    with col3:
        # Calculate how many GeoJSON features have matching electoral data
        if district_data is not None and isinstance(district_data, pd.DataFrame):
            available_codes = (
                set(district_data["district_code"].astype(str).unique())
                if "district_code" in district_data.columns
                else set()
            )
            geojson_codes = set(
                get_district_code_from_geojson(f.get("properties", {}))
                for f in municipality_features
            )
            matches = len(available_codes.intersection(geojson_codes))
            st.metric("Shody mapy a dat", matches)
        else:
            st.metric("Shody mapy a dat", "N/A")

    # Instructions
    current_viz = viz_label(viz_type)
    if viz_type == "Party Results" and selected_party:
        current_viz = f"{selected_party}"

    st.info(
        "💡 Klikněte na okrsek v mapě pro detail. "
        f"Aktuálně zobrazuji: **{current_viz}**"
    )


def display_data_explorer(data):
    """Allow users to explore the raw data"""
    st.subheader("Datový průzkumník")

    if not data:
        st.warning("Žádná data nejsou dostupná. Nejprve spusťte analýzu.")
        return

    # Data source selector
    selected_source = st.selectbox(
        "Vyberte zdroj dat:",
        options=list(data.keys()),
        help="Zvolte datovou sadu pro prohlížení.",
    )

    if selected_source:
        dataset = data[selected_source]

        st.write(f"**Typ dat:** {type(dataset).__name__}")

        if isinstance(dataset, pd.DataFrame):
            st.write(f"**Rozměr:** {dataset.shape}")
            st.dataframe(dataset.head(100))

            # Basic statistics for numeric columns
            numeric_cols = dataset.select_dtypes(include=["number"]).columns
            if len(numeric_cols) > 0:
                st.subheader("Statistiky číselných sloupců")
                st.dataframe(dataset[numeric_cols].describe())

        elif isinstance(dataset, dict):
            st.write(f"**Klíče:** {list(dataset.keys())}")

            # Show a preview of the JSON structure
            with st.expander("Raw data (prvních 1000 znaků)"):
                preview = str(dataset)[:1000]
                if len(str(dataset)) > 1000:
                    preview += "..."
                st.text(preview)

        elif isinstance(dataset, list):
            st.write(f"**Délka:** {len(dataset)}")
            if len(dataset) > 0:
                st.write(f"**Typ prvního prvku:** {type(dataset[0]).__name__}")
                with st.expander("Zobrazit první prvek"):
                    st.json(dataset[0] if len(dataset) > 0 else {})


def display_district_analysis(data):
    """Display okrsek-level (polling district) analysis and comparisons"""

    has_candidates = bool(data.get("candidates"))
    has_district_data = "district_data" in data and "district_party_results" in data

    if has_candidates:
        st.subheader("Kandidáti")
        if not has_district_data:
            st.info(
                "📊 **Parlamentní volby**\n\n"
                "Tento obvod má data o kandidátech, ale nemá okrskové členění."
            )

        # Show candidate statistics if available
        if "candidates" in data and data["candidates"]:
            candidates = data["candidates"]
            st.subheader("Statistiky kandidátů")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Počet kandidátů", len(candidates))
            with col2:
                candidates_with_mandate = len(
                    [c for c in candidates if c.get("mandate_won", False)]
                )
                st.metric("Zvolených kandidátů", candidates_with_mandate)
            with col3:
                total_pref_votes = sum(
                    c.get("preferential_votes", 0) for c in candidates
                )
                st.metric("Preferenční hlasy", f"{fmt_int(total_pref_votes)}")

            # Show top candidates by preferential votes
            st.subheader("Top kandidáti podle preferenčních hlasů")
            candidates_sorted = sorted(
                candidates, key=lambda x: x.get("preferential_votes", 0), reverse=True
            )[:20]

            candidates_df = pd.DataFrame(
                [
                    {
                        "Pořadí": i + 1,
                        "Jméno": f"{c.get('first_name', '')} {c.get('surname', '')}",
                        "Strana": c.get("party_name", "Neznámá"),
                        "Preferenční hlasy": c.get("preferential_votes", 0),
                        "Podíl": f"{fmt_pct(c.get('preferential_percentage', 0), 2)}",
                        "Zvolen": "✅" if c.get("mandate_won", False) else "❌",
                    }
                    for i, c in enumerate(candidates_sorted)
                ]
            )

            st.dataframe(
                candidates_df,
                use_container_width=True,
                hide_index=True,
            )
        if not has_district_data:
            return

    if not has_district_data:
        st.warning("Okrsková data nejsou dostupná. Ověřte, že proběhla analýza.")
        return

    district_df = data["district_data"]
    district_party_df = data["district_party_results"]

    # Filter out summary rows
    district_df_filtered = district_df[district_df["district_code"] != "TOTAL"]

    if district_df_filtered.empty or district_party_df.empty:
        st.warning("Okrsková data nejsou k dispozici.")
        return

    # The district_code is already available directly in our data structure
    district_df_filtered = district_df_filtered.copy()
    district_df_filtered["district_code"] = district_df_filtered["district_code"].astype(
        str
    )

    # For party data, we may need to extract district_code from district_id if it exists
    district_party_df = district_party_df.copy()
    if (
        "district_id" in district_party_df.columns
        and "district_code" not in district_party_df.columns
    ):
        district_party_df["district_code"] = (
            district_party_df["district_id"].str.split("-").str[0]
        )
    district_party_df["district_code"] = district_party_df["district_code"].astype(str)

    # Get unique okrseks (use district_code as the unique identifier for polling districts)
    # Each district_code represents a physical polling location/okrsek
    unique_okrseks = district_df_filtered.groupby("district_code").first().reset_index()
    unique_okrseks["okrsek_name"] = unique_okrseks["district_code"].apply(
        lambda x: f"Okrsek {x}"
    )

    # Okrsek detail view
    st.subheader("Detail okrsku")

    polling_stations = data.get("polling_stations", [])
    station_lookup = {}
    if polling_stations:
        station_lookup = {
            str(station.get("station_number")): station
            for station in polling_stations
            if station.get("station_number")
        }

    okrsek_codes = unique_okrseks["district_code"].tolist()

    def _okrsek_sort_key(code):
        return (0, int(code)) if code.isdigit() else (1, code)

    okrsek_codes = sorted(okrsek_codes, key=_okrsek_sort_key)

    def _format_okrsek(code):
        station = station_lookup.get(code)
        if station:
            name = station.get("municipality_name") or station.get(
                "municipality_code"
            )
            if name:
                return f"Okrsek {code} - {name}"
        return f"Okrsek {code}"

    selected_okrsek = st.selectbox(
        "Vyberte okrsek:",
        okrsek_codes,
        format_func=_format_okrsek,
        key="okrsek_detail_select",
    )

    okrsek_row = district_df_filtered[
        district_df_filtered["district_code"] == selected_okrsek
    ]
    okrsek_party_rows = district_party_df[
        district_party_df["district_code"] == selected_okrsek
    ].copy()

    if not okrsek_party_rows.empty:
        okrsek_party_rows["votes"] = pd.to_numeric(
            okrsek_party_rows["votes"], errors="coerce"
        ).fillna(0)
        okrsek_party_rows = okrsek_party_rows.sort_values("votes", ascending=False)
        if "percentage" not in okrsek_party_rows.columns:
            total_votes = okrsek_party_rows["votes"].sum()
            okrsek_party_rows["percentage"] = (
                okrsek_party_rows["votes"] / total_votes * 100
                if total_votes > 0
                else 0
            )

    col1, col2, col3, col4 = st.columns(4)

    if not okrsek_row.empty:
        row = okrsek_row.iloc[0]
        col1.metric("Registrovaní voliči", f"{fmt_int(row.get('registered_voters', 0))}")
        col2.metric("Odevzdané obálky", f"{fmt_int(row.get('returned_ballots', 0))}")
        col3.metric("Platné hlasy", f"{fmt_int(row.get('valid_votes', 0))}")
        col4.metric("Účast", f"{fmt_pct(row.get('turnout_percentage', 0), 1)}")
    else:
        col1.metric("Registrovaní voliči", "N/A")
        col2.metric("Odevzdané obálky", "N/A")
        col3.metric("Platné hlasy", "N/A")
        col4.metric("Účast", "N/A")

    if station_lookup.get(selected_okrsek):
        station = station_lookup[selected_okrsek]
        st.write(
            f"**Obec:** {station.get('municipality_name', 'Neznámá')} "
            f"({station.get('municipality_code', 'Neznámý')})"
        )
        st.write(f"**Okres:** {station.get('district_code', 'Neznámý')}")

    if not okrsek_party_rows.empty:
        top_parties = okrsek_party_rows.head(15)
        fig_okrsek = px.bar(
            top_parties,
            x="party_name",
            y="votes",
            title=f"Okrsek {selected_okrsek} – výsledky stran",
            labels={"party_name": "Strana", "votes": "Hlasy"},
            color="votes",
            color_continuous_scale="blues",
        )
        fig_okrsek.update_xaxes(tickangle=45)
        st.plotly_chart(fig_okrsek, use_container_width=True)

        with st.expander("📋 Výsledky stran v okrsku"):
            display_rows = okrsek_party_rows[
                ["party_name", "votes", "percentage"]
            ].copy()
            display_rows["votes"] = display_rows["votes"].apply(lambda x: f"{fmt_int(int(x))}")
            display_rows["percentage"] = display_rows["percentage"].apply(
                lambda x: f"{fmt_pct(x, 2)}"
            )
            display_rows.columns = ["Strana", "Hlasy", "Podíl"]
            st.dataframe(display_rows, use_container_width=True)
    else:
        st.info("Pro tento okrsek nejsou výsledky stran dostupné.")

    # District turnout comparison
    st.subheader("Účast podle okrsku")

    if "turnout_percentage" in unique_okrseks.columns:
        # Sort by turnout
        unique_okrseks = unique_okrseks.sort_values(
            "turnout_percentage", ascending=False
        )

        col1, col2 = st.columns(2)

        with col1:
            st.metric(
                "Nejvyšší účast",
                f"Okrsek {unique_okrseks.iloc[0]['district_code']}: {fmt_pct(unique_okrseks.iloc[0]['turnout_percentage'], 1)}",
            )

        with col2:
            st.metric(
                "Nejnižší účast",
                f"Okrsek {unique_okrseks.iloc[-1]['district_code']}: {fmt_pct(unique_okrseks.iloc[-1]['turnout_percentage'], 1)}",
            )

        # Turnout distribution chart
        top_20_okrseks = unique_okrseks.head(20)
        fig_turnout = px.bar(
            top_20_okrseks,
            x="okrsek_name",
            y="turnout_percentage",
            title="Top 20 okrsků podle účasti (%)",
            labels={"turnout_percentage": "Účast (%)", "okrsek_name": "Okrsek"},
            color="turnout_percentage",
            color_continuous_scale="viridis",
        )
        fig_turnout.update_xaxes(tickangle=45)
        st.plotly_chart(fig_turnout, use_container_width=True)

    # Party performance by okrsek
    st.subheader("Výkon strany podle okrsku")

    # Available parties, strongest first, so the selectors start with the main ones
    party_totals = (
        district_party_df.groupby("party_name")["votes"].sum().sort_values(ascending=False)
    )
    available_parties = [p for p in party_totals.index if len(str(p).strip()) > 0]

    if len(available_parties) > 0:
        # Party selector
        selected_party = st.selectbox(
            "Vyberte stranu pro analýzu okrsků:",
            available_parties,
            index=0,
        )

        if selected_party:
            # Get unique okrsek data for the selected party (aggregate OBEC and MCMO if both exist)
            party_data = district_party_df[
                district_party_df["party_name"] == selected_party
            ].copy()

            if not party_data.empty:
                # Group by district_code to get okrsek-level data
                okrsek_party_data = (
                    party_data.groupby("district_code")
                    .agg({"votes": "sum", "total_district_votes": "sum"})
                    .reset_index()
                )

                # Calculate percentage for each okrsek
                okrsek_party_data["percentage"] = (
                    okrsek_party_data["votes"]
                    / okrsek_party_data["total_district_votes"]
                    * 100
                )
                okrsek_party_data["okrsek_name"] = okrsek_party_data[
                    "district_code"
                ].apply(lambda x: f"Okrsek {x}")

                # Sort by percentage
                okrsek_party_data = okrsek_party_data.sort_values(
                    "percentage", ascending=False
                )

                # Show top performing okrseks for this party
                col1, col2 = st.columns(2)

                with col1:
                    st.metric(
                        f"Nejlepší okrsek pro {selected_party}",
                        f"Okrsek {okrsek_party_data.iloc[0]['district_code']}: {fmt_pct(okrsek_party_data.iloc[0]['percentage'], 1)}",
                    )

                with col2:
                    st.metric(
                        f"Nejslabší okrsek pro {selected_party}",
                        f"Okrsek {okrsek_party_data.iloc[-1]['district_code']}: {fmt_pct(okrsek_party_data.iloc[-1]['percentage'], 1)}",
                    )

                # Chart showing party performance across okrseks
                top_15_party = okrsek_party_data.head(15)
                fig_party = px.bar(
                    top_15_party,
                    x="okrsek_name",
                    y="percentage",
                    title=f"{selected_party} – výkon podle okrsku (%)",
                    labels={"percentage": "Podíl hlasů (%)", "okrsek_name": "Okrsek"},
                    color="percentage",
                    color_continuous_scale="blues",
                )
                fig_party.update_xaxes(tickangle=45)
                st.plotly_chart(fig_party, use_container_width=True)

                # Show detailed table
                with st.expander("📋 Podrobná tabulka"):
                    display_party_data = okrsek_party_data[
                        ["okrsek_name", "votes", "percentage", "total_district_votes"]
                    ].copy()
                    display_party_data["votes"] = display_party_data["votes"].apply(
                        lambda x: f"{fmt_int(x)}"
                    )
                    display_party_data["percentage"] = display_party_data[
                        "percentage"
                    ].apply(lambda x: f"{fmt_pct(x, 2)}")
                    display_party_data["total_district_votes"] = display_party_data[
                        "total_district_votes"
                    ].apply(lambda x: f"{fmt_int(x)}")
                    display_party_data.columns = [
                        "Okrsek",
                        "Hlasy",
                        "Podíl",
                        "Hlasy celkem",
                    ]
                    st.dataframe(display_party_data, use_container_width=True)

    # Okrsek comparison
    st.subheader("Porovnání okrsků")

    if len(available_parties) >= 2:
        # Multi-party comparison
        selected_parties = st.multiselect(
            "Vyberte strany k porovnání okrsků:",
            available_parties,
            default=available_parties[:3]
            if len(available_parties) >= 3
            else available_parties[:2],
        )

        if len(selected_parties) >= 2:
            # Create comparison data
            comparison_data = []

            for party in selected_parties:
                party_districts = district_party_df[
                    district_party_df["party_name"] == party
                ].copy()

                if not party_districts.empty:
                    # Group by okrsek (district_code)
                    okrsek_data = (
                        party_districts.groupby("district_code")
                        .agg({"votes": "sum", "total_district_votes": "sum"})
                        .reset_index()
                    )

                    okrsek_data["percentage"] = (
                        okrsek_data["votes"] / okrsek_data["total_district_votes"] * 100
                    )
                    okrsek_data["okrsek_name"] = okrsek_data["district_code"].apply(
                        lambda x: f"Okrsek {x}"
                    )

                    # Get top 10 okrseks for this party
                    top_okrseks = okrsek_data.nlargest(10, "percentage")
                    for _, row in top_okrseks.iterrows():
                        comparison_data.append(
                            {
                                "okrsek_name": row["okrsek_name"],
                                "party_name": party,
                                "percentage": row["percentage"],
                            }
                        )

            if comparison_data:
                comparison_df = pd.DataFrame(comparison_data)

                # Create grouped bar chart
                fig_comparison = px.bar(
                    comparison_df,
                    x="okrsek_name",
                    y="percentage",
                    color="party_name",
                    title="Porovnání výkonu stran v top okrscích",
                    labels={
                        "percentage": "Podíl hlasů (%)",
                        "okrsek_name": "Okrsek",
                        "party_name": "Strana",
                    },
                    barmode="group",
                )
                fig_comparison.update_xaxes(tickangle=45)
                st.plotly_chart(fig_comparison, use_container_width=True)

    # Summary statistics
    if not unique_okrseks.empty:
        st.subheader("Souhrn okrsků")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Počet okrsků", len(unique_okrseks))

        with col2:
            avg_turnout = unique_okrseks["turnout_percentage"].mean()
            st.metric("Průměrná účast", f"{fmt_pct(avg_turnout, 1)}")

        with col3:
            total_voters = unique_okrseks["registered_voters"].sum()
            st.metric("Registrovaní voliči", f"{fmt_int(total_voters)}")

        with col4:
            total_valid_votes = unique_okrseks["valid_votes"].sum()
            st.metric("Platné hlasy", f"{fmt_int(total_valid_votes)}")

        # Additional info about data structure
        st.info(
            f"📍 Tyto volby mají {len(unique_okrseks)} okrsků. "
            "Každý okrsek představuje konkrétní volební místnost."
        )


def create_cartogram(
    geojson_data,
    electoral_data,
    viz_type="Turnout",
    selected_party=None,
    base_size=0.002,
    collision_avoidance=False,
):
    """Create a force-directed cartogram with areas proportional to vote counts and optional collision avoidance"""
    if not geojson_data or "features" not in geojson_data:
        return None

    # Use the already-filtered geojson_data (filtered by main function for the selected municipality)
    municipality_features = geojson_data.get("features", [])

    if not municipality_features:
        return None

    # Convert to GeoDataFrame
    gdf = gpd.GeoDataFrame.from_features(municipality_features)
    # Handle both 2022 (CISLO) and 2025 (cislo) GeoJSON formats
    if "cislo" in gdf.columns:
        gdf["district_code"] = gdf["cislo"].astype(str)
    elif "CISLO" in gdf.columns:
        gdf["district_code"] = gdf["CISLO"].astype(str)

    # Get vote counts and display values
    district_data = electoral_data.get("district_data") if electoral_data else None
    party_data = (
        electoral_data.get("district_party_results") if electoral_data else None
    )

    vote_counts = {}
    display_values = {}

    if (
        isinstance(district_data, pd.DataFrame)
        and "district_code" in district_data.columns
    ):
        for _, row in district_data.iterrows():
            district_code = str(row.get("district_code", ""))

            # Always use valid_votes for scaling
            if "valid_votes" in row and pd.notna(row.get("valid_votes", 0)):
                vote_counts[district_code] = int(row.get("valid_votes", 0))

            # Get display values for color coding
            if viz_type == "Turnout" and "turnout_percentage" in row:
                value = row.get("turnout_percentage", 0)
                if pd.notna(value):
                    display_values[district_code] = float(value)
            elif viz_type == "Estimated Voters" and "registered_voters" in row:
                value = row.get("registered_voters", 0)
                if pd.notna(value):
                    display_values[district_code] = int(value)
            elif viz_type == "Valid Votes" and "valid_votes" in row:
                value = row.get("valid_votes", 0)
                if pd.notna(value):
                    display_values[district_code] = int(value)

    # Handle party results
    if (
        viz_type == "Party Results"
        and selected_party
        and isinstance(party_data, pd.DataFrame)
    ):
        party_subset = party_data[party_data["party_name"] == selected_party].copy()
        if not party_subset.empty:
            party_subset["district_code"] = (
                party_subset["district_id"].str.split("-").str[0]
            )

            for district_code, group in party_subset.groupby("district_code"):
                total_district_votes = group["total_district_votes"].sum()
                party_votes = group["votes"].sum()

                # For area scaling: use actual party votes (not total district votes)
                if party_votes > 0:
                    vote_counts[str(district_code)] = party_votes

                # For color display: use party percentage
                if total_district_votes > 0:
                    percentage = (party_votes / total_district_votes) * 100
                    display_values[str(district_code)] = percentage

    if not vote_counts:
        return gdf

    # Create cartogram with normalized scaling and optional collision avoidance
    cartogram_gdf = gdf.copy()

    # Calculate normalized scaling between min and max vote counts
    min_votes = min(vote_counts.values())
    max_votes = max(vote_counts.values())

    # Set radius range for scaling
    base_radius = base_size
    max_radius = base_radius * 4  # Maximum size for highest vote count

    # Store centroid positions and radii for collision detection
    districts = []

    for idx, row in cartogram_gdf.iterrows():
        district_code = row["district_code"]
        original_centroid = row.geometry.centroid

        if district_code in vote_counts:
            votes = vote_counts[district_code]

            # Normalized scaling: 0 to 1 based on vote range
            if max_votes > min_votes:
                scale_factor = (votes - min_votes) / (max_votes - min_votes)
            else:
                scale_factor = 0  # All districts have same vote count

            # Scale radius between base_radius and max_radius
            radius = base_radius + (max_radius - base_radius) * scale_factor

            # Ensure minimum radius for visibility
            radius = max(radius, base_radius * 0.7)

            districts.append(
                {
                    "idx": idx,
                    "district_code": district_code,
                    "x": original_centroid.x,
                    "y": original_centroid.y,
                    "radius": radius,
                    "votes": votes,
                    "display_value": display_values.get(district_code, 0),
                    "original_x": original_centroid.x,
                    "original_y": original_centroid.y,
                }
            )
        else:
            districts.append(
                {
                    "idx": idx,
                    "district_code": district_code,
                    "x": original_centroid.x,
                    "y": original_centroid.y,
                    "radius": base_radius * 0.7,
                    "votes": 0,
                    "display_value": 0,
                    "original_x": original_centroid.x,
                    "original_y": original_centroid.y,
                }
            )

    # Only apply collision avoidance if requested
    if collision_avoidance:
        # Force-directed algorithm to separate overlapping circles with gentle forces
        def apply_forces(districts, iterations=100, force_strength=2.0, damping=0.9):
            """Apply robust repulsive forces to eliminate overlaps while staying reasonably close to original positions"""
            for iteration in range(iterations):
                forces = {d["idx"]: {"fx": 0, "fy": 0} for d in districts}
                overlaps_detected = 0
                max_overlap = 0

                # Calculate repulsive forces for all overlapping pairs
                for i, d1 in enumerate(districts):
                    for j, d2 in enumerate(districts[i + 1 :], i + 1):
                        dx = d2["x"] - d1["x"]
                        dy = d2["y"] - d1["y"]
                        distance = np.sqrt(dx * dx + dy * dy)

                        # Required minimum distance with small buffer
                        min_distance = (d1["radius"] + d2["radius"]) * 1.02

                        if distance < min_distance:
                            overlaps_detected += 1
                            overlap = min_distance - distance
                            max_overlap = max(max_overlap, overlap)

                            # Handle case where circles are exactly on top of each other
                            if distance < 0.00001:
                                # Push them apart in random directions
                                angle = np.random.random() * 2 * np.pi
                                dx = np.cos(angle) * min_distance
                                dy = np.sin(angle) * min_distance
                                distance = min_distance

                            # Calculate repulsive force - stronger for larger overlaps
                            force_magnitude = overlap * force_strength * 2

                            # Normalize direction and apply force
                            fx = (dx / distance) * force_magnitude
                            fy = (dy / distance) * force_magnitude

                            # Weight by circle size - smaller circles move more
                            total_radius = d1["radius"] + d2["radius"]
                            weight1 = (
                                d2["radius"] / total_radius
                            )  # d1 moves based on d2's size
                            weight2 = (
                                d1["radius"] / total_radius
                            )  # d2 moves based on d1's size

                            forces[d1["idx"]]["fx"] -= fx * weight1
                            forces[d1["idx"]]["fy"] -= fy * weight1
                            forces[d2["idx"]]["fx"] += fx * weight2
                            forces[d2["idx"]]["fy"] += fy * weight2

                # Moderate attraction force back to original position
                for d in districts:
                    attraction_force = 0.1  # Balanced attraction
                    forces[d["idx"]]["fx"] += (
                        d["original_x"] - d["x"]
                    ) * attraction_force
                    forces[d["idx"]]["fy"] += (
                        d["original_y"] - d["y"]
                    ) * attraction_force

                # Update positions with damping
                for d in districts:
                    d["x"] += forces[d["idx"]]["fx"] * damping
                    d["y"] += forces[d["idx"]]["fy"] * damping

                # Continue until no overlaps or very small overlap remains
                if overlaps_detected == 0 or max_overlap < 0.00001:
                    break

            # Final pass: if any overlaps remain, use direct separation
            if overlaps_detected > 0:
                for i, d1 in enumerate(districts):
                    for j, d2 in enumerate(districts[i + 1 :], i + 1):
                        dx = d2["x"] - d1["x"]
                        dy = d2["y"] - d1["y"]
                        distance = np.sqrt(dx * dx + dy * dy)
                        min_distance = (d1["radius"] + d2["radius"]) * 1.02

                        if distance < min_distance:
                            # Direct separation - move apart to minimum distance
                            if distance < 0.00001:
                                angle = np.random.random() * 2 * np.pi
                                dx = np.cos(angle) * min_distance
                                dy = np.sin(angle) * min_distance
                                distance = min_distance

                            # Calculate how much to move each circle
                            separation_needed = min_distance - distance
                            move_ratio = separation_needed / (2 * distance)

                            # Move both circles apart equally
                            d1["x"] -= dx * move_ratio
                            d1["y"] -= dy * move_ratio
                            d2["x"] += dx * move_ratio
                            d2["y"] += dy * move_ratio

        # Apply force-directed positioning only if collision avoidance is enabled
        apply_forces(districts)

    # Create new geometries based on final positions
    for d in districts:
        idx = d["idx"]
        new_center = Point(d["x"], d["y"])

        # Create a circular geometry with proportional area
        circle_geom = new_center.buffer(d["radius"])

        cartogram_gdf.loc[idx, "geometry"] = circle_geom
        cartogram_gdf.loc[idx, "vote_count"] = d["votes"]
        cartogram_gdf.loc[idx, "display_value"] = d["display_value"]
        cartogram_gdf.loc[idx, "radius"] = d["radius"]
        cartogram_gdf.loc[idx, "moved_distance"] = np.sqrt(
            (d["x"] - d["original_x"]) ** 2 + (d["y"] - d["original_y"]) ** 2
        )

    return cartogram_gdf


def create_cartogram_map(
    cartogram_gdf, viz_type="Turnout", selected_party=None, electoral_data=None
):
    """Create a Folium map from cartogram GeoDataFrame with circular districts"""
    if cartogram_gdf is None or cartogram_gdf.empty:
        return None

    # Calculate map center and appropriate zoom
    bounds = cartogram_gdf.total_bounds
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2

    # Calculate zoom based on geographic extent
    lat_range = bounds[3] - bounds[1]
    lon_range = bounds[2] - bounds[0]
    max_range = max(lat_range, lon_range)

    # Set zoom based on geographic extent
    if max_range < 0.01:  # Very small area
        zoom_start = 15
    elif max_range < 0.05:  # Small area
        zoom_start = 13
    elif max_range < 0.1:  # Medium area
        zoom_start = 12
    elif max_range < 0.2:  # Large area
        zoom_start = 11
    else:  # Very large area
        zoom_start = 10

    m = create_map_with_tiles([center_lat, center_lon], zoom_start, "OpenStreetMap")

    # Color mapping function (uses display_value, not vote_count)
    def get_color_for_value(value, viz_type):
        """Get color based on value and visualization type"""
        if viz_type == "Turnout":
            if value >= 60:
                return "#006400"
            elif value >= 50:
                return "#228B22"
            elif value >= 40:
                return "#FFD700"
            elif value >= 30:
                return "#FFA500"
            else:
                return "#FF6347"
        elif viz_type == "Estimated Voters":
            if value >= 800:
                return "#006400"
            elif value >= 600:
                return "#228B22"
            elif value >= 400:
                return "#FFD700"
            elif value >= 200:
                return "#FFA500"
            else:
                return "#FF6347"
        elif viz_type == "Valid Votes":
            if value >= 1000:
                return "#006400"
            elif value >= 800:
                return "#228B22"
            elif value >= 600:
                return "#FFD700"
            elif value >= 400:
                return "#FFA500"
            else:
                return "#FF6347"
        elif viz_type == "Party Results":
            if value >= 25:
                return "#006400"
            elif value >= 20:
                return "#228B22"
            elif value >= 15:
                return "#32CD32"
            elif value >= 10:
                return "#FFD700"
            elif value >= 5:
                return "#87CEEB"
            else:
                return "#4169E1"
        return "#CCCCCC"

    # Add each district to the map
    for idx, row in cartogram_gdf.iterrows():
        district_code = get_district_code_from_geojson(row) or "Neznámý"
        vote_count = row.get("vote_count", 0)
        display_value = row.get("display_value", 0)
        radius = row.get("radius", 0)
        moved_distance = row.get("moved_distance", 0)

        # Calculate area for display
        area_km2 = np.pi * (radius * 111) ** 2  # Rough conversion to km²

        # Create popup content
        popup_html = f"""
        <div style="font-family: Arial; width: 270px;">
            <h4 style="color: #1f77b4;">Okrsek {district_code}</h4>
            <hr>
            <p><strong>Počet hlasů:</strong> {fmt_int(vote_count)} hlasů</p>
            <p><strong>Plocha kruhu:</strong> {area_km2:.2f} km² (proporčně)</p>
            <p><strong>Posun:</strong> {moved_distance * 111:.0f} m od původní polohy</p>
            <hr>
        """

        if viz_type == "Turnout":
            popup_html += f"<p><strong>Účast:</strong> {fmt_pct(display_value, 1)}</p>"
        elif viz_type == "Estimated Voters":
            popup_html += (
                f"<p><strong>Registrovaní voliči:</strong> {display_value:,.0f}</p>"
            )
        elif viz_type == "Valid Votes" or viz_type == "Valid Votes (dots)":
            popup_html += f"<p><strong>Platné hlasy:</strong> {display_value:,.0f}</p>"
        elif viz_type == "Party Results" and selected_party:
            popup_html += (
                f"<p><strong>{selected_party}:</strong> {fmt_pct(display_value, 1)}</p>"
            )

        popup_html += """
            <hr>
            <p style="font-size: 10px; color: #666;">
                ⭕ Velikost kruhu = počet hlasů<br>
                🎨 Barva kruhu = hodnota metriky<br>
                📍 Pozice posunuta kvůli překryvu
            </p>
        </div>
        """

        # Style the circle (color based on display_value)
        color = get_color_for_value(display_value, viz_type)

        # Create circle marker with informative tooltip
        tooltip_text = f"Okrsek {district_code}: {fmt_int(vote_count)} hlasů"

        # Add display value to tooltip based on visualization type
        if viz_type == "Turnout":
            tooltip_text = (
                f"Okrsek {district_code}: {fmt_pct(display_value, 1)} účast | {fmt_int(vote_count)} hlasů"
            )
        elif viz_type == "Estimated Voters":
            tooltip_text = (
                f"Okrsek {district_code}: {fmt_int(int(display_value))} voličů | {fmt_int(vote_count)} hlasů"
            )
        elif viz_type == "Valid Votes":
            tooltip_text = (
                f"Okrsek {district_code}: {fmt_int(int(display_value))} platných hlasů"
            )
        elif viz_type == "Party Results" and selected_party:
            tooltip_text = (
                f"Okrsek {district_code}: {fmt_pct(display_value, 1)} {selected_party} | {fmt_int(vote_count)} hlasů"
            )

        # Add voter estimate to tooltip if we have electoral data
        if electoral_data and vote_count > 0:
            # Calculate voter estimate (votes ÷ seats available)
            num_seats = get_seat_count(electoral_data)

            if num_seats > 0:
                voter_estimate = round(vote_count / num_seats)
                # Add voter estimate to tooltip based on visualization type
                if viz_type == "Party Results":
                    tooltip_text += f" | ~{fmt_int(voter_estimate)} voličů"
                elif viz_type not in [
                    "Estimated Voters"
                ]:  # Don't duplicate for estimated voters viz
                    tooltip_text += f" | ~{fmt_int(voter_estimate)} voličů"

        folium.Circle(
            location=[row.geometry.centroid.y, row.geometry.centroid.x],
            radius=radius * 111000,  # Convert degrees to meters approximately
            popup=folium.Popup(popup_html, max_width=320),
            tooltip=folium.Tooltip(tooltip_text),
            color="black",
            weight=2,
            fillColor=color,
            fillOpacity=0.7,
        ).add_to(m)

        # Add district label with key metric - show only the main figure
        label_text = ""

        # Show only key metric in label based on visualization type
        if viz_type == "Turnout":
            label_text = f"{fmt_pct(display_value, 0)}"
        elif viz_type == "Estimated Voters":
            if display_value >= 1000:
                label_text = f"{display_value / 1000:.1f}k"
            else:
                label_text = f"{int(display_value)}"
        elif viz_type == "Valid Votes":
            if display_value >= 1000:
                label_text = f"{int(display_value) / 1000:.1f}k"
            else:
                label_text = f"{int(display_value)}"
        elif viz_type == "Party Results" and selected_party:
            label_text = f"{fmt_pct(display_value, 0)}"

        if label_text:  # Only add label if we have data
            folium.Marker(
                location=[row.geometry.centroid.y, row.geometry.centroid.x],
                icon=folium.DivIcon(
                    html=f'<div style="font-size: 18px; color: white; font-weight: bold; text-shadow: 2px 2px 2px black; text-align: center; line-height: 1.1;">{label_text}</div>',
                    icon_size=(60, 40),
                    icon_anchor=(30, 20),
                ),
            ).add_to(m)

    # Add enhanced cartogram legend
    legend_html = f"""
    <div style="position: fixed; 
                bottom: 50px; left: 50px; width: 220px; height: auto; min-height: 160px;
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:11px; font-family: Arial; padding: 8px; box-sizing: border-box;">
        <h5 style="margin: 0 0 8px 0; font-size: 13px;">Kartogram</h5>
        <p style="margin: 3px 0; font-style: italic; font-weight: bold; font-size: 10px;">
            ⭕ <strong>Velikost kruhu</strong> = počet hlasů (proporcionálně)<br>
            🎨 <strong>Barva kruhu</strong> = {viz_label(viz_type)}<br>
            📍 <strong>Pozice</strong> = odsun kvůli překryvu
        </p>
        <hr style="margin: 5px 0;">
    """

    # Add color legend
    if viz_type == "Turnout":
        legend_html += """
        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#006400"></i> ≥60% účast</p>
        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#228B22"></i> 50–59%</p>
        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#FFD700"></i> 40–49%</p>
        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#FFA500"></i> 30–39%</p>
        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#FF6347"></i> <30% účast</p>
        """
    elif viz_type == "Estimated Voters":
        legend_html += """
        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#006400"></i> ≥800 voličů</p>
        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#228B22"></i> 600–799</p>
        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#FFD700"></i> 400–599</p>
        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#FFA500"></i> 200–399 (nižší)</p>
        <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#FF6347"></i> <200 (nízké)</p>
        """
    elif viz_type == "Valid Votes":
        legend_html += """
        <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#2E8B57"></i> ≥1000 (vysoké)</p>
        <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#90EE90"></i> 800–999 (středně vysoké)</p>
        <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#FFD700"></i> 600–799 (střední)</p>
        <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#FFA500"></i> 400–599 (nižší)</p>
        <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#FF6347"></i> <400 (nízké)</p>
        """
    elif viz_type == "Party Results":
        legend_html += f"""
        <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#006400"></i> ≥25% (velmi silné)</p>
        <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#228B22"></i> 20–24% (silné)</p>
        <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#32CD32"></i> 15–19% (dobré)</p>
        <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#FFD700"></i> 10–14% (střední)</p>
        <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#87CEEB"></i> 5–9% (slabé)</p>
        <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#4169E1"></i> <5% (velmi slabé)</p>
        """

    legend_html += "</div>"

    m.get_root().html.add_child(folium.Element(legend_html))

    # Don't use fit_bounds in tabs - the calculated zoom should work
    # Auto-fit causes issues in Streamlit tabs

    return m


def get_geographic_municipality_code(electoral_code):
    """
    Map electoral municipality codes to geographic municipality codes.
    This is needed because the electoral data uses different codes than the GeoJSON data.
    """
    # Known mappings between electoral and geographic municipality codes
    electoral_to_geographic = {
        "500143": "554782",  # Praha 5
        # Add more mappings as needed
    }

    return electoral_to_geographic.get(electoral_code, electoral_code)


def icon_fill_layer(
    districts_gdf: gpd.GeoDataFrame,
    vote_series,  # pd.Series indexed by district_code, holding vote counts
    k_votes_per_dot=100,  # granularity
    spacing_m=70,  # waffle spacing in metres (≈ dot diameter)
    dot_radius_px=2,
    dot_color="#de425b",
    seed=42,
    color_scale_data=None,  # pd.Series indexed by district_code, holding percentages for color scaling
    use_color_scale=False,  # Whether to use color scaling instead of single color
):
    """
    Returns a folium.FeatureGroup with dot-fills for every district.
    districts_gdf must contain columns: ['district_code', 'geometry'] in EPSG:4326.

    If use_color_scale=True and color_scale_data is provided, dots will be colored
    based on vote share percentages (red=low, green=high).
    """

    def get_color_from_percentage(percentage):
        """Convert percentage to color scale: red (low) to green (high)"""
        if percentage >= 25:
            return "#00FF00"  # Bright lime green (very high) - most attention-grabbing
        elif percentage >= 20:
            return "#32CD32"  # Lime green (high) - bright and noticeable
        elif percentage >= 15:
            return "#228B22"  # Forest green (good) - solid green
        elif percentage >= 10:
            return "#FFD700"  # Gold (moderate)
        elif percentage >= 5:
            return "#FF8C00"  # Dark orange (low)
        else:
            return "#FF4500"  # Red orange (very low)

    rng = np.random.default_rng(seed)

    # Project to a metric CRS so 'spacing_m' means metres.
    gdf_m = districts_gdf.to_crs(3857)  # Web-Mercator metres

    features = []

    for _, row in gdf_m.iterrows():
        code = str(row["district_code"])
        votes = int(vote_series.get(code, 0))
        if votes <= 0:
            continue

        n_dots = max(1, votes // k_votes_per_dot)
        poly = row.geometry

        if poly.is_empty or not poly.is_valid:
            continue

        xmin, ymin, xmax, ymax = poly.bounds

        # build waffle grid
        xs = np.arange(xmin, xmax, spacing_m)
        ys = np.arange(ymin, ymax, spacing_m)
        pts = [Point(x, y) for x, y in product(xs, ys) if Point(x, y).within(poly)]

        if not pts:
            continue

        rng.shuffle(pts)  # blue-noise
        pts = pts[:n_dots]

        # back to lat-lon
        pts_ll = gpd.GeoSeries(pts, crs=3857).to_crs(4326)

        # Determine dot color
        if use_color_scale and color_scale_data is not None:
            percentage = color_scale_data.get(code, 0)
            dot_color_final = get_color_from_percentage(percentage)
            tooltip_suffix = f" | {fmt_pct(percentage, 1)} podíl hlasů"
        else:
            dot_color_final = dot_color
            tooltip_suffix = ""

        for p in pts_ll:
            marker = folium.CircleMarker(
                location=[p.y, p.x],
                radius=dot_radius_px,
                color=dot_color_final,
                fill=True,
                fill_opacity=0.9,
                stroke=False,
                tooltip=(
                    f"Okrsek {code}: {fmt_int(votes)} hlasů "
                    f"(1 tečka = {k_votes_per_dot} hlasů){tooltip_suffix}"
                ),
            )
            features.append(marker)

    # wrap in a feature-group so the layer can be toggled
    fg = folium.FeatureGroup(
        name=f"Bodová vrstva (1 tečka = {k_votes_per_dot} hlasů)"
    )
    for m in features:
        m.add_to(fg)

    return fg


def prepare_sankey_flows(
    flows_df: pd.DataFrame,
    include_outside_bounds: bool,
    include_same_list: bool,
    use_family_labels: bool,
    min_flow_share: float,
    max_flows: int,
) -> tuple[pd.DataFrame, float]:
    df = flows_df.copy()
    required_cols = {"source_party_name", "target_party_name", "weighted_flow_share"}
    if not required_cols.issubset(df.columns):
        return pd.DataFrame(), 0.0

    if not include_outside_bounds and "outside_bounds" in df.columns:
        df = df[df["outside_bounds"] == False]

    if not include_same_list and "same_list_number" in df.columns:
        df = df[df["same_list_number"] == False]

    has_families = "source_family" in df.columns and "target_family" in df.columns
    if use_family_labels and has_families:
        df["source_label_raw"] = df.apply(
            lambda r: r["source_family"]
            if r["source_family"]
            else r["source_party_name"],
            axis=1,
        )
        df["target_label_raw"] = df.apply(
            lambda r: r["target_family"]
            if r["target_family"]
            else r["target_party_name"],
            axis=1,
        )
    else:
        df["source_label_raw"] = df["source_party_name"]
        df["target_label_raw"] = df["target_party_name"]

    df["source_label"] = "MAGISTRÁT: " + df["source_label_raw"].fillna("Neznámé")
    df["target_label"] = "MČ: " + df["target_label_raw"].fillna("Neznámé")

    df = (
        df.groupby(["source_label", "target_label"], as_index=False)[
            "weighted_flow_share"
        ]
        .sum()
        .sort_values("weighted_flow_share", ascending=False)
    )

    if min_flow_share > 0:
        df = df[df["weighted_flow_share"] >= min_flow_share]

    if max_flows > 0:
        df = df.head(max_flows)

    total_share = df["weighted_flow_share"].sum()
    return df, total_share


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    hex_color = hex_color.strip()
    if hex_color.lower().startswith("rgb"):
        nums = re.findall(r"[\d.]+", hex_color)
        if len(nums) >= 3:
            r, g, b = [int(float(n)) for n in nums[:3]]
            return f"rgba({r},{g},{b},{alpha})"
        return hex_color
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join([c * 2 for c in hex_color])
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _format_sankey_label(label: str) -> str:
    if label.startswith("MAGISTRÁT: "):
        return label.replace("MAGISTRÁT: ", "")
    if label.startswith("MČ: "):
        return label.replace("MČ: ", "")
    return label


def _format_role_label(label: str) -> str:
    if label.startswith("MAGISTRÁT: "):
        return label.replace("MAGISTRÁT: ", "Magistrát: ")
    if label.startswith("MČ: "):
        return label.replace("MČ: ", "MČ: ")
    return label


def build_sankey_figure(flow_df: pd.DataFrame) -> go.Figure:
    raw_labels = pd.unique(
        flow_df["source_label"].tolist() + flow_df["target_label"].tolist()
    ).tolist()
    label_index = {label: idx for idx, label in enumerate(raw_labels)}

    sources = flow_df["source_label"].map(label_index).tolist()
    targets = flow_df["target_label"].map(label_index).tolist()
    values = (flow_df["weighted_flow_share"] * 100).tolist()
    link_customdata = [
        [
            _format_role_label(src),
            _format_role_label(tgt),
        ]
        for src, tgt in zip(flow_df["source_label"], flow_df["target_label"])
    ]

    left_palette = px.colors.qualitative.Set3
    right_palette = px.colors.qualitative.Bold

    def pick_color(label: str) -> str:
        palette = left_palette if label.startswith("MAGISTRÁT:") else right_palette
        idx = sum(ord(ch) for ch in label) % len(palette)
        return palette[idx]

    node_colors = [pick_color(label) for label in raw_labels]
    link_colors = [_hex_to_rgba(node_colors[idx], 0.35) for idx in sources]
    display_labels = [_format_sankey_label(label) for label in raw_labels]

    fig = go.Figure(
        data=[
            go.Sankey(
                arrangement="snap",
                node=dict(
                    label=display_labels,
                    pad=16,
                    thickness=16,
                    color=node_colors,
                    line=dict(color="#1f2d3d", width=0.6),
                ),
                link=dict(
                    source=sources,
                    target=targets,
                    value=values,
                    color=link_colors,
                    customdata=link_customdata,
                    hovertemplate="%{customdata[0]} → %{customdata[1]}"
                    "<br>%{value:.2f}% magistrátních hlasů<extra></extra>",
                ),
            )
        ]
    )

    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        height=700,
        font=dict(
            size=13,
            family="IBM Plex Sans, Source Sans Pro, sans-serif",
            color="#1f2d3d",
        ),
    )
    return fig


def display_flow_sankey(selected_election_id: str, selected_zastupitelstvo_code: str):
    st.caption(
        "Modelové přelivy Magistrát → MČ (Goodman EI). "
        "Hodnoty = podíl magistrátních hlasů."
    )
    st.markdown(
        """
        <style>
        .js-plotly-plot .plotly text {
            text-shadow: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    election_config = get_election_config(selected_election_id)
    if election_config.election_type != "municipal":
        st.info("Sankey je dostupný jen pro komunální volby.")
        return

    if selected_zastupitelstvo_code not in {"500143", "554782"}:
        st.warning(
            "Přelivy jsou zatím připravené pouze pro Prahu 5 (MČ) / Prahu (OBEC)."
        )

    share_mode = st.radio(
        "Normalizace:",
        options=["ballots", "votes"],
        format_func=lambda x: "Ekvivalent lístku (ballots)"
        if x == "ballots"
        else "Podíly hlasů (votes)",
        horizontal=True,
    )

    flows_path = (
        election_config.reports_dir
        / f"ei_prague5_all_parties_{share_mode}.csv"
    )

    if not flows_path.exists():
        st.warning("Sankey data nejsou k dispozici.")
        st.code(
            f"uv run python src/ecological_inference_all_parties.py --election {selected_election_id} --share-mode {share_mode}",
            language="bash",
        )
        return

    flows_df = pd.read_csv(flows_path)
    if flows_df.empty:
        st.warning("Sankey data jsou prázdná.")
        return
    if "weighted_flow_share" in flows_df.columns:
        flows_df["weighted_flow_share"] = pd.to_numeric(
            flows_df["weighted_flow_share"], errors="coerce"
        ).fillna(0)
    for col in ["outside_bounds", "same_list_number"]:
        if col in flows_df.columns:
            flows_df[col] = (
                flows_df[col]
                .astype(str)
                .str.lower()
                .isin(["true", "1", "yes"])
            )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        include_same = st.checkbox("Zahrnout retenci", value=True)
    with col2:
        include_outside = st.checkbox("Zahrnout mimo bounds", value=False)
    with col3:
        use_family = st.checkbox("Agregovat do rodin", value=False)
    with col4:
        max_flows = st.slider("Max. toků", 10, 120, 50, 5)

    min_flow_pct = st.slider("Min. tok (%)", 0.0, 5.0, 0.5, 0.1)
    sankey_df, total_share = prepare_sankey_flows(
        flows_df,
        include_outside_bounds=include_outside,
        include_same_list=include_same,
        use_family_labels=use_family,
        min_flow_share=min_flow_pct / 100,
        max_flows=max_flows,
    )

    if sankey_df.empty:
        st.info("Po zadaných filtrech nezbyla žádná data.")
        return

    header_left, header_right = st.columns(2)
    with header_left:
        st.markdown("**Magistrát**")
    with header_right:
        st.markdown("**MČ**")

    fig = build_sankey_figure(sankey_df)
    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"Zobrazeno {fmt_pct(total_share * 100, 1)} magistrátních hlasů.")


# Flows need enough precincts to tell the groups apart
MIN_PRECINCTS_FOR_FLOWS = 30
GROUP_PALETTE = [
    "#2563eb", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6",
    "#14b8a6", "#ec4899", "#84cc16", "#f97316", "#0ea5e9",
    "#a855f7", "#eab308", "#06b6d4", "#d946ef", "#65a30d", "#dc2626",
]


@st.cache_data(show_spinner="Porovnávám volby…")
def compute_election_comparison(
    code: str,
    election_id: str,
    previous_election_id: str,
    data_version: float,
    previous_data_version: float,
):
    """Matched precinct tables of both elections and, if possible, voter flows."""
    current = load_municipality_data(code, election_id, data_version)
    previous = load_municipality_data(code, previous_election_id, previous_data_version)

    tables = []
    for data in (previous, current):
        district_df = data.get("district_data")
        party_df = data.get("district_party_results")
        if not isinstance(district_df, pd.DataFrame) or not isinstance(
            party_df, pd.DataFrame
        ):
            return None
        tables.append(precinct_table(district_df, party_df))

    all_current_precincts = len(tables[1])
    previous_table, current_table = match_precincts(*tables)
    flows = None
    if len(current_table) >= MIN_PRECINCTS_FOR_FLOWS:
        flows = estimate_flows(previous_table, current_table)

    return {
        "previous": previous_table,
        "current": current_table,
        "all_current_precincts": all_current_precincts,
        "flows": flows,
    }


def _short_group_name(name: str, limit: int = 34) -> str:
    return name if len(name) <= limit else name[: limit - 2].rstrip() + "…"


def _group_colors(groups) -> Dict[str, str]:
    """The same list keeps its colour on both sides of the diagram."""
    colors = {NON_VOTERS: "#9ca3af", OTHER_LISTS: "#d1d5db"}
    for group in groups:
        if group not in colors:
            colors[group] = GROUP_PALETTE[(len(colors) - 2) % len(GROUP_PALETTE)]
    return colors


def build_flow_sankey(flows: Dict, previous_name: str, current_name: str) -> go.Figure:
    electorate_flows = flows["electorate_flows"]
    sources, targets = list(electorate_flows.index), list(electorate_flows.columns)
    colors = _group_colors(sources + targets)

    labels = [f"{_short_group_name(name)} {previous_name}" for name in sources] + [
        f"{_short_group_name(name)} {current_name}" for name in targets
    ]
    node_colors = [colors[name] for name in sources + targets]

    link_source, link_target, link_value, link_color, link_text = [], [], [], [], []
    for source_position, source in enumerate(sources):
        for target_position, target in enumerate(targets):
            share = electorate_flows.loc[source, target] * 100
            # People who stayed home twice would take up half of the picture
            if share < 0.1 or (source == NON_VOTERS and target == NON_VOTERS):
                continue
            link_source.append(source_position)
            link_target.append(len(sources) + target_position)
            link_value.append(share)
            link_color.append(_hex_to_rgba(colors[source], 0.4))
            link_text.append(
                f"{source} ({previous_name}) → {target} ({current_name})<br>"
                f"{fmt_pct(flows['transitions'].loc[source, target] * 100, 0)} skupiny, "
                f"{fmt_pct(share)} všech voličů"
            )

    fig = go.Figure(
        go.Sankey(
            arrangement="snap",
            # The default label shadow makes the text look smudged
            textfont=dict(color="#111827", size=13, shadow="none"),
            node=dict(
                label=labels,
                color=node_colors,
                pad=14,
                thickness=14,
                line=dict(width=0),
                hovertemplate="%{label}<extra></extra>",
            ),
            link=dict(
                source=link_source,
                target=link_target,
                value=link_value,
                color=link_color,
                customdata=link_text,
                hovertemplate="%{customdata}<extra></extra>",
            ),
        )
    )
    fig.update_layout(height=620, margin=dict(l=0, r=0, t=10, b=10), font=dict(size=13))
    return fig


def _flow_breakdown_chart(shares: pd.Series, colors: Dict[str, str]) -> go.Figure:
    shares = shares[shares >= 0.5].sort_values(ascending=False)
    fig = go.Figure(
        go.Bar(
            y=[_short_group_name(name, 30) for name in shares.index],
            x=shares.values,
            orientation="h",
            marker_color=[colors[name] for name in shares.index],
            text=[fmt_pct(value, 0) for value in shares.values],
            textposition="outside",
            cliponaxis=False,
            customdata=list(shares.index),
            hovertemplate="%{customdata}<br>%{x:.0f} %<extra></extra>",
        )
    )
    fig.update_layout(
        height=60 + 32 * len(shares),
        margin=dict(l=0, r=50, t=10, b=10),
        xaxis=dict(visible=False),
        yaxis=dict(autorange="reversed"),
    )
    return fig


def display_election_comparison(comparison, previous_name: str, current_name: str):
    """Voter flows between two elections and changes in individual precincts"""
    if not comparison or len(comparison["current"]) == 0:
        st.info(
            f"Okrsky se mezi roky {previous_name} a {current_name} nepodařilo spárovat, "
            "srovnání proto není k dispozici."
        )
        return

    previous_table, current_table = comparison["previous"], comparison["current"]
    flows = comparison["flows"]
    matched = len(current_table)
    skipped = comparison["all_current_precincts"] - matched

    st.subheader(f"Přesuny voličů {previous_name} → {current_name}")
    if flows is None:
        st.info(
            f"Odhad přesunů voličů potřebuje aspoň {MIN_PRECINCTS_FOR_FLOWS} okrsků, "
            f"tady je jich {matched}. Změny v jednotlivých okrscích najdete níže."
        )
    else:
        st.markdown(
            "Odhad, kam odešli voliči jednotlivých kandidátek a kolik lidí přišlo "
            "nebo zůstalo doma. Šířka pruhu odpovídá počtu voličů."
        )
        st.plotly_chart(
            build_flow_sankey(flows, previous_name, current_name),
            use_container_width=True,
        )

        transitions = flows["transitions"] * 100
        colors = _group_colors(list(transitions.index) + list(transitions.columns))

        def default_group(groups):
            pirates = [g for g in groups if "pirát" in g.lower()]
            return groups.index(pirates[0]) if pirates else 0

        col1, col2 = st.columns(2)
        with col1:
            sources = list(transitions.index)
            source = st.selectbox(
                f"Kam odešli voliči z roku {previous_name}",
                sources,
                index=default_group(sources),
                key="comparison_source",
            )
            st.plotly_chart(
                _flow_breakdown_chart(transitions.loc[source], colors),
                use_container_width=True,
            )
        with col2:
            targets = list(transitions.columns)
            target = st.selectbox(
                f"Odkud přišli voliči v roce {current_name}",
                targets,
                index=default_group(targets),
                key="comparison_target",
            )
            origin = flows["electorate_flows"][target]
            st.plotly_chart(
                _flow_breakdown_chart(origin / origin.sum() * 100, colors),
                use_container_width=True,
            )

        with st.expander("Celá tabulka přesunů"):
            matrix = transitions.round(0).astype(int)
            matrix.insert(
                0,
                "Podíl všech voličů (%)",
                (flows["source_size"] * 100).round(1),
            )
            matrix.index.name = f"Skupina {previous_name}"
            st.dataframe(
                czech_table(matrix.reset_index(), {"Podíl všech voličů (%)": 1}),
                use_container_width=True,
                hide_index=True,
            )
            st.caption(
                f"Řádky jsou skupiny voličů z roku {previous_name}, sloupce říkají, "
                f"kolik procent z nich skončilo u které kandidátky v roce {current_name}. "
                "Každý řádek dává dohromady 100 %."
            )

        notes = [
            "Jde o modelový odhad, ne o měření. Vychází z výsledků v okrscích a "
            "předpokládá, že se voliči stejné kandidátky chovali ve všech okrscích "
            "podobně. Malé přesuny (řádově jednotky procent) proto berte jako "
            "orientační a přesuny mezi voliči a nevoliči model spíš podceňuje.",
            f"Model vysvětluje {fmt_pct(flows['explained_variation'] * 100, 0)} "
            f"rozdílů mezi okrsky a pracuje s {fmt_int(matched)} okrsky.",
        ]
        if matched < 150:
            notes.append(
                "Na tak malém počtu okrsků je odhad hrubý, spolehlivější je u velkých měst."
            )
        if skipped > 0:
            notes.append(
                f"{fmt_int(skipped)} okrsků je vynecháno, protože v roce {previous_name} "
                "neexistovaly nebo se jim výrazně změnil počet voličů."
            )
        notes.append(
            "Hlasy jsou přepočtené na voliče, kandidátky pod 3 % jsou sloučené "
            "do skupiny Ostatní kandidátky."
        )
        st.caption(" ".join(notes))

    st.subheader("Změna v okrscích")
    same_lists = [
        group
        for group in group_columns(current_table)
        if group in previous_table.columns and group not in (NON_VOTERS, OTHER_LISTS)
    ]
    turnout_option = "Volební účast"
    options = [turnout_option] + same_lists
    pirates = [group for group in same_lists if "pirát" in group.lower()]
    metric = st.selectbox(
        "Co porovnat",
        options,
        index=options.index(pirates[0]) if pirates else 0,
        key="comparison_metric",
        help="Nabízí se účast a kandidátky, které kandidovaly v obou volbách pod stejným názvem.",
    )

    def precinct_values(table):
        if metric == turnout_option:
            return table["turnout"]
        voted = table["registered"] - table[NON_VOTERS]
        return (table[metric] / voted.replace(0, np.nan) * 100).fillna(0)

    precincts = pd.DataFrame(
        {
            "Okrsek": current_table.index,
            previous_name: precinct_values(previous_table).round(2).values,
            current_name: precinct_values(current_table).round(2).values,
            "Zapsaní voliči": current_table["registered"].astype(int).values,
        }
    )
    precincts["Změna (p. b.)"] = (precincts[current_name] - precincts[previous_name]).round(2)
    unit = "Účast (%)" if metric == turnout_option else "Podíl hlasů (%)"

    if len(precincts) < 3:
        st.dataframe(
            czech_table(
                precincts,
                {previous_name: 2, current_name: 2, "Změna (p. b.)": 2},
                signed=("Změna (p. b.)",),
            ),
            use_container_width=True,
            hide_index=True,
        )
        return

    improved = int((precincts["Změna (p. b.)"] > 0).sum())
    st.markdown(
        f"Hodnota vzrostla v **{fmt_int(improved)}** z {fmt_int(len(precincts))} okrsků. "
        "Body nad čárou jsou okrsky, kde je výsledek lepší než minule."
    )

    upper = float(max(precincts[previous_name].max(), precincts[current_name].max())) * 1.05
    fig = px.scatter(
        precincts,
        x=previous_name,
        y=current_name,
        size="Zapsaní voliči",
        size_max=12,
        hover_name="Okrsek",
        color="Změna (p. b.)",
        color_continuous_scale="RdYlGn",
        color_continuous_midpoint=0,
        labels={previous_name: f"{unit} {previous_name}", current_name: f"{unit} {current_name}"},
    )
    fig.add_shape(
        type="line", x0=0, y0=0, x1=upper, y1=upper, line=dict(color="#6b7280", dash="dash")
    )
    fig.update_layout(height=480, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        czech_table(
            precincts.sort_values("Změna (p. b.)", ascending=False),
            {previous_name: 2, current_name: 2, "Změna (p. b.)": 2},
            signed=("Změna (p. b.)",),
        ),
        use_container_width=True,
        hide_index=True,
        height=min(38 + 35 * len(precincts), 420),
    )
    st.caption(
        "Velikost bodu odpovídá počtu zapsaných voličů. "
        "Kliknutím na záhlaví sloupce tabulku seřadíte."
    )


def get_previous_election_id(election_id: str) -> Optional[str]:
    """Closest earlier election of the same type that has data on disk."""
    elections = get_election_info()
    current = elections[election_id]
    earlier = sorted(
        (
            (info["date"], other_id)
            for other_id, info in elections.items()
            if info["type"] == current["type"] and info["date"] < current["date"]
        ),
        reverse=True,
    )
    for _, other_id in earlier:
        if get_results_data_version(other_id) > 0:
            return other_id
    return None


@st.cache_data(show_spinner=False)
def get_largest_municipalities(election_id: str, data_version: float, count: int = 10):
    """Largest city councils (without city districts) with turnout and winner."""
    _, comprehensive_data = load_all_municipality_data(election_id)
    rows = []
    for code, municipality in (comprehensive_data or {}).get("municipalities", {}).items():
        districts = municipality.get("district_data") or []
        parties = municipality.get("party_results") or []
        if not districts or not parties or districts[0].get("type") != "OBEC":
            continue
        stats = municipality.get("summary_statistics", {})
        winner = max(parties, key=lambda party: party.get("votes_absolute", 0))
        total_votes = sum(party.get("votes_absolute", 0) for party in parties)
        rows.append(
            {
                "code": code,
                "Město": municipality.get("metadata", {}).get("municipality_name", code),
                "Zapsaní voliči": stats.get("registered_voters", 0),
                "Účast (%)": stats.get("turnout_percentage", 0),
                "Vítěz": winner.get("party_name", ""),
                "Podíl vítěze (%)": winner.get("votes_absolute", 0) / total_votes * 100
                if total_votes
                else 0,
            }
        )
    rows.sort(key=lambda row: row["Zapsaní voliči"], reverse=True)
    return rows[:count]


def display_landing(election_id: str, election_name: str, is_parliamentary: bool, count: int):
    """Shown until a municipality (or region) is selected."""
    st.title(election_name)

    if is_parliamentary:
        st.markdown(
            "Vyberte v levém panelu kraj. Zobrazí se výsledky stran, kandidáti, "
            "účast a mapa okrsků."
        )
        return

    st.markdown(
        f"Výsledky {fmt_int(count)} zastupitelstev obcí, měst a městských částí. "
        "Vyberte obec v levém panelu – stačí začít psát její název – "
        "nebo otevřete některé z největších měst."
    )

    largest = get_largest_municipalities(
        election_id, get_results_data_version(election_id)
    )
    if not largest:
        return

    def open_municipality(code):
        st.session_state[f"municipality_select_{election_id}"] = code

    columns = st.columns(5)
    for position, row in enumerate(largest):
        columns[position % 5].button(
            row["Město"],
            key=f"open_{row['code']}",
            on_click=open_municipality,
            args=(row["code"],),
            use_container_width=True,
        )

    st.subheader("Největší města")
    st.dataframe(
        czech_table(
            pd.DataFrame(largest).drop(columns="code"),
            {"Účast (%)": 1, "Podíl vítěze (%)": 1},
        ),
        use_container_width=True,
        hide_index=True,
    )
    st.caption(
        "Po výběru obce uvidíte výsledky kandidátek a srovnání s minulými volbami, "
        "účast, mapu okrsků a podrobná data za jednotlivé okrsky."
    )


def main():
    """Main Streamlit application"""

    # Get URL parameters early
    url_params = get_url_params()

    st.sidebar.title("Volební analýza")

    # Election selector
    available_elections = get_election_info()
    election_ids = list(available_elections.keys())
    elections_with_data = [
        election_id
        for election_id in election_ids
        if get_results_data_version(election_id) > 0
    ]

    def election_label(election_id):
        name = available_elections[election_id]["name"]
        if election_id not in elections_with_data:
            return f"{name} (data nejsou stažená)"
        return name

    fallback_election = elections_with_data[0] if elections_with_data else election_ids[0]
    default_election = get_param_value(url_params, "election", fallback_election)
    if default_election not in election_ids:
        default_election = fallback_election

    selected_election_id = st.sidebar.selectbox(
        "Volby",
        options=election_ids,
        format_func=election_label,
        index=election_ids.index(default_election),
        key="election_selector",
    )

    if get_param_value(url_params, "election") != selected_election_id:
        update_url_params(election=selected_election_id)

    election_config = get_election_config(selected_election_id)
    is_parliamentary = election_config.election_type == "parliamentary"

    # Load municipality data and create selector
    municipality_index, comprehensive_data = ensure_data_exists(selected_election_id)

    if not municipality_index or not comprehensive_data:
        return

    default_municipality = get_param_value(url_params, "municipality")
    selected_zastupitelstvo_code = create_municipality_selector(
        municipality_index, selected_election_id, is_parliamentary, default_municipality
    )

    # Update URL parameter for municipality selection
    update_url_params(municipality=selected_zastupitelstvo_code)

    if not selected_zastupitelstvo_code:
        display_landing(
            selected_election_id,
            election_config.election_name,
            is_parliamentary,
            len(municipality_index),
        )
        return

    # Get municipality/district info for title
    municipality_data = get_municipality_data(
        selected_zastupitelstvo_code, comprehensive_data
    )
    municipality_name = "Neznámé"
    election_type = "Volby"

    if municipality_data:
        metadata = municipality_data.get("metadata", {})

        # Check if parliamentary or municipal
        if is_parliamentary:
            municipality_name = metadata.get(
                "district_name", f"Obvod {selected_zastupitelstvo_code}"
            )
            election_type = "Volební kraj"
        else:
            municipality_name = metadata.get("municipality_name", "Neznámá obec")

            # Determine specific election type for municipal
            districts = municipality_data.get("district_data", [])
            election_type = "Zastupitelstvo"
            if districts:
                oznac_typu = districts[0].get("type", "")
                if oznac_typu == "OBEC":
                    election_type = "Zastupitelstvo obce"
                elif oznac_typu == "MCMO":
                    election_type = "Zastupitelstvo městské části nebo obvodu"

    st.title(municipality_name)
    st.caption(f"{election_type} · {election_config.election_name}")

    # Load data for selected municipality/zastupitelstvo
    with st.spinner(f"Načítám data: {municipality_name}…"):
        geojson_data = None
        geojson_kod_mco_set = set()
        obec_mapping = {}
        data_version = get_results_data_version(selected_election_id)
        electoral_data = load_municipality_data(
            selected_zastupitelstvo_code, selected_election_id, data_version
        )

        # The same council in the previous election, for comparisons
        previous_data = None
        previous_name = ""
        previous_election_id = get_previous_election_id(selected_election_id)
        if previous_election_id and not is_parliamentary:
            _, previous_comprehensive = load_all_municipality_data(previous_election_id)
            if get_municipality_data(selected_zastupitelstvo_code, previous_comprehensive):
                previous_data = load_municipality_data(
                    selected_zastupitelstvo_code,
                    previous_election_id,
                    get_results_data_version(previous_election_id),
                )
                previous_name = available_elections[previous_election_id]["date"][:4]

    # Views, with URL parameter support
    tab_options = ["Souhrn", "Účast", "Mapa", "Okrsky"]
    if previous_data:
        tab_options.insert(1, "Srovnání")
    flows_ready = (
        not is_parliamentary
        and selected_zastupitelstvo_code in {"500143", "554782"}
        and (election_config.reports_dir / "ei_prague5_all_parties_ballots.csv").exists()
    )
    if flows_ready:
        tab_options.append("Přelivy")
    tab_options.append("Data")

    # Get default tab from URL params
    default_tab = get_param_value(url_params, "tab", tab_options[0])
    legacy_tab_map = {
        "Overview": "Souhrn",
        "Turnout Analysis": "Účast",
        "Geographic Analysis": "Mapa",
        "Data Explorer": "Data",
        "Data (pokročilé)": "Data",
        "District Analysis": "Okrsky",
    }
    default_tab = legacy_tab_map.get(default_tab, default_tab)
    if default_tab not in tab_options:
        default_tab = tab_options[0]
    if st.session_state.get("main_tab_selector") not in tab_options:
        st.session_state.pop("main_tab_selector", None)

    selected_tab = (
        st.segmented_control(
            "Pohled",
            tab_options,
            default=default_tab,
            key="main_tab_selector",
            label_visibility="collapsed",
        )
        or default_tab
    )

    # Update URL parameter for tab selection immediately when selection changes
    update_url_params(tab=selected_tab)

    st.sidebar.caption(
        "Adresa stránky se mění podle toho, co si zobrazíte. "
        "Když ji zkopírujete, otevře se komukoli stejný pohled."
    )

    # For geographic analysis, we need to map zastupitelstvo_code to geographic municipality code
    # since the GeoJSON uses different codes (CIS_OBEC vs KODZASTUP)
    geographic_municipality_codes = [
        selected_zastupitelstvo_code
    ]  # Start with zastupitelstvo code

    # For city-wide elections (like Praha), we need to collect ALL municipality codes from districts
    if municipality_data:
        districts = municipality_data.get("district_data", [])
        unique_cis_obec_codes = {
            district.get("municipality_code")
            for district in districts
            if district.get("municipality_code")
        }
        geographic_municipality_codes.extend(list(unique_cis_obec_codes))

    # Display content based on selected tab
    if selected_tab == "Souhrn":
        display_electoral_overview(electoral_data, previous_data, previous_name)

    elif selected_tab == "Srovnání":
        display_election_comparison(
            compute_election_comparison(
                selected_zastupitelstvo_code,
                selected_election_id,
                previous_election_id,
                data_version,
                get_results_data_version(previous_election_id),
            ),
            previous_name,
            available_elections[selected_election_id]["date"][:4],
        )

    elif selected_tab == "Účast":
        display_turnout_analysis(electoral_data, previous_data, previous_name)

    elif selected_tab == "Mapa":
        geojson_data = None
        geojson_kod_mco_set = load_geojson_kod_mco_set(selected_election_id)
        obec_mapping = load_obec_mapping(selected_election_id)

        # Optional municipal-part filter for parliamentary elections
        election_config = get_election_config(selected_election_id)
        is_parliamentary = election_config.election_type == "parliamentary"
        geographic_electoral_data = electoral_data
        selected_polling_stations = None
        selected_geo_obec = get_param_value(url_params, "geo_obec", None)

        use_simplified_geo = False
        use_ram_cache = False
        if (
            is_parliamentary
            and electoral_data
            and "polling_stations" in electoral_data
            and electoral_data["polling_stations"]
        ):
            use_simplified_geo = st.checkbox(
                "Zjednodušené hranice (rychlejší)",
                value=True,
            )
            use_ram_cache = st.checkbox(
                "Uložit GeoJSON do RAM (rychlé, vyšší paměť)",
                value=False,
            )
            polling_stations = electoral_data["polling_stations"]
            municipality_map = {}
            for station in polling_stations:
                obec_code = station.get("municipality_code")
                if not obec_code:
                    continue
                if obec_code not in municipality_map:
                    municipality_map[obec_code] = station.get("municipality_name")

            municipality_codes = sorted(
                municipality_map.keys(),
                key=lambda code: (
                    municipality_map.get(code) or "",
                    int(code) if code.isdigit() else code,
                ),
            )

            if selected_geo_obec is None:
                selected_geo_obec = (
                    municipality_codes[0] if municipality_codes else "ALL"
                )

            if selected_geo_obec not in municipality_codes and selected_geo_obec != "ALL":
                selected_geo_obec = (
                    municipality_codes[0] if municipality_codes else "ALL"
                )

            selected_geo_obec = st.selectbox(
                "Filtrovat obec (volitelné):",
                ["ALL"] + municipality_codes,
                index=(["ALL"] + municipality_codes).index(selected_geo_obec),
                format_func=lambda code: "Všechny obce v obvodu"
                if code == "ALL"
                else f"{municipality_map.get(code) or 'Neznámá'} ({code})",
                key="geo_obec_select",
            )

            update_url_params(geo_obec=selected_geo_obec)

            if selected_geo_obec != "ALL":
                selected_polling_stations = [
                    station
                    for station in polling_stations
                    if station.get("municipality_code") == selected_geo_obec
                ]
                st.caption(
                    f"Filtr: {municipality_map.get(selected_geo_obec) or 'Neznámá'} "
                    f"({selected_geo_obec}) – {len(selected_polling_stations)} volebních místností"
                )
            else:
                render_all = st.checkbox(
                    "Vykreslit všechny obce v obvodu (pomalé)",
                    value=False,
                )
                if not render_all:
                    st.info(
                        "Vyberte obec pro rychlejší vykreslení, nebo povolte vykreslení všech."
                    )
                    return
                selected_polling_stations = polling_stations

            station_codes = {
                str(station.get("station_number"))
                for station in selected_polling_stations
                if station.get("station_number")
            }

            filtered_district_data = electoral_data.get("district_data")
            if isinstance(filtered_district_data, pd.DataFrame):
                filtered_district_data = filtered_district_data[
                    filtered_district_data["district_code"].astype(str).isin(
                        station_codes
                    )
                ]

            filtered_party_results = electoral_data.get("district_party_results")
            if isinstance(filtered_party_results, pd.DataFrame):
                filtered_party_results = filtered_party_results[
                    filtered_party_results["district_code"].astype(str).isin(
                        station_codes
                    )
                ]

            geographic_electoral_data = {
                **electoral_data,
                "polling_stations": selected_polling_stations,
                "district_data": filtered_district_data,
                "district_party_results": filtered_party_results,
            }

        # Filter geojson for this municipality/electoral district
        municipality_geojson = None
        municipality_districts = []

        if is_parliamentary and obec_mapping:
            if selected_polling_stations:
                polling_stations = selected_polling_stations

                # Extract unique OBEC codes from polling stations
                obec_codes = set()
                for station in polling_stations:
                    obec_code = station.get("municipality_code", "")
                    if obec_code:
                        obec_codes.add(str(obec_code))

                target_mco_codes = {
                    code for code in obec_codes if code in geojson_kod_mco_set
                }
                target_obec_codes = set()
                for obec_code in obec_codes:
                    if obec_code in target_mco_codes:
                        continue
                    mapped = (
                        obec_mapping.get(obec_code, {}).get("kod_obec_geojson")
                        or obec_code
                    )
                    target_obec_codes.add(str(mapped))

                if selected_geo_obec != "ALL":
                    municipality_geojson = load_pre_split_geojson(
                        selected_election_id, selected_geo_obec
                    )
                    if municipality_geojson is None:
                        municipality_geojson = load_geojson_subset(
                            selected_election_id,
                            sorted(target_mco_codes),
                            sorted(target_obec_codes),
                            use_simplified_geo,
                            use_ram_cache,
                        )

                if municipality_geojson is None:
                    geojson_data = load_geojson_data(selected_election_id)
                    if geojson_data and "features" in geojson_data:
                        for feature in geojson_data["features"]:
                            props = feature.get("properties", {})
                            kod_mco = props.get("kod_mco", "")
                            kod_obec = props.get("kod_obec", "")

                            if kod_mco and str(kod_mco) in target_mco_codes:
                                municipality_districts.append(feature)
                            elif kod_obec and str(kod_obec) in target_obec_codes:
                                municipality_districts.append(feature)

                if municipality_districts:
                    municipality_geojson = {
                        "type": "FeatureCollection",
                        "features": municipality_districts,
                    }

                st.info(
                    f"📍 Parlamentní volby: spárováno "
                    f"{len(municipality_geojson.get('features', []) if municipality_geojson else 0)} "
                    f"okrsků z {len(obec_codes)} obcí"
                )
            else:
                st.warning("⚠️ Pro parlamentní volby nejsou dostupná data o okrscích.")

        else:
            geojson_data = load_geojson_data(selected_election_id)
            if geojson_data and "features" in geojson_data:
                # First, try municipality-level matching (more precise)
                for feature in geojson_data["features"]:
                    props = feature.get("properties", {})

                    # Strategy 1: Match using MOMC field
                    if props.get("MOMC") in geographic_municipality_codes:
                        municipality_districts.append(feature)

                    # Strategy 2: Match using OBEC field
                    elif props.get("OBEC") in geographic_municipality_codes:
                        municipality_districts.append(feature)

                    # Strategy 3: Match using CIS_OBEC field
                    elif props.get("CIS_OBEC") in geographic_municipality_codes:
                        municipality_districts.append(feature)

                # If no municipality-level matches found, try district-level matching as fallback
                if (
                    not municipality_districts
                    and electoral_data
                    and "district_data" in electoral_data
                ):
                    electoral_districts = electoral_data["district_data"]
                    if hasattr(electoral_districts, "index"):  # It's a DataFrame
                        district_codes = set(
                            electoral_districts["district_code"].astype(str).tolist()
                        )
                    else:  # It's a list of dicts
                        district_codes = set(
                            str(d.get("district_code", "")) for d in electoral_districts
                        )

                    # Only match districts if we're confident about the municipality
                    for feature in geojson_data["features"]:
                        props = feature.get("properties", {})
                        feature_district_code = get_district_code_from_geojson(props)

                        # More conservative district matching - only if we have a reasonable number of matches
                        if feature_district_code in district_codes:
                            municipality_districts.append(feature)

                    # Safety check - if we get too many districts, something is wrong
                    if (
                        len(municipality_districts) > 200
                    ):  # Reasonable upper limit for any municipality
                        municipality_districts = []  # Clear the overly broad match

                if municipality_districts:
                    municipality_geojson = {
                        "type": "FeatureCollection",
                        "features": municipality_districts,
                    }
            else:
                # Enhanced debugging for municipality matching
                st.subheader("Mapa – ladění párování obce")
                st.warning(
                    f"📍 **Nenalezeny hranice** pro {municipality_name}"
                )

                # Show detailed debugging info
                with st.expander("🔧 Detail párování", expanded=True):
                    st.write(f"**Obec:** {municipality_name}")
                    st.write(f"**Kód zastupitelstva:** {selected_zastupitelstvo_code}")
                    st.write(
                        f"**Hledané kódy obce:** {geographic_municipality_codes}"
                    )

                    # Sample some GeoJSON features to understand the structure
                    if geojson_data and "features" in geojson_data:
                        st.write(
                            f"**Celkem prvků v GeoJSON:** {len(geojson_data.get('features', []))}"
                        )

                        # Show sample of available municipality codes in GeoJSON
                        sample_features = geojson_data["features"][
                            :50
                        ]  # Sample first 50

                        momc_codes = set()
                        obec_codes = set()
                        cis_obec_codes = set()

                        for feature in sample_features:
                            props = feature.get("properties", {})
                            if props.get("MOMC"):
                                momc_codes.add(props.get("MOMC"))
                            if props.get("OBEC"):
                                obec_codes.add(props.get("OBEC"))
                            if props.get("CIS_OBEC"):
                                cis_obec_codes.add(props.get("CIS_OBEC"))

                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.write("**Ukázka kódů MOMC:**")
                            st.write(sorted(list(momc_codes))[:10])
                        with col2:
                            st.write("**Ukázka kódů OBEC:**")
                            st.write(sorted(list(obec_codes))[:10])
                        with col3:
                            st.write("**Ukázka kódů CIS_OBEC:**")
                            st.write(sorted(list(cis_obec_codes))[:10])

                        # Show a sample feature structure
                        st.write("**Ukázka vlastností GeoJSON:**")
                        if sample_features:
                            sample_props = sample_features[0].get("properties", {})
                            st.json(
                                dict(list(sample_props.items())[:10])
                            )  # Show first 10 properties

                    st.info(
                        "**Zdá se, že kódy obcí v datech neodpovídají kódům v GeoJSON.** "
                        "To je běžné při rozdílných číselnících mezi systémy.\n\n"
                        "**Dostupné pohledy pro tuto obec:**\n"
                        "• Souhrn – výsledky stran a statistiky\n"
                        "• Účast – účast voličů\n"
                        "• Data (pokročilé) – surová data\n"
                        "• Okrsky – rozpad podle okrsků"
                    )

        display_geographic_analysis(
            municipality_geojson, geographic_electoral_data, selected_election_id
        )

    elif selected_tab == "Přelivy":
        display_flow_sankey(
            selected_election_id, selected_zastupitelstvo_code
        )

    elif selected_tab == "Data":
        display_data_explorer(electoral_data)

    elif selected_tab == "Okrsky":
        display_district_analysis(electoral_data)

    # Footer
    st.caption("Zdroj dat: Český statistický úřad, volby.cz")


if __name__ == "__main__":
    main()

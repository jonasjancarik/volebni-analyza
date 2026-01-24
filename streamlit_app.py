#!/usr/bin/env python3
"""
Czech Municipalities Election Analysis - Streamlit Dashboard
Interactive visualization dashboard for electoral analysis of any Czech municipality
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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
from typing import Dict, List, Optional

# Add src directory to path
sys.path.append(str(Path(__file__).parent / "src"))

from election_config import (
    get_election_config,
    get_election_info,
    list_available_elections,
)

logger = logging.getLogger(__name__)

# Configure Streamlit page
st.set_page_config(
    page_title="Czech Municipalities Electoral Analysis",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def run_data_collection(election_id="kv2022"):
    """Run the data collection script if data is missing"""
    st.info(f"🔄 Starting data collection for {election_id}...")

    # Create a progress bar and output display
    progress_bar = st.progress(0)
    status_text = st.empty()
    output_container = st.expander("📋 View Live Output", expanded=True)
    output_text = output_container.empty()

    try:
        status_text.text("🚀 Starting data collection...")
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
            status_text.text("✅ Data collection completed successfully!")
            st.success(
                "✅ Data collection completed! The page will refresh automatically."
            )
            st.balloons()
            import time

            time.sleep(2)
            return True
        else:
            st.error(f"❌ Data collection failed (exit code: {return_code})")
            st.warning(
                "Check the output above for error details, or view: all_municipalities_analysis.log"
            )
            return False

    except Exception as e:
        st.error(f"❌ Error running data collection: {e}")
        st.exception(e)
        return False


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

        # Load index
        if not index_file.exists():
            return None, None

        with open(index_file, "r", encoding="utf-8") as f:
            index_data = json.load(f)

        # Load comprehensive data
        if not comprehensive_file.exists():
            return None, None

        with open(comprehensive_file, "r", encoding="utf-8") as f:
            comprehensive_data = json.load(f)

        return index_data, comprehensive_data

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
    st.warning(f"⚠️ Election data not found for {election_config.election_name}!")

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "🚀 Run Data Collection", type="primary", key=f"collect_{election_id}"
        ):
            if run_data_collection(election_id):
                st.rerun()  # Refresh the app after data collection

    with col2:
        if election_config.election_type == "parliamentary":
            st.info(
                "This will download and process parliamentary election data for 14 electoral districts. It may take a minute."
            )
        else:
            st.info(
                "This will download and process data for all 6,377+ Czech municipalities. It may take a few minutes."
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


def create_municipality_selector(municipality_index, comprehensive_data):
    """Create municipality/district selection interface"""
    # Determine if this is parliamentary or municipal data
    is_parliamentary = (
        "electoral_districts" in comprehensive_data if comprehensive_data else False
    )

    if is_parliamentary:
        st.sidebar.header("🗳️ Electoral District Selection")
        label = "Choose electoral district:"
        help_text = f"Select from {len(municipality_index)} electoral districts"
    else:
        st.sidebar.header("🏛️ Municipality Selection")
        label = "Choose municipality:"
        help_text = f"Select from {len(municipality_index)} municipalities"

    # Convert to DataFrame and sort alphabetically by name
    df = pd.DataFrame.from_dict(municipality_index, orient="index")
    df["code"] = df.index
    df = df.reset_index(drop=True)
    df = df.sort_values("name", ascending=True)

    # Create simple dropdown with all items
    options = []
    for _, row in df.iterrows():
        option_text = f"{row['name']} ({row['code']})"
        options.append((option_text, row["code"]))

    if options:
        selected_option = st.sidebar.selectbox(
            label,
            options,
            format_func=lambda x: x[0],
            help=help_text,
        )

        if selected_option:
            selected_code = selected_option[1]
            display_municipality_sidebar_info(selected_code, comprehensive_data)
            return selected_code

    return None


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


def display_municipality_sidebar_info(municipality_code, comprehensive_data):
    """Display detailed information about selected municipality/district in sidebar"""
    if not comprehensive_data:
        return

    municipality_data = get_data_by_code(municipality_code, comprehensive_data)
    if not municipality_data:
        st.sidebar.error("Data not found for this code")
        return

    metadata = municipality_data["metadata"]
    stats = municipality_data["summary_statistics"]

    # Check if this is parliamentary or municipal data
    is_parliamentary = "district_number" in metadata

    if is_parliamentary:
        st.sidebar.subheader("Electoral District Info")
        st.sidebar.write(f"**District:** {metadata.get('district_name', 'Unknown')}")
        st.sidebar.write(f"**Number:** {metadata.get('district_number', 'N/A')}")
        st.sidebar.write(f"**Total Mandates:** {stats.get('total_mandates', 0)}")

        st.sidebar.subheader("Election Statistics")
        st.sidebar.write(f"**Candidates:** {stats.get('total_candidates', 0)}")
        st.sidebar.write(f"**Parties:** {stats.get('parties_participating', 0)}")
    else:
        st.sidebar.subheader("Municipality Info")
        st.sidebar.write(f"**Name:** {metadata.get('municipality_name', 'Unknown')}")
        st.sidebar.write(f"**Code:** {metadata.get('municipality_code', 'N/A')}")
        st.sidebar.write(f"**Council Seats:** {metadata.get('total_mandates', 0)}")
        st.sidebar.write(f"**Seats Won:** {metadata.get('mandates_won', 0)}")

        st.sidebar.subheader("Election Statistics")
        if "electoral_districts" in stats:
            st.sidebar.write(f"**Electoral Districts:** {stats['electoral_districts']}")
        if "registered_voters" in stats:
            st.sidebar.write(f"**Registered Voters:** {stats['registered_voters']:,}")
        if "turnout_percentage" in stats:
            st.sidebar.write(f"**Turnout:** {stats['turnout_percentage']:.2f}%")
        if "valid_votes" in stats:
            st.sidebar.write(f"**Valid Votes:** {stats['valid_votes']:,}")
        st.sidebar.write(f"**Parties:** {stats.get('parties_participating', 0)}")
        if "parties_with_mandates" in stats:
            st.sidebar.write(
                f"**Parties with Seats:** {stats['parties_with_mandates']}"
            )


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
        # Use 2022 geojson for municipal elections
        cache_file = Path("input/raw/electoral_districts_boundaries.geojson")
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

            st.warning("⚠️ Cached file appears corrupted, re-downloading...")

        except Exception as e:
            st.warning(f"⚠️ Error reading cached file: {e}. Re-downloading...")

    # For parliamentary elections, expect the preprocessed WGS84 file.
    if election_config.election_type == "parliamentary":
        if raw_cache_file.exists():
            st.error(
                f"❌ Preprocessed GeoJSON not found: {cache_file}\n\n"
                "Run the preprocessing step to convert the raw 2025 polling station GeoJSON to WGS84:\n"
                "  uv run python run_all_municipalities.py --election ps2025 --no-download"
            )
        else:
            st.error(
                f"❌ GeoJSON file not found: {raw_cache_file}\n\n"
                f"The 2025 polling station GeoJSON (252.6 MB) must be downloaded separately.\n"
                f"Please download it from the ČSÚ GIS portal and place it in the input/raw/ directory."
            )
        return None

    # Download the file (municipal elections only)
    try:
        st.info(
            "🌐 Downloading electoral district boundaries (8MB) - this may take a moment..."
        )
        response = requests.get(url, timeout=120)  # Increased timeout for large file
        response.raise_for_status()

        st.info("📊 Parsing GeoJSON data...")
        geojson_data = response.json()

        # Validate the data structure
        if not isinstance(geojson_data, dict):
            raise ValueError("Invalid GeoJSON format: not a dictionary")

        if geojson_data.get("type") != "FeatureCollection":
            raise ValueError(f"Invalid GeoJSON type: {geojson_data.get('type')}")

        features = geojson_data.get("features", [])
        if not features:
            raise ValueError("No features found in GeoJSON")

        # Save to cache
        st.info("💾 Saving to local cache for future use...")
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(geojson_data, f, ensure_ascii=False)

        st.success(f"✅ Downloaded and cached {len(features):,} electoral districts")
        return geojson_data

    except requests.exceptions.Timeout:
        st.error(
            "⏱️ Download timed out. Please try again or check your internet connection."
        )
        return None
    except requests.exceptions.ConnectionError:
        st.error("🔌 Connection error. Please check your internet connection.")
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"🌐 HTTP error downloading GeoJSON data: {e}")
        return None
    except ValueError as e:
        st.error(f"📊 Data format error: {e}")
        return None
    except Exception as e:
        st.error(f"❌ Unexpected error loading GeoJSON data: {e}")
        st.error(
            "💡 Try refreshing the page or contact support if the problem persists."
        )
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
            f"⚠️ OBEC mapping file not found: {mapping_file}\n\n"
            f"This file is required to match PS2025 district codes to GeoJSON features."
        )
        return {}

    try:
        with open(mapping_file, "r", encoding="utf-8") as f:
            mapping = json.load(f)
        return mapping
    except Exception as e:
        st.error(f"❌ Error loading OBEC mapping: {e}")
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
            "electoral district"
            if election_config.election_type == "parliamentary"
            else "zastupitelstvo"
        )
        st.error(f"No data found for {entity_type} {zastupitelstvo_code}")
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
                p.get("party_code"): p.get("party_name", "Unknown")
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
                p.get("party_code"): p.get("party_name", "Unknown")
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
                    party_name = party_name_map.get(
                        party_code, f"Party {party_code}"
                    )
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
            district_code = get_district_code_from_geojson(properties) or "Unknown"

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
                    popup_html += f"<p><strong>Turnout:</strong> {value:.1f}%</p>"
                elif viz_type == "Estimated Voters":
                    popup_html += (
                        f"<p><strong>Registered Voters:</strong> {int(value):,}</p>"
                    )
                elif viz_type == "Valid Votes" or viz_type == "Valid Votes (dots)":
                    popup_html += f"<p><strong>Valid Votes:</strong> {int(value):,}</p>"
                elif viz_type == "Party Results" and selected_party:
                    popup_html += (
                        f"<p><strong>{selected_party}:</strong> {value:.1f}%</p>"
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
                        popup_html += f"<p><strong>Estimated Voters:</strong> {voter_estimate:,}</p>"

                    popup_html += (
                        f"<p><strong>Valid Votes:</strong> {valid_votes:,}</p>"
                    )

                if "registered_voters" in district_row and pd.notna(
                    district_row["registered_voters"]
                ):
                    registered_voters = int(district_row["registered_voters"])
                    if registered_voters > 0 and "valid_votes" in locals():
                        vote_share = (valid_votes / registered_voters) * 100
                        popup_html += f"<p><strong>Vote Share:</strong> {vote_share:.1f}% of registered voters</p>"

                # Add other context data if not already shown
                if (
                    viz_type != "Turnout"
                    and "turnout_percentage" in district_row
                    and pd.notna(district_row["turnout_percentage"])
                ):
                    popup_html += f"<p><strong>Turnout:</strong> {district_row['turnout_percentage']:.1f}%</p>"

                if (
                    viz_type != "Estimated Voters"
                    and "registered_voters" in district_row
                    and pd.notna(district_row["registered_voters"])
                ):
                    popup_html += f"<p><strong>Registered Voters:</strong> {int(district_row['registered_voters']):,}</p>"
            else:
                popup_html += (
                    f"<p><em>No detailed data available for this okrsek</em></p>"
                )

            popup_html += f"""
                <hr style="margin: 5px 0;">
                <p style="font-size: 10px; color: #666;">Click for more details</p>
            </div>
            """

            return popup_html

        # Add GeoJSON layer with data styling
        for feature in geojson_data["features"]:
            popup_content = create_popup_content(feature)

            # Create informative tooltip based on visualization type
            properties = feature.get("properties", {})
            district_code = get_district_code_from_geojson(properties) or "Unknown"

            tooltip_text = f"Okrsek {district_code}"

            # Add relevant data to tooltip based on visualization type
            if district_code in viz_data:
                value = viz_data[district_code]

                if viz_type == "Turnout":
                    tooltip_text = f"Okrsek {district_code}: {value:.1f}% turnout"
                elif viz_type == "Estimated Voters":
                    tooltip_text = f"Okrsek {district_code}: {int(value):,} voters"
                elif viz_type == "Valid Votes" or viz_type == "Valid Votes (dots)":
                    tooltip_text = f"Okrsek {district_code}: {int(value):,} valid votes"
                elif viz_type == "Party Results" and selected_party:
                    tooltip_text = (
                        f"Okrsek {district_code}: {value:.1f}% {selected_party}"
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
                                tooltip_text += f" | ~{voter_estimate:,} voters"
                            elif viz_type not in [
                                "Estimated Voters"
                            ]:  # Don't duplicate for estimated voters viz
                                tooltip_text += f" | ~{voter_estimate:,} voters"

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
                            label_text = f"{value:.0f}%"
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
                            label_text = f"{value:.0f}%"

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
                    if label_text:  # Only add label if we have data
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
                <h5 style="margin: 0 0 8px 0; font-size: 13px;">{viz_type} Legend</h5>
            """

            if viz_type == "Turnout":
                legend_html += """
                <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#2E8B57"></i> ≥60% (High)</p>
                <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#90EE90"></i> 50-59% (Med-High)</p>
                <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#FFD700"></i> 40-49% (Medium)</p>
                <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#FFA500"></i> 30-39% (Low-Med)</p>
                <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#FF6347"></i> <30% (Low)</p>
                """
            elif viz_type == "Estimated Voters":
                legend_html += """
                <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#2E8B57"></i> ≥800 (High)</p>
                <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#90EE90"></i> 600-799 (Med-High)</p>
                <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#FFD700"></i> 400-599 (Medium)</p>
                <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#FFA500"></i> 200-399 (Low-Med)</p>
                <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#FF6347"></i> <200 (Low)</p>
                """
            elif viz_type == "Party Results":
                legend_html += f"""
                <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#006400"></i> ≥25% (Very Strong)</p>
                <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#228B22"></i> 20-24% (Strong)</p>
                <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#32CD32"></i> 15-19% (Good)</p>
                <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#FFD700"></i> 10-14% (Moderate)</p>
                <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#87CEEB"></i> 5-9% (Weak)</p>
                <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#4169E1"></i> <5% (Very Weak)</p>
                """

            legend_html += '<p style="margin: 3px 0;"><i class="fa fa-square" style="color:#CCCCCC"></i> No Data</p></div>'

            m.get_root().html.add_child(folium.Element(legend_html))

    # Don't use auto-fit in tabs - it causes zoom issues
    # The calculated zoom_start should be sufficient

    return m


def display_electoral_overview(data):
    """Display overview statistics using CSV data"""
    st.subheader("📊 Electoral Overview")

    # Create columns for metrics
    col1, col2, col3, col4 = st.columns(4)

    # Extract statistics from CSV data
    total_districts = 0
    avg_turnout = 0
    total_voters = 0
    total_parties = 0

    # Get summary statistics
    if "summary_statistics" in data:
        stats = data["summary_statistics"]
        total_voters = (
            int(stats.get("registered_voters", 0))
            if stats.get("registered_voters")
            else 0
        )
        avg_turnout = (
            float(stats.get("turnout_percentage", 0))
            if stats.get("turnout_percentage")
            else 0
        )
        total_districts = (
            int(stats.get("electoral_districts", 0))
            if stats.get("electoral_districts")
            else 0
        )

    # Get party count from party results
    if "party_results" in data and isinstance(data["party_results"], pd.DataFrame):
        total_parties = len(data["party_results"])

    # Get district count from district data
    if "district_data" in data and isinstance(data["district_data"], pd.DataFrame):
        district_count = len(data["district_data"])
        if district_count > total_districts:
            total_districts = district_count

    # Display metrics
    with col1:
        st.metric(
            "Electoral Districts",
            f"{total_districts:,}" if total_districts > 0 else "N/A",
        )

    with col2:
        st.metric(
            "Average Turnout", f"{avg_turnout:.1f}%" if avg_turnout > 0 else "N/A"
        )

    with col3:
        st.metric(
            "Registered Voters", f"{total_voters:,}" if total_voters > 0 else "N/A"
        )

    with col4:
        st.metric(
            "Political Parties", f"{total_parties:,}" if total_parties > 0 else "N/A"
        )

    # Display party results if available
    if "party_results" in data and isinstance(data["party_results"], pd.DataFrame):
        party_df = data["party_results"].copy()

        if not party_df.empty:
            st.subheader("🏛️ Party Results Overview")

            # Create visualization - single percentage chart
            top_parties = party_df.head(10)

            if len(top_parties) > 0:
                # Check which percentage column exists
                percentage_col = None
                if "votes_percentage" in party_df.columns:
                    percentage_col = "votes_percentage"
                elif "percentage" in party_df.columns:
                    percentage_col = "percentage"

                if percentage_col:
                    fig_pct = px.bar(
                        top_parties,
                        x="party_name",
                        y=percentage_col,
                        title="Vote Share by Party (%)",
                        labels={
                            percentage_col: "Vote Share (%)",
                            "party_name": "Political Party",
                        },
                        text=percentage_col,
                        color_discrete_sequence=["#1f77b4"],
                    )
                    fig_pct.update_xaxes(tickangle=45)
                    fig_pct.update_traces(
                        texttemplate="%{text:.1f}%", textposition="outside"
                    )
                    st.plotly_chart(fig_pct, use_container_width=True)

                # Display results table
                st.subheader("📊 Detailed Results")

                # Prepare display dataframe
                display_df = party_df.copy()

                # Format percentage column
                if percentage_col and percentage_col in display_df.columns:
                    display_df[percentage_col] = display_df[percentage_col].apply(
                        lambda x: f"{x:.2f}%"
                    )

                # Format votes column
                votes_col = None
                if "votes_absolute" in display_df.columns:
                    votes_col = "votes_absolute"
                elif "votes" in display_df.columns:
                    votes_col = "votes"

                if votes_col:
                    display_df[votes_col] = display_df[votes_col].apply(
                        lambda x: f"{x:,}"
                    )

                # Format estimated voters if available
                if "estimated_voters" in display_df.columns:
                    display_df["estimated_voters"] = display_df[
                        "estimated_voters"
                    ].apply(lambda x: f"{x:,}" if pd.notna(x) else "N/A")

                # Rename columns for display
                column_renames = {
                    "party_name": "Party",
                    "list_number": "List #",
                }

                if votes_col:
                    column_renames[votes_col] = "Total Votes"
                if percentage_col:
                    column_renames[percentage_col] = "Percentage"
                if "estimated_voters" in display_df.columns:
                    column_renames["estimated_voters"] = "Est. Voters"

                display_df = display_df.rename(columns=column_renames)

                # Select and reorder columns
                display_cols = []
                if "List #" in display_df.columns:
                    display_cols.append("List #")
                if "Party" in display_df.columns:
                    display_cols.append("Party")
                if "Total Votes" in display_df.columns:
                    display_cols.append("Total Votes")
                if "Est. Voters" in display_df.columns:
                    display_cols.append("Est. Voters")
                if "Percentage" in display_df.columns:
                    display_cols.append("Percentage")

                # Use available columns
                available_cols = [
                    col for col in display_cols if col in display_df.columns
                ]

                if available_cols:
                    st.dataframe(display_df[available_cols], use_container_width=True)

                # Add explanation
                if "estimated_voters" in party_df.columns:
                    seats_used = (
                        party_df["num_seats_used"].iloc[0]
                        if "num_seats_used" in party_df.columns
                        else 41
                    )
                    st.info(
                        f"💡 **Est. Voters** = Total Votes ÷ {seats_used} seats "
                        f"(voters can vote for up to {seats_used} candidates)"
                    )

        else:
            st.warning("No party results data available")

    # Show data source information
    st.subheader("📁 Data Sources Loaded")
    for i, (key, dataset) in enumerate(data.items(), 1):
        if isinstance(dataset, pd.DataFrame):
            st.write(
                f"{i}. **{key}** - CSV Data ({dataset.shape[0]} rows, {dataset.shape[1]} columns)"
            )
        elif isinstance(dataset, dict):
            st.write(f"{i}. **{key}** - Dictionary ({len(dataset)} keys)")
        else:
            st.write(f"{i}. **{key}** - {type(dataset).__name__}")


def display_turnout_analysis(data):
    """Display turnout analysis visualizations using CSV data"""
    st.subheader("📈 Turnout Analysis")

    # Check for district-level turnout data
    if "district_data" in data and isinstance(data["district_data"], pd.DataFrame):
        district_df = data["district_data"]

        # Filter out summary rows and check for meaningful district data
        district_df_filtered = district_df[
            (district_df["district_code"] != "TOTAL")
            & (district_df["turnout_percentage"].notna())
            & (district_df["turnout_percentage"] > 0)
        ]

        if not district_df_filtered.empty:
            # Create turnout visualization
            fig = px.bar(
                district_df_filtered.head(20),  # Show top 20 for readability
                x="district_code",
                y="turnout_percentage",
                title="Voter Turnout by District",
                labels={
                    "turnout_percentage": "Turnout (%)",
                    "district_code": "Electoral District",
                },
            )
            fig.update_xaxes(tickangle=45)
            st.plotly_chart(fig, use_container_width=True)

            # Summary statistics
            col1, col2 = st.columns(2)
            with col1:
                st.metric(
                    "Highest Turnout",
                    f"{district_df_filtered['turnout_percentage'].max():.1f}%",
                )
            with col2:
                st.metric(
                    "Lowest Turnout",
                    f"{district_df_filtered['turnout_percentage'].min():.1f}%",
                )

            # Show district count
            st.metric("Districts with Data", len(district_df_filtered))
        else:
            # Show summary turnout data if available
            summary_row = district_df[district_df["district_code"] == "TOTAL"]
            if not summary_row.empty and summary_row.iloc[0]["turnout_percentage"] > 0:
                turnout_pct = summary_row.iloc[0]["turnout_percentage"]
                st.info(f"Overall Turnout: {turnout_pct:.1f}%")

                # Create a simple single-bar chart
                fig = px.bar(
                    x=["Municipality"],
                    y=[turnout_pct],
                    title="Overall Voter Turnout",
                    labels={"y": "Turnout (%)", "x": "District"},
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No district-level turnout data found.")

    # Show summary statistics from summary_statistics if available
    if "summary_statistics" in data:
        stats = data["summary_statistics"]
        st.subheader("📊 Summary Statistics")

        col1, col2, col3 = st.columns(3)

        if "turnout_percentage" in stats:
            with col1:
                try:
                    turnout_val = float(stats["turnout_percentage"])
                    st.metric("Turnout", f"{turnout_val:.1f}%")
                except (ValueError, TypeError):
                    st.metric("Turnout", f"{stats['turnout_percentage']}%")

        if "registered_voters" in stats:
            with col2:
                try:
                    voters_val = int(float(stats["registered_voters"]))
                    st.metric("Registered Voters", f"{voters_val:,}")
                except (ValueError, TypeError):
                    st.metric("Registered Voters", f"{stats['registered_voters']}")

        if "valid_votes" in stats:
            with col3:
                try:
                    votes_val = int(float(stats["valid_votes"]))
                    st.metric("Valid Votes", f"{votes_val:,}")
                except (ValueError, TypeError):
                    st.metric("Valid Votes", f"{stats['valid_votes']}")

    # If no meaningful data is found, suggest running the analysis pipeline
    if ("district_data" not in data or data["district_data"].empty) and (
        "summary_statistics" not in data or not data["summary_statistics"]
    ):
        st.warning("Run the analysis pipeline first to generate turnout data.")
        st.code("uv run python run_analysis.py")


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
        st.error("Unable to load GeoJSON data. Please check your internet connection.")

        # Add cache clearing option
        col1, col2 = st.columns([3, 1])
        with col1:
            st.info(
                "💡 If you're having repeated issues, try clearing the geographic data cache."
            )
        with col2:
            if st.button(
                "🔄 Clear Cache",
                help="Clear cached geographic data and try downloading again",
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
                    st.success("🗑️ Local cache file deleted!")

                st.success("Cache cleared! Please refresh the page.")
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

    st.info(
        f"Found {len(municipality_features)} electoral districts for this municipality"
    )

    if not municipality_features:
        st.warning(
            "No electoral districts found for this municipality in the geographic data."
        )
        return

    # The geojson_data is already filtered for the selected municipality
    filtered_geojson = geojson_data

    # Map visualization controls
    st.subheader("📊 Map Visualization Controls")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        # Get default from URL or use first option
        viz_options = [
            "Turnout",
            "Estimated Voters",
            "Valid Votes",
            "Valid Votes (dots)",
            "Party Results",
        ]
        default_viz_type = get_param_value(url_params, "viz_type", viz_options[0])
        if default_viz_type not in viz_options:
            default_viz_type = viz_options[0]

        viz_type = st.selectbox(
            "Choose what to visualize:",
            viz_options,
            index=viz_options.index(default_viz_type),
            help="Select the data to display on the map with color coding",
            key="viz_type_select",
        )

    with col2:
        map_options = ["Geographic Map", "Cartogram", "Dot Density"]
        default_map_type = get_param_value(url_params, "map_type", map_options[0])
        if default_map_type not in map_options:
            default_map_type = map_options[0]

        map_type = st.selectbox(
            "Map type:",
            map_options,
            index=map_options.index(default_map_type),
            help="Choose between geographic accuracy, data-proportional areas, or dot-fill visualization",
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
            "Base map style:",
            style_options,
            index=style_options.index(default_style),
            help="Choose a base map style. Muted styles help overlays stand out better.",
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
                    "Select party:",
                    available_parties,
                    index=available_parties.index(default_party),
                    help="Choose which party's results to visualize",
                    key="selected_party_select",
                )
            else:
                st.warning("No party data available")
                viz_type = "Turnout"  # Fallback

    # Update URL parameters when filters change
    update_url_params(
        viz_type=viz_type,
        map_type=map_type,
        base_map_style=base_map_style_main,
        selected_party=selected_party if viz_type == "Party Results" else None,
    )

    # Create and display the map based on type
    if map_type == "Cartogram":
        st.subheader("🗺️ Cartogram View")
        st.info(
            "📐 **Cartogram**: Areas are scaled by **vote count** (larger areas = more total votes). Colors show the selected visualization data. By default, circles stay at true geographic positions - enable collision avoidance if overlap reduction is more important than geographic accuracy."
        )

        # Add base size control
        col_a, col_b, col_c = st.columns([2, 1, 1])
        with col_a:
            st.write("**Adjust Circle Size:**")
        with col_b:
            default_base_size = float(
                get_param_value(url_params, "base_size", "0.0015")
            )
            base_size = st.slider(
                "Base size",
                min_value=0.001,
                max_value=0.005,
                value=default_base_size,
                step=0.0001,
                format="%.10f",
                help="Controls the overall size of circles. Larger values = bigger circles.",
                key="base_size_slider",
            )
        with col_c:
            default_collision = (
                get_param_value(url_params, "collision_avoidance", "false").lower()
                == "true"
            )
            collision_avoidance = st.checkbox(
                "Collision Avoidance",
                value=default_collision,
                help="When enabled, circles are moved to avoid overlaps but may drift from geographic accuracy. When disabled, circles stay at true geographic positions (recommended).",
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
                st.error("Failed to create cartogram map")
        else:
            st.error("Failed to create cartogram data")
    elif map_type == "Dot Density":
        st.subheader("🔵 Dot Density Map")
        st.info(
            "🔵 **Dot Density**: Each dot represents a fixed number of votes (e.g., 1 dot = 100 votes). "
            "Dots are evenly distributed within each electoral district. "
            "When color scaling is enabled, dot colors show vote share: 🔴 red (low) → 🟡 yellow (moderate) → 🟢 green (high). "
            "Choose a muted base map style to make colored dots stand out better. "
            "Count the dots to see vote distribution!"
        )

        # Dot density controls
        col_a, col_b, col_c, col_d = st.columns([1, 1, 1, 1])
        with col_a:
            votes_per_dot_options = [50, 100, 150, 200, 250]
            default_votes_per_dot = int(
                get_param_value(url_params, "votes_per_dot", "100")
            )
            if default_votes_per_dot not in votes_per_dot_options:
                default_votes_per_dot = 100

            votes_per_dot = st.selectbox(
                "Votes per dot:",
                votes_per_dot_options,
                index=votes_per_dot_options.index(default_votes_per_dot),
                help="How many votes each dot represents. Smaller values = more dots = finer detail.",
                key="votes_per_dot_select",
            )
        with col_b:
            default_dot_spacing = int(get_param_value(url_params, "dot_spacing", "70"))
            dot_spacing = st.slider(
                "Dot spacing (meters)",
                min_value=30,
                max_value=120,
                value=default_dot_spacing,
                step=10,
                help="Distance between dots in meters. Affects dot density within districts.",
                key="dot_spacing_slider",
            )
        with col_c:
            default_dot_size = int(get_param_value(url_params, "dot_size", "2"))
            dot_size = st.slider(
                "Dot size",
                min_value=1,
                max_value=5,
                value=default_dot_size,
                help="Visual size of each dot on the map.",
                key="dot_size_slider",
            )
        with col_d:
            default_color_scale = (
                get_param_value(url_params, "use_color_scale", "true").lower() == "true"
            )
            use_color_scale = st.checkbox(
                "Color by vote share",
                value=default_color_scale,
                help="Color dots based on vote share: red (low) to green (high). When disabled, uses single color.",
                key="use_color_scale_checkbox",
            )

        # Update URL parameters for dot density controls
        update_url_params(
            votes_per_dot=votes_per_dot,
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
                    "Could not find district code field (CISLO or cislo) in GeoJSON"
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
                        legend_title = f"{selected_party} Vote Share"
                        legend_type = "Party Performance"
                    else:
                        legend_title = "Turnout Percentage"
                        legend_type = "District Turnout"

                    color_legend_html = f"""
                    <div style="position: fixed; 
                                bottom: 50px; right: 50px; width: 200px; height: auto;
                                background-color: white; border:2px solid grey; z-index:9999; 
                                font-size:11px; font-family: Arial; padding: 8px; box-sizing: border-box;">
                        <h5 style="margin: 0 0 8px 0; font-size: 13px;">Dot Color Scale</h5>
                        <p style="margin: 3px 0; font-weight: bold;">{legend_title}</p>
                        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#00FF00"></i> ≥25% (Excellent)</p>
                        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#32CD32"></i> 20-24% (Very Good)</p>
                        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#228B22"></i> 15-19% (Good)</p>
                        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#FFD700"></i> 10-14% (Moderate)</p>
                        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#FF8C00"></i> 5-9% (Low)</p>
                        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#FF4500"></i> <5% (Very Low)</p>
                        <hr style="margin: 5px 0;">
                        <p style="font-size: 10px; color: #666;">
                            🔵 Dot count = vote quantity<br>
                            🎨 Dot color = {legend_type.lower()}
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
                st.error(f"Error creating dot density map: {e}")
                st.info("Falling back to regular geographic map...")
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
            st.warning("No district data available for dot density visualization.")
            map_data = None
    else:
        st.subheader("🗺️ Geographic Map View")
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
        st.subheader("Selected Okrsek Information")
        clicked_data = map_data["last_object_clicked"]

        # Extract useful information
        properties = clicked_data.get("properties", {})
        district_code = get_district_code_from_geojson(properties) or "Unknown"

        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Okrsek:** {district_code}")
            st.write(f"**Municipality Code:** {properties.get('OBEC', 'Unknown')}")
            st.write(f"**District ID:** {properties.get('KOD', 'Unknown')}")

        with col2:
            # Try to find electoral data for this okrsek
            okrsek_data = district_data[district_data["district_code"] == district_code]
            if not okrsek_data.empty:
                st.write("**Electoral Data:**")
                st.metric(
                    "Turnout", f"{okrsek_data['turnout_percentage'].iloc[0]:.1f}%"
                )
                st.metric(
                    "Registered Voters", f"{okrsek_data['registered_voters'].iloc[0]:,}"
                )
                st.metric("Valid Votes", f"{okrsek_data['valid_votes'].iloc[0]:,}")
            else:
                st.write("*No electoral data available for this okrsek*")

        # Show raw data in expander
        with st.expander("Raw GeoJSON Properties"):
            st.json(properties)

    # Summary statistics
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Electoral Districts on Map", len(municipality_features))

    with col2:
        if district_data is not None and isinstance(district_data, pd.DataFrame):
            unique_districts = (
                len(district_data["district_code"].unique())
                if "district_code" in district_data.columns
                else 0
            )
            st.metric("Districts with Data", unique_districts)
        else:
            st.metric("Electoral Data", "Not Available")

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
            st.metric("Map-Data Matches", matches)
        else:
            st.metric("Map-Data Matches", "N/A")

    # Instructions
    current_viz = viz_type.lower()
    if viz_type == "Party Results" and selected_party:
        current_viz = f"{selected_party} results"

    st.info(
        f"💡 Click on any electoral district on the map to see its electoral data. Currently showing: **{current_viz}**"
    )


def display_data_explorer(data):
    """Allow users to explore the raw data"""
    st.subheader("🔍 Data Explorer")

    if not data:
        st.warning("No data available. Please run the analysis pipeline first.")
        return

    # Data source selector
    selected_source = st.selectbox(
        "Select data source to explore:",
        options=list(data.keys()),
        help="Choose a dataset to explore its contents",
    )

    if selected_source:
        dataset = data[selected_source]

        st.write(f"**Data Type:** {type(dataset).__name__}")

        if isinstance(dataset, pd.DataFrame):
            st.write(f"**Shape:** {dataset.shape}")
            st.dataframe(dataset.head(100))

            # Basic statistics for numeric columns
            numeric_cols = dataset.select_dtypes(include=["number"]).columns
            if len(numeric_cols) > 0:
                st.subheader("Numeric Column Statistics")
                st.dataframe(dataset[numeric_cols].describe())

        elif isinstance(dataset, dict):
            st.write(f"**Keys:** {list(dataset.keys())}")

            # Show a preview of the JSON structure
            with st.expander("View Raw Data (First 1000 characters)"):
                preview = str(dataset)[:1000]
                if len(str(dataset)) > 1000:
                    preview += "..."
                st.text(preview)

        elif isinstance(dataset, list):
            st.write(f"**Length:** {len(dataset)}")
            if len(dataset) > 0:
                st.write(f"**First item type:** {type(dataset[0]).__name__}")
                with st.expander("View First Item"):
                    st.json(dataset[0] if len(dataset) > 0 else {})


def display_district_analysis(data):
    """Display okrsek-level (polling district) analysis and comparisons"""

    has_candidates = bool(data.get("candidates"))
    has_district_data = "district_data" in data and "district_party_results" in data

    if has_candidates:
        st.subheader("👥 Candidate Analysis")
        if not has_district_data:
            st.info(
                "📊 **Parliamentary Election View**\n\n"
                "This electoral district has candidate data but no polling station breakdowns available."
            )

        # Show candidate statistics if available
        if "candidates" in data and data["candidates"]:
            candidates = data["candidates"]
            st.subheader(f"📋 Candidate Statistics")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Candidates", len(candidates))
            with col2:
                candidates_with_mandate = len(
                    [c for c in candidates if c.get("mandate_won", False)]
                )
                st.metric("Candidates Elected", candidates_with_mandate)
            with col3:
                total_pref_votes = sum(
                    c.get("preferential_votes", 0) for c in candidates
                )
                st.metric("Total Preferential Votes", f"{total_pref_votes:,}")

            # Show top candidates by preferential votes
            st.subheader("🏆 Top Candidates by Preferential Votes")
            candidates_sorted = sorted(
                candidates, key=lambda x: x.get("preferential_votes", 0), reverse=True
            )[:20]

            import pandas as pd

            candidates_df = pd.DataFrame(
                [
                    {
                        "Rank": i + 1,
                        "Name": f"{c.get('first_name', '')} {c.get('surname', '')}",
                        "Party": c.get("party_name", "Unknown"),
                        "Preferential Votes": c.get("preferential_votes", 0),
                        "Percentage": f"{c.get('preferential_percentage', 0):.2f}%",
                        "Elected": "✅" if c.get("mandate_won", False) else "❌",
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
        st.warning(
            "District data not available. Please ensure the analysis has been run."
        )
        return

    st.subheader("🏘️ Okrsek (Polling District) Analysis")

    district_df = data["district_data"]
    district_party_df = data["district_party_results"]

    # Filter out summary rows
    district_df_filtered = district_df[district_df["district_code"] != "TOTAL"]

    if district_df_filtered.empty or district_party_df.empty:
        st.warning("No district-level data available for analysis.")
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
    st.subheader("🔎 Okrsek Detail")

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
        "Vyber okrsek:",
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
        col1.metric("Registered Voters", f"{row.get('registered_voters', 0):,}")
        col2.metric("Returned Ballots", f"{row.get('returned_ballots', 0):,}")
        col3.metric("Valid Votes", f"{row.get('valid_votes', 0):,}")
        col4.metric("Turnout", f"{row.get('turnout_percentage', 0):.1f}%")
    else:
        col1.metric("Registered Voters", "N/A")
        col2.metric("Returned Ballots", "N/A")
        col3.metric("Valid Votes", "N/A")
        col4.metric("Turnout", "N/A")

    if station_lookup.get(selected_okrsek):
        station = station_lookup[selected_okrsek]
        st.write(
            f"**Obec:** {station.get('municipality_name', 'Unknown')} "
            f"({station.get('municipality_code', 'Unknown')})"
        )
        st.write(f"**Okres:** {station.get('district_code', 'Unknown')}")

    if not okrsek_party_rows.empty:
        top_parties = okrsek_party_rows.head(15)
        fig_okrsek = px.bar(
            top_parties,
            x="party_name",
            y="votes",
            title=f"Okrsek {selected_okrsek} - Party Results",
            labels={"party_name": "Party", "votes": "Votes"},
            color="votes",
            color_continuous_scale="blues",
        )
        fig_okrsek.update_xaxes(tickangle=45)
        st.plotly_chart(fig_okrsek, use_container_width=True)

        with st.expander("📋 Okrsek Party Results"):
            display_rows = okrsek_party_rows[
                ["party_name", "votes", "percentage"]
            ].copy()
            display_rows["votes"] = display_rows["votes"].apply(lambda x: f"{int(x):,}")
            display_rows["percentage"] = display_rows["percentage"].apply(
                lambda x: f"{x:.2f}%"
            )
            display_rows.columns = ["Party", "Votes", "Percentage"]
            st.dataframe(display_rows, use_container_width=True)
    else:
        st.info("No party results available for this okrsek.")

    # District turnout comparison
    st.subheader("📊 Turnout by Okrsek (Polling District)")

    if "turnout_percentage" in unique_okrseks.columns:
        # Sort by turnout
        unique_okrseks = unique_okrseks.sort_values(
            "turnout_percentage", ascending=False
        )

        col1, col2 = st.columns(2)

        with col1:
            st.metric(
                "Highest Turnout Okrsek",
                f"Okrsek {unique_okrseks.iloc[0]['district_code']}: {unique_okrseks.iloc[0]['turnout_percentage']:.1f}%",
            )

        with col2:
            st.metric(
                "Lowest Turnout Okrsek",
                f"Okrsek {unique_okrseks.iloc[-1]['district_code']}: {unique_okrseks.iloc[-1]['turnout_percentage']:.1f}%",
            )

        # Turnout distribution chart
        top_20_okrseks = unique_okrseks.head(20)
        fig_turnout = px.bar(
            top_20_okrseks,
            x="okrsek_name",
            y="turnout_percentage",
            title="Top 20 Okrseks by Turnout (%)",
            labels={"turnout_percentage": "Turnout (%)", "okrsek_name": "Okrsek"},
            color="turnout_percentage",
            color_continuous_scale="viridis",
        )
        fig_turnout.update_xaxes(tickangle=45)
        st.plotly_chart(fig_turnout, use_container_width=True)

    # Party performance by okrsek
    st.subheader("🎯 Party Performance by Okrsek")

    # Get available parties
    available_parties = district_party_df["party_name"].unique()
    available_parties = [p for p in available_parties if len(p.strip()) > 0]

    if len(available_parties) > 0:
        # Party selector
        selected_party = st.selectbox(
            "Select a party to analyze by okrsek:", available_parties, index=0
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
                        f"Best Okrsek for {selected_party}",
                        f"Okrsek {okrsek_party_data.iloc[0]['district_code']}: {okrsek_party_data.iloc[0]['percentage']:.1f}%",
                    )

                with col2:
                    st.metric(
                        f"Worst Okrsek for {selected_party}",
                        f"Okrsek {okrsek_party_data.iloc[-1]['district_code']}: {okrsek_party_data.iloc[-1]['percentage']:.1f}%",
                    )

                # Chart showing party performance across okrseks
                top_15_party = okrsek_party_data.head(15)
                fig_party = px.bar(
                    top_15_party,
                    x="okrsek_name",
                    y="percentage",
                    title=f"{selected_party} - Performance by Okrsek (%)",
                    labels={"percentage": "Vote Share (%)", "okrsek_name": "Okrsek"},
                    color="percentage",
                    color_continuous_scale="blues",
                )
                fig_party.update_xaxes(tickangle=45)
                st.plotly_chart(fig_party, use_container_width=True)

                # Show detailed table
                with st.expander("📋 Detailed Results Table"):
                    display_party_data = okrsek_party_data[
                        ["okrsek_name", "votes", "percentage", "total_district_votes"]
                    ].copy()
                    display_party_data["votes"] = display_party_data["votes"].apply(
                        lambda x: f"{x:,}"
                    )
                    display_party_data["percentage"] = display_party_data[
                        "percentage"
                    ].apply(lambda x: f"{x:.2f}%")
                    display_party_data["total_district_votes"] = display_party_data[
                        "total_district_votes"
                    ].apply(lambda x: f"{x:,}")
                    display_party_data.columns = [
                        "Okrsek",
                        "Votes",
                        "Percentage",
                        "Total Okrsek Votes",
                    ]
                    st.dataframe(display_party_data, use_container_width=True)

    # Okrsek comparison
    st.subheader("🔍 Okrsek Comparison")

    if len(available_parties) >= 2:
        # Multi-party comparison
        selected_parties = st.multiselect(
            "Select parties to compare across okrseks:",
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
                    title="Party Performance Comparison Across Top Okrseks",
                    labels={
                        "percentage": "Vote Share (%)",
                        "okrsek_name": "Okrsek",
                        "party_name": "Party",
                    },
                    barmode="group",
                )
                fig_comparison.update_xaxes(tickangle=45)
                st.plotly_chart(fig_comparison, use_container_width=True)

    # Summary statistics
    if not unique_okrseks.empty:
        st.subheader("📈 Okrsek Summary Statistics")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Okrseks", len(unique_okrseks))

        with col2:
            avg_turnout = unique_okrseks["turnout_percentage"].mean()
            st.metric("Average Turnout", f"{avg_turnout:.1f}%")

        with col3:
            total_voters = unique_okrseks["registered_voters"].sum()
            st.metric("Total Registered Voters", f"{total_voters:,}")

        with col4:
            total_valid_votes = unique_okrseks["valid_votes"].sum()
            st.metric("Total Valid Votes", f"{total_valid_votes:,}")

        # Additional info about data structure
        st.info(
            f"📍 This election has {len(unique_okrseks)} okrseks (polling districts). Each okrsek represents a physical voting location where residents cast their ballots."
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
        district_code = get_district_code_from_geojson(row) or "Unknown"
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
            <p><strong>Vote Count:</strong> {vote_count:,} votes</p>
            <p><strong>Circle Area:</strong> {area_km2:.2f} km² (proportional)</p>
            <p><strong>Moved Distance:</strong> {moved_distance * 111:.0f}m from original</p>
            <hr>
        """

        if viz_type == "Turnout":
            popup_html += f"<p><strong>Turnout:</strong> {display_value:.1f}%</p>"
        elif viz_type == "Estimated Voters":
            popup_html += (
                f"<p><strong>Registered Voters:</strong> {display_value:,.0f}</p>"
            )
        elif viz_type == "Valid Votes" or viz_type == "Valid Votes (dots)":
            popup_html += f"<p><strong>Valid Votes:</strong> {display_value:,.0f}</p>"
        elif viz_type == "Party Results" and selected_party:
            popup_html += (
                f"<p><strong>{selected_party}:</strong> {display_value:.1f}%</p>"
            )

        popup_html += """
            <hr>
            <p style="font-size: 10px; color: #666;">
                ⭕ Circle size = vote count<br>
                🎨 Circle color = data value<br>
                📍 Position adjusted to avoid overlaps
            </p>
        </div>
        """

        # Style the circle (color based on display_value)
        color = get_color_for_value(display_value, viz_type)

        # Create circle marker with informative tooltip
        tooltip_text = f"Okrsek {district_code}: {vote_count:,} votes"

        # Add display value to tooltip based on visualization type
        if viz_type == "Turnout":
            tooltip_text = f"Okrsek {district_code}: {display_value:.1f}% turnout | {vote_count:,} votes"
        elif viz_type == "Estimated Voters":
            tooltip_text = f"Okrsek {district_code}: {int(display_value):,} voters | {vote_count:,} votes"
        elif viz_type == "Valid Votes":
            tooltip_text = f"Okrsek {district_code}: {int(display_value):,} valid votes"
        elif viz_type == "Party Results" and selected_party:
            tooltip_text = f"Okrsek {district_code}: {display_value:.1f}% {selected_party} | {vote_count:,} votes"

        # Add voter estimate to tooltip if we have electoral data
        if electoral_data and vote_count > 0:
            # Calculate voter estimate (votes ÷ seats available)
            num_seats = get_seat_count(electoral_data)

            if num_seats > 0:
                voter_estimate = round(vote_count / num_seats)
                # Add voter estimate to tooltip based on visualization type
                if viz_type == "Party Results":
                    tooltip_text += f" | ~{voter_estimate:,} voters"
                elif viz_type not in [
                    "Estimated Voters"
                ]:  # Don't duplicate for estimated voters viz
                    tooltip_text += f" | ~{voter_estimate:,} voters"

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
            label_text = f"{display_value:.0f}%"
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
            label_text = f"{display_value:.0f}%"

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
        <h5 style="margin: 0 0 8px 0; font-size: 13px;">Force-Directed Cartogram</h5>
        <p style="margin: 3px 0; font-style: italic; font-weight: bold; font-size: 10px;">
            ⭕ <strong>Circle Size</strong> = Vote Count (proportional)<br>
            🎨 <strong>Circle Color</strong> = {viz_type}<br>
            📍 <strong>Position</strong> = Collision-avoided
        </p>
        <hr style="margin: 5px 0;">
    """

    # Add color legend
    if viz_type == "Turnout":
        legend_html += """
        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#006400"></i> ≥60% turnout</p>
        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#228B22"></i> 50-59%</p>
        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#FFD700"></i> 40-49%</p>
        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#FFA500"></i> 30-39%</p>
        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#FF6347"></i> <30% turnout</p>
        """
    elif viz_type == "Estimated Voters":
        legend_html += """
        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#006400"></i> ≥800 voters</p>
        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#228B22"></i> 600-799</p>
        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#FFD700"></i> 400-599</p>
        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#FFA500"></i> 200-399 (Low-Med)</p>
        <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#FF6347"></i> <200 (Low)</p>
        """
    elif viz_type == "Valid Votes":
        legend_html += """
        <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#2E8B57"></i> ≥1000 (High)</p>
        <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#90EE90"></i> 800-999 (Med-High)</p>
        <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#FFD700"></i> 600-799 (Medium)</p>
        <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#FFA500"></i> 400-599 (Low-Med)</p>
        <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#FF6347"></i> <400 (Low)</p>
        """
    elif viz_type == "Party Results":
        legend_html += f"""
        <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#006400"></i> ≥25% (Very Strong)</p>
        <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#228B22"></i> 20-24% (Strong)</p>
        <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#32CD32"></i> 15-19% (Good)</p>
        <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#FFD700"></i> 10-14% (Moderate)</p>
        <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#87CEEB"></i> 5-9% (Weak)</p>
        <p style="margin: 3px 0;"><i class="fa fa-square" style="color:#4169E1"></i> <5% (Very Weak)</p>
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
            tooltip_suffix = f" | {percentage:.1f}% vote share"
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
                tooltip=f"Okrsek {code}: {votes:,} votes (1 dot = {k_votes_per_dot} votes){tooltip_suffix}",
            )
            features.append(marker)

    # wrap in a feature-group so the layer can be toggled
    fg = folium.FeatureGroup(name=f"Icon fill (1 dot = {k_votes_per_dot} votes)")
    for m in features:
        m.add_to(fg)

    return fg


def main():
    """Main Streamlit application"""

    # Get URL parameters early
    url_params = get_url_params()

    # Header
    st.markdown(
        '<h1 class="main-header">🏛️ Czech Municipalities Electoral Analysis</h1>',
        unsafe_allow_html=True,
    )

    # Sidebar - Election Selection
    st.sidebar.title("⚙️ Settings")

    # Election selector
    st.sidebar.subheader("🗳️ Select Election")

    # Get available elections
    available_elections = get_election_info()
    election_labels = {
        election_id: f"{info['name']} ({info['date'][:4]})"
        for election_id, info in available_elections.items()
    }

    # Create selectbox for elections
    selected_election_id = st.sidebar.selectbox(
        "Election:",
        options=list(election_labels.keys()),
        format_func=lambda x: election_labels[x],
        index=0,  # Default to first election (kv2022)
        key="election_selector",
    )

    # Show election info
    election_info = available_elections[selected_election_id]
    st.sidebar.caption(f"📅 {election_info['name']}")
    st.sidebar.caption(f"📆 Date: {election_info['date']}")

    st.sidebar.markdown("---")

    # Municipality Selection
    st.sidebar.subheader("🏛️ Municipality Selection")

    # Load municipality data and create selector
    municipality_index, comprehensive_data = ensure_data_exists(selected_election_id)

    if not municipality_index or not comprehensive_data:
        return

    # Get default municipality from URL params (we'll handle this via session state if needed)
    default_municipality = get_param_value(url_params, "municipality")
    selected_zastupitelstvo_code = create_municipality_selector(
        municipality_index, comprehensive_data
    )

    # Update URL parameter for municipality selection
    update_url_params(municipality=selected_zastupitelstvo_code)

    if not selected_zastupitelstvo_code:
        st.info(
            "👈 Please select a council election from the sidebar to begin analysis."
        )
        st.markdown("---")

        # Show overall municipalities overview
        st.subheader("📊 Available Analysis Features")
        st.markdown("""
        **Once you select a council election, you'll have access to:**
        
        • **Overview** - Key statistics and party results
        • **Turnout Analysis** - Detailed voter participation analysis  
        • **Geographic Analysis** - Interactive maps and visualizations
        • **Data Explorer** - Detailed data tables and filtering
        • **District Analysis** - Electoral district breakdown
        
        **Select from 6,000+ Czech council elections from the sidebar!**
        
        **Note**: Some areas (like Prague) have multiple elections:
        - **Municipal Council** (OBEC) - Main city/town council
        - **City District Council** (MCMO) - Local district council
        """)
        return

    # Get municipality/district info for title
    municipality_data = get_municipality_data(
        selected_zastupitelstvo_code, comprehensive_data
    )
    municipality_name = "Unknown"
    election_type = "Election"

    # Get election config to determine type
    election_config = get_election_config(selected_election_id)

    if municipality_data:
        metadata = municipality_data.get("metadata", {})

        # Check if parliamentary or municipal
        if election_config.election_type == "parliamentary":
            municipality_name = metadata.get(
                "district_name", f"District {selected_zastupitelstvo_code}"
            )
            election_type = "Parliamentary Election"
        else:
            municipality_name = metadata.get(
                "municipality_name", "Unknown Municipality"
            )

            # Determine specific election type for municipal
            districts = municipality_data.get("district_data", [])
            if districts:
                first_district = districts[0]
                oznac_typu = first_district.get("type", "")

                if oznac_typu == "OBEC":
                    election_type = "Municipal Council Election"
                elif oznac_typu == "MCMO":
                    election_type = "City District Council Election"
            else:
                election_type = "Council Election"

    st.subheader(f"📍 Analysis for: **{municipality_name}** - {election_type}")

    # Load data for selected municipality/zastupitelstvo
    with st.spinner(f"Loading data for {municipality_name} {election_type}..."):
        geojson_data = load_geojson_data(selected_election_id)
        obec_mapping = load_obec_mapping(
            selected_election_id
        )  # For parliamentary elections
        data_version = get_results_data_version(selected_election_id)
        electoral_data = load_municipality_data(
            selected_zastupitelstvo_code, selected_election_id, data_version
        )

    # Analysis Views as prominent tabs with URL parameter support
    tab_options = [
        "Overview",
        "Turnout Analysis",
        "Geographic Analysis",
        "Data Explorer",
        "District Analysis",
    ]

    # Get default tab from URL params
    default_tab = get_param_value(url_params, "tab", tab_options[0])
    if default_tab not in tab_options:
        default_tab = tab_options[0]

    # Create a selectbox for tab selection that updates URL immediately
    st.subheader("📊 Select Analysis View")
    selected_tab = st.selectbox(
        "Choose analysis view:",
        tab_options,
        index=tab_options.index(default_tab),
        key="main_tab_selector",
        help="Select which analysis view to display. URL will update automatically for sharing.",
    )

    # Update URL parameter for tab selection immediately when selection changes
    update_url_params(tab=selected_tab)

    # Add some visual separation
    st.markdown("---")

    # Sidebar info - simplified
    st.sidebar.markdown("---")

    # Quick stats in sidebar
    if electoral_data:
        st.sidebar.subheader("📈 Quick Stats")
        if "summary_statistics" in electoral_data:
            stats = electoral_data["summary_statistics"]
            st.sidebar.metric(
                "Electoral Districts", stats.get("electoral_districts", "N/A")
            )
            st.sidebar.metric(
                "Registered Voters", f"{stats.get('registered_voters', 0):,}"
            )
            st.sidebar.metric("Turnout %", f"{stats.get('turnout_percentage', 0):.1f}%")

        st.sidebar.metric("Data Sources Loaded", len(electoral_data))

    # Add URL sharing info in sidebar
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔗 Share This Analysis")
    st.sidebar.info(
        "💡 The URL automatically updates with your filter settings. Copy and share the link to let others see the same view!"
    )

    # For geographic analysis, we need to map zastupitelstvo_code to geographic municipality code
    # since the GeoJSON uses different codes (CIS_OBEC vs KODZASTUP)
    geographic_municipality_codes = [
        selected_zastupitelstvo_code
    ]  # Start with zastupitelstvo code

    # For city-wide elections (like Praha), we need to collect ALL municipality codes from districts
    if municipality_data:
        metadata = municipality_data.get("metadata", {})
        districts = municipality_data.get("district_data", [])

        # If we have district data, collect ALL unique CIS_OBEC codes from the districts
        if districts:
            # Get all unique CIS_OBEC codes from all districts
            unique_cis_obec_codes = set()
            for district in districts:
                cis_obec = district.get("municipality_code")
                if cis_obec:
                    unique_cis_obec_codes.add(cis_obec)

            # Add all unique codes to our search list
            geographic_municipality_codes.extend(list(unique_cis_obec_codes))

    if geojson_data and "features" in geojson_data:
        # Filter geojson for this municipality using MOMC field (electoral municipality code)
        municipality_districts = []
        for feature in geojson_data["features"]:
            props = feature.get("properties", {})
            # Try matching against any of our geographic codes
            if props.get("MOMC") in geographic_municipality_codes:
                municipality_districts.append(feature)

        if municipality_districts:
            st.sidebar.metric("Geographic Districts Found", len(municipality_districts))
        else:
            # Try a different approach - look for matching district codes in the electoral data
            if electoral_data and "district_data" in electoral_data:
                electoral_districts = electoral_data["district_data"]
                if hasattr(electoral_districts, "index"):  # It's a DataFrame
                    district_codes = electoral_districts["district_code"].tolist()
                else:  # It's a list of dicts
                    district_codes = [
                        d.get("district_code", "") for d in electoral_districts
                    ]

                # Try to find matching districts by district code
                for feature in geojson_data["features"]:
                    props = feature.get("properties", {})
                    if props.get("CISLO_OKRS") in district_codes:
                        municipality_districts.append(feature)

                if municipality_districts:
                    st.sidebar.metric(
                        "Geographic Districts Found (by district match)",
                        len(municipality_districts),
                    )

    # Display content based on selected tab
    if selected_tab == "Overview":
        st.header("📊 Electoral Overview")
        display_electoral_overview(electoral_data)

    elif selected_tab == "Turnout Analysis":
        st.header("📈 Turnout Analysis")
        display_turnout_analysis(electoral_data)

    elif selected_tab == "Geographic Analysis":
        st.header("🗺️ Geographic Analysis")
        # Optional municipal-part filter for parliamentary elections
        election_config = get_election_config(selected_election_id)
        is_parliamentary = election_config.election_type == "parliamentary"
        geographic_electoral_data = electoral_data
        selected_polling_stations = None
        selected_geo_obec = get_param_value(url_params, "geo_obec", "ALL")

        if (
            is_parliamentary
            and electoral_data
            and "polling_stations" in electoral_data
            and electoral_data["polling_stations"]
        ):
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

            if selected_geo_obec not in municipality_codes and selected_geo_obec != "ALL":
                selected_geo_obec = "ALL"

            selected_geo_obec = st.selectbox(
                "Filter municipality (optional):",
                ["ALL"] + municipality_codes,
                index=(["ALL"] + municipality_codes).index(selected_geo_obec),
                format_func=lambda code: "All municipalities in district"
                if code == "ALL"
                else f"{municipality_map.get(code) or 'Unknown'} ({code})",
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
                    f"Filter applied: {municipality_map.get(selected_geo_obec) or 'Unknown'} "
                    f"({selected_geo_obec}) - {len(selected_polling_stations)} polling stations"
                )
            else:
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
        if geojson_data and "features" in geojson_data:
            municipality_districts = []

            # For parliamentary elections, use OBEC mapping
            if is_parliamentary and obec_mapping:
                # For parliamentary elections, selected_zastupitelstvo_code is actually an electoral district number (1-14)
                # But we need to match polling stations by OBEC code
                # We need to get all polling stations from the electoral data
                if selected_polling_stations:
                    polling_stations = selected_polling_stations

                    # Extract unique OBEC codes from polling stations
                    obec_codes = set()
                    for station in polling_stations:
                        obec_code = station.get("municipality_code", "")
                        if obec_code:
                            obec_codes.add(str(obec_code))

                    geojson_kod_mco_codes = set()
                    for feature in geojson_data["features"]:
                        props = feature.get("properties", {})
                        kod_mco = props.get("kod_mco")
                        if kod_mco:
                            geojson_kod_mco_codes.add(str(kod_mco))

                    target_mco_codes = {
                        code for code in obec_codes if code in geojson_kod_mco_codes
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

                    # Match GeoJSON features using kod_mco when possible, fallback to kod_obec
                    for feature in geojson_data["features"]:
                        props = feature.get("properties", {})
                        kod_mco = props.get("kod_mco", "")
                        kod_obec = props.get("kod_obec", "")

                        if kod_mco and str(kod_mco) in target_mco_codes:
                            municipality_districts.append(feature)
                        elif kod_obec and str(kod_obec) in target_obec_codes:
                            municipality_districts.append(feature)

                    st.info(
                        f"📍 Parliamentary Elections: Matched {len(municipality_districts)} polling stations from {len(obec_codes)} municipalities"
                    )
                else:
                    st.warning(
                        "⚠️ No polling station data found for parliamentary elections"
                    )

            # For municipal elections, use traditional matching strategies
            else:
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
                st.subheader("🗺️ Geographic Analysis - Debugging Municipality Match")
                st.warning(
                    f"📍 **No geographic boundaries found** for {municipality_name}"
                )

                # Show detailed debugging info
                with st.expander("🔧 Detailed Matching Analysis", expanded=True):
                    st.write(f"**Municipality:** {municipality_name}")
                    st.write(f"**Zastupitelstvo Code:** {selected_zastupitelstvo_code}")
                    st.write(
                        f"**Municipality Codes Searched:** {geographic_municipality_codes}"
                    )

                    # Sample some GeoJSON features to understand the structure
                    if geojson_data and "features" in geojson_data:
                        st.write(
                            f"**Total GeoJSON Features:** {len(geojson_data.get('features', []))}"
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
                            st.write("**Sample MOMC codes:**")
                            st.write(sorted(list(momc_codes))[:10])
                        with col2:
                            st.write("**Sample OBEC codes:**")
                            st.write(sorted(list(obec_codes))[:10])
                        with col3:
                            st.write("**Sample CIS_OBEC codes:**")
                            st.write(sorted(list(cis_obec_codes))[:10])

                        # Show a sample feature structure
                        st.write("**Sample GeoJSON feature properties:**")
                        if sample_features:
                            sample_props = sample_features[0].get("properties", {})
                            st.json(
                                dict(list(sample_props.items())[:10])
                            )  # Show first 10 properties

                    st.info(
                        "**This suggests that the municipality codes in our electoral data don't match "
                        "the codes used in the GeoJSON boundary data.** This is a common issue when "
                        "different Czech government systems use different coding schemes.\n\n"
                        "**Available analysis for this municipality:**\n"
                        "• Overview - Party results and statistics\n"
                        "• Turnout Analysis - Voter participation data\n"
                        "• Data Explorer - Raw electoral data\n"
                        "• District Analysis - Polling district breakdown"
                    )

        display_geographic_analysis(
            municipality_geojson, geographic_electoral_data, selected_election_id
        )

    elif selected_tab == "Data Explorer":
        st.header("🔍 Data Explorer")
        display_data_explorer(electoral_data)

    elif selected_tab == "District Analysis":
        st.header("🏘️ District Analysis")
        display_district_analysis(electoral_data)

    # Footer
    st.markdown("---")
    st.markdown(
        f"**Czech Municipalities Electoral Analysis** | "
        f"**{municipality_name}** | "
        "Built with Streamlit | "
        f"Data sources: {len(electoral_data)} loaded"
    )


if __name__ == "__main__":
    main()

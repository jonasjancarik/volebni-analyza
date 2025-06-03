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

from src.streamlit_municipality_selector import MunicipalitySelector

# Configure Streamlit page
st.set_page_config(
    page_title="Czech Municipalities Electoral Analysis",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown(
    """
<style>
    .main-header {
        font-size: 2.5em;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 20px;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
    }
    .sidebar .sidebar-content {
        background-color: #fafafa;
    }
</style>
""",
    unsafe_allow_html=True,
)


@st.cache_data
def load_geojson_data():
    """Download and cache GeoJSON data for electoral districts to local disk"""
    # Local cache file path
    cache_file = Path("input/raw/electoral_districts_boundaries.geojson")
    cache_file.parent.mkdir(parents=True, exist_ok=True)

    # Check if file already exists
    if cache_file.exists():
        try:
            st.info("📁 Loading electoral districts from local cache...")
            with open(cache_file, "r", encoding="utf-8") as f:
                geojson_data = json.load(f)

            # Validate the cached data
            if (
                isinstance(geojson_data, dict)
                and geojson_data.get("type") == "FeatureCollection"
            ):
                features = geojson_data.get("features", [])
                if features:
                    st.success(
                        f"✅ Loaded {len(features):,} electoral districts from cache"
                    )
                    return geojson_data

            st.warning("⚠️ Cached file appears corrupted, re-downloading...")

        except Exception as e:
            st.warning(f"⚠️ Error reading cached file: {e}. Re-downloading...")

    # Download the file
    url = "https://www.volby.cz/opendata/kv2022/geo/vol_okrsky_2022g100.geojson"

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
def load_municipality_data(zastupitelstvo_code: str):
    """Load processed election data for a specific zastupitelstvo (council election)"""
    if not zastupitelstvo_code:
        return {}

    # Load from our all municipalities data using zastupitelstvo_code
    selector = MunicipalitySelector()
    municipality_data = selector.get_municipality_data(zastupitelstvo_code)

    if not municipality_data:
        st.error(f"No data found for zastupitelstvo {zastupitelstvo_code}")
        return {}

    # Convert to format expected by visualization functions
    converted_data = {}

    # Convert party results
    party_results = municipality_data.get("party_results", [])
    if party_results:
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

    # Convert district data
    district_data = municipality_data.get("district_data", [])
    if district_data:
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
    converted_data["summary_statistics"] = stats

    # Create district party results
    district_party_results = []
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
                    "percentage": (votes / total_votes * 100) if total_votes > 0 else 0,
                }
            )

    if district_party_results:
        converted_data["district_party_results"] = pd.DataFrame(district_party_results)

    return converted_data


def create_folium_map(
    geojson_data, electoral_data=None, viz_type="Turnout", selected_party=None
):
    """Create an interactive Folium map with electoral districts and optional data overlay"""

    # Calculate map center from geojson data
    map_center = [50.0755, 14.4378]  # Default to Prague center
    zoom_start = 10

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

            # Calculate appropriate zoom level based on area
            lat_range = max(lats) - min(lats)
            lon_range = max(lons) - min(lons)
            max_range = max(lat_range, lon_range)

            if max_range < 0.01:  # Very small area
                zoom_start = 15
            elif max_range < 0.05:  # Small area
                zoom_start = 13
            elif max_range < 0.1:  # Medium area
                zoom_start = 12
            elif max_range < 0.5:  # Large area
                zoom_start = 10
            else:  # Very large area
                zoom_start = 8

    m = folium.Map(location=map_center, zoom_start=zoom_start, tiles="OpenStreetMap")

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
            district_code = properties.get("CISLO", "")

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
            district_code = properties.get("CISLO", "Unknown")

            popup_html = f"""
            <div style="font-family: Arial; width: 220px;">
                <h4 style="margin-bottom: 10px; color: #1f77b4;">Okrsek {district_code}</h4>
                <hr style="margin: 5px 0;">
            """

            # Add data based on visualization type
            if district_code in viz_data:
                value = viz_data[district_code]

                if viz_type == "Turnout":
                    popup_html += f"<p><strong>Turnout:</strong> {value:.1f}%</p>"
                elif viz_type == "Estimated Voters":
                    popup_html += (
                        f"<p><strong>Registered Voters:</strong> {value:,}</p>"
                    )
                elif viz_type == "Party Results":
                    popup_html += (
                        f"<p><strong>{selected_party}:</strong> {value:.1f}%</p>"
                    )

                # Add additional context data
                if district_data is not None:
                    okrsek_rows = district_data[
                        district_data["district_code"] == str(district_code)
                    ]
                    if not okrsek_rows.empty:
                        row = okrsek_rows.iloc[0]

                        if (
                            viz_type != "Turnout"
                            and "turnout_percentage" in row
                            and pd.notna(row["turnout_percentage"])
                        ):
                            popup_html += f"<p><strong>Turnout:</strong> {row['turnout_percentage']:.1f}%</p>"
                        if (
                            viz_type != "Estimated Voters"
                            and "registered_voters" in row
                            and pd.notna(row["registered_voters"])
                        ):
                            popup_html += f"<p><strong>Registered Voters:</strong> {int(row['registered_voters']):,}</p>"
                        if "valid_votes" in row and pd.notna(row["valid_votes"]):
                            popup_html += f"<p><strong>Valid Votes:</strong> {int(row['valid_votes']):,}</p>"
            else:
                popup_html += f"<p><em>No {viz_type.lower()} data available</em></p>"

            popup_html += f"""
                <hr style="margin: 5px 0;">
                <p style="font-size: 10px; color: #666;">Click for more details</p>
            </div>
            """

            return popup_html

        # Add GeoJSON layer with data styling
        for feature in geojson_data["features"]:
            popup_content = create_popup_content(feature)

            folium.GeoJson(
                feature,
                style_function=style_function,
                popup=folium.Popup(popup_content, max_width=300),
                tooltip=folium.Tooltip(
                    f"Okrsek {feature.get('properties', {}).get('CISLO', 'Unknown')}"
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
            (district_df["district_id"] != "TOTAL")
            & (district_df["turnout_percentage"].notna())
            & (district_df["turnout_percentage"] > 0)
        ]

        if not district_df_filtered.empty:
            # Create turnout visualization
            fig = px.bar(
                district_df_filtered.head(20),  # Show top 20 for readability
                x="district_name",
                y="turnout_percentage",
                title="Voter Turnout by District",
                labels={
                    "turnout_percentage": "Turnout (%)",
                    "district_name": "Electoral District",
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
            summary_row = district_df[district_df["district_id"] == "TOTAL"]
            if not summary_row.empty and summary_row.iloc[0]["turnout_percentage"] > 0:
                turnout_pct = summary_row.iloc[0]["turnout_percentage"]
                st.info(f"Overall Prague 5 Turnout: {turnout_pct:.1f}%")

                # Create a simple single-bar chart
                fig = px.bar(
                    x=["Praha 5"],
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


def display_geographic_analysis(geojson_data, electoral_data=None):
    """Display geographic analysis with filtered electoral districts map for the selected municipality"""
    st.subheader("🗺️ Geographic Analysis - Municipality Districts")

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
                cache_file = Path("input/raw/electoral_districts_boundaries.geojson")
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

    col1, col2, col3 = st.columns(3)

    with col1:
        viz_type = st.selectbox(
            "Choose what to visualize:",
            ["Turnout", "Estimated Voters", "Valid Votes", "Party Results"],
            help="Select the data to display on the map with color coding",
        )

    with col2:
        map_type = st.selectbox(
            "Map type:",
            ["Geographic Map", "Cartogram"],
            help="Choose between geographic accuracy or data-proportional areas",
        )

    selected_party = None
    if viz_type == "Party Results" and party_data is not None:
        with col3:
            # Get available parties
            available_parties = (
                sorted(party_data["party_name"].unique())
                if isinstance(party_data, pd.DataFrame)
                else []
            )
            if available_parties:
                selected_party = st.selectbox(
                    "Select party:",
                    available_parties,
                    help="Choose which party's results to visualize",
                )
            else:
                st.warning("No party data available")
                viz_type = "Turnout"  # Fallback

    # Create and display the map based on type
    if map_type == "Cartogram":
        st.subheader("🗺️ Cartogram View")
        st.info(
            "📐 **Cartogram**: Areas are scaled by **vote count** (larger areas = more total votes). Colors show the selected visualization data."
        )

        # Add base size control
        col_a, col_b = st.columns([2, 1])
        with col_a:
            st.write("**Adjust Circle Size:**")
        with col_b:
            base_size = st.slider(
                "Base size",
                min_value=0.001,
                max_value=0.005,
                value=0.002,
                step=0.0001,
                format="%.3f",
                help="Controls the overall size of circles. Larger values = bigger circles.",
            )

        # Create cartogram
        cartogram_gdf = create_cartogram(
            filtered_geojson, electoral_data, viz_type, selected_party, base_size
        )

        if cartogram_gdf is not None:
            cartogram_map = create_cartogram_map(
                cartogram_gdf, viz_type, selected_party
            )

            if cartogram_map:
                # Display the cartogram map
                map_data = st_folium(
                    cartogram_map,
                    width=None,  # Full width
                    height=900,  # Taller map
                    returned_objects=["last_clicked", "last_object_clicked"],
                    key=f"cartogram_{viz_type}_{selected_party}_{base_size}",  # Include base_size in key
                )
            else:
                st.error("Failed to create cartogram map")
        else:
            st.error("Failed to create cartogram data")
    else:
        st.subheader("🗺️ Geographic Map View")
        # Create and display the regular map
        map_obj = create_folium_map(
            filtered_geojson, electoral_data, viz_type, selected_party
        )

        # Display the map
        map_data = st_folium(
            map_obj,
            width=None,  # Full width
            height=900,  # Taller map
            returned_objects=["last_clicked", "last_object_clicked"],
            key=f"map_{viz_type}_{selected_party}",  # Unique key for re-rendering
        )

    # Display information about clicked features
    if map_data and map_data.get("last_object_clicked"):
        st.subheader("Selected Okrsek Information")
        clicked_data = map_data["last_object_clicked"]

        # Extract useful information
        properties = clicked_data.get("properties", {})
        district_code = properties.get("CISLO", "Unknown")

        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Okrsek:** {district_code}")
            st.write(f"**Municipality Code:** {properties.get('OBEC', 'Unknown')}")
            st.write(f"**District ID:** {properties.get('KOD', 'Unknown')}")

        with col2:
            # Try to find electoral data for this okrsek
            if district_data is not None and isinstance(district_data, pd.DataFrame):
                # Filter district data for this okrsek
                okrsek_data = district_data[
                    district_data["district_code"] == str(district_code)
                ]

                if not okrsek_data.empty:
                    # Get first row (or aggregate if multiple)
                    data_row = okrsek_data.iloc[0]

                    st.write("**Electoral Data:**")
                    if "turnout_percentage" in data_row:
                        st.metric("Turnout", f"{data_row['turnout_percentage']:.1f}%")
                    if "registered_voters" in data_row:
                        st.metric(
                            "Registered Voters", f"{data_row['registered_voters']:,}"
                        )
                    if "valid_votes" in data_row:
                        st.metric("Valid Votes", f"{data_row['valid_votes']:,}")
                else:
                    st.write("*No electoral data available for this okrsek*")

            # Show party results for this okrsek if available
            if party_data is not None and isinstance(party_data, pd.DataFrame):
                okrsek_party_data = party_data[
                    party_data["district_id"].str.startswith(str(district_code) + "-")
                ]

                if not okrsek_party_data.empty:
                    # Aggregate party results for this okrsek
                    party_summary = (
                        okrsek_party_data.groupby("party_name")["votes"]
                        .sum()
                        .sort_values(ascending=False)
                    )

                    st.write("**Top 3 Parties in this Okrsek:**")
                    for i, (party, votes) in enumerate(party_summary.head(3).items()):
                        total_votes = (
                            okrsek_party_data["total_district_votes"].iloc[0]
                            if not okrsek_party_data.empty
                            else 1
                        )
                        pct = (votes / total_votes * 100) if total_votes > 0 else 0
                        st.write(f"{i + 1}. {party}: {votes:,} votes ({pct:.1f}%)")

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
                f.get("properties", {}).get("CISLO", "") for f in municipality_features
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
    st.subheader("🏘️ Okrsek (Polling District) Analysis")

    if "district_data" not in data or "district_party_results" not in data:
        st.warning(
            "District data not available. Please ensure the analysis has been run."
        )
        return

    district_df = data["district_data"]
    district_party_df = data["district_party_results"]

    # Filter out summary rows
    district_df_filtered = district_df[district_df["district_id"] != "TOTAL"]

    if district_df_filtered.empty or district_party_df.empty:
        st.warning("No district-level data available for analysis.")
        return

    # Extract district codes from district_id (e.g., "5001-1" -> "5001")
    district_df_filtered = district_df_filtered.copy()
    district_df_filtered["district_code"] = (
        district_df_filtered["district_id"].str.split("-").str[0]
    )

    district_party_df = district_party_df.copy()
    district_party_df["district_code"] = (
        district_party_df["district_id"].str.split("-").str[0]
    )

    # Get unique okrseks (use district_code as the unique identifier for polling districts)
    # Each district_code represents a physical polling location/okrsek
    unique_okrseks = district_df_filtered.groupby("district_code").first().reset_index()
    unique_okrseks["okrsek_name"] = unique_okrseks["district_code"].apply(
        lambda x: f"Okrsek {x}"
    )

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
            f"📍 Prague 5 has {len(unique_okrseks)} okrseks (polling districts). Each okrsek represents a physical voting location where residents cast their ballots."
        )


def create_cartogram(
    geojson_data,
    electoral_data,
    viz_type="Turnout",
    selected_party=None,
    base_size=0.002,
):
    """Create a force-directed cartogram with areas proportional to vote counts and collision avoidance"""
    if not geojson_data or "features" not in geojson_data:
        return None

    # Get Prague 5 features
    prague5_features = []
    prague5_municipality_code = "554782"

    for feature in geojson_data["features"]:
        properties = feature.get("properties", {})
        if properties.get("OBEC") == prague5_municipality_code:
            cislo = properties.get("CISLO", "")
            try:
                district_num = int(cislo)
                if 5001 <= district_num <= 5081:
                    prague5_features.append(feature)
            except (ValueError, TypeError):
                continue

    if not prague5_features:
        return None

    # Convert to GeoDataFrame
    gdf = gpd.GeoDataFrame.from_features(prague5_features)
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

    # Create cartogram with direct proportionality and collision avoidance
    cartogram_gdf = gdf.copy()

    # Calculate areas directly proportional to vote counts
    min_votes = min(vote_counts.values())
    max_votes = max(vote_counts.values())

    # Set a base radius for the smallest district
    base_radius = base_size
    max_radius = base_radius * 4  # Restore reasonable maximum size

    # Store centroid positions and radii for collision detection
    districts = []

    for idx, row in cartogram_gdf.iterrows():
        district_code = row["district_code"]
        original_centroid = row.geometry.centroid

        if district_code in vote_counts:
            votes = vote_counts[district_code]
            # Direct proportionality: area proportional to votes
            # Area = π * r², so r = sqrt(area/π) = sqrt(votes * scale / π)
            scale_factor = votes / min_votes  # Direct ratio
            radius = base_radius * np.sqrt(scale_factor)
            radius = min(radius, max_radius)  # Cap maximum size
            radius = max(radius, base_radius * 0.7)  # Reasonable minimum size

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
                forces[d["idx"]]["fx"] += (d["original_x"] - d["x"]) * attraction_force
                forces[d["idx"]]["fy"] += (d["original_y"] - d["y"]) * attraction_force

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

    # Apply force-directed positioning
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


def create_cartogram_map(cartogram_gdf, viz_type="Turnout", selected_party=None):
    """Create a Folium map from cartogram GeoDataFrame with circular districts"""
    if cartogram_gdf is None or cartogram_gdf.empty:
        return None

    # Calculate map center
    bounds = cartogram_gdf.total_bounds
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2

    m = folium.Map(
        location=[center_lat, center_lon], zoom_start=12, tiles="OpenStreetMap"
    )

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
        district_code = row.get("CISLO", "Unknown")
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
        elif viz_type == "Valid Votes":
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

        # Create circle marker
        folium.Circle(
            location=[row.geometry.centroid.y, row.geometry.centroid.x],
            radius=radius * 111000,  # Convert degrees to meters approximately
            popup=folium.Popup(popup_html, max_width=320),
            tooltip=folium.Tooltip(f"Okrsek {district_code}: {vote_count:,} votes"),
            color="black",
            weight=2,
            fillColor=color,
            fillOpacity=0.7,
        ).add_to(m)

        # Add district label
        folium.Marker(
            location=[row.geometry.centroid.y, row.geometry.centroid.x],
            icon=folium.DivIcon(
                html=f'<div style="font-size: 10px; color: white; font-weight: bold; text-shadow: 1px 1px 1px black;">{district_code}</div>',
                icon_size=(50, 20),
                icon_anchor=(25, 10),
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
        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#FFA500"></i> 200-399</p>
        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#FF6347"></i> <200 voters</p>
        """
    elif viz_type == "Valid Votes":
        legend_html += """
        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#006400"></i> ≥1000 votes</p>
        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#228B22"></i> 800-999</p>
        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#FFD700"></i> 600-799</p>
        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#FFA500"></i> 400-599</p>
        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#FF6347"></i> <400 votes</p>
        """
    elif viz_type == "Party Results":
        legend_html += """
        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#006400"></i> ≥25% support</p>
        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#228B22"></i> 20-24%</p>
        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#32CD32"></i> 15-19%</p>
        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#FFD700"></i> 10-14%</p>
        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#87CEEB"></i> 5-9%</p>
        <p style="margin: 2px 0;"><i class="fa fa-circle" style="color:#4169E1"></i> <5% support</p>
        """

    legend_html += "</div>"

    m.get_root().html.add_child(folium.Element(legend_html))

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


def main():
    """Main Streamlit application"""

    # Header
    st.markdown(
        '<h1 class="main-header">🏛️ Czech Municipalities Electoral Analysis</h1>',
        unsafe_allow_html=True,
    )

    # Municipality Selection
    st.sidebar.title("🏛️ Election Selection")
    st.sidebar.markdown("---")

    # Initialize municipality selector
    selector = MunicipalitySelector()
    selected_zastupitelstvo_code = selector.create_municipality_selector()

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

    # Get municipality info for title
    municipality_data = selector.get_municipality_data(selected_zastupitelstvo_code)
    municipality_name = "Unknown Municipality"
    election_type = "Council Election"

    if municipality_data:
        metadata = municipality_data.get("metadata", {})
        municipality_name = metadata.get("municipality_name", "Unknown Municipality")

        # Determine election type
        districts = municipality_data.get("district_data", [])
        if districts:
            first_district = districts[0]
            oznac_typu = first_district.get("type", "")

            if oznac_typu == "OBEC":
                election_type = "Municipal Council Election"
            elif oznac_typu == "MCMO":
                election_type = "City District Council Election"

    st.subheader(f"📍 Analysis for: **{municipality_name}** - {election_type}")

    # Navigation
    st.sidebar.markdown("---")
    st.sidebar.title("📊 Analysis Views")
    page = st.sidebar.selectbox(
        "Choose a view:",
        [
            "Overview",
            "Turnout Analysis",
            "Geographic Analysis",
            "Data Explorer",
            "District Analysis",
        ],
    )

    # Load data for selected municipality/zastupitelstvo
    with st.spinner(f"Loading data for {municipality_name} {election_type}..."):
        geojson_data = load_geojson_data()
        electoral_data = load_municipality_data(selected_zastupitelstvo_code)

    # Sidebar info
    st.sidebar.markdown("---")
    st.sidebar.info(
        "This dashboard visualizes electoral data for Czech council elections. "
        "Use the election selector above to switch between different councils and election types."
    )

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

    # Main content based on navigation
    if page == "Overview":
        display_electoral_overview(electoral_data)

    elif page == "Turnout Analysis":
        display_turnout_analysis(electoral_data)

    elif page == "Geographic Analysis":
        # Filter geojson for this municipality
        municipality_geojson = None
        if geojson_data and "features" in geojson_data:
            municipality_districts = []
            for feature in geojson_data["features"]:
                props = feature.get("properties", {})
                # Try matching against any of our geographic codes
                if props.get("MOMC") in geographic_municipality_codes:
                    municipality_districts.append(feature)

            if municipality_districts:
                municipality_geojson = {
                    "type": "FeatureCollection",
                    "features": municipality_districts,
                }
                st.sidebar.success(
                    f"✅ Found {len(municipality_districts)} districts for mapping"
                )
            else:
                st.sidebar.warning(
                    f"⚠️ No geographic districts found for municipality {selected_zastupitelstvo_code}"
                )
                # Show debugging info
                st.sidebar.write(f"**Debug Info:**")
                st.sidebar.write(f"Zastupitelstvo Code: {selected_zastupitelstvo_code}")
                st.sidebar.write(f"Geographic Codes: {geographic_municipality_codes}")

        display_geographic_analysis(municipality_geojson, electoral_data)

    elif page == "Data Explorer":
        display_data_explorer(electoral_data)

    elif page == "District Analysis":
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

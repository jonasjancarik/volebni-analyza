#!/usr/bin/env python3
"""
Prague 5 Election Analysis - Streamlit Dashboard
Interactive visualization dashboard for electoral analysis
"""

import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
import json
import requests
import re
from pathlib import Path
import sys
import os

# Add src to path for importing our modules
sys.path.append(str(Path(__file__).parent / "src"))

# Configure Streamlit page
st.set_page_config(
    page_title="Prague 5 Electoral Analysis Dashboard",
    page_icon="🗳️",
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
    """Download and cache GeoJSON data for electoral districts"""
    url = "https://www.volby.cz/opendata/kv2022/geo/vol_okrsky_2022g100.geojson"

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Failed to download GeoJSON data: {e}")
        return None


@st.cache_data
def load_processed_data():
    """Load processed election data from CSV files"""
    csv_dir = "output/csv"

    if not os.path.exists(csv_dir):
        st.error(f"CSV data directory not found: {csv_dir}")
        st.info("Run the data conversion: `uv run python src/data_exporters.py`")
        return {}

    data = {}

    # Load party results
    party_file = os.path.join(csv_dir, "party_results.csv")
    if os.path.exists(party_file):
        try:
            data["party_results"] = pd.read_csv(party_file)
            st.success(f"✅ Loaded {len(data['party_results'])} parties from CSV")
        except Exception as e:
            st.error(f"Failed to load party results: {e}")

    # Load district data
    district_file = os.path.join(csv_dir, "district_data.csv")
    if os.path.exists(district_file):
        try:
            data["district_data"] = pd.read_csv(district_file)
            st.success(f"✅ Loaded {len(data['district_data'])} districts from CSV")
        except Exception as e:
            st.error(f"Failed to load district data: {e}")

    # Load summary statistics
    summary_file = os.path.join(csv_dir, "summary_statistics.csv")
    if os.path.exists(summary_file):
        try:
            summary_df = pd.read_csv(summary_file)
            # Convert summary to dictionary format for compatibility
            data["summary_statistics"] = {}
            for _, row in summary_df.iterrows():
                if row["category"] == "statistics":
                    data["summary_statistics"][row["metric"]] = row["value"]
            st.success(f"✅ Loaded summary statistics from CSV")
        except Exception as e:
            st.error(f"Failed to load summary statistics: {e}")

    # Load district party results
    district_party_file = os.path.join(csv_dir, "district_party_results.csv")
    if os.path.exists(district_party_file):
        try:
            data["district_party_results"] = pd.read_csv(district_party_file)
            st.success(
                f"✅ Loaded {len(data['district_party_results'])} district-party combinations from CSV"
            )
        except Exception as e:
            st.error(f"Failed to load district party results: {e}")

    return data


def create_folium_map(
    geojson_data, electoral_data=None, viz_type="Turnout", selected_party=None
):
    """Create an interactive Folium map with electoral districts and optional data overlay"""
    # Center on Prague 5 (more specific location)
    prague5_center = [50.0705, 14.4132]  # Prague 5 center

    m = folium.Map(location=prague5_center, zoom_start=13, tiles="OpenStreetMap")

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
                fig_pct = px.bar(
                    top_parties,
                    x="party_name",
                    y="votes_percentage",
                    title="Vote Share by Party (%)",
                    labels={
                        "votes_percentage": "Vote Share (%)",
                        "party_name": "Political Party",
                    },
                    text="votes_percentage",
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
                display_df["votes_percentage"] = display_df["votes_percentage"].apply(
                    lambda x: f"{x:.2f}%"
                )
                display_df["votes_absolute"] = display_df["votes_absolute"].apply(
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
                    "votes_absolute": "Total Votes",
                    "votes_percentage": "Percentage",
                    "estimated_voters": "Est. Voters",
                    "list_number": "List #",
                }

                display_df = display_df.rename(columns=column_renames)

                # Select and reorder columns
                display_cols = [
                    "List #",
                    "Party",
                    "Total Votes",
                    "Est. Voters",
                    "Percentage",
                ]
                available_cols = [
                    col for col in display_cols if col in display_df.columns
                ]

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
                st.metric("Turnout", f"{stats['turnout_percentage']:.1f}%")

        if "registered_voters" in stats:
            with col2:
                st.metric("Registered Voters", f"{stats['registered_voters']:,}")

        if "valid_votes" in stats:
            with col3:
                st.metric("Valid Votes", f"{stats['valid_votes']:,}")

    # If no meaningful data is found, suggest running the analysis pipeline
    if ("district_data" not in data or data["district_data"].empty) and (
        "summary_statistics" not in data or not data["summary_statistics"]
    ):
        st.warning("Run the analysis pipeline first to generate turnout data.")
        st.code("uv run python run_analysis.py")


def display_geographic_analysis(geojson_data, electoral_data=None):
    """Display geographic analysis with filtered electoral districts map for Prague 5 okrseks"""
    st.subheader("🗺️ Geographic Analysis - Prague 5 Okrseks")

    if not geojson_data:
        st.error("Unable to load GeoJSON data. Please check your internet connection.")
        return

    # Check if we have electoral data to overlay
    district_data = None
    party_data = None
    if electoral_data and "district_data" in electoral_data:
        district_data = electoral_data["district_data"]
    if electoral_data and "district_party_results" in electoral_data:
        party_data = electoral_data["district_party_results"]

    # Filter GeoJSON for Prague 5 okrseks
    prague5_features = []
    prague5_municipality_code = "554782"  # Prague 5 municipality code

    if "features" in geojson_data:
        for feature in geojson_data["features"]:
            properties = feature.get("properties", {})

            # Check if this feature belongs to Prague 5
            if properties.get("OBEC") == prague5_municipality_code:
                # Check if CISLO (district number) matches our okrseks (5001-5081)
                cislo = properties.get("CISLO", "")
                try:
                    district_num = int(cislo)
                    if 5001 <= district_num <= 5081:
                        prague5_features.append(feature)
                except (ValueError, TypeError):
                    continue

    st.info(
        f"Found {len(prague5_features)} Prague 5 okrseks in GeoJSON data out of {len(geojson_data.get('features', []))} total features"
    )

    if not prague5_features:
        st.warning(
            "No Prague 5 okrseks found in GeoJSON data. Showing full map instead."
        )
        prague5_features = geojson_data.get("features", [])

    # Create filtered GeoJSON for Prague 5 only
    filtered_geojson = {"type": "FeatureCollection", "features": prague5_features}

    # Map visualization controls
    st.subheader("📊 Map Visualization Controls")

    col1, col2 = st.columns(2)

    with col1:
        viz_type = st.selectbox(
            "Choose what to visualize:",
            ["Turnout", "Estimated Voters", "Party Results"],
            help="Select the data to display on the map with color coding",
        )

    selected_party = None
    if viz_type == "Party Results" and party_data is not None:
        with col2:
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

    # Create and display the map with selected visualization
    map_obj = create_folium_map(
        filtered_geojson, electoral_data, viz_type, selected_party
    )

    # Display the map
    map_data = st_folium(
        map_obj,
        width=None,  # Full width
        height=600,  # Taller map
        returned_objects=["last_clicked", "last_object_clicked"],
        key=f"map_{viz_type}_{selected_party}",  # Unique key for re-rendering
    )

    # Display information about clicked features
    if map_data["last_object_clicked"]:
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
        st.metric("Prague 5 Okrseks on Map", len(prague5_features))

    with col2:
        if district_data is not None and isinstance(district_data, pd.DataFrame):
            unique_okrseks = (
                len(district_data["district_code"].unique())
                if "district_code" in district_data.columns
                else 0
            )
            st.metric("Okrseks with Data", unique_okrseks)
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
                f.get("properties", {}).get("CISLO", "") for f in prague5_features
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
        f"💡 Click on any okrsek (polling district) on the map to see its electoral data. Currently showing: **{current_viz}**"
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


def main():
    """Main Streamlit application"""

    # Header
    st.markdown(
        '<h1 class="main-header">🗳️ Prague 5 Electoral Analysis Dashboard</h1>',
        unsafe_allow_html=True,
    )

    # Sidebar
    st.sidebar.title("Navigation")
    st.sidebar.markdown("---")

    # Load data
    with st.spinner("Loading data..."):
        geojson_data = load_geojson_data()
        electoral_data = load_processed_data()

    # Navigation
    page = st.sidebar.selectbox(
        "Choose a view:",
        [
            "Overview",
            "Turnout Analysis",
            "Geographic Analysis",
            "Data Explorer",
            "Okrsek Analysis",
        ],
    )

    # Sidebar info
    st.sidebar.markdown("---")
    st.sidebar.info(
        "This dashboard visualizes electoral data for Prague 5. "
        "Make sure to run the analysis pipeline first to generate the data."
    )

    # Quick stats in sidebar
    if electoral_data:
        st.sidebar.subheader("Quick Stats")
        st.sidebar.metric("Data Sources Loaded", len(electoral_data))

    if geojson_data and "features" in geojson_data:
        st.sidebar.metric("Electoral Districts", len(geojson_data["features"]))

    # Main content based on navigation
    if page == "Overview":
        display_electoral_overview(electoral_data)

        # Show sample data if available
        if electoral_data:
            st.subheader("Available Datasets")
            for key in electoral_data.keys():
                st.write(f"• {key}")

    elif page == "Turnout Analysis":
        display_turnout_analysis(electoral_data)

    elif page == "Geographic Analysis":
        display_geographic_analysis(geojson_data, electoral_data)

    elif page == "Data Explorer":
        display_data_explorer(electoral_data)

    elif page == "Okrsek Analysis":
        display_district_analysis(electoral_data)

    # Footer
    st.markdown("---")
    st.markdown(
        "**Prague 5 Electoral Analysis** | "
        "Built with Streamlit | "
        f"Data sources: {len(electoral_data)} loaded"
    )


if __name__ == "__main__":
    main()

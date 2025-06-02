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
    """Load processed electoral data from the analysis pipeline"""
    data_dir = Path(__file__).parent / "data"

    # Try to load different data sources
    data_sources = {
        "processed": data_dir / "processed",
        "detailed": data_dir / "detailed",
        "results": data_dir / "results",
        "raw": data_dir / "raw",
    }

    loaded_data = {}

    for source_name, source_path in data_sources.items():
        if source_path.exists():
            for file_path in source_path.glob("*.json"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        loaded_data[f"{source_name}_{file_path.stem}"] = json.load(f)
                except Exception as e:
                    st.warning(f"Could not load {file_path}: {e}")

            for file_path in source_path.glob("*.csv"):
                try:
                    loaded_data[f"{source_name}_{file_path.stem}"] = pd.read_csv(
                        file_path
                    )
                except Exception as e:
                    st.warning(f"Could not load {file_path}: {e}")

    return loaded_data


def create_folium_map(geojson_data, electoral_data=None):
    """Create an interactive Folium map with electoral districts"""
    # Center on Prague
    prague_center = [50.0755, 14.4378]

    m = folium.Map(location=prague_center, zoom_start=11, tiles="OpenStreetMap")

    if geojson_data:
        # Add GeoJSON layer
        folium.GeoJson(
            geojson_data,
            style_function=lambda x: {
                "fillColor": "#1f77b4",
                "color": "black",
                "weight": 1,
                "fillOpacity": 0.3,
            },
            popup=folium.Popup("Electoral District"),
            tooltip=folium.Tooltip("Click for details"),
        ).add_to(m)

    return m


def display_electoral_overview(data):
    """Display overview statistics"""
    st.subheader("📊 Electoral Overview")

    # Create columns for metrics
    col1, col2, col3, col4 = st.columns(4)

    # Try to extract meaningful statistics from available data
    total_districts = 0
    avg_turnout = 0
    total_voters = 0
    total_parties = 0

    # Look for relevant data in loaded datasets
    for key, dataset in data.items():
        if isinstance(dataset, dict):
            # Check for detailed statistics first
            if "detailed_statistics" in dataset:
                stats = dataset["detailed_statistics"]
                total_districts = stats.get("total_districts_analyzed", 0)
                avg_turnout = stats.get("average_turnout", 0)
                total_voters = stats.get("total_eligible_voters", 0)
                break

            # Check for summary statistics
            elif "summary_statistics" in dataset:
                stats = dataset["summary_statistics"]
                total_voters = stats.get("registered_voters", 0)
                turnout_pct = stats.get("turnout_percentage", 0)
                if isinstance(turnout_pct, (int, float)):
                    avg_turnout = turnout_pct

            # Check for districts list
            elif "districts" in dataset and isinstance(dataset["districts"], list):
                total_districts = len(dataset["districts"])

            # Check for party results
            elif "party_results" in dataset and isinstance(
                dataset["party_results"], list
            ):
                total_parties = len(dataset["party_results"])

                # Try to extract summary info from party results
                if not total_voters and "summary_statistics" in dataset:
                    summary = dataset["summary_statistics"]
                    total_voters = summary.get("registered_voters", 0)
                    if "turnout_percentage" in summary:
                        avg_turnout = summary["turnout_percentage"]

    with col1:
        if total_districts > 0:
            st.metric("Electoral Districts", f"{total_districts:,}")
        else:
            st.metric("Electoral Districts", "N/A")

    with col2:
        if avg_turnout > 0:
            st.metric("Average Turnout", f"{avg_turnout:.1f}%")
        else:
            st.metric("Average Turnout", "N/A")

    with col3:
        if total_voters > 0:
            st.metric("Registered Voters", f"{total_voters:,}")
        else:
            st.metric("Registered Voters", "N/A")

    with col4:
        st.metric("Data Sources", len(data))

    # Show additional metrics if we have party data
    if total_parties > 0:
        st.metric("Political Parties", total_parties)

    # Show data source breakdown
    if data:
        st.subheader("📁 Data Sources Loaded")
        for i, (key, dataset) in enumerate(data.items(), 1):
            data_type = "Unknown"
            size_info = ""

            if isinstance(dataset, dict):
                if "party_results" in dataset:
                    data_type = "Electoral Results"
                    size_info = f"({len(dataset['party_results'])} parties)"
                elif "districts" in dataset:
                    data_type = "District Data"
                    size_info = f"({len(dataset['districts'])} districts)"
                elif "summary_statistics" in dataset:
                    data_type = "Summary Statistics"
                else:
                    data_type = "JSON Data"
                    size_info = f"({len(dataset)} keys)"
            elif isinstance(dataset, pd.DataFrame):
                data_type = "CSV Data"
                size_info = f"({dataset.shape[0]} rows, {dataset.shape[1]} cols)"
            elif isinstance(dataset, list):
                data_type = "List Data"
                size_info = f"({len(dataset)} items)"

            st.write(f"{i}. **{key}** - {data_type} {size_info}")

    # Show party results if available
    for key, dataset in data.items():
        if isinstance(dataset, dict) and "party_results" in dataset:
            party_results = dataset["party_results"]
            if isinstance(party_results, list) and len(party_results) > 0:
                st.subheader("🏛️ Party Results Overview")

                # Create a DataFrame for party results
                party_data = []
                for party in party_results[:10]:  # Show top 10 parties
                    if isinstance(party, dict):
                        name = party.get("name", party.get("party_name", "Unknown"))
                        votes = party.get("votes", party.get("total_votes", 0))
                        percentage = party.get(
                            "percentage", party.get("vote_percentage", 0)
                        )
                        mandates = party.get("mandates", party.get("seats", 0))

                        # Handle different data types
                        if isinstance(votes, str):
                            try:
                                votes = int(votes.replace(" ", "").replace(",", ""))
                            except:
                                votes = 0

                        if isinstance(percentage, str):
                            try:
                                percentage = float(
                                    percentage.replace("%", "").replace(",", ".")
                                )
                            except:
                                percentage = 0

                        if isinstance(mandates, str):
                            try:
                                mandates = int(mandates)
                            except:
                                mandates = 0

                        party_data.append(
                            {
                                "Party": name,
                                "Votes": votes,
                                "Percentage": percentage,
                                "Mandates": mandates,
                            }
                        )

                if party_data:
                    party_df = pd.DataFrame(party_data)

                    # Display party results chart
                    fig = px.bar(
                        party_df.head(8),
                        x="Party",
                        y="Percentage",
                        title="Vote Share by Party (%)",
                        labels={
                            "Percentage": "Vote Share (%)",
                            "Party": "Political Party",
                        },
                    )
                    fig.update_xaxis(tickangle=45)
                    st.plotly_chart(fig, use_container_width=True)

                    # Display results table
                    st.subheader("📊 Detailed Results")
                    st.dataframe(party_df, use_container_width=True)

                break


def display_turnout_analysis(data):
    """Display turnout analysis visualizations"""
    st.subheader("📈 Turnout Analysis")

    # Look for turnout data
    turnout_data = None

    for key, dataset in data.items():
        if isinstance(dataset, dict) and "districts" in dataset:
            districts = dataset["districts"]
            if isinstance(districts, list) and len(districts) > 0:
                # Try to extract turnout information
                turnout_list = []
                district_names = []

                for district in districts:
                    if isinstance(district, dict):
                        district_name = district.get(
                            "name", district.get("district_id", "Unknown")
                        )

                        # Try multiple ways to get turnout value
                        turnout = None

                        # Try different possible keys for turnout
                        for turnout_key in [
                            "turnout_percentage",
                            "turnout",
                            "voter_turnout",
                            "participation",
                        ]:
                            if turnout_key in district:
                                turnout_value = district[turnout_key]

                                # Handle different data types
                                if isinstance(turnout_value, (int, float)):
                                    turnout = float(turnout_value)
                                    break
                                elif isinstance(turnout_value, str):
                                    try:
                                        # Try to extract number from string (e.g., "42.5%" -> 42.5)
                                        number_match = re.search(
                                            r"[\d,]+\.?\d*",
                                            turnout_value.replace(",", ""),
                                        )
                                        if number_match:
                                            turnout = float(number_match.group())
                                            break
                                    except (ValueError, AttributeError):
                                        continue
                                elif isinstance(turnout_value, dict):
                                    # If it's a dict, try to find a numeric value inside
                                    for sub_key, sub_value in turnout_value.items():
                                        if isinstance(sub_value, (int, float)):
                                            turnout = float(sub_value)
                                            break
                                    if turnout is not None:
                                        break

                        if turnout is not None and turnout > 0:
                            turnout_list.append(turnout)
                            district_names.append(district_name)

                if turnout_list:
                    turnout_data = pd.DataFrame(
                        {"District": district_names, "Turnout": turnout_list}
                    )
                    break

        # Also try to look for party results with turnout info
        elif isinstance(dataset, dict) and "party_results" in dataset:
            party_results = dataset["party_results"]
            if isinstance(party_results, list) and len(party_results) > 0:
                # Extract overall statistics if available
                summary_stats = dataset.get("summary_statistics", {})
                if "turnout_percentage" in summary_stats:
                    overall_turnout = summary_stats["turnout_percentage"]
                    if isinstance(overall_turnout, (int, float)):
                        st.info(f"Overall Prague 5 Turnout: {overall_turnout:.1f}%")

    if turnout_data is not None and not turnout_data.empty:
        # Create turnout visualization
        fig = px.bar(
            turnout_data.head(20),  # Show top 20 for readability
            x="District",
            y="Turnout",
            title="Voter Turnout by District",
            labels={"Turnout": "Turnout (%)", "District": "Electoral District"},
        )
        fig.update_xaxis(tickangle=45)
        st.plotly_chart(fig, use_container_width=True)

        # Summary statistics
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Highest Turnout", f"{turnout_data['Turnout'].max():.1f}%")
        with col2:
            st.metric("Lowest Turnout", f"{turnout_data['Turnout'].min():.1f}%")

        # Show district count
        st.metric("Districts with Data", len(turnout_data))

    else:
        st.info("No district-level turnout data found in the current dataset.")

        # Try to show any available summary statistics instead
        for key, dataset in data.items():
            if isinstance(dataset, dict):
                summary_stats = dataset.get("summary_statistics", {})
                if summary_stats:
                    st.subheader("Available Summary Statistics")

                    # Display any turnout-related info we can find
                    col1, col2, col3 = st.columns(3)

                    if "turnout_percentage" in summary_stats:
                        with col1:
                            st.metric(
                                "Turnout", f"{summary_stats['turnout_percentage']:.1f}%"
                            )

                    if "registered_voters" in summary_stats:
                        with col2:
                            st.metric(
                                "Registered Voters",
                                f"{summary_stats['registered_voters']:,}",
                            )

                    if "valid_votes" in summary_stats:
                        with col3:
                            st.metric(
                                "Valid Votes", f"{summary_stats['valid_votes']:,}"
                            )
                    break
        else:
            st.warning("Run the analysis pipeline first to generate turnout data.")


def display_geographic_analysis(geojson_data):
    """Display geographic analysis with the electoral districts map"""
    st.subheader("🗺️ Geographic Analysis")

    if geojson_data:
        # Create and display the map
        map_obj = create_folium_map(geojson_data)

        # Display the map
        map_data = st_folium(
            map_obj,
            width=700,
            height=500,
            returned_objects=["last_clicked", "last_object_clicked"],
        )

        # Display information about clicked features
        if map_data["last_object_clicked"]:
            st.subheader("Selected District Information")
            clicked_data = map_data["last_object_clicked"]
            st.json(clicked_data)

        # Basic statistics about the GeoJSON
        if "features" in geojson_data:
            st.info(
                f"Total electoral districts in GeoJSON: {len(geojson_data['features'])}"
            )
    else:
        st.error("Unable to load GeoJSON data. Please check your internet connection.")


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
        ["Overview", "Turnout Analysis", "Geographic Analysis", "Data Explorer"],
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
        display_geographic_analysis(geojson_data)

    elif page == "Data Explorer":
        display_data_explorer(electoral_data)

    # Footer
    st.markdown("---")
    st.markdown(
        "**Prague 5 Electoral Analysis** | "
        "Built with Streamlit | "
        f"Data sources: {len(electoral_data)} loaded"
    )


if __name__ == "__main__":
    main()

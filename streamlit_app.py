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

    return data


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

            # Create visualization
            # Limit to top 10 parties for readability
            top_parties = party_df.head(10)

            if len(top_parties) > 0:
                # Add option to show estimated voters vs total votes
                col_chart1, col_chart2 = st.columns(2)

                with col_chart1:
                    # Percentage chart (always show)
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

                with col_chart2:
                    # Show estimated voters if available, otherwise total votes
                    if "estimated_voters" in top_parties.columns:
                        fig_voters = px.bar(
                            top_parties,
                            x="party_name",
                            y="estimated_voters",
                            title="Estimated Number of Voters",
                            labels={
                                "estimated_voters": "Est. Voters",
                                "party_name": "Political Party",
                            },
                            text="estimated_voters",
                            color_discrete_sequence=["#ff7f0e"],
                        )
                        fig_voters.update_xaxes(tickangle=45)
                        fig_voters.update_traces(
                            texttemplate="%{text:,}", textposition="outside"
                        )
                        st.plotly_chart(fig_voters, use_container_width=True)
                    else:
                        # Fallback to total votes
                        fig_votes = px.bar(
                            top_parties,
                            x="party_name",
                            y="votes_absolute",
                            title="Total Votes (All Candidates)",
                            labels={
                                "votes_absolute": "Total Votes",
                                "party_name": "Political Party",
                            },
                            text="votes_absolute",
                            color_discrete_sequence=["#2ca02c"],
                        )
                        fig_votes.update_xaxes(tickangle=45)
                        fig_votes.update_traces(
                            texttemplate="%{text:,}", textposition="outside"
                        )
                        st.plotly_chart(fig_votes, use_container_width=True)

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

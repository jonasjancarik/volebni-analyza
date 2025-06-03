#!/usr/bin/env python3
"""
Streamlit Municipality Selector - Interface for selecting Czech municipalities
"""

import streamlit as st
import json
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class MunicipalitySelector:
    """Municipality selection interface for Streamlit"""

    def __init__(self, data_dir="output"):
        self.data_dir = Path(data_dir)
        self.municipality_index = None
        self.comprehensive_data = None

    def load_municipality_data(self) -> bool:
        """Load municipality index and comprehensive data"""
        try:
            # Load municipality index
            index_file = self.data_dir / "results" / "municipality_index.json"
            if index_file.exists():
                with open(index_file, "r", encoding="utf-8") as f:
                    self.municipality_index = json.load(f)
            else:
                st.error(
                    "Municipality data not found. Please run the data collection first."
                )
                return False

            # Load comprehensive data (we'll load specific municipality data on demand)
            comprehensive_file = (
                self.data_dir / "results" / "all_municipalities_comprehensive.json"
            )
            if comprehensive_file.exists():
                with open(comprehensive_file, "r", encoding="utf-8") as f:
                    self.comprehensive_data = json.load(f)
            else:
                st.error("Comprehensive municipality data not found.")
                return False

            return True

        except Exception as e:
            st.error(f"Error loading municipality data: {e}")
            return False

    def create_municipality_selector(self) -> Optional[str]:
        """Create municipality selection interface"""
        if not self.municipality_index:
            if not self.load_municipality_data():
                return None

        st.sidebar.header("🏛️ Municipality Selection")

        # Convert to DataFrame for easier filtering
        df = pd.DataFrame.from_dict(self.municipality_index, orient="index")
        df["code"] = df.index
        df = df.reset_index(drop=True)

        # Add filters
        st.sidebar.subheader("Filters")

        # Search by name
        search_term = st.sidebar.text_input(
            "Search by name:", placeholder="e.g., Praha, Brno, Ostrava"
        )

        if search_term:
            df = df[df["name"].str.contains(search_term, case=False, na=False)]

        # Filter by size (number of mandates)
        mandates_min = int(df["mandates"].min())
        mandates_max = int(df["mandates"].max())

        # Handle case where all municipalities have same number of mandates
        if mandates_min == mandates_max:
            st.sidebar.info(f"All municipalities have {mandates_min} council seats")
            min_mandates = mandates_min
        else:
            min_mandates = st.sidebar.slider(
                "Minimum council seats:",
                min_value=mandates_min,
                max_value=mandates_max,
                value=mandates_min,
            )
        df = df[df["mandates"] >= min_mandates]

        # Filter by turnout
        min_turnout = st.sidebar.slider(
            "Minimum turnout %:", min_value=0.0, max_value=100.0, value=0.0, step=0.1
        )
        df = df[df["turnout"] >= min_turnout]

        # Sort options
        sort_options = {
            "Name (A-Z)": ("name", True),
            "Name (Z-A)": ("name", False),
            "Council Seats (Most)": ("mandates", False),
            "Council Seats (Least)": ("mandates", True),
            "Turnout (Highest)": ("turnout", False),
            "Turnout (Lowest)": ("turnout", True),
            "Districts (Most)": ("districts", False),
        }

        sort_choice = st.sidebar.selectbox("Sort by:", list(sort_options.keys()))
        sort_column, ascending = sort_options[sort_choice]
        df = df.sort_values(sort_column, ascending=ascending)

        # Show statistics
        st.sidebar.info(f"**Found {len(df)} municipalities**")

        # Display top municipalities
        if len(df) > 0:
            st.sidebar.subheader("Select Municipality")

            # Create selection with municipality info
            municipality_options = []
            for _, row in df.head(20).iterrows():  # Limit to top 20 for performance
                option_text = f"{row['name']} ({row['mandates']} seats, {row['turnout']:.1f}% turnout)"
                municipality_options.append((option_text, row["code"]))

            if municipality_options:
                selected_option = st.sidebar.selectbox(
                    "Choose municipality:",
                    municipality_options,
                    format_func=lambda x: x[0],
                )

                if selected_option:
                    selected_code = selected_option[1]
                    self.display_municipality_info(selected_code)
                    return selected_code
        else:
            st.sidebar.warning("No municipalities match your criteria.")

        return None

    def display_municipality_info(self, municipality_code):
        """Display detailed information about selected municipality"""
        if not self.comprehensive_data:
            return

        municipality_data = self.comprehensive_data["municipalities"].get(
            municipality_code
        )
        if not municipality_data:
            st.sidebar.error("Municipality data not found")
            return

        metadata = municipality_data["metadata"]
        stats = municipality_data["summary_statistics"]

        st.sidebar.subheader("Municipality Info")
        st.sidebar.write(f"**Name:** {metadata['municipality_name']}")
        st.sidebar.write(f"**Code:** {metadata['municipality_code']}")
        st.sidebar.write(f"**Council Seats:** {metadata['total_mandates']}")
        st.sidebar.write(f"**Seats Won:** {metadata.get('mandates_won', 0)}")

        st.sidebar.subheader("Election Statistics")
        st.sidebar.write(f"**Electoral Districts:** {stats['electoral_districts']}")
        st.sidebar.write(f"**Registered Voters:** {stats['registered_voters']:,}")
        st.sidebar.write(f"**Turnout:** {stats['turnout_percentage']:.2f}%")
        st.sidebar.write(f"**Valid Votes:** {stats['valid_votes']:,}")
        st.sidebar.write(f"**Parties:** {stats['parties_participating']}")
        st.sidebar.write(f"**Parties with Seats:** {stats['parties_with_mandates']}")

    def get_municipality_data(self, municipality_code: str) -> Optional[Dict]:
        """Get complete data for a specific municipality"""
        if not self.comprehensive_data:
            if not self.load_municipality_data():
                return None

        return self.comprehensive_data["municipalities"].get(municipality_code)

    def create_comparison_interface(self) -> List[str]:
        """Create interface for comparing multiple municipalities"""
        if not self.municipality_index:
            if not self.load_municipality_data():
                return []

        st.sidebar.subheader("🔄 Compare Municipalities")

        # Multi-select for comparison
        df = pd.DataFrame.from_dict(self.municipality_index, orient="index")
        df["code"] = df.index
        df = df.reset_index(drop=True)

        # Popular municipalities for quick selection
        popular_municipalities = [
            ("Praha 1", "554782"),
            ("Praha 5", "500143"),
            ("Brno", "582786"),
            ("Ostrava", "554821"),
            ("Plzeň", "554804"),
        ]

        selected_codes = []

        # Quick selection buttons
        st.sidebar.write("**Quick Selection:**")
        for name, code in popular_municipalities:
            if st.sidebar.button(f"Add {name}", key=f"add_{code}"):
                if code not in st.session_state.get("selected_municipalities", []):
                    selected_codes.append(code)

        # Manual selection
        municipality_names = {row["code"]: row["name"] for _, row in df.iterrows()}
        selected_for_comparison = st.sidebar.multiselect(
            "Select municipalities to compare:",
            options=list(municipality_names.keys()),
            format_func=lambda x: municipality_names[x],
            key="municipality_comparison",
        )

        return selected_for_comparison + selected_codes


def display_municipality_overview():
    """Display overview of all available municipalities"""
    selector = MunicipalitySelector()

    if not selector.load_municipality_data():
        return

    st.header("📍 Czech Municipalities - Electoral Analysis")

    # Create summary statistics
    df = pd.DataFrame.from_dict(selector.municipality_index, orient="index")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Municipalities", len(df))

    with col2:
        st.metric("Total Council Seats", f"{df['mandates'].sum():,}")

    with col3:
        avg_turnout = df["turnout"].mean()
        st.metric("Average Turnout", f"{avg_turnout:.1f}%")

    with col4:
        total_voters = (
            df.get("registered_voters", pd.Series([])).sum()
            if "registered_voters" in df.columns
            else 0
        )
        st.metric("Total Registered Voters", f"{total_voters:,}")

    # Display top municipalities by various metrics
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🏆 Largest Municipalities (by seats)")
        top_by_seats = df.nlargest(10, "mandates")[["name", "mandates", "turnout"]]
        top_by_seats.columns = ["Municipality", "Council Seats", "Turnout %"]
        st.dataframe(top_by_seats, use_container_width=True)

    with col2:
        st.subheader("📈 Highest Turnout")
        top_by_turnout = df.nlargest(10, "turnout")[["name", "turnout", "mandates"]]
        top_by_turnout.columns = ["Municipality", "Turnout %", "Council Seats"]
        st.dataframe(top_by_turnout, use_container_width=True)

    # Interactive map would go here (requires geographic coordinates)
    st.subheader("🗺️ Municipality Distribution")
    st.info(
        "Interactive map visualization would be displayed here with municipality locations and data."
    )

    # Search functionality
    st.subheader("🔍 Search Municipalities")
    search_col1, search_col2 = st.columns([3, 1])

    with search_col1:
        search_query = st.text_input("Search by municipality name:")

    with search_col2:
        min_seats = st.number_input("Min. seats:", min_value=1, value=1)

    if search_query or min_seats > 1:
        filtered_df = df.copy()

        if search_query:
            filtered_df = filtered_df[
                filtered_df["name"].str.contains(search_query, case=False, na=False)
            ]

        if min_seats > 1:
            filtered_df = filtered_df[filtered_df["mandates"] >= min_seats]

        st.write(f"Found {len(filtered_df)} municipalities:")
        display_df = filtered_df[
            ["name", "mandates", "turnout", "districts", "parties"]
        ].copy()
        display_df.columns = [
            "Municipality",
            "Council Seats",
            "Turnout %",
            "Districts",
            "Parties",
        ]
        st.dataframe(display_df, use_container_width=True)


if __name__ == "__main__":
    # Test the selector
    st.set_page_config(page_title="Municipality Selector", layout="wide")

    selector = MunicipalitySelector()
    selected_code = selector.create_municipality_selector()

    if selected_code:
        st.header(f"📊 Municipality Analysis")
        municipality_data = selector.get_municipality_data(selected_code)
        if municipality_data:
            metadata = municipality_data["metadata"]
            stats = municipality_data["summary_statistics"]

            # Display key information
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Council Seats", metadata["total_mandates"])
            with col2:
                st.metric("Turnout", f"{stats['turnout_percentage']:.1f}%")
            with col3:
                st.metric("Registered Voters", f"{stats['registered_voters']:,}")
            with col4:
                st.metric("Electoral Districts", stats["electoral_districts"])

            # Party results
            st.subheader("🗳️ Election Results")
            party_results = municipality_data.get("party_results", [])
            if party_results:
                party_df = pd.DataFrame(party_results)
                # Show top parties
                display_df = party_df[
                    ["party_name", "votes_percentage", "mandates_won"]
                ].head(10)
                display_df.columns = ["Party", "Vote %", "Seats Won"]
                st.dataframe(display_df, use_container_width=True)
            else:
                st.info("No party results available for this municipality.")
    else:
        # Show overview when no municipality is selected
        display_municipality_overview()

#!/usr/bin/env python3
"""
Streamlit Municipality Selector - Interface for selecting Czech municipalities
Updated to handle KODZASTUP-based data structure properly
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
        self.municipality_registry = None  # For mapping user selection to data

    def load_municipality_data(self) -> bool:
        """Load municipality index and comprehensive data"""
        try:
            # Load municipality index (this is now keyed by zastupitelstvo_code)
            index_file = self.data_dir / "results" / "municipality_index.json"
            if index_file.exists():
                with open(index_file, "r", encoding="utf-8") as f:
                    self.municipality_index = json.load(f)
            else:
                st.error(
                    "Municipality data not found. Please run the data collection first."
                )
                return False

            # Load comprehensive data (also keyed by zastupitelstvo_code)
            comprehensive_file = (
                self.data_dir / "results" / "all_municipalities_comprehensive.json"
            )
            if comprehensive_file.exists():
                with open(comprehensive_file, "r", encoding="utf-8") as f:
                    self.comprehensive_data = json.load(f)
            else:
                st.error("Comprehensive municipality data not found.")
                return False

            # Load municipality registry for mapping geographic names to zastupitelstvo codes
            registry_file = self.data_dir / "processed" / "municipality_registry.json"
            if registry_file.exists():
                with open(registry_file, "r", encoding="utf-8") as f:
                    registry_data = json.load(f)
                    self.municipality_registry = registry_data.get("municipalities", {})

            return True

        except Exception as e:
            st.error(f"Error loading municipality data: {e}")
            return False

    def _create_user_friendly_index(self) -> Dict[str, Dict]:
        """Create a user-friendly municipality index that shows all available elections separately"""
        if not self.municipality_index or not self.comprehensive_data:
            return {}

        user_index = {}
        municipalities_data = self.comprehensive_data.get("municipalities", {})

        for zastupitelstvo_code, index_entry in self.municipality_index.items():
            municipality_data = municipalities_data.get(zastupitelstvo_code, {})
            metadata = municipality_data.get("metadata", {})

            municipality_name = metadata.get(
                "municipality_name", index_entry.get("name", "Unknown")
            )

            # Determine election type from the data
            election_type = "Municipal Council"  # Default

            # Look at the district data to determine election type
            districts = municipality_data.get("district_data", [])
            if districts:
                first_district = districts[0]
                oznac_typu = first_district.get("type", "")

                if oznac_typu == "OBEC":
                    election_type = "Municipal Council"
                elif oznac_typu == "MCMO":
                    election_type = "City District Council"
                else:
                    election_type = f"Council ({oznac_typu})"

            # Create a unique, descriptive key for each election
            if election_type == "City District Council":
                user_key = f"{municipality_name} - District Council"
            else:
                user_key = f"{municipality_name} - Municipal Council"

            # If we already have an entry with this name, add the zastupitelstvo code to differentiate
            original_key = user_key
            counter = 1
            while user_key in user_index:
                user_key = f"{original_key} ({zastupitelstvo_code})"
                counter += 1
                if counter > 10:  # Safety break
                    break

            user_index[user_key] = {
                "name": municipality_name,
                "election_type": election_type,
                "zastupitelstvo_code": zastupitelstvo_code,
                "mandates": index_entry.get("mandates", 0),
                "mandates_won": index_entry.get("mandates_won", 0),
                "districts": index_entry.get("districts", 0),
                "turnout": index_entry.get("turnout", 0),
                "parties": index_entry.get("parties", 0),
                "parties_with_mandates": index_entry.get("parties_with_mandates", 0),
                "registered_voters": index_entry.get("registered_voters", 0),
            }

        return user_index

    def create_municipality_selector(self) -> Optional[str]:
        """Create municipality selection interface"""
        if not self.municipality_index:
            if not self.load_municipality_data():
                return None

        st.sidebar.header("🏛️ Municipality Selection")

        # Create user-friendly index
        user_index = self._create_user_friendly_index()

        # Convert to DataFrame for easier filtering
        df = pd.DataFrame.from_dict(user_index, orient="index")
        df["name_key"] = df.index
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
        if len(df) > 0:
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
                "Minimum turnout %:",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=0.1,
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
            st.sidebar.subheader("Select Election")

            # Prioritize OBEC (Municipal Council) elections by bringing them to the top
            obec_entries = df[df["election_type"] == "Municipal Council"]
            mcmo_entries = df[df["election_type"] == "City District Council"]
            other_entries = df[
                ~df["election_type"].isin(
                    ["Municipal Council", "City District Council"]
                )
            ]

            # Combine with OBEC first, then MCMO, then others
            df_prioritized = pd.concat(
                [obec_entries, mcmo_entries, other_entries], ignore_index=True
            )

            # Create selection with municipality and election type info
            municipality_options = []
            for _, row in df_prioritized.head(
                50
            ).iterrows():  # Increased from 20 to 50 for better coverage
                election_type = row.get("election_type", "Council")
                option_text = f"{row['name']} - {election_type} ({row['mandates']} seats, {row['turnout']:.1f}% turnout)"
                municipality_options.append((option_text, row["zastupitelstvo_code"]))

            if municipality_options:
                selected_option = st.sidebar.selectbox(
                    "Choose election:",
                    municipality_options,
                    format_func=lambda x: x[0],
                    help="Each entry represents a specific council election. Some areas may have multiple elections (municipal + district).",
                )

                if selected_option:
                    selected_zastupitelstvo_code = selected_option[1]
                    self.display_municipality_info(selected_zastupitelstvo_code)
                    return selected_zastupitelstvo_code
        else:
            st.sidebar.warning("No elections match your criteria.")

        return None

    def display_municipality_info(self, zastupitelstvo_code):
        """Display detailed information about selected election"""
        if not self.comprehensive_data:
            return

        municipality_data = self.comprehensive_data["municipalities"].get(
            zastupitelstvo_code
        )
        if not municipality_data:
            st.sidebar.error("Election data not found")
            return

        metadata = municipality_data["metadata"]
        stats = municipality_data["summary_statistics"]

        # Determine election type from district data
        election_type = "Council Election"
        districts = municipality_data.get("district_data", [])
        if districts:
            first_district = districts[0]
            oznac_typu = first_district.get("type", "")

            if oznac_typu == "OBEC":
                election_type = "Municipal Council Election"
            elif oznac_typu == "MCMO":
                election_type = "City District Council Election"

        st.sidebar.subheader("Election Info")
        st.sidebar.write(f"**Municipality:** {metadata['municipality_name']}")
        st.sidebar.write(f"**Election Type:** {election_type}")
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

        # Show a note about election type
        if oznac_typu == "OBEC":
            st.sidebar.info("🏛️ This is a **municipal council** election (OBEC)")
        elif oznac_typu == "MCMO":
            st.sidebar.info("🏢 This is a **city district council** election (MCMO)")
        else:
            st.sidebar.info(f"📊 Election type: {oznac_typu}")

    def get_municipality_data(self, zastupitelstvo_code: str) -> Optional[Dict]:
        """Get complete data for a specific zastupitelstvo (council election)"""
        if not self.comprehensive_data:
            if not self.load_municipality_data():
                return None

        return self.comprehensive_data["municipalities"].get(zastupitelstvo_code)

    def create_comparison_interface(self) -> List[str]:
        """Create interface for comparing multiple municipalities"""
        if not self.municipality_index:
            if not self.load_municipality_data():
                return []

        st.sidebar.subheader("🔄 Compare Municipalities")

        # Create user-friendly index for comparison
        user_index = self._create_user_friendly_index()

        selected_codes = []

        # Quick selection buttons for major cities
        st.sidebar.write("**Quick Selection:**")

        # Look for major cities in our data
        major_cities = [
            "Praha",
            "Brno",
            "Ostrava",
            "Plzeň",
            "Liberec",
            "Hradec Králové",
        ]

        for city_name in major_cities:
            # Find the closest match in our data
            matching_cities = [
                name for name in user_index.keys() if city_name.lower() in name.lower()
            ]
            if matching_cities:
                # Use the first match
                city_key = matching_cities[0]
                zastupitelstvo_code = user_index[city_key]["zastupitelstvo_code"]
                if st.sidebar.button(
                    f"Add {city_key}", key=f"add_{zastupitelstvo_code}"
                ):
                    if zastupitelstvo_code not in st.session_state.get(
                        "selected_municipalities", []
                    ):
                        selected_codes.append(zastupitelstvo_code)

        # Manual selection using user-friendly names
        municipality_names = {
            entry["zastupitelstvo_code"]: name for name, entry in user_index.items()
        }
        selected_for_comparison = st.sidebar.multiselect(
            "Select municipalities to compare:",
            options=list(municipality_names.keys()),
            format_func=lambda x: municipality_names[x],
            key="municipality_comparison",
        )

        return selected_for_comparison + selected_codes


def display_municipality_overview():
    """Display overview of all available elections"""
    selector = MunicipalitySelector()

    if not selector.load_municipality_data():
        return

    st.header("📍 Czech Council Elections - Electoral Analysis")

    # Create user-friendly index
    user_index = selector._create_user_friendly_index()
    df = pd.DataFrame.from_dict(user_index, orient="index")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Elections", len(df))

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

    # Show election type breakdown
    if "election_type" in df.columns:
        st.subheader("📊 Elections by Type")
        type_counts = df["election_type"].value_counts()

        col1, col2 = st.columns(2)
        with col1:
            st.write("**Election Types:**")
            for election_type, count in type_counts.items():
                st.write(f"• {election_type}: {count:,} elections")

        with col2:
            # Show a pie chart of election types
            import plotly.express as px

            fig = px.pie(
                values=type_counts.values,
                names=type_counts.index,
                title="Distribution of Election Types",
            )
            st.plotly_chart(fig, use_container_width=True)

    # Display top elections by various metrics
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🏆 Largest Elections (by seats)")
        top_by_seats = df.nlargest(10, "mandates")[
            ["name", "election_type", "mandates", "turnout"]
        ]
        top_by_seats.columns = [
            "Municipality",
            "Election Type",
            "Council Seats",
            "Turnout %",
        ]
        st.dataframe(top_by_seats, use_container_width=True)

    with col2:
        st.subheader("📈 Highest Turnout Elections")
        top_by_turnout = df.nlargest(10, "turnout")[
            ["name", "election_type", "turnout", "mandates"]
        ]
        top_by_turnout.columns = [
            "Municipality",
            "Election Type",
            "Turnout %",
            "Council Seats",
        ]
        st.dataframe(top_by_turnout, use_container_width=True)

    # Show information about data structure
    st.subheader("📊 Data Information")
    st.info(
        f"📋 **Note**: This analysis covers {len(df)} distinct council elections across Czech municipalities. "
        f"Each election represents a specific council (OBEC = municipal council, MCMO = city district council). "
        f"Areas like Prague may have both municipal and district elections listed separately."
    )

    # Search functionality
    st.subheader("🔍 Search Elections")
    search_col1, search_col2, search_col3 = st.columns([2, 1, 1])

    with search_col1:
        search_query = st.text_input("Search by municipality name:")

    with search_col2:
        min_seats = st.number_input("Min. seats:", min_value=1, value=1)

    with search_col3:
        election_type_filter = st.selectbox(
            "Election type:",
            ["All", "Municipal Council", "City District Council"],
            help="Filter by specific election type",
        )

    if search_query or min_seats > 1 or election_type_filter != "All":
        filtered_df = df.copy()

        if search_query:
            filtered_df = filtered_df[
                filtered_df["name"].str.contains(search_query, case=False, na=False)
            ]

        if min_seats > 1:
            filtered_df = filtered_df[filtered_df["mandates"] >= min_seats]

        if election_type_filter != "All":
            filtered_df = filtered_df[
                filtered_df["election_type"] == election_type_filter
            ]

        st.write(f"Found {len(filtered_df)} elections:")
        display_df = filtered_df[
            ["name", "election_type", "mandates", "turnout", "districts", "parties"]
        ].copy()
        display_df.columns = [
            "Municipality",
            "Election Type",
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

"""
Data exporters for converting processed election data to structured CSV format.

This module provides functions to export electoral data in clean, structured CSV
files that are optimized for pandas analysis and visualization.
"""

import pandas as pd
import os
from pathlib import Path
import json
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


def ensure_directory(path: str) -> None:
    """Ensure directory exists, create if not."""
    Path(path).mkdir(parents=True, exist_ok=True)


def export_party_results_csv(data: Dict[str, Any], output_dir: str) -> str:
    """
    Export party results to a clean CSV format.

    Args:
        data: Electoral data dictionary
        output_dir: Output directory path

    Returns:
        Path to created CSV file
    """
    ensure_directory(output_dir)

    # Extract party results
    party_results = []

    # Try to get number of seats - Prague 5 has 41 seats for municipal elections
    num_seats = 41  # Default for Prague 5 municipal council

    # Try to extract from metadata if available
    if "metadata" in data:
        metadata = data["metadata"]
        if "elected_members" in metadata and metadata["elected_members"]:
            try:
                num_seats = int(metadata["elected_members"])
            except (ValueError, TypeError):
                pass

    # Try summary statistics
    if "summary_statistics" in data:
        stats = data["summary_statistics"]
        if "elected_members" in stats and stats["elected_members"]:
            try:
                num_seats = int(stats["elected_members"])
            except (ValueError, TypeError):
                pass

    if "party_results" in data:
        for party in data["party_results"]:
            votes_absolute = party.get("votes_absolute", 0)

            # Calculate estimated number of voters for this party
            estimated_voters = round(votes_absolute / num_seats) if num_seats > 0 else 0

            party_results.append(
                {
                    "list_number": party.get("list_number"),
                    "party_name": party.get("party_name", "")
                    .replace('"', "")
                    .replace('"', ""),
                    "votes_absolute": votes_absolute,
                    "votes_percentage": party.get("votes_percentage", 0.0),
                    "estimated_voters": estimated_voters,
                    "num_seats_used": num_seats,
                    "candidate_count": party.get("candidate_count"),
                    "mandates_won": party.get("mandates_won"),
                    "data_source": party.get("data_source", ""),
                }
            )

    # Create DataFrame and clean data
    df = pd.DataFrame(party_results)

    if not df.empty:
        # Clean party names - remove generic names and quotes
        df["party_name"] = df["party_name"].str.replace('^„|"$', "", regex=True)
        df["party_name"] = df["party_name"].str.replace(
            r"^Party List \d+$", "", regex=True
        )

        # Remove rows with empty party names or zero votes
        df = df[df["party_name"].str.len() > 0]
        df = df[df["votes_absolute"] > 0]

        # Sort by votes (descending)
        df = df.sort_values("votes_absolute", ascending=False)

        # Reset index
        df = df.reset_index(drop=True)

    output_path = os.path.join(output_dir, "party_results.csv")
    df.to_csv(output_path, index=False)

    logger.info(f"Exported {len(df)} party results to {output_path}")
    return output_path


def export_district_data_csv(data: Dict[str, Any], output_dir: str) -> str:
    """
    Export district-level data to CSV format.

    Args:
        data: Electoral data dictionary
        output_dir: Output directory path

    Returns:
        Path to created CSV file
    """
    ensure_directory(output_dir)

    district_data = []

    # Look for district data in the new structure
    if "district_data" in data and isinstance(data["district_data"], dict):
        district_info = data["district_data"]

        if "districts" in district_info and isinstance(
            district_info["districts"], list
        ):
            for district in district_info["districts"]:
                if isinstance(district, dict):
                    # Extract basic district info
                    district_id = f"{district.get('district_code', '')}-{district.get('obvod_number', '')}"
                    district_name = f"District {district.get('obvod_number', 'Unknown')} ({district.get('type', '')})"

                    # Extract turnout information
                    turnout_info = district.get("turnout", {})

                    district_record = {
                        "district_id": district_id,
                        "district_name": district_name,
                        "district_code": district.get("district_code", ""),
                        "obvod_number": district.get("obvod_number", ""),
                        "type": district.get("type", ""),
                        "turnout_percentage": turnout_info.get("turnout_percentage"),
                        "registered_voters": turnout_info.get("registered_voters"),
                        "issued_ballots": turnout_info.get("issued_ballots"),
                        "returned_ballots": turnout_info.get("returned_ballots"),
                        "valid_votes": turnout_info.get("valid_votes"),
                        "processing_time": district.get("processing_time", ""),
                    }

                    district_data.append(district_record)

    # Look for legacy district data structure as fallback
    elif "districts" in data:
        districts = data["districts"]
        if isinstance(districts, list):
            for district in districts:
                if isinstance(district, dict):
                    district_data.append(
                        {
                            "district_id": district.get(
                                "district_id", district.get("id")
                            ),
                            "district_name": district.get(
                                "name", district.get("district_name", "")
                            ),
                            "district_code": district.get("district_code", ""),
                            "obvod_number": district.get("obvod_number", ""),
                            "type": district.get("type", ""),
                            "turnout_percentage": district.get(
                                "turnout_percentage", district.get("turnout")
                            ),
                            "registered_voters": district.get("registered_voters"),
                            "issued_ballots": district.get("issued_ballots"),
                            "returned_ballots": district.get("returned_ballots"),
                            "valid_votes": district.get("valid_votes"),
                            "processing_time": district.get("processing_time", ""),
                        }
                    )

    # If no districts found, try to extract from metadata as summary
    if not district_data and "summary_statistics" in data:
        stats = data["summary_statistics"]
        district_data.append(
            {
                "district_id": "TOTAL",
                "district_name": "Praha 5 - Total",
                "district_code": "",
                "obvod_number": "",
                "type": "summary",
                "turnout_percentage": stats.get("turnout_percentage"),
                "registered_voters": stats.get("registered_voters"),
                "issued_ballots": None,
                "returned_ballots": None,
                "valid_votes": stats.get("valid_votes"),
                "processing_time": "",
            }
        )

    df = pd.DataFrame(district_data)

    if not df.empty:
        # Clean and validate data
        df = df.dropna(subset=["district_id"])

        # Ensure numeric columns are properly typed
        numeric_cols = [
            "turnout_percentage",
            "registered_voters",
            "issued_ballots",
            "returned_ballots",
            "valid_votes",
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Sort by district_id
        df = df.sort_values("district_id")
        df = df.reset_index(drop=True)

    output_path = os.path.join(output_dir, "district_data.csv")
    df.to_csv(output_path, index=False)

    logger.info(f"Exported {len(df)} district records to {output_path}")
    return output_path


def export_summary_stats_csv(data: Dict[str, Any], output_dir: str) -> str:
    """
    Export summary statistics to CSV format.

    Args:
        data: Electoral data dictionary
        output_dir: Output directory path

    Returns:
        Path to created CSV file
    """
    ensure_directory(output_dir)

    summary_data = []

    # Extract metadata
    metadata = data.get("metadata", {})
    summary_stats = data.get("summary_statistics", {})

    # Create summary records
    summary_data.extend(
        [
            {
                "metric": "municipality",
                "value": metadata.get("municipality", ""),
                "category": "metadata",
                "data_type": "string",
            },
            {
                "metric": "election_year",
                "value": metadata.get("election_year", ""),
                "category": "metadata",
                "data_type": "string",
            },
            {
                "metric": "scrape_date",
                "value": metadata.get("scrape_date", ""),
                "category": "metadata",
                "data_type": "datetime",
            },
            {
                "metric": "districts_processed",
                "value": metadata.get("districts_processed", 0),
                "category": "metadata",
                "data_type": "integer",
            },
        ]
    )

    # Add statistical metrics
    for key, value in summary_stats.items():
        summary_data.append(
            {
                "metric": key,
                "value": value,
                "category": "statistics",
                "data_type": "numeric" if isinstance(value, (int, float)) else "string",
            }
        )

    df = pd.DataFrame(summary_data)

    output_path = os.path.join(output_dir, "summary_statistics.csv")
    df.to_csv(output_path, index=False)

    logger.info(f"Exported {len(df)} summary statistics to {output_path}")
    return output_path


def export_district_party_results_csv(data: Dict[str, Any], output_dir: str) -> str:
    """
    Export district-level party results for comparative analysis.

    Args:
        data: Electoral data dictionary
        output_dir: Output directory path

    Returns:
        Path to created CSV file
    """
    ensure_directory(output_dir)

    district_party_data = []

    # Create party name mapping from main party results
    party_mapping = {}
    if "party_results" in data:
        for party in data["party_results"]:
            list_num = party.get("list_number")
            if list_num:
                party_mapping[int(list_num)] = party.get(
                    "party_name", f"Party {list_num}"
                )

    # Extract district-level party results
    if "district_data" in data and isinstance(data["district_data"], dict):
        district_info = data["district_data"]

        if "districts" in district_info and isinstance(
            district_info["districts"], list
        ):
            for district in district_info["districts"]:
                if isinstance(district, dict):
                    district_id = f"{district.get('district_code', '')}-{district.get('obvod_number', '')}"
                    district_name = f"District {district.get('obvod_number', 'Unknown')} ({district.get('type', '')})"
                    obvod_number = district.get("obvod_number", "")
                    district_type = district.get("type", "")

                    # Get turnout info for context
                    turnout_info = district.get("turnout", {})
                    total_valid_votes = turnout_info.get("valid_votes", 0)

                    # Extract party votes for this district
                    party_votes = district.get("party_votes", [])

                    for party_vote in party_votes:
                        if isinstance(party_vote, dict):
                            party_list_num = party_vote.get("party_list_number")
                            votes = party_vote.get("votes", 0)

                            # Skip parties with zero votes
                            if votes > 0:
                                party_name = party_mapping.get(
                                    party_list_num, f"Party {party_list_num}"
                                )

                                # Calculate percentage for this district
                                percentage = (
                                    (votes / total_valid_votes * 100)
                                    if total_valid_votes > 0
                                    else 0
                                )

                                district_party_data.append(
                                    {
                                        "district_id": district_id,
                                        "district_name": district_name,
                                        "obvod_number": obvod_number,
                                        "district_type": district_type,
                                        "party_list_number": party_list_num,
                                        "party_name": party_name,
                                        "votes": votes,
                                        "percentage": percentage,
                                        "total_district_votes": total_valid_votes,
                                    }
                                )

    df = pd.DataFrame(district_party_data)

    if not df.empty:
        # Clean party names
        df["party_name"] = df["party_name"].str.replace('^„|"$', "", regex=True)
        df["party_name"] = df["party_name"].str.replace(
            r"^Party List \d+$", "", regex=True
        )

        # Remove rows with empty party names
        df = df[df["party_name"].str.len() > 0]

        # Ensure numeric columns are properly typed
        numeric_cols = ["votes", "percentage", "total_district_votes"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Sort by district and then by votes within district
        df = df.sort_values(["district_id", "votes"], ascending=[True, False])
        df = df.reset_index(drop=True)

    output_path = os.path.join(output_dir, "district_party_results.csv")
    df.to_csv(output_path, index=False)

    logger.info(f"Exported {len(df)} district-party records to {output_path}")
    return output_path


def convert_json_to_csv_format(input_json_path: str, output_dir: str) -> Dict[str, str]:
    """
    Convert existing JSON results to CSV format.

    Args:
        input_json_path: Path to existing JSON file
        output_dir: Output directory for CSV files

    Returns:
        Dictionary of created file paths
    """
    ensure_directory(output_dir)

    try:
        with open(input_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load {input_json_path}: {e}")
        return {}

    created_files = {}

    # Export each data type
    try:
        created_files["party_results"] = export_party_results_csv(data, output_dir)
    except Exception as e:
        logger.error(f"Failed to export party results: {e}")

    try:
        created_files["district_data"] = export_district_data_csv(data, output_dir)
    except Exception as e:
        logger.error(f"Failed to export district data: {e}")

    try:
        created_files["summary_stats"] = export_summary_stats_csv(data, output_dir)
    except Exception as e:
        logger.error(f"Failed to export summary statistics: {e}")

    try:
        created_files["district_party_results"] = export_district_party_results_csv(
            data, output_dir
        )
    except Exception as e:
        logger.error(f"Failed to export district party results: {e}")

    return created_files


def load_csv_data(csv_dir: str) -> Dict[str, pd.DataFrame]:
    """
    Load all CSV files from a directory into a dictionary of DataFrames.

    Args:
        csv_dir: Directory containing CSV files

    Returns:
        Dictionary mapping file names to DataFrames
    """
    data = {}
    csv_files = {
        "party_results": "party_results.csv",
        "district_data": "district_data.csv",
        "summary_stats": "summary_statistics.csv",
        "district_party_results": "district_party_results.csv",
    }

    for key, filename in csv_files.items():
        filepath = os.path.join(csv_dir, filename)
        if os.path.exists(filepath):
            try:
                data[key] = pd.read_csv(filepath)
                logger.info(f"Loaded {len(data[key])} rows from {filename}")
            except Exception as e:
                logger.error(f"Failed to load {filename}: {e}")
        else:
            logger.warning(f"CSV file not found: {filepath}")

    return data


if __name__ == "__main__":
    # Convert existing JSON to CSV format
    input_file = "output/results/prague5_comprehensive_results.json"
    output_directory = "output/csv"

    if os.path.exists(input_file):
        print(f"Converting {input_file} to CSV format...")
        created_files = convert_json_to_csv_format(input_file, output_directory)

        print("Created files:")
        for file_type, filepath in created_files.items():
            print(f"  {file_type}: {filepath}")

        # Test loading
        print("\nTesting data loading...")
        csv_data = load_csv_data(output_directory)
        for key, df in csv_data.items():
            print(f"  {key}: {len(df)} rows, {len(df.columns)} columns")
    else:
        print(f"Input file not found: {input_file}")

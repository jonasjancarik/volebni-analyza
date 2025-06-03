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

    # Look for district data in various possible locations
    if "districts" in data:
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
                            "turnout_percentage": district.get(
                                "turnout_percentage", district.get("turnout")
                            ),
                            "registered_voters": district.get("registered_voters"),
                            "valid_votes": district.get("valid_votes"),
                            "total_votes": district.get("total_votes"),
                            "district_type": district.get("district_type", ""),
                            "address": district.get("address", ""),
                        }
                    )

    # If no districts found, try to extract from metadata
    if not district_data and "summary_statistics" in data:
        stats = data["summary_statistics"]
        district_data.append(
            {
                "district_id": "TOTAL",
                "district_name": "Praha 5 - Total",
                "turnout_percentage": stats.get("turnout_percentage"),
                "registered_voters": stats.get("registered_voters"),
                "valid_votes": stats.get("valid_votes"),
                "total_votes": None,
                "district_type": "summary",
                "address": "",
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
            "valid_votes",
            "total_votes",
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

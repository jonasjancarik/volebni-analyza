#!/usr/bin/env python3
"""
Election Configuration - Manage settings for different elections
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class ElectionConfig:
    """Configuration for a specific election"""

    # Election identification
    election_id: str  # e.g., "kv2022", "kv2018", "senat2024"
    election_name: str  # e.g., "Komunální volby 2022"
    election_type: str  # e.g., "municipal", "senate", "parliamentary"
    election_date: str  # Format: YYYYMMDD, e.g., "20220923"

    # Data source URLs
    base_url: str  # e.g., "https://www.volby.cz/pls/kv2022"
    opendata_url: str  # e.g., "https://www.volby.cz/opendata/kv2022/xml"

    # API endpoints (relative to base_url)
    districts_endpoint: str = "vysledky_okrsky"

    # XML file names
    municipality_registry_file: str = "kvcoco.xml"
    party_registry_file: str = "kvros.xml"

    # Directory structure
    base_dir: Path = Path(".")

    @property
    def input_dir(self) -> Path:
        """Get input directory for this election"""
        return self.base_dir / "input" / self.election_id

    @property
    def output_dir(self) -> Path:
        """Get output directory for this election"""
        return self.base_dir / "output" / self.election_id

    @property
    def raw_input_dir(self) -> Path:
        """Get raw input directory"""
        return self.input_dir / "raw"

    @property
    def raw_output_dir(self) -> Path:
        """Get raw output directory"""
        return self.output_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        """Get processed data directory"""
        return self.output_dir / "processed"

    @property
    def results_dir(self) -> Path:
        """Get results directory"""
        return self.output_dir / "results"

    @property
    def csv_dir(self) -> Path:
        """Get CSV exports directory"""
        return self.output_dir / "csv"

    @property
    def reports_dir(self) -> Path:
        """Get reports directory"""
        return self.output_dir / "reports"

    @property
    def visualizations_dir(self) -> Path:
        """Get visualizations directory"""
        return self.output_dir / "visualizations"

    @property
    def detailed_dir(self) -> Path:
        """Get detailed analysis directory"""
        return self.output_dir / "detailed"

    def ensure_directories(self):
        """Create all necessary directories"""
        directories = [
            self.raw_input_dir,
            self.raw_output_dir,
            self.processed_dir,
            self.results_dir,
            self.csv_dir,
            self.reports_dir,
            self.visualizations_dir,
            self.detailed_dir,
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

        logger.info(f"Ensured directories for election: {self.election_name}")

    def get_municipality_registry_url(self) -> str:
        """Get URL for municipality registry"""
        return f"{self.opendata_url}/{self.municipality_registry_file}"

    def get_party_registry_url(self) -> str:
        """Get URL for party registry"""
        return f"{self.opendata_url}/{self.party_registry_file}"

    def get_districts_api_url(self) -> str:
        """Get URL for electoral districts API"""
        return f"{self.base_url}/{self.districts_endpoint}"

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "election_id": self.election_id,
            "election_name": self.election_name,
            "election_type": self.election_type,
            "election_date": self.election_date,
            "base_url": self.base_url,
            "opendata_url": self.opendata_url,
            "districts_endpoint": self.districts_endpoint,
            "municipality_registry_file": self.municipality_registry_file,
            "party_registry_file": self.party_registry_file,
        }

    @classmethod
    def from_dict(cls, data: dict, base_dir: Path = Path(".")) -> "ElectionConfig":
        """Create from dictionary"""
        return cls(
            election_id=data["election_id"],
            election_name=data["election_name"],
            election_type=data["election_type"],
            election_date=data["election_date"],
            base_url=data["base_url"],
            opendata_url=data["opendata_url"],
            districts_endpoint=data.get("districts_endpoint", "vysledky_okrsky"),
            municipality_registry_file=data.get(
                "municipality_registry_file", "kvcoco.xml"
            ),
            party_registry_file=data.get("party_registry_file", "kvros.xml"),
            base_dir=base_dir,
        )

    def save_to_file(self, filepath: Optional[Path] = None):
        """Save configuration to JSON file"""
        if filepath is None:
            filepath = self.output_dir / "election_config.json"

        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

        logger.info(f"Saved election config to {filepath}")

    @classmethod
    def load_from_file(
        cls, filepath: Path, base_dir: Path = Path(".")
    ) -> "ElectionConfig":
        """Load configuration from JSON file"""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        return cls.from_dict(data, base_dir)


# Predefined election configurations
ELECTIONS = {
    # Municipal Elections
    "kv2022": ElectionConfig(
        election_id="kv2022",
        election_name="Komunální volby 2022",
        election_type="municipal",
        election_date="20220923",
        base_url="https://www.volby.cz/pls/kv2022",
        opendata_url="https://www.volby.cz/opendata/kv2022/xml",
    ),
    "kv2018": ElectionConfig(
        election_id="kv2018",
        election_name="Komunální volby 2018",
        election_type="municipal",
        election_date="20181005",
        base_url="https://www.volby.cz/pls/kv2018",
        opendata_url="https://www.volby.cz/opendata/kv2018/xml",
    ),
    "kv2014": ElectionConfig(
        election_id="kv2014",
        election_name="Komunální volby 2014",
        election_type="municipal",
        election_date="20141010",
        base_url="https://www.volby.cz/pls/kv2014",
        opendata_url="https://www.volby.cz/opendata/kv2014/xml",
    ),
    # Parliamentary Elections
    "ps2025": ElectionConfig(
        election_id="ps2025",
        election_name="Volby do Poslanecké sněmovny 2025",
        election_type="parliamentary",
        election_date="20251005",  # October 5, 2025 - DATA AVAILABLE!
        base_url="https://www.volby.cz/pls/ps2025",
        opendata_url="https://www.volby.cz/opendata/ps2025",
        districts_endpoint="pst4",  # Polling station data file
        municipality_registry_file="psrk.xml",  # Candidate registry
        party_registry_file="psrkl.xml",  # Party/coalition list
    ),
}


def get_election_config(election_id: str, base_dir: Path = Path(".")) -> ElectionConfig:
    """
    Get election configuration by ID

    Args:
        election_id: Election identifier (e.g., "kv2022")
        base_dir: Base directory for paths (default: current directory)

    Returns:
        ElectionConfig object

    Raises:
        ValueError: If election_id is not found
    """
    if election_id not in ELECTIONS:
        available = ", ".join(ELECTIONS.keys())
        raise ValueError(
            f"Unknown election_id: {election_id}. Available elections: {available}"
        )

    config = ELECTIONS[election_id]
    config.base_dir = base_dir
    return config


def list_available_elections() -> list[str]:
    """List all available election configurations"""
    return list(ELECTIONS.keys())


def get_election_info() -> dict:
    """Get information about all available elections"""
    return {
        election_id: {
            "name": config.election_name,
            "type": config.election_type,
            "date": config.election_date,
        }
        for election_id, config in ELECTIONS.items()
    }

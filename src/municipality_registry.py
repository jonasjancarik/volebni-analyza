#!/usr/bin/env python3
"""
Municipality Registry - Handle municipality data and mandate information
"""

import requests
import xml.etree.ElementTree as ET
import json
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union
import pandas as pd

from election_config import ElectionConfig, get_election_config

logger = logging.getLogger(__name__)


@dataclass
class MunicipalityInfo:
    """Municipality information from registry"""

    municipality_code: str
    municipality_name: str
    region_code: str
    district_code: str
    council_type: int
    council_kind: int
    mandates: int
    election_districts: int
    status: int  # 0=processed, 1=insufficient candidates, 2=repeated voting
    parent_municipality: Optional[str] = None


class MunicipalityRegistry:
    """
    Registry for Czech municipalities and their electoral information
    """

    def __init__(
        self,
        election_config: Optional[Union[ElectionConfig, str]] = None,
        data_dir: Optional[str] = None,
    ):
        """
        Initialize municipality registry

        Args:
            election_config: ElectionConfig object or election_id string (e.g., "kv2022").
                           If None, defaults to "kv2022" for backwards compatibility.
            data_dir: (Deprecated) Output directory. Only used if election_config is None.
        """
        # Handle election config
        if election_config is None:
            # Backwards compatibility: use kv2022 as default
            if data_dir:
                logger.warning(
                    "data_dir parameter is deprecated. Please use election_config instead."
                )
            election_config = "kv2022"

        if isinstance(election_config, str):
            self.election_config = get_election_config(election_config)
        else:
            self.election_config = election_config

        # Ensure directories exist
        self.election_config.ensure_directories()

        # Set up directories (for backwards compatibility)
        self.data_dir = self.election_config.output_dir
        self.input_dir = self.election_config.input_dir

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
        )
        self.municipalities: Dict[str, MunicipalityInfo] = {}

    def download_municipality_registry(
        self, election_date: Optional[str] = None
    ) -> bool:
        """Download the municipality registry (kvcoco.xml) from ČSÚ"""
        url = self.election_config.get_municipality_registry_url()

        if election_date is None:
            election_date = self.election_config.election_date

        try:
            logger.info(
                f"Downloading municipality registry for {self.election_config.election_name}..."
            )
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            # Save the registry to input directory
            registry_file = (
                self.election_config.raw_input_dir
                / f"{self.election_config.municipality_registry_file.replace('.xml', '_municipality_registry.xml')}"
            )
            registry_file.parent.mkdir(parents=True, exist_ok=True)

            with open(registry_file, "wb") as f:
                f.write(response.content)

            logger.info(f"Saved municipality registry to {registry_file}")
            return True

        except Exception as e:
            logger.error(f"Error downloading municipality registry: {e}")
            return False

    def parse_municipality_registry(self) -> Dict[str, MunicipalityInfo]:
        """Parse the kvcoco.xml file to extract municipality information"""
        registry_file = (
            self.election_config.raw_input_dir
            / f"{self.election_config.municipality_registry_file.replace('.xml', '_municipality_registry.xml')}"
        )

        if not registry_file.exists():
            logger.warning("Municipality registry file not found, downloading...")
            if not self.download_municipality_registry():
                return {}

        try:
            tree = ET.parse(registry_file)
            root = tree.getroot()

            # Define namespace
            ns = {"kv": "http://www.volby.cz/kv/"}

            municipalities = {}
            rows = root.findall(".//kv:KV_COCO_ROW", ns)

            for row in rows:
                # Extract fields from XML structure
                election_date = self._get_text(row, "kv:DATUMVOLEB", ns)
                region_code = self._get_text(row, "kv:KRAJ", ns)
                district_code = self._get_text(row, "kv:OKRES", ns)
                council_type = self._get_int(row, "kv:TYPZASTUP", ns)
                council_kind = self._get_int(row, "kv:DRUHZASTUP", ns)
                municipality_code = self._get_text(row, "kv:KODZASTUP", ns)
                municipality_name = self._get_text(row, "kv:NAZEVZAST", ns)
                election_districts = self._get_int(row, "kv:OBVODY", ns)
                district_number = self._get_int(row, "kv:COBVODU", ns)
                mandates = self._get_int(row, "kv:MANDATY", ns)
                status = self._get_int(row, "kv:STAV_OBCE", ns)
                parent_municipality = self._get_text(row, "kv:NADRZASTUP", ns)

                if municipality_code and municipality_name:
                    # Create unique key for municipality (some have multiple election districts)
                    key = (
                        f"{municipality_code}-{district_number}"
                        if district_number > 1
                        else municipality_code
                    )

                    municipalities[key] = MunicipalityInfo(
                        municipality_code=municipality_code,
                        municipality_name=municipality_name,
                        region_code=region_code or "",
                        district_code=district_code or "",
                        council_type=council_type or 0,
                        council_kind=council_kind or 0,
                        mandates=mandates or 0,
                        election_districts=election_districts or 0,
                        status=status or 0,
                        parent_municipality=parent_municipality,
                    )

            logger.info(
                f"Parsed {len(municipalities)} municipality entries from registry"
            )
            self.municipalities = municipalities
            return municipalities

        except Exception as e:
            logger.error(f"Error parsing municipality registry: {e}")
            return {}

    def _get_text(self, element, path: str, namespace: dict) -> Optional[str]:
        """Safely extract text from XML element"""
        elem = element.find(path, namespace)
        return elem.text.strip() if elem is not None and elem.text else None

    def _get_int(self, element, path: str, namespace: dict) -> Optional[int]:
        """Safely extract integer from XML element"""
        text = self._get_text(element, path, namespace)
        try:
            return int(text) if text else None
        except (ValueError, TypeError):
            return None

    def get_municipality_info(
        self, municipality_code: str
    ) -> Optional[MunicipalityInfo]:
        """Get municipality information by code"""
        if not self.municipalities:
            self.parse_municipality_registry()

        return self.municipalities.get(municipality_code)

    def search_municipalities(self, query: str) -> List[MunicipalityInfo]:
        """Search municipalities by name or code"""
        if not self.municipalities:
            self.parse_municipality_registry()

        results = []
        query_lower = query.lower()

        for municipality in self.municipalities.values():
            if (
                query_lower in municipality.municipality_name.lower()
                or query in municipality.municipality_code
            ):
                results.append(municipality)

        return results

    def get_all_municipalities(self) -> List[MunicipalityInfo]:
        """Get all municipalities from registry"""
        if not self.municipalities:
            self.parse_municipality_registry()

        # Return unique municipalities (remove duplicates from multi-district municipalities)
        unique_municipalities = {}
        for municipality in self.municipalities.values():
            key = municipality.municipality_code
            if key not in unique_municipalities:
                unique_municipalities[key] = municipality

        return list(unique_municipalities.values())

    def get_municipalities_with_mandates(self) -> List[MunicipalityInfo]:
        """Get municipalities that have valid electoral data (mandates > 0)"""
        all_municipalities = self.get_all_municipalities()
        return [m for m in all_municipalities if m.mandates > 0 and m.status == 0]

    def save_registry_to_json(self, output_path: str = None) -> str:
        """Save municipality registry to JSON file"""
        if not output_path:
            output_path = (
                self.election_config.processed_dir / "municipality_registry.json"
            )

        if not self.municipalities:
            self.parse_municipality_registry()

        # Convert to JSON-serializable format
        registry_data = {
            "metadata": {
                "total_municipalities": len(self.municipalities),
                "valid_municipalities": len(self.get_municipalities_with_mandates()),
                "source": self.election_config.municipality_registry_file,
                "election_id": self.election_config.election_id,
                "election_name": self.election_config.election_name,
                "election_date": self.election_config.election_date,
                "description": "Czech municipality registry with electoral information",
            },
            "municipalities": {},
        }

        for code, info in self.municipalities.items():
            registry_data["municipalities"][code] = {
                "municipality_code": info.municipality_code,
                "municipality_name": info.municipality_name,
                "region_code": info.region_code,
                "district_code": info.district_code,
                "council_type": info.council_type,
                "council_kind": info.council_kind,
                "mandates": info.mandates,
                "election_districts": info.election_districts,
                "status": info.status,
                "parent_municipality": info.parent_municipality,
            }

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(registry_data, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved municipality registry to {output_path}")
        return str(output_path)


if __name__ == "__main__":
    # Test the registry
    logging.basicConfig(level=logging.INFO)

    import sys

    # Allow specifying election_id as command line argument
    election_id = sys.argv[1] if len(sys.argv) > 1 else "kv2022"

    print(f"\nTesting with election: {election_id}")
    registry = MunicipalityRegistry(election_config=election_id)
    municipalities = registry.parse_municipality_registry()

    print(f"Found {len(municipalities)} municipality entries")

    # Show some examples
    valid_municipalities = registry.get_municipalities_with_mandates()
    print(f"Valid municipalities with elections: {len(valid_municipalities)}")

    # Search for Prague
    prague_results = registry.search_municipalities("Praha")
    print(f"\nPrague-related municipalities: {len(prague_results)}")
    for result in prague_results[:5]:
        print(
            f"  {result.municipality_code}: {result.municipality_name} ({result.mandates} mandates)"
        )

    # Save to JSON
    registry.save_registry_to_json()

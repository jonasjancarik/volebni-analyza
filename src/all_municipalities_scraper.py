#!/usr/bin/env python3
"""
All Municipalities Scraper - Process electoral data for ALL Czech municipalities
"""

import requests
import xml.etree.ElementTree as ET
import json
import os
import logging
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup
from collections import defaultdict
from typing import Dict, List, Set, Optional, Union
import pandas as pd

from municipality_registry import MunicipalityRegistry, MunicipalityInfo
from election_config import ElectionConfig, get_election_config

logger = logging.getLogger(__name__)


class AllMunicipalitiesScraper:
    """
    Scraper for electoral data from ALL Czech municipalities
    """

    def __init__(
        self,
        election_config: Optional[Union[ElectionConfig, str]] = None,
        data_dir: Optional[str] = None,
    ):
        """
        Initialize scraper for all municipalities

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
        self.municipality_registry = MunicipalityRegistry(
            election_config=self.election_config
        )
        self.party_registry = {}  # Cache for party information

    def ensure_data_dir(self):
        """Deprecated: Use election_config.ensure_directories() instead"""
        logger.warning(
            "ensure_data_dir() is deprecated. Directories are now managed by ElectionConfig."
        )
        self.election_config.ensure_directories()

    def download_batch_xml(self, batch_number, election_date: Optional[str] = None):
        """Download a specific batch of electoral district data"""
        if election_date is None:
            election_date = self.election_config.election_date

        url = self.election_config.get_districts_batch_url(batch_number)
        params = None
        if url is None:
            url = self.election_config.get_districts_api_url()
            params = {"datumvoleb": election_date, "davka": batch_number}

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()

            # Save raw XML to input directory
            raw_file = (
                self.election_config.raw_input_dir
                / f"electoral_districts_batch_{batch_number}.xml"
            )
            with open(raw_file, "wb") as f:
                f.write(response.content)

            logger.info(f"Downloaded batch {batch_number} to {raw_file}")
            return raw_file

        except Exception as e:
            logger.error(f"Error downloading batch {batch_number}: {e}")
            return None

    def get_last_batch_number(self) -> Optional[int]:
        """Number of the last published batch (static batch files only)"""
        url = self.election_config.get_districts_batch_url()
        if url is None:
            return None

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            davka = ET.fromstring(response.content).find(
                "kv:DAVKA", {"kv": "http://www.volby.cz/kv/"}
            )
            return int(davka.get("PORADI_DAVKY"))
        except Exception as e:
            logger.error(f"Error reading the last batch number: {e}")
            return None

    def parse_xml_batch(self, xml_file):
        """Parse XML batch file and extract electoral district data for ALL municipalities"""
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()

            # Define namespace
            ns = {"kv": "http://www.volby.cz/kv/"}

            results = {"metadata": {}, "districts": []}

            # Extract batch metadata
            davka = root.find("kv:DAVKA", ns)
            if davka is not None:
                results["metadata"] = {
                    "election_date": davka.get("DATUMVOLEB"),
                    "batch_number": int(davka.get("PORADI_DAVKY", 0)),
                    "districts_in_batch": int(davka.get("OKRSKY_DAVKA", 0)),
                    "total_districts": int(davka.get("OKRSKY_CELKEM", 0)),
                    "processed_districts": int(davka.get("OKRSKY_ZPRAC", 0)),
                    "generation_time": root.get("DATUM_CAS_GENEROVANI"),
                }

            # Extract district data for ALL municipalities (no filtering)
            for okrsek in root.findall("kv:OKRSEK", ns):
                district_data = {
                    "municipality_code": okrsek.get("CIS_OBEC"),
                    "district_code": okrsek.get("CIS_OKRSEK"),
                    "zastupitelstvo_code": okrsek.get("KODZASTUP"),
                    "obvod_number": okrsek.get("CIS_OBVODU"),
                    "type": okrsek.get("OZNAC_TYPU"),  # OBEC or MCMO
                    "processing_order": int(okrsek.get("PORADI_ZPRAC", 0)),
                    "processing_time": okrsek.get("DATUM_CAS_ZPRAC"),
                    "repeated": okrsek.get("OPAKOVANE") == "1",
                }

                # Extract turnout data
                ucast = okrsek.find("kv:UCAST_OKRSEK", ns)
                if ucast is not None:
                    district_data["turnout"] = {
                        "registered_voters": int(ucast.get("ZAPSANI_VOLICI", 0)),
                        "issued_ballots": int(ucast.get("VYDANE_OBALKY", 0)),
                        "returned_ballots": int(ucast.get("ODEVZDANE_OBALKY", 0)),
                        "valid_votes": int(ucast.get("PLATNE_HLASY", 0)),
                    }

                    # Calculate turnout percentage
                    if district_data["turnout"]["registered_voters"] > 0:
                        district_data["turnout"]["turnout_percentage"] = round(
                            (
                                district_data["turnout"]["returned_ballots"]
                                / district_data["turnout"]["registered_voters"]
                            )
                            * 100,
                            2,
                        )

                # Extract vote results by party
                district_data["party_votes"] = []
                for hlasy in okrsek.findall("kv:HLASY_OKRSEK", ns):
                    party_result = {
                        "party_list_number": int(hlasy.get("POR_STR_HLAS_LIST", 0)),
                        "votes": int(hlasy.get("HLASY", 0)),
                    }
                    district_data["party_votes"].append(party_result)

                results["districts"].append(district_data)

            return results

        except ET.ParseError as e:
            logger.error(f"XML parsing error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing XML file {xml_file}: {e}")
            return None

    def download_and_parse_party_registry(self) -> Dict[str, Dict[int, Dict]]:
        """Download and parse the kvros.xml file to get ALL party information"""
        url = self.election_config.get_party_registry_url()

        try:
            # Check if we already have the file
            register_file = (
                self.election_config.raw_input_dir
                / f"{self.election_config.party_registry_file.replace('.xml', '_electoral_parties_register.xml')}"
            )

            if not register_file.exists():
                logger.info(
                    f"Downloading Electoral Parties Register for {self.election_config.election_name}..."
                )
                response = self.session.get(
                    url, timeout=60
                )  # Longer timeout for large file
                response.raise_for_status()

                with open(register_file, "wb") as f:
                    f.write(response.content)
                logger.info(f"Saved party registry to {register_file}")

            # Parse the XML to extract party information for ALL municipalities
            logger.info("Parsing party registry for all municipalities...")
            tree = ET.parse(register_file)
            root = tree.getroot()

            ns = {"kv": "http://www.volby.cz/kv/"}

            # Structure: {municipality_code: {party_list_number: {name, mandates, votes, percentage}}}
            party_data = defaultdict(dict)

            rows = root.findall(".//kv:KV_ROS_ROW", ns)

            for row in rows:
                # Extract all relevant fields
                municipality_code = self._get_text(row, "kv:KODZASTUP", ns)
                party_list_number = self._get_int(row, "kv:POR_STR_HL", ns)
                party_name_full = self._get_text(row, "kv:NAZEVCELK", ns)
                party_name_short = self._get_text(row, "kv:ZKRATKAO30", ns)
                mandates_won = self._get_int(row, "kv:MAND_STR", ns)
                votes_received = self._get_int(row, "kv:HLASY_STR", ns)
                vote_percentage = self._get_float(row, "kv:PROCHLSTR", ns)

                if municipality_code and party_list_number is not None:
                    # Choose the best party name (prefer shorter if reasonable)
                    party_name = party_name_full or f"Party List {party_list_number}"
                    if (
                        party_name_short
                        and len(party_name_short) < len(party_name)
                        and party_name_short != "SNK"
                    ):
                        party_name = party_name_short

                    party_data[municipality_code][party_list_number] = {
                        "party_name": party_name,
                        "party_name_full": party_name_full,
                        "party_name_short": party_name_short,
                        "mandates_won": mandates_won or 0,
                        "votes_received": votes_received or 0,
                        "vote_percentage": vote_percentage or 0.0,
                    }

            logger.info(f"Loaded party data for {len(party_data)} municipalities")

            # Show some statistics
            total_parties = sum(len(parties) for parties in party_data.values())
            municipalities_with_data = len([m for m in party_data if party_data[m]])
            logger.info(f"Total party entries: {total_parties}")
            logger.info(f"Municipalities with party data: {municipalities_with_data}")

            self.party_registry = party_data
            return party_data

        except Exception as e:
            logger.error(f"Error downloading/parsing party registry: {e}")
            return {}

    def _get_text(self, element, path: str, namespace: dict) -> str:
        """Safely extract text from XML element"""
        elem = element.find(path, namespace)
        return elem.text.strip() if elem is not None and elem.text else None

    def _get_int(self, element, path: str, namespace: dict) -> int:
        """Safely extract integer from XML element"""
        text = self._get_text(element, path, namespace)
        try:
            return int(text) if text else None
        except (ValueError, TypeError):
            return None

    def _get_float(self, element, path: str, namespace: dict) -> float:
        """Safely extract float from XML element"""
        text = self._get_text(element, path, namespace)
        try:
            return float(text) if text else None
        except (ValueError, TypeError):
            return None

    def collect_all_municipality_data(self, max_batches=200) -> Dict[str, any]:
        """Collect electoral data for ALL municipalities from all batch files"""
        logger.info("Collecting electoral data for ALL Czech municipalities...")

        all_districts = []
        zastupitelstvo_found = (
            set()
        )  # Track by zastupitelstvo codes, not municipality codes
        processed_batches = []

        # Process all existing batch files first
        raw_dir = self.election_config.raw_input_dir
        existing_files = list(raw_dir.glob("electoral_districts_batch_*.xml"))

        if existing_files:
            logger.info(f"Processing {len(existing_files)} existing batch files...")
            for xml_file in existing_files:
                batch_data = self.parse_xml_batch(xml_file)
                if batch_data and batch_data["districts"]:
                    all_districts.extend(batch_data["districts"])
                    # Track zastupitelstvo codes found (elections, not just geographic municipalities)
                    for district in batch_data["districts"]:
                        if district["zastupitelstvo_code"]:
                            zastupitelstvo_found.add(district["zastupitelstvo_code"])
                    processed_batches.append(xml_file.name)

        # If we don't have enough data, download more batches
        if len(processed_batches) < 10:  # Adjust threshold as needed
            logger.info(
                "Downloading additional batch files to ensure complete coverage..."
            )

            last_batch = self.get_last_batch_number() or max_batches
            logger.info(f"Last batch to download: {last_batch}")

            for batch_num in range(1, last_batch + 1):
                batch_file_name = f"electoral_districts_batch_{batch_num}.xml"
                if batch_file_name not in processed_batches:
                    xml_file = self.download_batch_xml(batch_num)
                    if xml_file:
                        batch_data = self.parse_xml_batch(xml_file)
                        if batch_data and batch_data["districts"]:
                            all_districts.extend(batch_data["districts"])
                            # Track zastupitelstvo codes found
                            for district in batch_data["districts"]:
                                if district["zastupitelstvo_code"]:
                                    zastupitelstvo_found.add(
                                        district["zastupitelstvo_code"]
                                    )
                            processed_batches.append(xml_file.name)

        all_districts = self._drop_superseded_districts(all_districts)

        logger.info(f"Collected data from {len(processed_batches)} batch files")
        logger.info(f"Found {len(all_districts)} total electoral districts")
        logger.info(
            f"Covering {len(zastupitelstvo_found)} council elections (zastupitelstvo)"
        )

        # Group districts by zastupitelstvo (council election)
        municipalities_data = self._group_districts_by_municipality(all_districts)

        return {
            "metadata": {
                "total_districts": len(all_districts),
                "total_zastupitelstvo": len(zastupitelstvo_found),
                "processed_batches": len(processed_batches),
                "batch_files": processed_batches,
                "collection_date": datetime.now().isoformat(),
                "source": "XML_API_all_municipalities_by_zastupitelstvo",
            },
            "municipalities": municipalities_data,
            "raw_districts": all_districts,
        }

    @staticmethod
    def _drop_superseded_districts(districts: List[Dict]) -> List[Dict]:
        """Keep only the latest record of each precinct.

        ČSÚ re-sends a precinct in a later batch when its result is corrected,
        so counting every record would count those precincts twice.
        """
        latest = {}
        for district in districts:
            key = (
                district["zastupitelstvo_code"],
                district["municipality_code"],
                district["district_code"],
                district["obvod_number"],
            )
            current = latest.get(key)
            if current is None or (
                district["processing_time"] or "",
                district["processing_order"],
            ) >= (current["processing_time"] or "", current["processing_order"]):
                latest[key] = district

        dropped = len(districts) - len(latest)
        if dropped:
            logger.info(f"Dropped {dropped} superseded precinct records")
        return list(latest.values())

    def _group_districts_by_municipality(
        self, all_districts: List[Dict]
    ) -> Dict[str, Dict]:
        """Group electoral districts by zastupitelstvo (council election)"""
        municipalities = defaultdict(
            lambda: {
                "districts": [],
                "summary": {
                    "total_districts": 0,
                    "total_registered_voters": 0,
                    "total_returned_ballots": 0,
                    "total_valid_votes": 0,
                    "turnout_percentage": 0.0,
                },
                "party_totals": defaultdict(int),
            }
        )

        for district in all_districts:
            # Use zastupitelstvo_code (KODZASTUP) instead of municipality_code (CIS_OBEC)
            # This ensures we group by the actual council election, not just the geographic municipality
            zastupitelstvo_code = district["zastupitelstvo_code"]
            if not zastupitelstvo_code:
                continue

            municipalities[zastupitelstvo_code]["districts"].append(district)

            # Aggregate turnout data
            if "turnout" in district:
                turnout = district["turnout"]
                summary = municipalities[zastupitelstvo_code]["summary"]
                summary["total_registered_voters"] += turnout.get(
                    "registered_voters", 0
                )
                summary["total_returned_ballots"] += turnout.get("returned_ballots", 0)
                summary["total_valid_votes"] += turnout.get("valid_votes", 0)
                summary["total_districts"] += 1

            # Aggregate party votes
            for party_vote in district.get("party_votes", []):
                party_num = party_vote.get("party_list_number")
                votes = party_vote.get("votes", 0)
                if party_num:
                    municipalities[zastupitelstvo_code]["party_totals"][party_num] += (
                        votes
                    )

        # Calculate turnout percentages
        for zastupitelstvo_code, data in municipalities.items():
            summary = data["summary"]
            if summary["total_registered_voters"] > 0:
                summary["turnout_percentage"] = round(
                    (
                        summary["total_returned_ballots"]
                        / summary["total_registered_voters"]
                    )
                    * 100,
                    2,
                )

        return dict(municipalities)

    def generate_municipality_reports(
        self, municipalities_data: Dict[str, Dict]
    ) -> Dict[str, Dict]:
        """Generate comprehensive reports for each zastupitelstvo (council election)"""
        logger.info("Generating reports for all zastupitelstvo elections...")

        # Get municipality registry for metadata
        registry = self.municipality_registry.get_all_municipalities()
        registry_by_code = {m.municipality_code: m for m in registry}

        municipality_reports = {}

        for zastupitelstvo_code, data in municipalities_data.items():
            # Get municipality info from registry using zastupitelstvo_code
            # The zastupitelstvo_code should match a municipality_code in most cases
            municipality_info = registry_by_code.get(zastupitelstvo_code)
            municipality_name = (
                municipality_info.municipality_name
                if municipality_info
                else f"Zastupitelstvo {zastupitelstvo_code}"
            )
            total_mandates = municipality_info.mandates if municipality_info else 0

            # Get party information from the party registry using zastupitelstvo_code
            party_info = self.party_registry.get(zastupitelstvo_code, {})

            # Create party results with enriched data
            party_results = []
            total_votes = sum(data["party_totals"].values())

            for party_num, votes in sorted(
                data["party_totals"].items(), key=lambda x: x[1], reverse=True
            ):
                percentage = (
                    round((votes / total_votes) * 100, 2) if total_votes > 0 else 0
                )

                # Get party information from registry
                party_data = party_info.get(party_num, {})
                party_name = party_data.get("party_name", f"Party List {party_num}")
                mandates_won = party_data.get("mandates_won", 0)
                official_votes = party_data.get(
                    "votes_received", votes
                )  # Use official count if available
                official_percentage = party_data.get("vote_percentage", percentage)

                party_results.append(
                    {
                        "list_number": str(party_num),
                        "party_name": party_name,
                        "party_name_full": party_data.get("party_name_full"),
                        "votes_absolute": official_votes,  # Use official count
                        "votes_percentage": official_percentage,  # Use official percentage
                        "mandates_won": mandates_won,  # Actual mandates won
                        "total_mandates": total_mandates,  # Total available mandates
                        "data_source": "kvros_registry_with_xml_districts",
                    }
                )

            # Calculate summary statistics
            total_mandates_won = sum(p["mandates_won"] for p in party_results)

            # Create municipality report (using zastupitelstvo_code as the key)
            municipality_reports[zastupitelstvo_code] = {
                "metadata": {
                    "municipality_code": zastupitelstvo_code,  # This is actually the zastupitelstvo code
                    "municipality_name": municipality_name,
                    "total_mandates": total_mandates,
                    "mandates_won": total_mandates_won,
                    "election_id": self.election_config.election_id,
                    "election_name": self.election_config.election_name,
                    "election_year": self.election_config.election_date[
                        :4
                    ],  # Extract year from YYYYMMDD
                    "election_date": self.election_config.election_date,
                    "data_source": "All_municipalities_scraper_with_kvros_by_zastupitelstvo",
                },
                "summary_statistics": {
                    "electoral_districts": data["summary"]["total_districts"],
                    "registered_voters": data["summary"]["total_registered_voters"],
                    "turnout_percentage": data["summary"]["turnout_percentage"],
                    "valid_votes": data["summary"]["total_valid_votes"],
                    "parties_participating": len(data["party_totals"]),
                    "parties_with_mandates": len(
                        [p for p in party_results if p["mandates_won"] > 0]
                    ),
                },
                "party_results": party_results,
                "district_data": data["districts"],
            }

        return municipality_reports

    def save_all_data(
        self,
        municipalities_data: Dict[str, Dict],
        municipality_reports: Dict[str, Dict],
    ) -> str:
        """Save all collected data to files"""
        output_dir = self.election_config.results_dir
        output_dir.mkdir(exist_ok=True)

        # Save comprehensive data
        comprehensive_file = output_dir / "all_municipalities_comprehensive.json"
        comprehensive_data = {
            "metadata": {
                "total_zastupitelstvo": len(municipalities_data),
                "collection_date": datetime.now().isoformat(),
                "election_id": self.election_config.election_id,
                "election_name": self.election_config.election_name,
                "election_date": self.election_config.election_date,
                "source": "All_municipalities_scraper_with_kvros_by_zastupitelstvo",
                "description": "Complete electoral data for all Czech council elections (zastupitelstvo) with party names and mandates. Each entry represents a specific council election, distinguished by KODZASTUP.",
                "note": "Data is grouped by zastupitelstvo_code (KODZASTUP) to properly distinguish between municipal (OBEC) and district (MCMO) elections in the same geographic area.",
            },
            "municipalities": municipality_reports,
        }

        with open(comprehensive_file, "w", encoding="utf-8") as f:
            json.dump(comprehensive_data, f, ensure_ascii=False, indent=2)

        logger.info(
            f"Saved comprehensive data for {len(municipalities_data)} council elections to {comprehensive_file}"
        )

        # Save municipality index for quick lookup
        index_file = output_dir / "municipality_index.json"
        municipality_index = {}

        for code, report in municipality_reports.items():
            metadata = report["metadata"]
            stats = report["summary_statistics"]

            municipality_index[code] = {
                "name": metadata["municipality_name"],
                "mandates": metadata["total_mandates"],
                "mandates_won": metadata["mandates_won"],
                "districts": stats["electoral_districts"],
                "turnout": stats["turnout_percentage"],
                "parties": stats["parties_participating"],
                "parties_with_mandates": stats["parties_with_mandates"],
                "registered_voters": stats["registered_voters"],
            }

        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(municipality_index, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved municipality index to {index_file}")
        return str(comprehensive_file)

    def run_complete_analysis(self) -> str:
        """Run complete analysis for all council elections (zastupitelstvo)"""
        logger.info(
            "Starting complete electoral analysis for ALL Czech council elections (zastupitelstvo)"
        )

        # Step 1: Load municipality registry
        self.municipality_registry.parse_municipality_registry()

        # Step 2: Download and parse party registry (kvros.xml)
        self.download_and_parse_party_registry()

        # Step 3: Collect all electoral data
        all_data = self.collect_all_municipality_data()

        # Step 4: Generate municipality reports
        municipality_reports = self.generate_municipality_reports(
            all_data["municipalities"]
        )

        # Step 5: Save all data
        output_file = self.save_all_data(
            all_data["municipalities"], municipality_reports
        )

        logger.info(f"Complete analysis finished. Results saved to {output_file}")
        logger.info(
            f"Processed {len(municipality_reports)} council elections (zastupitelstvo)"
        )
        return output_file


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    import sys

    # Allow specifying election_id as command line argument
    election_id = sys.argv[1] if len(sys.argv) > 1 else "kv2022"

    print(f"\nAnalyzing election: {election_id}")
    scraper = AllMunicipalitiesScraper(election_config=election_id)
    result_file = scraper.run_complete_analysis()

    print(f"Analysis complete! Results saved to: {result_file}")

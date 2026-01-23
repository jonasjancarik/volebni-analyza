#!/usr/bin/env python3
"""Parliamentary elections scraper."""

import requests
import json
import logging
import zipfile
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Optional

from all_municipalities_scraper import AllMunicipalitiesScraper
from election_config import ElectionConfig
from parliamentary_parsers import (
    parse_candidate_registry,
    parse_municipality_registry,
    parse_party_list,
    parse_party_votes,
    parse_polling_stations,
)

logger = logging.getLogger(__name__)


class ParliamentaryScraper(AllMunicipalitiesScraper):
    """Scraper for parliamentary election data (PS elections)."""

    def __init__(self, election_config: ElectionConfig):
        """Initialize parliamentary scraper."""
        super().__init__(election_config)

        if self.election_config.election_type != "parliamentary":
            logger.warning(
                f"Election type is '{self.election_config.election_type}', "
                f"expected 'parliamentary'. This may cause issues."
            )

        # Parliamentary-specific attributes
        self.candidate_registry = {}  # psrk.xml data
        self.party_list = {}  # psrkl.xml data
        self.electoral_districts = {}  # VOLKRAJ 1-14 data
        self.obec_registry = {}  # pscoco.xml mapping
        self.party_votes_by_station = {}  # pst4p.xml data
        self.party_votes_by_district = {}  # Aggregated party votes by VOLKRAJ
        self.district_turnout = {}  # Aggregated turnout by VOLKRAJ

    def download_zip_archive(self, zip_filename: str) -> Optional[Path]:
        """Download a ZIP archive from parliamentary opendata."""
        url = f"{self.election_config.opendata_url}/{zip_filename}"
        output_path = self.election_config.raw_input_dir / zip_filename

        # Skip if already downloaded
        if output_path.exists():
            logger.info(f"ZIP archive already exists: {output_path}")
            return output_path

        try:
            logger.info(f"Downloading ZIP archive from {url}...")
            response = self.session.get(
                url, timeout=120
            )  # Longer timeout for large files
            response.raise_for_status()

            with open(output_path, "wb") as f:
                f.write(response.content)

            logger.info(
                f"Downloaded {zip_filename} ({len(response.content) / 1024 / 1024:.1f} MB)"
            )
            return output_path

        except Exception as e:
            logger.error(f"Error downloading {zip_filename}: {e}")
            return None

    def extract_xml_from_zip(self, zip_path: Path, xml_filename: str) -> Optional[Path]:
        """Extract a specific XML file from a ZIP archive."""
        output_path = self.election_config.raw_input_dir / xml_filename

        # Skip if already extracted
        if output_path.exists():
            logger.info(f"XML file already extracted: {output_path}")
            return output_path

        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                # Find the XML file (case-insensitive)
                xml_files = [
                    f
                    for f in zip_ref.namelist()
                    if f.lower().endswith(xml_filename.lower())
                ]

                if not xml_files:
                    logger.error(f"XML file {xml_filename} not found in {zip_path}")
                    return None

                # Extract the file
                zip_ref.extract(xml_files[0], self.election_config.raw_input_dir)

                # Rename if needed (case mismatch)
                extracted_path = self.election_config.raw_input_dir / xml_files[0]
                if extracted_path != output_path:
                    extracted_path.rename(output_path)

                logger.info(f"Extracted {xml_filename} from {zip_path.name}")
                return output_path

        except Exception as e:
            logger.error(f"Error extracting {xml_filename} from {zip_path}: {e}")
            return None

    def download_and_parse_party_list(self) -> Dict[int, Dict]:
        """Download and parse psrkl.xml (party/coalition list)."""
        logger.info("Downloading parliamentary party list (psrkl.xml)...")

        # Step 1: Download the registry ZIP
        zip_filename = f"{self.election_config.election_id.upper()}reg{self.election_config.election_date}_xml.zip"
        zip_path = self.download_zip_archive(zip_filename)

        if not zip_path:
            logger.error("Failed to download registry ZIP")
            return {}

        # Step 2: Extract psrkl.xml
        xml_path = self.extract_xml_from_zip(zip_path, "psrkl.xml")

        if not xml_path:
            logger.error("Failed to extract psrkl.xml")
            return {}

        # Step 3: Parse the XML
        party_list = parse_party_list(xml_path)
        self.party_list = party_list
        return party_list

    def download_and_parse_candidate_registry(self) -> Dict[int, List[Dict]]:
        """Download and parse psrk.xml (candidate registry)."""
        logger.info("Downloading candidate registry (psrk.xml)...")

        # Step 1: Download the registry ZIP (might already be downloaded)
        zip_filename = f"{self.election_config.election_id.upper()}reg{self.election_config.election_date}_xml.zip"
        zip_path = self.download_zip_archive(zip_filename)

        if not zip_path:
            logger.error("Failed to download registry ZIP")
            return {}

        # Step 2: Extract psrk.xml
        xml_path = self.extract_xml_from_zip(zip_path, "psrk.xml")

        if not xml_path:
            logger.error("Failed to extract psrk.xml")
            return {}

        # Step 3: Parse the XML
        candidates_by_district = parse_candidate_registry(xml_path)
        self.candidate_registry = candidates_by_district
        return self.candidate_registry

    def download_and_parse_municipality_registry(self) -> Dict[str, Dict]:
        """Download and parse pscoco.xml (municipality registry with VOLKRAJ mapping)."""
        logger.info("Downloading municipality registry (pscoco.xml)...")

        xml_path = self.election_config.raw_input_dir / "pscoco.xml"

        if not xml_path.exists():
            zip_filename = f"{self.election_config.election_id.upper()}ciselniky{self.election_config.election_date}_xml.zip"
            zip_path = self.download_zip_archive(zip_filename)

            if not zip_path:
                logger.error("Failed to download ciselniky ZIP for municipality registry")
                return {}

            xml_path = self.extract_xml_from_zip(zip_path, "pscoco.xml")

        if not xml_path:
            logger.error("Failed to extract pscoco.xml")
            return {}

        obec_registry = parse_municipality_registry(xml_path)
        self.obec_registry = obec_registry
        return obec_registry

    def download_and_parse_polling_stations(
        self, obec_registry: Optional[Dict[str, Dict]] = None
    ) -> Dict[int, Dict]:
        """Download and parse pst4.xml (polling station results)."""
        logger.info("Downloading polling station results (pst4.xml)...")

        # Step 1: Download the data ZIP
        zip_filename = f"{self.election_config.election_id.upper()}data{self.election_config.election_date}_xml.zip"
        zip_path = self.download_zip_archive(zip_filename)

        if not zip_path:
            logger.error("Failed to download data ZIP")
            return {}

        # Step 2: Extract pst4.xml
        xml_path = self.extract_xml_from_zip(zip_path, "pst4.xml")

        if not xml_path:
            logger.error("Failed to extract pst4.xml")
            return {}

        # Step 3: Parse the XML
        logger.info("Parsing polling station data (this may take a moment)...")
        polling_stations, district_turnout = parse_polling_stations(
            xml_path, obec_registry=obec_registry
        )
        self.district_turnout = district_turnout

        return {
            "polling_stations": polling_stations,
            "district_turnout": self.district_turnout,
        }

    def download_and_parse_party_votes(
        self, obec_registry: Optional[Dict[str, Dict]] = None
    ) -> Dict[str, Dict]:
        """Download and parse pst4p.xml (party votes by polling station)."""
        logger.info("Downloading party results (pst4p.xml)...")

        zip_filename = f"{self.election_config.election_id.upper()}data{self.election_config.election_date}_xml.zip"
        zip_path = self.download_zip_archive(zip_filename)

        if not zip_path:
            logger.error("Failed to download data ZIP for party votes")
            return {}

        xml_path = self.extract_xml_from_zip(zip_path, "pst4p.xml")

        if not xml_path:
            logger.error("Failed to extract pst4p.xml")
            return {}

        party_votes_by_station, party_votes_by_district, rows_parsed = (
            parse_party_votes(xml_path, obec_registry=obec_registry)
        )

        logger.info(f"Parsed {rows_parsed} party vote rows")

        self.party_votes_by_station = party_votes_by_station
        self.party_votes_by_district = party_votes_by_district

        return {
            "party_votes_by_station": self.party_votes_by_station,
            "party_votes_by_district": self.party_votes_by_district,
        }

    def collect_all_municipality_data(self, max_batches=200) -> Dict[str, any]:
        """Collect parliamentary election data (no batch API)."""
        logger.info("Collecting parliamentary election data...")

        # Step 1: Download and parse party list
        self.download_and_parse_party_list()

        # Step 2: Download and parse candidate registry
        self.download_and_parse_candidate_registry()

        # Step 3: Download and parse municipality registry (OBEC -> VOLKRAJ mapping)
        obec_registry = self.download_and_parse_municipality_registry()

        # Step 4: Download and parse polling station results
        polling_data = self.download_and_parse_polling_stations(
            obec_registry=obec_registry
        )

        # Step 5: Download and parse party votes by polling station
        party_votes = self.download_and_parse_party_votes(obec_registry=obec_registry)

        polling_stations = polling_data.get("polling_stations", [])
        party_votes_by_station = party_votes.get("party_votes_by_station", {})

        for station in polling_stations:
            station_id = station.get("station_id")
            if station_id is not None:
                station["party_votes"] = party_votes_by_station.get(station_id, [])

        # For now, return the collected data
        return {
            "metadata": {
                "election_id": self.election_config.election_id,
                "election_name": self.election_config.election_name,
                "election_date": self.election_config.election_date,
                "collection_date": datetime.now().isoformat(),
                "source": "ParliamentaryScraper",
                "electoral_districts": 14,
            },
            "party_list": self.party_list,
            "candidates": self.candidate_registry,
            "polling_stations": polling_stations,
        }

    def generate_municipality_reports(
        self, municipalities_data: Dict[str, Dict]
    ) -> Dict[str, Dict]:
        """Generate reports for electoral districts instead of municipalities."""
        logger.info("Generating reports for electoral districts...")

        district_reports = {}

        # District names (VOLKRAJ 1-14)
        district_names = {1: "Praha", 2: "Středočeský", 3: "Jihočeský", 4: "Plzeňský", 5: "Karlovarský", 6: "Ústecký", 7: "Liberecký", 8: "Královéhradecký", 9: "Pardubický", 10: "Vysočina", 11: "Jihomoravský", 12: "Olomoucký", 13: "Zlínský", 14: "Moravskoslezský"}

        # For each electoral district
        for district_num in range(1, 15):
            candidates = self.candidate_registry.get(district_num, [])

            # Aggregate candidate stats by party
            candidate_stats = defaultdict(
                lambda: {
                    "votes": 0,
                    "candidates": 0,
                    "mandates": 0,
                    "preferential_votes": 0,
                }
            )

            for candidate in candidates:
                party_code = candidate["party_code"]
                candidate_stats[party_code]["candidates"] += 1
                candidate_stats[party_code]["preferential_votes"] += candidate[
                    "preferential_votes"
                ]
                if candidate["mandate_won"]:
                    candidate_stats[party_code]["mandates"] += 1

            party_votes = self.party_votes_by_district.get(district_num, {})
            total_votes = sum(party_votes.values())
            party_codes = set(party_votes.keys()) | set(candidate_stats.keys())

            # Create party list with details
            party_list = []
            if party_votes:
                party_codes_sorted = sorted(
                    party_codes, key=lambda code: party_votes.get(code, 0), reverse=True
                )
            else:
                party_codes_sorted = sorted(
                    party_codes,
                    key=lambda code: candidate_stats[code]["mandates"],
                    reverse=True,
                )

            for party_code in party_codes_sorted:
                stats = candidate_stats.get(
                    party_code,
                    {
                        "candidates": 0,
                        "mandates": 0,
                        "preferential_votes": 0,
                    },
                )
                votes = party_votes.get(party_code, 0)
                percentage = round((votes / total_votes) * 100, 2) if total_votes else 0
                party_info = self.party_list.get(party_code, {})
                party_list.append(
                    {
                        "party_code": party_code,
                        "party_name": party_info.get(
                            "party_name", f"Party {party_code}"
                        ),
                        "party_name_short": party_info.get("party_name_short", ""),
                        "votes_absolute": votes,
                        "votes_percentage": percentage,
                        "candidates": stats["candidates"],
                        "mandates": stats["mandates"],
                        "preferential_votes": stats["preferential_votes"],
                    }
                )

            turnout_summary = self.district_turnout.get(district_num, {})

            district_reports[district_num] = {
                "metadata": {
                    "district_number": district_num,
                    "district_name": district_names.get(
                        district_num, f"District {district_num}"
                    ),
                    "election_id": self.election_config.election_id,
                    "election_name": self.election_config.election_name,
                },
                "summary_statistics": {
                    "total_candidates": len(candidates),
                    "parties_participating": len(party_codes),
                    "total_mandates": sum(
                        stats["mandates"] for stats in candidate_stats.values()
                    ),
                    "polling_stations": turnout_summary.get("polling_stations", 0),
                    "registered_voters": turnout_summary.get("registered_voters", 0),
                    "returned_ballots": turnout_summary.get("returned_ballots", 0),
                    "valid_votes": turnout_summary.get("valid_votes", 0),
                    "turnout_percentage": turnout_summary.get("turnout_percentage", 0),
                },
                "party_results": party_list,
                "candidates": candidates,
            }

        return district_reports

    def save_all_data(
        self,
        municipalities_data: Dict[str, Dict],
        municipality_reports: Dict[str, Dict],
    ) -> str:
        """Save parliamentary election data to JSON outputs."""
        output_dir = self.election_config.results_dir
        output_dir.mkdir(exist_ok=True)

        # Save comprehensive data
        comprehensive_file = output_dir / "parliamentary_election_results.json"
        comprehensive_data = {
            "metadata": {
                "election_id": self.election_config.election_id,
                "election_name": self.election_config.election_name,
                "election_date": self.election_config.election_date,
                "collection_date": datetime.now().isoformat(),
                "source": "ParliamentaryScraper",
                "electoral_districts": 14,
            },
            "electoral_districts": municipality_reports,
            "raw_data": municipalities_data,
        }

        with open(comprehensive_file, "w", encoding="utf-8") as f:
            json.dump(comprehensive_data, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved parliamentary election results to {comprehensive_file}")

        # Save district index for quick lookup
        index_file = output_dir / "district_index.json"
        district_index = {}

        for district_num, report in municipality_reports.items():
            metadata = report["metadata"]
            stats = report["summary_statistics"]

            district_index[district_num] = {
                "name": metadata["district_name"],
                "candidates": stats["total_candidates"],
                "parties": stats["parties_participating"],
                "mandates": stats["total_mandates"],
            }

        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(district_index, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved district index to {index_file}")
        return str(comprehensive_file)

    def run_complete_analysis(self) -> str:
        """Run complete parliamentary election analysis."""
        logger.info("Starting parliamentary election analysis...")

        # Step 1: Collect all data (downloads and parses all files)
        all_data = self.collect_all_municipality_data()

        # Step 2: Generate district reports
        district_reports = self.generate_municipality_reports(all_data)

        # Step 3: Save all data
        output_file = self.save_all_data(all_data, district_reports)

        logger.info(
            f"Parliamentary election analysis complete. Results saved to {output_file}"
        )
        logger.info(f"Processed {len(district_reports)} electoral districts")

        return output_file


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    # Allow specifying election_id as command line argument
    election_id = sys.argv[1] if len(sys.argv) > 1 else "ps2025"

    from election_config import get_election_config

    config = get_election_config(election_id)
    print(f"\nAnalyzing parliamentary election: {config.election_name}")

    scraper = ParliamentaryScraper(config)
    result_file = scraper.run_complete_analysis()

    print(f"\nAnalysis complete! Results saved to: {result_file}")

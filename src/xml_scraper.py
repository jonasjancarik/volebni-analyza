#!/usr/bin/env python3
"""
XML scraper for detailed electoral district data from Czech election API
"""

import requests
import xml.etree.ElementTree as ET
import json
import os
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


class ElectoralDistrictXMLScraper:
    """
    Scraper for detailed electoral district (okrsky) data from XML API
    """

    def __init__(self, data_dir="data"):
        self.data_dir = Path(data_dir)
        self.ensure_data_dir()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
        )

    def ensure_data_dir(self):
        """Create data directory structure"""
        subdirs = ["raw", "processed", "detailed", "results"]
        for subdir in subdirs:
            (self.data_dir / subdir).mkdir(parents=True, exist_ok=True)

    def download_batch_xml(self, batch_number, election_date="20220923"):
        """Download a specific batch of electoral district data"""
        url = "https://www.volby.cz/pls/kv2022/vysledky_okrsky"
        params = {"datumvoleb": election_date, "davka": batch_number}

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()

            # Save raw XML
            raw_file = (
                self.data_dir / "raw" / f"electoral_districts_batch_{batch_number}.xml"
            )
            with open(raw_file, "wb") as f:
                f.write(response.content)

            logger.info(f"Downloaded batch {batch_number} to {raw_file}")
            return raw_file

        except Exception as e:
            logger.error(f"Error downloading batch {batch_number}: {e}")
            return None

    def parse_xml_batch(self, xml_file):
        """Parse XML batch file and extract electoral district data"""
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

            # Extract district data
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

    def cleanup_unnecessary_files(self):
        """Remove batch files that don't contain Prague 5 data"""
        logger.info("Cleaning up unnecessary batch files...")

        raw_dir = self.data_dir / "raw"
        prague5_code = "500143"
        kept_files = []
        removed_files = []

        for xml_file in raw_dir.glob("electoral_districts_batch_*.xml"):
            try:
                # Quick check if this file contains Prague 5
                with open(xml_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    if prague5_code in content:
                        kept_files.append(xml_file.name)
                    else:
                        xml_file.unlink()  # Delete the file
                        removed_files.append(xml_file.name)
            except Exception as e:
                logger.warning(f"Error checking file {xml_file.name}: {e}")

        logger.info(f"Kept {len(kept_files)} relevant files: {', '.join(kept_files)}")
        logger.info(f"Removed {len(removed_files)} unnecessary files")

        return kept_files, removed_files

    def find_prague5_data_efficiently(self, max_batches=200):
        """Find Prague 5 data more efficiently, only keeping relevant batches"""
        logger.info("Searching for Prague 5 electoral district data efficiently...")

        prague5_districts = []
        prague5_code = "500143"
        relevant_batches = []

        # First, check for existing files in raw directory
        raw_dir = self.data_dir / "raw"
        existing_files = list(raw_dir.glob("*.xml"))

        for xml_file in existing_files:
            if not xml_file.exists():
                continue

            # Quick check if this file contains Prague 5
            try:
                with open(xml_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    if prague5_code not in content:
                        continue
            except:
                continue

            logger.info(f"Processing existing file: {xml_file.name}")
            relevant_batches.append(xml_file.name)

            # Parse the file
            parsed_data = self.parse_xml_batch(xml_file)
            if not parsed_data:
                continue

            # Extract ALL Prague 5 districts (both OBEC and MCMO types)
            for district in parsed_data["districts"]:
                if district["municipality_code"] == prague5_code:
                    prague5_districts.append(district)

        # If we found data in existing files, clean up and return
        if prague5_districts:
            self.cleanup_unnecessary_files()
        else:
            # Search through new batches, but be smarter about it
            logger.info("No existing Prague 5 data found, searching new batches...")

            for batch_num in range(1, max_batches + 1):
                try:
                    logger.info(f"Checking batch {batch_num}...")

                    # First, do a quick HEAD request or small download to check
                    # if the batch contains Prague 5 data before full download
                    xml_file = self.download_batch_xml(batch_num)

                    if not xml_file:
                        continue

                    # Quick check if this batch contains Prague 5
                    with open(xml_file, "r", encoding="utf-8") as f:
                        content = f.read()
                        if prague5_code not in content:
                            # Delete this file immediately if it doesn't contain Prague 5
                            xml_file.unlink()
                            continue

                    logger.info(f"Found Prague 5 data in batch {batch_num}!")
                    relevant_batches.append(xml_file.name)

                    # Parse the batch
                    parsed_data = self.parse_xml_batch(xml_file)
                    if not parsed_data:
                        continue

                    # Extract ALL Prague 5 districts
                    for district in parsed_data["districts"]:
                        if district["municipality_code"] == prague5_code:
                            prague5_districts.append(district)

                    # Continue searching for more batches - don't break early

                except Exception as e:
                    logger.error(f"Error processing batch {batch_num}: {e}")
                    continue

        if prague5_districts:
            logger.info(f"Found {len(prague5_districts)} Prague 5 electoral districts")
            logger.info(f"Relevant batch files kept: {', '.join(relevant_batches)}")

            # Separate by type for better understanding
            mcmo_districts = [d for d in prague5_districts if d["type"] == "MCMO"]
            obec_districts = [d for d in prague5_districts if d["type"] == "OBEC"]

            logger.info(
                f"  - MCMO (Prague 5 municipal district): {len(mcmo_districts)} districts"
            )
            logger.info(
                f"  - OBEC (municipality level): {len(obec_districts)} districts"
            )

            # Save detailed Prague 5 data
            output_file = (
                self.data_dir / "detailed" / "prague5_electoral_districts.json"
            )
            detailed_data = {
                "metadata": {
                    "municipality": "Praha 5",
                    "municipality_code": prague5_code,
                    "election_date": "2022-09-23",
                    "scrape_date": datetime.now().isoformat(),
                    "districts_found": len(prague5_districts),
                    "mcmo_districts": len(mcmo_districts),
                    "obec_districts": len(obec_districts),
                    "relevant_batch_files": relevant_batches,
                },
                "districts": prague5_districts,
            }

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(detailed_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Saved Prague 5 electoral district data to {output_file}")
            return detailed_data
        else:
            logger.warning("No Prague 5 electoral district data found")
            return None

    def find_prague5_data(self, max_batches=200):
        """Find and download Prague 5 electoral district data (now calls efficient version)"""
        return self.find_prague5_data_efficiently(max_batches)

    def get_all_prague5_districts(self):
        """Get complete Prague 5 electoral district data"""
        # Check if we already have the data
        existing_file = self.data_dir / "detailed" / "prague5_electoral_districts.json"
        if existing_file.exists():
            logger.info("Loading existing Prague 5 electoral district data")
            with open(existing_file, "r", encoding="utf-8") as f:
                return json.load(f)

        # Otherwise, scrape the data
        return self.find_prague5_data()

    def run_complete_scraping(self):
        """
        Run complete scraping process with interface compatible with EnhancedPrague5Scraper
        This method transforms XML district data into the format expected by main.py
        """
        logger.info("Starting complete Prague 5 election data scraping from XML API")

        # Get district data using XML API
        district_data = self.get_all_prague5_districts()
        if not district_data:
            logger.error("Failed to scrape district data from XML API")
            return None

        # Transform district data into compatible format
        results = {
            "metadata": {
                "municipality": "Praha 5",
                "election_year": "2022",
                "source_url": "https://www.volby.cz/pls/kv2022/vysledky_okrsky (XML API)",
                "scrape_date": datetime.now().isoformat(),
                "data_source": "XML_API",
                "districts_processed": len(district_data.get("districts", [])),
            }
        }

        # Calculate summary statistics from district data
        districts = district_data.get("districts", [])
        if districts:
            total_registered = sum(
                d.get("turnout", {}).get("registered_voters", 0) for d in districts
            )
            total_returned = sum(
                d.get("turnout", {}).get("returned_ballots", 0) for d in districts
            )
            total_valid = sum(
                d.get("turnout", {}).get("valid_votes", 0) for d in districts
            )

            results["summary_statistics"] = {
                "elected_members": None,  # Not available in XML data
                "electoral_districts": len(districts),
                "registered_voters": total_registered,
                "turnout_percentage": round(
                    (total_returned / total_registered) * 100, 2
                )
                if total_registered > 0
                else 0,
                "valid_votes": total_valid,
                "data_source": "XML_district_aggregation",
            }

            # Aggregate party results from districts
            party_votes = {}
            for district in districts:
                for party_vote in district.get("party_votes", []):
                    party_num = party_vote.get("party_list_number")
                    votes = party_vote.get("votes", 0)
                    if party_num not in party_votes:
                        party_votes[party_num] = 0
                    party_votes[party_num] += votes

            # Convert to party results format
            results["party_results"] = []
            total_votes = sum(party_votes.values()) if party_votes else 0

            for party_num, votes in sorted(party_votes.items()):
                percentage = (
                    round((votes / total_votes) * 100, 2) if total_votes > 0 else 0
                )
                results["party_results"].append(
                    {
                        "list_number": str(party_num),
                        "party_name": f"Party List {party_num}",  # Names not available in XML
                        "votes_absolute": votes,
                        "votes_percentage": percentage,
                        "candidate_count": None,  # Not available in XML data
                        "mandates_won": None,  # Not available in XML data
                        "data_source": "XML_aggregation",
                    }
                )

        # Include original district data
        results["district_data"] = district_data

        # Save comprehensive results
        output_file = self.data_dir / "results" / "prague5_comprehensive_results.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        logger.info(f"Complete XML scraping finished. Saved to {output_file}")
        return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    scraper = ElectoralDistrictXMLScraper()
    prague5_data = scraper.get_all_prague5_districts()

    if prague5_data:
        print(f"Successfully extracted Prague 5 electoral district data!")
        print(f"Found {len(prague5_data['districts'])} districts")

        # Print summary
        total_voters = sum(
            d["turnout"]["registered_voters"] for d in prague5_data["districts"]
        )
        total_turnout = sum(
            d["turnout"]["returned_ballots"] for d in prague5_data["districts"]
        )

        print(f"Total registered voters: {total_voters:,}")
        print(f"Total turnout: {total_turnout:,}")
        print(f"Average turnout: {(total_turnout / total_voters) * 100:.1f}%")
    else:
        print("Failed to extract Prague 5 data")

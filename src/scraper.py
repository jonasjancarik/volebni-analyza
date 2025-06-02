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
from bs4 import BeautifulSoup

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

    def get_party_list_names(
        self, municipality_code="500143", election_date="20220923"
    ):
        """Get party list names from official Czech election data sources"""
        logger.info("Fetching party names from official election data sources...")

        # First try the Electoral Parties Register (ROS) - this should have local list number mappings
        party_names = self._download_electoral_parties_register(municipality_code)

        if not party_names:
            # Fallback to electoral parties code list (cvs.xml) - though this has universal codes
            party_names = self._download_electoral_parties_codelist()

        if not party_names:
            # Fallback to political parties code list (cns.xml)
            party_names = self._download_political_parties_codelist()

        if not party_names:
            # Last resort: try to get party names from municipality-specific data
            party_names = self._get_party_names_from_municipality_data(
                municipality_code
            )

        return party_names

    def _download_electoral_parties_codelist(self):
        """Download and parse the electoral parties code list (cvs.xml)"""
        url = "https://www.volby.cz/opendata/kv2022/xml/cvs.xml"

        try:
            logger.info("Downloading electoral parties code list (cvs.xml)...")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            # Save the code list
            codelist_file = self.data_dir / "raw" / "cvs_electoral_parties.xml"
            with open(codelist_file, "wb") as f:
                f.write(response.content)

            # Parse the XML with namespace handling
            tree = ET.parse(codelist_file)
            root = tree.getroot()

            # Define namespace
            ns = {"vol": "http://www.volby.cz/vol/"}

            party_names = {}
            # Handle both with and without namespace
            rows = root.findall(".//vol:CVS_ROW", ns) or root.findall(".//CVS_ROW")

            for row in rows:
                # Try with namespace first, then without
                vstrana = row.find("vol:VSTRANA", ns) or row.find("VSTRANA")
                nazev = (
                    row.find("vol:NAZEV_STRV", ns)
                    or row.find("NAZEV_STRV")
                    or row.find("vol:NAZEVCELK", ns)
                    or row.find("NAZEVCELK")
                )

                if vstrana is not None and nazev is not None:
                    try:
                        party_code = int(vstrana.text)
                        party_name = (
                            nazev.text.strip() if nazev.text else f"Party {party_code}"
                        )
                        party_names[party_code] = party_name
                    except (ValueError, AttributeError):
                        continue

            logger.info(f"Loaded {len(party_names)} electoral parties from code list")
            return party_names

        except Exception as e:
            logger.error(f"Error downloading electoral parties code list: {e}")
            return {}

    def _download_political_parties_codelist(self):
        """Download and parse the political parties code list (cns.xml)"""
        url = "https://www.volby.cz/opendata/kv2022/xml/cns.xml"

        try:
            logger.info("Downloading political parties code list (cns.xml)...")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            # Save the code list
            codelist_file = self.data_dir / "raw" / "cns_political_parties.xml"
            with open(codelist_file, "wb") as f:
                f.write(response.content)

            # Parse the XML with namespace handling
            tree = ET.parse(codelist_file)
            root = tree.getroot()

            # Define namespace
            ns = {"vol": "http://www.volby.cz/vol/"}

            party_names = {}
            # Handle both with and without namespace
            rows = root.findall(".//vol:CNS_ROW", ns) or root.findall(".//CNS_ROW")

            for row in rows:
                # Try with namespace first, then without
                nstrana = row.find("vol:NSTRANA", ns) or row.find("NSTRANA")
                nazev = row.find("vol:NAZEV_STRN", ns) or row.find("NAZEV_STRN")

                if nstrana is not None and nazev is not None:
                    try:
                        party_code = int(nstrana.text)
                        party_name = (
                            nazev.text.strip() if nazev.text else f"Party {party_code}"
                        )
                        party_names[party_code] = party_name
                    except (ValueError, AttributeError):
                        continue

            logger.info(f"Loaded {len(party_names)} political parties from code list")
            return party_names

        except Exception as e:
            logger.error(f"Error downloading political parties code list: {e}")
            return {}

    def _get_party_names_from_municipality_data(self, municipality_code):
        """Fallback: Get party names from municipality-specific results page"""
        logger.info("Falling back to municipality-specific party name extraction...")

        url = "https://www.volby.cz/pls/kv2022/kv1111"
        params = {
            "xjazyk": "CZ",
            "xid": "0",
            "xdz": "5",
            "xnumnuts": "1100",
            "xobec": municipality_code,
            "xstat": "0",
            "xvyber": "0",
        }

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()

            # Parse HTML to extract party names
            soup = BeautifulSoup(response.content, "html.parser")

            # Find the party results table
            party_table = soup.find("table", {"id": "kv11111_t1"})
            if not party_table:
                logger.warning("Party results table not found")
                return {}

            party_names = {}
            data_rows = party_table.find_all("tr")[2:]  # Skip header rows

            for row in data_rows:
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    # First cell contains the list number
                    list_number_text = cells[0].get_text().strip()
                    # Second cell contains the party name
                    party_name_text = cells[1].get_text().strip()

                    # Clean up the list number
                    try:
                        list_number = int(list_number_text)
                        party_names[list_number] = party_name_text
                    except ValueError:
                        continue

            logger.info(
                f"Retrieved {len(party_names)} party names from municipality page"
            )
            return party_names

        except Exception as e:
            logger.error(f"Error fetching party names from municipality page: {e}")
            return {}

    def _download_electoral_parties_register(self, municipality_code="500143"):
        """Download and parse the Electoral Parties Register (ROS) for party list mappings"""
        url = "https://www.volby.cz/opendata/kv2022/xml/kvros.xml"

        try:
            logger.info("Downloading Electoral Parties Register (kvros.xml)...")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            # Save the register
            register_file = (
                self.data_dir / "raw" / "kvros_electoral_parties_register.xml"
            )
            with open(register_file, "wb") as f:
                f.write(response.content)

            # Parse the XML with namespace handling
            tree = ET.parse(register_file)
            root = tree.getroot()

            # Define namespace for KV data (different from CVS)
            ns = {"kv": "http://www.volby.cz/kv/"}

            party_mappings = {}
            # Look for entries related to our municipality
            rows = root.findall(".//kv:KV_ROS_ROW", ns)

            for row in rows:
                # Use namespace approach (fallback doesn't work for this XML)
                kodzastup = row.find("kv:KODZASTUP", ns)
                por_str_hl = row.find("kv:POR_STR_HL", ns)  # Local party list number
                nazevcelk = row.find("kv:NAZEVCELK", ns)  # Full party name
                zkratkao30 = row.find("kv:ZKRATKAO30", ns)  # 30-char abbreviation

                # Filter for Prague 5 (municipality code 500143)
                if (
                    kodzastup is not None
                    and kodzastup.text == municipality_code
                    and por_str_hl is not None
                    and nazevcelk is not None
                ):
                    try:
                        local_list_number = int(por_str_hl.text)
                        party_name = (
                            nazevcelk.text.strip()
                            if nazevcelk.text
                            else f"Party List {local_list_number}"
                        )

                        # Prefer shorter name if available
                        if zkratkao30 is not None and zkratkao30.text:
                            short_name = zkratkao30.text.strip()
                            if (
                                len(short_name) < len(party_name)
                                and short_name != "SNK"
                            ):
                                party_name = short_name

                        party_mappings[local_list_number] = party_name
                    except (ValueError, AttributeError):
                        continue

            logger.info(
                f"Loaded {len(party_mappings)} party mappings from electoral register for Prague 5"
            )
            return party_mappings

        except Exception as e:
            logger.error(f"Error downloading electoral parties register: {e}")
            return {}

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

        # Get party names from web interface
        logger.info("Fetching party names from web interface...")
        party_names = self.get_party_list_names()

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

            # Convert to party results format with real names
            results["party_results"] = []
            total_votes = sum(party_votes.values()) if party_votes else 0

            for party_num, votes in sorted(party_votes.items()):
                percentage = (
                    round((votes / total_votes) * 100, 2) if total_votes > 0 else 0
                )

                # Use real party name if available, fallback to generic name
                party_name = party_names.get(party_num, f"Party List {party_num}")

                results["party_results"].append(
                    {
                        "list_number": str(party_num),
                        "party_name": party_name,
                        "votes_absolute": votes,
                        "votes_percentage": percentage,
                        "candidate_count": None,  # Not available in XML data
                        "mandates_won": None,  # Not available in XML data
                        "data_source": "XML_aggregation_with_web_names",
                    }
                )

        # Include original district data and party name mapping
        results["district_data"] = district_data
        results["party_name_mapping"] = party_names

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

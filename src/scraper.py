#!/usr/bin/env python3
"""
Enhanced election data scraper for Prague 5 that extracts complete results
"""

import requests
import json
import os
import time
import logging
import pandas as pd
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class EnhancedPrague5Scraper:
    """
    Enhanced scraper for Prague 5 election data with complete data extraction
    """

    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
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
            os.makedirs(os.path.join(self.data_dir, subdir), exist_ok=True)

    def clean_text(self, text):
        """Clean and normalize text data"""
        if not text:
            return ""
        return re.sub(r"\s+", " ", text.strip()).replace("\u00a0", " ")

    def parse_number(self, text):
        """Parse Czech number format (with spaces as thousands separators)"""
        if not text:
            return None
        cleaned = text.replace(" ", "").replace("\u00a0", "").replace(",", ".")
        try:
            if "." in cleaned:
                return float(cleaned)
            return int(cleaned)
        except ValueError:
            return None

    def scrape_prague5_main_results(self):
        """
        Scrape the main Prague 5 election results page with complete data extraction
        """
        logger.info("Scraping Prague 5 main results page")

        url = "https://www.volby.cz/pls/kv2022/kv1111"
        params = {
            "xjazyk": "CZ",
            "xid": "0",
            "xdz": "5",
            "xnumnuts": "1100",
            "xobec": "500143",
            "xstat": "0",
            "xvyber": "0",
        }

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            # Extract complete results
            results = {
                "metadata": {
                    "municipality": "Praha 5",
                    "election_year": "2022",
                    "source_url": response.url,
                    "scrape_date": pd.Timestamp.now().isoformat(),
                },
                "summary_statistics": self.extract_summary_statistics(soup),
                "party_results": self.extract_party_results(soup),
                "additional_links": self.extract_additional_links(soup, response.url),
            }

            # Save complete results
            output_file = os.path.join(
                self.data_dir, "results", "prague5_complete_results.json"
            )
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

            logger.info(f"Saved complete results to {output_file}")
            return results

        except Exception as e:
            logger.error(f"Error scraping main results: {e}")
            return None

    def extract_summary_statistics(self, soup):
        """Extract summary statistics from the first table (kv1111_t1)"""
        logger.info("Extracting summary statistics")

        summary_table = soup.find("table", {"id": "kv1111_t1"})
        if not summary_table:
            logger.warning("Summary statistics table not found")
            return None

        # Extract headers
        headers = []
        header_rows = summary_table.find_all("tr")[:2]  # First two rows contain headers

        for row in header_rows:
            row_headers = []
            for cell in row.find_all(["th", "td"]):
                text = self.clean_text(cell.get_text())
                colspan = int(cell.get("colspan", 1))
                rowspan = int(cell.get("rowspan", 1))
                row_headers.append(
                    {"text": text, "colspan": colspan, "rowspan": rowspan}
                )
            headers.append(row_headers)

        # Extract data row
        data_row = (
            header_rows[2] if len(header_rows) > 2 else summary_table.find_all("tr")[2]
        )
        data_cells = []

        for cell in data_row.find_all(["td", "th"]):
            text = self.clean_text(cell.get_text())
            data_cells.append(text)

        # Parse data into structured format
        summary = {
            "elected_members": self.parse_number(data_cells[0])
            if len(data_cells) > 0
            else None,
            "electoral_districts": self.parse_number(data_cells[1])
            if len(data_cells) > 1
            else None,
            "total_polling_stations": self.parse_number(data_cells[2])
            if len(data_cells) > 2
            else None,
            "reported_polling_stations": self.parse_number(data_cells[3])
            if len(data_cells) > 3
            else None,
            "reporting_percentage": self.parse_number(data_cells[4])
            if len(data_cells) > 4
            else None,
            "registered_voters": self.parse_number(data_cells[5])
            if len(data_cells) > 5
            else None,
            "ballots_issued": self.parse_number(data_cells[6])
            if len(data_cells) > 6
            else None,
            "turnout_percentage": self.parse_number(data_cells[7])
            if len(data_cells) > 7
            else None,
            "ballots_returned": self.parse_number(data_cells[8])
            if len(data_cells) > 8
            else None,
            "valid_votes": self.parse_number(data_cells[9])
            if len(data_cells) > 9
            else None,
            "raw_data": data_cells,
            "headers": headers,
        }

        return summary

    def extract_party_results(self, soup):
        """Extract party results from the second table (kv11111_t1)"""
        logger.info("Extracting party results")

        party_table = soup.find("table", {"id": "kv11111_t1"})
        if not party_table:
            logger.warning("Party results table not found")
            return []

        # Extract headers
        header_rows = party_table.find_all("tr")[:2]
        headers = []
        for row in header_rows:
            for cell in row.find_all("th"):
                headers.append(self.clean_text(cell.get_text()))

        # Extract party data
        data_rows = party_table.find_all("tr")[2:]  # Skip header rows
        parties = []

        for row in data_rows:
            cells = row.find_all(["td", "th"])
            if len(cells) < 8:  # Skip rows with insufficient data
                continue

            party_data = {
                "list_number": self.clean_text(cells[0].get_text()),
                "party_name": self.clean_text(cells[1].get_text()),
                "votes_absolute": self.parse_number(cells[2].get_text()),
                "votes_percentage": self.parse_number(cells[3].get_text()),
                "candidate_count": self.parse_number(cells[4].get_text()),
                "recalculated_base": self.parse_number(cells[5].get_text()),
                "recalculated_percentage": self.parse_number(cells[6].get_text()),
                "mandates_won": self.parse_number(cells[7].get_text()),
                "raw_data": [self.clean_text(cell.get_text()) for cell in cells],
            }

            # Extract links
            links = {}
            detail_link = cells[0].find("a")
            if detail_link:
                links["detail_url"] = detail_link.get("href")

            elected_link = cells[8].find("a") if len(cells) > 8 else None
            if elected_link:
                links["elected_members_url"] = elected_link.get("href")

            if links:
                party_data["links"] = links

            parties.append(party_data)

        return parties

    def extract_additional_links(self, soup, base_url):
        """Extract additional navigation links"""
        logger.info("Extracting additional links")

        links = {}

        # Find menu section
        menu_section = soup.find("div", {"id": "outer_menu"})
        if menu_section:
            for link in menu_section.find_all("a", href=True):
                text = self.clean_text(link.get_text())
                href = link.get("href")
                full_url = urljoin(base_url, href)

                if "Pořadí podílů hlasů" in text:
                    links["vote_share_ranking"] = full_url
                elif "Zvolení členové" in text:
                    links["elected_members"] = full_url
                elif "Náhradníci" in text:
                    links["substitute_members"] = full_url

        return links

    def scrape_party_details(self, party_results):
        """Scrape detailed information for each party"""
        logger.info("Scraping detailed party information")

        detailed_parties = []

        for party in party_results:
            if "links" not in party or "detail_url" not in party["links"]:
                detailed_parties.append(party)
                continue

            detail_url = party["links"]["detail_url"]
            full_url = f"https://www.volby.cz/pls/kv2022/{detail_url}"

            try:
                logger.info(f"Scraping details for {party['party_name']}")
                response = self.session.get(full_url, timeout=10)
                response.raise_for_status()

                soup = BeautifulSoup(response.content, "html.parser")

                # Extract candidate information
                candidates = self.extract_candidates(soup)
                party_with_details = party.copy()
                party_with_details["candidates"] = candidates
                party_with_details["detail_scraped_url"] = full_url

                detailed_parties.append(party_with_details)
                time.sleep(1)  # Be respectful

            except Exception as e:
                logger.error(
                    f"Error scraping party details for {party['party_name']}: {e}"
                )
                detailed_parties.append(party)

        return detailed_parties

    def extract_candidates(self, soup):
        """Extract candidate information from party detail page"""
        candidates = []

        # Find candidate table
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")

            # Look for candidate data
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) >= 3:
                    # Check if this looks like candidate data
                    cell_texts = [self.clean_text(cell.get_text()) for cell in cells]
                    if any(
                        text.isdigit() for text in cell_texts[:2]
                    ):  # Likely candidate number/votes
                        candidate = {
                            "raw_data": cell_texts,
                            "candidate_number": self.parse_number(cell_texts[0])
                            if cell_texts
                            else None,
                            "name": cell_texts[1] if len(cell_texts) > 1 else None,
                            "votes": self.parse_number(cell_texts[2])
                            if len(cell_texts) > 2
                            else None,
                        }
                        candidates.append(candidate)

        return candidates

    def run_complete_scraping(self):
        """Run complete scraping process"""
        logger.info("Starting complete Prague 5 election data scraping")

        # 1. Scrape main results
        main_results = self.scrape_prague5_main_results()
        if not main_results:
            logger.error("Failed to scrape main results")
            return None

        # 2. Scrape detailed party information
        if main_results.get("party_results"):
            detailed_parties = self.scrape_party_details(main_results["party_results"])
            main_results["party_results_detailed"] = detailed_parties

        # 3. Save final comprehensive results
        output_file = os.path.join(
            self.data_dir, "results", "prague5_comprehensive_results.json"
        )
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(main_results, f, ensure_ascii=False, indent=2)

        logger.info(f"Complete scraping finished. Saved to {output_file}")
        return main_results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scraper = EnhancedPrague5Scraper()
    results = scraper.run_complete_scraping()

    if results:
        print("Scraping completed successfully!")
        print(f"Found {len(results.get('party_results', []))} parties")
        print(f"Summary statistics: {results.get('summary_statistics', {})}")
    else:
        print("Scraping failed!")

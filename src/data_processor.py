import pandas as pd
import geopandas as gpd
import xml.etree.ElementTree as ET
import json
import os
import logging
from shapely.geometry import Point, Polygon
import numpy as np

logger = logging.getLogger(__name__)


class Prague5DataProcessor:
    """
    Data processor for Prague 5 election and geographic data
    """

    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.prague_5_code = "500143"

    def read_csu_csv(self, filepath, encoding="utf-8"):
        """Read ČSÚ CSV files with proper encoding handling"""
        encodings_to_try = ["utf-8", "cp1250", "iso-8859-2"]

        for encoding in encodings_to_try:
            try:
                df = pd.read_csv(filepath, encoding=encoding, sep=";")
                logger.info(f"Successfully read {filepath} with encoding {encoding}")
                return df
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.warning(
                    f"Error reading {filepath} with encoding {encoding}: {e}"
                )
                continue

        logger.error(f"Could not read {filepath} with any encoding")
        return None

    def process_municipal_results(self, year="2022"):
        """Process municipal election results for Prague 5"""
        logger.info(f"Processing municipal results for {year}")

        results_dir = os.path.join(self.data_dir, "raw")
        processed_dir = os.path.join(self.data_dir, "processed")

        # Find relevant files
        candidates_file = None
        results_file = None
        parties_file = None
        districts_file = None

        for filename in os.listdir(results_dir):
            if year in filename and filename.endswith(".csv"):
                if "kandidat" in filename.lower():
                    candidates_file = os.path.join(results_dir, filename)
                elif "vysledek" in filename.lower() or "pv_" in filename.lower():
                    results_file = os.path.join(results_dir, filename)
                elif "strana" in filename.lower():
                    parties_file = os.path.join(results_dir, filename)
                elif "okrsky" in filename.lower():
                    districts_file = os.path.join(results_dir, filename)

        processed_data = {}

        # Process candidates
        if candidates_file:
            logger.info(f"Processing candidates from {candidates_file}")
            candidates_df = self.read_csu_csv(candidates_file)
            if candidates_df is not None:
                # Filter for Prague 5
                if "KODZASTUP" in candidates_df.columns:
                    prague5_candidates = candidates_df[
                        candidates_df["KODZASTUP"] == self.prague_5_code
                    ].copy()
                else:
                    # Try other common column names
                    prague5_candidates = candidates_df

                processed_data["candidates"] = prague5_candidates

        # Process results
        if results_file:
            logger.info(f"Processing results from {results_file}")
            results_df = self.read_csu_csv(results_file)
            if results_df is not None:
                # Filter for Prague 5
                if "KODZASTUP" in results_df.columns:
                    prague5_results = results_df[
                        results_df["KODZASTUP"] == self.prague_5_code
                    ].copy()
                else:
                    prague5_results = results_df

                processed_data["results"] = prague5_results

        # Process parties
        if parties_file:
            logger.info(f"Processing parties from {parties_file}")
            parties_df = self.read_csu_csv(parties_file)
            if parties_df is not None:
                processed_data["parties"] = parties_df

        # Process electoral districts
        if districts_file:
            logger.info(f"Processing districts from {districts_file}")
            districts_df = self.read_csu_csv(districts_file)
            if districts_df is not None:
                # Filter for Prague 5
                if "KODZASTUP" in districts_df.columns:
                    prague5_districts = districts_df[
                        districts_df["KODZASTUP"] == self.prague_5_code
                    ].copy()
                else:
                    prague5_districts = districts_df

                processed_data["districts"] = prague5_districts

        # Save processed data
        output_file = os.path.join(processed_dir, f"prague5_municipal_{year}.json")

        # Convert DataFrames to JSON-serializable format
        json_data = {}
        for key, df in processed_data.items():
            if isinstance(df, pd.DataFrame):
                json_data[key] = df.to_dict("records")

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved processed data to {output_file}")
        return processed_data

    def create_district_summary(self, processed_data):
        """Create summary statistics by electoral district"""
        if "results" not in processed_data or "districts" not in processed_data:
            logger.warning("Missing results or districts data for summary")
            return None

        results_df = processed_data["results"]
        districts_df = processed_data["districts"]

        # Group results by electoral district
        if "OKRSEK" in results_df.columns:
            district_summary = (
                results_df.groupby("OKRSEK")
                .agg(
                    {
                        "PLATNE_HLASY": "sum",  # Total valid votes
                        "VOLICI": "first",  # Number of voters
                        "UCAST": "first",  # Turnout
                    }
                )
                .reset_index()
            )

            # Merge with district info
            if "OKRSEK" in districts_df.columns:
                district_summary = district_summary.merge(
                    districts_df[["OKRSEK", "NAZEV", "ADRESA"]], on="OKRSEK", how="left"
                )

            return district_summary

        return None

    def process_party_results(self, processed_data):
        """Process results by political parties"""
        if "results" not in processed_data or "parties" not in processed_data:
            logger.warning("Missing results or parties data")
            return None

        results_df = processed_data["results"]
        parties_df = processed_data["parties"]

        # Group results by party
        if "KSTRANA" in results_df.columns and "PLATNE_HLASY" in results_df.columns:
            party_results = (
                results_df.groupby("KSTRANA")
                .agg({"PLATNE_HLASY": "sum", "PROCENT": "first"})
                .reset_index()
            )

            # Merge with party names
            if "KSTRANA" in parties_df.columns:
                party_results = party_results.merge(
                    parties_df[["KSTRANA", "NAZEV", "ZKRATKA"]],
                    on="KSTRANA",
                    how="left",
                )

            # Sort by votes
            party_results = party_results.sort_values("PLATNE_HLASY", ascending=False)

            return party_results

        return None

    def parse_xml_electoral_districts(self, xml_file):
        """Parse electoral districts from XML file (RUIAN format)"""
        logger.info(f"Parsing electoral districts from {xml_file}")

        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()

            districts = []

            # Look for electoral district elements (this depends on the XML structure)
            # The exact structure may vary based on the RUIAN format
            for elem in root.iter():
                if "okrsek" in elem.tag.lower() or "district" in elem.tag.lower():
                    district_data = {}

                    # Extract attributes and child elements
                    district_data.update(elem.attrib)

                    for child in elem:
                        if child.text:
                            district_data[child.tag] = child.text

                    districts.append(district_data)

            if districts:
                districts_df = pd.DataFrame(districts)

                # Filter for Prague 5 if possible
                if "obec_kod" in districts_df.columns:
                    prague5_districts = districts_df[
                        districts_df["obec_kod"] == self.prague_5_code
                    ]
                else:
                    prague5_districts = districts_df

                return prague5_districts

        except ET.ParseError as e:
            logger.error(f"XML parsing error: {e}")
        except Exception as e:
            logger.error(f"Error processing XML file: {e}")

        return None

    def create_geospatial_data(self, districts_df):
        """Create geospatial representation of electoral districts"""
        logger.info("Creating geospatial data for districts")

        # This is a placeholder - actual implementation depends on the geographic data available
        # In practice, you would need coordinate data for electoral district boundaries

        if districts_df is None or districts_df.empty:
            logger.warning("No districts data available for geospatial processing")
            return None

        # For now, create point data if we have addresses
        if "ADRESA" in districts_df.columns:
            # You would typically geocode addresses here
            # This is a simplified example
            gdf = gpd.GeoDataFrame(districts_df)

            # Add dummy coordinates for demonstration
            # In practice, you'd geocode the addresses
            gdf["geometry"] = [
                Point(
                    14.4 + np.random.uniform(-0.01, 0.01),
                    50.05 + np.random.uniform(-0.01, 0.01),
                )
                for _ in range(len(gdf))
            ]

            return gdf

        return None

    def process_all_data(self):
        """Process all collected data"""
        logger.info("Processing all collected data")

        processed_results = {}

        # Process data for each available year
        for year in ["2022", "2018", "2014"]:
            logger.info(f"Processing data for year {year}")

            data = self.process_municipal_results(year)
            if data:
                processed_results[year] = {
                    "raw_data": data,
                    "district_summary": self.create_district_summary(data),
                    "party_results": self.process_party_results(data),
                }

        # Process electoral districts XML if available
        xml_file = os.path.join(self.data_dir, "geo", "20250503_ST_UVOH.xml")
        if os.path.exists(xml_file):
            districts_df = self.parse_xml_electoral_districts(xml_file)
            if districts_df is not None:
                processed_results["geographic_districts"] = districts_df
                processed_results["geospatial_data"] = self.create_geospatial_data(
                    districts_df
                )

        # Save comprehensive results
        output_file = os.path.join(
            self.data_dir, "processed", "prague5_comprehensive.json"
        )

        # Convert to JSON-serializable format
        json_data = {}
        for year, year_data in processed_results.items():
            if year in ["2022", "2018", "2014"]:
                json_data[year] = {}
                for key, value in year_data.items():
                    if isinstance(value, pd.DataFrame):
                        json_data[year][key] = value.to_dict("records")
                    else:
                        json_data[year][key] = value
            else:
                if isinstance(processed_results[year], pd.DataFrame):
                    json_data[year] = processed_results[year].to_dict("records")

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)

        logger.info(
            f"Comprehensive processing completed. Results saved to {output_file}"
        )
        return processed_results


if __name__ == "__main__":
    processor = Prague5DataProcessor()
    results = processor.process_all_data()
    print("Data processing completed!")

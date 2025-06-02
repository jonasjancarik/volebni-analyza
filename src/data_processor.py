import pandas as pd
import geopandas as gpd
import xml.etree.ElementTree as ET
import json
import os
import logging
from shapely.geometry import Point, Polygon
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class Prague5DataProcessor:
    """
    Data processor for Prague 5 election and geographic data
    """

    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.prague_5_code = "500143"  # Municipality code for Prague 5
        self.prague_5_districts = list(
            range(5001, 5082)
        )  # Electoral districts 5001-5081

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

    def _filter_prague5_by_district(self, df, district_column="OKRSEK"):
        """Filter dataframe for Prague 5 electoral districts (5001-5081)"""
        if district_column in df.columns:
            # Convert to numeric and filter for Prague 5 districts
            df_copy = df.copy()
            df_copy[district_column] = pd.to_numeric(
                df_copy[district_column], errors="coerce"
            )
            return df_copy[df_copy[district_column].isin(self.prague_5_districts)]
        return df

    def _filter_prague5_by_municipality(self, df, municipality_column="KODZASTUP"):
        """Filter dataframe for Prague 5 municipality"""
        if municipality_column in df.columns:
            return df[df[municipality_column] == self.prague_5_code].copy()
        return df

    def validate_prague5_districts(self, districts_df):
        """Validate that we have the expected 81 electoral districts for Prague 5"""
        if districts_df is None or districts_df.empty:
            logger.warning("No districts data to validate")
            return False

        # Check if we have a CIS_OKRSEK column and what districts we have
        district_column = None
        for col in ["CIS_OKRSEK", "OKRSEK", "CIS_OKRSEK_NUM"]:
            if col in districts_df.columns:
                district_column = col
                break

        if district_column:
            district_codes = pd.to_numeric(
                districts_df[district_column], errors="coerce"
            ).dropna()
            unique_districts = sorted(district_codes.unique())

            logger.info(f"Found {len(unique_districts)} unique electoral districts")
            if len(unique_districts) > 0:
                logger.info(
                    f"District range: {min(unique_districts)} - {max(unique_districts)}"
                )

            # Check if we have all 81 expected districts (5001-5081)
            expected_districts = set(range(5001, 5082))
            found_districts = set(unique_districts)

            missing_districts = expected_districts - found_districts
            extra_districts = found_districts - expected_districts

            if missing_districts:
                logger.warning(
                    f"Missing {len(missing_districts)} expected districts: {sorted(list(missing_districts))[:10]}..."
                )

            if extra_districts:
                logger.info(
                    f"Found {len(extra_districts)} additional districts: {sorted(list(extra_districts))[:10]}..."
                )

            prague5_count = len(found_districts & expected_districts)
            if prague5_count == 81:
                logger.info("✓ Found all 81 expected Prague 5 electoral districts!")
                return True
            else:
                logger.warning(
                    f"Expected 81 districts, found {prague5_count} matching districts"
                )
                return False

        logger.warning(
            f"No district column found for validation (columns: {list(districts_df.columns)})"
        )
        return False

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
                # Filter for Prague 5 by municipality code
                prague5_candidates = self._filter_prague5_by_municipality(candidates_df)
                processed_data["candidates"] = prague5_candidates

        # Process results
        if results_file:
            logger.info(f"Processing results from {results_file}")
            results_df = self.read_csu_csv(results_file)
            if results_df is not None:
                # Filter for Prague 5 by municipality code
                prague5_results = self._filter_prague5_by_municipality(results_df)
                processed_data["results"] = prague5_results

                # Validate that we have the expected 81 districts in results
                if not prague5_results.empty:
                    self.validate_prague5_districts(prague5_results)

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
                # Filter for Prague 5 by municipality code
                prague5_districts = self._filter_prague5_by_municipality(districts_df)
                processed_data["districts"] = prague5_districts
                logger.info(
                    f"Found {len(prague5_districts)} electoral districts for Prague 5"
                )

                # Validate that we have the expected 81 districts
                self.validate_prague5_districts(prague5_districts)

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

            # Parse the XML structure - look for OKRSEK elements
            for okrsek in root.iter():
                if okrsek.tag.endswith("}OKRSEK"):
                    district_data = {}

                    # Extract attributes from OKRSEK element
                    district_data.update(okrsek.attrib)

                    # Look for child elements like UCAST_OKRSEK (turnout) and HLASY_OKRSEK (votes)
                    for child in okrsek:
                        if child.tag.endswith("}UCAST_OKRSEK"):
                            # Add turnout data with prefix
                            for key, value in child.attrib.items():
                                district_data[f"UCAST_{key}"] = value
                        elif child.tag.endswith("}HLASY_OKRSEK"):
                            # Add vote data - for now just collect the first vote entry
                            if "HLASY_DATA" not in district_data:
                                district_data["HLASY_DATA"] = []
                            district_data["HLASY_DATA"].append(child.attrib)

                    if district_data:
                        districts.append(district_data)

            if districts:
                districts_df = pd.DataFrame(districts)
                logger.info(f"Parsed {len(districts_df)} total districts from XML")

                # Filter for Prague 5 using municipality code - this gives us exactly 81 districts
                if "CIS_OBEC" in districts_df.columns:
                    prague5_districts = districts_df[
                        districts_df["CIS_OBEC"] == self.prague_5_code
                    ].copy()
                    logger.info(
                        f"Found {len(prague5_districts)} Prague 5 electoral districts"
                    )

                    return prague5_districts
                else:
                    logger.warning("No CIS_OBEC column found in XML data")
                    return districts_df

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

        # Process electoral districts XML files from raw directory
        xml_dir = os.path.join(self.data_dir, "raw")
        if os.path.exists(xml_dir):
            all_prague5_districts = []

            # Process all XML files that contain electoral district data
            xml_files = [
                f
                for f in os.listdir(xml_dir)
                if f.endswith(".xml") and "electoral_districts" in f
            ]
            logger.info(f"Found {len(xml_files)} XML files to process")

            for xml_file in xml_files:  # Process all XML files to get all districts
                xml_path = os.path.join(xml_dir, xml_file)
                logger.info(f"Processing {xml_file}")
                districts_df = self.parse_xml_electoral_districts(xml_path)
                if districts_df is not None and not districts_df.empty:
                    all_prague5_districts.append(districts_df)

            # Combine all districts data
            if all_prague5_districts:
                combined_districts = pd.concat(all_prague5_districts, ignore_index=True)
                logger.info(
                    f"Combined data from {len(all_prague5_districts)} XML files"
                )
                logger.info(f"Total districts found: {len(combined_districts)}")

                # Remove duplicates based on CIS_OKRSEK
                if "CIS_OKRSEK" in combined_districts.columns:
                    unique_districts = combined_districts.drop_duplicates(
                        subset=["CIS_OKRSEK"]
                    )
                    logger.info(
                        f"Unique districts after deduplication: {len(unique_districts)}"
                    )

                    # Validate the final dataset
                    self.validate_prague5_districts(unique_districts)

                    processed_results["xml_districts"] = unique_districts
                    processed_results["geospatial_data"] = self.create_geospatial_data(
                        unique_districts
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

        # Create processed directory if it doesn't exist
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

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

#!/usr/bin/env python3
"""
Main script to collect and process electoral data for ALL Czech municipalities
"""

import logging
import sys
from pathlib import Path
import argparse
from datetime import datetime

# Add src directory to path for imports
sys.path.append(str(Path(__file__).parent / "src"))

from municipality_registry import MunicipalityRegistry
from all_municipalities_scraper import AllMunicipalitiesScraper
from parliamentary_scraper import ParliamentaryScraper
from election_config import (
    get_election_config,
    list_available_elections,
    get_election_info,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("all_municipalities_analysis.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def ensure_municipal_boundaries(election_config):
    """Build the precinct boundaries file for municipal maps from the 2025 GeoPackage.

    The result uses the property names of the 2022 GeoJSON (KOD, CISLO, OBEC,
    MOMC), so the map code handles both files the same way.
    """
    if not election_config.boundaries_file:
        return

    target_file = Path("input/raw") / election_config.boundaries_file
    source_file = Path("input/raw/electoral_districts_boundaries_2025_wgs84.gpkg")

    if target_file.exists():
        logger.info(f"✅ Precinct boundaries ready: {target_file}")
        return

    if not source_file.exists():
        logger.warning(
            f"⚠️  {source_file} not found, maps will use the 2022 precinct "
            "boundaries. Run the ps2025 collection first to get newer ones."
        )
        return

    try:
        import geopandas as gpd
        import shapely
    except Exception as exc:
        logger.error(f"❌ Missing geopandas, cannot prepare boundaries: {exc}")
        return

    logger.info(f"🗺️  Preparing precinct boundaries from {source_file}")
    gdf = gpd.read_file(source_file, layer="okrsky_simplified")

    # Roughly the detail of the 2022 file (generalised to 100 m);
    # coverage_simplify keeps shared borders without gaps
    gdf["geometry"] = shapely.make_valid(
        shapely.coverage_simplify(gdf.geometry.values, 0.0015)
    )
    kod_mco = gdf["kod_mco"].astype(str).str.strip()
    result = gpd.GeoDataFrame(
        {
            "KOD": gdf["kod"].astype(str),
            "CISLO": gdf["cislo"].astype(str),
            "OBEC": gdf["kod_obec"].astype(str),
            "MOMC": kod_mco.where(kod_mco != "", "0"),
        },
        geometry=gdf.geometry,
        crs=gdf.crs,
    )
    result = result[~result.geometry.is_empty]
    result.to_file(target_file, driver="GeoJSON", COORDINATE_PRECISION=5)
    logger.info(f"✅ Saved {len(result)} precinct boundaries to {target_file}")


def ensure_parliamentary_geojson_wgs84(election_config):
    """Convert 2025 polling station GeoJSON to WGS84 for map rendering."""
    if election_config.election_type != "parliamentary":
        return

    raw_file = Path("input/raw/electoral_districts_boundaries_2025.geojson")
    converted_file = Path(
        "input/raw/electoral_districts_boundaries_2025_wgs84.geojson"
    )

    if not raw_file.exists():
        logger.warning(
            "⚠️  Raw 2025 polling station GeoJSON not found. "
            "Download it and rerun to generate WGS84 output."
        )
        return

    needs_convert = not converted_file.exists() or (
        converted_file.stat().st_mtime < raw_file.stat().st_mtime
    )

    try:
        import geopandas as gpd
    except Exception as exc:
        logger.error(
            "❌ geopandas not available; cannot convert 2025 GeoJSON to WGS84."
        )
        logger.error(f"   Import error: {exc}")
        return

    try:
        import json

        if needs_convert:
            logger.info("📐 Converting 2025 polling station GeoJSON to WGS84...")
            gdf = gpd.read_file(raw_file)
            minx, miny, maxx, maxy = gdf.total_bounds
            projected = (
                max(abs(minx), abs(maxx)) > 180 or max(abs(miny), abs(maxy)) > 90
            )

            if projected:
                if gdf.crs is None:
                    gdf = gdf.set_crs(5514)
                gdf = gdf.to_crs(4326)
            elif gdf.crs is None:
                gdf = gdf.set_crs(4326)

            converted_file.parent.mkdir(parents=True, exist_ok=True)
            converted_file.write_text(gdf.to_json(), encoding="utf-8")
            logger.info(f"✅ Saved converted GeoJSON to {converted_file}")
        else:
            logger.info("✅ WGS84 GeoJSON already up to date.")
            gdf = gpd.read_file(converted_file)

        gpkg_file = Path("input/raw/electoral_districts_boundaries_2025_wgs84.gpkg")
        if not gpkg_file.exists() or (
            gpkg_file.exists()
            and gpkg_file.stat().st_mtime < converted_file.stat().st_mtime
        ):
            try:
                gdf.to_file(gpkg_file, layer="okrsky", driver="GPKG")
                logger.info(f"✅ Saved GeoPackage to {gpkg_file}")
            except Exception as exc:
                logger.warning(f"⚠️ Failed to write GeoPackage: {exc}")
        simplified_layer = "okrsky_simplified"
        simplified_needs_update = needs_convert or not gpkg_file.exists()
        if not simplified_needs_update and gpkg_file.exists():
            try:
                gpd.read_file(gpkg_file, layer=simplified_layer, rows=1)
            except Exception:
                simplified_needs_update = True
        if simplified_needs_update:
            try:
                simplified = gdf.copy()
                simplified["geometry"] = simplified.geometry.simplify(
                    0.0002, preserve_topology=True
                )
                simplified.to_file(gpkg_file, layer=simplified_layer, driver="GPKG")
                logger.info(
                    f"✅ Saved simplified GeoPackage layer to {gpkg_file}:{simplified_layer}"
                )
            except Exception as exc:
                logger.warning(f"⚠️ Failed to write simplified GeoPackage: {exc}")
        else:
            simplified = gpd.read_file(gpkg_file, layer=simplified_layer)

        results_file = election_config.results_dir / "parliamentary_election_results.json"
        municipality_code_set = set()
        if results_file.exists():
            try:
                with open(results_file, "r", encoding="utf-8") as f:
                    results_data = json.load(f)
                stations = results_data.get("raw_data", {}).get("polling_stations", [])
                municipality_code_set = {
                    str(station.get("municipality_code"))
                    for station in stations
                    if station.get("municipality_code") is not None
                }
                logger.info(
                    f"✅ Loaded {len(municipality_code_set)} municipality codes from results"
                )
            except Exception as exc:
                logger.warning(f"⚠️ Failed to load municipality codes: {exc}")

        split_dir = Path("input/ps2025/processed/geojson_by_municipality")
        split_index = split_dir / "index.json"
        split_needs_update = needs_convert or not split_index.exists()
        if not split_needs_update:
            split_needs_update = (
                split_index.stat().st_mtime < converted_file.stat().st_mtime
            )
        if not split_needs_update and results_file.exists():
            split_needs_update = split_index.stat().st_mtime < results_file.stat().st_mtime

        if split_needs_update:
            split_dir.mkdir(parents=True, exist_ok=True)
            split = simplified.copy()
            split["municipality_code"] = split["kod_obec"]
            if municipality_code_set:
                split["municipality_code"] = split.apply(
                    lambda row: row["kod_mco"]
                    if str(row.get("kod_mco")) in municipality_code_set
                    else row.get("kod_obec"),
                    axis=1,
                )
            split["municipality_code"] = split["municipality_code"].astype(
                int, errors="ignore"
            ).astype(str, errors="ignore")

            codes = []
            for code, group in split.groupby("municipality_code"):
                if not code or code == "nan":
                    continue
                codes.append(code)
                out_file = split_dir / f"{code}.geojson"
                out_file.write_text(group.to_json(), encoding="utf-8")

            split_index.write_text(
                json.dumps(sorted(set(codes)), ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info(
                f"✅ Saved {len(codes)} per-municipality GeoJSON files to {split_dir}"
            )
        kod_mco = gdf.get("kod_mco")
        if kod_mco is not None:
            kod_mco_values = (
                kod_mco.dropna()
                .astype(int, errors="ignore")
                .astype(str, errors="ignore")
                .unique()
                .tolist()
            )
            kod_mco_file = Path("input/ps2025/processed/geojson_kod_mco_set.json")
            kod_mco_file.parent.mkdir(parents=True, exist_ok=True)
            kod_mco_file.write_text(
                json.dumps(sorted(set(kod_mco_values)), ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info(f"✅ Saved kod_mco index to {kod_mco_file}")
    except Exception as exc:
        logger.error(f"❌ Failed to convert 2025 GeoJSON to WGS84: {exc}")


def main():
    """Main function to run all municipalities analysis"""
    parser = argparse.ArgumentParser(
        description="Collect and analyze electoral data for all Czech municipalities"
    )
    parser.add_argument(
        "--election",
        "-e",
        default="kv2022",
        help="Election ID (e.g., kv2022, kv2018, kv2014). Default: kv2022",
    )
    parser.add_argument(
        "--list-elections",
        action="store_true",
        help="List all available elections and exit",
    )
    parser.add_argument(
        "--data-dir",
        help="(Deprecated) Data directory path. Use --election instead.",
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        default=200,
        help="Maximum number of batch files to download (default: 200)",
    )
    parser.add_argument(
        "--registry-only",
        action="store_true",
        help="Only download and process municipality registry",
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Skip downloading, only process existing data",
    )

    args = parser.parse_args()

    # Handle list elections flag
    if args.list_elections:
        print("\nAvailable elections:")
        print("=" * 60)
        elections_info = get_election_info()
        for election_id, info in elections_info.items():
            print(f"\n{election_id}:")
            print(f"  Name: {info['name']}")
            print(f"  Type: {info['type']}")
            print(f"  Date: {info['date']}")
        print("\n" + "=" * 60)
        return 0

    # Get election configuration
    try:
        election_config = get_election_config(args.election)
    except ValueError as e:
        logger.error(str(e))
        logger.info("Run with --list-elections to see available elections")
        return 1

    if args.data_dir:
        logger.warning(
            "--data-dir parameter is deprecated. Data will be stored in "
            f"output/{args.election}/ instead."
        )

    logger.info("=" * 80)
    logger.info("CZECH ELECTORAL ANALYSIS")
    logger.info("=" * 80)
    logger.info(f"Election: {election_config.election_name}")
    logger.info(f"Election ID: {election_config.election_id}")
    logger.info(f"Election Type: {election_config.election_type}")
    logger.info(f"Election Date: {election_config.election_date}")
    logger.info(f"Input directory: {election_config.input_dir}")
    logger.info(f"Output directory: {election_config.output_dir}")
    logger.info(f"Max batches: {args.max_batches}")
    logger.info(f"Registry only: {args.registry_only}")
    logger.info(f"No download: {args.no_download}")
    logger.info("-" * 80)

    try:
        # Step 1: Initialize registry (skip for parliamentary elections)
        if election_config.election_type == "parliamentary":
            logger.info(
                "🏛️  STEP 1: Skipping registry (handled by ParliamentaryScraper)"
            )

            if args.registry_only:
                logger.warning(
                    "--registry-only not applicable for parliamentary elections"
                )
                logger.info(
                    "Parliamentary data is downloaded as part of complete analysis"
                )
                return 0
        else:
            logger.info("🏛️  STEP 1: Processing Municipality Registry")
            registry = MunicipalityRegistry(election_config=election_config)

            if not args.no_download:
                registry.download_municipality_registry()

            municipalities = registry.parse_municipality_registry()
            if not municipalities:
                logger.error("Failed to load municipality registry")
                return 1

            valid_municipalities = registry.get_municipalities_with_mandates()
            logger.info(f"✅ Found {len(municipalities)} total entries")
            logger.info(
                f"✅ Found {len(valid_municipalities)} municipalities with valid elections"
            )

            # Save registry to JSON
            registry_file = registry.save_registry_to_json()
            logger.info(f"✅ Saved registry to {registry_file}")

            # Show some examples
            logger.info("\n📊 Sample municipalities:")
            for i, municipality in enumerate(valid_municipalities[:10]):
                logger.info(
                    f"  {i + 1:2d}. {municipality.municipality_name} "
                    f"({municipality.municipality_code}) - {municipality.mandates} seats"
                )

            if args.registry_only:
                logger.info("✅ Registry processing complete!")
                return 0

        # Step 2: Collect electoral data - choose appropriate scraper
        logger.info("\n🗳️  STEP 2: Collecting Electoral Data")

        # Select scraper based on election type
        if election_config.election_type == "parliamentary":
            logger.info("📊 Using ParliamentaryScraper for parliamentary elections")
            scraper = ParliamentaryScraper(election_config=election_config)
        else:
            logger.info("🏛️  Using AllMunicipalitiesScraper for municipal elections")
            scraper = AllMunicipalitiesScraper(election_config=election_config)

        if args.no_download:
            logger.info("⏭️  Skipping download, processing existing files...")

        result_file = scraper.run_complete_analysis()

        if result_file:
            logger.info(f"✅ Complete analysis saved to: {result_file}")

            summary_step_label = "STEP 3"
            if election_config.election_type == "parliamentary":
                logger.info("\n🗺️  STEP 3: Preparing GeoJSON for maps")
                ensure_parliamentary_geojson_wgs84(election_config)
                summary_step_label = "STEP 4"
            elif election_config.boundaries_file:
                logger.info("\n🗺️  STEP 3: Preparing precinct boundaries for maps")
                ensure_municipal_boundaries(election_config)
                summary_step_label = "STEP 4"

            # Generate summary report
            logger.info(f"\n📋 {summary_step_label}: Generating Summary Report")
            generate_summary_report(result_file, election_config)

            logger.info("\n🎉 ELECTORAL ANALYSIS COMPLETE!")
            logger.info("=" * 80)
            logger.info("📁 Output files:")
            if election_config.election_type != "parliamentary":
                logger.info(f"   • Municipality registry: {registry_file}")
                logger.info(
                    f"   • Municipality index: {election_config.results_dir / 'municipality_index.json'}"
                )
            else:
                logger.info(
                    f"   • District index: {election_config.results_dir / 'district_index.json'}"
                )
            logger.info(f"   • Complete analysis: {result_file}")
            logger.info(
                f"   • Summary report: {election_config.reports_dir / 'analysis_summary.md'}"
            )
            logger.info("=" * 80)
            logger.info("\n🚀 Ready to use in the app:")
            logger.info("   uv run uvicorn --app-dir src web_api:app --host 0.0.0.0 --port 8600")

            return 0
        else:
            logger.error("❌ Analysis failed")
            return 1

    except KeyboardInterrupt:
        logger.warning("\n⚠️  Analysis interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"❌ Analysis failed with error: {e}")
        logger.exception("Full error details:")
        return 1


def generate_summary_report(result_file: str, election_config):
    """Generate a summary report of the analysis"""
    import json
    from pathlib import Path

    try:
        # Load the results
        with open(result_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Handle parliamentary elections differently
        if election_config.election_type == "parliamentary":
            logger.info(
                "⏭️  Skipping detailed summary report for parliamentary elections"
            )
            logger.info("   (Parliamentary reports are in the results JSON)")
            return

        municipalities = data.get("municipalities", {})
        metadata = data.get("metadata", {})

        # Create reports directory
        reports_dir = election_config.reports_dir
        reports_dir.mkdir(exist_ok=True)

        # Generate markdown summary
        summary_file = reports_dir / "analysis_summary.md"

        with open(summary_file, "w", encoding="utf-8") as f:
            f.write("# Czech Municipalities Electoral Analysis Summary\n\n")
            f.write(
                f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            )
            f.write(f"**Election:** {metadata.get('election_name', 'Unknown')}\n")
            f.write(
                f"**Election Date:** {metadata.get('election_date', 'Unknown')}\n\n"
            )

            # Overall statistics
            f.write("## 📊 Overall Statistics\n\n")
            f.write(f"- **Total Municipalities:** {len(municipalities)}\n")
            f.write(
                f"- **Collection Date:** {metadata.get('collection_date', 'Unknown')}\n"
            )
            f.write(f"- **Data Source:** {metadata.get('source', 'Unknown')}\n\n")

            # Top municipalities by size
            municipality_list = []
            for code, muni_data in municipalities.items():
                metadata_muni = muni_data.get("metadata", {})
                stats = muni_data.get("summary_statistics", {})
                municipality_list.append(
                    {
                        "code": code,
                        "name": metadata_muni.get("municipality_name", "Unknown"),
                        "mandates": metadata_muni.get("mandates", 0),
                        "turnout": stats.get("turnout_percentage", 0),
                        "voters": stats.get("registered_voters", 0),
                        "parties": stats.get("parties_participating", 0),
                    }
                )

            # Sort by mandates (council size)
            municipality_list.sort(key=lambda x: x["mandates"], reverse=True)

            f.write("## 🏆 Largest Municipalities (by council seats)\n\n")
            f.write(
                "| Rank | Municipality | Council Seats | Turnout % | Registered Voters | Parties |\n"
            )
            f.write(
                "|------|--------------|---------------|-----------|-------------------|----------|\n"
            )

            for i, muni in enumerate(municipality_list[:20]):
                f.write(
                    f"| {i + 1:2d} | {muni['name']} | {muni['mandates']} | "
                    f"{muni['turnout']:.1f}% | {muni['voters']:,} | {muni['parties']} |\n"
                )

            # Sort by turnout
            municipality_list.sort(key=lambda x: x["turnout"], reverse=True)

            f.write("\n## 📈 Highest Turnout Municipalities\n\n")
            f.write(
                "| Rank | Municipality | Turnout % | Council Seats | Registered Voters |\n"
            )
            f.write(
                "|------|--------------|-----------|---------------|-----------------|\n"
            )

            for i, muni in enumerate(municipality_list[:15]):
                f.write(
                    f"| {i + 1:2d} | {muni['name']} | {muni['turnout']:.1f}% | "
                    f"{muni['mandates']} | {muni['voters']:,} |\n"
                )

            # Data quality report
            f.write("\n## 🔍 Data Quality\n\n")

            municipalities_with_data = sum(
                1 for m in municipality_list if m["voters"] > 0
            )
            avg_turnout = sum(m["turnout"] for m in municipality_list) / len(
                municipality_list
            )
            total_voters = sum(m["voters"] for m in municipality_list)
            total_seats = sum(m["mandates"] for m in municipality_list)

            f.write(
                f"- **Municipalities with voter data:** {municipalities_with_data}/{len(municipality_list)}\n"
            )
            f.write(f"- **Average turnout:** {avg_turnout:.1f}%\n")
            f.write(f"- **Total registered voters:** {total_voters:,}\n")
            f.write(f"- **Total council seats:** {total_seats:,}\n")

            f.write("\n## 🚀 Next Steps\n\n")
            f.write(
                "1. **Explore data:** Use the web app to explore individual municipalities\n"
            )
            f.write(
                "2. **Compare municipalities:** Use comparison features to analyze differences\n"
            )
            f.write(
                "3. **Geographic analysis:** Add geographic coordinates for mapping\n"
            )
            f.write(
                "4. **Historical analysis:** Compare with previous election cycles\n"
            )

            f.write(f"\n---\n*Report generated by Czech Electoral Analysis Tool*\n")

        logger.info(f"✅ Summary report saved to {summary_file}")

        # Also save as JSON for programmatic access
        json_summary = {
            "metadata": {
                "generation_date": datetime.now().isoformat(),
                "total_municipalities": len(municipalities),
                "municipalities_with_data": municipalities_with_data,
                "average_turnout": avg_turnout,
                "total_voters": total_voters,
                "total_seats": total_seats,
            },
            "top_by_seats": municipality_list[:20],
            "top_by_turnout": sorted(
                municipality_list, key=lambda x: x["turnout"], reverse=True
            )[:15],
        }

        json_summary_file = reports_dir / "analysis_summary.json"
        with open(json_summary_file, "w", encoding="utf-8") as f:
            json.dump(json_summary, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ JSON summary saved to {json_summary_file}")

    except Exception as e:
        logger.error(f"Error generating summary report: {e}")


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

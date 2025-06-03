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


def main():
    """Main function to run all municipalities analysis"""
    parser = argparse.ArgumentParser(
        description="Collect and analyze electoral data for all Czech municipalities"
    )
    parser.add_argument(
        "--data-dir", default="output", help="Data directory path (default: output)"
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

    logger.info("=" * 80)
    logger.info("CZECH MUNICIPALITIES ELECTORAL ANALYSIS")
    logger.info("=" * 80)
    logger.info(f"Data directory: {args.data_dir}")
    logger.info(f"Max batches: {args.max_batches}")
    logger.info(f"Registry only: {args.registry_only}")
    logger.info(f"No download: {args.no_download}")
    logger.info("-" * 80)

    try:
        # Step 1: Initialize municipality registry
        logger.info("🏛️  STEP 1: Processing Municipality Registry")
        registry = MunicipalityRegistry(args.data_dir)

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

        # Step 2: Collect electoral data for all municipalities
        logger.info("\n🗳️  STEP 2: Collecting Electoral Data")
        scraper = AllMunicipalitiesScraper(args.data_dir)

        if args.no_download:
            logger.info("⏭️  Skipping download, processing existing files...")

        result_file = scraper.run_complete_analysis()

        if result_file:
            logger.info(f"✅ Complete analysis saved to: {result_file}")

            # Step 3: Generate summary report
            logger.info("\n📋 STEP 3: Generating Summary Report")
            generate_summary_report(result_file, args.data_dir)

            logger.info("\n🎉 ALL MUNICIPALITIES ANALYSIS COMPLETE!")
            logger.info("=" * 80)
            logger.info("📁 Output files:")
            logger.info(f"   • Municipality registry: {registry_file}")
            logger.info(f"   • Complete analysis: {result_file}")
            logger.info(
                f"   • Municipality index: {Path(args.data_dir) / 'results' / 'municipality_index.json'}"
            )
            logger.info(
                f"   • Summary report: {Path(args.data_dir) / 'reports' / 'analysis_summary.md'}"
            )
            logger.info("=" * 80)
            logger.info("\n🚀 Ready to use with Streamlit:")
            logger.info("   streamlit run streamlit_municipality_selector.py")

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


def generate_summary_report(result_file: str, data_dir: str):
    """Generate a summary report of the analysis"""
    import json
    from pathlib import Path

    try:
        # Load the results
        with open(result_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        municipalities = data.get("municipalities", {})
        metadata = data.get("metadata", {})

        # Create reports directory
        reports_dir = Path(data_dir) / "reports"
        reports_dir.mkdir(exist_ok=True)

        # Generate markdown summary
        summary_file = reports_dir / "analysis_summary.md"

        with open(summary_file, "w", encoding="utf-8") as f:
            f.write("# Czech Municipalities Electoral Analysis Summary\n\n")
            f.write(
                f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
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
                "1. **Explore data:** Use the Streamlit app to explore individual municipalities\n"
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

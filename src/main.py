#!/usr/bin/env python3
"""
Main execution script for Prague 5 Election Analysis
"""

import logging
import os
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent))

from xml_scraper import ElectoralDistrictXMLScraper
from data_processor import Prague5DataProcessor

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Main execution function"""
    logger.info("Starting Prague 5 Election Analysis Pipeline")

    # Get project root directory
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "data"

    # Initialize components
    scraper = ElectoralDistrictXMLScraper(str(data_dir))
    processor = Prague5DataProcessor(str(data_dir))

    try:
        # Phase 1: Enhanced Data Collection
        logger.info("=== PHASE 1: ENHANCED DATA COLLECTION ===")

        # Run comprehensive scraping with our enhanced scraper
        logger.info("Running comprehensive election data scraping...")
        results = scraper.run_complete_scraping()

        if results:
            logger.info("Successfully completed enhanced data collection:")
            logger.info(f"  - Municipality: {results['metadata']['municipality']}")
            logger.info(f"  - Election Year: {results['metadata']['election_year']}")
            logger.info(f"  - Source URL: {results['metadata']['source_url']}")

            # Summary statistics
            if results.get("summary_statistics"):
                stats = results["summary_statistics"]
                logger.info("  - Summary Statistics:")
                logger.info(f"    * Elected Members: {stats.get('elected_members')}")
                logger.info(
                    f"    * Registered Voters: {stats.get('registered_voters'):,}"
                )
                logger.info(f"    * Turnout: {stats.get('turnout_percentage')}%")
                logger.info(f"    * Valid Votes: {stats.get('valid_votes'):,}")

            # Party results
            if results.get("party_results"):
                party_count = len(results["party_results"])
                logger.info(f"  - Party Results: {party_count} parties")

                # Show top 3 parties
                top_parties = sorted(
                    results["party_results"],
                    key=lambda x: x.get("votes_absolute", 0),
                    reverse=True,
                )[:3]

                logger.info("  - Top 3 parties by votes:")
                for party in top_parties:
                    name = party.get("party_name", "Unknown")
                    votes = party.get("votes_absolute", 0)
                    percentage = party.get("votes_percentage", 0)
                    mandates = party.get("mandates_won", 0)
                    logger.info(
                        f"    * {name}: {votes:,} votes ({percentage}%) - {mandates} mandates"
                    )

            # Detailed party results
            if results.get("party_results_detailed"):
                detailed_count = len(results["party_results_detailed"])
                logger.info(
                    f"  - Detailed Party Data: {detailed_count} parties with candidate information"
                )

                # Count total candidates
                total_candidates = sum(
                    len(party.get("candidates", []))
                    for party in results["party_results_detailed"]
                )
                logger.info(f"  - Total Candidates: {total_candidates}")

        else:
            logger.error("Enhanced data collection failed")
            return False

        # Phase 2: Data Processing (Optional - using existing processor if needed)
        logger.info("=== PHASE 2: DATA PROCESSING ===")
        logger.info("Enhanced scraper provides already structured data.")
        logger.info("Traditional CSV processing can be run separately if needed.")

        # Save a summary report
        logger.info("Generating summary report...")
        summary_file = data_dir / "results" / "analysis_summary.json"

        summary_report = {
            "pipeline_status": "completed",
            "data_collection": {
                "method": "enhanced_web_scraping",
                "source": results.get("metadata", {}).get("source_url"),
                "scrape_date": results.get("metadata", {}).get("scrape_date"),
            },
            "statistics": results.get("summary_statistics", {}),
            "parties_analyzed": len(results.get("party_results", [])),
            "candidates_analyzed": total_candidates
            if results.get("party_results_detailed")
            else 0,
            "files_generated": [
                "prague5_complete_results.json",
                "prague5_comprehensive_results.json",
            ],
        }

        import json

        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary_report, f, ensure_ascii=False, indent=2)

        logger.info(f"Summary report saved to: {summary_file}")

        logger.info("=== PIPELINE COMPLETED SUCCESSFULLY ===")
        logger.info("Generated files:")
        logger.info(f"  - {data_dir}/results/prague5_complete_results.json")
        logger.info(f"  - {data_dir}/results/prague5_comprehensive_results.json")
        logger.info(f"  - {summary_file}")
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Review comprehensive election data")
        logger.info("2. Run analysis components: python src/analyzer.py")
        logger.info("3. Generate visualizations: python src/visualizer.py")

        return True

    except Exception as e:
        logger.error(f"Pipeline failed with error: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

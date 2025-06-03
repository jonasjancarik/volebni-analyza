#!/usr/bin/env python3
"""
Prague 5 Election Analysis - Complete Pipeline Runner
"""

import logging
import sys
import os
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from data_collector import Prague5DataCollector
from data_processor import Prague5DataProcessor
from improved_collector import ImprovedPrague5Collector
from visualizer import Prague5Visualizer
from analyzer import Prague5ElectionAnalyzer

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def print_banner():
    """Print a nice banner for the analysis"""
    banner = """
╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                           ║
║                🗳️  PRAGUE 5 ELECTION ANALYSIS PIPELINE                   ║
║                                                                           ║
║                    Municipal Elections 2022 Analysis                     ║
║                          Data • Insights • Action                        ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_section(title):
    """Print a section header"""
    print(f"\n{'=' * 20} {title} {'=' * 20}")


def print_results_summary():
    """Print a summary of all generated outputs"""
    print_section("ANALYSIS COMPLETE")

    project_root = Path(__file__).parent
    output_dir = project_root / "output"

    # Check what was generated
    outputs = {
        "📊 Interactive Visualizations": output_dir / "visualizations" / "index.html",
        "📈 Turnout Analysis Chart": output_dir
        / "visualizations"
        / "turnout_analysis.html",
        "🗺️ Electoral Districts Map": output_dir
        / "visualizations"
        / "districts_map.html",
        "📋 Summary Dashboard": output_dir
        / "visualizations"
        / "summary_dashboard.html",
        "📑 Analysis Report (JSON)": output_dir
        / "reports"
        / "comprehensive_analysis_report.json",
        "📝 Analysis Summary (Markdown)": output_dir
        / "reports"
        / "analysis_summary.md",
        "📦 Raw District Data": output_dir / "processed" / "prague5_districts.json",
        "🔍 Detailed Results Data": output_dir
        / "detailed"
        / "prague5_detailed_results.json",
    }

    print("\n🎯 Generated Outputs:")
    for description, filepath in outputs.items():
        if filepath.exists():
            print(f"   ✅ {description}")
            print(f"      📁 {filepath}")
        else:
            print(f"   ❌ {description} (not found)")

    # Show key findings
    try:
        import json

        report_file = output_dir / "reports" / "comprehensive_analysis_report.json"
        if report_file.exists():
            with open(report_file, "r", encoding="utf-8") as f:
                report = json.load(f)

            print("\n🔑 Key Findings:")
            for finding in report["executive_summary"]["key_findings"]:
                print(f"   • {finding}")

            if report["executive_summary"]["main_concerns"]:
                print("\n⚠️  Areas of Concern:")
                for concern in report["executive_summary"]["main_concerns"]:
                    print(f"   • {concern}")

            if report["executive_summary"]["positive_findings"]:
                print("\n✨ Positive Findings:")
                for finding in report["executive_summary"]["positive_findings"]:
                    print(f"   • {finding}")

    except Exception as e:
        logger.warning(f"Could not load report summary: {e}")

    print("\n🚀 Next Steps:")
    print("   1. Open output/visualizations/index.html in your browser")
    print("   2. Review output/reports/analysis_summary.md for detailed insights")
    print("   3. Share findings with stakeholders")
    print("   4. Implement recommended actions")


def main():
    """Run the complete Prague 5 election analysis pipeline"""
    print_banner()

    project_root = Path(__file__).parent
    output_dir = project_root / "output"
    input_dir = project_root / "input"

    try:
        # Phase 1: Data Collection
        print_section("DATA COLLECTION")

        print("🔄 Initializing collectors...")
        collector = Prague5DataCollector(str(output_dir))
        improved_collector = ImprovedPrague5Collector(str(output_dir))

        print("📡 Collecting Prague 5 district information...")
        web_data = collector.scrape_prague5_results_web()
        if web_data:
            print(f"   ✅ Found {len(web_data)} electoral districts")

        print("🕷️ Scraping detailed election results...")
        alternative_data = improved_collector.collect_all_alternative_data()
        if alternative_data:
            print("   ✅ Alternative data collection completed")

        # Phase 2: Data Processing
        print_section("DATA PROCESSING")

        print("⚙️ Processing election data...")
        processor = Prague5DataProcessor(
            output_dir=str(output_dir), input_dir=str(input_dir)
        )
        processed_data = processor.process_all_data()
        print("   ✅ Data processing completed")

        # Phase 3: Visualization
        print_section("VISUALIZATION GENERATION")

        print("📊 Creating interactive visualizations...")
        visualizer = Prague5Visualizer(str(output_dir))
        viz_results = visualizer.generate_all_visualizations()
        print(f"   ✅ Generated {len(viz_results)} visualization components")

        # Phase 4: Analysis & Insights
        print_section("STATISTICAL ANALYSIS")

        print("🔍 Performing comprehensive analysis...")
        analyzer = Prague5ElectionAnalyzer(str(output_dir))
        analysis_report = analyzer.generate_comprehensive_report()

        if analysis_report:
            avg_turnout = analysis_report["detailed_statistics"]["average_turnout"]
            districts_analyzed = analysis_report["detailed_statistics"][
                "total_districts_analyzed"
            ]
            print(
                f"   ✅ Analysis complete: {avg_turnout:.1f}% avg turnout across {districts_analyzed} districts"
            )

        # Phase 5: Results Summary
        print_results_summary()

        return True

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    success = main()
    if success:
        print("\n🎉 Prague 5 Election Analysis completed successfully!")
        print("📱 Check output/visualizations/index.html to explore your results")
    else:
        print("\n❌ Analysis pipeline encountered errors")
        print("📋 Check the logs above for troubleshooting information")

    sys.exit(0 if success else 1)

#!/usr/bin/env python3
"""
Prague 5 Electoral Analysis - Quick Start Guide
This script helps you get started with the complete analysis pipeline
"""

import subprocess
import sys
from pathlib import Path
import time


def print_banner():
    """Print a welcome banner"""
    banner = """
╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                           ║
║                🗳️  PRAGUE 5 ELECTORAL ANALYSIS                           ║
║                          Quick Start Guide                               ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_step(step, description):
    """Print a step with formatting"""
    print(f"\n📋 Step {step}: {description}")
    print("=" * 60)


def run_command(cmd, description):
    """Run a command with nice output"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(
            cmd, shell=True, check=True, capture_output=True, text=True
        )
        print(f"✅ {description} completed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        if e.stdout:
            print(f"Output: {e.stdout}")
        if e.stderr:
            print(f"Error: {e.stderr}")
        return False


def check_data_exists():
    """Check if analysis data already exists"""
    data_dir = Path(__file__).parent / "data"

    key_files = [
        data_dir / "results" / "prague5_comprehensive_results.json",
        data_dir / "detailed" / "prague5_detailed_results.json",
        data_dir / "reports" / "comprehensive_analysis_report.json",
    ]

    existing_files = [f for f in key_files if f.exists()]

    return len(existing_files) > 0, existing_files


def main():
    """Main quick start flow"""
    print_banner()

    print("Welcome to the Prague 5 Electoral Analysis toolkit!")
    print("This script will guide you through the complete analysis process.")

    # Check if data already exists
    data_exists, existing_files = check_data_exists()

    if data_exists:
        print(f"\n🎯 Found existing analysis data ({len(existing_files)} files)")
        print("You can either:")
        print("  1. Skip to the Streamlit dashboard")
        print("  2. Re-run the analysis pipeline (will overwrite existing data)")

        choice = input("\nChoose (1/2) or press Enter for dashboard: ").strip()

        if choice != "2":
            print("\n🚀 Launching Streamlit dashboard...")
            subprocess.run([sys.executable, "run_streamlit.py"])
            return

    # Step 1: Data Collection & Analysis
    print_step(1, "Data Collection & Analysis")
    print("This will collect electoral data and perform comprehensive analysis.")
    print("Expected time: 2-5 minutes")

    if not run_command(f"{sys.executable} run_analysis.py", "Electoral data analysis"):
        print("\n❌ Analysis failed. Please check the error messages above.")
        return False

    # Step 2: Verify Output
    print_step(2, "Verify Generated Data")
    data_exists, existing_files = check_data_exists()

    if data_exists:
        print(f"✅ Generated {len(existing_files)} analysis files:")
        for file in existing_files:
            print(f"   📄 {file}")
    else:
        print("⚠️  No analysis files found. The analysis may have failed.")

    # Step 3: Launch Dashboard
    print_step(3, "Launch Interactive Dashboard")
    print("Starting the Streamlit dashboard for data visualization...")
    print("🌐 The dashboard will open in your browser at http://localhost:8501")
    print("🔄 Press Ctrl+C in the terminal to stop the dashboard")

    input("\nPress Enter to launch the dashboard...")

    print("\n🚀 Launching dashboard...")
    time.sleep(1)

    try:
        subprocess.run([sys.executable, "run_streamlit.py"])
    except KeyboardInterrupt:
        print("\n👋 Dashboard stopped")

    print("\n🎉 Quick start completed!")
    print("\nNext steps:")
    print("  • Explore the dashboard at http://localhost:8501")
    print("  • Check data/ directory for generated files")
    print("  • Review README.md for detailed usage instructions")


if __name__ == "__main__":
    main()

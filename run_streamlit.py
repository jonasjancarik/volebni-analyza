#!/usr/bin/env python3
"""
Streamlit App Launcher - Launch Czech Municipal Electoral Analysis Dashboard
"""

import argparse
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Launch Czech Municipal Electoral Analysis Dashboard"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8501,
        help="Port number for Streamlit (default: 8501)",
    )
    parser.add_argument(
        "--dev", action="store_true", help="Run in development mode with auto-reload"
    )

    args = parser.parse_args()

    print("🏛️ Czech Municipal Electoral Analysis Dashboard")
    print("=" * 50)
    print("🚀 Launching Comprehensive Analysis Dashboard")
    print(f"   → http://localhost:{args.port}")
    print("   → All 6,377+ Czech municipalities")
    print("   → Full electoral analysis with maps and visualizations")
    print("   → Auto-setup: Will automatically download data if missing")

    cmd = ["uv", "run", "streamlit", "run", "streamlit_app.py"]
    if args.port != 8501:
        cmd.extend(["--server.port", str(args.port)])
    if args.dev:
        cmd.extend(["--server.fileWatcherType", "auto"])

    print("\n" + "=" * 50)
    print("📊 Features Available:")
    print("   • 6,377+ Czech municipalities")
    print("   • 2022 municipal election data")
    print("   • Party results and mandate distribution")
    print("   • Turnout and voter statistics")
    print("   • District-level analysis")
    print("   • Interactive geographic maps")
    print("   • Advanced visualizations")
    print("   • Auto-setup for missing data")
    print("=" * 50)

    # Run the app
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n🛑 App stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running app: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Streamlit App Launcher - Choose between different analysis interfaces
"""

import argparse
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Launch Czech Municipal Electoral Analysis Apps"
    )
    parser.add_argument(
        "--app",
        choices=["selector", "dashboard", "both"],
        default="selector",
        help="Choose which app to run: selector (simple), dashboard (comprehensive), or both",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8502,
        help="Port number for Streamlit (default: 8502)",
    )
    parser.add_argument(
        "--dev", action="store_true", help="Run in development mode with auto-reload"
    )

    args = parser.parse_args()

    print("🏛️ Czech Municipal Electoral Analysis Apps")
    print("=" * 50)

    if args.app == "selector":
        print("🚀 Launching Municipal Selector (Simple Interface)")
        print(f"   → http://localhost:{args.port}")
        print("   → Choose from 6,377+ Czech municipalities")
        print("   → Quick overview and party results")

        cmd = ["uv", "run", "streamlit", "run", "streamlit_municipality_selector.py"]
        if args.port != 8501:
            cmd.extend(["--server.port", str(args.port)])
        if args.dev:
            cmd.extend(["--server.fileWatcherType", "auto"])

    elif args.app == "dashboard":
        print("🚀 Launching Comprehensive Analysis Dashboard")
        print(f"   → http://localhost:{args.port}")
        print("   → Full electoral analysis with maps")
        print("   → Geographic visualizations and detailed stats")

        cmd = ["uv", "run", "streamlit", "run", "streamlit_app.py"]
        if args.port != 8501:
            cmd.extend(["--server.port", str(args.port)])
        if args.dev:
            cmd.extend(["--server.fileWatcherType", "auto"])

    elif args.app == "both":
        print("🚀 Launching Both Apps")
        print(f"   → Municipal Selector: http://localhost:{args.port}")
        print(f"   → Analysis Dashboard: http://localhost:{args.port + 1}")

        import subprocess
        import time

        # Launch selector
        print("\n   Starting Municipal Selector...")
        selector_cmd = [
            "uv",
            "run",
            "streamlit",
            "run",
            "streamlit_municipality_selector.py",
            "--server.port",
            str(args.port),
        ]
        selector_process = subprocess.Popen(selector_cmd)
        time.sleep(3)

        # Launch dashboard
        print("   Starting Analysis Dashboard...")
        dashboard_cmd = [
            "uv",
            "run",
            "streamlit",
            "run",
            "streamlit_app.py",
            "--server.port",
            str(args.port + 1),
        ]
        dashboard_process = subprocess.Popen(dashboard_cmd)

        print(f"\n✅ Both apps are running!")
        print(f"   • Simple Interface: http://localhost:{args.port}")
        print(f"   • Full Dashboard: http://localhost:{args.port + 1}")
        print("\n   Press Ctrl+C to stop both apps")

        try:
            # Wait for both processes
            selector_process.wait()
            dashboard_process.wait()
        except KeyboardInterrupt:
            print("\n🛑 Stopping both apps...")
            selector_process.terminate()
            dashboard_process.terminate()
            return

    print("\n" + "=" * 50)
    print("📊 Features Available:")
    print("   • 6,377+ Czech municipalities")
    print("   • 2022 municipal election data")
    print("   • Party results and mandate distribution")
    print("   • Turnout and voter statistics")
    print("   • District-level analysis")
    if args.app in ["dashboard", "both"]:
        print("   • Interactive geographic maps")
        print("   • Advanced visualizations")
    print("=" * 50)

    # Run the selected app
    if args.app != "both":
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

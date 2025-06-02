#!/usr/bin/env python3
"""
Simple script to run the Prague 5 Electoral Analysis Streamlit Dashboard
"""

import subprocess
import sys
from pathlib import Path


def main():
    """Run the Streamlit dashboard"""

    # Ensure we're in the correct directory
    project_root = Path(__file__).parent
    app_file = project_root / "streamlit_app.py"

    if not app_file.exists():
        print("❌ streamlit_app.py not found!")
        return False

    print("🚀 Starting Prague 5 Electoral Analysis Dashboard...")
    print("📱 The dashboard will open in your default browser")
    print("🔄 Press Ctrl+C to stop the server")
    print("-" * 50)

    try:
        # Run streamlit with the app file
        cmd = [sys.executable, "-m", "streamlit", "run", str(app_file)]
        subprocess.run(cmd, cwd=str(project_root))
        return True
    except KeyboardInterrupt:
        print("\n👋 Dashboard stopped by user")
        return True
    except Exception as e:
        print(f"❌ Error running dashboard: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

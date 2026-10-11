#!/usr/bin/env python3
"""Show how far the running Bayesian cross-checks are, with council names.

    python3 research/bayesian_progress.py
"""

import json
import time
from pathlib import Path

ELECTION = "kv2026"
reports = Path(f"output/{ELECTION}/reports")
names = {
    code: info["name"]
    for code, info in json.loads(
        Path(f"output/{ELECTION}/results/municipality_index.json").read_text(encoding="utf-8")
    ).items()
}

files = sorted(reports.glob("bayesian_flows_*_progress.txt"), key=lambda f: f.stat().st_mtime)
if not files:
    print("No Bayesian run has reported progress yet.")
for file in files:
    code = file.name.split("_")[2]
    line = file.read_text(encoding="utf-8").strip()
    # A run that stopped reporting without finishing was most likely interrupted
    stale = "finished" not in line and time.time() - file.stat().st_mtime > 300
    print(f"{names.get(code, code):<14} {line}{'   (no update for 5+ min)' if stale else ''}")

# Czech Municipalities Electoral Analysis

> **Comprehensive analysis tool for Czech municipal elections** covering **6,377+ municipalities** across **multiple election years**

[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/streamlit-1.45+-red.svg)](https://streamlit.io/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## 🏛️ What This Tool Does

This tool provides **comprehensive electoral analysis** for any Czech municipality across multiple municipal elections (2026, 2022, and earlier). Originally developed for Prague 5, it now supports **all 6,377+ Czech municipalities** with detailed party results, turnout analysis, interactive visualizations, and **multi-election comparison capabilities**.

### ✨ Key Features

- **📊 All Municipalities**: Support for 6,377+ Czech municipalities
- **🗳️ Multiple Elections**: 2026 and 2022 municipal elections, 2025 parliamentary elections
- **↔️ Comparison with the previous election**: turnout and party results of 2026 next to 2022 for the same council
- **🔄 Easy Election Switching**: Select different elections with a simple dropdown
- **📈 Complete Election Data**: Party results, mandates, turnout statistics  
- **📍 Geographic Analysis**: Interactive maps and district-level breakdowns
- **🔍 Advanced Filtering**: Search by name, size, turnout, and more
- **📊 Data Visualization**: Charts, maps, and comprehensive dashboards
- **💾 Multiple Formats**: JSON, CSV, and interactive displays
- **🚀 Auto-Setup**: Streamlit app automatically runs data collection when needed
- **🔧 Migration Tool**: Easy migration from old single-election structure

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <repository-url>
cd volebni-analyza

# Install dependencies (using uv - recommended)
uv sync

# Alternative: using pip
pip install -r requirements.txt
```

### 2. Launch Analysis Dashboard (Auto-Setup)

The Streamlit app will automatically detect if data is missing and offer to run the data collection for you!

```bash
# Launch the comprehensive analysis dashboard
uv run python run_streamlit.py

# Or run directly
streamlit run streamlit_app.py
```

### 3. Manual Data Collection (Optional)

If you prefer to collect data manually first:

```bash
# List available elections
uv run python run_all_municipalities.py --list-elections

# Collect data for the 2026 municipal elections
uv run python run_all_municipalities.py --election kv2026

# Collect data for 2022 (needed for the 2026 vs 2022 comparison)
uv run python run_all_municipalities.py --election kv2022

# Collect data for 2018 elections
uv run python run_all_municipalities.py --election kv2018

# Short form
uv run python run_all_municipalities.py -e kv2014

# This will:
# - Download municipality registry (6,377+ municipalities)
# - Download electoral district data (200+ batch files)
# - Download party registry (party names, mandates, votes)
# - Generate comprehensive analysis for all municipalities
```

## 📊 Analysis Dashboard

**Comprehensive analysis with interactive visualizations**

- 🎯 **Purpose**: Complete electoral analysis for any Czech municipality
- 🏛️ **Coverage**: All 6,377+ Czech municipalities  
- 🗺️ **Features**:
  - Municipality selection with advanced filtering
  - Interactive geographic maps
  - District-level breakdowns
  - Advanced turnout analysis
  - Data exploration tools
  - Cartographic visualizations
  - **Auto-setup**: Runs data collection if missing

```bash
# Launch the dashboard
streamlit run streamlit_app.py
```

## 🗂️ Project Structure

```
volebni-analyza/
├── 📥 input/                   # All input data organized by election
│   ├── kv2022/                 # 2022 Municipal Elections
│   │   └── raw/                # Source data from ČSÚ
│   ├── kv2018/                 # 2018 Municipal Elections
│   │   └── raw/
│   └── kv2014/                 # 2014 Municipal Elections
│       └── raw/
├── 📤 output/                  # All output data organized by election
│   ├── kv2022/                 # 2022 Election Results
│   │   ├── results/            # Analysis results
│   │   │   ├── all_municipalities_comprehensive.json
│   │   │   └── municipality_index.json
│   │   ├── processed/          # Intermediate data
│   │   ├── csv/                # CSV exports
│   │   └── reports/            # Generated reports
│   ├── kv2018/                 # 2018 Election Results
│   │   └── ...
│   └── kv2014/                 # 2014 Election Results
│       └── ...
├── 🔧 src/                     # Source code modules
│   ├── election_config.py      # Election configuration (NEW)
│   ├── all_municipalities_scraper.py
│   ├── municipality_registry.py
│   ├── data_processor.py
│   ├── analyzer.py
│   ├── visualizer.py
│   └── data_exporters.py
├── 📊 streamlit_app.py                    # Main analysis dashboard
├── 🎛️ run_streamlit.py                   # App launcher
├── 📋 run_all_municipalities.py           # Data collection script
└── 🔄 migrate_to_multi_election.py        # Migration tool (NEW)
```

## 🛠️ Command Line Tools

### 📊 Data Collection
```bash
# List available elections
uv run python run_all_municipalities.py --list-elections

# Full analysis pipeline for specific election
uv run python run_all_municipalities.py --election kv2022

# Collect multiple elections
uv run python run_all_municipalities.py -e kv2022
uv run python run_all_municipalities.py -e kv2018
uv run python run_all_municipalities.py -e kv2014

# Registry only (faster for testing)
uv run python run_all_municipalities.py --election kv2022 --registry-only

# Use existing data (no downloads)
uv run python run_all_municipalities.py --election kv2022 --no-download
```

### 🔄 Migration Tool
```bash
# Migrate existing data from old structure to new multi-election structure
python migrate_to_multi_election.py --dry-run          # Preview changes
python migrate_to_multi_election.py --election-id kv2022  # Perform migration
```

### 🚀 App Launcher
```bash
# Launch the dashboard
uv run python run_streamlit.py

# Custom port
uv run python run_streamlit.py --port 8080

# Development mode with auto-reload
uv run python run_streamlit.py --dev
```

## 📈 Data Sources

### 🏛️ Czech Statistical Office (ČSÚ)
- **Municipality Registry**: `kvcoco.xml` - Official municipality codes, names, mandates
- **Party Registry**: `kvros.xml` - Party names, vote counts, mandates won  
- **Electoral Districts**: `vysledky_okrsky` API - District-level vote data (200+ batches)
- **Geographic Data**: GeoJSON boundaries for mapping

### 📊 Data Coverage (per election)
- **6,377+ municipalities** (complete coverage)
- **16,901 electoral districts** 
- **23,361 party entries** (across all municipalities)
- **10M+ registered voters** total

### 🗳️ Supported Elections

**Municipal Elections** (Komunální volby):
- **2026** - October 9-10, 2026 ✅ Full data available
  - Precinct batches are static files under `volby.cz/appdata/kv2026/20261009/odata/okrsky/`
    (the older `vysledky_okrsky` endpoint is gone); see `districts_batch_url_template` in `src/election_config.py`
  - Maps use the 2025 precinct boundaries. ČSÚ lists the 2026 boundaries in its
    [GIS catalogue](https://geodata.csu.gov.cz/as/dp-gis/), but the download links did not work on 11 October 2026.
    Once they do, point `boundaries_file` of `kv2026` at the new file.
- **2022** - September 23-24, 2022 ✅ Full data available
- **2018** - October 5-6, 2018 ✅ Full data available
- **2014** - October 10-11, 2014 ✅ Full data available

**Parliamentary Elections** (Volby do Poslanecké sněmovny):
- **2025** - October 5, 2025 ✅ **Data available! Ready for implementation**
  - Note: Full XML opendata structure with complete election results
  - Source: [ČSÚ OpenData PS2025](https://www.volby.cz/opendata/ps2025/ps2025_opendata.htm)
  - Status: Configuration updated, data analyzed, scraper implementation needed

Additional elections can be easily added by extending the `election_config.py` file.

## 🔧 Development

### Testing
```bash
# Test data structure
uv run python -c "
import json
from pathlib import Path
data_file = Path('output/results/municipality_index.json')
if data_file.exists():
    with open(data_file) as f:
        data = json.load(f)
    print(f'✅ Data loaded successfully: {len(data)} municipalities')
else:
    print('❌ Data file not found')
"

# Run with development mode
uv run python run_streamlit.py --dev
```

### Data Export
```bash
# Export specific municipality to CSV
uv run python src/data_exporters.py --municipality 554782

# Export multiple formats
uv run python src/data_exporters.py --format json,csv
```

## 📊 Example Usage

### Find Large Municipalities
```python
import json
from pathlib import Path

# Load municipality data
with open("output/results/municipality_index.json") as f:
    data = json.load(f)

# Get municipalities with 40+ council seats
large_cities = {k: v for k, v in data.items() if v.get('mandates', 0) >= 40}
print(f"Found {len(large_cities)} large cities")
```

### Analyze Turnout Patterns
```python
import pandas as pd

# Load comprehensive data
with open("output/results/all_municipalities_comprehensive.json") as f:
    comprehensive = json.load(f)

# Extract turnout data
turnout_data = []
for code, municipality in comprehensive["municipalities"].items():
    stats = municipality.get("summary_statistics", {})
    turnout_data.append({
        "name": municipality["metadata"]["municipality_name"],
        "turnout": stats.get("turnout_percentage", 0),
        "voters": stats.get("registered_voters", 0)
    })

df = pd.DataFrame(turnout_data)
print(f"Average turnout: {df['turnout'].mean():.1f}%")
```

## 📱 User Interface

The dashboard provides several analysis views:

The app opens on the newest election with a list of the largest cities. After
you pick a municipality (type its name in the sidebar), the views are:

- **Souhrn**: turnout, seats and party results, with the change since the previous election
- **Srovnání**: estimated voter flows between this and the previous election (including
  non-voters) and precinct-by-precinct change of turnout or of a list that ran in both
- **Účast**: turnout across precincts
- **Mapa**: interactive precinct maps
- **Okrsky**: precinct detail and party comparison between precincts
- **Přelivy**: modelled vote flows (only where the ecological inference outputs exist, i.e. Prague 2022)
- **Data**: raw tables

Party shares in **Souhrn** are votes divided by all valid votes. ČSÚ's own
percentage for municipal elections is recalculated for lists with fewer
candidates than seats; the table shows it as a separate column where it differs.

Precincts that ČSÚ corrected and re-sent are counted once (the latest record wins).

### How the voter flows are estimated

`src/election_comparison.py` matches precincts of the two elections by number
(dropping those whose electorate changed by more than 35 %), converts votes to
voters (a list's share of the precinct's votes times the returned envelopes),
merges lists under 3 % into one group and adds non-voters. It then fits one
transition matrix for the whole municipality: an ecological regression like the
Goodman model in `src/ei_models.py`, but for all groups at once and with the
shares constrained to be non-negative and to add up to 100 %.

Treat the result as a model estimate. It assumes voters of a list behaved alike
in every precinct, ignores people who moved, died or came of age, and tends to
underestimate movement between voters and non-voters. Flows are shown only for
councils with at least 30 matched precincts.

```bash
uv run --with pytest pytest tests/
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Czech Statistical Office (ČSÚ) for providing open electoral data
- Streamlit team for the excellent visualization framework
- Czech Pirate Party for supporting open data initiatives

## 🧭 Ecological Inference (Prague 5 split-ticket)

Estimate where OBEC Pirate support likely goes in MCMO using Goodman ecological
regression with Duncan-Davis bounds.

```bash
uv run python src/ecological_inference.py --election kv2022 --share-mode votes
```

Outputs:
- `output/kv2022/reports/ei_prague5_pirates_mcmo_votes.csv`
- `output/kv2022/detailed/ei_prague5_inputs_votes.csv`
- `output/kv2022/reports/ei_prague5_pirates_mcmo_votes_by_family.csv`
- `output/kv2022/reports/ei_prague5_pirates_mcmo_votes_summary.json`

Notes:
- If Pirates are part of a coalition list, pass `--obec-list-number` or tweak
  `--pirate-alias`. Use `--mcmo-list-number` if MČ list differs.
- Use `--share-mode ballots` to normalize by seat counts (defaults: OBEC 65,
  MCMO 41).

### All parties (OBEC → MČ)

```bash
uv run python src/ecological_inference_all_parties.py --election kv2022 --share-mode ballots
```

Outputs:
- `output/kv2022/reports/ei_prague5_all_parties_ballots.csv`
- `output/kv2022/reports/ei_prague5_all_parties_ballots_summary.csv`
- `output/kv2022/reports/ei_prague5_all_parties_ballots_by_family.csv`

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

The CartoDB base maps need a free API key from
<https://carto.com/basemaps/apikey/>. Put it in `.streamlit/secrets.toml` (gitignored) as
`CARTO_BASEMAPS_KEY = "your-key"`, or set an environment variable of the same
name. Without it only OpenStreetMap is offered.

### The new web app

A redesigned app lives next to the Streamlit dashboard: a JSON API
(`src/web_api.py`, FastAPI) over the same result files and a React frontend in
`web/`. It covers the same data with a different workflow: search for a
council, pick the list you follow, then move between the overview, the
precinct map, voter flows, the precinct table and downloads. The Streamlit app
stays available for comparison.

```bash
# API on port 8600
uv run uvicorn --app-dir src web_api:app --host 0.0.0.0 --port 8600

# Frontend with hot reload on port 5180 (proxies /api to the API)
npm --prefix web install
npm --prefix web run dev
```

For a single process, build the frontend once with `npm --prefix web run build`;
the API then serves it from `web/dist` on port 8600. Set `VOLBY_LEGACY_URL` to
the address of the Streamlit app to show a link to it in the header.

The map uses the free OpenFreeMap base map and needs no API key.

Voter-flow estimates take a few seconds each, so the API computes all of them
in the background when it starts (about half a minute the first time) and
keeps them in `output/<election>/cache/`, or in `VOLBY_CACHE_DIR` when that is
set. A stored estimate is used only while the results of both elections and
the model (`FLOW_MODEL_VERSION`) are the ones it was computed from. Set
`VOLBY_PRECOMPUTE=0` to compute them only when a page asks for them.

The voter-flow tab has a second view, "Jak odhad vzniká" (`?pohled=metoda`),
that explains the method on the precincts of the council being viewed: what a
single precinct leaves open, how precincts differ, the search for the
transition table played back step by step, and the repeated fits behind the
ranges. It repeats the estimate in the browser (`web/src/method/model.ts`)
from the model inputs served by `/api/elections/<election>/councils/<code>/comparison/inputs`,
so a change to the estimate in `src/election_comparison.py` has to be mirrored there.

### Address points for the dot map

The map of precincts can show votes as dots, one for a given number of votes.
The dots are drawn next to addresses of the precinct, so that forests, parks
and fields stay empty. The addresses come from the monthly export of the
address register (RÚIAN, about 60 MB to download):

```bash
uv run python src/address_points.py
```

This writes `input/raw/address_points.npy`. Without the file the map still
works and spreads the dots at random inside each precinct.

### Running in Docker

`docker compose up -d --build` serves the new app on `127.0.0.1:3023` (change
the port with `VOLBY_APP_PORT`) and the original Streamlit app on
`127.0.0.1:3022` (`VOLBY_PORT`). The image holds only the code. Election
results and precinct boundaries are not in Git, so copy `output/` and the files
the apps read from `input/` (`input/raw/*.geojson`, `input/raw/*.gpkg`,
`input/raw/address_points.npy` and `input/ps2025/processed/`) next to `docker-compose.yml` before starting it,
together with `.streamlit/secrets.toml` (an empty file is enough if you have
no CARTO key).

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
  non-voters) and precinct-by-precinct change of turnout or of a list that ran in both.
  A city-wide election (e.g. the Prague city council) can be narrowed to one city district.
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
transition matrix: an ecological regression like the Goodman model in
`src/ei_models.py`, but for all groups at once and with the shares constrained
to be non-negative and to add up to 100 %.

Two refinements make the estimate more honest:

- **Types of precincts.** Voters of one list need not behave alike across a
  city. Precincts are clustered by how they voted in the previous election and
  a separate matrix is fitted for each cluster. The number of clusters (1 to 6)
  is the one that best predicts the current result in precincts left out of the
  fit; small municipalities stay with one.
- **Intervals.** The fit is repeated on 100 resamples of the precincts and the
  app shows the 90 % range next to every estimate. The range tells how much a
  number depends on which precincts are in the data. It does not cover the
  error of the model's assumptions.

Treat the result as a model estimate. It ignores people who moved, died or came
of age, and it underestimates movement between voters and non-voters: precinct
results pin down the net change in turnout, not the gross exchange. Flows are
shown only for councils with at least 50 matched precincts, and with a warning
below 100. The thresholds come from running the simple Bayesian model below on the
13 largest Prague districts: from about 100 precincts the two methods agreed within
3-5 points on average, under about 60 they could differ by tens of points.

`research/bayesian_flows_check.py` fits a Bayesian hierarchical model
(multinomial-Dirichlet, every precinct with its own rates) to the same data as
a one-off cross-check. It needs PyMC and takes much longer, so it is not part of the app:

```bash
PYTENSOR_FLAGS='cxx=' uv run --with pymc --with nutpie python research/bayesian_flows_check.py --code 554782
```

(`PYTENSOR_FLAGS='cxx='` avoids a C compiler failure seen on macOS 27.)

That hierarchical model did not converge in our runs (Prague: 137 min, R-hat 1.85;
Prague 5: 86 min, R-hat 1.20). For district councils use `--model simple`: one set of
rates for the council plus estimated noise. It converges in under a minute:

```bash
PYTENSOR_FLAGS='cxx=' uv run --with pymc --with nutpie python research/bayesian_flows_check.py --code 500143 --model simple --draws 2000 --tune 2000
```

`research/bayesian_flows_batch.py` runs the simple model for every council with
50+ matched precincts (27 in 2026) and writes
`output/kv2026/reports/bayesian_simple_summary.csv` with its agreement with the
app's estimate. All 27 converged; the mean difference grows from 1.7 points for
Prague (1 087 precincts) to 5-7 points for councils with 50-60 precincts.

`python3 research/bayesian_progress.py` shows how far running fits are.


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

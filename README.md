# Czech Municipalities Electoral Analysis

> **Comprehensive analysis tool for Czech municipal elections** covering **6,377+ municipalities** across **multiple election years**

[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/streamlit-1.45+-red.svg)](https://streamlit.io/)
[![License](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](LICENSE)

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
the API then serves it from `web/dist` on port 8600.

The map uses the free OpenFreeMap base map and needs no API key.

Voter-flow estimates take a few seconds each, so the API computes all of them
in the background when it starts (`src/web_prepare.py`, about half a minute
the first time) and keeps them in `output/<election>/cache/`, or in
`VOLBY_CACHE_DIR` when that is set. A stored estimate is used only while the
results of both elections and the model (`FLOW_MODEL_VERSION`) are the ones it
was computed from. Set `VOLBY_PRECOMPUTE=0` to compute them only when a page
asks for them. The figures of the analyses below are prepared and stored the
same way.

The voter-flow tab has a second view, "Jak odhad vzniká" (`?pohled=metoda`),
that explains the method on the precincts of the council being viewed: what a
single precinct leaves open, how precincts differ, the search for the
transition table played back step by step, and the repeated fits behind the
ranges. It repeats the estimate in the browser (`web/src/method/model.ts`)
from the model inputs served by `/api/elections/<election>/councils/<code>/comparison/inputs`,
so a change to the estimate in `src/election_comparison.py` has to be mirrored there.

### Analyses

The "Analýzy" section (`/analyzy`) holds written analyses: an article about
one result, with its tables and charts drawn from the same data as the rest
of the app. The first one looks at the Pirates and Praha Sobě in the 2026
Prague election: seats and what would have changed them, voter flows since
2022, precincts and city districts, and an estimate of how the Pirates'
voters of the 2025 parliamentary election voted a year later. The second one
asks where the voters of Spolu and STAN are least firmly theirs: how many of
Spolu's parliamentary voters it keeps in the municipal election, by precinct
and city district, where STAN's new voters came from, and the smallest shift
that would end the two lists' majority. The third one weighs what would have
changed the result: how many seats the voters of SEN would bring on another
list depending on how many of them follow, what more voters or voters coming
back from STAN would take, and the combinations of these. The fourth one looks at
geography: support by travel time to the centre by public transport and by
what people live in (older apartment buildings, panel housing estates, newer
apartment buildings, family houses), with a map of the precincts the reader
can recolour, radar charts and a chart of all precincts. It needs the two
files described under "Travel times and buildings" below.

The fifth one is about a single city district, Praha 5. It has no voter-flow
estimate, because 81 precincts give only a rough one. Instead it looks at the
seats of the district's two blocs and how close the last seat was, compares
how the same voters filled in their two ballots (for the council of the
district and for the council of the city), and goes through the precincts: a
map the reader can recolour, the Pirates' losses by how strong they were
before, neighbourhoods, kinds of housing, a table of all precincts, and whether
turnout goes with the result (precincts by how much it rose and how high it is).
Kinds of housing need the buildings file; without it the article leaves that
part out.

The sixth one does the same for Praha 1, which has 27 seats and only 21
precincts. Its council is split among seven lists, so in place of two blocs it
shows how many votes each list was short of one more seat (one list missed the
five-percent threshold, and a seat, by about 13 voters) and lists every
precinct in a table instead of grouping them.

The figures of both districts come from `src/web_districts.py`: `_District`
holds what any district's analysis shows, and each district adds its lists,
its groups of lists and its neighbourhoods. Neighbourhoods are lists of
precinct numbers (`PRAGUE_5_PARTS`, `PRAGUE_1_PARTS`) that
`research/praha5_neighbourhoods.py` helps to rebuild from the address
register. On the page, `districtBlocks.tsx` and `DistrictMap.tsx` hold what
the two articles share.

An analysis has two halves that are kept apart on purpose:

- `src/web_analyses.py` computes every number (`ANALYSES` maps the address of
  an analysis to the function that builds its figures; those of city districts
  are in `src/web_districts.py`) and serves them at
  `/api/analyses/<slug>`. Bump `ANALYSIS_VERSION` when the figures change, so
  that stored ones are recomputed.
- `web/src/analyses/` holds the text and the page: `index.tsx` lists the
  analyses, one file per analysis (`Prague2026.tsx`) writes the article around
  the figures, and `blocks.tsx` has the tables and charts they share.
  `PrecinctMap.tsx` is a map of a council's precincts for an article: it is
  given the layers to offer, each a number on a colour scale or a named kind.

The estimate between a parliamentary and a municipal election is rougher than
the one between two municipal elections: turnout differs a lot, the lists are
not the same, and the result moves with the number of precinct types more than
with the choice of precincts. Its ranges therefore also cover every number of
precinct types the data allow (`flows_across_settings`).

### Looking for counting errors

`research/precinct_anomalies.py` goes through the precinct results of Prague
for signs of counting errors, for every list on both ballots a voter in Prague
gets. It reads the official results with the votes of every candidate in every
precinct, which the precinct batches above do not hold; ČSÚ publishes them as
two archives (about 23 MB) that the script downloads to
`input/<election>/official/` on its first run.

```bash
uv run python research/precinct_anomalies.py                    # all city districts
uv run python research/precinct_anomalies.py --council 500143   # Praha 5, with the findings printed
```

It writes five tables to `output/<election>/anomalies/` (a run for one district
writes to a folder of its own there):

- `kandidati.csv`: single candidates with a zero or a fraction of the votes of
  their neighbours on the list in one precinct, or a multiple of them. These
  are visible in the data as they are. A list left mostly empty in a
  precinct (only the candidates with votes of their own filled in) is marked,
  because its pile is then read from those few candidates.
- `okrsky.csv`: precincts with unusually many or few votes counted per
  returned envelope.
- `listky.csv`: lists with far more or fewer votes on one ballot than the
  other ballot of the same precinct suggests.
- `mandaty.csv`: how many votes each list was from one more seat, from one
  fewer and from the five-percent threshold, next to the votes missing at its
  candidates and those added by a slip of the pen, and the seats it would have
  with both put right.
- `prehled.csv`: city districts, first those where putting the clear errors
  right would change the seats, then by how large the largest finding is
  against the closest seat.

Only the first table is evidence. The others are hints: a precinct may differ
for a reason of the place (a candidate who lives there, a new housing estate),
and only a recount of the ballots can tell.

### MCP server for AI assistants

The API also offers the same data as tools for AI assistants over the Model
Context Protocol (`src/web_mcp.py`): the list of elections, search for a
council, its results, results by precinct, voter flows and candidates. The
tools only read, and their answers leave out what only the charts and maps
need.

A running app serves them at `/mcp` (streamable HTTP, no sign-in), so an
assistant connects to the address of the app:

```bash
claude mcp add --transport http volby http://localhost:8600/mcp
```

Without a running app, a client can start the server itself over stdio:

```bash
claude mcp add volby -- uv run --project /path/to/volebni-analyza python /path/to/volebni-analyza/src/web_mcp.py
```

Set `VOLBY_PUBLIC_URL` to the public address of the app to have the answers
link to the matching page.

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

### Travel times and buildings

`video/` holds a short motion video made from the same figures; see
`video/README.md` for how to render it.

One analysis places every precinct by how long it takes to the centre of
Prague and by the buildings its people live in. Both come from open data that
two scripts download and reduce to small files:

```bash
# Timetable of Prague Integrated Transport (GTFS, about 50 MB), under a minute
uv run python src/transit_times.py

# Buildings of Prague from the address register (RÚIAN, about 48 MB), a few minutes
uv run python src/buildings.py --municipality 554782
```

`transit_times.py` writes `input/raw/transit_minutes.npy`: for every stop, the
minutes to Můstek on a working morning. It scans the timetable backwards from
the arrival time, so the number is how long before a deadline one has to be at
the stop, averaged over deadlines between 7:30 and 9:00; waiting and changes
are in it. `buildings.py` writes `input/raw/buildings_554782.npy`: position,
flats, floors, use, construction and year of every building.

`src/places.py` puts the two together with the outlines of the precincts. A
precinct's travel time is that of its middle flat: on foot to the stop that
gets to the centre soonest, then by public transport. Its kind of housing is
the kind of building that holds at least half of its flats, otherwise it is
mixed. Apartment buildings built of panels are housing estates; the others
are split at 1990. Without the two files the analysis says what is missing.

### Running in Docker

`docker compose up -d --build` serves the new app on `127.0.0.1:3023` (change
the port with `VOLBY_APP_PORT`). The image holds only the code. Election
results and precinct boundaries are not in Git, so copy `output/` and the files
the app reads from `input/` (`input/raw/*.geojson`, `input/raw/*.gpkg`,
`input/raw/address_points.npy`, `input/raw/transit_minutes.npy`,
`input/raw/buildings_554782.npy` and `input/ps2025/processed/`) next to
`docker-compose.yml` before starting it.

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

This project is licensed under the GNU Affero General Public License v3.0 - see the [LICENSE](LICENSE) file for details. If you run a modified version as a public web service, you must offer its users the source code of your changes.

The election results come from the Czech Statistical Office (volby.cz), addresses and buildings from the RÚIAN register (ČÚZK), and map tiles from OpenFreeMap with data © OpenStreetMap contributors. Those data keep their own terms.

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

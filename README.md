# Czech Municipalities Electoral Analysis

> **Comprehensive analysis tool for 2022 Czech municipal elections** covering **6,377+ municipalities**

[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/streamlit-1.45+-red.svg)](https://streamlit.io/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## 🏛️ What This Tool Does

This tool provides **comprehensive electoral analysis** for any Czech municipality from the 2022 municipal elections. Originally developed for Prague 5, it now supports **all 6,377+ Czech municipalities** with detailed party results, turnout analysis, and interactive visualizations.

### ✨ Key Features

- **📊 All Municipalities**: Support for 6,377+ Czech municipalities
- **🗳️ Complete Election Data**: Party results, mandates, turnout statistics  
- **📍 Geographic Analysis**: Interactive maps and district-level breakdowns
- **🔍 Advanced Filtering**: Search by name, size, turnout, and more
- **📈 Data Visualization**: Charts, maps, and comprehensive dashboards
- **💾 Multiple Formats**: JSON, CSV, and interactive displays
- **🚀 Auto-Setup**: Streamlit app automatically runs data collection when needed

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
# Collect data for ALL municipalities (one-time setup)
uv run python run_all_municipalities.py

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
├── 📥 input/
│   └── raw/                    # Source data from ČSÚ
│       ├── kvcoco_municipality_registry.xml
│       ├── kvros_electoral_parties_register.xml
│       └── electoral_districts_batch_*.xml
├── 📤 output/
│   ├── results/                # Analysis results
│   │   ├── all_municipalities_comprehensive.json
│   │   └── municipality_index.json
│   ├── processed/              # Intermediate data
│   ├── csv/                    # CSV exports
│   └── reports/                # Generated reports
├── 🔧 src/                     # Source code modules
│   ├── all_municipalities_scraper.py
│   ├── municipality_registry.py
│   ├── data_processor.py
│   ├── analyzer.py
│   ├── visualizer.py
│   └── data_exporters.py
├── 📊 streamlit_app.py                    # Main analysis dashboard
├── 🎛️ run_streamlit.py                   # App launcher
└── 📋 run_all_municipalities.py           # Data collection script
```

## 🛠️ Command Line Tools

### 📊 Data Collection
```bash
# Full analysis pipeline
uv run python run_all_municipalities.py

# Registry only (faster for testing)
uv run python run_all_municipalities.py --registry-only

# Use existing data (no downloads)
uv run python run_all_municipalities.py --no-download
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

### 📊 Data Coverage
- **6,377+ municipalities** (complete coverage)
- **16,901 electoral districts** 
- **23,361 party entries** (across all municipalities)
- **10M+ registered voters** total

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

- **📊 Overview**: Key statistics and party results
- **📈 Turnout Analysis**: Detailed voter participation analysis
- **🗺️ Geographic Analysis**: Interactive maps with district boundaries
- **🔍 Data Explorer**: Raw data tables with filtering options
- **🏘️ District Analysis**: Polling district breakdown and comparison

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Czech Statistical Office (ČSÚ) for providing open electoral data
- Streamlit team for the excellent visualization framework
- Czech Pirate Party for supporting open data initiatives

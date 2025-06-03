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

### 2. Data Collection

```bash
# Collect data for ALL municipalities (one-time setup)
uv run python run_all_municipalities.py

# This will:
# - Download municipality registry (6,377+ municipalities)
# - Download electoral district data (200+ batch files)
# - Download party registry (party names, mandates, votes)
# - Generate comprehensive analysis for all municipalities
```

### 3. Launch Analysis Interface

```bash
# Option 1: Simple Municipality Selector
uv run python run_streamlit.py --app selector

# Option 2: Comprehensive Analysis Dashboard  
uv run python run_streamlit.py --app dashboard

# Option 3: Both apps simultaneously
uv run python run_streamlit.py --app both
```

## 📱 Available Interfaces

### 🔍 Municipal Selector (`streamlit_municipality_selector.py`)
**Simple, fast interface for exploring municipalities**

- 🎯 **Purpose**: Quick municipality lookup and comparison
- 🏛️ **Coverage**: All 6,377+ Czech municipalities
- 📊 **Features**: 
  - Advanced filtering (name, size, turnout)
  - Municipality comparison
  - Key statistics and party results
  - Fast loading and responsive

```bash
# Launch simple selector
streamlit run streamlit_municipality_selector.py
```

### 📊 Analysis Dashboard (`streamlit_app.py`)
**Comprehensive analysis with geographic visualizations**

- 🎯 **Purpose**: Deep-dive analysis for selected municipalities  
- 🗺️ **Features**:
  - Interactive geographic maps
  - District-level breakdowns
  - Advanced turnout analysis
  - Data exploration tools
  - Cartographic visualizations

```bash
# Launch comprehensive dashboard
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
├── 🔧 src/                     # Source code
│   ├── all_municipalities_scraper.py
│   ├── municipality_registry.py
│   └── ...
├── 🚀 streamlit_municipality_selector.py  # Simple interface
├── 📊 streamlit_app.py                    # Comprehensive dashboard
└── 🎛️ run_streamlit.py                   # App launcher
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
# Simple selector interface
uv run python run_streamlit.py --app selector

# Comprehensive dashboard
uv run python run_streamlit.py --app dashboard  

# Both apps on different ports
uv run python run_streamlit.py --app both

# Custom port
uv run python run_streamlit.py --app selector --port 8080
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
uv run python -c "from streamlit_municipality_selector import MunicipalitySelector; s=MunicipalitySelector(); print('✅ Data loaded successfully')"

# Run with development mode
uv run python run_streamlit.py --app selector --dev
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
from streamlit_municipality_selector import MunicipalitySelector

selector = MunicipalitySelector()
data = selector.load_municipality_data()

# Get municipalities with 40+ council seats
large_cities = {k: v for k, v in data.items() if v.get('mandates', 0) >= 40}
print(f"Found {len(large_cities)} large cities")
```

### Analyze Turnout Patterns
```python
import pandas as pd
import json

# Load municipality index
with open('output/results/municipality_index.json') as f:
    municipalities = json.load(f)

df = pd.DataFrame.from_dict(municipalities, orient='index')
print(f"Average turnout: {df['turnout'].mean():.1f}%")
print(f"Highest turnout: {df.loc[df['turnout'].idxmax(), 'name']} ({df['turnout'].max():.1f}%)")
```

## 🤝 Contributing

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/amazing-feature`
3. **Commit** changes: `git commit -m 'Add amazing feature'`
4. **Push** to branch: `git push origin feature/amazing-feature`
5. **Open** a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Links

- **Data Source**: [Czech Statistical Office (ČSÚ)](https://www.volby.cz/)
- **Election Results**: [2022 Municipal Elections](https://www.volby.cz/pls/kv2022/kv2022)
- **Geographic Data**: [Electoral District Boundaries](https://www.volby.cz/opendata/kv2022/geo/)

---

**Built with ❤️ for Czech electoral transparency and analysis**

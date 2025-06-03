# Prague 5 Election Analysis 🗳️

A comprehensive data analysis pipeline for Prague 5 municipal election results, providing detailed insights into voter participation, party performance, candidate analysis, and civic engagement patterns.

## Overview

This project analyzes the 2022 municipal elections in Prague 5 (Městská část Praha 5), one of Prague's municipal districts, using comprehensive web scraping from the Czech Statistical Office's volby.cz website. The analysis includes complete party results, individual candidate performance, voter turnout statistics, and actionable recommendations for improving civic engagement.

## Key Findings

### 2022 Prague 5 Municipal Elections
- **Total Registered Voters**: 60,242 citizens
- **Voter Turnout**: 42.4% (25,540 ballots cast)
- **Valid Votes**: 978,054 total votes cast
- **Elected Members**: 41 council members
- **Parties Analyzed**: 12 political parties/coalitions
- **Candidates Analyzed**: 475 individual candidates

### Top Electoral Results
1. **PRAHA 5 SOBĚ**: 209,131 votes (21.38%) → **10 mandates**
2. **SPOLEČNĚ PRO PRAHU 5**: 208,605 votes (21.33%) → **10 mandates**  
3. **ANO 2011**: 135,445 votes (13.85%) → **7 mandates**
4. **Česká pirátská strana**: 114,871 votes (11.74%) → **6 mandates**
5. **Koalice SEN 21 pro Prahu 5**: 105,102 votes (10.75%) → **5 mandates**

## Features

### 🔍 Enhanced Data Collection
- **Comprehensive Web Scraping**: Complete election results from volby.cz
- **Party-Level Data**: Vote counts, percentages, mandates for all 12 parties
- **Candidate-Level Data**: Individual candidate names, votes, and rankings
- **Summary Statistics**: Turnout, registered voters, ballot data
- **Structured Output**: Clean JSON format ready for analysis

### 📊 Data Processing  
- **Czech Number Formatting**: Handles space-separated thousands properly
- **Character Encoding**: UTF-8 support for Czech characters and diacritics
- **Data Validation**: Ensures data integrity throughout the pipeline
- **Multiple Output Formats**: JSON, structured data ready for analysis

### 🌐 Interactive Streamlit Dashboard
- **Real-time Visualization**: Interactive web dashboard powered by Streamlit
- **Geographic Analysis**: Interactive maps with electoral district boundaries
- **Data Explorer**: Browse and explore all collected electoral data
- **Turnout Analysis**: Visual analysis of voter participation patterns
- **Responsive Design**: Works on desktop and mobile devices

### 📈 Interactive Visualizations
- **Party Performance**: Vote share analysis and mandate distribution
- **Candidate Analysis**: Individual performance within parties
- **Turnout Analysis**: Voter participation patterns
- **Web Interface**: Beautiful HTML dashboards with responsive design

### 🎯 Statistical Analysis
- **Electoral Mathematics**: Vote-to-mandate conversion analysis
- **Party Competition**: Market share and competitive landscape
- **Candidate Performance**: Individual vote analysis within party lists
- **Turnout Patterns**: Participation rate analysis

### 📋 Automated Reporting
- **Comprehensive Reports**: JSON format with complete election data
- **Executive Summaries**: Key findings for stakeholders
- **Data Quality Assessment**: Coverage and source documentation

## Installation & Setup

### Prerequisites
- Python 3.13+
- `uv` package manager (recommended)

### Quick Start
```bash
# Clone the repository
git clone <repository-url>
cd volebni-analyza

# Install dependencies using uv
uv sync

# Run the complete analysis pipeline
uv run python run_analysis.py

# Launch the interactive Streamlit dashboard
uv run python run_streamlit.py
# OR: uv run streamlit run streamlit_app.py
```

### Manual Installation
```bash
# Alternative: Install with pip  
pip install -r requirements.txt

# Run analysis
python run_analysis.py

# Launch dashboard
streamlit run streamlit_app.py
```

## Usage

### 🚀 Streamlit Dashboard (Recommended)
```bash
# Launch the interactive dashboard
uv run python run_streamlit.py

# Or directly with streamlit
uv run streamlit run streamlit_app.py
```

The dashboard provides:
- **📊 Overview**: Key metrics and summary statistics
- **📈 Turnout Analysis**: Interactive charts and voter participation data
- **🗺️ Geographic Analysis**: Interactive map with electoral districts (automatically downloads GeoJSON data)
- **🔍 Data Explorer**: Browse and analyze all collected data

### Complete Analysis Pipeline
```bash
uv run python run_analysis.py
```
This runs the entire pipeline: comprehensive data scraping → processing → analysis reporting

### Individual Components
```bash
# XML API electoral district data scraping (primary scraper)
uv run src/xml_scraper.py

# Generate visualizations
uv run src/visualizer.py

# Statistical analysis and reporting
uv run src/analyzer.py

# Process data (if using CSV files)
uv run src/data_processor.py
```

## Project Structure

```
volebni-analyza/
├── src/                          # Source code modules
│   ├── xml_scraper.py           # Electoral district XML API scraper (primary)
│   ├── data_processor.py        # Data cleaning and CSV processing  
│   ├── visualizer.py            # Interactive chart generation
│   ├── analyzer.py              # Statistical analysis engine
│   └── main.py                  # Main pipeline script
├── input/                        # Input data (source files)
│   └── raw/                     # Raw source data files
│       ├── *.xml               # Electoral district XML files
│       ├── *.csv               # Election results CSV files
│       └── ...                 # Other raw data sources
├── output/                       # Generated data and outputs
│   ├── processed/               # Processed and cleaned data
│   │   ├── prague5_municipal_*.json
│   │   └── prague5_comprehensive.json
│   ├── detailed/                # Detailed analysis data
│   │   └── prague5_electoral_districts.json
│   ├── results/                 # Final analysis results
│   │   ├── analysis_summary.json
│   │   └── prague5_comprehensive_results.json
│   ├── visualizations/          # Generated charts and maps
│   │   ├── index.html
│   │   ├── turnout_analysis.html
│   │   └── districts_map.html
│   └── reports/                 # Analysis reports
│       ├── comprehensive_analysis_report.json
│       └── analysis_summary.md
├── streamlit_app.py             # Interactive Streamlit dashboard
├── run_streamlit.py             # Streamlit launcher script
├── run_analysis.py              # Main analysis pipeline
├── migrate_data_structure.py    # Data structure migration utility
├── DATA_STRUCTURE.md            # Documentation of directory structure
├── pyproject.toml              # Project dependencies and configuration
├── uv.lock                     # Dependency lock file
└── README.md                   # This documentation
```

### Directory Structure

#### Input Directory (`input/`)
- **`input/raw/`**: Original, unmodified source data files
  - XML files with electoral district information from volby.cz API
  - CSV files with election results (if available)
  - Any other source data files

#### Output Directory (`output/`)
All generated/processed data is organized by type:
- **`output/processed/`**: Cleaned and processed datasets ready for analysis
- **`output/detailed/`**: Detailed analysis with enriched data
- **`output/results/`**: Final analysis results and findings
- **`output/visualizations/`**: Interactive HTML charts and maps
- **`output/reports/`**: Generated analysis reports and documentation

## Generated Outputs

### 🌐 Interactive Dashboard
- **Streamlit App**: `streamlit_app.py` - Interactive web dashboard
- **Geographic Data**: Automatically downloads electoral district GeoJSON from volby.cz
- **Real-time Analysis**: Live data exploration and visualization

### 📊 Complete Election Data
- **`output/results/prague5_comprehensive_results.json`** - Complete results with all candidate data
- **`output/results/prague5_complete_results.json`** - Main results page data
- **`output/results/analysis_summary.json`** - Pipeline execution summary

### 📑 Analysis Reports
- **`output/reports/analysis_summary.md`** - Human-readable summary report  
- **`output/reports/comprehensive_analysis_report.json`** - Detailed statistical analysis

### 📦 Datasets
- **`output/processed/prague5_districts.json`** - List of all 81 electoral districts
- **`output/detailed/prague5_detailed_results.json`** - District-level results
- **`output/processed/prague5_*.json`** - Processed datasets by year

## Data Sources

### Primary Data Sources
- **Primary**: Czech Statistical Office (Český statistický úřad) - volby.cz
- **Method**: Comprehensive web scraping of complete results pages
- **Coverage**: Prague 5 municipality (code: 500143) - 100% complete
- **Elections**: 2022 Municipal Elections
- **URL**: https://www.volby.cz/pls/kv2022/kv1111?xjazyk=CZ&xid=0&xdz=5&xnumnuts=1100&xobec=500143&xstat=0&xvyber=0

### Geographic Data
- **Electoral Districts GeoJSON**: https://www.volby.cz/opendata/kv2022/geo/vol_okrsky_2022g100.geojson
- **Format**: GeoJSON with electoral district boundaries
- **Usage**: Automatically downloaded by Streamlit dashboard for interactive maps
- **Coverage**: All Czech electoral districts (filtered for analysis)

### Electoral District XML API
- **API Endpoint**: https://www.volby.cz/pls/kv2022/vysledky_okrsky
- **Format**: Structured XML data with detailed district-level results
- **Coverage**: Individual electoral districts (okrsky) with granular vote data
- **Current Approach**: Downloads relevant batches, filters locally for Prague 5 data
- **Files Generated**: 
  - `input/raw/electoral_districts_batch_30.xml` - Contains Prague 5 district data
  - `input/raw/prague5_districts_batch100.xml` - Additional Prague 5 data
  - `output/detailed/prague5_electoral_districts.json` - Processed district results

### 🚀 Optimization Opportunity
**TODO**: The XML API likely supports direct municipality/district filtering parameters that could eliminate the need to download and filter batches locally. Potential parameters to investigate:
- `obec=500143` (municipality code)
- `kodzastup=500143` (district code) 
- `nuts=CZ0100` (Prague NUTS code)
- Other filtering parameters in the API documentation

**Current Efficiency**: Downloads ~30 batches, keeps only 2 relevant files (~95% reduction)
**Potential**: Direct API filtering could eliminate batch downloads entirely

**API Schema**: See `kv_vysledky_okrsky.xsd` for complete XML structure documentation

## Key Insights

### Electoral Competition
- **Tight Race**: Top 2 parties separated by only 526 votes (0.05%)
- **Coalition Government**: No single party achieved majority (21 seats needed)
- **High Fragmentation**: 12 parties competed, 6 won representation
- **Strong Participation**: 42.4% turnout typical for municipal elections

### Party Performance
- **PRAHA 5 SOBĚ** and **SPOLEČNĚ PRO PRAHU 5** tied for leadership
- **ANO 2011** maintained strong third position with 7 mandates
- **Pirates** achieved solid representation with 6 mandates
- 5 parties failed to cross electoral threshold

### Candidate Analysis
- **475 total candidates** across all party lists
- Individual candidate vote analysis available for all parties
- Performance metrics calculated for candidate ranking within parties

## Technical Implementation

### Enhanced Scraping Architecture
- **Session Management**: Maintains cookies and headers for reliable scraping
- **Table Parsing**: Intelligent extraction of both summary and detailed tables
- **Link Following**: Automatically discovers and scrapes party detail pages
- **Error Handling**: Robust failure recovery with detailed logging
- **Rate Limiting**: Respectful 1-second delays between requests

### Data Structure
```python
{
  "metadata": {
    "municipality": "Praha 5",
    "election_year": "2022", 
    "source_url": "...",
    "scrape_date": "2025-06-02T16:01:34"
  },
  "summary_statistics": {
    "elected_members": 41,
    "registered_voters": 60242,
    "turnout_percentage": 42.4,
    "valid_votes": 978054
  },
  "party_results": [...],
  "party_results_detailed": [...]
}
```

## Development & Contributing

### Architecture
- **Modular Design**: Separate modules for scraping, processing, visualization, analysis
- **Clean Codebase**: Removed outdated collectors, streamlined to essential components
- **Error Handling**: Comprehensive logging and graceful failure recovery
- **Documentation**: Detailed docstrings and type hints

### Testing
```bash
# Run individual components to test
uv run src/xml_scraper.py
uv run src/visualizer.py
uv run src/analyzer.py
```

### Adding New Features
1. **Data Sources**: Extend `ElectoralDistrictXMLScraper` class in `xml_scraper.py`
2. **Visualizations**: Add methods to `Prague5Visualizer` class  
3. **Analysis**: Enhance `Prague5ElectionAnalyzer` with new metrics
4. **Reports**: Modify report generation in analyzer module

## Dependencies

### Core Libraries
- **pandas**: Data manipulation and analysis
- **plotly**: Interactive visualizations  
- **beautifulsoup4**: Web scraping and HTML parsing
- **requests**: HTTP requests and session management
- **geopandas**: Geographic data processing

### Visualization Stack
- **plotly.express**: Quick chart creation
- **plotly.graph_objects**: Advanced chart customization
- **HTML/CSS**: Custom dashboard styling

## Future Enhancements

### Planned Features
1. **Historical Analysis**: Multi-year trend analysis (2014, 2018, 2022)
2. **District Mapping**: Geographic visualization of voting patterns
3. **Demographic Correlation**: Link voter patterns to census data
4. **Comparative Analysis**: Cross-district analysis with other Prague areas
5. **Real-time Monitoring**: Live election night analysis capabilities

### Technical Improvements
1. **API Integration**: If Czech Statistical Office APIs become available
2. **Database Storage**: PostgreSQL/SQLite for larger datasets
3. **Automated Scheduling**: Regular data updates and monitoring
4. **Advanced Analytics**: Machine learning for pattern recognition

## License

This project is for educational and research purposes. Election data is public domain from the Czech Statistical Office.

---

## Quick Start 🚀

### First Time Setup
```bash
# Clone and setup
git clone <repository-url>
cd volebni-analyza
uv sync

# Run the guided quick start
uv run python quick_start.py
```

The `quick_start.py` script will:
1. Check for existing data
2. Run the complete analysis pipeline if needed
3. Launch the interactive Streamlit dashboard
4. Guide you through the entire process

### Alternative: Manual Setup
```bash
# 1. Run analysis pipeline
uv run python run_analysis.py

# 2. Launch dashboard  
uv run python run_streamlit.py
```

### What You'll Get
- **📊 Interactive Dashboard**: Web-based visualization at `http://localhost:8501`
- **🗺️ Electoral Maps**: Interactive maps with district boundaries
- **📈 Data Analysis**: Comprehensive electoral statistics and insights
- **🔍 Data Explorer**: Browse all collected data interactively

## Getting Started

### For Quick Exploration
```bash
# One-command guided setup
uv run python quick_start.py
```

### For Development & Customization
1. **Complete Analysis**: `uv run python run_analysis.py`
2. **Interactive Dashboard**: `uv run python run_streamlit.py` 
3. **Explore Results**: Check `data/results/` for comprehensive election data
4. **Read Analysis**: Review generated reports in `data/reports/`
5. **Customize**: Modify source code in `src/` directory for your needs

### Available Commands
```bash
# Analysis pipeline
uv run python run_analysis.py          # Complete data collection & analysis

# Visualization options  
uv run python run_streamlit.py         # Interactive Streamlit dashboard
uv run streamlit run streamlit_app.py  # Alternative dashboard launch

# Individual components
uv run src/xml_scraper.py              # Data collection only
uv run src/visualizer.py               # Static visualizations
uv run src/analyzer.py                 # Analysis & reporting

# Quick start wizard
uv run python quick_start.py           # Guided setup process
```

**📊 Happy Analyzing!** 🇨🇿

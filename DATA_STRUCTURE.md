# Data Directory Structure

This document explains the organized data directory structure that supports multiple elections, separating input and output data for better organization and clarity, along with detailed descriptions of all data files and their contents.

## Multi-Election Directory Structure

The application now supports multiple elections with a clear separation by election ID:

```
volebni-analyza/
├── input/                     # All input data (source files)
│   ├── kv2022/                # 2022 Municipal Elections
│   │   └── raw/               # Raw source data files
│   │       ├── electoral_districts_batch_*.xml
│   │       ├── kvcoco_municipality_registry.xml
│   │       └── kvros_electoral_parties_register.xml
│   ├── kv2018/                # 2018 Municipal Elections
│   │   └── raw/
│   └── kv2014/                # 2014 Municipal Elections
│       └── raw/
│
├── output/                    # All generated/processed data
│   ├── kv2022/                # 2022 Election Results
│   │   ├── csv/               # CSV exports for dashboard
│   │   │   ├── party_results.csv
│   │   │   ├── district_data.csv
│   │   │   ├── summary_statistics.csv
│   │   │   └── district_party_results.csv
│   │   ├── processed/         # Processed and cleaned data
│   │   │   └── municipality_registry.json
│   │   ├── detailed/          # Detailed analysis data
│   │   ├── results/           # Final analysis results
│   │   │   ├── all_municipalities_comprehensive.json
│   │   │   └── municipality_index.json
│   │   ├── visualizations/    # Generated charts and maps
│   │   └── reports/           # Analysis reports
│   │       └── analysis_summary.md
│   ├── kv2018/                # 2018 Election Results
│   │   └── ...
│   └── kv2014/                # 2014 Election Results
│       └── ...
│
├── src/                       # Source code modules
│   ├── election_config.py     # Election configuration management (NEW)
│   ├── all_municipalities_scraper.py
│   ├── municipality_registry.py
│   ├── data_processor.py
│   ├── analyzer.py
│   ├── visualizer.py
│   └── data_exporters.py
│
├── streamlit_app.py                    # Main analysis dashboard
├── run_streamlit.py                    # App launcher
├── run_all_municipalities.py           # Data collection script
└── migrate_to_multi_election.py        # Migration tool (NEW)
```

## Election Configuration

Each election is identified by an election ID and has its own configuration:

### Available Elections

- **kv2022**: Komunální volby 2022 (Municipal Elections 2022)
  - Date: 2022-09-23
  - Base URL: https://www.volby.cz/pls/kv2022
  - OpenData: https://www.volby.cz/opendata/kv2022/xml

- **kv2018**: Komunální volby 2018 (Municipal Elections 2018)
  - Date: 2018-10-05
  - Base URL: https://www.volby.cz/pls/kv2018
  - OpenData: https://www.volby.cz/opendata/kv2018/xml

- **kv2014**: Komunální volby 2014 (Municipal Elections 2014)
  - Date: 2014-10-10
  - Base URL: https://www.volby.cz/pls/kv2014
  - OpenData: https://www.volby.cz/opendata/kv2014/xml

## Using Multiple Elections

### Command Line

```bash
# List available elections
python run_all_municipalities.py --list-elections

# Collect data for specific election
python run_all_municipalities.py --election kv2022
python run_all_municipalities.py --election kv2018

# Use short form
python run_all_municipalities.py -e kv2014
```

### Streamlit Dashboard

The Streamlit app includes an **election selector** in the sidebar:

1. Select the election year from the dropdown (e.g., "Komunální volby 2022")
2. The app automatically loads data for that election
3. All visualizations and analyses update accordingly

### Auto-Setup Feature

The Streamlit applications include **auto-setup functionality** for each election:

- **Automatic Detection**: Apps detect when required data files are missing for the selected election
- **One-Click Setup**: Users can run data collection directly from the web interface
- **Progress Monitoring**: Real-time progress updates during data collection
- **Seamless Experience**: No need to run command-line tools manually

### How Auto-Setup Works

1. **Data Check**: App checks for `output/{election_id}/results/municipality_index.json` and `output/{election_id}/results/all_municipalities_comprehensive.json`
2. **Missing Data Alert**: If files are missing, shows a user-friendly warning with setup button
3. **Background Collection**: Runs `run_all_municipalities.py --election {election_id}` in the background with progress updates
4. **Auto-Refresh**: Automatically refreshes the app once data collection completes

## Migration from Old Structure

If you have existing data in the old structure (`input/raw/`, `output/`), use the migration script:

```bash
# Dry run (shows what would happen)
python migrate_to_multi_election.py --dry-run

# Perform migration (creates backups automatically)
python migrate_to_multi_election.py --election-id kv2022

# Skip backups (not recommended)
python migrate_to_multi_election.py --no-backup
```

The migration script:
- Creates backups of your existing data
- Moves data to the new structure (`input/kv2022/`, `output/kv2022/`)
- Preserves all your existing files
- Creates a migration info file for reference

## Input Data Files (`input/raw/`)

### XML Electoral Data Files

**Source**: Czech Statistical Office (Český statistický úřad) - Municipal Elections 2022  
**URL Pattern**: `https://www.volby.cz/opendata/kv2022/xml/`

#### Electoral District XML Files
- **Pattern**: `electoral_districts_batch_[ID].xml`
- **Count**: ~55 files covering all Czech electoral districts
- **Prague 5 Files**: Batches 30, 34, 40, 45-50, 55-58, 60, 63-81, 83, 85-87, 89-97, 100-103, 107, 109, 119, 121, 136, 142, 144
- **Content**: Detailed voting results by electoral district and party
- **Key Elements**:
  - `<OBVOD>` - Electoral district information
  - `<OKRSEK>` - Polling station data
  - `<HLASY>` - Vote counts by party
  - `<UCAST>` - Turnout statistics

#### Political Party Registry Files
- **Files**: 
  - `kvros_electoral_parties_register.xml` (12MB) - Complete party registry
  - `cvs_electoral_parties.xml` (460KB) - CVS party data
  - `cns_political_parties.xml` (37KB) - CNS party data
- **Content**: Party registration details, candidate lists, coalition information

### Key XML Data Structure
**Source**: Direct analysis of actual ČSÚ XML files in `input/raw/electoral_districts_batch_*.xml`

```xml
<VYSLEDKY_OKRSKY xmlns="http://www.volby.cz/kv/" 
                  DATUM_CAS_GENEROVANI="2022-09-24T18:10:00">
  <DAVKA DATUMVOLEB="20220923" PORADI_DAVKY="45" OKRSKY_DAVKA="230" 
         OKRSKY_CELKEM="16854" OKRSKY_ZPRAC="11173"/>
  
  <OKRSEK CIS_OBEC="500208" CIS_OKRSEK="8057" KODZASTUP="554782" 
          CIS_OBVODU="1" OZNAC_TYPU="OBEC" PORADI_ZPRAC="10721" 
          DATUM_CAS_ZPRAC="2022-09-24T18:05:24" OPAKOVANE="1">
    
    <UCAST_OKRSEK ZAPSANI_VOLICI="92"    <!-- Registered voters -->
                  VYDANE_OBALKY="41"     <!-- Issued ballots -->
                  ODEVZDANE_OBALKY="40"  <!-- Returned ballots -->
                  PLATNE_HLASY="1386"/>  <!-- Valid votes -->
    
    <HLASY_OKRSEK POR_STR_HLAS_LIST="1" HLASY="65"/>   <!-- Party 1: 65 votes -->
    <HLASY_OKRSEK POR_STR_HLAS_LIST="2" HLASY="130"/>  <!-- Party 2: 130 votes -->
    <HLASY_OKRSEK POR_STR_HLAS_LIST="4" HLASY="455"/>  <!-- Party 4: 455 votes -->
    <!-- ... additional HLASY_OKRSEK elements for each party with votes -->
    
  </OKRSEK>
  
  <!-- ... additional OKRSEK elements for other districts -->
</VYSLEDKY_OKRSKY>
```

**Key Elements Explained**:
- `<VYSLEDKY_OKRSKY>` - Root element with namespace and generation timestamp
- `<DAVKA>` - Batch metadata (election date, batch number, total districts processed)
- `<OKRSEK>` - Individual polling district/okrsek with attributes:
  - `CIS_OBEC` - Municipality code (554782 = Prague 5 administrative code)
  - `CIS_OKRSEK` - District number (5001-5081 for Prague 5 okrseks)
  - `KODZASTUP` - Administrative territorial code (554782 for Prague 5)
  - `CIS_OBVODU` - Electoral district number (always 1 for Prague 5)
  - `OZNAC_TYPU` - Election type ("OBEC" = municipal, "MCMO" = city district)
  - `OPAKOVANE` - Whether results were corrected (0=original, 1=corrected)
- `<UCAST_OKRSEK>` - Turnout statistics (all as attributes)
- `<HLASY_OKRSEK>` - Vote counts per party (one element per party with votes)

## Output Data Files

### CSV Files (`output/csv/`)

#### 1. `party_results.csv` (1KB, 14 lines)
**Purpose**: Aggregated results for all political parties in Prague 5  
**Source**: Aggregated from XML district files  

| Field | Type | Description |
|-------|------|-------------|
| `list_number` | integer | Official party list number |
| `party_name` | string | Clean party name |
| `votes_absolute` | integer | Total votes received |
| `votes_percentage` | float | Percentage of total votes |
| `estimated_voters` | integer | Total votes ÷ 41 seats |
| `num_seats_used` | integer | Number of seats (always 41) |
| `candidate_count` | integer | Number of candidates (currently empty) |
| `mandates_won` | integer | Seats won (currently empty) |
| `data_source` | string | "XML_aggregation_with_web_names" |

**Sample Data**:
```csv
list_number,party_name,votes_absolute,votes_percentage,estimated_voters
4,PRAHA 5 SOBĚ,520329,20.78,12691
8,Česká pirátská strana,407531,16.28,9940
6,Koalice SEN 21 pro Prahu 5,226147,9.03,5516
```

#### 2. `district_data.csv` (13KB, 164 lines)
**Purpose**: Turnout and voting statistics for each electoral district  
**Source**: Processed from XML files with district-level aggregation  

| Field | Type | Description |
|-------|------|-------------|
| `district_id` | string | Format: "5001-1" (district-obvod) |
| `district_name` | string | "District 1 (OBEC)" or "District 1 (MCMO)" |
| `district_code` | string | 4-digit okrsek number (5001-5081) |
| `obvod_number` | integer | Electoral district number (always 1) |
| `type` | string | "OBEC" (municipal) or "MCMO" (city district) |
| `turnout_percentage` | float | Voter turnout percentage |
| `registered_voters` | integer | Number of registered voters |
| `issued_ballots` | integer | Ballots issued to voters |
| `returned_ballots` | integer | Ballots returned by voters |
| `valid_votes` | integer | Total valid votes cast |
| `processing_time` | datetime | When data was processed |

**Sample Data**:
```csv
district_id,district_name,district_code,turnout_percentage,registered_voters,valid_votes
5001-1,District 1 (OBEC),5001,41.82,440,11481
5001-1,District 1 (MCMO),5001,41.82,440,7141
```

**Note**: Each district has 2 rows (OBEC and MCMO elections held simultaneously)

#### 3. `summary_statistics.csv` (462B, 12 lines)
**Purpose**: High-level statistics for Prague 5  
**Source**: Aggregated from all district data  

| Field | Type | Description |
|-------|------|-------------|
| `metric` | string | Name of the statistic |
| `value` | string/numeric | Value of the statistic |
| `category` | string | "metadata" or "statistics" |
| `data_type` | string | Data type hint |

**Key Statistics**:
- `municipality`: "Praha 5"
- `election_year`: 2022
- `electoral_districts`: 162 (81 districts × 2 election types)
- `registered_voters`: 120,484
- `turnout_percentage`: 42.36%
- `valid_votes`: 2,503,423

#### 4. `district_party_results.csv` (147KB, 1,781 lines)
**Purpose**: Detailed vote counts for each party in each district  
**Source**: Direct extraction from XML files  

| Field | Type | Description |
|-------|------|-------------|
| `district_id` | string | Format: "5001-1" |
| `district_name` | string | District description |
| `obvod_number` | integer | Electoral district number |
| `district_type` | string | "OBEC" or "MCMO" |
| `party_list_number` | integer | Official party list number |
| `party_name` | string | Clean party name |
| `votes` | integer | Votes received by party in district |
| `percentage` | float | Party's percentage in this district |
| `total_district_votes` | integer | Total valid votes in district |

**Sample Data**:
```csv
district_id,party_name,votes,percentage,total_district_votes
5001-1,PRAHA 5 SOBĚ,2468,21.50,11481
5001-1,Česká pirátská strana,2403,20.93,11481
```

### JSON Files (`output/processed/`, `output/detailed/`, `output/results/`)

#### Processed Data
- **`municipality_registry.json`**: Intermediate processing files
- **`intermediate processing files`**: Additional intermediate processing files

#### Detailed Analysis
- **`detailed analysis results`**: Detailed analysis results

#### Results
- **`municipality_index.json`**: Key findings and statistics
- **`all_municipalities_comprehensive.json`**: Complete analysis results

### Visualization Files (`output/visualizations/`)

#### HTML Dashboards
- **`index.html`**: Main interactive dashboard
- **`turnout_analysis.html`**: Turnout-focused analysis
- **`districts_map.html`**: Geographic visualization

### Report Files (`output/reports/`)

- **`comprehensive_analysis_report.json`**: Machine-readable analysis
- **`analysis_summary.md`**: Human-readable summary

## Data Processing Pipeline

### 1. Input Processing (`run_analysis.py`)
```
XML Files → Parse Electoral Data → Extract Prague 5 → Clean Party Names
```

### 2. Data Transformation (`src/data_exporters.py`)
```
Parsed Data → Aggregate by Party/District → Export to CSV → Generate Statistics
```

### 3. Dashboard Integration (`streamlit_app.py`)
```
CSV Files → Load into DataFrames → Interactive Visualizations → Geographic Maps
```

## Key Data Relationships

### Geographic Hierarchy
```
Prague 5 Municipality (554782)
├── Okrsek 5001 (Polling District)
│   ├── OBEC Election Results
│   └── MCMO Election Results
├── Okrsek 5002
│   ├── OBEC Election Results
│   └── MCMO Election Results
└── ... (5003-5081)
```

### Electoral System
- **OBEC**: Municipal council elections (broader candidate pool)
- **MCMO**: City district elections (local representatives)
- **Dual Voting**: Citizens vote in both elections simultaneously
- **Seats**: 41 seats available in Prague 5 council

### Party Filtering
Original XML contains ~22 party lists, filtered to 12 real parties:
- Removed generic "Party List X" entries
- Cleaned names with quotation marks
- Filtered out zero-vote entries

## Data Quality Notes

### Completeness
- **Districts**: 81 okrseks covered (5001-5081)
- **Missing Districts**: Some batch files may not contain Prague 5 data
- **Data Types**: Both OBEC and MCMO results for each district

### Accuracy
- **Source**: Official Czech Statistical Office data
- **Processing Date**: 2025-06-02 (recent extraction)
- **Validation**: Cross-checked totals between aggregated and detailed data

### Known Issues
- Some candidate counts and mandate information not yet populated
- Processing times vary significantly between districts
- Legacy data directory structure still exists (to be cleaned)

## Usage Examples

### Loading Party Results
```python
import pandas as pd
parties = pd.read_csv('output/csv/party_results.csv')
top_party = parties.loc[0, 'party_name']  # "PRAHA 5 SOBĚ"
```

### District Analysis
```python
districts = pd.read_csv('output/csv/district_data.csv')
# Group by okrsek (combine OBEC and MCMO)
districts['district_code'] = districts['district_id'].str.split('-').str[0]
by_okrsek = districts.groupby('district_code').first()
```

### Geographic Visualization
```python
# Used by streamlit_app.py for cartogram generation
party_results = pd.read_csv('output/csv/district_party_results.csv')
geographic_data = party_results[party_results['party_name'] == 'PRAHA 5 SOBĚ']
```

This structure enables reproducible analysis, clear data lineage, and efficient dashboard performance while maintaining official data accuracy. 
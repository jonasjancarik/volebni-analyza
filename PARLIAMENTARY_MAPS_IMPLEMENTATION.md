# Parliamentary Elections Map Implementation

## ✅ Implementation Complete!

Successfully implemented polling station-level map visualization for parliamentary elections (PS2025).

## 📊 What Was Implemented

### 1. **GeoJSON Data Management**
- **Municipal Elections (KV2022)**: Uses `input/raw/electoral_districts_boundaries.geojson` (8 MB, 14,733 stations)
- **Parliamentary Elections (PS2025)**: Uses `input/raw/electoral_districts_boundaries_2025.geojson` (252.6 MB, 14,711 stations)
- Automatic selection based on `election_type` in `load_geojson_data()`

### 2. **OBEC Code Mapping**
Created `input/ps2025/processed/obec_to_geojson_mapping.json` to map PS2025 municipality codes to GeoJSON codes:
- **PS2025 Data**: Uses `OBEC` codes (e.g., "500054" for Praha 1)
- **2025 GeoJSON**: Uses `kod_obec` codes (e.g., "554782" for Praha 1)
- **Mapping File**: Contains 6,389 OBEC mappings extracted from `pscoco.xml`

### 3. **Polling Station Integration**
- Added `load_obec_mapping()` function to load OBEC→GeoJSON mapping
- Updated `load_municipality_data()` to include polling stations for parliamentary elections
- Converts polling stations to `district_data` DataFrame format for visualization compatibility

### 4. **GeoJSON Property Compatibility**
Created `get_district_code_from_geojson()` helper function to handle:
- **2022 GeoJSON**: Uses uppercase `CISLO` property
- **2025 GeoJSON**: Uses lowercase `cislo` property
- Automatically detects and uses the correct format

### 5. **Map Filtering for Parliamentary Elections**
Updated the "Geographic Analysis" tab to:
- Extract unique OBEC codes from polling stations
- Map OBEC codes to GeoJSON `kod_obec` using the mapping file
- Filter 2025 GeoJSON features by matched `kod_obec` values
- Display all polling stations for the selected electoral district

## 📁 File Structure

```
input/
├── raw/
│   ├── electoral_districts_boundaries.geojson         # KV2022 (8 MB)
│   └── electoral_districts_boundaries_2025.geojson    # PS2025 (252.6 MB)
└── ps2025/
    ├── raw/
    │   └── pscoco.xml                                 # Source for mapping
    └── processed/
        └── obec_to_geojson_mapping.json               # OBEC→GeoJSON mapping

output/
└── ps2025/
    └── results/
        ├── parliamentary_election_results.json         # 10.4 MB, includes 14,819 polling stations
        └── district_index.json                        # District index
```

## 🗺️ How It Works

### Data Flow for Parliamentary Elections

1. **User selects Electoral District** (e.g., "1 - Praha")
   - `selected_zastupitelstvo_code = "1"`

2. **Load Electoral Data**
   ```python
   electoral_data = load_municipality_data("1", "ps2025")
   ```
   - Loads district 1 from `parliamentary_election_results.json`
   - Filters polling stations where `district_code` starts with "1" (e.g., "1100")
   - Returns: `party_results`, `candidates`, `polling_stations`, `district_data`

3. **Load GeoJSON and Mapping**
   ```python
   geojson_data = load_geojson_data("ps2025")  # Loads 2025 GeoJSON
   obec_mapping = load_obec_mapping("ps2025")  # Loads OBEC mapping
   ```

4. **Filter GeoJSON for Electoral District**
   - Extract OBEC codes from polling stations (e.g., "500054", "500046", ...)
   - Map OBEC codes to `kod_obec` (e.g., "554782", "500046", ...)
   - Filter GeoJSON features where `properties.kod_obec` matches
   - Result: ~1,119 polling station boundaries for district 1

5. **Display Map**
   - Uses `display_geographic_analysis()` with filtered GeoJSON
   - Matches `district_data.district_code` (station_number like "1001") to `geojson.properties.cislo`
   - Shows turnout, vote counts, and party results at polling station level

### Code Mapping Example (Praha 1)

| PS2025 Data | Mapping File | 2025 GeoJSON | Polling Stations |
|-------------|--------------|--------------|------------------|
| `OBEC="500054"` | → `kod_obec_geojson="554782"` | `properties.kod_obec="554782"` | 21 polling stations |
| `OKRSEK="1001"` | - | `properties.cislo=1001` | Praha 1, okrsek 1001 |
| `district_code="1100"` | Electoral district 1 | `properties.naz_mco="Praha 1"` | |

## 🎯 Key Features

### Parliamentary Elections Now Support:
- ✅ **Turnout Maps**: Color-coded by polling station turnout percentage
- ✅ **Vote Distribution**: Valid votes visualization
- ✅ **Party Results**: Party-specific vote maps
- ✅ **Dot Density Maps**: Visual representation of vote counts
- ✅ **Cartograms**: Area-proportional vote visualizations
- ✅ **Interactive Tooltips**: Click polling stations to see detailed data

### Map Visualization Types:
1. **Turnout**: Color intensity = turnout %
2. **Estimated Voters**: Based on registered voters
3. **Valid Votes**: Total valid votes per station
4. **Valid Votes (dots)**: Dot density representation
5. **Party Results**: Party-specific vote distribution

## 🔍 Verification

All data structures verified:
- ✅ `parliamentary_election_results.json` (10.4 MB)
- ✅ `district_index.json` (0.0 MB)
- ✅ `electoral_districts_boundaries_2025.geojson` (252.6 MB)
- ✅ `obec_to_geojson_mapping.json` (0.8 MB, 6,389 mappings)

Electoral District 1 (Praha):
- 25 party results
- 525 candidates
- 1,119 polling stations
- 100% mapping success rate

## 🚀 How to Use

### In Streamlit App:

1. **Select Parliamentary Election**
   - Sidebar: Election Selector → "Volby do Poslanecké sněmovny 2025"

2. **Choose Electoral District**
   - Sidebar: Electoral District Selection → e.g., "1 - Praha"

3. **Navigate to Geographic Analysis**
   - Tab selector → "Geographic Analysis"

4. **Explore Maps**
   - Choose visualization type (Turnout, Valid Votes, Party Results, etc.)
   - Select map type (Geographic Map, Cartogram, Dot Density)
   - Choose base map style (OpenStreetMap; the CartoDB styles appear only when
     `CARTO_BASEMAPS_KEY` is set to a key from https://carto.com/basemaps/apikey/)
   - For Party Results: Select specific party from dropdown

5. **Interact with Map**
   - Click on polling stations to see detailed data
   - Pan and zoom to explore specific areas
   - Use layer controls if available

### From Command Line:

```bash
# Run data collection (if not already done)
uv run python run_all_municipalities.py --election ps2025

# Start Streamlit app
uv run streamlit run streamlit_app.py
```

## 📝 Technical Details

### Functions Updated/Created:
1. `load_geojson_data(election_id)` - Election-aware GeoJSON loading
2. `load_obec_mapping(election_id)` - Load OBEC mapping for parliamentary
3. `get_district_code_from_geojson(properties)` - Handle cislo/CISLO compatibility
4. `load_municipality_data()` - Add polling_stations and district_data for parliamentary
5. Geographic Analysis tab filtering - OBEC-based filtering for parliamentary

### Data Conversion:
Parliamentary polling stations are converted to `district_data` format:
```python
{
    "district_code": station["station_number"],  # e.g., "1001"
    "registered_voters": station["registered_voters"],
    "returned_ballots": station["returned_ballots"],
    "valid_votes": station["valid_votes"],
    "turnout_percentage": station["turnout_percentage"]
}
```

## ✨ Result

Parliamentary elections (PS2025) now have **full parity** with municipal elections (KV2022) in terms of map visualization capabilities. Users can explore election results at the polling station level with interactive, color-coded maps.

---

**Implementation Date**: October 13, 2025
**Status**: ✅ Complete & Verified



# Multi-Election Support Migration Guide

This document explains the changes made to support multiple elections in the Czech Municipalities Electoral Analysis application.

## 🎯 What Changed

The application has been restructured to support multiple elections (2022, 2018, 2014, etc.) with a clear separation of data by election year.

### Key Changes

1. **New Directory Structure**: Data is now organized by election ID
   - Old: `input/raw/`, `output/`
   - New: `input/{election_id}/raw/`, `output/{election_id}/`

2. **Election Configuration System**: New `ElectionConfig` class manages election-specific settings
   - Centralized configuration for URLs, dates, and file paths
   - Easy to add new elections

3. **Updated Command-Line Tools**: Support for `--election` parameter
   - List available elections: `--list-elections`
   - Select specific election: `--election kv2022`

4. **Enhanced Streamlit App**: Election selector in sidebar
   - Switch between elections with a dropdown
   - Automatic data loading for selected election

5. **Migration Script**: Tool to move existing data to new structure
   - Automatic backup creation
   - Safe migration process
   - Dry-run mode for preview

## 📁 New File Structure

```
volebni-analyza/
├── input/
│   ├── kv2022/              # 2022 Elections
│   │   └── raw/
│   ├── kv2018/              # 2018 Elections
│   │   └── raw/
│   └── kv2014/              # 2014 Elections
│       └── raw/
├── output/
│   ├── kv2022/              # 2022 Results
│   │   ├── csv/
│   │   ├── processed/
│   │   ├── results/
│   │   ├── reports/
│   │   ├── visualizations/
│   │   └── detailed/
│   ├── kv2018/              # 2018 Results
│   └── kv2014/              # 2014 Results
└── src/
    ├── election_config.py   # NEW: Election configuration
    ├── municipality_registry.py  # Updated
    ├── all_municipalities_scraper.py  # Updated
    └── ...
```

## 🚀 Migration Steps

### For Existing Users

If you have existing data in the old structure, follow these steps:

1. **Backup Your Data** (Recommended)
   ```bash
   # Create manual backup if desired
   cp -r input input_backup_$(date +%Y%m%d)
   cp -r output output_backup_$(date +%Y%m%d)
   ```

2. **Run Migration Script**
   ```bash
   # Preview what will happen (dry run)
   python migrate_to_multi_election.py --dry-run
   
   # Perform migration (creates automatic backups)
   python migrate_to_multi_election.py --election-id kv2022
   ```

3. **Verify Migration**
   ```bash
   # Test with existing data
   python run_all_municipalities.py --election kv2022 --no-download
   ```

4. **Test Streamlit App**
   ```bash
   streamlit run streamlit_app.py
   ```

### For New Users

No migration needed! Just start using the new commands:

```bash
# List available elections
python run_all_municipalities.py --list-elections

# Collect data for specific election
python run_all_municipalities.py --election kv2022

# Launch Streamlit app
streamlit run streamlit_app.py
```

## 🔧 Updated API

### MunicipalityRegistry

**Old:**
```python
registry = MunicipalityRegistry(data_dir="output")
```

**New:**
```python
# Using election_id string
registry = MunicipalityRegistry(election_config="kv2022")

# Using ElectionConfig object
from election_config import get_election_config
config = get_election_config("kv2022")
registry = MunicipalityRegistry(election_config=config)
```

### AllMunicipalitiesScraper

**Old:**
```python
scraper = AllMunicipalitiesScraper(data_dir="output")
```

**New:**
```python
# Using election_id string
scraper = AllMunicipalitiesScraper(election_config="kv2022")

# Using ElectionConfig object
from election_config import get_election_config
config = get_election_config("kv2022")
scraper = AllMunicipalitiesScraper(election_config=config)
```

### Backwards Compatibility

The old API still works with deprecation warnings:

```python
# Still works, but shows warning
registry = MunicipalityRegistry(data_dir="output")
scraper = AllMunicipalitiesScraper(data_dir="output")
```

## 📊 Adding New Elections

To add support for a new election, update `src/election_config.py`:

```python
ELECTIONS = {
    # Existing elections...
    
    # Add new election
    "kv2010": ElectionConfig(
        election_id="kv2010",
        election_name="Komunální volby 2010",
        election_type="municipal",
        election_date="20101015",
        base_url="https://www.volby.cz/pls/kv2010",
        opendata_url="https://www.volby.cz/opendata/kv2010/xml",
    ),
}
```

Then collect data:

```bash
python run_all_municipalities.py --election kv2010
```

## 🎨 Streamlit App Changes

### Election Selector

A new election selector appears at the top of the sidebar:

```
⚙️ Settings
  🗳️ Select Election
    Election: [Komunální volby 2022 (2022)]
    📅 Komunální volby 2022
    📆 Date: 20220923
```

### Auto-Detection

The app automatically detects missing data for the selected election and offers to run data collection.

### Data Loading

All data loading functions now accept an `election_id` parameter:

```python
# Old
municipality_index, comprehensive_data = load_all_municipality_data()

# New
municipality_index, comprehensive_data = load_all_municipality_data("kv2022")
```

## 📝 Command-Line Changes

### Old Commands

```bash
# Old way (still works with kv2022 as default)
python run_all_municipalities.py
python run_all_municipalities.py --registry-only
python run_all_municipalities.py --no-download
```

### New Commands

```bash
# List available elections
python run_all_municipalities.py --list-elections

# Select specific election
python run_all_municipalities.py --election kv2022
python run_all_municipalities.py --election kv2018
python run_all_municipalities.py -e kv2014

# Combined with other options
python run_all_municipalities.py --election kv2022 --registry-only
python run_all_municipalities.py -e kv2018 --no-download
```

## 🐛 Troubleshooting

### Issue: Migration script can't find data

**Solution**: Make sure you're running the script from the project root directory.

```bash
cd /path/to/volebni-analyza
python migrate_to_multi_election.py --dry-run
```

### Issue: Streamlit app shows "Data not found"

**Solution**: Make sure you've collected data for the selected election:

```bash
python run_all_municipalities.py --election kv2022
```

### Issue: Import errors in custom scripts

**Solution**: Update imports to use the new election config:

```python
# Add at top of your script
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / "src"))

from election_config import get_election_config

# Use in your code
config = get_election_config("kv2022")
```

## 📚 Further Reading

- See `DATA_STRUCTURE.md` for detailed file structure documentation
- See `README.md` for updated usage examples
- See `src/election_config.py` for available elections and configuration

## ✅ Checklist for Migration

- [ ] Backup existing data (if any)
- [ ] Run migration script with `--dry-run`
- [ ] Run actual migration
- [ ] Test data loading with `--no-download`
- [ ] Test Streamlit app
- [ ] Update any custom scripts to use new API
- [ ] Delete backup directories after confirming everything works

## 🎉 Benefits

1. **Multiple Elections**: Analyze multiple years of electoral data side by side
2. **Clean Organization**: Each election has its own directory structure
3. **Easy Comparison**: Compare results across different years
4. **Flexible**: Easy to add support for new elections
5. **Backwards Compatible**: Old code still works with deprecation warnings
6. **Safe Migration**: Automatic backups prevent data loss

## 💬 Questions?

For questions or issues, please refer to:
- Main README.md for general usage
- DATA_STRUCTURE.md for detailed structure information
- Source code comments for implementation details


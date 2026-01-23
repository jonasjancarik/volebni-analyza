# Parliamentary Elections Support

## 🎯 Status: Data Available - Core Parsing Implemented

**Election**: Volby do Poslanecké sněmovny 2025 (Parliamentary Elections 2025)  
**Date**: October 5, 2025  
**Data Source**: [ČSÚ OpenData](https://www.volby.cz/opendata/ps2025/ps2025_opendata.htm)  
**Status**: ✅ Complete election results available

## 📊 Quick Overview

The 2025 parliamentary elections have **full XML opendata support** with complete results:
- ✅ Candidate registry (psrk.xml)
- ✅ Party/coalition list (psrkl.xml)
- ✅ Polling station results (pst4.xml)
- ✅ Detailed party results (pst4p.xml)
- ✅ Multiple formats (XML, Excel, CSV, JSON)

**For detailed technical analysis, see:** [PS2025_DATA_ANALYSIS.md](PS2025_DATA_ANALYSIS.md)

## 🚀 Current Implementation Status

### ✅ Completed
- Multi-election infrastructure (supports multiple election types)
- PS2025 configuration added to `election_config.py`
- Data structure fully analyzed and documented
- Sample data downloaded and verified
- Election date and file names confirmed
- ParliamentaryScraper parses psrkl.xml, psrk.xml, pscoco.xml, pst4.xml, pst4p.xml
- Party votes aggregated by electoral district + polling station

### 🔄 Next Steps (Implementation)

**1. Preferential vote analysis (HLASY_01..XX)**
- Parse candidate-level preference counts from pst4p.xml
- Add per-candidate and per-party preference stats

**2. Seat allocation**
- Implement D'Hondt seat allocation at national level
- Expose mandates by party + district

**3. Streamlit enhancements**
- Preferential vote visualization
- District vs national seat breakdowns

## 🔑 Key Differences from Municipal Elections

| Aspect | Municipal | Parliamentary |
|--------|-----------|---------------|
| **Geographic Units** | 6,377 municipalities | 14 electoral districts |
| **Namespace** | `http://www.volby.cz/kv/` | `http://www.volby.cz/ps/` |
| **Encoding** | UTF-8 | windows-1250 |
| **Registry Files** | kvcoco.xml, kvros.xml | psrk.xml, psrkl.xml |
| **Results Files** | vysledky_okrsky_*.xml | pst4.xml, pst4p.xml |
| **Batch Processing** | Yes (~200 batches) | No (single large files) |
| **Special Features** | - | Preferential votes, seat allocation |

## 📁 Data Files Structure

```
input/ps2025/raw/
  ├── psrk.xml           # Candidate registry (2.3MB)
  ├── psrkl.xml          # Party list (15KB)
  └── pst4.xml           # Polling stations (7.3MB)

output/ps2025/
  ├── processed/         # Intermediate data
  ├── results/           # Final analysis
  ├── csv/               # CSV exports
  └── reports/           # Generated reports
```

## 🗺️ Electoral Districts (14 Kraje)

1. Praha
2. Středočeský
3. Jihočeský
4. Plzeňský
5. Karlovarský
6. Ústecký
7. Liberecký
8. Královéhradecký
9. Pardubický
10. Vysočina
11. Jihomoravský
12. Olomoucký
13. Zlínský
14. Moravskoslezský

## 💡 Implementation Notes

### Code Reusability
- **80% of municipal scraper code is reusable**
- Main differences: XML namespace and element names
- Inherit from `AllMunicipalitiesScraper` and override specific methods

### Encoding Handling
```python
# Municipal: UTF-8 (default)
tree = ET.parse(xml_file)

# Parliamentary: windows-1250
with open(xml_file, 'r', encoding='windows-1250') as f:
    tree = ET.parse(f)
```

### XML Namespace
```python
# Municipal
ns = {"kv": "http://www.volby.cz/kv/"}
root.findall("kv:OKRSEK", ns)

# Parliamentary
ns = {"ps": "http://www.volby.cz/ps/"}
root.findall("ps:PS_T4_ROW", ns)
```

## 📋 Testing Checklist

- [ ] Download complete ps2025 data files
- [ ] Parse psrkl.xml successfully
- [ ] Parse psrk.xml successfully
- [ ] Parse pst4.xml successfully
- [ ] Aggregate results by district
- [ ] Calculate national seat allocation
- [ ] Generate results in output/ps2025/
- [ ] Display in Streamlit
- [ ] Compare with municipal elections in UI

## 🔗 Related Documentation

- [PS2025_DATA_ANALYSIS.md](PS2025_DATA_ANALYSIS.md) - Complete technical analysis
- [MULTI_ELECTION_MIGRATION.md](MULTI_ELECTION_MIGRATION.md) - Multi-election infrastructure guide
- [DATA_STRUCTURE.md](DATA_STRUCTURE.md) - Overall data organization

## 📚 Resources

- [ČSÚ OpenData PS2025](https://www.volby.cz/opendata/ps2025/ps2025_opendata.htm)
- [PS2025 Web Interface](https://www.volby.cz/pls/ps2025/)
- Sample data: `research/ps2025/`

---

**Last Updated**: 2025-10-08  
**Status**: Configuration complete, implementation ready to begin  
**Priority**: Medium (infrastructure complete, implementation when needed)

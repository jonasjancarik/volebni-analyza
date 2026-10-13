# Open data of the 2025 parliamentary election

Notes on the files ČSÚ publishes for the 2025 election to the Chamber of Deputies, which `src/parliamentary_scraper.py` and
`src/parliamentary_parsers.py` read. Source:
<https://www.volby.cz/opendata/ps2025/ps2025_opendata.htm>

## 📊 Data Files Available

### Registry Files (`PS2025reg20251005_xml.zip`)

#### 1. **psrk.xml** (2.3MB) - Candidate Registry
**Purpose**: Complete list of all candidates across all electoral districts  
**Root Element**: `<PS_REGKAND>`  
**Row Element**: `<PS_REGKAND_ROW>`

**Key Fields**:
```xml
<VOLKRAJ>1</VOLKRAJ>              <!-- Electoral district (1-14) -->
<KSTRANA>1</KSTRANA>              <!-- Party code -->
<PORCISLO>1</PORCISLO>            <!-- Candidate number on list -->
<JMENO>FirstName</JMENO>          <!-- First name -->
<PRIJMENI>Surname</PRIJMENI>      <!-- Surname -->
<VEK>49</VEK>                     <!-- Age -->
<POVOLANI>Occupation</POVOLANI>   <!-- Occupation/description -->
<BYDLISTEN>Praha</BYDLISTEN>      <!-- Place of residence -->
<PSTRANA>1706</PSTRANA>           <!-- Party running under -->
<NSTRANA>1706</NSTRANA>           <!-- Nominating party -->
<PLATNOST>A</PLATNOST>            <!-- Validity (A=active) -->
<POCHLASU>70</POCHLASU>           <!-- Preferential votes received -->
<POCPROC>9.95</POCPROC>           <!-- Percentage of preferential votes -->
<MANDAT>N</MANDAT>                <!-- Mandate won (Y/N) -->
<PORADIMAND>0</PORADIMAND>        <!-- Ranking for mandate -->
<PORADINAHR>0</PORADINAHR>        <!-- Substitute ranking -->
```

**Namespace**: `http://www.volby.cz/ps/`  
**Encoding**: windows-1250

#### 2. **psrkl.xml** (15KB) - Party/Coalition List
**Purpose**: Registry of all parties and coalitions  
**Root Element**: `<PS_RKL>`  
**Row Element**: `<PS_RKL_ROW>`

**Key Fields**:
```xml
<KSTRANA>1</KSTRANA>              <!-- Party code -->
<VSTRANA>1706</VSTRANA>           <!-- Coalition/party ID -->
<NAZEVCELK>Full Name</NAZEVCELK>  <!-- Full party name -->
<NAZEV_STRK>Short</NAZEV_STRK>    <!-- Short name -->
<ZKRATKAK30>30char</ZKRATKAK30>   <!-- 30-char abbreviation -->
<ZKRATKAK8>8char</ZKRATKAK8>      <!-- 8-char abbreviation -->
<POCSTRVKO>1</POCSTRVKO>          <!-- Number of parties in coalition -->
<SLOZENI>1706</SLOZENI>           <!-- Composition -->
<STAVREG>00022202222220</STAVREG> <!-- Registration status by district -->
<PLAT_STR>A</PLAT_STR>            <!-- Validity -->
<POCMANDCR>0</POCMANDCR>          <!-- Mandates won nationwide -->
<NAZEVPLNY>Full name</NAZEVPLNY>  <!-- Full descriptive name -->
```

#### 3. **psrkl_slozeni.xml** (3.6KB) - Coalition Composition
**Purpose**: Details of coalition member parties

### Electoral Data Files (`PS2025data20251005_xml.zip`)

#### 4. **pst4.xml** (7.3MB) - Polling Station Results
**Purpose**: Complete results from all polling stations  
**Root Element**: `<PS_T4>`  
**Row Element**: `<PS_T4_ROW>`

**Key Fields**:
```xml
<ID_OKRSKY>7</ID_OKRSKY>          <!-- Polling station ID -->
<TYP_FORM>1</TYP_FORM>            <!-- Form type -->
<OPRAVA>0</OPRAVA>                <!-- Correction flag -->
<CHYBA>0</CHYBA>                  <!-- Error flag -->
<OKRES>1100</OKRES>               <!-- District code (okres) -->
<OBEC>500054</OBEC>               <!-- Municipality code -->
<OKRSEK>1001</OKRSEK>             <!-- Polling station number -->
<KC_1>3</KC_1>                    <!-- Classification 1 -->
<KC_2>2576</KC_2>                 <!-- Classification 2 -->
<ZAKRSTRANA>000011...</ZAKRSTRANA> <!-- Bit string: which parties ran -->
<VOL_SEZNAM>751</VOL_SEZNAM>      <!-- Registered voters -->
<VYD_OBALKY>613</VYD_OBALKY>      <!-- Issued ballots -->
<DOR_OBALKY>0</DOR_OBALKY>        <!-- Delivered envelopes -->
<DOR_ODLOZ>0</DOR_ODLOZ>          <!-- Delayed deliveries -->
<ODEVZ_OBAL>611</ODEVZ_OBAL>      <!-- Returned ballots -->
<PL_HL_CELK>601</PL_HL_CELK>      <!-- Valid votes total -->
```

**Note**: `ZAKRSTRANA` is a bit string where each position represents a party (1=ran, 0=didn't run)

#### 5. **pst4p.xml** (227MB!) - Detailed Party Results by Polling Station
**Purpose**: Vote counts for each party at each polling station  
**Estimated**: Millions of rows (party × polling station combinations)

## 🗺️ Geographic Structure

### 14 Electoral Districts (Kraje)
1. VOLKRAJ=1: Praha
2. VOLKRAJ=2: Středočeský
3. VOLKRAJ=3: Jihočeský
4. VOLKRAJ=4: Plzeňský
5. VOLKRAJ=5: Karlovarský
6. VOLKRAJ=6: Ústecký
7. VOLKRAJ=7: Liberecký
8. VOLKRAJ=8: Královéhradecký
9. VOLKRAJ=9: Pardubický
10. VOLKRAJ=10: Vysočina
11. VOLKRAJ=11: Jihomoravský
12. VOLKRAJ=12: Olomoucký
13. VOLKRAJ=13: Zlínský
14. VOLKRAJ=14: Moravskoslezský

## 🔄 Comparison with Municipal Elections

| Aspect | Municipal (kv2022) | Parliamentary (ps2025) |
|--------|-------------------|------------------------|
| **Registry File** | `kvcoco.xml` | `psrk.xml` (candidates) + `psrkl.xml` (parties) |
| **Party Results** | `kvros.xml` | `pst4p.xml` |
| **Polling Stations** | `vysledky_okrsky_NNNNN.xml` | `pst4.xml` |
| **Root Element** | `<VYSLEDKY_OKRSKY>` | `<PS_T4>` |
| **Row Element** | `<OKRSEK>` | `<PS_T4_ROW>` |
| **Turnout Element** | `<UCAST_OKRSEK>` | Embedded in `<PS_T4_ROW>` |
| **Vote Element** | `<HLASY_OKRSEK>` | In separate `pst4p.xml` |
| **Namespace** | `http://www.volby.cz/kv/` | `http://www.volby.cz/ps/` |
| **Encoding** | UTF-8 | windows-1250 |
| **Geographic Unit** | Municipality (OBEC) | Electoral district (VOLKRAJ) |
| **Batch Processing** | Yes (~200 batches) | Single large files |

## 💡 Key Insights

### Similarities (Good News!)
- ✅ XML structure with XSD schemas
- ✅ Polling station level detail
- ✅ Similar field naming conventions
- ✅ Turnout statistics available
- ✅ Party identification via codes

### Differences (Need Adaptation)
- ❌ Different root/row element names
- ❌ Different namespace
- ❌ Windows-1250 encoding (not UTF-8)
- ❌ No batch processing (single large files)
- ❌ Party results in separate file
- ❌ Bit string for party participation

## 📁 Available Download Links

### Direct XML Files
- Candidate Registry: `/appdata/ps2025/odata/vysledky_kandid.xml`
- Overall Results: `/appdata/ps2025/odata/vysledky.xml`
- District Results: `/appdata/ps2025/odata/okresy/vysledky_okres_CZXXXX.xml`
- Regional Capitals: `/appdata/ps2025/odata/vysledky_krajmesta.xml`
- International: `/appdata/ps2025/odata/vysledky_zahranici.xml`

### ZIP Packages (Recommended)
```bash
# Registries
curl -O https://www.volby.cz/opendata/ps2025/PS2025reg20251005_xml.zip

# Electoral data
curl -O https://www.volby.cz/opendata/ps2025/PS2025data20251005_xml.zip

# Code lists
curl -O https://www.volby.cz/opendata/ps2025/PS2025ciselniky20251005_xml.zip
```

## 📊 Data Quality

- ✅ Complete data for all 14 electoral districts
- ✅ All candidates included with details
- ✅ Preferential votes recorded
- ✅ Mandate allocation included
- ✅ Polling station level detail
- ✅ Multiple format support (XML, Excel, CSV, JSON)

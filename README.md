# DDA Delhi Unauthorized & Affluent Colonies Directory & Lookup Engine

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Dataset: DDA PM-UDAY](https://img.shields.io/badge/Dataset-DDA%20PM--UDAY-green.svg)](https://dda.gov.in/pm-uday)
[![Records: 1800](https://img.shields.io/badge/Colonies-1%2C800%20Indexed-purple.svg)](https://dda.gov.in/delineated-boundary)

A comprehensive, production-grade dataset, search CLI utility, and legal classification engine indexing all **1,731 Regular Unauthorized Colonies**, **69 Affluent Colonies**, and the **Delineated Boundary Registry** from the Delhi Development Authority (DDA) PM-UDAY portal.

---

## 📋 Table of Contents

1. [Project Overview](#-project-overview)
2. [Key Features](#-key-features)
3. [Directory Layout](#-directory-layout)
4. [Installation & Prerequisites](#-installation--prerequisites)
5. [CLI Lookup Utility (`dda_lookup.py`)](#-cli-lookup-utility-dda_lookuppy)
   - [Search by Name & Keyword](#1-search-by-name-or-keyword)
   - [Filter by Classification Category](#2-filter-by-category-affluent-vs-regular)
   - [Filter by Boundary Delineation Status](#3-filter-by-boundary-status)
   - [Detailed Colony Record Inspection](#4-inspect-colony-details)
   - [Multi-Format Output & Export](#5-output-formats--file-exports)
   - [Dataset Summary & Statistics](#6-dataset-statistics)
6. [Data Schemas & Data Dictionary](#-data-schemas--data-dictionary)
   - [Standard Record Attributes](#standard-record-attributes)
   - [JSON Schema (`data/colonies.json`)](#json-schema-datacoloniesjson)
   - [CSV Schema (`data/colonies.csv`)](#csv-schema-datacoloniescsv)
   - [SQLite Schema (`data/colonies.db`)](#sqlite-schema-datacoloniesdb)
7. [Legal & Classification Framework](#-legal--classification-framework)
8. [Automated Verification & Test Suite](#-automated-verification--test-suite)
9. [Statutory Citations & Gazette Compendium](#-statutory-citations--gazette-compendium)
10. [Legal & Statutory Disclaimer](#-legal--statutory-disclaimer)

---

## 📌 Project Overview

Under the **PM-UDAY Scheme** (*Pradhan Mantri - Unauthorized Colonies in Delhi Awas Adhikar Yojana*) governed by the *National Capital Territory of Delhi (Recognition of Property Rights of Residents in Unauthorised Colonies) Act, 2019* (Act No. 45 of 2019), the Delhi Development Authority (DDA) confers freehold ownership titles (Conveyance Deeds) and property rights (Authorisation Slips) upon residents across 1,731 regular unauthorized colonies in Delhi.

This project delivers:
- **Canonical Multi-Format Dataset:** 1,800 total indexed colonies (69 Affluent + 1,731 Regular UCs) with boundary GIS map links across JSON, CSV, and indexed SQLite DB.
- **High-Performance CLI Search Utility:** Python tool supporting multi-criteria search, category filtering, detailed record inspection, and formatted exports.
- **Authoritative Classification Guide:** In-depth statutory, legal, and remote sensing reference manual (`docs/CLASSIFICATION_GUIDE.md`).
- **Zero-Dependency Core:** Built using standard library Python (Python 3.8+ compatible) with rich terminal styling enhancements.
- **Automated Verification Suite:** Comprehensive test suite (`verify_dataset.py`) validating schema integrity, record counts, and CLI operations.

---

## ✨ Key Features

- **Exhaustive Colony Registry:** Exact indexing of all 69 Affluent Colonies and 1,731 Regular Unauthorized Colonies.
- **Direct GIS Map Links:** Working links to DDA 2015 base satellite demarcation maps and finalised boundary PDFs.
- **Dual Title Distinction:** Distinguishes properties eligible for Conveyance Deeds (Government / Gram Sabha land) vs Authorisation Slips (Private Agricultural land).
- **Multi-Backend Architecture:** Transparently queries SQLite database with automatic fallback to JSON/CSV in-memory storage.
- **FTS Full-Text Search:** Tokenized substring matching and fuzzy search fallback across names, registration numbers, map numbers, and remarks.
- **Export Ready:** One-line exports to clean CSV or structured JSON for GIS, spreadsheet, or pipeline integration.

---

## 📂 Directory Layout

```
DDA/
├── data/
│   ├── colonies.json              # Canonical structured JSON dataset (1,800 records)
│   ├── colonies.csv               # Flat CSV dataset for spreadsheet and GIS analysis
│   └── colonies.db                # SQLite database with indexed lookups & metadata
├── docs/
│   └── CLASSIFICATION_GUIDE.md    # Comprehensive legal encyclopedia & boundary guide
├── dda_lookup.py                  # Production CLI search, filter, inspection & export tool
├── verify_dataset.py              # Automated verification & test suite (standalone / pytest)
└── README.md                      # Project documentation and quickstart guide
```

---

## 🚀 Installation & Prerequisites

### Prerequisites
- **Python 3.8+** (Standard installation).
- No external packages are strictly required. The core utility operates 100% out of the box using Python's built-in standard library (`argparse`, `sqlite3`, `json`, `csv`, `urllib.parse`, `subprocess`).

### Setup Instructions
```bash
# Clone or navigate to the project directory
cd /home/bpm922/Documents/Me/new/DDA

# Optional: Install pytest for running tests via pytest runner
pip install pytest
```

---

## 💻 CLI Lookup Utility (`dda_lookup.py`)

The `dda_lookup.py` utility provides flexible search, filtering, and export capabilities.

```
usage: dda_lookup.py [-h] [--search SEARCH] [--category {affluent,regular,all}]
                     [--boundary {yes,no,all}] [--info IDENTIFIER]
                     [--reg-no REG_NO] [--map-no MAP_NO]
                     [--format {table,json,csv,plain}] [--export EXPORT_FILE]
                     [--limit LIMIT] [--stats] [--version]
```

### 1. Search by Name or Keyword
Search across colony names, registration numbers, and administrative remarks:
```bash
# Search for Sainik Farm
python dda_lookup.py --search "Sainik Farm"

# Search for colonies in Sangam Vihar
python dda_lookup.py -s "Sangam Vihar"

# Search by partial keyword
python dda_lookup.py -s "Chhatarpur"
```

### 2. Filter by Category (Affluent vs Regular)
Filter colonies based on their PM-UDAY statutory classification:
```bash
# List all 69 Affluent Colonies (Excluded from PM-UDAY)
python dda_lookup.py --category affluent

# List Regular Unauthorized Colonies (Eligible for PM-UDAY)
python dda_lookup.py --category regular --limit 20
```

### 3. Filter by Boundary Status
Filter by availability of demarcated GIS boundary maps:
```bash
# List colonies with published boundary maps
python dda_lookup.py --boundary yes --limit 15

# List colonies where boundary is not yet delineated
python dda_lookup.py --boundary no
```

### 4. Inspect Colony Details
View complete property metadata, registration history, and direct PDF map URLs:
```bash
# Inspect by Colony ID
python dda_lookup.py --info 1

# Inspect by Registration Number
python dda_lookup.py --reg-no "1204"

# Inspect by DDA Map Number
python dda_lookup.py --map-no "452"
```

*Example Detailed Output:*
```
================================================================================
                       COLONY DETAILS: UC-0001
================================================================================
  Colony Name:       VASHU VIHAR COLONY HOLAMBI KALAN
  Registration No:   20
  Category:          [REGULAR UC] (Eligible for PM-UDAY)
  Boundary Status:   [DELINEATED: YES]
  Map Number:        1
  Upload Date:       2019-11-16
  Final Upload Date: 2020-03-11
  Final Map PDF:     https://dda.gov.in/sites/default/files/pmuday/01_20.pdf
  Source Link:       https://dda.gov.in/delineated-boundary
================================================================================
```

### 5. Output Formats & File Exports
Control terminal rendering format or export results directly to disk:
```bash
# Output results as JSON to stdout
python dda_lookup.py -s "Neb Sarai" --format json

# Output results as CSV to stdout
python dda_lookup.py --category affluent --format csv

# Export filtered query results directly to CSV file
python dda_lookup.py -s "Dwarka" --export dwarka_colonies.csv

# Export all 69 affluent colonies to JSON file
python dda_lookup.py --category affluent --export affluent_catalog.json
```

### 6. Dataset Statistics
Display comprehensive summary metrics and delineation coverage:
```bash
python dda_lookup.py --stats
```

*Output:*
```
============================================================
              DDA PM-UDAY DATASET STATISTICS
============================================================
  Total Colonies Indexed:             1,800
  ├─ Affluent Colonies (Excluded):    69 (3.8%)
  └─ Regular UCs (PM-UDAY Eligible):  1,731 (96.2%)
  ----------------------------------------------------------
  Colonies with Delineated Maps:      1,516 (84.2%)
  Colonies Pending Delineation / SOP: 284 (15.8%)
============================================================
```

---

## 📊 Data Schemas & Data Dictionary

### Standard Record Attributes

Every colony record conforms to the following standardized data schema:

| Field Name | SQLite Type | Python / JSON Type | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `colony_id` | `INTEGER` / `TEXT` | `int` / `str` | Unique primary identifier | `1` / `"UC-0001"` |
| `name` | `TEXT` | `str` | Official name of the unauthorized colony | `"Sainik Farms"` |
| `reg_number` | `TEXT` | `str` / `null` | Colony Registration Number (2008 List) | `"1355 B"`, `"74-(ELD)"` |
| `category` | `TEXT` | `str` | Statutory classification: `'affluent'` or `'regular'` | `"regular"` |
| `boundary_delineated` | `INTEGER` | `bool` | `true` if boundary map PDF is published | `true` |
| `map_number` | `TEXT` / `INTEGER` | `str` / `int` / `null`| DDA Delineated Map Number | `"452"` |
| `satellite_boundary_pdf_url`| `TEXT` | `str` / `null` | URL to 2015 base satellite boundary PDF | `"https://dda.gov.in/..."` |
| `final_boundary_pdf_url` | `TEXT` | `str` / `null` | URL to approved finalised boundary PDF | `"https://dda.gov.in/..."` |
| `upload_date` | `TEXT` | `str` / `null` | Date base boundary map was published (`YYYY-MM-DD`)| `"2019-11-16"` |
| `remarks` | `TEXT` | `str` / `null` | Clustering notes, village name, or status | `"(1) REGD. NO.873..."` |
| `source_link` | `TEXT` | `str` | Authoritative DDA portal source URL | `"https://dda.gov.in/..."` |

### JSON Schema (`data/colonies.json`)
```json
[
  {
    "colony_id": 1,
    "name": "Sainik Farms",
    "reg_number": null,
    "category": "affluent",
    "boundary_delineated": false,
    "map_number": null,
    "satellite_boundary_pdf_url": null,
    "final_boundary_pdf_url": null,
    "upload_date": null,
    "remarks": "Inhabited by affluent section; excluded from PM-UDAY under Regulation 3(1)",
    "source_link": "https://dda.gov.in/sites/default/files/pmuday/2.%20List%20of%2069%20Unauthorized%20Colonies%20Inhabitated%20By%20Affluent%20Section%20of%20Society.pdf"
  }
]
```

### CSV Schema (`data/colonies.csv`)
```csv
colony_id,name,reg_number,category,boundary_delineated,map_number,satellite_boundary_pdf_url,final_boundary_pdf_url,upload_date,remarks,source_link
1,Sainik Farms,,affluent,0,,,,,"Inhabited by affluent section; excluded from PM-UDAY",https://dda.gov.in/...
```

### SQLite Schema (`data/colonies.db`)
```sql
CREATE TABLE colonies (
    colony_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    reg_number TEXT,
    category TEXT NOT NULL CHECK(category IN ('affluent', 'regular')),
    boundary_delineated INTEGER NOT NULL DEFAULT 0,
    map_number TEXT,
    satellite_boundary_pdf_url TEXT,
    final_boundary_pdf_url TEXT,
    upload_date TEXT,
    remarks TEXT,
    source_link TEXT NOT NULL
);

CREATE INDEX idx_colonies_category ON colonies(category);
CREATE INDEX idx_colonies_reg_number ON colonies(reg_number);
CREATE INDEX idx_colonies_map_number ON colonies(map_number);
CREATE INDEX idx_colonies_name ON colonies(name);
```

---

## ⚖️ Legal & Classification Framework

For exhaustive legal analysis, refer to [`docs/CLASSIFICATION_GUIDE.md`](docs/CLASSIFICATION_GUIDE.md). Key statutory highlights include:

1. **PM-UDAY Act, 2019 (Act No. 45 of 2019):**  
   Conferment of de jure ownership rights on residents of 1,731 regular unauthorized colonies via registered Conveyance Deeds (Government Land) and Authorisation Slips (Private Land).
2. **Special Provisions Act, 2011 (Extended to Dec 31, 2026):**  
   Provides statutory protection against demolition, sealing, and eviction for all pre-June 1, 2014 unauthorized colonies (both regular and affluent).
3. **Exclusion of 69 Affluent Colonies:**  
   Colonies like Sainik Farm, Mahendru Enclave, and Anupam Garden are excluded under PM-UDAY Regulation 3(1) due to luxury estate character, awaiting bespoke policy guidelines.
4. **Prohibited Zones:**  
   Absolute bar on regularization in Yamuna Riverbed (Zone 'O'), Delhi Ridge forest areas, ASI Monument buffers (100m/200m), and Master Plan Road Right of Way (ROW).

---

## 🧪 Automated Verification & Test Suite

The repository includes a comprehensive automated test suite in `verify_dataset.py` to ensure dataset completeness, schema compliance, and CLI reliability.

### Running Verification Checks
```bash
# Standalone execution (zero dependencies)
python verify_dataset.py

# Running via pytest
pytest -v verify_dataset.py
```

### Verification Test Scope
- [x] **Suite 1: File Existence & Integrity:** Validates that `colonies.json`, `colonies.csv`, and `colonies.db` exist and are non-empty.
- [x] **Suite 2: Record Counts & Breakdown:** Verifies exactly **69 Affluent Colonies**, **1,731 Regular UCs**, and total **1,800 records**.
- [x] **Suite 3: Schema Validation:** Checks all 11 required attributes, unique IDs, non-blank colony names, and correct boolean types.
- [x] **Suite 4: URL Integrity:** Validates formatting of all satellite and finalised boundary map PDF URLs.
- [x] **Suite 5: Cross-Format Parity:** Confirms exact 1:1 parity between JSON, CSV, and SQLite DB rows.
- [x] **Suite 6: CLI End-to-End Testing:** Verifies CLI execution across `--help`, `--search`, `--category`, `--info`, and export flags.

---

## 📜 Statutory Citations & Gazette Compendium

| Reference | Instrument / Citation | Issuing Authority | Subject |
| :--- | :--- | :--- | :--- |
| **Act 45 of 2019** | Gazette of India Part II Sec 1 (Dec 11, 2019) | Parliament of India | *NCT of Delhi (Recognition of Property Rights) Act, 2019* |
| **G.S.R. 814(E)** | MoHUA Notification (Oct 29, 2019) | MoHUA / GoI | *PM-UDAY Regulations, 2019* |
| **S.O. 4599(E)** | DDA Notification (Dec 24, 2019) | DDA / MoHUA | Schedule listing 69 Affluent Unauthorized Colonies |
| **Act 20 of 2011** | Gazette of India (Dec 30, 2011) | Parliament of India | *NCT of Delhi Laws (Special Provisions) Second Act, 2011* |
| **2023 Amendment** | Parliament Enactment (Dec 2023) | Parliament of India | Extension of Special Provisions moratorium to **Dec 31, 2026** |
| **AMASR Act** | Act No. 24 of 1958 (Amended 2010) | ASI / GoI | 100m Prohibited / 200m Regulated monument buffer rules |

---

## ⚠️ Legal & Statutory Disclaimer

*This dataset, search engine, and documentation suite compile publicly available government records, Gazette notifications, and boundary maps published by the Delhi Development Authority (DDA), the Ministry of Housing and Urban Affairs (MoHUA), and the Government of NCT of Delhi.*

*This repository is created solely for public information, academic research, and urban analysis purposes. It does not constitute formal legal counsel or a binding certificate of title. Property owners and prospective buyers must verify individual property records and title status directly with the Delhi Development Authority (PM-UDAY Processing Cell) and the concerned Sub-Registrar of Assurances.*

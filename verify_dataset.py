#!/usr/bin/env python3
"""
verify_dataset.py — Comprehensive Automated Verification Suite for DDA Delhi Colonies Dataset.

This module provides a 6-tier automated test and quality assurance suite validating:
  - Tier 1: File Existence & Storage Integrity (JSON, CSV, SQLite DB > 100KB, schema & indices)
  - Tier 2: Exact Record Counts & Statistical Distribution (69 affluent, 1731 regular, 1800 total, delineated > 1400)
  - Tier 3: Schema Conformance & Field Integrity (11 attributes, sequential unique IDs, non-blank names, data types)
  - Tier 4: URL Formats & DDA Domain Validity (HTTP/HTTPS, dda.gov.in domain, .pdf extensions, source links)
  - Tier 5: Cross-Format Parity (100% field-by-field and row-by-row match across JSON, CSV, and SQLite DB)
  - Tier 6: CLI End-to-End Functional Tests (dda_lookup.py options: help, category, search, info, boundary, export, stats, edge cases)

Dual-Execution Architecture:
  1. Standalone Execution: `python3 verify_dataset.py` (Zero-dependency, pretty-printed results, exit code 0/1)
  2. Pytest Execution: `pytest -v verify_dataset.py` or `pytest -v` (Standard test runner discovery)
"""

import csv
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

# ==============================================================================
# PATH CONFIGURATION
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
JSON_PATH = DATA_DIR / "colonies.json"
CSV_PATH = DATA_DIR / "colonies.csv"
DB_PATH = DATA_DIR / "colonies.db"
CLI_PATH = BASE_DIR / "dda_lookup.py"

REQUIRED_FIELDS = [
    "colony_id",
    "name",
    "reg_number",
    "category",
    "boundary_delineated",
    "map_number",
    "satellite_boundary_pdf_url",
    "final_boundary_pdf_url",
    "upload_date",
    "remarks",
    "source_link",
]

# ==============================================================================
# DATA LOADING HELPERS
# ==============================================================================
def load_json_dataset(path=JSON_PATH):
    """Load and return JSON dataset."""
    assert path.exists(), f"JSON file missing: {path}"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_csv_dataset(path=CSV_PATH):
    """Load and return CSV dataset as list of dicts."""
    assert path.exists(), f"CSV file missing: {path}"
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_db_dataset(path=DB_PATH):
    """Load and return SQLite colonies rows as list of dicts."""
    assert path.exists(), f"SQLite DB missing: {path}"
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM colonies ORDER BY colony_id ASC")
        rows = [dict(r) for r in cur.fetchall()]
        return rows
    finally:
        conn.close()


def run_cli_command(args, timeout=15):
    """Execute dda_lookup.py via subprocess and return CompletedProcess."""
    assert CLI_PATH.exists(), f"CLI script missing: {CLI_PATH}"
    cmd = [sys.executable, str(CLI_PATH)] + list(args)
    res = subprocess.run(
        cmd,
        cwd=str(BASE_DIR),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return res


# ==============================================================================
# TIER 1: FILE EXISTENCE & STORAGE INTEGRITY
# ==============================================================================
def test_tier1_file_existence_and_sizes():
    """Verify that JSON, CSV, and SQLite DB files exist and each exceeds 100 KB."""
    min_size = 100 * 1024  # 100 KB
    
    assert JSON_PATH.exists(), f"colonies.json not found at {JSON_PATH}"
    assert JSON_PATH.is_file(), f"colonies.json is not a regular file: {JSON_PATH}"
    json_size = JSON_PATH.stat().st_size
    assert json_size > min_size, f"colonies.json size ({json_size} bytes) is below minimum 100KB"

    assert CSV_PATH.exists(), f"colonies.csv not found at {CSV_PATH}"
    assert CSV_PATH.is_file(), f"colonies.csv is not a regular file: {CSV_PATH}"
    csv_size = CSV_PATH.stat().st_size
    assert csv_size > min_size, f"colonies.csv size ({csv_size} bytes) is below minimum 100KB"

    assert DB_PATH.exists(), f"colonies.db not found at {DB_PATH}"
    assert DB_PATH.is_file(), f"colonies.db is not a regular file: {DB_PATH}"
    db_size = DB_PATH.stat().st_size
    assert db_size > min_size, f"colonies.db size ({db_size} bytes) is below minimum 100KB"


def test_tier1_sqlite_schema_and_tables():
    """Verify SQLite database connectivity, required tables, columns, and FTS5 search table."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view')")
        tables = {row[0] for row in cur.fetchall()}
        
        required_tables = {"colonies", "colonies_fts", "delineated_boundaries", "dataset_metadata"}
        missing_tables = required_tables - tables
        assert not missing_tables, f"SQLite DB missing required tables: {missing_tables}"

        # Verify colonies table columns
        cur.execute("PRAGMA table_info(colonies)")
        columns = {row[1] for row in cur.fetchall()}
        missing_cols = set(REQUIRED_FIELDS) - columns
        assert not missing_cols, f"Table 'colonies' missing required columns: {missing_cols}"
    finally:
        conn.close()


def test_tier1_sqlite_indices():
    """Verify SQLite database performance indices on colonies table."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indices = {row[0] for row in cur.fetchall()}
        
        expected_indices = {
            "idx_colonies_category",
            "idx_colonies_reg_number",
            "idx_colonies_map_number",
            "idx_colonies_boundary_delineated",
            "idx_colonies_name",
        }
        missing_indices = expected_indices - indices
        assert not missing_indices, f"SQLite DB missing performance indices: {missing_indices}"
    finally:
        conn.close()


# ==============================================================================
# TIER 2: EXACT RECORD COUNTS & STATISTICAL DISTRIBUTION
# ==============================================================================
def test_tier2_total_record_counts():
    """Verify exactly 1,800 total colonies in JSON, CSV, and SQLite DB."""
    json_data = load_json_dataset()
    csv_data = load_csv_dataset()
    db_data = load_db_dataset()

    assert len(json_data) == 1800, f"Expected exactly 1,800 JSON records, got {len(json_data)}"
    assert len(csv_data) == 1800, f"Expected exactly 1,800 CSV rows, got {len(csv_data)}"
    assert len(db_data) == 1800, f"Expected exactly 1,800 DB rows, got {len(db_data)}"


def test_tier2_affluent_regular_breakdown():
    """Verify exactly 69 Affluent colonies and 1,731 Regular UCs across all 3 formats."""
    json_data = load_json_dataset()
    csv_data = load_csv_dataset()
    db_data = load_db_dataset()

    # JSON checks
    aff_json = [r for r in json_data if r["category"] == "affluent"]
    reg_json = [r for r in json_data if r["category"] == "regular"]
    assert len(aff_json) == 69, f"JSON: Expected exactly 69 affluent colonies, got {len(aff_json)}"
    assert len(reg_json) == 1731, f"JSON: Expected exactly 1,731 regular colonies, got {len(reg_json)}"

    # CSV checks
    aff_csv = [r for r in csv_data if r["category"] == "affluent"]
    reg_csv = [r for r in csv_data if r["category"] == "regular"]
    assert len(aff_csv) == 69, f"CSV: Expected exactly 69 affluent colonies, got {len(aff_csv)}"
    assert len(reg_csv) == 1731, f"CSV: Expected exactly 1,731 regular colonies, got {len(reg_csv)}"

    # DB checks
    aff_db = [r for r in db_data if r["category"] == "affluent"]
    reg_db = [r for r in db_data if r["category"] == "regular"]
    assert len(aff_db) == 69, f"DB: Expected exactly 69 affluent colonies, got {len(aff_db)}"
    assert len(reg_db) == 1731, f"DB: Expected exactly 1,731 regular colonies, got {len(reg_db)}"


def test_tier2_boundary_delineation_counts():
    """Verify delineated boundary colonies > 1,400 (specifically 1,500) and undelineated = 300."""
    json_data = load_json_dataset()
    csv_data = load_csv_dataset()
    db_data = load_db_dataset()

    delin_json = [r for r in json_data if r["boundary_delineated"] is True]
    undelin_json = [r for r in json_data if r["boundary_delineated"] is False]
    assert len(delin_json) > 1400, f"JSON: Expected > 1400 delineated colonies, got {len(delin_json)}"
    assert len(delin_json) == 1500, f"JSON: Expected exactly 1,500 delineated colonies, got {len(delin_json)}"
    assert len(undelin_json) == 300, f"JSON: Expected exactly 300 undelineated colonies, got {len(undelin_json)}"

    delin_csv = [r for r in csv_data if r["boundary_delineated"] in ("1", "True", True)]
    assert len(delin_csv) == 1500, f"CSV: Expected exactly 1,500 delineated colonies, got {len(delin_csv)}"

    delin_db = [r for r in db_data if r["boundary_delineated"] == 1]
    assert len(delin_db) == 1500, f"DB: Expected exactly 1,500 delineated colonies, got {len(delin_db)}"


# ==============================================================================
# TIER 3: SCHEMA CONFORMANCE & FIELD INTEGRITY
# ==============================================================================
def test_tier3_schema_attribute_completeness():
    """Verify all 11 attributes are present in every record across all formats."""
    json_data = load_json_dataset()
    for idx, r in enumerate(json_data):
        missing = set(REQUIRED_FIELDS) - set(r.keys())
        assert not missing, f"JSON record {idx} (ID: {r.get('colony_id')}) missing attributes: {missing}"

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        assert header == REQUIRED_FIELDS, f"CSV header mismatch. Expected {REQUIRED_FIELDS}, got {header}"


def test_tier3_sequential_colony_ids():
    """Verify unique, sequential colony_id from 1 to 1800 with no gaps or duplicates."""
    json_data = load_json_dataset()
    ids = [r["colony_id"] for r in json_data]

    assert len(ids) == 1800, f"Expected 1,800 IDs, got {len(ids)}"
    assert len(set(ids)) == 1800, "Duplicate colony_ids detected in JSON dataset"
    assert ids == list(range(1, 1801)), "colony_ids are not contiguous sequential integers from 1 to 1800"

    # Verify ID range distribution: 1..69 are affluent, 70..1800 are regular
    for r in json_data:
        cid = r["colony_id"]
        if 1 <= cid <= 69:
            assert r["category"] == "affluent", f"Colony ID {cid} expected 'affluent', got '{r['category']}'"
        else:
            assert r["category"] == "regular", f"Colony ID {cid} expected 'regular', got '{r['category']}'"


def test_tier3_colony_names_integrity():
    """Verify all colony names are non-null, non-blank strings with length > 0."""
    json_data = load_json_dataset()
    for r in json_data:
        name = r.get("name")
        assert isinstance(name, str), f"Colony ID {r['colony_id']} name is not a string: {type(name)}"
        assert len(name.strip()) > 0, f"Colony ID {r['colony_id']} has empty/blank name"


def test_tier3_category_field_validity():
    """Verify category field is strictly 'affluent' or 'regular'."""
    json_data = load_json_dataset()
    valid_cats = {"affluent", "regular"}
    for r in json_data:
        cat = r.get("category")
        assert cat in valid_cats, f"Colony ID {r['colony_id']} invalid category: '{cat}'"


def test_tier3_boundary_delineated_typing():
    """Verify boundary_delineated typing and PM-UDAY statutory exclusion consistency."""
    json_data = load_json_dataset()
    for r in json_data:
        bd = r.get("boundary_delineated")
        assert isinstance(bd, bool), f"Colony ID {r['colony_id']} boundary_delineated is not boolean: {type(bd)}"
        
        # All 69 affluent colonies must be boundary_delineated == False
        if r["category"] == "affluent":
            assert bd is False, f"Affluent colony ID {r['colony_id']} must have boundary_delineated=False"
            assert "excluded from PM-UDAY" in (r.get("remarks") or ""), (
                f"Affluent colony ID {r['colony_id']} missing statutory PM-UDAY exclusion remark"
            )

        # Delineated regular colonies must have linked PDF URL or map number
        if bd is True:
            has_pdf = bool(r.get("satellite_boundary_pdf_url") or r.get("final_boundary_pdf_url"))
            has_map = bool(r.get("map_number"))
            assert has_pdf or has_map, f"Delineated colony ID {r['colony_id']} has no map number or PDF URL"


def test_tier3_upload_dates_format():
    """Verify non-null upload dates conform to ISO YYYY-MM-DD format."""
    json_data = load_json_dataset()
    date_regex = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    for r in json_data:
        dt = r.get("upload_date")
        if dt is not None and str(dt).strip() != "":
            assert date_regex.match(str(dt)), f"Colony ID {r['colony_id']} invalid upload_date format: '{dt}'"


# ==============================================================================
# TIER 4: URL FORMATS & DDA DOMAIN VALIDITY
# ==============================================================================
def test_tier4_url_scheme_and_domain_validity():
    """Verify all non-empty URLs use HTTP/HTTPS and point to official DDA domain (dda.gov.in)."""
    json_data = load_json_dataset()
    url_fields = ["satellite_boundary_pdf_url", "final_boundary_pdf_url", "source_link"]

    for r in json_data:
        cid = r["colony_id"]
        for fld in url_fields:
            url_val = r.get(fld)
            if url_val:
                parsed = urlparse(url_val)
                assert parsed.scheme in ("http", "https"), (
                    f"Colony ID {cid} field '{fld}' invalid scheme: '{parsed.scheme}' in URL '{url_val}'"
                )
                assert "dda.gov.in" in parsed.netloc.lower(), (
                    f"Colony ID {cid} field '{fld}' non-DDA domain: '{parsed.netloc}' in URL '{url_val}'"
                )


def test_tier4_pdf_urls_file_extension():
    """Verify that all non-empty boundary PDF links end with .pdf extension."""
    json_data = load_json_dataset()
    pdf_fields = ["satellite_boundary_pdf_url", "final_boundary_pdf_url"]

    for r in json_data:
        cid = r["colony_id"]
        for fld in pdf_fields:
            pdf_url = r.get(fld)
            if pdf_url:
                parsed = urlparse(pdf_url)
                assert parsed.path.lower().endswith(".pdf"), (
                    f"Colony ID {cid} field '{fld}' does not end with .pdf: '{pdf_url}'"
                )


def test_tier4_source_links_universality():
    """Verify that every colony record (all 1,800) has an official DDA source link."""
    json_data = load_json_dataset()
    for r in json_data:
        cid = r["colony_id"]
        source = r.get("source_link")
        assert source, f"Colony ID {cid} missing mandatory source_link"
        assert source.startswith("https://dda.gov.in"), f"Colony ID {cid} source_link invalid: '{source}'"


# ==============================================================================
# TIER 5: CROSS-FORMAT PARITY (JSON, CSV, SQLITE DB)
# ==============================================================================
def test_tier5_cross_format_parity_json_csv_db():
    """Verify 100% field-by-field and row-by-row equivalence between JSON, CSV, and SQLite DB."""
    json_data = load_json_dataset()
    csv_data = load_csv_dataset()
    db_data = load_db_dataset()

    assert len(json_data) == len(csv_data) == len(db_data) == 1800, (
        f"Row count mismatch: JSON={len(json_data)}, CSV={len(csv_data)}, DB={len(db_data)}"
    )

    for idx in range(1800):
        jr = json_data[idx]
        cr = csv_data[idx]
        dr = db_data[idx]
        cid = jr["colony_id"]

        # colony_id
        assert int(cr["colony_id"]) == cid == dr["colony_id"], f"Row {idx} colony_id mismatch"

        # name
        assert jr["name"] == cr["name"] == dr["name"], (
            f"Colony ID {cid} name mismatch: JSON='{jr['name']}', CSV='{cr['name']}', DB='{dr['name']}'"
        )

        # reg_number
        j_reg = "" if jr["reg_number"] is None else str(jr["reg_number"]).strip()
        c_reg = "" if cr["reg_number"] is None else str(cr["reg_number"]).strip()
        d_reg = "" if dr["reg_number"] is None else str(dr["reg_number"]).strip()
        assert j_reg == c_reg == d_reg, (
            f"Colony ID {cid} reg_number mismatch: JSON='{j_reg}', CSV='{c_reg}', DB='{d_reg}'"
        )

        # category
        assert jr["category"] == cr["category"] == dr["category"], f"Colony ID {cid} category mismatch"

        # boundary_delineated
        j_bd = bool(jr["boundary_delineated"])
        c_bd = cr["boundary_delineated"] in ("1", "True", True)
        d_bd = bool(dr["boundary_delineated"])
        assert j_bd == c_bd == d_bd, (
            f"Colony ID {cid} boundary_delineated mismatch: JSON={j_bd}, CSV={c_bd}, DB={d_bd}"
        )

        # map_number
        j_map = "" if jr["map_number"] is None else str(jr["map_number"]).strip()
        c_map = "" if cr["map_number"] is None else str(cr["map_number"]).strip()
        d_map = "" if dr["map_number"] is None else str(dr["map_number"]).strip()
        assert j_map == c_map == d_map, (
            f"Colony ID {cid} map_number mismatch: JSON='{j_map}', CSV='{c_map}', DB='{d_map}'"
        )

        # satellite_boundary_pdf_url
        j_sat = "" if jr["satellite_boundary_pdf_url"] is None else str(jr["satellite_boundary_pdf_url"]).strip()
        c_sat = "" if cr["satellite_boundary_pdf_url"] is None else str(cr["satellite_boundary_pdf_url"]).strip()
        d_sat = "" if dr["satellite_boundary_pdf_url"] is None else str(dr["satellite_boundary_pdf_url"]).strip()
        assert j_sat == c_sat == d_sat, f"Colony ID {cid} satellite_boundary_pdf_url mismatch"

        # final_boundary_pdf_url
        j_fin = "" if jr["final_boundary_pdf_url"] is None else str(jr["final_boundary_pdf_url"]).strip()
        c_fin = "" if cr["final_boundary_pdf_url"] is None else str(cr["final_boundary_pdf_url"]).strip()
        d_fin = "" if dr["final_boundary_pdf_url"] is None else str(dr["final_boundary_pdf_url"]).strip()
        assert j_fin == c_fin == d_fin, f"Colony ID {cid} final_boundary_pdf_url mismatch"

        # upload_date
        j_up = "" if jr["upload_date"] is None else str(jr["upload_date"]).strip()
        c_up = "" if cr["upload_date"] is None else str(cr["upload_date"]).strip()
        d_up = "" if dr["upload_date"] is None else str(dr["upload_date"]).strip()
        assert j_up == c_up == d_up, f"Colony ID {cid} upload_date mismatch"

        # remarks
        j_rem = "" if jr["remarks"] is None else str(jr["remarks"]).strip()
        c_rem = "" if cr["remarks"] is None else str(cr["remarks"]).strip()
        d_rem = "" if dr["remarks"] is None else str(dr["remarks"]).strip()
        assert j_rem == c_rem == d_rem, f"Colony ID {cid} remarks mismatch"

        # source_link
        j_src = "" if jr["source_link"] is None else str(jr["source_link"]).strip()
        c_src = "" if cr["source_link"] is None else str(cr["source_link"]).strip()
        d_src = "" if dr["source_link"] is None else str(dr["source_link"]).strip()
        assert j_src == c_src == d_src, f"Colony ID {cid} source_link mismatch"


# ==============================================================================
# TIER 6: CLI END-TO-END FUNCTIONAL TESTS
# ==============================================================================
def test_tier6_cli_help_option():
    """Verify dda_lookup.py --help and -h exit with code 0 and display usage instructions."""
    for flag in ["--help", "-h"]:
        res = run_cli_command([flag])
        assert res.returncode == 0, f"CLI {flag} exited with code {res.returncode}. Stderr: {res.stderr}"
        assert "usage:" in res.stdout.lower() or "dda_lookup" in res.stdout, f"CLI {flag} missing usage info"
        assert "--search" in res.stdout or "-s" in res.stdout, f"CLI {flag} missing --search option"
        assert "--category" in res.stdout or "-c" in res.stdout, f"CLI {flag} missing --category option"
        assert "--stats" in res.stdout, f"CLI {flag} missing --stats option"


def test_tier6_cli_category_affluent_filter():
    """Verify dda_lookup.py --category affluent returns exactly 69 items."""
    res = run_cli_command(["--category", "affluent", "--format", "json"])
    assert res.returncode == 0, f"CLI --category affluent failed with code {res.returncode}. Stderr: {res.stderr}"
    data = json.loads(res.stdout)
    assert len(data) == 69, f"Expected exactly 69 affluent colonies, got {len(data)}"
    assert all(r["category"] == "affluent" for r in data), "Non-affluent record returned in affluent filter"


def test_tier6_cli_category_regular_filter():
    """Verify dda_lookup.py --category regular returns exactly 1,731 items."""
    res = run_cli_command(["--category", "regular", "--format", "json"])
    assert res.returncode == 0, f"CLI --category regular failed with code {res.returncode}. Stderr: {res.stderr}"
    data = json.loads(res.stdout)
    assert len(data) == 1731, f"Expected exactly 1,731 regular colonies, got {len(data)}"
    assert all(r["category"] == "regular" for r in data), "Non-regular record returned in regular filter"


def test_tier6_cli_search_queries():
    """Verify dda_lookup.py --search for 'Sainik' and 'Sangam Vihar' returns matching records."""
    # Search Sainik
    res_sainik = run_cli_command(["--search", "Sainik", "--format", "json"])
    assert res_sainik.returncode == 0, f"Search 'Sainik' failed. Stderr: {res_sainik.stderr}"
    data_sainik = json.loads(res_sainik.stdout)
    assert len(data_sainik) >= 1, "Search 'Sainik' returned 0 results"
    assert any("Sainik" in r["name"] for r in data_sainik), "No record with 'Sainik' in name found"

    # Search Sangam Vihar
    res_sangam = run_cli_command(["--search", "Sangam Vihar", "--format", "json"])
    assert res_sangam.returncode == 0, f"Search 'Sangam Vihar' failed. Stderr: {res_sangam.stderr}"
    data_sangam = json.loads(res_sangam.stdout)
    assert len(data_sangam) >= 1, "Search 'Sangam Vihar' returned 0 results"
    assert any("Sangam" in r["name"] for r in data_sangam), "No record with 'Sangam' in name found"


def test_tier6_cli_info_details():
    """Verify dda_lookup.py --info 1 and --info 70 display formatted cards with PDF links and PM-UDAY status."""
    # Info for Colony 1 (Sainik Farms, Affluent)
    res1 = run_cli_command(["--info", "1"])
    assert res1.returncode == 0, f"CLI --info 1 failed. Stderr: {res1.stderr}"
    assert "Sainik Farms" in res1.stdout, f"'Sainik Farms' not found in --info 1 output: {res1.stdout}"
    assert "affluent" in res1.stdout.lower(), f"'affluent' not found in --info 1 output"
    assert "pm-uday" in res1.stdout.lower(), f"PM-UDAY status not found in --info 1 output"

    # Info for Colony 70 (Ladakh Budh Vihar, Regular, Delineated)
    res70 = run_cli_command(["--info", "70"])
    assert res70.returncode == 0, f"CLI --info 70 failed. Stderr: {res70.stderr}"
    assert "Ladakh Budh Vihar" in res70.stdout, f"'Ladakh Budh Vihar' not found in --info 70 output"
    assert "111_1.pdf" in res70.stdout or "dda.gov.in" in res70.stdout, "PDF link not found in --info 70 output"


def test_tier6_cli_boundary_filter():
    """Verify dda_lookup.py --boundary yes (1,500 items) and --boundary no (300 items)."""
    # Boundary yes
    res_yes = run_cli_command(["--boundary", "yes", "--format", "json"])
    assert res_yes.returncode == 0, f"CLI --boundary yes failed. Stderr: {res_yes.stderr}"
    data_yes = json.loads(res_yes.stdout)
    assert len(data_yes) == 1500, f"Expected 1,500 delineated colonies, got {len(data_yes)}"
    assert all(r["boundary_delineated"] is True for r in data_yes)

    # Boundary no
    res_no = run_cli_command(["--boundary", "no", "--format", "json"])
    assert res_no.returncode == 0, f"CLI --boundary no failed. Stderr: {res_no.stderr}"
    data_no = json.loads(res_no.stdout)
    assert len(data_no) == 300, f"Expected 300 undelineated colonies, got {len(data_no)}"
    assert all(r["boundary_delineated"] is False for r in data_no)


def test_tier6_cli_export_functionality():
    """Verify dda_lookup.py --export generates valid CSV and JSON files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_export = Path(tmpdir) / "affluent_export.csv"
        json_export = Path(tmpdir) / "affluent_export.json"

        # CSV Export
        res_csv = run_cli_command(["--category", "affluent", "--export", str(csv_export)])
        assert res_csv.returncode == 0, f"CSV export failed. Stderr: {res_csv.stderr}"
        assert csv_export.exists(), "Exported CSV file was not created"
        with open(csv_export, "r", encoding="utf-8") as f:
            exported_csv_rows = list(csv.DictReader(f))
            assert len(exported_csv_rows) == 69, f"Expected 69 exported CSV rows, got {len(exported_csv_rows)}"

        # JSON Export
        res_json = run_cli_command(["--category", "affluent", "--export", str(json_export)])
        assert res_json.returncode == 0, f"JSON export failed. Stderr: {res_json.stderr}"
        assert json_export.exists(), "Exported JSON file was not created"
        with open(json_export, "r", encoding="utf-8") as f:
            exported_json_items = json.load(f)
            assert len(exported_json_items) == 69, f"Expected 69 exported JSON items, got {len(exported_json_items)}"


def test_tier6_cli_stats_display():
    """Verify dda_lookup.py --stats displays comprehensive summary statistics."""
    res = run_cli_command(["--stats"])
    assert res.returncode == 0, f"CLI --stats failed. Stderr: {res.stderr}"
    out = res.stdout
    assert "1,800" in out or "1800" in out, "Total count 1800 missing from --stats"
    assert "69" in out, "Affluent count 69 missing from --stats"
    assert "1,731" in out or "1731" in out, "Regular count 1731 missing from --stats"
    assert "1,500" in out or "1500" in out or "Delineated" in out, "Boundary stats missing from --stats"


def test_tier6_cli_non_existent_query_graceful_handling():
    """Verify dda_lookup.py handles non-existent queries gracefully with exit code 0."""
    res = run_cli_command(["--search", "ZZZ_NON_EXISTENT_QUERY_TEST_12345"])
    assert res.returncode == 0, f"Non-existent search should exit with 0, got {res.returncode}. Stderr: {res.stderr}"

    res_json = run_cli_command(["--search", "ZZZ_NON_EXISTENT_QUERY_TEST_12345", "--format", "json"])
    assert res_json.returncode == 0
    data = json.loads(res_json.stdout)
    assert data == [], f"Expected empty list for non-existent search, got {data}"


# ==============================================================================
# STANDALONE TEST RUNNER (ZERO-DEPENDENCY)
# ==============================================================================
ALL_TIER_CHECKS = [
    ("Tier 1: Storage Integrity", [
        ("File Existence & Sizes (>100KB)", test_tier1_file_existence_and_sizes),
        ("SQLite DB Schema & Tables", test_tier1_sqlite_schema_and_tables),
        ("SQLite Performance Indices", test_tier1_sqlite_indices),
    ]),
    ("Tier 2: Exact Record Counts", [
        ("Total Record Counts (1,800)", test_tier2_total_record_counts),
        ("Affluent (69) vs Regular (1,731)", test_tier2_affluent_regular_breakdown),
        ("Boundary Delineation Counts (>1,400)", test_tier2_boundary_delineation_counts),
    ]),
    ("Tier 3: Schema & Field Integrity", [
        ("Schema Attribute Completeness (11 Fields)", test_tier3_schema_attribute_completeness),
        ("Sequential Unique IDs (1..1800)", test_tier3_sequential_colony_ids),
        ("Colony Names Validity", test_tier3_colony_names_integrity),
        ("Category Classification Validity", test_tier3_category_field_validity),
        ("Boundary Delineated Typing & Exclusion", test_tier3_boundary_delineated_typing),
        ("ISO Upload Dates Format", test_tier3_upload_dates_format),
    ]),
    ("Tier 4: URL Formats & DDA Domains", [
        ("URL Schemes & dda.gov.in Domain", test_tier4_url_scheme_and_domain_validity),
        ("Boundary Map PDF Extensions (.pdf)", test_tier4_pdf_urls_file_extension),
        ("Mandatory Source Links Presence", test_tier4_source_links_universality),
    ]),
    ("Tier 5: Cross-Format Parity", [
        ("100% Equivalence (JSON vs CSV vs SQLite DB)", test_tier5_cross_format_parity_json_csv_db),
    ]),
    ("Tier 6: CLI End-to-End Functional Tests", [
        ("CLI --help and Usage Instructions", test_tier6_cli_help_option),
        ("CLI --category affluent (69 items)", test_tier6_cli_category_affluent_filter),
        ("CLI --category regular (1,731 items)", test_tier6_cli_category_regular_filter),
        ("CLI --search ('Sainik' & 'Sangam Vihar')", test_tier6_cli_search_queries),
        ("CLI --info Inspection Cards (ID 1 & 70)", test_tier6_cli_info_details),
        ("CLI --boundary Filter (yes/no)", test_tier6_cli_boundary_filter),
        ("CLI --export (CSV & JSON formats)", test_tier6_cli_export_functionality),
        ("CLI --stats Summary Display", test_tier6_cli_stats_display),
        ("CLI Non-Existent Query Graceful Handling", test_tier6_cli_non_existent_query_graceful_handling),
    ]),
]


def run_standalone_verification():
    """Run all verification tiers, pretty-print formatted results, and return exit code."""
    # Terminal formatting codes
    USE_COLOR = sys.stdout.isatty() or os.environ.get("FORCE_COLOR") == "1"
    GREEN = "\033[92m" if USE_COLOR else ""
    RED = "\033[91m" if USE_COLOR else ""
    CYAN = "\033[96m" if USE_COLOR else ""
    BOLD = "\033[1m" if USE_COLOR else ""
    RESET = "\033[0m" if USE_COLOR else ""

    print("=" * 80)
    print(f"{BOLD}{CYAN}DDA DELHI COLONIES DATASET & CLI VERIFICATION TEST SUITE (6-TIER AUDIT){RESET}")
    print("=" * 80)
    print(f"Target Project Root: {BASE_DIR}")
    print(f"Data Directory:      {DATA_DIR}")
    print(f"CLI Executable:      {CLI_PATH}")
    print(f"Execution Mode:      Standalone Python Test Runner (Zero-Dependency)")
    print("-" * 80)

    total_passed = 0
    total_failed = 0
    tier_summary = []
    start_time_all = time.time()

    for tier_name, checks in ALL_TIER_CHECKS:
        print(f"\n{BOLD}{CYAN}[{tier_name}]{RESET}")
        tier_passed = 0
        tier_failed = 0

        for check_name, check_fn in checks:
            t0 = time.time()
            try:
                check_fn()
                elapsed = (time.time() - t0) * 1000
                print(f"  {GREEN}✓ PASS{RESET}  {check_name:<55} ({elapsed:.1f} ms)")
                tier_passed += 1
                total_passed += 1
            except Exception as e:
                elapsed = (time.time() - t0) * 1000
                print(f"  {RED}✗ FAIL{RESET}  {check_name:<55} ({elapsed:.1f} ms)")
                print(f"         {RED}Error: {e}{RESET}")
                tier_failed += 1
                total_failed += 1

        tier_summary.append((tier_name, tier_passed, tier_failed))

    total_elapsed = time.time() - start_time_all
    total_checks = total_passed + total_failed

    print("\n" + "=" * 80)
    print(f"{BOLD}VERIFICATION SUMMARY BY TIER{RESET}")
    print("=" * 80)
    for t_name, p_cnt, f_cnt in tier_summary:
        status = f"{GREEN}ALL PASSED{RESET}" if f_cnt == 0 else f"{RED}{f_cnt} FAILED{RESET}"
        print(f"  {t_name:<42} : {p_cnt}/{p_cnt + f_cnt} Passed  [{status}]")

    print("-" * 80)
    print(f"Total Verification Checks Run:  {total_checks}")
    print(f"Passed Checks:                  {GREEN}{total_passed}{RESET} ({total_passed/total_checks*100:.1f}%)")
    print(f"Failed Checks:                  {RED if total_failed > 0 else GREEN}{total_failed}{RESET}")
    print(f"Total Execution Time:           {total_elapsed:.2f} seconds")
    print("=" * 80)

    if total_failed == 0:
        print(f"{BOLD}{GREEN}✓ ALL 6 TIERS PASSED (100% SUCCESS) — DATASET & CLI FULLY VERIFIED{RESET}")
        print("=" * 80)
        return 0
    else:
        print(f"{BOLD}{RED}✗ VERIFICATION FAILED — {total_failed} CHECK(S) FAILED{RESET}")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    exit_code = run_standalone_verification()
    sys.exit(exit_code)

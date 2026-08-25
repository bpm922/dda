"""
tests/test_dataset.py — Comprehensive pytest suite for Tiers 1-5 of DDA Colonies Dataset.
"""

import csv
import json
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlparse
import pytest

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
# TIER 1: FILE EXISTENCE & STORAGE INTEGRITY
# ==============================================================================
class TestTier1StorageIntegrity:
    """Test physical storage, file existence, minimum sizes, and database schemas."""

    def test_json_file_exists_and_size(self, json_path):
        assert json_path.exists(), f"colonies.json missing at {json_path}"
        assert json_path.is_file()
        size = json_path.stat().st_size
        assert size > 100 * 1024, f"colonies.json size ({size} bytes) under 100KB"

    def test_csv_file_exists_and_size(self, csv_path):
        assert csv_path.exists(), f"colonies.csv missing at {csv_path}"
        assert csv_path.is_file()
        size = csv_path.stat().st_size
        assert size > 100 * 1024, f"colonies.csv size ({size} bytes) under 100KB"

    def test_db_file_exists_and_size(self, db_path):
        assert db_path.exists(), f"colonies.db missing at {db_path}"
        assert db_path.is_file()
        size = db_path.stat().st_size
        assert size > 100 * 1024, f"colonies.db size ({size} bytes) under 100KB"

    def test_sqlite_tables_present(self, db_connection):
        cur = db_connection.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view')")
        tables = {row[0] for row in cur.fetchall()}
        required = {"colonies", "colonies_fts", "delineated_boundaries", "dataset_metadata"}
        assert required.issubset(tables), f"Missing tables: {required - tables}"

    def test_sqlite_colonies_columns(self, db_connection):
        cur = db_connection.cursor()
        cur.execute("PRAGMA table_info(colonies)")
        columns = {row[1] for row in cur.fetchall()}
        assert set(REQUIRED_FIELDS).issubset(columns), f"Missing columns in colonies table: {set(REQUIRED_FIELDS) - columns}"

    def test_sqlite_indices_present(self, db_connection):
        cur = db_connection.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indices = {row[0] for row in cur.fetchall()}
        expected = {
            "idx_colonies_category",
            "idx_colonies_reg_number",
            "idx_colonies_map_number",
            "idx_colonies_boundary_delineated",
            "idx_colonies_name",
        }
        assert expected.issubset(indices), f"Missing indexes: {expected - indices}"

    def test_sqlite_fts5_triggers_present(self, db_connection):
        cur = db_connection.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
        triggers = {row[0] for row in cur.fetchall()}
        expected_triggers = {"colonies_ai", "colonies_ad", "colonies_au"}
        assert expected_triggers.issubset(triggers), f"Missing triggers: {expected_triggers - triggers}"


# ==============================================================================
# TIER 2: EXACT RECORD COUNTS & STATISTICAL DISTRIBUTION
# ==============================================================================
class TestTier2RecordCounts:
    """Test exact total record counts and category distributions."""

    def test_total_count_json(self, json_data):
        assert len(json_data) == 1800, f"Expected 1800 JSON records, got {len(json_data)}"

    def test_total_count_csv(self, csv_data):
        assert len(csv_data) == 1800, f"Expected 1800 CSV rows, got {len(csv_data)}"

    def test_total_count_db(self, db_data):
        assert len(db_data) == 1800, f"Expected 1800 DB rows, got {len(db_data)}"

    def test_affluent_count(self, json_data, csv_data, db_data):
        aff_json = [r for r in json_data if r["category"] == "affluent"]
        aff_csv = [r for r in csv_data if r["category"] == "affluent"]
        aff_db = [r for r in db_data if r["category"] == "affluent"]

        assert len(aff_json) == 69, f"JSON affluent count: {len(aff_json)}"
        assert len(aff_csv) == 69, f"CSV affluent count: {len(aff_csv)}"
        assert len(aff_db) == 69, f"DB affluent count: {len(aff_db)}"

    def test_regular_count(self, json_data, csv_data, db_data):
        reg_json = [r for r in json_data if r["category"] == "regular"]
        reg_csv = [r for r in csv_data if r["category"] == "regular"]
        reg_db = [r for r in db_data if r["category"] == "regular"]

        assert len(reg_json) == 1731, f"JSON regular count: {len(reg_json)}"
        assert len(reg_csv) == 1731, f"CSV regular count: {len(reg_csv)}"
        assert len(reg_db) == 1731, f"DB regular count: {len(reg_db)}"

    def test_delineated_boundary_count(self, json_data, csv_data, db_data):
        delin_json = [r for r in json_data if r["boundary_delineated"] is True]
        delin_csv = [r for r in csv_data if r["boundary_delineated"] in ("1", "True", True)]
        delin_db = [r for r in db_data if r["boundary_delineated"] == 1]

        assert len(delin_json) > 1400, f"Delineated JSON count too low: {len(delin_json)}"
        assert len(delin_json) == 1500, f"Expected exactly 1500 delineated in JSON, got {len(delin_json)}"
        assert len(delin_csv) == 1500, f"Expected exactly 1500 delineated in CSV, got {len(delin_csv)}"
        assert len(delin_db) == 1500, f"Expected exactly 1500 delineated in DB, got {len(delin_db)}"

    def test_undelineated_count(self, json_data):
        undelin_json = [r for r in json_data if r["boundary_delineated"] is False]
        assert len(undelin_json) == 300, f"Expected exactly 300 undelineated in JSON, got {len(undelin_json)}"


# ==============================================================================
# TIER 3: SCHEMA CONFORMANCE & FIELD INTEGRITY
# ==============================================================================
class TestTier3SchemaIntegrity:
    """Test field existence, sequential primary keys, data typing, and constraints."""

    def test_all_11_fields_present_in_every_json_record(self, json_data):
        for idx, r in enumerate(json_data):
            missing = set(REQUIRED_FIELDS) - set(r.keys())
            assert not missing, f"JSON index {idx} missing fields: {missing}"

    def test_csv_header_order_and_names(self, csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            header = next(csv.reader(f))
            assert header == REQUIRED_FIELDS, f"CSV header mismatch: {header}"

    def test_sequential_unique_colony_ids(self, json_data):
        ids = [r["colony_id"] for r in json_data]
        assert len(ids) == 1800
        assert len(set(ids)) == 1800, "Duplicate colony_id found"
        assert ids == list(range(1, 1801)), "colony_ids are not contiguous integers 1..1800"

    def test_id_category_mapping(self, json_data):
        for r in json_data:
            cid = r["colony_id"]
            if 1 <= cid <= 69:
                assert r["category"] == "affluent", f"ID {cid} should be affluent"
            else:
                assert r["category"] == "regular", f"ID {cid} should be regular"

    def test_non_empty_colony_names(self, json_data):
        for r in json_data:
            cid = r["colony_id"]
            name = r.get("name")
            assert isinstance(name, str), f"ID {cid} name is not string: {type(name)}"
            assert len(name.strip()) > 0, f"ID {cid} name is blank"

    def test_category_validity(self, json_data):
        valid_cats = {"affluent", "regular"}
        for r in json_data:
            assert r["category"] in valid_cats

    def test_boundary_delineated_type_and_exclusion_logic(self, json_data):
        for r in json_data:
            bd = r["boundary_delineated"]
            assert isinstance(bd, bool), f"ID {r['colony_id']} boundary_delineated not bool"
            if r["category"] == "affluent":
                assert bd is False, f"Affluent ID {r['colony_id']} must have boundary_delineated=False"
                assert "excluded from PM-UDAY" in (r.get("remarks") or "")

    def test_iso_upload_dates(self, json_data):
        date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        for r in json_data:
            dt = r.get("upload_date")
            if dt is not None and str(dt).strip() != "":
                assert date_pattern.match(str(dt)), f"ID {r['colony_id']} invalid upload_date: {dt}"


# ==============================================================================
# TIER 4: URL FORMATS & DDA DOMAIN VALIDITY
# ==============================================================================
class TestTier4UrlIntegrity:
    """Test URL validity, HTTP/HTTPS schemes, DDA domain containment, and PDF extensions."""

    def test_url_schemes_and_domain(self, json_data):
        url_fields = ["satellite_boundary_pdf_url", "final_boundary_pdf_url", "source_link"]
        for r in json_data:
            cid = r["colony_id"]
            for fld in url_fields:
                val = r.get(fld)
                if val:
                    parsed = urlparse(val)
                    assert parsed.scheme in ("http", "https"), f"ID {cid} {fld} scheme invalid: {parsed.scheme}"
                    assert "dda.gov.in" in parsed.netloc.lower(), f"ID {cid} {fld} domain invalid: {parsed.netloc}"

    def test_pdf_url_extensions(self, json_data):
        pdf_fields = ["satellite_boundary_pdf_url", "final_boundary_pdf_url"]
        for r in json_data:
            cid = r["colony_id"]
            for fld in pdf_fields:
                val = r.get(fld)
                if val:
                    parsed = urlparse(val)
                    assert parsed.path.lower().endswith(".pdf"), f"ID {cid} {fld} not .pdf: {val}"

    def test_source_links_universality(self, json_data):
        for r in json_data:
            cid = r["colony_id"]
            src = r.get("source_link")
            assert src is not None and len(src.strip()) > 0, f"ID {cid} missing source_link"
            assert src.startswith("https://dda.gov.in"), f"ID {cid} source_link invalid: {src}"


# ==============================================================================
# TIER 5: CROSS-FORMAT PARITY
# ==============================================================================
class TestTier5CrossFormatParity:
    """Test exact row-by-row and field-by-field parity between JSON, CSV, and SQLite DB."""

    def test_full_field_equivalence(self, json_data, csv_data, db_data):
        assert len(json_data) == len(csv_data) == len(db_data) == 1800

        for i in range(1800):
            jr = json_data[i]
            cr = csv_data[i]
            dr = db_data[i]
            cid = jr["colony_id"]

            # colony_id
            assert int(cr["colony_id"]) == cid == dr["colony_id"]

            # name
            assert jr["name"] == cr["name"] == dr["name"]

            # reg_number
            j_reg = "" if jr["reg_number"] is None else str(jr["reg_number"]).strip()
            c_reg = "" if cr["reg_number"] is None else str(cr["reg_number"]).strip()
            d_reg = "" if dr["reg_number"] is None else str(dr["reg_number"]).strip()
            assert j_reg == c_reg == d_reg

            # category
            assert jr["category"] == cr["category"] == dr["category"]

            # boundary_delineated
            j_bd = bool(jr["boundary_delineated"])
            c_bd = cr["boundary_delineated"] in ("1", "True", True)
            d_bd = bool(dr["boundary_delineated"])
            assert j_bd == c_bd == d_bd

            # map_number
            j_map = "" if jr["map_number"] is None else str(jr["map_number"]).strip()
            c_map = "" if cr["map_number"] is None else str(cr["map_number"]).strip()
            d_map = "" if dr["map_number"] is None else str(dr["map_number"]).strip()
            assert j_map == c_map == d_map

            # satellite_boundary_pdf_url
            j_sat = "" if jr["satellite_boundary_pdf_url"] is None else str(jr["satellite_boundary_pdf_url"]).strip()
            c_sat = "" if cr["satellite_boundary_pdf_url"] is None else str(cr["satellite_boundary_pdf_url"]).strip()
            d_sat = "" if dr["satellite_boundary_pdf_url"] is None else str(dr["satellite_boundary_pdf_url"]).strip()
            assert j_sat == c_sat == d_sat

            # final_boundary_pdf_url
            j_fin = "" if jr["final_boundary_pdf_url"] is None else str(jr["final_boundary_pdf_url"]).strip()
            c_fin = "" if cr["final_boundary_pdf_url"] is None else str(cr["final_boundary_pdf_url"]).strip()
            d_fin = "" if dr["final_boundary_pdf_url"] is None else str(dr["final_boundary_pdf_url"]).strip()
            assert j_fin == c_fin == d_fin

            # upload_date
            j_up = "" if jr["upload_date"] is None else str(jr["upload_date"]).strip()
            c_up = "" if cr["upload_date"] is None else str(cr["upload_date"]).strip()
            d_up = "" if dr["upload_date"] is None else str(dr["upload_date"]).strip()
            assert j_up == c_up == d_up

            # remarks
            j_rem = "" if jr["remarks"] is None else str(jr["remarks"]).strip()
            c_rem = "" if cr["remarks"] is None else str(cr["remarks"]).strip()
            d_rem = "" if dr["remarks"] is None else str(dr["remarks"]).strip()
            assert j_rem == c_rem == d_rem

            # source_link
            j_src = "" if jr["source_link"] is None else str(jr["source_link"]).strip()
            c_src = "" if cr["source_link"] is None else str(cr["source_link"]).strip()
            d_src = "" if dr["source_link"] is None else str(dr["source_link"]).strip()
            assert j_src == c_src == d_src

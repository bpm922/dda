"""
tests/test_cli.py — Comprehensive pytest suite for Tier 6 (CLI utility dda_lookup.py).
"""

import csv
import json
import os
import tempfile
from pathlib import Path
import pytest


class TestTier6CliHelpAndUsage:
    """Test CLI help flags, exit codes, and usage text."""

    def test_help_flag_long(self, run_cli):
        res = run_cli(["--help"])
        assert res.returncode == 0
        assert "usage:" in res.stdout.lower() or "dda_lookup" in res.stdout
        assert "--search" in res.stdout
        assert "--category" in res.stdout

    def test_help_flag_short(self, run_cli):
        res = run_cli(["-h"])
        assert res.returncode == 0
        assert "usage:" in res.stdout.lower() or "dda_lookup" in res.stdout

    def test_version_flag(self, run_cli):
        res = run_cli(["--version"])
        assert res.returncode == 0
        assert "1.0.0" in res.stdout or "v" in res.stdout.lower()


class TestTier6CliCategoryFiltering:
    """Test category filtering (--category affluent and --category regular)."""

    def test_category_affluent_json_count_and_content(self, run_cli):
        res = run_cli(["--category", "affluent", "--format", "json"])
        assert res.returncode == 0
        data = json.loads(res.stdout)
        assert len(data) == 69
        assert all(r["category"] == "affluent" for r in data)
        assert any(r["name"] == "Sainik Farms" for r in data)

    def test_category_regular_json_count_and_content(self, run_cli):
        res = run_cli(["--category", "regular", "--format", "json"])
        assert res.returncode == 0
        data = json.loads(res.stdout)
        assert len(data) == 1731
        assert all(r["category"] == "regular" for r in data)

    def test_category_invalid_choice(self, run_cli):
        res = run_cli(["--category", "invalid_category", "--format", "json"])
        assert res.returncode == 0
        data = json.loads(res.stdout)
        assert data == []

    def test_category_invalid_choice_text(self, run_cli):
        res = run_cli(["--category", "invalid_category"])
        assert res.returncode == 0
        assert "no colony records found" in res.stdout.lower()


class TestTier6CliKeywordSearch:
    """Test keyword search functionality across names, registration numbers, and remarks."""

    def test_search_sainik(self, run_cli):
        res = run_cli(["--search", "Sainik", "--format", "json"])
        assert res.returncode == 0
        data = json.loads(res.stdout)
        assert len(data) >= 1
        assert any("Sainik" in r["name"] for r in data)

    def test_search_sangam_vihar(self, run_cli):
        res = run_cli(["--search", "Sangam Vihar", "--format", "json"])
        assert res.returncode == 0
        data = json.loads(res.stdout)
        assert len(data) >= 1
        assert any("Sangam" in r["name"] for r in data)

    def test_search_reg_number(self, run_cli):
        res = run_cli(["--search", "453", "--format", "json"])
        assert res.returncode == 0
        data = json.loads(res.stdout)
        assert len(data) >= 1
        assert any(r.get("reg_number") == "453" or "453" in str(r.get("remarks")) for r in data)

    def test_search_non_existent(self, run_cli):
        res = run_cli(["--search", "ZZZ_NON_EXISTENT_QUERY_987654321", "--format", "json"])
        assert res.returncode == 0
        data = json.loads(res.stdout)
        assert data == []


class TestTier6CliColonyInspection:
    """Test colony inspection card display (--info, --id, --reg-no, --map-no)."""

    def test_info_affluent_colony_1(self, run_cli):
        res = run_cli(["--info", "1"])
        assert res.returncode == 0
        assert "Sainik Farms" in res1_text if "res1_text" in locals() else "Sainik Farms" in res.stdout
        assert "affluent" in res.stdout.lower()
        assert "pm-uday" in res.stdout.lower()

    def test_info_regular_colony_70(self, run_cli):
        res = run_cli(["--info", "70"])
        assert res.returncode == 0
        assert "Ladakh Budh Vihar" in res.stdout
        assert "regular" in res.stdout.lower()
        assert "111_1.pdf" in res.stdout or "dda.gov.in" in res.stdout

    def test_lookup_by_id(self, run_cli):
        res = run_cli(["--id", "1", "--format", "json"])
        assert res.returncode == 0
        data = json.loads(res.stdout)
        colony = data[0] if isinstance(data, list) else data
        assert colony["colony_id"] == 1
        assert colony["name"] == "Sainik Farms"

    def test_lookup_by_reg_no(self, run_cli):
        res = run_cli(["--reg-no", "1", "--format", "json"])
        assert res.returncode == 0
        data = json.loads(res.stdout)
        assert len(data) >= 1
        assert any(r["reg_number"] == "1" for r in data)

    def test_lookup_by_map_no(self, run_cli):
        res = run_cli(["--map-no", "111", "--format", "json"])
        assert res.returncode == 0
        data = json.loads(res.stdout)
        assert len(data) >= 1
        assert any(r["map_number"] == "111" for r in data)


class TestTier6CliBoundaryFiltering:
    """Test boundary delineation filtering (--boundary yes/no, --delineated)."""

    def test_boundary_yes(self, run_cli):
        res = run_cli(["--boundary", "yes", "--format", "json"])
        assert res.returncode == 0
        data = json.loads(res.stdout)
        assert len(data) == 1500
        assert all(r["boundary_delineated"] is True for r in data)

    def test_boundary_no(self, run_cli):
        res = run_cli(["--boundary", "no", "--format", "json"])
        assert res.returncode == 0
        data = json.loads(res.stdout)
        assert len(data) == 300
        assert all(r["boundary_delineated"] is False for r in data)

    def test_delineated_shortcut_flag(self, run_cli):
        res = run_cli(["--delineated", "--format", "json"])
        assert res.returncode == 0
        data = json.loads(res.stdout)
        assert len(data) == 1500
        assert all(r["boundary_delineated"] is True for r in data)


class TestTier6CliExport:
    """Test data export to CSV and JSON files."""

    def test_export_csv_affluent(self, run_cli):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "affluent.csv"
            res = run_cli(["--category", "affluent", "--export", str(out_file)])
            assert res.returncode == 0
            assert out_file.exists()
            with open(out_file, "r", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
                assert len(rows) == 69

    def test_export_json_regular(self, run_cli):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "regular.json"
            res = run_cli(["--category", "regular", "--export", str(out_file)])
            assert res.returncode == 0
            assert out_file.exists()
            with open(out_file, "r", encoding="utf-8") as f:
                items = json.load(f)
                assert len(items) == 1731


class TestTier6CliStats:
    """Test summary statistics display."""

    def test_stats_output(self, run_cli):
        res = run_cli(["--stats"])
        assert res.returncode == 0
        assert "1,800" in res.stdout or "1800" in res.stdout
        assert "69" in res.stdout
        assert "1,731" in res.stdout or "1731" in res.stdout
        assert "1,500" in res.stdout or "1500" in res.stdout


class TestTier6CliOutputFormats:
    """Test table, json, csv, and plain formatting options."""

    def test_format_table(self, run_cli):
        res = run_cli(["--category", "affluent", "--limit", "5", "--format", "table"])
        assert res.returncode == 0
        assert "Sainik Farms" in res.stdout

    def test_format_csv(self, run_cli):
        res = run_cli(["--category", "affluent", "--limit", "5", "--format", "csv"])
        assert res.returncode == 0
        lines = res.stdout.strip().splitlines()
        assert len(lines) >= 2
        assert "colony_id" in lines[0]

    def test_format_plain(self, run_cli):
        res = run_cli(["--category", "affluent", "--limit", "5", "--format", "plain"])
        assert res.returncode == 0
        assert "Sainik Farms" in res.stdout
        assert "\t" in res.stdout


class TestTier6CliPaginationAndLimits:
    """Test --limit and --offset parameters."""

    def test_limit_parameter(self, run_cli):
        res = run_cli(["--category", "regular", "--limit", "10", "--format", "json"])
        assert res.returncode == 0
        data = json.loads(res.stdout)
        assert len(data) == 10

    def test_offset_parameter(self, run_cli):
        res1 = run_cli(["--category", "regular", "--limit", "5", "--offset", "0", "--format", "json"])
        res2 = run_cli(["--category", "regular", "--limit", "5", "--offset", "5", "--format", "json"])
        assert res1.returncode == 0
        assert res2.returncode == 0
        data1 = json.loads(res1.stdout)
        data2 = json.loads(res2.stdout)
        assert len(data1) == 5
        assert len(data2) == 5
        ids1 = {r["colony_id"] for r in data1}
        ids2 = {r["colony_id"] for r in data2}
        assert ids1.isdisjoint(ids2)

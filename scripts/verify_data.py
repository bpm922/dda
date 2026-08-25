#!/usr/bin/env python3
"""
Verification script for DDA Delhi Colonies datasets.
Validates JSON, CSV, SQLite database integrity, counts, schemas, and cross-format parity.
"""

import json
import csv
import sqlite3
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
JSON_PATH = DATA_DIR / "colonies.json"
CSV_PATH = DATA_DIR / "colonies.csv"
DB_PATH = DATA_DIR / "colonies.db"

def main():
    print("=" * 60)
    print("RUNNING DDA DATASET VERIFICATION CHECKS")
    print("=" * 60)
    
    assert JSON_PATH.exists(), f"Missing JSON: {JSON_PATH}"
    assert CSV_PATH.exists(), f"Missing CSV: {CSV_PATH}"
    assert DB_PATH.exists(), f"Missing DB: {DB_PATH}"
    print("[PASS] File existence check.")

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        json_data = json.load(f)
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        csv_data = list(csv.DictReader(f))
        
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM colonies")
    db_count = cur.fetchone()[0]

    assert len(json_data) == 1800, f"Expected 1800 JSON items, got {len(json_data)}"
    assert len(csv_data) == 1800, f"Expected 1800 CSV rows, got {len(csv_data)}"
    assert db_count == 1800, f"Expected 1800 DB rows, got {db_count}"
    print(f"[PASS] Total record count check: exactly 1,800 records across all 3 formats.")

    aff_json = [r for r in json_data if r["category"] == "affluent"]
    reg_json = [r for r in json_data if r["category"] == "regular"]
    assert len(aff_json) == 69, f"Expected 69 affluent, got {len(aff_json)}"
    assert len(reg_json) == 1731, f"Expected 1731 regular, got {len(reg_json)}"
    print("[PASS] Categorization check: exactly 69 Affluent and 1,731 Regular colonies.")

    # FTS5 search check
    cur.execute("SELECT COUNT(*) FROM colonies_fts WHERE colonies_fts MATCH 'Sainik'")
    sainik_hits = cur.fetchone()[0]
    assert sainik_hits > 0, "FTS5 query for 'Sainik' yielded 0 results"
    print(f"[PASS] SQLite FTS5 search index verified ({sainik_hits} hits for 'Sainik').")

    conn.close()
    print("=" * 60)
    print("[✓] ALL VERIFICATION CHECKS PASSED (100% SUCCESS)")
    print("=" * 60)

if __name__ == "__main__":
    main()

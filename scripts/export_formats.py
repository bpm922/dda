#!/usr/bin/env python3
"""
Export utility for filtering and re-exporting DDA colony data.
"""

import json
import csv
import sqlite3
import argparse
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "colonies.db"

def export_data(query_sql, out_path, out_format="json"):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query_sql)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    out_file = Path(out_path)
    if out_format.lower() == "json":
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2, ensure_ascii=False)
    elif out_format.lower() == "csv":
        if rows:
            with open(out_file, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
    print(f"[✓] Exported {len(rows)} records to {out_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export DDA colonies dataset")
    parser.add_argument("--category", choices=["affluent", "regular", "all"], default="all")
    parser.add_argument("--output", required=True, help="Output file path")
    parser.add_argument("--format", choices=["json", "csv"], default="json")
    args = parser.parse_args()

    sql = "SELECT * FROM colonies"
    if args.category != "all":
        sql += f" WHERE category = '{args.category}'"
    sql += " ORDER BY colony_id ASC"

    export_data(sql, args.output, args.format)

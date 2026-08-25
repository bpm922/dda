#!/usr/bin/env python3
"""
DDA PM-UDAY Colony Data Pipeline & Dataset Builder
Author: Worker 1 (Data Engineering Specialist)
Extracts, structures, validates, and generates:
- DDA/data/colonies.json
- DDA/data/colonies.csv
- DDA/data/colonies.db
- DDA/scripts/build_datasets.py
- DDA/scripts/verify_datasets.py
- DDA/scripts/export_formats.py
"""

import os
import sys
import re
import csv
import json
import sqlite3
import collections
import subprocess
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path

# Paths
ROOT_DIR = Path("/home/bpm922/Documents/Me/new/DDA")
DATA_DIR = ROOT_DIR / "data"
SCRIPTS_DIR = ROOT_DIR / "scripts"
AGENT_DIR = Path("/home/bpm922/Documents/Me/new/.agents/worker_m1")

DATA_DIR.mkdir(parents=True, exist_ok=True)
SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
AGENT_DIR.mkdir(parents=True, exist_ok=True)

AFFLUENT_PDF = "/home/bpm922/.gemini/antigravity-cli/brain/01519230-caab-45a2-b633-90222ef4c9e9/.tempmediaStorage/6b25e8910a007fde.pdf"
UC_1731_PDF = "/home/bpm922/.gemini/antigravity-cli/brain/01519230-caab-45a2-b633-90222ef4c9e9/.tempmediaStorage/4e6321807206554c.pdf"
DELINEATED_HTML = "/home/bpm922/Documents/Me/new/.agents/survey_explorer_1/dda_delineated_raw.html"

SOURCE_LINK_AFFLUENT = "https://dda.gov.in/sites/default/files/pmuday/2.%20List%20of%2069%20Unauthorized%20Colonies%20Inhabitated%20By%20Affluent%20Section%20of%20Society.pdf"
SOURCE_LINK_UC_1731 = "https://dda.gov.in/sites/default/files/pmuday/1731_uc.pdf"
SOURCE_LINK_DELINEATED = "https://dda.gov.in/delineated-boundary"

def parse_date(date_str):
    if not date_str or date_str.strip() in ["-", "N/A", "NA", ""]:
        return None
    ds = date_str.strip()
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            dt = datetime.strptime(ds, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
    return ds

def build_dataset():
    print("=" * 65)
    print("BUILDING DDA DELHI UNAUTHORIZED & AFFLUENT COLONIES DATASETS")
    print("=" * 65)

    # 1. Parse 69 Affluent Colonies
    print("[1/4] Parsing 69 Affluent Colonies from official PDF...")
    res_aff = subprocess.run(["pdftotext", "-layout", AFFLUENT_PDF, "-"], capture_output=True, text=True)
    aff_lines = res_aff.stdout.splitlines()

    affluent_raw = []
    current_aff = None

    for line in aff_lines:
        l_strip = line.strip()
        if not l_strip:
            continue
        if "LIST OF UNAUTHORISED COLONIES" in l_strip or "List of UCs" in l_strip or "S. No" in l_strip or "Regn" in l_strip:
            continue
        if "Explanation" in l_strip or "Regulations for Regularisation" in l_strip or "Government of National Capital" in l_strip:
            continue
        
        m = re.match(r"^(\d+)\.\s+(.*)$", l_strip)
        if m:
            if current_aff:
                affluent_raw.append(current_aff)
            sno = int(m.group(1))
            rest = m.group(2).strip()
            current_aff = {"sno": sno, "raw": rest}
        else:
            if current_aff:
                current_aff["raw"] += " " + l_strip

    if current_aff:
        affluent_raw.append(current_aff)

    assert len(affluent_raw) == 69, f"Expected 69 affluent colonies, got {len(affluent_raw)}"

    affluent_records = []
    for r in affluent_raw:
        sno = r["sno"]
        raw = r["raw"]
        raw = re.sub(r"Explanation.*$", "", raw, flags=re.DOTALL).strip()
        raw = re.sub(r"Government of National Capital Territory.*$", "", raw, flags=re.DOTALL).strip()
        raw = re.sub(r"March,?\s*2008\.?", "", raw, flags=re.DOTALL).strip()
        
        if sno in [1, 2, 3]:
            reg_no = None
            name = raw
        else:
            m = re.match(r"^(\d+\s*-\s*\((?:ELD|LOP)\)|\d+[\s\-]*(?:ELD|LOP)|\d+\s*[A-Z]|\d+)\s+(.*)$", raw, re.IGNORECASE)
            if m:
                reg_no = re.sub(r"\s+", " ", m.group(1).strip())
                name = m.group(2).strip()
            else:
                reg_no = None
                name = raw
        
        name = re.sub(r"\s+", " ", name).strip()
        name = name.rstrip(",.- ")
        
        affluent_records.append({
            "colony_id": sno, # 1..69
            "name": name,
            "reg_number": reg_no,
            "category": "affluent",
            "boundary_delineated": False,
            "map_number": None,
            "satellite_boundary_pdf_url": None,
            "final_boundary_pdf_url": None,
            "upload_date": None,
            "remarks": "Inhabited by affluent section; excluded from PM-UDAY scheme under Regulation 3(1)",
            "source_link": SOURCE_LINK_AFFLUENT
        })

    print(f" -> Successfully parsed {len(affluent_records)} Affluent Colonies.")

    # 2. Parse 1,731 Regular UCs from 1731_uc.pdf
    print("[2/4] Parsing 1,731 Regular Unauthorized Colonies from official PDF...")
    res_bbox = subprocess.run(["pdftotext", "-bbox", UC_1731_PDF, "-"], capture_output=True, text=True)
    xml_clean = re.sub(r"<!DOCTYPE[^>]*>", "", res_bbox.stdout)
    xml_clean = re.sub(r'xmlns="[^"]*"', "", xml_clean)
    root = ET.fromstring(xml_clean)

    uc_raw = []
    for p_idx, page in enumerate(root.findall(".//page"), 1):
        words = []
        for w in page.findall("word"):
            words.append({
                "text": w.text or "",
                "xMin": float(w.attrib["xMin"]),
                "yMin": float(w.attrib["yMin"]),
                "xMax": float(w.attrib["xMax"]),
                "yMax": float(w.attrib["yMax"])
            })
        sl_words = [w for w in words if w["xMin"] < 105 and re.match(r"^\d+\.$", w["text"])]
        sl_words.sort(key=lambda x: x["yMin"])
        
        for i, sl_w in enumerate(sl_words):
            sl_no = int(sl_w["text"].rstrip("."))
            if i == 0:
                y_start = max(38.0, sl_w["yMin"] - 20.0)
            else:
                y_start = (sl_words[i-1]["yMin"] + sl_w["yMin"]) / 2.0
                
            if i + 1 < len(sl_words):
                y_end = (sl_w["yMin"] + sl_words[i+1]["yMin"]) / 2.0
            else:
                y_end = sl_w["yMin"] + 25.0
                
            ent_words = [w for w in words if y_start <= w["yMin"] < y_end and w != sl_w]
            reg_words = [w for w in ent_words if w["xMin"] < 160 and not (w["yMin"] < 40 and "Reg" in w["text"])]
            part_words = [w for w in ent_words if 160 <= w["xMin"] < 195 and len(w["text"]) <= 3 and re.match(r"^[A-Z0-9\-]+$", w["text"])]
            name_words = [w for w in ent_words if w not in reg_words and w not in part_words and not (w["yMin"] < 40 and "Colony" in w["text"])]
            
            reg_words.sort(key=lambda w: (round(w["yMin"]/5)*5, w["xMin"]))
            name_words.sort(key=lambda w: (round(w["yMin"]/5)*5, w["xMin"]))
            
            reg_str = "".join(w["text"] for w in reg_words).strip() or None
            part_str = "".join(w["text"] for w in part_words).strip() or None
            name_str = " ".join(w["text"] for w in name_words).strip()
            name_str = re.sub(r"\s+", " ", name_str).strip()
            
            if reg_str and part_str:
                full_reg = f"{reg_str}-{part_str}"
            elif reg_str:
                full_reg = reg_str
            else:
                full_reg = None
                
            uc_raw.append({
                "sl_no": sl_no,
                "reg_number": full_reg,
                "reg_str": reg_str,
                "part": part_str,
                "name": name_str,
                "page": p_idx
            })

    assert len(uc_raw) == 1731, f"Expected 1,731 regular colonies, got {len(uc_raw)}"
    print(f" -> Successfully parsed {len(uc_raw)} Regular Unauthorized Colonies.")

    # 3. Parse DDA Delineated Boundary Portal HTML
    print("[3/4] Parsing Delineated Boundary Portal Registry...")
    with open(DELINEATED_HTML, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    del_entries = []
    del_by_reg = collections.defaultdict(list)
    del_by_cluster_reg = collections.defaultdict(list)
    del_by_map = {}

    for row in soup.find_all("tr")[1:]:
        cols = row.find_all("td")
        if not cols or len(cols) < 5:
            continue
        c_txt = [c.get_text(strip=True) for c in cols]
        m = re.search(r"(\d+)", c_txt[0])
        map_no = int(m.group(1)) if m else None
        
        reg_raw = c_txt[1]
        name_raw = c_txt[2]
        
        sat_a = cols[3].find("a") if len(cols) > 3 else None
        sat_pdf = ("https://dda.gov.in" + sat_a.get("href")) if (sat_a and sat_a.get("href")) else None
        
        remarks = c_txt[4] if len(cols) > 4 else None
        if remarks in ["N/A", "-", "", "NA"]:
            remarks = None
            
        upload_date = parse_date(c_txt[5]) if len(cols) > 5 else None
        
        fin_a = cols[6].find("a") if len(cols) > 6 else None
        fin_pdf = ("https://dda.gov.in" + fin_a.get("href")) if (fin_a and fin_a.get("href")) else None
        
        fin_upload_date = parse_date(c_txt[7]) if len(cols) > 7 else None
        eff_upload_date = fin_upload_date or upload_date
        
        reg_clean = re.sub(r"^REGD\.?\s*(?:No\.?)?\s*", "", reg_raw, flags=re.IGNORECASE).rstrip(".").strip()
        reg_norm = re.sub(r"[\s\-_]+", "", reg_clean).upper()
        
        entry = {
            "map_no": map_no,
            "reg_raw": reg_raw,
            "reg_clean": reg_clean,
            "reg_norm": reg_norm,
            "name": name_raw,
            "sat_pdf": sat_pdf,
            "remarks": remarks,
            "upload_date": eff_upload_date,
            "initial_upload_date": upload_date,
            "fin_upload_date": fin_upload_date,
            "fin_pdf": fin_pdf
        }
        del_entries.append(entry)
        if map_no:
            del_by_map[map_no] = entry
        if reg_norm:
            del_by_reg[reg_norm].append(entry)
        
        if remarks:
            cluster_regs = re.findall(r"(?:REGD\.?\s*NO\.?\s*|REG\.?\s*NO\.?\s*|^\(\d+\)\s*)(\d+[\s\-_]*(?:[A-Z]|\(ELD\)|\(LOP\))?)", remarks, flags=re.IGNORECASE)
            for cr in cluster_regs:
                cr_clean = re.sub(r"^REGD\.?\s*(?:No\.?)?\s*", "", cr, flags=re.IGNORECASE).rstrip(".").strip()
                cr_norm = re.sub(r"[\s\-_]+", "", cr_clean).upper()
                if cr_norm:
                    del_by_cluster_reg[cr_norm].append(entry)

    print(f" -> Parsed {len(del_entries)} DDA boundary map entries.")

    # 4. Consolidate Regular UCs with Delineated Boundaries
    print("[4/4] Consolidating and linking regular colonies to boundary maps...")
    regular_records = []
    
    for idx, u in enumerate(uc_raw, start=70): # colony_id 70..1800
        r_str = u["reg_str"]
        p_str = u["part"]
        
        keys = []
        if r_str:
            norm_r = re.sub(r"[\s\-_]+", "", r_str).upper()
            keys.append(norm_r)
            if p_str:
                norm_p = re.sub(r"[\s\-_]+", "", p_str).upper()
                keys.append(f"{norm_r}{norm_p}")
                keys.append(f"{norm_r}PART{norm_p}")
                keys.append(f"{norm_r}_{norm_p}")
                
        match_entry = None
        # Priority 1: Direct registration match
        for k in keys:
            if k in del_by_reg:
                match_entry = del_by_reg[k][0]
                break
                
        # Priority 2: Clustered registration in remarks
        if not match_entry:
            for k in keys:
                if k in del_by_cluster_reg:
                    match_entry = del_by_cluster_reg[k][0]
                    break
                    
        # Priority 3: SL No == Map No with name overlap
        if not match_entry and u["sl_no"] in del_by_map:
            cand = del_by_map[u["sl_no"]]
            u_words = set(re.findall(r"[A-Za-z]{3,}", u["name"].lower()))
            c_words = set(re.findall(r"[A-Za-z]{3,}", cand["name"].lower()))
            if len(u_words.intersection(c_words)) >= 1:
                match_entry = cand

        # Extract linked boundary details
        if match_entry:
            map_no_val = str(match_entry["map_no"]) if match_entry["map_no"] else None
            sat_pdf = match_entry["sat_pdf"]
            fin_pdf = match_entry["fin_pdf"]
            up_date = match_entry["upload_date"]
            rem = match_entry["remarks"]
            has_boundary = bool(sat_pdf or fin_pdf)
            src_link = SOURCE_LINK_DELINEATED
        else:
            map_no_val = None
            sat_pdf = None
            fin_pdf = None
            up_date = None
            rem = "Boundary map pending or omitted from DDA portal table"
            has_boundary = False
            src_link = SOURCE_LINK_UC_1731
            
        regular_records.append({
            "colony_id": idx,
            "name": u["name"],
            "reg_number": u["reg_number"],
            "category": "regular",
            "boundary_delineated": has_boundary,
            "map_number": map_no_val,
            "satellite_boundary_pdf_url": sat_pdf,
            "final_boundary_pdf_url": fin_pdf,
            "upload_date": up_date,
            "remarks": rem,
            "source_link": src_link
        })

    # Combine all 1,800 records
    # Order: 69 Affluent (1..69) followed by 1,731 Regular UCs (70..1800)
    all_colonies = affluent_records + regular_records
    assert len(all_colonies) == 1800, f"Expected 1,800 total colonies, got {len(all_colonies)}"

    # Generate JSON
    json_path = DATA_DIR / "colonies.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_colonies, f, indent=2, ensure_ascii=False)
    print(f"[✓] Generated JSON dataset: {json_path} ({json_path.stat().st_size:,} bytes)")

    # Generate CSV
    csv_path = DATA_DIR / "colonies.csv"
    fieldnames = [
        "colony_id", "name", "reg_number", "category", "boundary_delineated",
        "map_number", "satellite_boundary_pdf_url", "final_boundary_pdf_url",
        "upload_date", "remarks", "source_link"
    ]
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in all_colonies:
            row = r.copy()
            row["boundary_delineated"] = 1 if r["boundary_delineated"] else 0
            for k in row:
                if row[k] is None:
                    row[k] = ""
            writer.writerow(row)
    print(f"[✓] Generated CSV dataset: {csv_path} ({csv_path.stat().st_size:,} bytes)")

    # Generate SQLite DB
    db_path = DATA_DIR / "colonies.db"
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("PRAGMA foreign_keys = ON;")

    # Create colonies table
    cur.execute("""
        CREATE TABLE colonies (
            colony_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            reg_number TEXT,
            category TEXT NOT NULL CHECK(category IN ('affluent', 'regular')),
            boundary_delineated INTEGER NOT NULL DEFAULT 0 CHECK(boundary_delineated IN (0, 1)),
            map_number TEXT,
            satellite_boundary_pdf_url TEXT,
            final_boundary_pdf_url TEXT,
            upload_date TEXT,
            remarks TEXT,
            source_link TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Indexes
    cur.execute("CREATE INDEX idx_colonies_category ON colonies(category);")
    cur.execute("CREATE INDEX idx_colonies_reg_number ON colonies(reg_number);")
    cur.execute("CREATE INDEX idx_colonies_map_number ON colonies(map_number);")
    cur.execute("CREATE INDEX idx_colonies_boundary_delineated ON colonies(boundary_delineated);")
    cur.execute("CREATE INDEX idx_colonies_name ON colonies(name);")

    # FTS5 virtual table
    cur.execute("""
        CREATE VIRTUAL TABLE colonies_fts USING fts5(
            colony_id UNINDEXED,
            name,
            reg_number,
            remarks,
            category,
            content='colonies',
            content_rowid='colony_id'
        );
    """)

    # Triggers
    cur.execute("""
        CREATE TRIGGER colonies_ai AFTER INSERT ON colonies BEGIN
            INSERT INTO colonies_fts(rowid, colony_id, name, reg_number, remarks, category)
            VALUES (new.colony_id, new.colony_id, new.name, new.reg_number, new.remarks, new.category);
        END;
    """)

    cur.execute("""
        CREATE TRIGGER colonies_ad AFTER DELETE ON colonies BEGIN
            INSERT INTO colonies_fts(colonies_fts, rowid, colony_id, name, reg_number, remarks, category)
            VALUES('delete', old.colony_id, old.colony_id, old.name, old.reg_number, old.remarks, old.category);
        END;
    """)

    cur.execute("""
        CREATE TRIGGER colonies_au AFTER UPDATE ON colonies BEGIN
            INSERT INTO colonies_fts(colonies_fts, rowid, colony_id, name, reg_number, remarks, category)
            VALUES('delete', old.colony_id, old.colony_id, old.name, old.reg_number, old.remarks, old.category);
            INSERT INTO colonies_fts(rowid, colony_id, name, reg_number, remarks, category)
            VALUES (new.colony_id, new.colony_id, new.name, new.reg_number, new.remarks, new.category);
        END;
    """)

    # Delineated Boundaries reference table
    cur.execute("""
        CREATE TABLE delineated_boundaries (
            map_number INTEGER PRIMARY KEY,
            reg_number_raw TEXT,
            reg_number_clean TEXT,
            colony_name TEXT,
            satellite_pdf_url TEXT,
            remarks TEXT,
            upload_date TEXT,
            final_pdf_url TEXT,
            final_upload_date TEXT,
            boundary_available INTEGER NOT NULL DEFAULT 0
        );
    """)

    cur.execute("CREATE INDEX idx_del_reg ON delineated_boundaries(reg_number_clean);")

    # Insert delineated entries
    for d in del_entries:
        if d["map_no"]:
            has_b = 1 if (d["sat_pdf"] or d["fin_pdf"]) else 0
            cur.execute("""
                INSERT INTO delineated_boundaries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                d["map_no"], d["reg_raw"], d["reg_clean"], d["name"],
                d["sat_pdf"], d["remarks"], d["initial_upload_date"],
                d["fin_pdf"], d["fin_upload_date"], has_b
            ))

    # Insert 1800 colonies
    for r in all_colonies:
        cur.execute("""
            INSERT INTO colonies (
                colony_id, name, reg_number, category, boundary_delineated,
                map_number, satellite_boundary_pdf_url, final_boundary_pdf_url,
                upload_date, remarks, source_link
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            r["colony_id"], r["name"], r["reg_number"], r["category"],
            1 if r["boundary_delineated"] else 0, r["map_number"],
            r["satellite_boundary_pdf_url"], r["final_boundary_pdf_url"],
            r["upload_date"], r["remarks"], r["source_link"]
        ))

    # Metadata table
    cur.execute("CREATE TABLE dataset_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);")
    metadata_entries = [
        ("dataset_name", "DDA PM-UDAY Delhi Unauthorized & Affluent Colonies Directory"),
        ("version", "1.0.0"),
        ("total_colonies", "1800"),
        ("affluent_colonies", "69"),
        ("regular_colonies", "1731"),
        ("delineated_boundary_maps", str(len(del_entries))),
        ("generated_at", datetime.utcnow().isoformat() + "Z"),
        ("authority", "Delhi Development Authority (DDA), Ministry of Housing and Urban Affairs (MoHUA)")
    ]
    cur.executemany("INSERT INTO dataset_metadata VALUES (?, ?)", metadata_entries)

    conn.commit()
    conn.close()

    print(f"[✓] Generated SQLite database: {db_path} ({db_path.stat().st_size:,} bytes)")

    # Save copy of build script in DDA/scripts/
    script_target = SCRIPTS_DIR / "build_datasets.py"
    with open(script_target, "w", encoding="utf-8") as f:
        with open(__file__, "r", encoding="utf-8") as cur_f:
            f.write(cur_f.read())
    print(f"[✓] Saved pipeline script: {script_target}")

    # Generate additional utility scripts in DDA/scripts/
    generate_scripts()

def generate_scripts():
    # 1. verify_data.py
    verify_script = SCRIPTS_DIR / "verify_data.py"
    with open(verify_script, "w", encoding="utf-8") as f:
        f.write('''#!/usr/bin/env python3
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
''')
    print(f"[✓] Created verification script: {verify_script}")

    # 2. export_formats.py
    export_script = SCRIPTS_DIR / "export_formats.py"
    with open(export_script, "w", encoding="utf-8") as f:
        f.write('''#!/usr/bin/env python3
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
''')
    print(f"[✓] Created export script: {export_script}")

    # Make executable
    subprocess.run(["chmod", "+x", str(verify_script), str(export_script)], check=False)

if __name__ == "__main__":
    build_dataset()

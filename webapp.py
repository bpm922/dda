#!/usr/bin/env python3
"""
DDA Colony Lookup — Windows XP Edition Web App
===============================================
A simple Flask web application serving the DDA PM-UDAY Colony Lookup
with an authentic Windows XP visual style.

Usage:
    pip install flask
    python webapp.py

Then open http://localhost:5000 in your browser.
"""

import json
import os
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder="webapp_static")

# ---------------------------------------------------------------------------
# Data Loading
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).parent / "data"

def load_colonies():
    """Load colonies from JSON dataset."""
    json_path = DATA_DIR / "colonies.json"
    if not json_path.exists():
        print(f"ERROR: {json_path} not found. Run the data pipeline first.")
        return []
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)

COLONIES = load_colonies()
print(f"Loaded {len(COLONIES)} colonies from dataset.")

# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory("webapp_static", "index.html")

@app.route("/api/stats")
def api_stats():
    total = len(COLONIES)
    affluent = sum(1 for c in COLONIES if c["category"] == "affluent")
    regular = sum(1 for c in COLONIES if c["category"] == "regular")
    boundary_yes = sum(1 for c in COLONIES if c.get("boundary_delineated"))
    boundary_no = total - boundary_yes
    has_final_pdf = sum(1 for c in COLONIES if c.get("final_boundary_pdf_url"))
    has_satellite_pdf = sum(1 for c in COLONIES if c.get("satellite_boundary_pdf_url"))
    return jsonify({
        "total": total,
        "affluent": affluent,
        "regular": regular,
        "boundary_delineated": boundary_yes,
        "boundary_pending": boundary_no,
        "final_boundary_pdfs": has_final_pdf,
        "satellite_boundary_pdfs": has_satellite_pdf,
    })

@app.route("/api/search")
def api_search():
    query = request.args.get("q", "").strip().lower()
    category = request.args.get("category", "").strip().lower()
    boundary = request.args.get("boundary", "").strip().lower()
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 50))

    results = COLONIES

    # Filter by category
    if category in ("affluent", "regular"):
        results = [c for c in results if c["category"] == category]

    # Filter by boundary status
    if boundary == "yes":
        results = [c for c in results if c.get("boundary_delineated")]
    elif boundary == "no":
        results = [c for c in results if not c.get("boundary_delineated")]

    # Search by query
    if query:
        tokens = query.split()
        filtered = []
        for c in results:
            searchable = " ".join([
                str(c.get("name", "")),
                str(c.get("reg_number", "")),
                str(c.get("map_number", "")),
                str(c.get("remarks", "")),
            ]).lower()
            if all(t in searchable for t in tokens):
                filtered.append(c)
        results = filtered

    total = len(results)
    start = (page - 1) * per_page
    end = start + per_page
    page_results = results[start:end]

    return jsonify({
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page if per_page else 1,
        "results": page_results,
    })

@app.route("/api/colony/<int:colony_id>")
def api_colony_detail(colony_id):
    for c in COLONIES:
        if c["colony_id"] == colony_id:
            return jsonify(c)
    return jsonify({"error": "Colony not found"}), 404


if __name__ == "__main__":
    print("=" * 60)
    print("  DDA Colony Lookup — Windows XP Edition")
    print("  Open http://localhost:5000 in your browser")
    print("=" * 60)
    app.run(debug=True, host="0.0.0.0", port=5000)

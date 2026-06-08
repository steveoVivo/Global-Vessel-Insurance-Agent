"""
Flask REST API for the Global Vessel Insurance Risk tool.

Endpoints:
  GET /api/data      — per-flag risk scores (with optional year range / weight overrides)
  GET /api/trend     — per-flag historical accident rates + Holt predictions
  GET /api/accidents — individual accident records for a given flag state
"""

import csv
import os

from flask import Flask, jsonify, request

from data_pipeline import DEFAULT_WEIGHTS, build_merged_rows, compute_temporal_trends, normalize_flag_name
from country_lookup import get_country_info

# Absolute path to the accident CSV so the server works from any working directory.
ACCIDENT_CSV = os.path.join(os.path.dirname(__file__), "data", "accident_data_20110101_20251231.csv")

app = Flask(__name__)

# Maps query-parameter names (long and short forms) to their weight key in DEFAULT_WEIGHTS.
# Model selected from evaluation_results_06051335.txt (highest test accuracy,
# accident-rate-excluded variant).
WEIGHT_QUERY_PARAMS = {
    "event_entropy":    ("event_entropy_weight",    "w1"),
    "ship_type":        ("ship_type_weight",         "w2"),
    "open_sea":         ("open_sea_weight",          "w3"),
    "fleet_volatility": ("fleet_volatility_weight",  "w4"),
}


# ---------------------------------------------------------------------------
# Query-parameter helpers
# ---------------------------------------------------------------------------

def float_arg(param_names: tuple[str, ...], default: float) -> float:
    """Read a float from query params, trying each name in order."""
    for name in param_names:
        raw = request.args.get(name)
        if raw is not None:
            try:
                return float(raw)
            except ValueError:
                return default
    return default


def int_arg(param_name: str) -> int | None:
    """Read an optional integer from query params; returns None if absent or invalid."""
    raw = request.args.get(param_name)
    try:
        return int(raw) if raw not in (None, "") else None
    except (TypeError, ValueError):
        return None


def parse_weight_overrides() -> dict[str, float]:
    """Build a weight dict from query params, falling back to DEFAULT_WEIGHTS."""
    return {
        weight_key: float_arg(param_names, DEFAULT_WEIGHTS[weight_key])
        for weight_key, param_names in WEIGHT_QUERY_PARAMS.items()
    }


# ---------------------------------------------------------------------------
# Response builders
# ---------------------------------------------------------------------------

def build_flag_payload(row: dict) -> dict:
    """Convert a merged risk row into the JSON payload for one flag state."""
    country_code, coordinates = get_country_info(row["flag_key"])
    return {
        "flag":                 row["flag"],
        "country_code":         country_code,
        "coordinates":          coordinates,
        "vessel_count":         row["fleet_size"],
        "risk_score":           row["risk_score"],
        # Normalised component scores used by the selected model
        "event_entropy_norm":   row["event_entropy_norm"],
        "ship_type_risk_norm":  row["ship_type_risk_norm"],
        "open_sea_rate_norm":   row["open_sea_rate_norm"],
        "fleet_volatility_norm": row["fleet_volatility_norm"],
    }


def build_risk_response() -> dict:
    """Run the risk pipeline and return the full /api/data response dict."""
    start_year = int_arg("start_year")
    end_year   = int_arg("end_year")
    weights    = parse_weight_overrides()
    rows       = build_merged_rows(start_year=start_year, end_year=end_year, weights=weights)
    return {
        "count": len(rows),
        "data":  [build_flag_payload(row) for row in rows],
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return "<h1>This is the Flask API. The React app is served at http://localhost:5173/</h1>"


@app.route("/api/test")
def health_check():
    return jsonify({"message": "If you see this message, BOTH your React AND Flask environments are working"})


@app.route("/api/data")
def get_risk_data():
    """Return per-flag risk scores, optionally filtered by year range and weight overrides."""
    return jsonify(build_risk_response())


@app.route("/api/trend")
def get_trend_data():
    """Return per-flag yearly/monthly accident rates and Holt trend predictions."""
    trends = compute_temporal_trends()
    return jsonify({"count": len(trends), "data": trends})


@app.route("/api/accidents")
def get_accidents():
    """Return all recorded accidents for the flag state named in the `country` query param."""
    country_name = request.args.get("country", "").strip()
    if not country_name:
        return jsonify({"error": "country parameter required"}), 400

    target_key = normalize_flag_name(country_name)
    accident_records = []

    try:
        with open(ACCIDENT_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw_flags = row.get("Flag Administrations", "")
                flag_keys = {normalize_flag_name(f) for f in raw_flags.split(",") if f.strip()}
                if target_key not in flag_keys:
                    continue

                severity = row.get("Casualty severity", "").strip()
                # Skip cells where the severity field contains non-severity data
                # (e.g. coordinates or digits — a known CSV parse artifact).
                if not severity or severity[0].isdigit() or "°" in severity:
                    severity = ""

                accident_records.append({
                    "reference":        row.get("Reference", ""),
                    "num_ships":        row.get("Number of ships involved", ""),
                    "ships":            row.get("Ships involved", ""),
                    "solas_status":     row.get("SOLAS status", ""),
                    "flags":            raw_flags,
                    "ship_types":       row.get("Ship types", ""),
                    "date":             row.get("Occurrence date and time", ""),
                    "event":            row.get("Casualty event", ""),
                    "severity":         severity,
                    "geo_coordinates":  row.get("Coordinates", ""),
                    "place":            row.get("Place", ""),
                    "location":         row.get("Location", ""),
                    "num_reports":      row.get("Number of investigation reports", ""),
                    "reporting_admins": row.get("Administrations submitting investigation reports", ""),
                })
    except FileNotFoundError:
        return jsonify({"error": "Accident data file not found"}), 500

    # Most-recent accidents first
    accident_records.sort(key=lambda x: x["date"], reverse=True)
    return jsonify({"country": country_name, "count": len(accident_records), "data": accident_records})


if __name__ == "__main__":
    app.run(port=5000, debug=True)

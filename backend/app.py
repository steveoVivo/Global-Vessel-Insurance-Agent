import csv
import os

from flask import Flask, jsonify, request

from data_pipeline import DEFAULT_WEIGHTS, build_merged_rows, compute_temporal_trends, normalize_flag_name
from country_lookup import get_country_info

ACCIDENT_CSV = os.path.join(os.path.dirname(__file__), "data", "accident_data_20110101_20251231.csv")


app = Flask(__name__)

WEIGHT_ARGS = {
    # Selected accident-rate-excluded model from evaluation_results_06050020.txt (highest test acc).
    "event_entropy":         ("event_entropy_weight",         "w1"),
    "ship_type":             ("ship_type_weight",             "w2"),
    "open_sea":              ("open_sea_weight",              "w3"),
}


def float_arg(names, default):
    for name in names:
        value = request.args.get(name)
        if value is not None:
            try:
                return float(value)
            except ValueError:
                return default
    return default


def int_arg(name):
    value = request.args.get(name)
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def get_weights():
    return {
        key: float_arg(names, DEFAULT_WEIGHTS[key])
        for key, names in WEIGHT_ARGS.items()
    }


def flag_risk_payload(row):
    country_code, coordinates = get_country_info(row["flag_key"])
    return {
        "flag":                    row["flag"],
        "country_code":            country_code,
        "coordinates":             coordinates,
        "vessel_count":            row["fleet_size"],
        "risk_score":              row["risk_score"],
        # Selected non-accident components (evaluation_results_06050020.txt, highest test acc).
        "event_entropy_norm":      row["event_entropy_norm"],
        "ship_type_risk_norm":     row["ship_type_risk_norm"],
        "open_sea_rate_norm":      row["open_sea_rate_norm"],
    }


def get_risk_payload():
    start_year = int_arg("start_year")
    end_year = int_arg("end_year")
    weights = get_weights()
    rows = build_merged_rows(start_year=start_year, end_year=end_year, weights=weights)
    return {
        "count": len(rows),
        "data": [flag_risk_payload(row) for row in rows],
    }


@app.route("/")
def entrypoint():
    return "<h1>This is the Flask API. The React app is served at http://localhost:5173/</h1>"


@app.route("/api/test")
def get_test_message():
    return jsonify({"message": "If you see this message, BOTH your React AND Flask environments are working"})


@app.route("/api/data")
def get_data():
    return jsonify(get_risk_payload())


@app.route("/api/trend")
def get_trends():
    trends = compute_temporal_trends()
    return jsonify({"count": len(trends), "data": trends})


@app.route("/api/accidents")
def get_accidents():
    country = request.args.get("country", "").strip()
    if not country:
        return jsonify({"error": "country parameter required"}), 400

    target_key = normalize_flag_name(country)
    accidents = []
    try:
        with open(ACCIDENT_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                flags = row.get("Flag Administrations", "")
                flag_keys = {normalize_flag_name(f) for f in flags.split(",") if f.strip()}
                if target_key not in flag_keys:
                    continue
                severity = row.get("Casualty severity", "").strip()
                # Skip rows where severity field contains non-severity data (CSV parse artifacts)
                if not severity or severity[0].isdigit() or "°" in severity:
                    severity = ""
                accidents.append({
                    "reference":        row.get("Reference", ""),
                    "num_ships":        row.get("Number of ships involved", ""),
                    "ships":            row.get("Ships involved", ""),
                    "solas_status":     row.get("SOLAS status", ""),
                    "flags":            flags,
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

    accidents.sort(key=lambda x: x["date"], reverse=True)
    return jsonify({"country": country, "count": len(accidents), "data": accidents})


if __name__ == "__main__":
    app.run(port=5000, debug=True)

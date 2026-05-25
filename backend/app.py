from flask import Flask, jsonify, request

from data_pipeline import DEFAULT_WEIGHTS, build_merged_rows


app = Flask(__name__)

WEIGHT_ARGS = {
    "accident_rate": ("accident_rate_weight", "w1"),
    "severity": ("severity_weight", "w2"),
    "ship_type": ("ship_type_weight", "w3"),
    "flag_safety": ("flag_safety_weight", "w4"),
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
    return {
        "flag": row["flag"],
        "vessel_count": row["fleet_size"],
        "risk_score": row["risk_score"],
        "accident_rate_norm": row["accident_rate_norm"],
        "severity_risk_norm": row["severity_risk_norm"],
        "ship_type_risk_norm": row["ship_type_risk_norm"],
        "flag_safety_risk_norm": row["flag_safety_risk_norm"],
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

if __name__ == "__main__":
    app.run(port=5000, debug=True)

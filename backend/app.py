from flask import Flask, jsonify, request

from data_pipeline import DEFAULT_WEIGHTS, build_merged_rows, compute_temporal_trends


app = Flask(__name__)

WEIGHT_ARGS = {
    # Original 4 components (frontend sliders control these)
    "accident_rate":         ("accident_rate_weight",         "w1"),
    "severity":              ("severity_weight",               "w2"),
    "ship_type":             ("ship_type_weight",              "w3"),
    "flag_safety":           ("flag_safety_weight",            "w4"),
    # Extended components (API query-param only)
    "trend":                 ("trend_weight",                  "w5"),
    "multi_ship":            ("multi_ship_weight",             "w6"),
    "collision":             ("collision_weight",              "w7"),
    "open_sea":              ("open_sea_weight",               "w8"),
    "event_entropy":         ("event_entropy_weight",          "w9"),
    "investigation":         ("investigation_weight",          "w10"),
    "solas_noncompliance":   ("solas_noncompliance_weight",    "w11"),
    "excess_factor":         ("excess_factor_weight",          "w12"),
    "excess_factor_trend":   ("excess_factor_trend_weight",    "w13"),
    "fleet_growth":          ("fleet_growth_weight",           "w14"),
    "fleet_volatility":      ("fleet_volatility_weight",       "w15"),
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
        # Core fields (frontend uses these 4 + risk_score + vessel_count)
        "flag":                    row["flag"],
        "vessel_count":            row["fleet_size"],
        "risk_score":              row["risk_score"],
        "accident_rate_norm":      row["accident_rate_norm"],
        "severity_risk_norm":      row["severity_risk_norm"],
        "ship_type_risk_norm":     row["ship_type_risk_norm"],
        "flag_safety_risk_norm":   row["flag_safety_risk_norm"],  # = detention rate norm
        # Extended fields (frontend ignores; available for external API consumers)
        "trend_slope_norm":            row["trend_slope_norm"],
        "multi_ship_rate_norm":        row["multi_ship_rate_norm"],
        "collision_rate_norm":         row["collision_rate_norm"],
        "open_sea_rate_norm":          row["open_sea_rate_norm"],
        "event_entropy_norm":          row["event_entropy_norm"],
        "investigation_rate_norm":     row["investigation_rate_norm"],
        "solas_noncompliance_norm":    row["solas_noncompliance_norm"],
        "excess_factor_norm":          row["excess_factor_norm"],
        "excess_factor_trend_norm":    row["excess_factor_trend_norm"],
        "fleet_growth_norm":           row["fleet_growth_norm"],
        "fleet_volatility_norm":       row["fleet_volatility_norm"],
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
@app.route("/api/trends")
def get_trends():
    trends = compute_temporal_trends()
    return jsonify({"count": len(trends), "data": trends})


if __name__ == "__main__":
    app.run(port=5000, debug=True)

import csv
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
ACCIDENT_CSV = BASE_DIR / "accident_data_2020200101_20250508.csv"
FLEET_CSV = BASE_DIR / "Num_of_ships_by_flag.csv"
PARIS_PDFS = {
    "black": BASE_DIR / "Paris MoU Black List 2024.pdf",
    "grey": BASE_DIR / "Paris MoU Grey List 2024.pdf",
    "white": BASE_DIR / "Paris MoU White List 2024.pdf",
}

PARIS_CSV = BASE_DIR / "paris_mou_2024.csv"
ACCIDENT_RISK_CSV = BASE_DIR / "accident_risk_by_flag.csv"
MERGED_CSV = BASE_DIR / "merged_vessel_risk_by_flag.csv"

PARIS_FIELDS = [
    "flag",
    "flag_key",
    "paris_mou_category",
    "paris_rank",
    "paris_inspections_2022_2024",
    "paris_detentions_2022_2024",
    "paris_black_to_grey_limit",
    "paris_grey_to_white_limit",
    "paris_risk_text",
    "paris_excess_factor",
    "flag_safety_risk",
]

ACCIDENT_RISK_FIELDS = [
    "flag",
    "flag_key",
    "accident_count",
    "avg_severity_risk",
    "avg_ship_type_risk",
]

MERGED_FIELDS = [
    "flag",
    "flag_key",
    "fleet_size",
    "accident_count",
    "accident_rate",
    "accident_rate_norm",
    "avg_severity_risk",
    "severity_risk_norm",
    "avg_ship_type_risk",
    "ship_type_risk_norm",
    "paris_mou_category",
    "paris_rank",
    "paris_inspections_2022_2024",
    "paris_detentions_2022_2024",
    "paris_excess_factor",
    "flag_safety_risk",
    "flag_safety_risk_norm",
    "risk_score",
]

DEFAULT_WEIGHTS = {
    "accident_rate": 0.25,
    "severity": 0.25,
    "ship_type": 0.25,
    "flag_safety": 0.25,
}


NAME_ALIASES = {
    "bahamas, the": "bahamas",
    "bermuda (uk)": "bermuda",
    "cayman islands (uk)": "cayman islands",
    "gibraltar (uk)": "gibraltar",
    "hong kong (china)": "hong kong",
    "hong kong, china": "hong kong",
    "iran (islamic republic of)": "iran",
    "isle of man (uk)": "isle of man",
    "jersey (uk)": "jersey",
    "korea, republic of": "south korea",
    "mar (portugal)": "portugal",
    "moldova, republic of": "moldova",
    "republic of korea": "south korea",
    "russian federation": "russia",
    "saint kitts and nevis": "st. kitts and nevis",
    "saint vincent and the grenadines": "st. vincent and the grenadines",
    "st vincent and the grenadines": "st. vincent and the grenadines",
    "tanzania, united republic of": "tanzania",
    "turkiye": "turkiye",
    "türkiye": "turkiye",
    "united states": "united states of america",
    "venezuela (bolivarian republic of)": "venezuela",
    "viet nam": "vietnam",
    "zanzibar (united republic of tanzania)": "tanzania",
}

COMMA_NAME_PLACEHOLDERS = {
    "Hong Kong, China": "__HONG_KONG_CHINA__",
    "Korea, Republic of": "__KOREA_REPUBLIC_OF__",
    "Moldova, Republic of": "__MOLDOVA_REPUBLIC_OF__",
    "Tanzania, United Republic of": "__TANZANIA_UNITED_REPUBLIC_OF__",
}

REGION_ROWS = {
    "africa",
    "northern africa",
    "sub-saharan africa",
    "eastern africa",
    "middle africa",
    "southern africa",
    "western africa",
    "americas",
    "northern america",
    "latin america and the caribbean",
    "caribbean",
    "central america",
    "south america",
    "asia",
    "central asia",
    "eastern asia",
    "south-eastern asia",
    "southern asia",
    "western asia",
    "europe",
    "eastern europe",
    "northern europe",
    "southern europe",
    "western europe",
    "oceania",
    "australia and new zealand",
    "oceania excluding australia and new zealand",
    "world",
    "developing economies",
    "developed economies",
}

SEVERITY_SCORES = {
    "marine incident": 0.25,
    "marine casualty": 0.65,
    "very serious marine casualty": 1.0,
}

PARIS_SAFETY_SCORES = {
    "white": 0.0,
    "grey": 0.5,
    "black": 1.0,
}


def normalize_flag_name(name):
    cleaned = re.sub(r"\s+", " ", (name or "").strip())
    cleaned = cleaned.replace("’", "'")
    cleaned = re.sub(
        r"\s*\([^)]*\)\s*$",
        lambda m: m.group(0) if "(UK)" in m.group(0) or "(China)" in m.group(0) else "",
        cleaned,
    )
    key = cleaned.casefold()
    key = NAME_ALIASES.get(key, key)
    key = re.sub(r"[^\w\s.]", " ", key)
    key = re.sub(r"\s+", " ", key).strip()
    return key


def split_flag_administrations(value):
    cleaned = re.sub(r"\s+", " ", (value or "").strip())
    if not cleaned:
        return []

    placeholder_to_name = {value: key for key, value in COMMA_NAME_PLACEHOLDERS.items()}
    for original, placeholder in COMMA_NAME_PLACEHOLDERS.items():
        cleaned = cleaned.replace(original, placeholder)

    flags = []
    seen = set()
    for flag in re.split(r"\s*,\s*|\s*;\s*", cleaned):
        flag = placeholder_to_name.get(flag.strip(), flag.strip())
        flag_key = normalize_flag_name(flag)
        if not flag or flag_key in {"", "unknown"} or flag_key in seen:
            continue
        flags.append(flag)
        seen.add(flag_key)
    return flags


def parse_int(value, default=0):
    try:
        return int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def parse_float(value, default=0.0):
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def minmax(values):
    values = [v for v in values if v is not None]
    if not values:
        return lambda _: 0.0
    lo, hi = min(values), max(values)
    if hi == lo:
        return lambda _: 0.0
    return lambda value: (value - lo) / (hi - lo)


def extract_pdf_text(pdf_path):
    output = subprocess.check_output(
        [
            "gs",
            "-q",
            "-dNOPAUSE",
            "-dBATCH",
            "-sDEVICE=txtwrite",
            "-sOutputFile=-",
            str(pdf_path),
        ],
        text=True,
    )
    return output


def parse_paris_text(text, category):
    rows = []
    for line in text.splitlines():
        match = re.match(
            r"^\s*(\d+)\s+(.+?)\s+([\d,]+)\s+(\d+)\s+(\d+)(?:\s+(\d+))?(?:\s+([A-Za-z ]+?))?\s+(-?\d+\.\d+)\s*$",
            line,
        )
        if not match:
            continue

        rank, flag, inspections, detentions, black_to_grey, grey_to_white, risk_text, excess = match.groups()
        rows.append(
            {
                "flag": flag.strip(),
                "flag_key": normalize_flag_name(flag),
                "paris_mou_category": category,
                "paris_rank": parse_int(rank),
                "paris_inspections_2022_2024": parse_int(inspections),
                "paris_detentions_2022_2024": parse_int(detentions),
                "paris_black_to_grey_limit": parse_int(black_to_grey),
                "paris_grey_to_white_limit": parse_int(grey_to_white, None) if grey_to_white else None,
                "paris_risk_text": (risk_text or "").strip(),
                "paris_excess_factor": parse_float(excess),
                "flag_safety_risk": PARIS_SAFETY_SCORES[category],
            }
        )
    return rows


def write_csv(path, rows, fieldnames):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_paris_mou_csv(output_path=PARIS_CSV):
    rows = []
    for category, pdf_path in PARIS_PDFS.items():
        rows.extend(parse_paris_text(extract_pdf_text(pdf_path), category))

    rows.sort(key=lambda row: row["paris_rank"])
    write_csv(output_path, rows, PARIS_FIELDS)
    return rows


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def accident_date(row):
    value = row.get("Occurrence date and time", "")
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def load_fleet_rows():
    rows = []
    for row in read_csv(FLEET_CSV):
        flag = row.get("Economy_Label", "").strip()
        flag_key = normalize_flag_name(flag)
        if flag_key in REGION_ROWS:
            continue
        fleet_size = parse_int(row.get("2025_Number_of_ships_Value"))
        rows.append(
            {
                "flag": flag,
                "flag_key": flag_key,
                "fleet_size": fleet_size,
            }
        )
    return rows


def load_paris_rows():
    if not PARIS_CSV.exists():
        return build_paris_mou_csv()
    return read_csv(PARIS_CSV)


def load_accident_rows(start_year=None, end_year=None):
    rows = []
    for row in read_csv(ACCIDENT_CSV):
        date = accident_date(row)
        if start_year and (not date or date.year < start_year):
            continue
        if end_year and (not date or date.year > end_year):
            continue
        for flag in split_flag_administrations(row.get("Flag Administrations", "")):
            flag_key = normalize_flag_name(flag)
            if not flag_key or flag_key in REGION_ROWS:
                continue
            rows.append({**row, "flag": flag, "flag_key": flag_key, "date": date})
    return rows


def compute_accident_metrics(start_year=None, end_year=None):
    accidents = load_accident_rows(start_year, end_year)
    ship_type_counts = Counter(
        row.get("Ship types", "").strip()
        for row in accidents
        if row.get("Ship types", "").strip()
    )
    max_ship_type_count = max(ship_type_counts.values(), default=1)
    ship_type_risk = {
        ship_type: count / max_ship_type_count for ship_type, count in ship_type_counts.items()
    }

    by_flag = defaultdict(
        lambda: {
            "flag": "",
            "flag_key": "",
            "accident_count": 0,
            "severity_total": 0.0,
            "severity_count": 0,
            "ship_type_risk_total": 0.0,
            "ship_type_count": 0,
        }
    )

    for row in accidents:
        bucket = by_flag[row["flag_key"]]
        bucket["flag"] = row["flag"]
        bucket["flag_key"] = row["flag_key"]
        bucket["accident_count"] += 1

        severity = SEVERITY_SCORES.get(row.get("Casualty severity", "").strip().casefold())
        if severity is not None:
            bucket["severity_total"] += severity
            bucket["severity_count"] += 1

        ship_type = row.get("Ship types", "").strip()
        if ship_type:
            bucket["ship_type_risk_total"] += ship_type_risk.get(ship_type, 0.0)
            bucket["ship_type_count"] += 1

    metrics = []
    for bucket in by_flag.values():
        severity_count = bucket.pop("severity_count")
        ship_type_count = bucket.pop("ship_type_count")
        severity_total = bucket.pop("severity_total")
        ship_type_risk_total = bucket.pop("ship_type_risk_total")
        bucket["avg_severity_risk"] = severity_total / severity_count if severity_count else 0.0
        bucket["avg_ship_type_risk"] = ship_type_risk_total / ship_type_count if ship_type_count else 0.0
        metrics.append(bucket)

    metrics.sort(key=lambda row: row["flag"])
    return metrics


def build_merged_rows(start_year=None, end_year=None, weights=None):
    weights = weights or DEFAULT_WEIGHTS

    fleet_by_key = {row["flag_key"]: row for row in load_fleet_rows()}
    paris_by_key = {row["flag_key"]: row for row in load_paris_rows()}
    accident_by_key = {row["flag_key"]: row for row in compute_accident_metrics(start_year, end_year)}
    all_keys = sorted(set(fleet_by_key) | set(paris_by_key) | set(accident_by_key))

    rows = []
    for key in all_keys:
        fleet = fleet_by_key.get(key, {})
        paris = paris_by_key.get(key, {})
        accident = accident_by_key.get(key, {})
        fleet_size = parse_int(fleet.get("fleet_size"))
        accident_count = parse_int(accident.get("accident_count"))
        accident_rate = accident_count / fleet_size if fleet_size else 0.0
        rows.append(
            {
                "flag": fleet.get("flag") or paris.get("flag") or accident.get("flag") or key.title(),
                "flag_key": key,
                "fleet_size": fleet_size,
                "accident_count": accident_count,
                "accident_rate": accident_rate,
                "avg_severity_risk": parse_float(accident.get("avg_severity_risk")),
                "avg_ship_type_risk": parse_float(accident.get("avg_ship_type_risk")),
                "paris_mou_category": paris.get("paris_mou_category", "unlisted"),
                "paris_rank": paris.get("paris_rank", ""),
                "paris_inspections_2022_2024": paris.get("paris_inspections_2022_2024", ""),
                "paris_detentions_2022_2024": paris.get("paris_detentions_2022_2024", ""),
                "paris_excess_factor": paris.get("paris_excess_factor", ""),
                "flag_safety_risk": parse_float(paris.get("flag_safety_risk"), 0.5),
            }
        )

    accident_rate_norm = minmax([row["accident_rate"] for row in rows])
    severity_norm = minmax([row["avg_severity_risk"] for row in rows])
    ship_type_norm = minmax([row["avg_ship_type_risk"] for row in rows])

    total_weight = sum(weights.values()) or 1.0
    for row in rows:
        row["accident_rate_norm"] = accident_rate_norm(row["accident_rate"])
        row["severity_risk_norm"] = severity_norm(row["avg_severity_risk"])
        row["ship_type_risk_norm"] = ship_type_norm(row["avg_ship_type_risk"])
        row["flag_safety_risk_norm"] = row["flag_safety_risk"]
        row["risk_score"] = (
            weights["accident_rate"] * row["accident_rate_norm"]
            + weights["severity"] * row["severity_risk_norm"]
            + weights["ship_type"] * row["ship_type_risk_norm"]
            + weights["flag_safety"] * row["flag_safety_risk_norm"]
        ) / total_weight

    rows.sort(key=lambda row: row["risk_score"], reverse=True)
    return rows


def build_output_csvs():
    paris_rows = build_paris_mou_csv()
    accident_rows = compute_accident_metrics()
    write_csv(ACCIDENT_RISK_CSV, accident_rows, ACCIDENT_RISK_FIELDS)

    merged_rows = build_merged_rows()
    write_csv(MERGED_CSV, merged_rows, MERGED_FIELDS)
    return {
        "paris_mou_rows": len(paris_rows),
        "accident_risk_rows": len(accident_rows),
        "merged_rows": len(merged_rows),
        "outputs": [str(PARIS_CSV), str(ACCIDENT_RISK_CSV), str(MERGED_CSV)],
    }


if __name__ == "__main__":
    summary = build_output_csvs()
    for key, value in summary.items():
        print(f"{key}: {value}")

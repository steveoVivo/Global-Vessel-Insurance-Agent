"""
Core data pipeline for the Global Vessel Insurance Risk tool.

Responsibilities:
  - Load and normalize fleet, accident, and Paris MoU data from CSV files.
  - Compute per-flag accident metrics, trend slopes, and fleet features.
  - Assemble and normalize a composite risk score for each flag state.
  - Produce temporal trend series (yearly + monthly) for the trend chart.
"""

import csv
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from temporal_trend_prediction import predict as holt_predict


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR  = BASE_DIR / "data"

ACCIDENT_CSV = DATA_DIR / "accident_data_20110101_20251231.csv"
FLEET_CSV    = DATA_DIR / "Num_of_ships_by_flag.csv"
PARIS_CSV    = DATA_DIR / "paris_mou.csv"

# Years covered by the fleet-size CSV (one column per year)
FLEET_YEARS = list(range(2011, 2026))


# ---------------------------------------------------------------------------
# Risk component weights
# ---------------------------------------------------------------------------
# Default model: accident-rate-excluded, selected from evaluation_results_06051335.txt
# (highest Spearman r vs test-period accident rates).
# Components: event_entropy + ship_type + open_sea + fleet_volatility, each weighted 1/4.
DEFAULT_WEIGHTS = {
    "accident_rate":       0.00,
    "event_entropy":       1/4,    # Shannon entropy of accident-event types (diversity of causes)
    "trend":               0.00,
    "investigation":       0.00,
    "flag_safety":         0.00,
    "severity":            0.00,
    "ship_type":           1/4,    # accident-proneness of the vessel types registered under the flag
    "multi_ship":          0.00,
    "collision":           0.00,
    "open_sea":            1/4,    # fraction of accidents that occurred in open-sea locations
    "solas_noncompliance": 0.00,
    "excess_factor":       0.00,
    "excess_factor_trend": 0.00,
    "fleet_growth":        0.00,
    "fleet_volatility":    1/4,    # RMSE of annual fleet-size changes / mean fleet size
}


# ---------------------------------------------------------------------------
# Flag-name normalization
# ---------------------------------------------------------------------------

# Alternate or official long-form names → short canonical keys used throughout the pipeline.
# Keys and values are both lowercased (casefold) to match normalize_flag_name output.
NAME_ALIASES = {
    "bahamas, the":                        "bahamas",
    "bermuda (uk)":                        "bermuda",
    "cayman islands (uk)":                 "cayman islands",
    "gibraltar (uk)":                      "gibraltar",
    "hong kong (china)":                   "hong kong",
    "hong kong, china":                    "hong kong",
    "iran (islamic republic of)":          "iran",
    "isle of man (uk)":                    "isle of man",
    "jersey (uk)":                         "jersey",
    "korea, republic of":                  "south korea",
    "mar (portugal)":                      "portugal",
    "moldova, republic of":                "moldova",
    "republic of korea":                   "south korea",
    "russian federation":                  "russia",
    "saint kitts and nevis":               "st. kitts and nevis",
    "saint vincent and the grenadines":    "st. vincent and the grenadines",
    "st vincent and the grenadines":       "st. vincent and the grenadines",
    "tanzania, united republic of":        "tanzania",
    "turkiye":                             "turkiye",
    "türkiye":                             "turkiye",
    "united states":                       "united states of america",
    "venezuela (bolivarian republic of)":  "venezuela",
    "viet nam":                            "vietnam",
    "zanzibar (united republic of tanzania)": "tanzania",
    # Accident CSV names that differ from fleet CSV canonical keys
    "cape verde":                          "cabo verde",
    "turkey":                              "turkiye",
    "north korea":                         "dem. people s rep. of korea",
    "czech republic":                      "czechia",
    "myanmar [burma]":                     "myanmar",
    "congo [drc]":                         "dem. rep. of the congo",
    "são tomé and príncipe":               "sao tome and principe",
    "falkland islands [islas malvinas]":   "falkland islands",
    "st. vincent and grenadines":          "st. vincent and the grenadines",
    "republic of south korea korea":       "south korea",
    # Fleet CSV official names → canonical short keys
    "china, hong kong sar":                "hong kong",
    "china, macao sar":                    "macau",
    "china, taiwan province of":           "taiwan",
    "united republic of tanzania":         "tanzania",
    "republic of moldova":                 "moldova",
    "syrian arab republic":                "syria",
}

# Countries whose names contain commas need temporary placeholders before splitting
# the comma-separated "Flag Administrations" field in the accident CSV.
COMMA_NAME_PLACEHOLDERS = {
    "Hong Kong, China":              "__HONG_KONG_CHINA__",
    "Korea, Republic of":            "__KOREA_REPUBLIC_OF__",
    "Moldova, Republic of":          "__MOLDOVA_REPUBLIC_OF__",
    "Tanzania, United Republic of":  "__TANZANIA_UNITED_REPUBLIC_OF__",
}

# Fleet CSV rows representing regional or aggregate totals — skip these.
REGION_ROWS = {
    "africa", "northern africa", "sub-saharan africa",
    "eastern africa", "middle africa", "southern africa", "western africa",
    "americas", "northern america", "latin america and the caribbean",
    "caribbean", "central america", "south america",
    "asia", "central asia", "eastern asia", "south-eastern asia", "southern asia", "western asia",
    "europe", "eastern europe", "northern europe", "southern europe", "western europe",
    "oceania", "australia and new zealand", "oceania excluding australia and new zealand",
    "world", "developing economies", "developed economies", "individual economies",
}

# Numeric severity levels for three IMO casualty categories
SEVERITY_SCORES = {
    "marine incident":              0.25,
    "marine casualty":              0.65,
    "very serious marine casualty": 1.00,
}


def normalize_flag_name(name: str) -> str:
    """Return a canonical lowercase key for a flag-state name.

    Steps:
      1. Collapse whitespace and strip leading/trailing spaces.
      2. Remove trailing parenthesised suffixes UNLESS they are "(UK)" or "(China)",
         which distinguish dependent territories with their own flag registries.
      3. Casefold and apply NAME_ALIASES.
      4. Strip punctuation except periods (needed for "St." names).
    """
    cleaned = re.sub(r"\s+", " ", (name or "").strip())
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


def split_flag_administrations(raw_value: str) -> list[str]:
    """Split the "Flag Administrations" CSV cell into individual flag name strings.

    The cell uses commas as separators, but some country names themselves contain
    commas (e.g. "Korea, Republic of").  These are temporarily replaced with
    placeholder tokens before splitting.
    """
    cleaned = re.sub(r"\s+", " ", (raw_value or "").strip())
    if not cleaned:
        return []

    placeholder_to_name = {v: k for k, v in COMMA_NAME_PLACEHOLDERS.items()}
    for original, placeholder in COMMA_NAME_PLACEHOLDERS.items():
        cleaned = cleaned.replace(original, placeholder)

    flags, seen_keys = [], set()
    for token in re.split(r"\s*,\s*|\s*;\s*", cleaned):
        flag_name = placeholder_to_name.get(token.strip(), token.strip())
        flag_key  = normalize_flag_name(flag_name)
        if not flag_name or flag_key in {"", "unknown"} or flag_key in seen_keys:
            continue
        flags.append(flag_name)
        seen_keys.add(flag_key)
    return flags


# ---------------------------------------------------------------------------
# Generic parsing helpers
# ---------------------------------------------------------------------------

def parse_int(value, default: int = 0) -> int:
    """Parse a possibly comma-formatted integer string; return default on failure."""
    try:
        return int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def parse_float(value, default: float = 0.0) -> float:
    """Parse a possibly comma-formatted float string; return default on failure."""
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Normalization utilities
# ---------------------------------------------------------------------------

def minmax_capped(values: list, percentile: int = 95):
    """Return a min-max normalization function capped at the given percentile.

    Capping prevents a handful of extreme outliers from compressing the rest
    of the distribution near zero.  Values above the cap are clamped to 1.0.
    Flags with value == 0 map to 0.0.

    Returns a callable: f(v) -> float in [0, 1].
    """
    nonzero_values = sorted(v for v in values if v is not None and v > 0)
    if not nonzero_values:
        return lambda _: 0.0
    cap_index = min(int(len(nonzero_values) * percentile / 100), len(nonzero_values) - 1)
    cap = nonzero_values[cap_index]
    if cap <= 0:
        return lambda _: 0.0
    return lambda v: min((v if v is not None else 0.0) / cap, 1.0)


def ols_slope(xy_pairs: list) -> float:
    """Ordinary Least Squares slope for a list of (x, y) pairs.

    Returns 0.0 when fewer than 3 points are available (not enough for a
    meaningful trend estimate).
    """
    if len(xy_pairs) < 3:
        return 0.0
    xs = [p[0] for p in xy_pairs]
    ys = [p[1] for p in xy_pairs]
    n   = len(xs)
    sx  = sum(xs);  sy  = sum(ys)
    sxy = sum(x * y for x, y in zip(xs, ys))
    sx2 = sum(x * x for x in xs)
    denominator = n * sx2 - sx ** 2
    return (n * sxy - sx * sy) / denominator if denominator else 0.0


def shannon_entropy(event_counts: dict) -> float:
    """Shannon entropy (bits) of a distribution given as {label: count}."""
    total = sum(event_counts.values())
    if total == 0:
        return 0.0
    return -sum((c / total) * math.log2(c / total) for c in event_counts.values() if c > 0)


# ---------------------------------------------------------------------------
# Fleet size interpolation
# ---------------------------------------------------------------------------

def interpolate_fleet_size(annual_sizes: dict, year: int, month: int) -> float:
    """Linearly interpolate fleet size within a year using annual snapshots.

    Formula:
        monthly_increment = (fleet[year+1] - fleet[year]) / 12
        fleet_at_month    = fleet[year] + monthly_increment * (month - 1)

    Falls back to fleet[year] if the following year is unavailable.
    Returns 0.0 if the year itself has no data.
    """
    fleet_current = annual_sizes.get(year, 0)
    if fleet_current <= 0:
        return 0.0
    fleet_next = annual_sizes.get(year + 1, 0)
    if fleet_next > 0:
        return fleet_current + (fleet_next - fleet_current) / 12 * (month - 1)
    return float(fleet_current)


def year_exposure(annual_sizes: dict, year: int) -> float:
    """Total ship-year exposure for one calendar year (average of 12 monthly snapshots)."""
    return sum(interpolate_fleet_size(annual_sizes, year, month) for month in range(1, 13)) / 12


# ---------------------------------------------------------------------------
# CSV loaders
# ---------------------------------------------------------------------------

def read_csv(path: Path) -> list[dict]:
    """Read a CSV file and return a list of row dicts (UTF-8 with BOM support)."""
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def parse_accident_date(row: dict):
    """Extract a date object from a row's 'Occurrence date and time' field, or None."""
    raw = row.get("Occurrence date and time", "")
    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def load_fleet_rows() -> list[dict]:
    """Load 2025 fleet sizes per flag from the fleet CSV.

    Returns one dict per flag: {flag, flag_key, fleet_size}.
    When multiple rows exist for the same flag key (e.g. from differently named
    entries), keeps the row with the largest fleet size.
    """
    best_by_key: dict = {}
    for row in read_csv(FLEET_CSV):
        flag_name = row.get("Economy_Label", "").strip()
        flag_key  = normalize_flag_name(flag_name)
        if flag_key in REGION_ROWS:
            continue
        fleet_size = parse_int(row.get("2025_Number_of_ships_Value"))
        if flag_key not in best_by_key or fleet_size > best_by_key[flag_key]["fleet_size"]:
            best_by_key[flag_key] = {"flag": flag_name, "flag_key": flag_key, "fleet_size": fleet_size}
    return list(best_by_key.values())


def load_fleet_by_year() -> dict:
    """Load annual fleet sizes for all flags from the fleet CSV.

    Returns {flag_key: (display_name, {year: fleet_size})}.
    When multiple rows share a key (e.g. "Sudan (...2011)"), missing years are
    filled in from the secondary row so the series is as complete as possible.
    """
    fleet_series: dict = {}
    for row in read_csv(FLEET_CSV):
        flag_name = row.get("Economy_Label", "").strip()
        flag_key  = normalize_flag_name(flag_name)
        if flag_key in REGION_ROWS:
            continue

        year_sizes = {
            year: size
            for year in FLEET_YEARS
            for size in [parse_int(row.get(f"{year}_Number_of_ships_Value", ""))]
            if size > 0
        }
        if not year_sizes:
            continue

        existing = fleet_series.get(flag_key)
        if existing is None:
            fleet_series[flag_key] = (flag_name, year_sizes)
        else:
            # Merge: fill gaps in the primary row from secondary rows
            merged = dict(existing[1])
            for yr, sz in year_sizes.items():
                if yr not in merged:
                    merged[yr] = sz
            fleet_series[flag_key] = (existing[0], merged)
    return fleet_series


def load_paris_data() -> list[dict]:
    """Load multi-year Paris MoU data from paris_mou.csv.

    Returns one dict per (flag, year) row.
    """
    rows = []
    for row in read_csv(PARIS_CSV):
        flag_name = row.get("flag", "").strip()
        flag_key  = normalize_flag_name(flag_name)
        if not flag_key:
            continue
        rows.append({
            "year":             parse_int(row.get("year", 0)),
            "flag":             flag_name,
            "flag_key":         flag_key,
            "category":         row.get("category", "").strip().lower(),
            "flag_safety_risk": parse_float(row.get("flag_safety_risk"), 0.5),
            "inspections":      parse_int(row.get("inspections", 0)),
            "detentions":       parse_int(row.get("detentions", 0)),
            "excess_factor":    parse_float(row.get("excess_factor", 0.0)),
        })
    return rows


def aggregate_paris(
    paris_data: list,
    start_year: int,
    end_year: int,
    valid_flag_keys: set = None,
) -> dict:
    """Aggregate Paris MoU rows into per-flag summary stats for [start_year, end_year].

    valid_flag_keys: when provided, skips rows whose key is not in the fleet or
        accident data — this filters out OCR-artifact entries (e.g. classification
        society names that appear as flag states in corrupted PDF extracts).

    Returns {flag_key: {paris_mou_category, detention_rate, excess_factor_avg,
                         excess_factor_trend}}.
    """
    # Use all years when the requested window yields no rows (e.g. pre-2010 queries)
    relevant_rows = [r for r in paris_data if start_year <= r["year"] <= end_year] or paris_data

    by_flag: dict = {}
    for row in relevant_rows:
        key = row["flag_key"]
        if valid_flag_keys is not None and key not in valid_flag_keys:
            continue
        if key not in by_flag:
            by_flag[key] = {
                "flag": row["flag"], "flag_key": key,
                "inspections_total": 0, "detentions_total": 0,
                "excess_factor_pairs": [],
                "categories": [],
            }
        by_flag[key]["inspections_total"] += parse_int(row.get("inspections", 0))
        by_flag[key]["detentions_total"]  += parse_int(row.get("detentions", 0))
        by_flag[key]["categories"].append(row.get("category", "unlisted"))
        if row.get("excess_factor") not in (None, ""):
            try:
                by_flag[key]["excess_factor_pairs"].append(
                    (float(row["year"]), float(row["excess_factor"]))
                )
            except (ValueError, KeyError):
                pass

    result = {}
    for key, data in by_flag.items():
        inspections = data["inspections_total"]
        detentions  = data["detentions_total"]
        # det > insp is physically impossible; treat it as an OCR-corrupted row.
        detention_rate = detentions / inspections if inspections > 0 and detentions <= inspections else 0.0

        ef_pairs = data["excess_factor_pairs"]
        excess_factor_avg   = sum(ef for _, ef in ef_pairs) / len(ef_pairs) if ef_pairs else 0.0
        excess_factor_trend = ols_slope(ef_pairs) if ef_pairs else 0.0

        # Most-frequent Paris MoU category over the period
        category_counts: dict = {}
        for cat in data["categories"]:
            category_counts[cat] = category_counts.get(cat, 0) + 1
        dominant_category = max(category_counts, key=lambda c: category_counts[c])

        result[key] = {
            "flag":                data["flag"],
            "flag_key":            key,
            "paris_mou_category":  dominant_category,
            "detention_rate":      detention_rate,
            "excess_factor_avg":   excess_factor_avg,
            "excess_factor_trend": excess_factor_trend,
        }
    return result


def load_accident_rows(start_year: int = None, end_year: int = None) -> list[dict]:
    """Load accident CSV rows, expanding multi-flag entries into one row per flag.

    Each returned dict adds "flag", "flag_key", and "date" fields.
    Rows outside [start_year, end_year] are excluded when those bounds are set.
    """
    rows = []
    for raw_row in read_csv(ACCIDENT_CSV):
        date = parse_accident_date(raw_row)
        if start_year and (not date or date.year < start_year):
            continue
        if end_year and (not date or date.year > end_year):
            continue
        for flag_name in split_flag_administrations(raw_row.get("Flag Administrations", "")):
            flag_key = normalize_flag_name(flag_name)
            if not flag_key or flag_key in REGION_ROWS:
                continue
            rows.append({**raw_row, "flag": flag_name, "flag_key": flag_key, "date": date})
    return rows


# ---------------------------------------------------------------------------
# Accident metrics
# ---------------------------------------------------------------------------

# Location values recognized as "open sea" (high navigational risk)
_OPEN_SEA_LOCATIONS = {"open sea"}

# All location values considered reliable (used as denominator for open_sea_rate)
_KNOWN_LOCATIONS = {
    "open sea", "coastal waters", "port", "at berth", "anchorage",
    "port approach", "river", "inland waters", "strait/channel",
    "canal", "archipelagos", "offshore installation", "traffic separation scheme",
}


def compute_accident_metrics(start_year: int = None, end_year: int = None) -> list[dict]:
    """Compute per-flag accident metrics using monthly-interpolated fleet exposure.

    Exposure formula:
        fleet_at(Y, m) = fleet[Y] + (fleet[Y+1] - fleet[Y]) / 12 * (m - 1)
        exposure_Y     = mean(fleet_at(Y, 1..12))
        accident_rate  = accident_count / sum(exposure_Y for Y in period)

    Returns a list of per-flag metric dicts sorted by flag name.
    """
    fleet_by_year     = {key: sizes for key, (_, sizes) in load_fleet_by_year().items()}
    analysis_start    = start_year or FLEET_YEARS[0]
    analysis_end      = end_year   or FLEET_YEARS[-1]

    accident_rows = load_accident_rows(start_year, end_year)

    # Ship-type risk: log-scaled frequency across all accidents in the period.
    # More common ship types receive higher risk scores (they generate more claims).
    ship_type_counts = Counter(
        row.get("Ship types", "").strip()
        for row in accident_rows if row.get("Ship types", "").strip()
    )
    max_ship_type_count = max(ship_type_counts.values(), default=1)
    ship_type_risk_score = {
        ship_type: math.log1p(count) / math.log1p(max_ship_type_count)
        for ship_type, count in ship_type_counts.items()
    }

    # Accumulate raw counts per flag
    buckets = defaultdict(lambda: {
        "flag": "", "flag_key": "",
        "accident_count": 0,
        "vsmc_count": 0, "severity_total": 0.0, "severity_count": 0,
        "ship_type_risk_total": 0.0, "ship_type_count": 0,
        "multi_ship_count": 0, "collision_count": 0,
        "open_sea_count": 0, "location_known_count": 0,
        "event_counts": {},
        "investigation_total": 0,
        "solas_noncompliant_count": 0, "solas_known_count": 0,
    })

    for row in accident_rows:
        bucket = buckets[row["flag_key"]]
        bucket["flag"]          = row["flag"]
        bucket["flag_key"]      = row["flag_key"]
        bucket["accident_count"] += 1

        severity_label = row.get("Casualty severity", "").strip().casefold()
        severity_score = SEVERITY_SCORES.get(severity_label)
        if severity_score is not None:
            bucket["severity_total"] += severity_score
            bucket["severity_count"] += 1
        if severity_label == "very serious marine casualty":
            bucket["vsmc_count"] += 1

        ship_type = row.get("Ship types", "").strip()
        if ship_type:
            bucket["ship_type_risk_total"] += ship_type_risk_score.get(ship_type, 0.0)
            bucket["ship_type_count"] += 1

        # Multi-ship: accidents involving two or more vessels
        if parse_int(row.get("Number of ships involved", "1"), default=1) >= 2:
            bucket["multi_ship_count"] += 1

        # Event entropy: categorize by top-level event type (before " - " separator)
        event_full = row.get("Casualty event", "").strip()
        event_category = event_full.split(" - ")[0].strip() if " - " in event_full else event_full
        if event_category:
            bucket["event_counts"][event_category] = bucket["event_counts"].get(event_category, 0) + 1
        if event_category.lower().startswith("collision"):
            bucket["collision_count"] += 1

        location = row.get("Location", "").strip().lower()
        if location in _KNOWN_LOCATIONS:
            bucket["location_known_count"] += 1
            if location in _OPEN_SEA_LOCATIONS:
                bucket["open_sea_count"] += 1

        bucket["investigation_total"] += parse_int(row.get("Number of investigation reports", "0"))

        solas_status = row.get("SOLAS status", "").strip()
        if solas_status:
            bucket["solas_known_count"] += 1
            if ": N" in solas_status:   # e.g. "SOLAS chapter IV: No"
                bucket["solas_noncompliant_count"] += 1

    metrics = []
    for bucket in buckets.values():
        severity_count  = bucket.pop("severity_count")
        ship_type_count = bucket.pop("ship_type_count")
        severity_total  = bucket.pop("severity_total")
        ship_type_total = bucket.pop("ship_type_risk_total")
        event_counts    = bucket.pop("event_counts")
        acc_count       = bucket["accident_count"]
        loc_known       = bucket["location_known_count"]

        bucket["avg_severity_risk"]  = severity_total  / severity_count  if severity_count  else 0.0
        bucket["avg_ship_type_risk"] = ship_type_total / ship_type_count if ship_type_count else 0.0
        bucket["vsmc_rate"]          = bucket["vsmc_count"]       / acc_count if acc_count else 0.0
        bucket["multi_ship_rate"]    = bucket["multi_ship_count"]  / acc_count if acc_count else 0.0
        bucket["collision_rate"]     = bucket["collision_count"]   / acc_count if acc_count else 0.0
        bucket["open_sea_rate"]      = bucket["open_sea_count"]    / loc_known  if loc_known  else 0.0
        bucket["event_entropy"]      = shannon_entropy(event_counts)
        bucket["investigation_rate"] = bucket["investigation_total"] / acc_count if acc_count else 0.0

        solas_known = bucket["solas_known_count"]
        bucket["solas_noncompliance_rate"] = (
            bucket["solas_noncompliant_count"] / solas_known if solas_known else 0.0
        )

        # Exposure-weighted accident rate over the analysis period
        flag_year_sizes = fleet_by_year.get(bucket["flag_key"], {})
        total_exposure  = sum(year_exposure(flag_year_sizes, y) for y in range(analysis_start, analysis_end + 1))
        bucket["accident_rate"] = bucket["accident_count"] / total_exposure if total_exposure > 0 else 0.0

        # Remove intermediate count fields that are no longer needed
        for count_field in ("vsmc_count", "multi_ship_count", "collision_count",
                            "open_sea_count", "location_known_count",
                            "investigation_total", "solas_noncompliant_count", "solas_known_count"):
            bucket.pop(count_field, None)

        metrics.append(bucket)

    metrics.sort(key=lambda r: r["flag"])
    return metrics


# ---------------------------------------------------------------------------
# Trend slope (OLS on yearly accident rates)
# ---------------------------------------------------------------------------

def compute_trend_slopes(start_year: int = None, end_year: int = None) -> dict:
    """Compute the OLS slope of the yearly exposure-weighted accident rate per flag.

    slope > 0 → worsening trend (higher future risk)
    slope < 0 → improving trend

    Returns {flag_key: slope} in units of accidents/ship-year per year.
    """
    fleet_by_year  = {key: sizes for key, (_, sizes) in load_fleet_by_year().items()}
    analysis_start = start_year or FLEET_YEARS[0]
    analysis_end   = end_year   or FLEET_YEARS[-1]
    analysis_years = [y for y in FLEET_YEARS if analysis_start <= y <= analysis_end]

    accidents_by_flag_year: dict = defaultdict(lambda: defaultdict(int))
    for row in load_accident_rows(start_year, end_year):
        if row["date"] is None:
            continue
        accidents_by_flag_year[row["flag_key"]][row["date"].year] += 1

    slopes = {}
    for flag_key in set(fleet_by_year) | set(accidents_by_flag_year):
        annual_sizes  = fleet_by_year.get(flag_key, {})
        annual_counts = accidents_by_flag_year.get(flag_key, {})
        rate_pairs = [
            (float(year), annual_counts.get(year, 0) / year_exposure(annual_sizes, year))
            for year in analysis_years
            if year_exposure(annual_sizes, year) > 0
        ]
        slopes[flag_key] = ols_slope(rate_pairs)
    return slopes


# ---------------------------------------------------------------------------
# Fleet features
# ---------------------------------------------------------------------------

def compute_fleet_features(start_year: int = None, end_year: int = None) -> dict:
    """Compute fleet-based risk features from annual fleet size data.

    fleet_growth_rate = (fleet[end] - fleet[start]) / fleet[start]
    fleet_volatility  = RMSE of year-to-year changes / mean fleet size
        (high volatility → rapid unexplained fleet churn, a risk signal)

    Returns {flag_key: {fleet_growth_rate, fleet_volatility}}.
    """
    analysis_start = start_year or FLEET_YEARS[0]
    analysis_end   = end_year   or FLEET_YEARS[-1]

    result = {}
    for flag_key, (_, annual_sizes) in load_fleet_by_year().items():
        sizes_in_range = [annual_sizes[y] for y in range(analysis_start, analysis_end + 1) if y in annual_sizes]
        if not sizes_in_range:
            continue

        first_size, last_size = sizes_in_range[0], sizes_in_range[-1]
        growth_rate = (last_size - first_size) / first_size if first_size > 0 else 0.0

        if len(sizes_in_range) >= 2:
            annual_changes = [abs(sizes_in_range[i + 1] - sizes_in_range[i]) for i in range(len(sizes_in_range) - 1)]
            mean_fleet_size = sum(sizes_in_range) / len(sizes_in_range)
            rmse        = (sum(c ** 2 for c in annual_changes) / len(annual_changes)) ** 0.5
            volatility  = rmse / mean_fleet_size if mean_fleet_size > 0 else 0.0
        else:
            volatility = 0.0

        result[flag_key] = {"fleet_growth_rate": growth_rate, "fleet_volatility": volatility}
    return result


# ---------------------------------------------------------------------------
# Risk score assembly
# ---------------------------------------------------------------------------

def build_merged_rows(start_year: int = None, end_year: int = None, weights: dict = None) -> list[dict]:
    """Assemble per-flag risk rows with all computed features and normalised scores.

    All normalised component fields are included in the output so callers can
    combine them with different weights (e.g. via query params) without re-running
    the pipeline.

    Returns a list of row dicts sorted by descending risk_score.
    """
    weights        = weights or DEFAULT_WEIGHTS
    analysis_start = start_year or FLEET_YEARS[0]
    analysis_end   = end_year   or FLEET_YEARS[-1]

    fleet_by_key    = {r["flag_key"]: r for r in load_fleet_rows()}
    accident_by_key = {r["flag_key"]: r for r in compute_accident_metrics(start_year, end_year)}
    valid_keys      = set(fleet_by_key) | set(accident_by_key)
    paris_by_key    = aggregate_paris(load_paris_data(), analysis_start, analysis_end, valid_flag_keys=valid_keys)
    trend_by_key    = compute_trend_slopes(start_year, end_year)
    fleet_feat_by   = compute_fleet_features(start_year, end_year)

    all_flag_keys = sorted(set(fleet_by_key) | set(paris_by_key) | set(accident_by_key))

    def safe_float(source_dict: dict, field: str) -> float:
        return parse_float(source_dict.get(field))

    # Build one row per flag with raw (un-normalised) feature values
    rows = []
    for key in all_flag_keys:
        fleet    = fleet_by_key.get(key, {})
        paris    = paris_by_key.get(key, {})
        acc      = accident_by_key.get(key, {})
        fleet_ft = fleet_feat_by.get(key, {})
        rows.append({
            "flag":     fleet.get("flag") or paris.get("flag") or acc.get("flag") or key.title(),
            "flag_key": key,
            "fleet_size":               parse_int(fleet.get("fleet_size")),
            "accident_count":           parse_int(acc.get("accident_count")),
            "accident_rate":            safe_float(acc, "accident_rate"),
            "avg_severity_risk":        safe_float(acc, "avg_severity_risk"),
            "vsmc_rate":                safe_float(acc, "vsmc_rate"),
            "avg_ship_type_risk":       safe_float(acc, "avg_ship_type_risk"),
            "multi_ship_rate":          safe_float(acc, "multi_ship_rate"),
            "collision_rate":           safe_float(acc, "collision_rate"),
            "open_sea_rate":            safe_float(acc, "open_sea_rate"),
            "event_entropy":            safe_float(acc, "event_entropy"),
            "investigation_rate":       safe_float(acc, "investigation_rate"),
            "solas_noncompliance_rate": safe_float(acc, "solas_noncompliance_rate"),
            "paris_mou_category":       paris.get("paris_mou_category", "unlisted"),
            "detention_rate":           safe_float(paris, "detention_rate"),
            "excess_factor_avg":        safe_float(paris, "excess_factor_avg"),
            "excess_factor_trend":      safe_float(paris, "excess_factor_trend"),
            "trend_slope":              trend_by_key.get(key, 0.0),
            "fleet_growth_rate":        safe_float(fleet_ft, "fleet_growth_rate"),
            "fleet_volatility":         safe_float(fleet_ft, "fleet_volatility"),
        })

    # ------------------------------------------------------------------
    # Build per-feature normalization functions from the assembled rows.
    # norm_pos: min-max cap on raw values (all non-negative)
    # norm_clip: same but first clamps any negatives to 0 (safe for ratios)
    # norm_trend: percentile-clipped signed normalization for OLS slopes
    # ------------------------------------------------------------------
    def norm_pos(field: str):
        return minmax_capped([r[field] for r in rows])

    def norm_clip(field: str):
        return minmax_capped([max(r[field], 0.0) for r in rows])

    def norm_trend(field: str, min_accidents: int = 5, lo_pct: int = 5, hi_pct: int = 95):
        """Signed normalization using a percentile-clipped range.

        Only flags with >= min_accidents qualify; others are mapped to 0.0.
        Maps [lo_pct-ile, hi_pct-ile] → [0, 1]: improving (negative slope) → 0,
        worsening (positive slope) → 1.  Clipping keeps micro-state outliers
        from compressing the scores of major flag states near the midpoint.
        """
        qualified = sorted(
            r[field] for r in rows if r.get("accident_count", 0) >= min_accidents
        )
        if not qualified:
            return lambda _: 0.0
        n  = len(qualified)
        lo = qualified[int(n * lo_pct / 100)]
        hi = qualified[min(int(n * hi_pct / 100), n - 1)]
        if lo >= hi:
            return lambda _: 0.5
        return lambda v: max(0.0, min(1.0, (v - lo) / (hi - lo)))

    # One normalization function per raw feature field
    acc_rate_norm    = norm_pos("accident_rate")
    severity_norm    = norm_pos("avg_severity_risk")
    vsmc_norm        = norm_pos("vsmc_rate")
    ship_type_norm   = norm_pos("avg_ship_type_risk")
    detention_norm   = norm_pos("detention_rate")
    trend_norm       = norm_trend("trend_slope")
    multi_ship_norm  = norm_pos("multi_ship_rate")
    collision_norm   = norm_pos("collision_rate")
    open_sea_norm    = norm_pos("open_sea_rate")
    entropy_norm     = norm_pos("event_entropy")
    invest_norm      = norm_pos("investigation_rate")
    solas_norm       = norm_pos("solas_noncompliance_rate")
    excess_norm      = norm_clip("excess_factor_avg")
    excess_tr_norm   = norm_clip("excess_factor_trend")
    fleet_gr_norm    = norm_clip("fleet_growth_rate")
    fleet_vol_norm   = norm_pos("fleet_volatility")

    total_weight = sum(weights.values()) or 1.0

    for row in rows:
        clip = lambda v: max(v, 0.0)  # noqa: E731 — clip negatives to zero before normalising

        row["accident_rate_norm"]       = acc_rate_norm(row["accident_rate"])
        # Severity combines mean severity (60%) and very-serious-casualty rate (40%)
        row["severity_risk_norm"]       = (
            severity_norm(row["avg_severity_risk"]) * 0.6 + vsmc_norm(row["vsmc_rate"]) * 0.4
        )
        row["ship_type_risk_norm"]      = ship_type_norm(row["avg_ship_type_risk"])
        row["flag_safety_risk_norm"]    = detention_norm(row["detention_rate"])
        row["trend_slope_norm"]         = trend_norm(row["trend_slope"])
        row["multi_ship_rate_norm"]     = multi_ship_norm(row["multi_ship_rate"])
        row["collision_rate_norm"]      = collision_norm(row["collision_rate"])
        row["open_sea_rate_norm"]       = open_sea_norm(row["open_sea_rate"])
        row["event_entropy_norm"]       = entropy_norm(row["event_entropy"])
        row["investigation_rate_norm"]  = invest_norm(row["investigation_rate"])
        row["solas_noncompliance_norm"] = solas_norm(row["solas_noncompliance_rate"])
        row["excess_factor_norm"]       = excess_norm(clip(row["excess_factor_avg"]))
        row["excess_factor_trend_norm"] = excess_tr_norm(clip(row["excess_factor_trend"]))
        row["fleet_growth_norm"]        = fleet_gr_norm(clip(row["fleet_growth_rate"]))
        row["fleet_volatility_norm"]    = fleet_vol_norm(row["fleet_volatility"])

        row["risk_score"] = (
            weights.get("accident_rate",       0) * row["accident_rate_norm"]
            + weights.get("severity",          0) * row["severity_risk_norm"]
            + weights.get("ship_type",         0) * row["ship_type_risk_norm"]
            + weights.get("flag_safety",       0) * row["flag_safety_risk_norm"]
            + weights.get("trend",             0) * row["trend_slope_norm"]
            + weights.get("multi_ship",        0) * row["multi_ship_rate_norm"]
            + weights.get("collision",         0) * row["collision_rate_norm"]
            + weights.get("open_sea",          0) * row["open_sea_rate_norm"]
            + weights.get("event_entropy",     0) * row["event_entropy_norm"]
            + weights.get("investigation",     0) * row["investigation_rate_norm"]
            + weights.get("solas_noncompliance", 0) * row["solas_noncompliance_norm"]
            + weights.get("excess_factor",     0) * row["excess_factor_norm"]
            + weights.get("excess_factor_trend", 0) * row["excess_factor_trend_norm"]
            + weights.get("fleet_growth",      0) * row["fleet_growth_norm"]
            + weights.get("fleet_volatility",  0) * row["fleet_volatility_norm"]
        ) / total_weight

    rows.sort(key=lambda r: r["risk_score"], reverse=True)
    return rows


# ---------------------------------------------------------------------------
# Temporal trends (yearly + monthly granularity for the trend chart)
# ---------------------------------------------------------------------------

def compute_temporal_trends() -> list[dict]:
    """Build per-flag time-series of accident rates at yearly and monthly granularity.

    Yearly rate:  accidents_in_year  / year_exposure(Y)
    Monthly rate: accidents_in_month / (interpolated_fleet(Y, M) / 12)

    Also calls holt_predict to append a 3-year forecast to each flag's series.

    Returns a list of dicts: {flag, flag_key, yearly, monthly, predicted_yearly}.
    """
    fleet_by_year_all = load_fleet_by_year()
    fleet_year_sizes  = {key: sizes for key, (_, sizes) in fleet_by_year_all.items()}

    accidents_by_flag_year:  dict = defaultdict(lambda: defaultdict(int))
    accidents_by_flag_month: dict = defaultdict(lambda: defaultdict(int))
    flag_display_name: dict = {}

    for row in load_accident_rows():
        if row["date"] is None:
            continue
        key = row["flag_key"]
        accidents_by_flag_year[key][row["date"].year] += 1
        accidents_by_flag_month[key][(row["date"].year, row["date"].month)] += 1
        flag_display_name[key] = row["flag"]

    trends = []
    for key in sorted(set(fleet_year_sizes) | set(accidents_by_flag_year)):
        fleet_entry  = fleet_by_year_all.get(key)
        display_name = fleet_entry[0] if fleet_entry else flag_display_name.get(key, key.title())
        annual_sizes = fleet_entry[1] if fleet_entry else {}
        by_year      = accidents_by_flag_year.get(key, {})
        by_month     = accidents_by_flag_month.get(key, {})

        yearly_series  = []
        monthly_series = []

        for year in FLEET_YEARS:
            annual_exp = year_exposure(annual_sizes, year)
            acc_count  = by_year.get(year, 0)
            yearly_series.append({
                "year":           year,
                "accident_rate":  acc_count / annual_exp if annual_exp > 0 else 0.0,
                "accident_count": acc_count,
                "exposure":       annual_exp,
                "has_fleet_data": annual_exp > 0,
            })
            for month in range(1, 13):
                monthly_exp = interpolate_fleet_size(annual_sizes, year, month) / 12
                month_acc   = by_month.get((year, month), 0)
                monthly_series.append({
                    "date":           f"{year}-{month:02d}",
                    "year":           year,
                    "month":          month,
                    "accident_rate":  month_acc / monthly_exp if monthly_exp > 0 else 0.0,
                    "accident_count": month_acc,
                    "exposure":       monthly_exp,
                    "has_fleet_data": monthly_exp > 0,
                })

        predicted_yearly = holt_predict(yearly_series)
        trends.append({
            "flag":             display_name,
            "flag_key":         key,
            "yearly":           yearly_series,
            "monthly":          monthly_series,
            "predicted_yearly": predicted_yearly,
        })

    return trends

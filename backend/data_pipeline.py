import csv
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
ACCIDENT_CSV = DATA_DIR / "accident_data_20110101_20251231.csv"
FLEET_CSV = DATA_DIR / "archive" / "Num_of_Ships_2011_2025.csv"
PARIS_CSV = DATA_DIR / "paris_mou.csv"

FLEET_YEARS = list(range(2011, 2026))

DEFAULT_WEIGHTS = {
    # === Active components ===
    # Selected based on single-variable Spearman r against future accident rates.
    # These four are the only components with r >= 0.4 (all p < 0.05) individually.
    "accident_rate":         0.40,  # r=+0.674** exposure-weighted accidents/ship-year
    "event_entropy":         0.25,  # r=+0.477** Shannon entropy of accident-cause diversity
    "trend":                 0.20,  # r=+0.458*  OLS slope of yearly accident rate (worsening = risky)
    "investigation":         0.15,  # r=+0.439*  mean investigation reports per accident
    # === Optional components (enable via ?wN= query params) ===
    # Individually weaker (r < 0.3 in top-30 evaluation) but may add information
    # for specific use cases or smaller fleets.
    "flag_safety":           0.00,  # detention rate (detentions/inspections from Paris MoU)
    "severity":              0.00,  # weighted avg casualty severity + VSMC proportion
    "ship_type":             0.00,  # log-normalized ship type frequency risk
    "multi_ship":            0.00,  # proportion of accidents involving 2+ vessels
    "collision":             0.00,  # proportion of collision-type accidents
    "open_sea":              0.00,  # proportion of accidents in open sea
    "solas_noncompliance":   0.00,  # fraction with SOLAS non-compliant ships involved
    "excess_factor":         0.00,  # mean Paris MoU excess factor (continuous)
    "excess_factor_trend":   0.00,  # OLS slope of Paris MoU excess factor over time
    "fleet_growth":          0.00,  # relative fleet growth rate
    "fleet_volatility":      0.00,  # RMSE of annual fleet size changes / mean size
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

# ---------------------------------------------------------------------------
# Name normalization
# ---------------------------------------------------------------------------

def normalize_flag_name(name):
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


def split_flag_administrations(value):
    cleaned = re.sub(r"\s+", " ", (value or "").strip())
    if not cleaned:
        return []

    placeholder_to_name = {v: k for k, v in COMMA_NAME_PLACEHOLDERS.items()}
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


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def minmax_capped(values, percentile=95):
    """Min-max normalization capped at a percentile of nonzero values.

    Prevents a handful of extreme outliers from compressing the rest of the
    scale so badly that tiny-but-real nonzero values are indistinguishable
    from 0. Flags with value==0 remain at 0; flags above the cap are
    clamped to 1.0.
    """
    nonzero = sorted(v for v in values if v is not None and v > 0)
    if not nonzero:
        return lambda _: 0.0
    cap_idx = min(int(len(nonzero) * percentile / 100), len(nonzero) - 1)
    cap = nonzero[cap_idx]
    if cap <= 0:
        return lambda _: 0.0
    return lambda value: min((value if value is not None else 0.0) / cap, 1.0)


def ols_slope(xy_pairs):
    """Compute ordinary-least-squares slope from [(x, y), ...] pairs.

    Returns 0.0 when fewer than 3 points are available, preventing
    noisy two-point estimates from dominating the signal.
    """
    if len(xy_pairs) < 3:
        return 0.0
    xs = [p[0] for p in xy_pairs]
    ys = [p[1] for p in xy_pairs]
    n = len(xs)
    sx  = sum(xs)
    sy  = sum(ys)
    sxy = sum(x * y for x, y in zip(xs, ys))
    sx2 = sum(x * x for x in xs)
    d   = n * sx2 - sx ** 2
    return (n * sxy - sx * sy) / d if d else 0.0


def shannon_entropy(counts) -> float:
    """Shannon entropy (base-2) of a frequency distribution."""
    total = sum(counts.values())
    if total == 0:
        return 0.0
    return -sum(
        (c / total) * math.log2(c / total)
        for c in counts.values() if c > 0
    )


# ---------------------------------------------------------------------------
# Fleet helpers — monthly linear interpolation
# ---------------------------------------------------------------------------

def interpolate_fleet_size(year_sizes, year, month):
    """Fleet size at a given month, linearly interpolated between annual snapshots.

    Formula (user-specified):
        monthly_increment = (fleet[year+1] - fleet[year]) / 12
        fleet_at_month    = fleet[year] + monthly_increment * (month - 1)

    If the next year is not available (e.g. month in 2025), the current
    year's snapshot is returned unchanged.
    """
    current = year_sizes.get(year, 0)
    if current <= 0:
        return 0.0
    next_val = year_sizes.get(year + 1, 0)
    if next_val > 0:
        monthly_increment = (next_val - current) / 12
        return current + monthly_increment * (month - 1)
    return float(current)


def year_exposure(year_sizes, year):
    """Total ship-year exposure for a flag in one calendar year.

    Sums the monthly-interpolated fleet sizes across all 12 months and
    divides by 12 to convert from ship-months to ship-years.
    """
    return sum(interpolate_fleet_size(year_sizes, year, m) for m in range(1, 13)) / 12


# ---------------------------------------------------------------------------
# CSV loading
# ---------------------------------------------------------------------------

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
    """2025 fleet size per flag, used for vessel_count in the API payload."""
    rows = []
    for row in read_csv(FLEET_CSV):
        flag = row.get("Economy_Label", "").strip()
        flag_key = normalize_flag_name(flag)
        if flag_key in REGION_ROWS:
            continue
        fleet_size = parse_int(row.get("2025_Number_of_ships_Value"))
        rows.append({"flag": flag, "flag_key": flag_key, "fleet_size": fleet_size})
    return rows


def load_fleet_by_year():
    """Annual fleet sizes per flag: {flag_key: (display_name, {year: fleet_size})}"""
    result = {}
    for row in read_csv(FLEET_CSV):
        flag = row.get("Economy_Label", "").strip()
        flag_key = normalize_flag_name(flag)
        if flag_key in REGION_ROWS:
            continue
        year_sizes = {}
        for year in FLEET_YEARS:
            size = parse_int(row.get(f"{year}_Number_of_ships_Value", ""))
            if size > 0:
                year_sizes[year] = size
        if year_sizes:
            result[flag_key] = (flag, year_sizes)
    return result


def load_paris_data():
    """Load multi-year Paris MoU data from paris_mou.csv."""
    rows = []
    for row in read_csv(PARIS_CSV):
        flag = row.get("flag", "").strip()
        flag_key = normalize_flag_name(flag)
        if not flag_key:
            continue
        rows.append({
            "year":            parse_int(row.get("year", 0)),
            "flag":            flag,
            "flag_key":        flag_key,
            "category":        row.get("category", "").strip().lower(),
            "flag_safety_risk": parse_float(row.get("flag_safety_risk"), 0.5),
            "inspections":     parse_int(row.get("inspections", 0)),
            "detentions":      parse_int(row.get("detentions", 0)),
            "excess_factor":   parse_float(row.get("excess_factor", 0.0)),
        })
    return rows


def aggregate_paris(paris_data, start_year, end_year):
    """
    Compute per-flag Paris MoU aggregates for a given analysis period:

    detention_rate        = total_detentions / total_inspections
                            Process indicator: fraction of inspections that
                            result in ship detention; independent of accident
                            outcomes since detentions happen in port, accidents
                            at sea.

    excess_factor_avg     = mean(excess_factor) across period years
                            Continuous version of the categorical
                            White(0)/Grey(0.5)/Black(1.0) score. Negative
                            values = better-than-expected; positive = worse.

    excess_factor_trend   = OLS slope of excess_factor over time
                            Captures whether a flag's Port State Control
                            performance is improving (negative slope) or
                            worsening (positive slope) over the period.

    Falls back to all available years if none exist within the period.
    """
    relevant = [r for r in paris_data if start_year <= r["year"] <= end_year]
    if not relevant:
        relevant = paris_data

    by_flag = {}
    for row in relevant:
        key = row["flag_key"]
        if key not in by_flag:
            by_flag[key] = {
                "flag": row["flag"], "flag_key": key,
                "inspections_sum": 0, "detentions_sum": 0,
                "excess_factor_pairs": [],  # [(year, excess_factor), ...]
                "categories": [],
            }
        by_flag[key]["inspections_sum"] += parse_int(row.get("inspections", 0))
        by_flag[key]["detentions_sum"]  += parse_int(row.get("detentions", 0))
        by_flag[key]["categories"].append(row.get("category", "unlisted"))

        ef = row.get("excess_factor")
        if ef is not None and ef != "":
            try:
                by_flag[key]["excess_factor_pairs"].append(
                    (float(row["year"]), float(ef))
                )
            except (ValueError, KeyError):
                pass

    result = {}
    for key, data in by_flag.items():
        insp = data["inspections_sum"]
        det  = data["detentions_sum"]
        detention_rate = det / insp if insp > 0 else 0.0

        ef_pairs = data["excess_factor_pairs"]
        if ef_pairs:
            excess_factor_avg = sum(ef for _, ef in ef_pairs) / len(ef_pairs)
            excess_factor_trend = ols_slope(ef_pairs)
        else:
            excess_factor_avg   = 0.0
            excess_factor_trend = 0.0

        cat_counts = {}
        for c in data["categories"]:
            cat_counts[c] = cat_counts.get(c, 0) + 1
        most_common = max(cat_counts, key=lambda c: cat_counts[c])

        result[key] = {
            "flag":                 data["flag"],
            "flag_key":             key,
            "paris_mou_category":   most_common,
            "detention_rate":       detention_rate,
            "excess_factor_avg":    excess_factor_avg,
            "excess_factor_trend":  excess_factor_trend,
        }
    return result


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


# ---------------------------------------------------------------------------
# Accident metrics (exposure-weighted)
# ---------------------------------------------------------------------------

def compute_accident_metrics(start_year=None, end_year=None):
    """Compute per-flag accident metrics using monthly-interpolated fleet exposure.

    accident_rate = accident_count / total_ship_year_exposure

    where exposure is computed by summing monthly-interpolated fleet sizes
    (per the user formula: monthly_increment = (next_year - current) / 12)
    over the given period and converting ship-months to ship-years.
    This corrects the previous approach of dividing by the 2025 fleet size,
    which introduced a systematic bias for countries whose fleet changed
    significantly over the training period.
    """
    fleet_by_year_all = load_fleet_by_year()
    fleet_year_sizes = {k: v[1] for k, v in fleet_by_year_all.items()}

    _start = start_year or FLEET_YEARS[0]
    _end = end_year or FLEET_YEARS[-1]

    accidents = load_accident_rows(start_year, end_year)

    # Ship-type risk uses log scale to compress the 788x count range
    ship_type_counts = Counter(
        row.get("Ship types", "").strip()
        for row in accidents
        if row.get("Ship types", "").strip()
    )
    max_ship_type_count = max(ship_type_counts.values(), default=1)
    ship_type_risk = {
        ship_type: math.log1p(count) / math.log1p(max_ship_type_count)
        for ship_type, count in ship_type_counts.items()
    }

    # Location categories treated as "open sea" for open_sea_rate
    OPEN_SEA_LOCATIONS = {"open sea"}
    # Location values that indicate usable (non-missing) data
    VALID_LOCATIONS = {
        "open sea", "coastal waters", "port", "at berth", "anchorage",
        "port approach", "river", "inland waters", "strait/channel",
        "canal", "archipelagos", "offshore installation",
        "traffic separation scheme",
    }

    by_flag = defaultdict(lambda: {
        "flag": "",
        "flag_key": "",
        "accident_count": 0,
        "vsmc_count": 0,
        "severity_total": 0.0,
        "severity_count": 0,
        "ship_type_risk_total": 0.0,
        "ship_type_count": 0,
        # New accident-based accumulators
        "multi_ship_count": 0,
        "collision_count": 0,
        "open_sea_count": 0,
        "location_known_count": 0,
        "event_counts": {},
        "investigation_total": 0,
        "solas_noncompliant_count": 0,
        "solas_known_count": 0,
    })

    for row in accidents:
        bucket = by_flag[row["flag_key"]]
        bucket["flag"]           = row["flag"]
        bucket["flag_key"]       = row["flag_key"]
        bucket["accident_count"] += 1

        # --- Existing: severity ---
        sev_label = row.get("Casualty severity", "").strip().casefold()
        severity = SEVERITY_SCORES.get(sev_label)
        if severity is not None:
            bucket["severity_total"] += severity
            bucket["severity_count"] += 1
        if sev_label == "very serious marine casualty":
            bucket["vsmc_count"] += 1

        # --- Existing: ship type ---
        ship_type = row.get("Ship types", "").strip()
        if ship_type:
            bucket["ship_type_risk_total"] += ship_type_risk.get(ship_type, 0.0)
            bucket["ship_type_count"] += 1

        # --- New: multi-ship incident ---
        n_ships = parse_int(row.get("Number of ships involved", "1"), default=1)
        if n_ships >= 2:
            bucket["multi_ship_count"] += 1

        # --- New: collision event type ---
        ev = row.get("Casualty event", "").strip()
        ev_cat = ev.split(" - ")[0].strip() if " - " in ev else ev
        if ev_cat:
            bucket["event_counts"][ev_cat] = bucket["event_counts"].get(ev_cat, 0) + 1
        if ev_cat.lower().startswith("collision"):
            bucket["collision_count"] += 1

        # --- New: location (open sea vs other) ---
        loc = row.get("Location", "").strip().lower()
        if loc in VALID_LOCATIONS:
            bucket["location_known_count"] += 1
            if loc in OPEN_SEA_LOCATIONS:
                bucket["open_sea_count"] += 1

        # --- New: investigation reports ---
        bucket["investigation_total"] += parse_int(
            row.get("Number of investigation reports", "0")
        )

        # --- New: SOLAS non-compliance ---
        solas = row.get("SOLAS status", "").strip()
        if solas:
            bucket["solas_known_count"] += 1
            # ": N" = non-compliant; ": U" = unknown/not SOLAS ship
            if ": N" in solas:
                bucket["solas_noncompliant_count"] += 1

    metrics = []
    for bucket in by_flag.values():
        severity_count       = bucket.pop("severity_count")
        ship_type_count      = bucket.pop("ship_type_count")
        severity_total       = bucket.pop("severity_total")
        ship_type_risk_total = bucket.pop("ship_type_risk_total")
        event_counts         = bucket.pop("event_counts")

        acc = bucket["accident_count"]

        bucket["avg_severity_risk"] = severity_total / severity_count if severity_count else 0.0
        bucket["avg_ship_type_risk"] = (
            ship_type_risk_total / ship_type_count if ship_type_count else 0.0
        )
        # Tail-risk: proportion of very serious casualties
        bucket["vsmc_rate"] = bucket["vsmc_count"] / acc if acc else 0.0

        # Multi-ship: fraction of accidents involving 2+ vessels
        bucket["multi_ship_rate"] = bucket["multi_ship_count"] / acc if acc else 0.0

        # Collision: fraction of accidents categorised as collisions
        bucket["collision_rate"] = bucket["collision_count"] / acc if acc else 0.0

        # Open-sea: fraction of accidents occurring in open sea
        loc_known = bucket["location_known_count"]
        bucket["open_sea_rate"] = (
            bucket["open_sea_count"] / loc_known if loc_known > 0 else 0.0
        )

        # Event entropy: Shannon entropy of top-level accident-cause distribution.
        # High entropy -> diverse causes (systemic/multi-dimensional risk).
        # Low entropy  -> one dominant cause (potentially addressable).
        bucket["event_entropy"] = shannon_entropy(event_counts)

        # Investigation rate: mean reports per accident.
        # Low rate may indicate underreporting or poor governance.
        bucket["investigation_rate"] = (
            bucket["investigation_total"] / acc if acc else 0.0
        )

        # SOLAS non-compliance: fraction of accidents where a non-SOLAS-compliant
        # ship was involved, among accidents with known SOLAS data.
        solas_known = bucket["solas_known_count"]
        bucket["solas_noncompliance_rate"] = (
            bucket["solas_noncompliant_count"] / solas_known if solas_known > 0 else 0.0
        )

        # Exposure in ship-years over the analysis period
        year_sizes = fleet_year_sizes.get(bucket["flag_key"], {})
        exposure = sum(year_exposure(year_sizes, y) for y in range(_start, _end + 1))
        bucket["accident_rate"] = bucket["accident_count"] / exposure if exposure > 0 else 0.0

        # Clean up intermediate accumulators
        for key in ("vsmc_count", "multi_ship_count", "collision_count",
                    "open_sea_count", "location_known_count",
                    "investigation_total", "solas_noncompliant_count", "solas_known_count"):
            bucket.pop(key, None)

        metrics.append(bucket)

    metrics.sort(key=lambda row: row["flag"])
    return metrics


# ---------------------------------------------------------------------------
# Trend slope computation
# ---------------------------------------------------------------------------

def compute_trend_slopes(start_year=None, end_year=None):
    """
    OLS slope of yearly exposure-weighted accident rate for each flag.

    slope > 0  →  accident rate is worsening  (higher future risk)
    slope < 0  →  accident rate is improving   (lower future risk)
    Returns {flag_key: slope} in units of accidents/ship-year per year.
    """
    fleet_by_year_all = load_fleet_by_year()
    fleet_year_sizes  = {k: v[1] for k, v in fleet_by_year_all.items()}

    _start = start_year or FLEET_YEARS[0]
    _end   = end_year   or FLEET_YEARS[-1]
    years_in_range = [y for y in FLEET_YEARS if _start <= y <= _end]

    accidents_by_flag_year = defaultdict(lambda: defaultdict(int))
    for row in load_accident_rows(start_year, end_year):
        if row["date"] is None:
            continue
        accidents_by_flag_year[row["flag_key"]][row["date"].year] += 1

    all_keys = set(fleet_year_sizes) | set(accidents_by_flag_year)
    slopes = {}

    for key in all_keys:
        year_sizes    = fleet_year_sizes.get(key, {})
        accident_data = accidents_by_flag_year.get(key, {})

        pairs = [
            (float(year), accident_data.get(year, 0) / year_exposure(year_sizes, year))
            for year in years_in_range
            if year_exposure(year_sizes, year) > 0
        ]
        slopes[key] = ols_slope(pairs)

    return slopes


def compute_fleet_features(start_year=None, end_year=None):
    """
    Fleet-based risk features derived from annual fleet size data.

    fleet_growth_rate  = (fleet[end] - fleet[start]) / fleet[start]
        Rapidly expanding flags may register ships faster than safety
        oversight infrastructure can keep up. Flags shedding ships may
        indicate loss of confidence in the registry.

    fleet_volatility   = RMSE of annual changes / mean fleet size
        High volatility signals unstable flag-of-convenience behaviour:
        ships registering and de-registering frequently, indicating
        opportunistic use rather than committed national oversight.

    Returns {flag_key: {"fleet_growth_rate": float, "fleet_volatility": float}}
    """
    fleet_by_year_all = load_fleet_by_year()
    _start = start_year or FLEET_YEARS[0]
    _end   = end_year   or FLEET_YEARS[-1]

    result = {}
    for flag_key, (_, year_sizes) in fleet_by_year_all.items():
        sizes = [year_sizes[y] for y in range(_start, _end + 1) if y in year_sizes]
        if not sizes:
            continue

        # Growth rate: use first and last available values in the period
        first, last = sizes[0], sizes[-1]
        growth_rate = (last - first) / first if first > 0 else 0.0

        # Volatility: RMSE of year-on-year changes, normalised by mean size
        if len(sizes) >= 2:
            changes = [abs(sizes[i + 1] - sizes[i]) for i in range(len(sizes) - 1)]
            mean_size = sum(sizes) / len(sizes)
            rmse_changes = (sum(c ** 2 for c in changes) / len(changes)) ** 0.5
            volatility = rmse_changes / mean_size if mean_size > 0 else 0.0
        else:
            volatility = 0.0

        result[flag_key] = {
            "fleet_growth_rate": growth_rate,
            "fleet_volatility":  volatility,
        }
    return result


# ---------------------------------------------------------------------------
# Risk score assembly
# ---------------------------------------------------------------------------

def build_merged_rows(start_year=None, end_year=None, weights=None):
    """
    Assemble per-flag risk rows with all computed features.

    Core risk score uses DEFAULT_WEIGHTS; extra variables are all included in
    the response payload (normalized to [0,1]) so callers can use them via
    query-param weight overrides without changing the response format.

    API field names for the four original components are preserved for
    frontend compatibility:
      flag_safety_risk_norm  ← detention_rate  (was Paris MoU 0/0.5/1.0)
      severity_risk_norm     ← blend of avg_severity + vsmc_rate
    """
    weights = weights or DEFAULT_WEIGHTS

    _start = start_year or FLEET_YEARS[0]
    _end   = end_year   or FLEET_YEARS[-1]

    fleet_by_key    = {row["flag_key"]: row for row in load_fleet_rows()}
    paris_by_key    = aggregate_paris(load_paris_data(), _start, _end)
    accident_by_key = {
        row["flag_key"]: row
        for row in compute_accident_metrics(start_year, end_year)
    }
    trend_by_key  = compute_trend_slopes(start_year, end_year)
    fleet_feat_by = compute_fleet_features(start_year, end_year)

    all_keys = sorted(set(fleet_by_key) | set(paris_by_key) | set(accident_by_key))

    def af(d, k):
        return parse_float(d.get(k))

    rows = []
    for key in all_keys:
        fleet    = fleet_by_key.get(key,    {})
        paris    = paris_by_key.get(key,    {})
        acc      = accident_by_key.get(key, {})
        fleet_ft = fleet_feat_by.get(key,   {})

        rows.append({
            "flag":        fleet.get("flag") or paris.get("flag") or acc.get("flag") or key.title(),
            "flag_key":    key,
            "fleet_size":  parse_int(fleet.get("fleet_size")),
            # --- Accident metrics ---
            "accident_count":           parse_int(acc.get("accident_count")),
            "accident_rate":            af(acc, "accident_rate"),
            "avg_severity_risk":        af(acc, "avg_severity_risk"),
            "vsmc_rate":                af(acc, "vsmc_rate"),
            "avg_ship_type_risk":       af(acc, "avg_ship_type_risk"),
            "multi_ship_rate":          af(acc, "multi_ship_rate"),
            "collision_rate":           af(acc, "collision_rate"),
            "open_sea_rate":            af(acc, "open_sea_rate"),
            "event_entropy":            af(acc, "event_entropy"),
            "investigation_rate":       af(acc, "investigation_rate"),
            "solas_noncompliance_rate": af(acc, "solas_noncompliance_rate"),
            # --- Paris MoU metrics ---
            "paris_mou_category":  paris.get("paris_mou_category", "unlisted"),
            "detention_rate":      af(paris, "detention_rate"),
            "excess_factor_avg":   af(paris, "excess_factor_avg"),
            "excess_factor_trend": af(paris, "excess_factor_trend"),
            # --- Trend slope ---
            "trend_slope": trend_by_key.get(key, 0.0),
            # --- Fleet features ---
            "fleet_growth_rate": af(fleet_ft, "fleet_growth_rate"),
            "fleet_volatility":  af(fleet_ft, "fleet_volatility"),
        })

    # ------------------------------------------------------------------
    # Normalization helpers
    # For variables where higher = riskier: use minmax_capped directly.
    # For trend/excess_factor variables: clip negatives to 0 first
    #   (improving flags → 0 risk, not negative).
    # investigation_rate: higher = safer → invert before normalizing.
    # fleet_growth_rate: signed (can be negative); use max(., 0) to
    #   treat shrinking fleets as 0 risk from growth perspective.
    # ------------------------------------------------------------------
    def norm_positive(field):
        return minmax_capped([row[field] for row in rows])

    def norm_clipped(field):
        """Clip negatives to 0, then normalize (for trend-like variables)."""
        return minmax_capped([max(row[field], 0.0) for row in rows])

    acc_rate_nfn    = norm_positive("accident_rate")
    severity_nfn    = norm_positive("avg_severity_risk")
    vsmc_nfn        = norm_positive("vsmc_rate")
    ship_type_nfn   = norm_positive("avg_ship_type_risk")
    detention_nfn   = norm_positive("detention_rate")
    trend_nfn       = norm_clipped("trend_slope")
    multi_ship_nfn  = norm_positive("multi_ship_rate")
    collision_nfn   = norm_positive("collision_rate")
    open_sea_nfn    = norm_positive("open_sea_rate")
    # Event entropy: higher = more diverse causes = more systemic risk
    entropy_nfn     = norm_positive("event_entropy")
    # Investigation rate: higher = more reports filed per accident.
    # Empirically correlates POSITIVELY with future accidents (r≈+0.44):
    # countries with many investigations tend to have more/severer accidents.
    # Do NOT invert — treat as a risk amplifier, not safety indicator.
    invest_nfn = norm_positive("investigation_rate")
    solas_nfn       = norm_positive("solas_noncompliance_rate")
    # Excess factor: higher positive = riskier; clip negatives to 0
    excess_nfn      = norm_clipped("excess_factor_avg")
    excess_tr_nfn   = norm_clipped("excess_factor_trend")
    # Fleet growth: rapid positive growth = more ships, less oversight
    fleet_gr_nfn    = norm_clipped("fleet_growth_rate")
    fleet_vol_nfn   = norm_positive("fleet_volatility")

    total_weight = sum(weights.values()) or 1.0

    for row in rows:
        def clip0(v):
            return max(v, 0.0)

        row["accident_rate_norm"]          = acc_rate_nfn(row["accident_rate"])
        # Severity blend: weighted severity + tail-risk proportion
        row["severity_risk_norm"]          = (
            severity_nfn(row["avg_severity_risk"]) * 0.6
            + vsmc_nfn(row["vsmc_rate"]) * 0.4
        )
        row["ship_type_risk_norm"]         = ship_type_nfn(row["avg_ship_type_risk"])
        row["flag_safety_risk_norm"]       = detention_nfn(row["detention_rate"])
        # Clip-before-norm for signed variables (improving direction → 0, not negative)
        row["trend_slope_norm"]            = trend_nfn(clip0(row["trend_slope"]))
        row["multi_ship_rate_norm"]        = multi_ship_nfn(row["multi_ship_rate"])
        row["collision_rate_norm"]         = collision_nfn(row["collision_rate"])
        row["open_sea_rate_norm"]          = open_sea_nfn(row["open_sea_rate"])
        row["event_entropy_norm"]          = entropy_nfn(row["event_entropy"])
        row["investigation_rate_norm"]     = invest_nfn(row["investigation_rate"])
        row["solas_noncompliance_norm"]    = solas_nfn(row["solas_noncompliance_rate"])
        row["excess_factor_norm"]          = excess_nfn(clip0(row["excess_factor_avg"]))
        row["excess_factor_trend_norm"]    = excess_tr_nfn(clip0(row["excess_factor_trend"]))
        row["fleet_growth_norm"]           = fleet_gr_nfn(clip0(row["fleet_growth_rate"]))
        row["fleet_volatility_norm"]       = fleet_vol_nfn(row["fleet_volatility"])

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

    rows.sort(key=lambda row: row["risk_score"], reverse=True)
    return rows


# ---------------------------------------------------------------------------
# Temporal trend detection (monthly-interpolated exposure)
# ---------------------------------------------------------------------------

def compute_temporal_trends():
    """Per-flag accident rates computed with monthly-interpolated fleet exposure.

    For each year Y and flag F:
        exposure_Y = sum of interpolate_fleet_size(Y, month) / 12  (ship-years)
        rate_Y     = accidents_in_Y / exposure_Y

    For each month M:
        exposure_M = interpolate_fleet_size(Y, M) / 12  (ship-years)
        rate_M     = accidents_in_M / exposure_M

    The monthly interpolation uses the user-specified formula:
        fleet_at(Y, m) = fleet[Y] + (fleet[Y+1] - fleet[Y]) / 12 * (m - 1)

    This corrects the previous approach of using a single annual snapshot,
    which was inaccurate for countries with rapidly growing or shrinking fleets.
    """
    fleet_by_year_all = load_fleet_by_year()
    fleet_year_sizes = {k: v[1] for k, v in fleet_by_year_all.items()}

    # Count accidents per flag by year and by month
    accidents_by_flag_year = defaultdict(lambda: defaultdict(int))
    accidents_by_flag_month = defaultdict(lambda: defaultdict(int))
    flag_display_name = {}
    for row in load_accident_rows():
        if row["date"] is None:
            continue
        key = row["flag_key"]
        accidents_by_flag_year[key][row["date"].year] += 1
        month_key = (row["date"].year, row["date"].month)
        accidents_by_flag_month[key][month_key] += 1
        flag_display_name[key] = row["flag"]

    all_keys = sorted(set(fleet_year_sizes.keys()) | set(accidents_by_flag_year.keys()))

    trends = []
    for key in all_keys:
        fleet_entry = fleet_by_year_all.get(key)
        display_name = fleet_entry[0] if fleet_entry else flag_display_name.get(key, key.title())
        year_sizes = fleet_entry[1] if fleet_entry else {}
        yearly_accident_data = accidents_by_flag_year.get(key, {})
        monthly_accident_data = accidents_by_flag_month.get(key, {})

        yearly = []
        monthly = []
        for year in FLEET_YEARS:
            exp = year_exposure(year_sizes, year)
            acc_count = yearly_accident_data.get(year, 0)
            rate = acc_count / exp if exp > 0 else 0.0
            yearly.append({
                "year": year,
                "accident_rate": rate,
                "accident_count": acc_count,
                "exposure": exp,
                "has_fleet_data": exp > 0,
            })

            for month in range(1, 13):
                monthly_exp = interpolate_fleet_size(year_sizes, year, month) / 12
                monthly_acc_count = monthly_accident_data.get((year, month), 0)
                monthly_rate = (
                    monthly_acc_count / monthly_exp if monthly_exp > 0 else 0.0
                )
                monthly.append({
                    "date": f"{year}-{month:02d}",
                    "year": year,
                    "month": month,
                    "accident_rate": monthly_rate,
                    "accident_count": monthly_acc_count,
                    "exposure": monthly_exp,
                    "has_fleet_data": monthly_exp > 0,
                })

        trends.append({
            "flag": display_name,
            "flag_key": key,
            "yearly": yearly,
            "monthly": monthly,
        })

    return trends

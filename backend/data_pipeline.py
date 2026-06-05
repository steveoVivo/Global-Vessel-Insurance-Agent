import csv
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR  = BASE_DIR / "data"
ACCIDENT_CSV = DATA_DIR / "accident_data_20110101_20251231.csv"
FLEET_CSV    = DATA_DIR / "Num_of_ships_by_flag.csv"
PARIS_CSV    = DATA_DIR / "paris_mou.csv"

FLEET_YEARS = list(range(2011, 2026))

# ---------------------------------------------------------------------------
# Risk component weights
# ---------------------------------------------------------------------------
# Default model selected from accident-rate-excluded evaluation:
# event_entropy + investigation + flag_safety + ship_type + open_sea + solas_noncompliance.
DEFAULT_WEIGHTS = {
    "accident_rate":       0.00,
    "event_entropy":       1/4,    # Shannon entropy of accident-cause diversity
    "trend":               0.00,
    "investigation":       0.00,
    "flag_safety":         0.00,
    "severity":            0.00,
    "ship_type":           1/4,    # accident-proneness of involved vessel types
    "multi_ship":          0.00,
    "collision":           0.00,
    "open_sea":            1/4,    # share of accidents in open-sea locations
    "solas_noncompliance": 0.00,
    "excess_factor":       0.00,
    "excess_factor_trend": 0.00,
    "fleet_growth":        0.00,
    "fleet_volatility":    1/4,    # RMSE of annual fleet size changes / mean fleet size
}

# ---------------------------------------------------------------------------
# Name normalisation
# ---------------------------------------------------------------------------

# Alternate / official names → canonical short keys used throughout the pipeline.
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
    # Accident CSV names → fleet canonical keys
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
    # Fleet official names → canonical short keys
    "china, hong kong sar":                "hong kong",
    "china, macao sar":                    "macau",
    "china, taiwan province of":           "taiwan",
    "united republic of tanzania":         "tanzania",
    "republic of moldova":                 "moldova",
    "syrian arab republic":                "syria",
}

# Countries with commas in their names need a temporary placeholder before
# splitting the comma-separated "Flag Administrations" field.
COMMA_NAME_PLACEHOLDERS = {
    "Hong Kong, China":              "__HONG_KONG_CHINA__",
    "Korea, Republic of":            "__KOREA_REPUBLIC_OF__",
    "Moldova, Republic of":          "__MOLDOVA_REPUBLIC_OF__",
    "Tanzania, United Republic of":  "__TANZANIA_UNITED_REPUBLIC_OF__",
}

# Rows to skip when reading the fleet CSV (continents, aggregates, etc.)
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

SEVERITY_SCORES = {
    "marine incident":              0.25,
    "marine casualty":              0.65,
    "very serious marine casualty": 1.00,
}


def normalize_flag_name(name: str) -> str:
    cleaned = re.sub(r"\s+", " ", (name or "").strip())
    # Strip trailing parenthesised suffixes, but keep "(UK)" and "(China)"
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


def split_flag_administrations(value: str) -> list[str]:
    """Split a "Flag Administrations" cell into individual flag strings."""
    cleaned = re.sub(r"\s+", " ", (value or "").strip())
    if not cleaned:
        return []

    placeholder_to_name = {v: k for k, v in COMMA_NAME_PLACEHOLDERS.items()}
    for original, placeholder in COMMA_NAME_PLACEHOLDERS.items():
        cleaned = cleaned.replace(original, placeholder)

    flags, seen = [], set()
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

def parse_int(value, default: int = 0) -> int:
    try:
        return int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def parse_float(value, default: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Normalization utilities
# ---------------------------------------------------------------------------

def minmax_capped(values, percentile: int = 95):
    """Min-max normalisation capped at a percentile of nonzero values.

    Prevents a handful of extreme outliers from compressing the rest of the
    scale. Flags with value == 0 stay at 0; values above the cap are clamped
    to 1.0.
    """
    nonzero = sorted(v for v in values if v is not None and v > 0)
    if not nonzero:
        return lambda _: 0.0
    cap = nonzero[min(int(len(nonzero) * percentile / 100), len(nonzero) - 1)]
    if cap <= 0:
        return lambda _: 0.0
    return lambda v: min((v if v is not None else 0.0) / cap, 1.0)


def ols_slope(xy_pairs: list) -> float:
    """OLS slope of [(x, y), …]. Returns 0.0 for fewer than 3 points."""
    if len(xy_pairs) < 3:
        return 0.0
    xs  = [p[0] for p in xy_pairs]
    ys  = [p[1] for p in xy_pairs]
    n   = len(xs)
    sx  = sum(xs);  sy  = sum(ys)
    sxy = sum(x * y for x, y in zip(xs, ys))
    sx2 = sum(x * x for x in xs)
    d   = n * sx2 - sx ** 2
    return (n * sxy - sx * sy) / d if d else 0.0


def shannon_entropy(counts: dict) -> float:
    total = sum(counts.values())
    if total == 0:
        return 0.0
    return -sum((c / total) * math.log2(c / total) for c in counts.values() if c > 0)


# ---------------------------------------------------------------------------
# Fleet size interpolation
# ---------------------------------------------------------------------------

def interpolate_fleet_size(year_sizes: dict, year: int, month: int) -> float:
    """Fleet size at (year, month) via linear interpolation between annual snapshots.

    monthly_increment = (fleet[year+1] - fleet[year]) / 12
    fleet_at_month    = fleet[year] + monthly_increment * (month - 1)

    Falls back to fleet[year] if the next year is unavailable.
    """
    current = year_sizes.get(year, 0)
    if current <= 0:
        return 0.0
    next_val = year_sizes.get(year + 1, 0)
    if next_val > 0:
        return current + (next_val - current) / 12 * (month - 1)
    return float(current)


def year_exposure(year_sizes: dict, year: int) -> float:
    """Total ship-year exposure for one calendar year (sum of monthly interpolations / 12)."""
    return sum(interpolate_fleet_size(year_sizes, year, m) for m in range(1, 13)) / 12


# ---------------------------------------------------------------------------
# CSV loaders
# ---------------------------------------------------------------------------

def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def accident_date(row: dict):
    value = row.get("Occurrence date and time", "")
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def load_fleet_rows() -> list[dict]:
    """2025 fleet size per flag (used for vessel_count in the API payload)."""
    best: dict = {}
    for row in read_csv(FLEET_CSV):
        flag = row.get("Economy_Label", "").strip()
        flag_key = normalize_flag_name(flag)
        if flag_key in REGION_ROWS:
            continue
        fleet_size = parse_int(row.get("2025_Number_of_ships_Value"))
        if flag_key not in best or fleet_size > best[flag_key]["fleet_size"]:
            best[flag_key] = {"flag": flag, "flag_key": flag_key, "fleet_size": fleet_size}
    return list(best.values())


def load_fleet_by_year() -> dict:
    """Annual fleet sizes per flag: {flag_key: (display_name, {year: fleet_size})}"""
    result = {}
    for row in read_csv(FLEET_CSV):
        flag = row.get("Economy_Label", "").strip()
        flag_key = normalize_flag_name(flag)
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
        existing = result.get(flag_key)
        if existing is None:
            result[flag_key] = (flag, year_sizes)
        else:
            # Fill in missing years from secondary rows (e.g. "Sudan (...2011)")
            merged = dict(existing[1])
            for yr, sz in year_sizes.items():
                if yr not in merged:
                    merged[yr] = sz
            result[flag_key] = (existing[0], merged)
    return result


def load_paris_data() -> list[dict]:
    """Multi-year Paris MoU data from paris_mou.csv."""
    rows = []
    for row in read_csv(PARIS_CSV):
        flag = row.get("flag", "").strip()
        flag_key = normalize_flag_name(flag)
        if not flag_key:
            continue
        rows.append({
            "year":             parse_int(row.get("year", 0)),
            "flag":             flag,
            "flag_key":         flag_key,
            "category":         row.get("category", "").strip().lower(),
            "flag_safety_risk": parse_float(row.get("flag_safety_risk"), 0.5),
            "inspections":      parse_int(row.get("inspections", 0)),
            "detentions":       parse_int(row.get("detentions", 0)),
            "excess_factor":    parse_float(row.get("excess_factor", 0.0)),
        })
    return rows


def aggregate_paris(paris_data: list, start_year: int, end_year: int,
                    valid_flag_keys: set = None) -> dict:
    """Per-flag Paris MoU aggregates for a given analysis period.

    valid_flag_keys: if provided, skips OCR-artifact entries (e.g. classification
        society names that appear as flags in corrupted PDF extracts).

    Returns {flag_key: {detention_rate, excess_factor_avg, excess_factor_trend, …}}
    """
    relevant = [r for r in paris_data if start_year <= r["year"] <= end_year] or paris_data

    by_flag = {}
    for row in relevant:
        key = row["flag_key"]
        if valid_flag_keys is not None and key not in valid_flag_keys:
            continue
        if key not in by_flag:
            by_flag[key] = {
                "flag": row["flag"], "flag_key": key,
                "inspections_sum": 0, "detentions_sum": 0,
                "excess_factor_pairs": [],
                "categories": [],
            }
        by_flag[key]["inspections_sum"] += parse_int(row.get("inspections", 0))
        by_flag[key]["detentions_sum"]  += parse_int(row.get("detentions", 0))
        by_flag[key]["categories"].append(row.get("category", "unlisted"))
        if row.get("excess_factor") not in (None, ""):
            try:
                by_flag[key]["excess_factor_pairs"].append((float(row["year"]), float(row["excess_factor"])))
            except (ValueError, KeyError):
                pass

    result = {}
    for key, data in by_flag.items():
        insp, det = data["inspections_sum"], data["detentions_sum"]
        # det > insp is physically impossible; such entries are OCR-corrupted rows.
        detention_rate = det / insp if insp > 0 and det <= insp else 0.0

        ef_pairs = data["excess_factor_pairs"]
        excess_factor_avg   = sum(ef for _, ef in ef_pairs) / len(ef_pairs) if ef_pairs else 0.0
        excess_factor_trend = ols_slope(ef_pairs) if ef_pairs else 0.0

        cat_counts = {}
        for c in data["categories"]:
            cat_counts[c] = cat_counts.get(c, 0) + 1

        result[key] = {
            "flag":                data["flag"],
            "flag_key":            key,
            "paris_mou_category":  max(cat_counts, key=lambda c: cat_counts[c]),
            "detention_rate":      detention_rate,
            "excess_factor_avg":   excess_factor_avg,
            "excess_factor_trend": excess_factor_trend,
        }
    return result


def load_accident_rows(start_year: int = None, end_year: int = None) -> list[dict]:
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
# Accident metrics
# ---------------------------------------------------------------------------

# Location values treated as "open sea" and "known location" for open_sea_rate
_OPEN_SEA  = {"open sea"}
_VALID_LOC = {
    "open sea", "coastal waters", "port", "at berth", "anchorage",
    "port approach", "river", "inland waters", "strait/channel",
    "canal", "archipelagos", "offshore installation", "traffic separation scheme",
}


def compute_accident_metrics(start_year: int = None, end_year: int = None) -> list[dict]:
    """Per-flag accident metrics using monthly-interpolated fleet exposure.

    accident_rate = accident_count / total_ship_year_exposure
    where exposure uses monthly interpolation:
        fleet_at(Y, m) = fleet[Y] + (fleet[Y+1] - fleet[Y]) / 12 * (m - 1)
    """
    fleet_year_sizes = {k: v[1] for k, v in load_fleet_by_year().items()}
    _start = start_year or FLEET_YEARS[0]
    _end   = end_year   or FLEET_YEARS[-1]

    accidents = load_accident_rows(start_year, end_year)

    ship_type_counts = Counter(
        row.get("Ship types", "").strip()
        for row in accidents if row.get("Ship types", "").strip()
    )
    max_stc = max(ship_type_counts.values(), default=1)
    ship_type_risk = {
        st: math.log1p(c) / math.log1p(max_stc)
        for st, c in ship_type_counts.items()
    }

    by_flag = defaultdict(lambda: {
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

    for row in accidents:
        b = by_flag[row["flag_key"]]
        b["flag"]     = row["flag"]
        b["flag_key"] = row["flag_key"]
        b["accident_count"] += 1

        sev_label = row.get("Casualty severity", "").strip().casefold()
        sev_score = SEVERITY_SCORES.get(sev_label)
        if sev_score is not None:
            b["severity_total"] += sev_score
            b["severity_count"] += 1
        if sev_label == "very serious marine casualty":
            b["vsmc_count"] += 1

        ship_type = row.get("Ship types", "").strip()
        if ship_type:
            b["ship_type_risk_total"] += ship_type_risk.get(ship_type, 0.0)
            b["ship_type_count"] += 1

        if parse_int(row.get("Number of ships involved", "1"), default=1) >= 2:
            b["multi_ship_count"] += 1

        ev = row.get("Casualty event", "").strip()
        ev_cat = ev.split(" - ")[0].strip() if " - " in ev else ev
        if ev_cat:
            b["event_counts"][ev_cat] = b["event_counts"].get(ev_cat, 0) + 1
        if ev_cat.lower().startswith("collision"):
            b["collision_count"] += 1

        loc = row.get("Location", "").strip().lower()
        if loc in _VALID_LOC:
            b["location_known_count"] += 1
            if loc in _OPEN_SEA:
                b["open_sea_count"] += 1

        b["investigation_total"] += parse_int(row.get("Number of investigation reports", "0"))

        solas = row.get("SOLAS status", "").strip()
        if solas:
            b["solas_known_count"] += 1
            if ": N" in solas:
                b["solas_noncompliant_count"] += 1

    metrics = []
    for bucket in by_flag.values():
        sev_cnt   = bucket.pop("severity_count")
        st_cnt    = bucket.pop("ship_type_count")
        sev_tot   = bucket.pop("severity_total")
        st_tot    = bucket.pop("ship_type_risk_total")
        ev_counts = bucket.pop("event_counts")
        acc       = bucket["accident_count"]
        loc_known = bucket["location_known_count"]

        bucket["avg_severity_risk"]  = sev_tot / sev_cnt if sev_cnt else 0.0
        bucket["avg_ship_type_risk"] = st_tot  / st_cnt  if st_cnt  else 0.0
        bucket["vsmc_rate"]          = bucket["vsmc_count"]       / acc       if acc       else 0.0
        bucket["multi_ship_rate"]    = bucket["multi_ship_count"]  / acc       if acc       else 0.0
        bucket["collision_rate"]     = bucket["collision_count"]   / acc       if acc       else 0.0
        bucket["open_sea_rate"]      = bucket["open_sea_count"]    / loc_known if loc_known else 0.0
        bucket["event_entropy"]      = shannon_entropy(ev_counts)
        bucket["investigation_rate"] = bucket["investigation_total"] / acc     if acc       else 0.0
        solas_k = bucket["solas_known_count"]
        bucket["solas_noncompliance_rate"] = (
            bucket["solas_noncompliant_count"] / solas_k if solas_k else 0.0
        )

        year_sizes = fleet_year_sizes.get(bucket["flag_key"], {})
        exposure = sum(year_exposure(year_sizes, y) for y in range(_start, _end + 1))
        bucket["accident_rate"] = bucket["accident_count"] / exposure if exposure > 0 else 0.0

        for key in ("vsmc_count", "multi_ship_count", "collision_count",
                    "open_sea_count", "location_known_count",
                    "investigation_total", "solas_noncompliant_count", "solas_known_count"):
            bucket.pop(key, None)

        metrics.append(bucket)

    metrics.sort(key=lambda r: r["flag"])
    return metrics


# ---------------------------------------------------------------------------
# Trend slope
# ---------------------------------------------------------------------------

def compute_trend_slopes(start_year: int = None, end_year: int = None) -> dict:
    """OLS slope of yearly exposure-weighted accident rate per flag.

    slope > 0 → worsening (higher future risk)
    slope < 0 → improving

    Returns {flag_key: slope} in units of accidents/ship-year per year.
    """
    fleet_year_sizes = {k: v[1] for k, v in load_fleet_by_year().items()}
    _start = start_year or FLEET_YEARS[0]
    _end   = end_year   or FLEET_YEARS[-1]
    years  = [y for y in FLEET_YEARS if _start <= y <= _end]

    accidents_by_flag_year = defaultdict(lambda: defaultdict(int))
    for row in load_accident_rows(start_year, end_year):
        if row["date"] is None:
            continue
        accidents_by_flag_year[row["flag_key"]][row["date"].year] += 1

    slopes = {}
    for key in set(fleet_year_sizes) | set(accidents_by_flag_year):
        year_sizes    = fleet_year_sizes.get(key, {})
        accident_data = accidents_by_flag_year.get(key, {})
        pairs = [
            (float(y), accident_data.get(y, 0) / year_exposure(year_sizes, y))
            for y in years if year_exposure(year_sizes, y) > 0
        ]
        slopes[key] = ols_slope(pairs)
    return slopes


# ---------------------------------------------------------------------------
# Fleet features
# ---------------------------------------------------------------------------

def compute_fleet_features(start_year: int = None, end_year: int = None) -> dict:
    """Fleet-based risk features from annual fleet size data.

    fleet_growth_rate = (fleet[end] - fleet[start]) / fleet[start]
    fleet_volatility  = RMSE of annual changes / mean fleet size

    Returns {flag_key: {fleet_growth_rate, fleet_volatility}}
    """
    _start = start_year or FLEET_YEARS[0]
    _end   = end_year   or FLEET_YEARS[-1]

    result = {}
    for flag_key, (_, year_sizes) in load_fleet_by_year().items():
        sizes = [year_sizes[y] for y in range(_start, _end + 1) if y in year_sizes]
        if not sizes:
            continue
        first, last = sizes[0], sizes[-1]
        growth_rate = (last - first) / first if first > 0 else 0.0

        if len(sizes) >= 2:
            changes   = [abs(sizes[i + 1] - sizes[i]) for i in range(len(sizes) - 1)]
            mean_size = sum(sizes) / len(sizes)
            rmse      = (sum(c ** 2 for c in changes) / len(changes)) ** 0.5
            volatility = rmse / mean_size if mean_size > 0 else 0.0
        else:
            volatility = 0.0

        result[flag_key] = {"fleet_growth_rate": growth_rate, "fleet_volatility": volatility}
    return result


# ---------------------------------------------------------------------------
# Risk score assembly
# ---------------------------------------------------------------------------

def build_merged_rows(start_year: int = None, end_year: int = None, weights: dict = None) -> list[dict]:
    """Assemble per-flag risk rows with all computed features and normalised scores.

    All normalised fields are included in the payload so callers can override
    weights via query params without changing the response format.
    """
    weights = weights or DEFAULT_WEIGHTS
    _start  = start_year or FLEET_YEARS[0]
    _end    = end_year   or FLEET_YEARS[-1]

    fleet_by_key    = {r["flag_key"]: r for r in load_fleet_rows()}
    accident_by_key = {r["flag_key"]: r for r in compute_accident_metrics(start_year, end_year)}
    valid_keys      = set(fleet_by_key) | set(accident_by_key)
    paris_by_key    = aggregate_paris(load_paris_data(), _start, _end, valid_flag_keys=valid_keys)
    trend_by_key    = compute_trend_slopes(start_year, end_year)
    fleet_feat_by   = compute_fleet_features(start_year, end_year)

    all_keys = sorted(set(fleet_by_key) | set(paris_by_key) | set(accident_by_key))

    def af(d, k):
        return parse_float(d.get(k))

    rows = []
    for key in all_keys:
        fleet    = fleet_by_key.get(key, {})
        paris    = paris_by_key.get(key, {})
        acc      = accident_by_key.get(key, {})
        fleet_ft = fleet_feat_by.get(key, {})
        rows.append({
            "flag":     fleet.get("flag") or paris.get("flag") or acc.get("flag") or key.title(),
            "flag_key": key,
            "fleet_size": parse_int(fleet.get("fleet_size")),
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
            "paris_mou_category":       paris.get("paris_mou_category", "unlisted"),
            "detention_rate":           af(paris, "detention_rate"),
            "excess_factor_avg":        af(paris, "excess_factor_avg"),
            "excess_factor_trend":      af(paris, "excess_factor_trend"),
            "trend_slope":              trend_by_key.get(key, 0.0),
            "fleet_growth_rate":        af(fleet_ft, "fleet_growth_rate"),
            "fleet_volatility":         af(fleet_ft, "fleet_volatility"),
        })

    # ------------------------------------------------------------------
    # Normalisation functions
    # ------------------------------------------------------------------
    def norm_pos(field):
        return minmax_capped([r[field] for r in rows])

    def norm_clip(field):
        return minmax_capped([max(r[field], 0.0) for r in rows])

    def norm_trend(field, min_accidents=5, lo_pct=5, hi_pct=95):
        """Signed normalisation using percentile-clipped range of qualified flags.

        Maps [lo_pct-ile, hi_pct-ile] → [0, 1].  Improves (negative) → 0,
        worsens (positive) → 1.  Percentile clipping prevents micro-state
        outliers from compressing all other countries near the midpoint.
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

    acc_rate_nfn   = norm_pos("accident_rate")
    severity_nfn   = norm_pos("avg_severity_risk")
    vsmc_nfn       = norm_pos("vsmc_rate")
    ship_type_nfn  = norm_pos("avg_ship_type_risk")
    detention_nfn  = norm_pos("detention_rate")
    trend_nfn      = norm_trend("trend_slope")
    multi_ship_nfn = norm_pos("multi_ship_rate")
    collision_nfn  = norm_pos("collision_rate")
    open_sea_nfn   = norm_pos("open_sea_rate")
    entropy_nfn    = norm_pos("event_entropy")
    invest_nfn     = norm_pos("investigation_rate")
    solas_nfn      = norm_pos("solas_noncompliance_rate")
    excess_nfn     = norm_clip("excess_factor_avg")
    excess_tr_nfn  = norm_clip("excess_factor_trend")
    fleet_gr_nfn   = norm_clip("fleet_growth_rate")
    fleet_vol_nfn  = norm_pos("fleet_volatility")

    total_weight = sum(weights.values()) or 1.0

    for row in rows:
        c = lambda v: max(v, 0.0)  # noqa: E731 — clip-to-zero shorthand

        row["accident_rate_norm"]       = acc_rate_nfn(row["accident_rate"])
        row["severity_risk_norm"]       = (
            severity_nfn(row["avg_severity_risk"]) * 0.6 + vsmc_nfn(row["vsmc_rate"]) * 0.4
        )
        row["ship_type_risk_norm"]      = ship_type_nfn(row["avg_ship_type_risk"])
        row["flag_safety_risk_norm"]    = detention_nfn(row["detention_rate"])
        row["trend_slope_norm"]         = trend_nfn(row["trend_slope"])
        row["multi_ship_rate_norm"]     = multi_ship_nfn(row["multi_ship_rate"])
        row["collision_rate_norm"]      = collision_nfn(row["collision_rate"])
        row["open_sea_rate_norm"]       = open_sea_nfn(row["open_sea_rate"])
        row["event_entropy_norm"]       = entropy_nfn(row["event_entropy"])
        row["investigation_rate_norm"]  = invest_nfn(row["investigation_rate"])
        row["solas_noncompliance_norm"] = solas_nfn(row["solas_noncompliance_rate"])
        row["excess_factor_norm"]       = excess_nfn(c(row["excess_factor_avg"]))
        row["excess_factor_trend_norm"] = excess_tr_nfn(c(row["excess_factor_trend"]))
        row["fleet_growth_norm"]        = fleet_gr_nfn(c(row["fleet_growth_rate"]))
        row["fleet_volatility_norm"]    = fleet_vol_nfn(row["fleet_volatility"])

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
# Temporal trends (monthly granularity for the trend chart)
# ---------------------------------------------------------------------------

def compute_temporal_trends() -> list[dict]:
    """Per-flag accident rates at yearly and monthly granularity.

    For each year Y and flag F:
        exposure_Y = sum of interpolate_fleet_size(Y, m) / 12  (ship-years)
        rate_Y     = accidents_in_Y / exposure_Y

    For each month M:
        exposure_M = interpolate_fleet_size(Y, M) / 12  (ship-years)
        rate_M     = accidents_in_M / exposure_M
    """
    fleet_by_year_all = load_fleet_by_year()
    fleet_year_sizes  = {k: v[1] for k, v in fleet_by_year_all.items()}

    accidents_by_flag_year  = defaultdict(lambda: defaultdict(int))
    accidents_by_flag_month = defaultdict(lambda: defaultdict(int))
    flag_display_name = {}

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
        year_sizes   = fleet_entry[1] if fleet_entry else {}
        by_year      = accidents_by_flag_year.get(key, {})
        by_month     = accidents_by_flag_month.get(key, {})

        yearly, monthly = [], []
        for year in FLEET_YEARS:
            exp       = year_exposure(year_sizes, year)
            acc_count = by_year.get(year, 0)
            yearly.append({
                "year":           year,
                "accident_rate":  acc_count / exp if exp > 0 else 0.0,
                "accident_count": acc_count,
                "exposure":       exp,
                "has_fleet_data": exp > 0,
            })
            for month in range(1, 13):
                m_exp   = interpolate_fleet_size(year_sizes, year, month) / 12
                m_acc   = by_month.get((year, month), 0)
                monthly.append({
                    "date":           f"{year}-{month:02d}",
                    "year":           year,
                    "month":          month,
                    "accident_rate":  m_acc / m_exp if m_exp > 0 else 0.0,
                    "accident_count": m_acc,
                    "exposure":       m_exp,
                    "has_fleet_data": m_exp > 0,
                })

        trends.append({"flag": display_name, "flag_key": key, "yearly": yearly, "monthly": monthly})

    return trends

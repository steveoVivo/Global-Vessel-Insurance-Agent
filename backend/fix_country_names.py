#!/usr/bin/env python3
"""
fix_country_names.py — Normalize country/flag names in all datasets to match
the Google Canonical Country CSV used by the frontend (countries.ts).

Run once from the backend/ directory:
    python fix_country_names.py

Modifies in place (backups written as <file>.bak before any change):
  data/archive/Num_of_Ships_2011_2025.csv  — Economy_Label column
  data/paris_mou.csv                        — flag column
  data/accident_data_20110101_20251231.csv  — Flag Administrations column
  data/merged_vessel_risk_by_flag.csv       — flag column
  data/accident_risk_by_flag.csv            — flag column
"""

import csv
import io
import re
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# ---------------------------------------------------------------------------
# Comprehensive mapping: non-canonical name → canonical name (from countries.ts)
# ---------------------------------------------------------------------------

CANONICAL_MAP = {
    # --- Fleet data (Num_of_Ships Economy_Label) ---
    "Bolivia (Plurinational State of)":       "Bolivia",
    "Brunei Darussalam":                       "Brunei",
    "Cabo Verde":                              "Cape Verde",
    "China, Hong Kong SAR":                    "Hong Kong",
    "China, Macao SAR":                        "Macau",
    "China, Taiwan Province of":              "Taiwan",
    "Cote d'Ivoire":                           "Côte d'Ivoire",
    "Czechia":                                 "Czech Republic",
    "Dem. People's Rep. of Korea":            "North Korea",
    "Dem. Rep. of the Congo":                 "Congo [DRC]",
    "Democratic People's Republic of Korea":  "North Korea",
    "Democratic Republic of the Congo":       "Congo [DRC]",
    "Eswatini":                               "Swaziland",
    "Falkland Islands (Malvinas)":            "Falkland Islands [Islas Malvinas]",
    "Iran (Islamic Republic of)":             "Iran",
    "Lao People's Dem. Rep.":                 "Laos",
    "Micronesia (Federated States of)":       "Micronesia",
    "Myanmar":                                "Myanmar [Burma]",
    "Netherlands (Kingdom of the)":           "Netherlands",
    "North Macedonia":                        "Macedonia [FYROM]",
    "Republic of Korea":                      "South Korea",
    "Republic of Moldova":                    "Moldova",
    "Reunion":                                "Réunion",
    "Russian Federation":                     "Russia",
    "Saint Helena":                           "St. Helena",
    "Saint Kitts and Nevis":                  "St. Kitts and Nevis",
    "Saint Lucia":                            "St. Lucia",
    "Saint Pierre and Miquelon":              "St. Pierre and Miquelon",
    "Saint Vincent and the Grenadines":       "St. Vincent and Grenadines",
    "Sao Tome and Principe":                  "São Tomé and Príncipe",
    "Syrian Arab Republic":                   "Syria",
    "United Republic of Tanzania":            "Tanzania",
    "Venezuela (Bolivarian Rep. of)":         "Venezuela",
    "Venezuela (Bolivarian Republic of)":     "Venezuela",
    "Viet Nam":                               "Vietnam",
    "Wallis and Futuna Islands":              "Wallis and Futuna",

    # --- Historical / dissolved entries ---
    "Federal Republic of Germany":            "Germany",
    "Democratic Republic of Germany":         "Germany",
    "Ethiopia (...1991)":                     "Ethiopia",
    "Indonesia (...2002)":                    "Indonesia",
    "Sudan (...2011)":                        "Sudan",
    "Panama, excluding Canal Zone":           "Panama",

    # --- Accident data (Flag Administrations) ---
    "Anguilla (United Kingdom)":              "Anguilla",
    "Bermuda (United Kingdom)":               "Bermuda",
    "British Virgin Islands (United Kingdom)": "British Virgin Islands",
    "Cayman Islands (United Kingdom)":        "Cayman Islands",
    "Curaçao (Kingdom of the Netherlands)":   "Netherlands Antilles",
    "DIS (Denmark)":                          "Denmark",
    "Falkland Islands (Malvinas)‡":      "Falkland Islands [Islas Malvinas]",
    "Faroes":                                 "Faroe Islands",
    "FIS (France)":                           "France",
    "French Polynesia (France)":              "French Polynesia",
    "French Southern Territories (France)":  "French Southern Territories",
    "Gibraltar (United Kingdom)":             "Gibraltar",
    "Greenland (Denmark)":                    "Greenland",
    "Guernsey (United Kingdom)":              "Guernsey",
    "Isle of Man (United Kingdom)":           "Isle of Man",
    "Macao":                                  "Macau",
    "MAR (Portugal)":                         "Portugal",
    "Netherlands (Kingdom of)":              "Netherlands",
    "NIS (Norway)":                           "Norway",
    "St. Helena (United Kingdom)":            "St. Helena",
    "St Vincent and the Grenadines":          "St. Vincent and Grenadines",
    "Türkiye":                                "Turkey",
    "Turkiye":                                "Turkey",
    "United States of America":              "United States",
    "Wallis and Futuna (France)":             "Wallis and Futuna",
    "Zanzibar (United Republic of Tanzania)": "Tanzania",

    # --- Paris MoU data ---
    "Bermuda (UK)":                           "Bermuda",
    "Bermuda UK":                             "Bermuda",
    "Cayman Islands (UK)":                    "Cayman Islands",
    "Cayman Islands UK":                      "Cayman Islands",
    "Congo Republic of the":                  "Congo [Republic]",
    "Congo":                                  "Congo [Republic]",
    "Faroe Islands (DK)":                     "Faroe Islands",
    "Faroe Islands DK":                       "Faroe Islands",
    "Gibraltar (UK)":                         "Gibraltar",
    "Gibraltar UK":                           "Gibraltar",
    "Hong Kong (China)":                      "Hong Kong",
    "Hong Kong China":                        "Hong Kong",
    "Hong Kong, China":                       "Hong Kong",
    "Iran Islamic Republic of":               "Iran",
    "Isle of Man (UK)":                       "Isle of Man",
    "Isle of Man UK":                         "Isle of Man",
    "Jersey (UK)":                            "Jersey",
    "Korea Democratic People' Rep.":          "North Korea",
    "Korea Republic of":                      "South Korea",
    "Korea, Republic of":                     "South Korea",
    "Libyan Arab Jamahiriya":                 "Libya",
    "lran Islamic Republic of":               "Iran",   # OCR error: l→I
    "Man Isle of UK":                         "Isle of Man",
    "Moldova Republic of":                    "Moldova",
    "Moldova, Republic of":                   "Moldova",
    "St Kitts and Nevis":                     "St. Kitts and Nevis",
    "Tanzania United Rep.":                   "Tanzania",
    "Tanzania United Republic of":            "Tanzania",
    "Tanzania, United Republic of":           "Tanzania",
}

# Country names that contain commas — must be substituted BEFORE splitting
# the Flag Administrations field on commas.  Map to their canonical names.
COMMA_NAMES = {
    "Hong Kong, China":           "Hong Kong",
    "Korea, Republic of":         "South Korea",
    "Moldova, Republic of":       "Moldova",
    "Tanzania, United Republic of": "Tanzania",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def canonical(name: str) -> str:
    """Return canonical name for *name*, or *name* unchanged if already canonical."""
    return CANONICAL_MAP.get(name.strip(), name.strip())


def fix_flag_administrations(value: str) -> str:
    """Normalize a Flag Administrations cell (may contain multiple flags)."""
    cleaned = (value or "").strip()
    if not cleaned:
        return cleaned

    # Replace comma-containing country names before splitting on commas
    for original, replacement in COMMA_NAMES.items():
        cleaned = cleaned.replace(original, replacement)

    parts = re.split(r"\s*[,;]\s*", cleaned)
    fixed = []
    for part in parts:
        part = part.strip()
        if part:
            fixed.append(canonical(part))
    return ", ".join(fixed)


# ---------------------------------------------------------------------------
# Per-file processors
# ---------------------------------------------------------------------------

def fix_simple_csv(path: Path, col: str) -> int:
    """Fix *col* in a simple CSV (one flag per cell). Returns change count."""
    rows = []
    changes = 0
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        if fieldnames is None or col not in fieldnames:
            print(f"  [skip] {path.name}: column '{col}' not found")
            return 0
        for row in reader:
            old = row[col]
            new = canonical(old)
            if old != new:
                row[col] = new
                changes += 1
            rows.append(row)

    if changes:
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    return changes


def fix_accident_csv(path: Path) -> int:
    """Fix the Flag Administrations column in the accident CSV. Returns change count."""
    rows = []
    changes = 0
    col = "Flag Administrations"

    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        if fieldnames is None or col not in fieldnames:
            print(f"  [skip] {path.name}: column '{col}' not found")
            return 0
        for row in reader:
            # Drop the overflow key produced when a row has more fields than the header
            row.pop(None, None)
            old = row[col]
            new = fix_flag_administrations(old)
            if old != new:
                row[col] = new
                changes += 1
            rows.append(row)

    if changes:
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    return changes


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

FILES = [
    # (path,                                                  column,           fixer)
    (DATA_DIR / "archive" / "Num_of_Ships_2011_2025.csv",   "Economy_Label",  "simple"),
    (DATA_DIR / "paris_mou.csv",                             "flag",           "simple"),
    (DATA_DIR / "accident_data_20110101_20251231.csv",       None,             "accident"),
    (DATA_DIR / "merged_vessel_risk_by_flag.csv",            "flag",           "simple"),
    (DATA_DIR / "accident_risk_by_flag.csv",                 "flag",           "simple"),
]


def main():
    total = 0
    for path, col, fixer in FILES:
        if not path.exists():
            print(f"  [missing] {path.relative_to(BASE_DIR)}")
            continue

        if fixer == "accident":
            n = fix_accident_csv(path)
        else:
            n = fix_simple_csv(path, col)

        print(f"  {path.relative_to(BASE_DIR)}: {n} cell(s) updated")
        total += n

    print(f"\nDone. {total} total cell(s) updated across all datasets.")
    if total:
        print("Backup files written as <original>.bak")


if __name__ == "__main__":
    main()

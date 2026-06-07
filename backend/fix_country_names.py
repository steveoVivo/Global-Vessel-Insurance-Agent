#!/usr/bin/env python3
"""
fix_country_names.py — Normalize country/flag names in all datasets to match
the Google Canonical Country CSV used by the frontend (countries.ts).

Run once from the backend/ directory:
    python fix_country_names.py

Modifies in place (backups written as <file>.bak before any change):
  data/Num_of_ships_by_flag.csv             — Economy_Label column
  data/paris_mou.csv                        — flag column (garbage rows dropped)
  data/accident_data_20110101_20251231.csv  — Flag Administrations column
"""

import csv
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
    "Curaçao (Kingdom of the Netherlands)":   "Curacao",
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
    # OCR artifacts: trailing junk after real country name
    "Albania to":                             "Albania",
    "Comoros to":                             "Comoros",
    "Cook Islands Al":                        "Cook Islands",
    "Denmark at":                             "Denmark",
    "Germany ]":                              "Germany",
    "Marshall Islands =":                     "Marshall Islands",
    "Vanuatu Risk":                           "Vanuatu",
    "| Antigua and Barbuda":                  "Antigua and Barbuda",
    "' Singapore":                            "Singapore",
    # OCR artifacts: trailing quote (OCR reads closing " as part of name)
    "Bahamas \"":                             "Bahamas",
    "Belgium \"":                             "Belgium",
    "Bermuda UK \"":                          "Bermuda",
    "China \"":                               "China",
    "Hong Kong China ] \"":                   "Hong Kong",
    "Italy \"":                               "Italy",
    "Luxembourg \"":                          "Luxembourg",
    "Norway \"":                              "Norway",
    "United Kingdom \"":                      "United Kingdom",
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

    # --- Accident data additional fixes ---
    "Netherlands Antilles":                   "Curacao",
    "Republic of South Korea Korea":          "South Korea",
    "Denmark)":                               "Denmark",
    # Entries that are clearly not flag states (vessel/fishing names) — map to sentinel
    # so the caller can drop them; here we leave them unchanged (no mapping needed,
    # split_flag_administrations in data_pipeline.py already drops unknown keys).
}

# Country names that contain commas — must be substituted BEFORE splitting
# the Flag Administrations field on commas.  Map to their canonical names.
COMMA_NAMES = {
    "Hong Kong, China":           "Hong Kong",
    "Korea, Republic of":         "South Korea",
    "Moldova, Republic of":       "Moldova",
    "Tanzania, United Republic of": "Tanzania",
    # "FAS (Faeros, Denmark)" is the Faroe Islands second register — treat as Faroe Islands
    "FAS (Faeros, Denmark)":      "Faroe Islands",
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

# Flag values in paris_mou.csv that are classification societies or OCR garbage,
# not actual flag states.  Rows with these values are dropped entirely.
PARIS_GARBAGE_FLAGS = {
    "DNV GLAS", 'DNV GLAS DNVGL . "',
    "Germanischer Lloyd",
    "Inspeccion Clasificacion Maritima (INCLAMAR) INCLAMAR",
    "Intermaritime Certification Services ICS Class",
    "Macosnar Corporation",
    "Maritime Lloyd - Georgia", "Maritime Lloyd - Georgia ML", "Maritime Lloyd - Georgia | ML",
    "National Shipping Adjuster Inc. | NASHA",
    "Nippon Kaiji Kyokai", "Nippon Kaiji Kyokai INI .",
    "Overseas Marine Certification Services", "Overseas Marine Certification Services | OMCS",
    "Panama Maritime Documentation Services", "Panama Maritime Documentation Services | #\\| )",
    "Panama Shipping Registrar Inc. PSR", "Panama Shipping Registrar Inc. | PSR |",
    'Performance level DNV GL AS',
    "Registro Italiano Navale",
    "RINA Services . . . | RINA",
    "Shipping)",
    "Turkish Lloyd", "Turkish Lloyd TL",
    "chenmanitime Certification Services ICS Ics",
    "chermaritime Certification Services ICS",
    "Other",
    "low",
}


def fix_simple_csv(path: Path, col: str, drop_garbage: bool = False) -> tuple[int, int]:
    """Fix *col* in a simple CSV (one flag per cell).

    Returns (changes, dropped) counts.
    When *drop_garbage* is True, rows whose *col* value is in PARIS_GARBAGE_FLAGS
    are removed entirely.
    """
    rows = []
    changes = 0
    dropped = 0
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        if fieldnames is None or col not in fieldnames:
            print(f"  [skip] {path.name}: column '{col}' not found")
            return 0, 0
        for row in reader:
            old = row[col].strip()
            if drop_garbage and old in PARIS_GARBAGE_FLAGS:
                dropped += 1
                continue
            new = canonical(old)
            if old != new:
                row[col] = new
                changes += 1
            rows.append(row)

    if changes or dropped:
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    return changes, dropped


def fix_accident_csv(path: Path) -> tuple[int, int]:
    """Fix the Flag Administrations column in the accident CSV.

    Returns (changes, 0) — accident rows are never dropped, only normalised.
    """
    rows = []
    changes = 0
    col = "Flag Administrations"

    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        if fieldnames is None or col not in fieldnames:
            print(f"  [skip] {path.name}: column '{col}' not found")
            return 0, 0
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

    return changes, 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

FILES = [
    # (path,                                           column,           fixer,      drop_garbage)
    (DATA_DIR / "Num_of_ships_by_flag.csv",           "Economy_Label",  "simple",   False),
    (DATA_DIR / "paris_mou.csv",                       "flag",           "simple",   True),
    (DATA_DIR / "accident_data_20110101_20251231.csv", None,             "accident", False),
]


def main():
    total_changes = 0
    total_dropped = 0
    for path, col, fixer, drop_garbage in FILES:
        if not path.exists():
            print(f"  [missing] {path.relative_to(BASE_DIR)}")
            continue

        if fixer == "accident":
            n, d = fix_accident_csv(path)
        else:
            n, d = fix_simple_csv(path, col, drop_garbage=drop_garbage)

        msg = f"  {path.relative_to(BASE_DIR)}: {n} cell(s) updated"
        if d:
            msg += f", {d} garbage row(s) dropped"
        print(msg)
        total_changes += n
        total_dropped += d

    print(f"\nDone. {total_changes} cell(s) updated, {total_dropped} garbage row(s) dropped.")
    if total_changes or total_dropped:
        print("Backup files written as <original>.bak")


if __name__ == "__main__":
    main()

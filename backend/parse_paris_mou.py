"""
Parse all Paris MoU annual PDFs (2010-2024) into a single paris_mou.csv.

PDF formats handled:
  - Paris_MoU_YYYY.pdf (2010–2023): one combined file with Black/Grey/White lists.
  - "Paris MoU {Category} List 2024.pdf": three separate files for 2024.

Image-based PDFs (2017, 2018, 2022, 2023) fall back to pytesseract OCR.

Layout detection:
  - Multi-line (embedded text): each field on its own line; the excess factor
    appears on a standalone line matched by EXCESS_LINE_RE.
  - Single-line (OCR output): rank + flag + all numbers on one line; the
    excess factor is at the end, matched by EXCESS_END_RE.
"""

import csv
import io
import re
import sys
from pathlib import Path

import fitz
import pytesseract
from PIL import Image, ImageFilter

Image.MAX_IMAGE_PIXELS = None  # allow large scanned pages without memory error

DATA_DIR   = Path(__file__).resolve().parent / "data"
OUTPUT_CSV = DATA_DIR / "paris_mou.csv"

# Column headers written to the output CSV
CSV_FIELDS = [
    "year", "category", "rank", "flag",
    "inspections", "detentions",
    "black_to_grey_limit", "grey_to_white_limit",
    "excess_factor", "flag_safety_risk",
]

# Numeric safety risk score per Paris MoU category (used by the risk pipeline)
CATEGORY_SAFETY_SCORES = {"white": 0.0, "grey": 0.5, "black": 1.0}

# Excess factor on its own line: exactly 2 decimal digits (dot or comma separator).
# Unicode minus/hyphen variants are all accepted.
EXCESS_LINE_RE = re.compile(r"^\s*([-‐–−—]?\d+[.,]\d{2})\s*$")

# Excess factor at the END of a longer line (single-line / OCR layout).
# " is also matched as a minus (common OCR misread of −).
EXCESS_END_RE = re.compile(r'(["‐\-−]?\d+[.,]\d{2})\s*$')

# Risk-level adjectives embedded in the flag name column — strip before parsing
RISK_LABEL_RE = re.compile(
    r"\b(very\s+high\s+risk|high\s+risk|medium\s+to\s+high(\s+risk)?"
    r"|medium\s+risk|low\s+risk|high|medium)\b",
    re.IGNORECASE,
)

# Category section header (handles OCR spacing variations)
CATEGORY_HEADER_RE = re.compile(r"\b(black\s+list|grey\s+list|white\s+list)\b", re.IGNORECASE)

# "Recognized Organization" section header — pages with this header contain
# classification societies, NOT flag-state data; skip them entirely.
RECOGNIZED_ORG_RE = re.compile(r"\brecognized\s+organi[sz]ation", re.IGNORECASE)

# Column-header lines and table-header fragments to skip during entry parsing
SKIP_LINE_RE = re.compile(
    r"\b(INSPECTIONS|DETENTIONS|Classification|Bureau|Register|Veritas"
    r"|ANNUAL\s+REPORT|PORT\s+STATE|CONTROL|GETTING\s+BACK)\b",
    re.IGNORECASE,
)

# Plausible range for excess factor values (observed: approx −2.5 to +8)
EXCESS_FACTOR_MIN = -3.5
EXCESS_FACTOR_MAX = 12.0


# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------

def normalize_unicode(text: str) -> str:
    """Replace non-breaking spaces and Unicode dash variants with ASCII equivalents."""
    text = text.replace("\xa0", " ")
    for dash_char in "‐‑‒–—−":
        text = text.replace(dash_char, "-")
    return text


def fix_ocr_artifacts(line: str) -> str:
    """Correct common OCR misreads in a single line.

    Known issues:
      - Tesseract reads '−' (minus) as '"' before a digit.
      - Parenthesised single digits like (0) are formatting, not flags.
      - Trailing ')' after a digit is a stray brace from OCR.
    """
    line = re.sub(r'"(\d)', r'-\1', line)       # " before digit → minus
    line = re.sub(r'\((\d+)\)', r'\1', line)    # (0) → 0
    line = re.sub(r'(\d)\)', r'\1', line)       # 37) → 37
    return line


# ---------------------------------------------------------------------------
# PDF text extraction
# ---------------------------------------------------------------------------

def extract_page_text(page) -> str:
    """Extract text from a PDF page, falling back to OCR for image-based pages.

    A page is considered image-based when the embedded text is shorter than
    80 characters (typical for scanned PDFs with no selectable text layer).
    """
    text = page.get_text()
    if len(text.strip()) < 80:
        # Render at 200 DPI and sharpen before passing to Tesseract
        pixel_map = page.get_pixmap(dpi=200)
        image = Image.open(io.BytesIO(pixel_map.tobytes("png")))
        image = image.filter(ImageFilter.SHARPEN)
        text = pytesseract.image_to_string(image, config="--psm 6")
    return normalize_unicode(text)


# ---------------------------------------------------------------------------
# Category detection
# ---------------------------------------------------------------------------

def detect_category(page_text: str) -> str | None:
    """Return 'black', 'grey', or 'white' if a category header is found, else None."""
    match = CATEGORY_HEADER_RE.search(page_text)
    if not match:
        return None
    keyword = match.group(0).casefold().replace(" ", "")
    if keyword.startswith("black"):
        return "black"
    if keyword.startswith("grey"):
        return "grey"
    if keyword.startswith("white"):
        return "white"
    return None


# ---------------------------------------------------------------------------
# Number token parsing
# ---------------------------------------------------------------------------

def parse_number_token(token: str):
    """Classify a numeric string as integer or decimal.

    Returns:
        (int_value,   'int') for whole numbers and thousands-separated integers
        (float_value, 'dec') for values with 1–2 decimal places (excess factor)
        None                 if the token does not match either pattern
    """
    token = token.strip()
    if re.fullmatch(r"\d{1,3}(,\d{3})+", token):   # e.g. "1,234"
        return int(token.replace(",", "")), "int"
    if re.fullmatch(r"\d+", token):                  # e.g. "42"
        return int(token), "int"
    if re.fullmatch(r"-?\d+[.,]\d{1,2}", token):     # e.g. "-1.23" or "2,50"
        return float(token.replace(",", ".")), "dec"
    return None


# ---------------------------------------------------------------------------
# Entry assembly
# ---------------------------------------------------------------------------

def assemble_entry(
    integer_tokens: list[int],
    flag_text: str,
    excess_factor: float,
    category: str,
    has_rank_column: bool,
) -> dict | None:
    """Construct an entry dict from parsed components, or return None on failure.

    Args:
        integer_tokens:  All integer values found in the entry body.
        flag_text:       Raw text remaining after stripping all numbers.
        excess_factor:   Pre-parsed excess factor value.
        category:        'black', 'grey', or 'white'.
        has_rank_column: True for years >= 2012, which include a rank number.
    """
    # Clean up stray single-letter OCR artifacts from the flag name
    flag_name = re.sub(r"\s+", " ", flag_text).strip()
    flag_name = re.sub(r"(?<!\w)[a-zA-Z](?!\w)", " ", flag_name)
    flag_name = re.sub(r"\s+", " ", flag_name).strip()

    if not flag_name or not re.search(r"[A-Za-z]{2}", flag_name):
        return None

    # White/grey lists have 4 numeric columns; black list has 3 (no grey-to-white limit)
    expected_columns = 4 if category in ("white", "grey") else 3

    if has_rank_column:
        if len(integer_tokens) < expected_columns + 1:
            return None
        rank        = integer_tokens[0]
        data_tokens = integer_tokens[1:]
    else:
        if len(integer_tokens) < expected_columns:
            return None
        rank        = None
        data_tokens = integer_tokens[:]

    # Take the last `expected_columns` integers in case extra OCR digits appear early
    data_tokens = data_tokens[-expected_columns:]

    return {
        "rank":                rank,
        "flag":                flag_name,
        "inspections":         data_tokens[0],
        "detentions":          data_tokens[1],
        "black_to_grey_limit": data_tokens[2],
        "grey_to_white_limit": data_tokens[3] if expected_columns == 4 else None,
        "excess_factor":       excess_factor,
    }


def parse_multiline_entry(body_lines: list[str], raw_excess: str, category: str, has_rank_column: bool) -> dict | None:
    """Parse one entry from multi-line body text and a raw excess-factor string."""
    try:
        excess_factor = float(raw_excess.replace(",", ".").replace('"', "-"))
    except ValueError:
        return None
    if not (EXCESS_FACTOR_MIN <= excess_factor <= EXCESS_FACTOR_MAX):
        return None

    body = " ".join(body_lines)
    body = RISK_LABEL_RE.sub(" ", body)

    tokens         = re.findall(r"[\d,]+", body)
    integer_tokens = [
        val for t in tokens
        for val, kind in [parse_number_token(t) or (None, None)]
        if kind == "int"
    ]
    flag_text = re.sub(r"[\d,]+", " ", body)
    return assemble_entry(integer_tokens, flag_text, excess_factor, category, has_rank_column)


def parse_singleline_entry(line: str, category: str, has_rank_column: bool) -> dict | None:
    """Parse one entry where all fields are on a single line (OCR layout)."""
    match = EXCESS_END_RE.search(line)
    if not match:
        return None
    raw_excess = match.group(1)
    try:
        excess_factor = float(raw_excess.replace(",", ".").replace('"', "-"))
    except ValueError:
        return None
    if not (EXCESS_FACTOR_MIN <= excess_factor <= EXCESS_FACTOR_MAX):
        return None

    prefix = line[:match.start()]
    prefix = RISK_LABEL_RE.sub(" ", prefix)

    tokens         = re.findall(r"[\d,]+", prefix)
    integer_tokens = [
        val for t in tokens
        for val, kind in [parse_number_token(t) or (None, None)]
        if kind == "int"
    ]
    flag_text = re.sub(r"[\d,]+", " ", prefix)
    return assemble_entry(integer_tokens, flag_text, excess_factor, category, has_rank_column)


# ---------------------------------------------------------------------------
# Page-level parsing
# ---------------------------------------------------------------------------

def parse_page(page_text: str, category: str, year: int) -> list[dict]:
    """Extract all flag-state entries from one page's text.

    Auto-detects layout (multi-line vs single-line) by counting standalone
    excess-factor lines vs. lines that end with an excess factor.
    """
    raw_lines = page_text.splitlines()

    # Find the index of the first data line: the last category/column-header line
    # before the first excess-factor value.
    first_excess_idx = next(
        (
            i for i, ln in enumerate(raw_lines)
            if EXCESS_LINE_RE.match(ln.strip())
            or (EXCESS_END_RE.search(ln.strip()) and len(re.findall(r"[\d,]+", ln)) >= 3)
        ),
        len(raw_lines),
    )

    data_start_idx = 0
    for i in range(first_excess_idx):
        stripped = raw_lines[i].strip()
        if CATEGORY_HEADER_RE.search(stripped):
            data_start_idx = i + 1
        if re.search(r"\bFACTOR\b", stripped, re.I):
            data_start_idx = max(data_start_idx, i + 1)

    data_lines = [
        fix_ocr_artifacts(ln.strip())
        for ln in raw_lines[data_start_idx:]
        if ln.strip()
    ]

    has_rank_column = year >= 2012  # Rank column added starting in 2012

    # Layout detection: count standalone excess lines (multi-line) vs
    # end-of-line excess values with ≥3 numeric tokens (single-line)
    standalone_excess_count = sum(1 for ln in data_lines if EXCESS_LINE_RE.match(ln))
    endline_excess_count    = sum(
        1 for ln in data_lines
        if not EXCESS_LINE_RE.match(ln)
        and EXCESS_END_RE.search(ln)
        and len(re.findall(r"[\d,]+", ln)) >= 3
    )
    is_singleline_layout = (endline_excess_count > 0 and standalone_excess_count == 0)

    entries = []

    if is_singleline_layout:
        for line in data_lines:
            if SKIP_LINE_RE.search(line) or re.fullmatch(r"[A-Z]{2,6}", line):
                continue
            entry = parse_singleline_entry(line, category, has_rank_column)
            if entry:
                entries.append(entry)
    else:
        # Multi-line: accumulate body lines until a standalone excess-factor line terminates the entry
        current_body: list[str] = []
        for line in data_lines:
            if SKIP_LINE_RE.search(line) or re.fullmatch(r"[A-Z]{2,6}", line):
                continue
            excess_match = EXCESS_LINE_RE.match(line)
            if excess_match:
                entry = parse_multiline_entry(current_body, excess_match.group(1), category, has_rank_column)
                if entry:
                    entries.append(entry)
                current_body = []
            else:
                current_body.append(line)

    return entries


# ---------------------------------------------------------------------------
# Per-year PDF dispatch
# ---------------------------------------------------------------------------

def parse_annual_pdf(year: int) -> list[dict]:
    """Parse one combined annual Paris MoU PDF (2010–2023 format)."""
    pdf_path = DATA_DIR / f"Paris_MoU_{year}.pdf"
    if not pdf_path.exists():
        print(f"  SKIP: {pdf_path.name} not found", file=sys.stderr)
        return []

    doc = fitz.open(pdf_path)
    all_entries   = []
    last_category = None

    for page_idx in range(doc.page_count):
        text = extract_page_text(doc[page_idx])

        if RECOGNIZED_ORG_RE.search(text):
            print(f"  {year} p{page_idx+1}: skipping Recognized Organization page", file=sys.stderr)
            continue

        category = detect_category(text) or last_category
        if category is None:
            continue
        last_category = category

        entries = parse_page(text, category, year)
        for entry in entries:
            entry["year"]             = year
            entry["category"]         = category
            entry["flag_safety_risk"] = CATEGORY_SAFETY_SCORES[category]
        all_entries.extend(entries)
        print(f"  {year} p{page_idx+1} ({category}): {len(entries)} entries", file=sys.stderr)

    doc.close()
    return all_entries


def parse_2024_pdfs() -> list[dict]:
    """Parse the three separate 2024 Paris MoU PDFs (one per category)."""
    all_entries = []
    for category in ("white", "grey", "black"):
        filename = f"Paris MoU {category.capitalize()} List 2024.pdf"
        pdf_path = DATA_DIR / filename
        if not pdf_path.exists():
            print(f"  SKIP: {filename} not found", file=sys.stderr)
            continue

        doc = fitz.open(pdf_path)
        for page_idx in range(doc.page_count):
            text    = extract_page_text(doc[page_idx])
            entries = parse_page(text, category, 2024)
            for entry in entries:
                entry["year"]             = 2024
                entry["category"]         = category
                entry["flag_safety_risk"] = CATEGORY_SAFETY_SCORES[category]
            all_entries.extend(entries)
            print(f"  2024 {category} p{page_idx+1}: {len(entries)} entries", file=sys.stderr)
        doc.close()

    return all_entries


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    all_entries = []

    print("Parsing annual PDFs 2010-2023...", file=sys.stderr)
    for year in range(2010, 2024):
        all_entries.extend(parse_annual_pdf(year))

    print("Parsing 2024 separate PDFs...", file=sys.stderr)
    all_entries.extend(parse_2024_pdfs())

    print(f"\nTotal entries: {len(all_entries)}", file=sys.stderr)

    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_entries)

    print(f"Written to {OUTPUT_CSV}", file=sys.stderr)

    # Summary: entry counts by year and category
    print("\nEntries per year:", file=sys.stderr)
    by_year: dict = {}
    for entry in all_entries:
        by_year.setdefault(entry["year"], []).append(entry)
    for yr in sorted(by_year):
        category_counts: dict = {}
        for entry in by_year[yr]:
            category_counts[entry["category"]] = category_counts.get(entry["category"], 0) + 1
        print(f"  {yr}: {category_counts}", file=sys.stderr)


if __name__ == "__main__":
    main()

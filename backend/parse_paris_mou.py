"""
Parse all Paris MoU annual PDFs (2010-2024) into a single paris_mou.csv.

PDF types handled:
  - Paris_MoU_YYYY.pdf (2010-2023): annual combined list (Black/Grey/White)
  - "Paris MoU {Cat} List 2024.pdf": three separate files for 2024

Image-based PDFs (2017, 2018, 2022, 2023) use pytesseract OCR.

Layout formats encountered:
  - Multi-line (embedded text): each field on its own line, excess factor
    on a standalone line → detected by EXCESS_LINE_RE matching a whole line.
  - Single-line (OCR output): rank + flag + all numbers on one line,
    excess factor at end → detected by EXCESS_END_RE matching line-end.
"""

import csv
import io
import re
import sys
from pathlib import Path

import fitz
import pytesseract
from PIL import Image, ImageFilter

Image.MAX_IMAGE_PIXELS = None  # allow large scanned pages

DATA_DIR = Path(__file__).resolve().parent / "data"
OUTPUT_CSV = DATA_DIR / "paris_mou.csv"

FIELDS = [
    "year", "category", "rank", "flag",
    "inspections", "detentions",
    "black_to_grey_limit", "grey_to_white_limit",
    "excess_factor", "flag_safety_risk",
]

SAFETY_SCORES = {"white": 0.0, "grey": 0.5, "black": 1.0}

# Excess factor on its own line: exactly 2 decimal digits (dot or comma separator).
# Includes Unicode minus/hyphen variants.
EXCESS_LINE_RE = re.compile(r"^\s*([-‐–−—]?\d+[.,]\d{2})\s*$")

# Excess factor at END of a longer line (single-line / OCR format).
# Also allow " as minus (common OCR error for -).
EXCESS_END_RE = re.compile(r'(["‐\-−]?\d+[.,]\d{2})\s*$')

# Risk level keywords to strip
RISK_TEXT_RE = re.compile(
    r"\b(very\s+high\s+risk|high\s+risk|medium\s+to\s+high(\s+risk)?"
    r"|medium\s+risk|low\s+risk|high|medium)\b",
    re.IGNORECASE,
)

# Category headline (handles normalized text)
CAT_LINE_RE = re.compile(r"\b(black\s+list|grey\s+list|white\s+list)\b", re.IGNORECASE)

# Recognized Organization section header — pages with this header are NOT flag-state data
RECOG_ORG_RE = re.compile(r"\brecognized\s+organi[sz]ation", re.IGNORECASE)

# Column-header fragments to skip
SKIP_LINE_RE = re.compile(
    r"\b(INSPECTIONS|DETENTIONS|Classification|Bureau|Register|Veritas"
    r"|ANNUAL\s+REPORT|PORT\s+STATE|CONTROL|GETTING\s+BACK)\b",
    re.IGNORECASE,
)

# Reasonable excess-factor range (true values observed: approx -2.5 to +8)
EXCESS_MIN, EXCESS_MAX = -3.5, 12.0


# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    for ch in "‐‑‒–—−":
        text = text.replace(ch, "-")
    return text


def clean_ocr_line(line: str) -> str:
    """Fix common OCR artifacts in a single line."""
    # " before a digit at line-end → minus  (OCR reads - as ")
    line = re.sub(r'"(\d)', r'-\1', line)
    # Remove parentheses around single numbers: (0) → 0
    line = re.sub(r'\((\d+)\)', r'\1', line)
    # Remove stray trailing ): 37) → 37
    line = re.sub(r'(\d)\)', r'\1', line)
    return line


# ---------------------------------------------------------------------------
# PDF text extraction
# ---------------------------------------------------------------------------

def page_text(page) -> str:
    text = page.get_text()
    if len(text.strip()) < 80:
        pix = page.get_pixmap(dpi=200)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        img = img.filter(ImageFilter.SHARPEN)
        text = pytesseract.image_to_string(img, config="--psm 6")
    return normalize_text(text)


# ---------------------------------------------------------------------------
# Category detection
# ---------------------------------------------------------------------------

def detect_category(text: str):
    m = CAT_LINE_RE.search(text)
    if not m:
        return None
    kw = m.group(0).casefold().replace(" ", "")
    if kw.startswith("black"):
        return "black"
    if kw.startswith("grey"):
        return "grey"
    if kw.startswith("white"):
        return "white"
    return None


# ---------------------------------------------------------------------------
# Number token parsing
# ---------------------------------------------------------------------------

def parse_number_token(s: str):
    """
    Return (value, 'int') or (value, 'dec') or None.
    3 digits after comma → thousands separator (int).
    1-2 digits after dot/comma → decimal (excess factor).
    """
    s = s.strip()
    if re.fullmatch(r"\d{1,3}(,\d{3})+", s):
        return int(s.replace(",", "")), "int"
    if re.fullmatch(r"\d+", s):
        return int(s), "int"
    if re.fullmatch(r"-?\d+[.,]\d{1,2}", s):
        return float(s.replace(",", ".")), "dec"
    return None


# ---------------------------------------------------------------------------
# Entry assembly
# ---------------------------------------------------------------------------

def assemble_entry(integers: list, text_only: str,
                   excess_factor: float, category: str, has_rank: bool):
    """
    Given a list of integers (from the entry body), the text-only flag
    area, and the excess factor, assemble an entry dict or return None.
    """
    flag = re.sub(r"\s+", " ", text_only).strip()

    # Drop lone single-letter tokens (OCR artifact like stray 'a')
    flag = re.sub(r"(?<!\w)[a-zA-Z](?!\w)", " ", flag)
    flag = re.sub(r"\s+", " ", flag).strip()

    if not flag or not re.search(r"[A-Za-z]{2}", flag):
        return None

    expected = 4 if category in ("white", "grey") else 3

    if has_rank:
        if len(integers) < expected + 1:
            return None
        rank = integers[0]
        nums = integers[1:]
    else:
        if len(integers) < expected:
            return None
        rank = None
        nums = integers[:]

    nums = nums[-expected:]

    return {
        "rank":                rank,
        "flag":                flag,
        "inspections":         nums[0],
        "detentions":          nums[1],
        "black_to_grey_limit": nums[2],
        "grey_to_white_limit": nums[3] if expected == 4 else None,
        "excess_factor":       excess_factor,
    }


def parse_entry_from_body(body_lines: list, excess_str: str,
                          category: str, has_rank: bool):
    """Parse an entry from multi-line body + raw excess-factor string."""
    try:
        excess_factor = float(excess_str.replace(",", ".").replace('"', "-"))
    except ValueError:
        return None
    if not (EXCESS_MIN <= excess_factor <= EXCESS_MAX):
        return None

    body = " ".join(body_lines)
    body = RISK_TEXT_RE.sub(" ", body)

    tokens = re.findall(r"[\d,]+", body)
    integers = [v for t in tokens
                for v, kind in [parse_number_token(t) or (None, None)]
                if kind == "int"]

    text_only = re.sub(r"[\d,]+", " ", body)
    return assemble_entry(integers, text_only, excess_factor, category, has_rank)


def parse_single_line_entry(line: str, category: str, has_rank: bool):
    """Parse an entry where all fields are on a single line (OCR format)."""
    m = EXCESS_END_RE.search(line)
    if not m:
        return None
    excess_str = m.group(1)
    try:
        excess_factor = float(excess_str.replace(",", ".").replace('"', "-"))
    except ValueError:
        return None
    if not (EXCESS_MIN <= excess_factor <= EXCESS_MAX):
        return None

    pre = line[:m.start()]
    pre = RISK_TEXT_RE.sub(" ", pre)

    tokens = re.findall(r"[\d,]+", pre)
    integers = [v for t in tokens
                for v, kind in [parse_number_token(t) or (None, None)]
                if kind == "int"]

    text_only = re.sub(r"[\d,]+", " ", pre)
    return assemble_entry(integers, text_only, excess_factor, category, has_rank)


# ---------------------------------------------------------------------------
# Page-level parsing
# ---------------------------------------------------------------------------

def parse_page(text: str, category: str, year: int):
    lines_raw = text.splitlines()

    # Find start of data: last header keyword BEFORE the first excess-factor line
    first_excess_idx = next(
        (i for i, ln in enumerate(lines_raw) if EXCESS_LINE_RE.match(ln.strip())
         or (EXCESS_END_RE.search(ln.strip())
             and len(re.findall(r"[\d,]+", ln)) >= 3)),
        len(lines_raw),
    )

    start_idx = 0
    for i in range(first_excess_idx):
        stripped = lines_raw[i].strip()
        if CAT_LINE_RE.search(stripped):
            start_idx = i + 1
        if re.search(r"\bFACTOR\b", stripped, re.I):
            start_idx = max(start_idx, i + 1)

    data_lines = [clean_ocr_line(ln.strip()) for ln in lines_raw[start_idx:] if ln.strip()]

    has_rank = year >= 2012

    # Detect layout: multi-line (pure excess-factor lines exist) vs
    # single-line (each full entry is one line, no standalone excess factors)
    n_pure   = sum(1 for l in data_lines if EXCESS_LINE_RE.match(l))
    n_end    = sum(1 for l in data_lines
                   if not EXCESS_LINE_RE.match(l)
                   and EXCESS_END_RE.search(l)
                   and len(re.findall(r"[\d,]+", l)) >= 3)
    single_line_mode = (n_end > 0 and n_pure == 0)

    entries = []

    if single_line_mode:
        for line in data_lines:
            if SKIP_LINE_RE.search(line) or re.fullmatch(r"[A-Z]{2,6}", line):
                continue
            entry = parse_single_line_entry(line, category, has_rank)
            if entry:
                entries.append(entry)
    else:
        current: list = []
        for line in data_lines:
            if SKIP_LINE_RE.search(line) or re.fullmatch(r"[A-Z]{2,6}", line):
                continue
            m = EXCESS_LINE_RE.match(line)
            if m:
                entry = parse_entry_from_body(current, m.group(1), category, has_rank)
                if entry:
                    entries.append(entry)
                current = []
            else:
                current.append(line)

    return entries


# ---------------------------------------------------------------------------
# Per-year PDF handling
# ---------------------------------------------------------------------------

def parse_annual_pdf(year: int):
    path = DATA_DIR / f"Paris_MoU_{year}.pdf"
    if not path.exists():
        print(f"  SKIP: {path.name} not found", file=sys.stderr)
        return []

    doc = fitz.open(path)
    all_entries = []
    last_category = None

    for page_num in range(doc.page_count):
        text = page_text(doc[page_num])
        if RECOG_ORG_RE.search(text):
            print(f"  {year} p{page_num+1}: skipping Recognized Organization page", file=sys.stderr)
            continue
        category = detect_category(text) or last_category
        if category is None:
            continue
        last_category = category

        entries = parse_page(text, category, year)
        for e in entries:
            e["year"] = year
            e["category"] = category
            e["flag_safety_risk"] = SAFETY_SCORES[category]
        all_entries.extend(entries)
        print(f"  {year} p{page_num+1} ({category}): {len(entries)} entries", file=sys.stderr)

    doc.close()
    return all_entries


def parse_2024_pdfs():
    all_entries = []
    for category in ("white", "grey", "black"):
        fname = f"Paris MoU {category.capitalize()} List 2024.pdf"
        path = DATA_DIR / fname
        if not path.exists():
            print(f"  SKIP: {fname} not found", file=sys.stderr)
            continue

        doc = fitz.open(path)
        for page_num in range(doc.page_count):
            text = page_text(doc[page_num])
            entries = parse_page(text, category, 2024)
            for e in entries:
                e["year"] = 2024
                e["category"] = category
                e["flag_safety_risk"] = SAFETY_SCORES[category]
            all_entries.extend(entries)
            print(f"  2024 {category} p{page_num+1}: {len(entries)} entries", file=sys.stderr)
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
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_entries)

    print(f"Written to {OUTPUT_CSV}", file=sys.stderr)

    print("\nEntries per year:", file=sys.stderr)
    by_year: dict = {}
    for e in all_entries:
        by_year.setdefault(e["year"], []).append(e)
    for yr in sorted(by_year):
        cats: dict = {}
        for e in by_year[yr]:
            cats[e["category"]] = cats.get(e["category"], 0) + 1
        print(f"  {yr}: {cats}", file=sys.stderr)


if __name__ == "__main__":
    main()

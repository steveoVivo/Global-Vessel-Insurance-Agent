# Backend

Python/Flask API that computes flag-state vessel risk scores from IMO accident
records, Paris MoU Port State Control data, and UNCTAD fleet statistics.

---

## Setup

### System dependencies

`parse_paris_mou.py` uses [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)
to extract text from image-based Paris MoU PDFs (2017, 2018, 2022, 2023).
Tesseract is a system binary — `pip install pytesseract` alone is not enough.

```bash
# Ubuntu / Debian
sudo apt install tesseract-ocr

# macOS (Homebrew)
brew install tesseract
```

Verify the installation:

```bash
tesseract --version
```

> **Note:** If you skip this step, `parse_paris_mou.py` will raise
> `TesseractNotFoundError` when it encounters an image-based PDF page.
> Text-embedded PDF pages (most years) are unaffected and will parse normally.

### Python dependencies

From the `backend/` directory:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

---

## Data Preparation

Run the following steps once from the `backend/` directory before starting the
API server.

### 0. Download source data

Download the `data/` directory from Box and place it inside `backend/`:

[https://ucdavis.box.com/s/nhxb0eb2jmloiw4ltdfzbw9b600o9n48](https://ucdavis.box.com/s/nhxb0eb2jmloiw4ltdfzbw9b600o9n48)

The archive contains:
- `accident_data_20110101_20251231.csv`
- `Num_of_ships_by_flag.csv`
- `country_name.md`
- Paris MoU PDF reports (2010–2024)

### 1. Parse Paris MoU PDFs (run once, or when rebuilding paris_mou.csv)
```bash
.venv/bin/python parse_paris_mou.py
```

### 2. Normalize country names (run once, after step 1)

Normalizes all country/flag names across every source dataset to the canonical
standard used by the frontend map library:

```bash
.venv/bin/python fix_country_names.py
```

Files modified in place (originals backed up as `<file>.bak`):

| File | Column |
| --- | --- |
| `data/Num_of_ships_by_flag.csv` | `Economy_Label` |
| `data/paris_mou.csv` | `flag` |
| `data/accident_data_20110101_20251231.csv` | `Flag Administrations` |

### 3. Run the API server

```bash
.venv/bin/python app.py
```

> **macOS note:** AirPlay Receiver uses port 5000 by default. Run on port 5001
> instead to avoid conflicts:
> ```bash
> .venv/bin/python app.py --port 5001
> ```

Base URL: `http://127.0.0.1:5000` (or `http://127.0.0.1:5001` on macOS)

---

## API Reference

### `GET /api/data`

Returns per-flag vessel risk data sorted by `risk_score` descending.

The default risk score is an equal-weighted combination of four components
selected by a temporal holdout evaluation (train 2011-2020, test 2021-2025,
top-30 fleets by 2025 size). See `results/evaluation_results_06051335.txt` for
the full evaluation output.

#### Query Parameters

| Parameter | Alias | Description | Default |
| --- | --- | --- | --- |
| `start_year` | | Include accidents from this year onward | all years |
| `end_year` | | Include accidents through this year | all years |
| `event_entropy_weight` | `w1` | Weight for `event_entropy_norm` | `0.25` |
| `ship_type_weight` | `w2` | Weight for `ship_type_risk_norm` | `0.25` |
| `open_sea_weight` | `w3` | Weight for `open_sea_rate_norm` | `0.25` |
| `fleet_volatility_weight` | `w4` | Weight for `fleet_volatility_norm` | `0.25` |

Weights are normalized by their sum, so relative ratios matter rather than
absolute values. Missing weight parameters fall back to the defaults above.

#### Example Request

```
GET /api/data?start_year=2015&end_year=2024&w1=0.4&w2=0.3&w3=0.2&w4=0.1
```

#### Response Schema

```json
{
  "count": 223,
  "data": [
    {
      "flag": "Togo",
      "country_code": "TG",
      "coordinates": [1.2232, 8.6195],
      "vessel_count": 512,
      "risk_score": 0.6821,
      "event_entropy_norm": 0.7104,
      "ship_type_risk_norm": 0.6832,
      "open_sea_rate_norm": 0.5940,
      "fleet_volatility_norm": 0.7410
    }
  ]
}
```

#### Response Fields

| Field | Type | Description |
| --- | --- | --- |
| `flag` | string | Flag-state display name |
| `country_code` | string | ISO 3166-1 alpha-2 country code |
| `coordinates` | [float, float] | [longitude, latitude] centroid |
| `vessel_count` | integer | Number of registered vessels (2025 fleet snapshot) |
| `risk_score` | float [0-1] | Weighted composite risk score; higher = riskier |
| `event_entropy_norm` | float [0-1] | Normalized Shannon entropy of casualty event categories. High entropy signals diverse, systemic risk. |
| `ship_type_risk_norm` | float [0-1] | Normalized accident-proneness of vessel types involved in accidents under this flag. |
| `open_sea_rate_norm` | float [0-1] | Normalized share of accidents occurring in open-sea locations. |
| `fleet_volatility_norm` | float [0-1] | Normalized RMSE of annual fleet size changes relative to mean fleet size. |

---

### `GET /api/trend`

Returns per-flag accident rate time series at yearly and monthly resolution,
plus a short-term forecast using Holt's linear trend model.

#### Response Schema

```json
{
  "count": 223,
  "data": [
    {
      "flag": "Panama",
      "flag_key": "panama",
      "yearly": [
        { "year": 2011, "accident_rate": 0.00412, "accident_count": 18, "exposure": 4369.5, "has_fleet_data": true }
      ],
      "monthly": [
        { "date": "2011-01", "year": 2011, "month": 1, "accident_rate": 0.00038, "accident_count": 2, "exposure": 364.1, "has_fleet_data": true }
      ],
      "predicted_yearly": [
        { "year": 2026, "accident_rate": 0.00390 }
      ]
    }
  ]
}
```

`predicted_yearly` contains up to 3 forecast points (Holt linear trend). It is
empty if fewer than 5 valid fleet-data years are available for the flag.

---

### `GET /api/accidents`

Returns individual accident records for a specific flag state.

#### Query Parameters

| Parameter | Required | Description |
| --- | --- | --- |
| `country` | Yes | Flag-state name (matched after normalization) |

#### Example Request

```
GET /api/accidents?country=Panama
```

#### Response Schema

```json
{
  "country": "Panama",
  "count": 312,
  "data": [
    {
      "reference": "...",
      "num_ships": "1",
      "ships": "...",
      "solas_status": "...",
      "flags": "Panama",
      "ship_types": "General cargo ship",
      "date": "2024-11-03T00:00:00",
      "event": "Flooding - ...",
      "severity": "Marine casualty",
      "geo_coordinates": "...",
      "place": "...",
      "location": "Open sea",
      "num_reports": "1",
      "reporting_admins": "..."
    }
  ]
}
```

Results are sorted by date, most recent first.

---

## Risk Score Methodology

### Components

| Component | Key | Source |
| --- | --- | --- |
| Event entropy | `event_entropy` | Shannon entropy of casualty event categories (IMO GISIS) |
| Ship type risk | `ship_type` | Log-frequency-weighted accident-proneness of vessel types (IMO GISIS) |
| Open sea rate | `open_sea` | Share of accidents in open-sea locations (IMO GISIS) |
| Fleet volatility | `fleet_volatility` | RMSE of annual fleet size changes / mean fleet size (UNCTAD) |

Additional components are computed but assigned zero weight in the default model.
They can be activated via query parameters:

| Component | Key |
| --- | --- |
| Accident rate | `accident_rate` |
| OLS trend slope of accident rate | `trend` |
| Investigation report rate | `investigation` |
| Paris MoU detention rate | `flag_safety` |
| Average casualty severity | `severity` |
| Multi-ship accident rate | `multi_ship` |
| Collision rate | `collision` |
| SOLAS non-compliance rate | `solas_noncompliance` |
| Paris MoU excess factor | `excess_factor` |
| Trend of Paris MoU excess factor | `excess_factor_trend` |
| Fleet growth rate | `fleet_growth` |

### Normalization

All components are min-max normalized against the 95th percentile of non-zero
values so that extreme outliers do not compress the rest of the scale. Trend
components (OLS slope, excess factor trend) clip negative values to zero before
normalization: improving flags score 0, not negative.

### Fleet Exposure

Accident rates use monthly-interpolated fleet exposure rather than annual
snapshots:

```
fleet_at(Y, m) = fleet[Y] + (fleet[Y+1] - fleet[Y]) / 12 * (m - 1)
exposure_Y     = sum(fleet_at(Y, m) for m in 1..12) / 12   (ship-years)
```

### Evaluation

Predictive validity is assessed with a temporal holdout:

- **Train**: risk score computed from 2011-2020 data
- **Test**: actual exposure-weighted accident rate measured over 2021-2025
- **Cohort**: top 30 flag states by 2025 fleet size
- **Metric**: Spearman rank correlation between train risk ranking and test accident rate ranking

Run `evaluate_risk_score.py` to reproduce the evaluation and save results to
`results/`.

### Trend Forecasting

`temporal_trend_prediction.py` implements Holt's linear trend model
(`statsmodels.tsa.holtwinters.Holt`) with walk-forward (expanding window)
validation. A minimum of 5 valid yearly data points is required to produce a
forecast. The forecast horizon is 3 years.

---

## Project Structure

```
backend/
├── app.py                      Flask API server
├── data_pipeline.py            Data loading, normalization, and risk score assembly
├── evaluate_risk_score.py      Temporal holdout evaluation (Spearman correlation)
├── temporal_trend_prediction.py  Holt trend model and walk-forward validation
├── fix_country_names.py        One-time script to canonicalize country names in all CSVs
├── parse_paris_mou.py          PDF parser for Paris MoU annual reports
├── country_lookup.py           Country code and coordinate lookup helpers
├── requirements.txt
├── data/
│   ├── accident_data_20110101_20251231.csv   IMO GISIS accident records
│   ├── Num_of_ships_by_flag.csv              UNCTAD fleet statistics
│   ├── paris_mou.csv                         Parsed Paris MoU inspection data (2010-2024)
│   ├── Paris MoU {Black,Grey,White} List 2024.pdf
│   ├── Paris_MoU_20{10..23}.pdf
│   └── country_name.md                       Canonical country name reference
└── results/
    └── evaluation_results_*.txt              Holdout evaluation outputs
```

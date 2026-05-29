# Backend

Python/Flask API that computes flag-state vessel risk scores from IMO accident
records, Paris MoU Port State Control data, and UNCTAD fleet statistics.

---

## Setup

From the project root:

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
```

---

## Data Preparation

### 1. Fix country names (run once)

Normalizes all country/flag names across every dataset to the Google Canonical
Country standard used by the frontend map library:

```bash
.venv/bin/python backend/fix_country_names.py
```

Files modified in place (originals backed up as `<file>.bak`):

| File | Column fixed |
| --- | --- |
| `data/archive/Num_of_Ships_2011_2025.csv` | `Economy_Label` |
| `data/paris_mou.csv` | `flag` |
| `data/accident_data_20110101_20251231.csv` | `Flag Administrations` |
| `data/merged_vessel_risk_by_flag.csv` | `flag` |
| `data/accident_risk_by_flag.csv` | `flag` |

### 2. Run the API server

```bash
.venv/bin/python backend/app.py
```

Base URL: `http://127.0.0.1:5000`

---

## API Reference

### `GET /api/data`

Returns flag-state vessel risk data, sorted by `risk_score` descending.

The risk score is a weighted sum of five normalized risk components, each
individually validated to have a Spearman rank correlation ≥ 0.4 against
out-of-sample accident rates (train 2011–2020, test 2021–2025, top-30 fleets).
See `results/evaluation_results_05282248.txt` for the full evaluation.

#### Query Parameters

| Parameter | Alias | Description | Default |
| --- | --- | --- | --- |
| `start_year` | | Include data from this year onward | all years |
| `end_year` | | Include data through this year | all years |
| `accident_rate_weight` | `w1` | Weight for `accident_rate_norm` | `0.40` |
| `event_entropy_weight` | `w2` | Weight for `event_entropy_norm` | `0.25` |
| `trend_weight` | `w3` | Weight for `trend_slope_norm` | `0.20` |
| `investigation_weight` | `w4` | Weight for `investigation_rate_norm` | `0.15` |
| `flag_safety_weight` | `w5` | Weight for `flag_safety_risk_norm` | `0.00` |

Weights are normalized by their sum, so relative ratios matter, not absolute
values. Missing weight parameters fall back to the defaults above.

#### Example Request

```
GET /api/data?start_year=2015&end_year=2024&w1=0.4&w2=0.2&w3=0.2&w4=0.1&w5=0.1
```

#### Response Schema

```json
{
  "count": 223,
  "data": [
    {
      "flag": "Portugal",
      "vessel_count": 512,
      "risk_score": 0.4502,
      "accident_rate_norm": 0.8731,
      "event_entropy_norm": 0.6214,
      "trend_slope_norm": 0.3905,
      "investigation_rate_norm": 0.9102,
      "flag_safety_risk_norm": 0.1540
    }
  ]
}
```

#### Response Fields

| Field | Type | Description |
| --- | --- | --- |
| `flag` | string | Country/flag-state name (Google Canonical Country standard) |
| `vessel_count` | integer | Number of registered vessels (2025 fleet snapshot) |
| `risk_score` | float [0–1] | Weighted composite risk score; higher = riskier |
| `accident_rate_norm` | float [0–1] | Normalized exposure-weighted accident rate (accidents per ship-year). Capped at 95th-percentile to reduce outlier distortion. |
| `event_entropy_norm` | float [0–1] | Normalized Shannon entropy of accident-cause categories. High entropy indicates diverse, systemic risk; low entropy indicates a single dominant cause type. |
| `trend_slope_norm` | float [0–1] | Normalized OLS slope of the yearly accident rate. Positive values mean the rate is worsening over time; zero-clipped so improving flags score 0. |
| `investigation_rate_norm` | float [0–1] | Normalized mean number of investigation reports filed per accident. Empirically correlates positively with future accident rates (r ≈ +0.44), so higher values indicate higher risk. |
| `flag_safety_risk_norm` | float [0–1] | Normalized Paris MoU detention rate (detentions ÷ inspections). Higher values indicate poorer port-state control compliance. |

---

### `GET /api/trend`

Returns per-flag accident rate time series at yearly and monthly resolution,
using monthly-interpolated fleet exposure. Intended for the trend chart panel.

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
      ]
    }
  ]
}
```

---

## Risk Score Methodology

### Component descriptions

| Component | Key | Source data |
| --- | --- | --- |
| Accident rate | `accident_rate` | IMO GISIS accident database (2011–2025) + UNCTAD fleet data |
| Event entropy | `event_entropy` | Shannon entropy of casualty event categories per flag |
| Trend | `trend` | OLS slope of annual exposure-weighted accident rate |
| Investigation rate | `investigation` | Mean investigation reports per accident (IMO GISIS) |
| Flag safety | `flag_safety` | Paris MoU Port State Control detention rate |

### Normalization

All components are min-max normalized, capped at the 95th percentile of
non-zero values, so that extreme outliers do not compress the rest of the scale.
Trend-like variables (trend slope, excess factor) have their negative values
clipped to zero before normalization — improving flags score 0, not negative.

### Evaluation

Predictive validity is assessed with a temporal holdout design:

- **Train**: risk score computed from 2011–2020 data  
- **Test**: actual exposure-weighted accident rate measured over 2021–2025  
- **Cohort**: top 30 flag states by 2025 fleet size  
- **Metric**: Spearman rank correlation between train risk ranking and test accident rate ranking

Current result (equal-weight baseline, `results/evaluation_results_05282248.txt`):

```
Spearman r = 0.545   p = 0.0018   (GOOD — r ≥ 0.5)
```

---

## Project Structure

```
backend/
├── app.py                  Flask API server
├── data_pipeline.py        Data loading, normalization, and risk score assembly
├── evaluate_risk_score.py  Temporal holdout evaluation (Spearman correlation)
├── fix_country_names.py    One-time script to canonicalize country names in all CSVs
├── parse_paris_mou.py      PDF parser for Paris MoU annual reports
├── requirements.txt
├── data/
│   ├── accident_data_20110101_20251231.csv   IMO GISIS accident records
│   ├── paris_mou.csv                         Parsed Paris MoU inspection data
│   ├── archive/
│   │   └── Num_of_Ships_2011_2025.csv        UNCTAD fleet statistics
│   └── country_name.md                       Google Canonical Country reference
└── results/
    └── evaluation_results_*.txt              Holdout evaluation outputs
```

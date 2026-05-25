# Backend

## Setup

From the project root:

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
```

## Build Data

```bash
.venv/bin/python backend/data_pipeline.py
```

## Run API

```bash
.venv/bin/python backend/app.py
```

API URL:

```text
http://127.0.0.1:5000
```

Useful endpoints:

```text
/api/data
```

`/api/data` returns country/flag-level vessel risk data sorted by `risk_score`
descending. The risk score is calculated from the normalized risk factors using
the configured weights.

Optional query parameters:

| Parameter | Alias | Description | Default |
| --- | --- | --- | --- |
| `start_year` | | Include accidents from this year onward | all years |
| `end_year` | | Include accidents through this year | all years |
| `accident_rate_weight` | `w1` | Weight for `accident_rate_norm` | `0.25` |
| `severity_weight` | `w2` | Weight for `severity_risk_norm` | `0.25` |
| `ship_type_weight` | `w3` | Weight for `ship_type_risk_norm` | `0.25` |
| `flag_safety_weight` | `w4` | Weight for `flag_safety_risk_norm` | `0.25` |

Example:

```text
/api/data?start_year=2024&end_year=2025&w1=0.4&w2=0.3&w3=0.2&w4=0.1
```

Response:

```json
{
  "count": 223,
  "data": [
    {
      "flag": "Cameroon",
      "vessel_count": 240,
      "risk_score": 0.684643817204301,
      "accident_rate_norm": 0.0125,
      "severity_risk_norm": 0.8833333333333333,
      "ship_type_risk_norm": 0.842741935483871,
      "flag_safety_risk_norm": 1.0
    }
  ]
}
```

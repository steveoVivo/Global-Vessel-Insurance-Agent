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

Both endpoints return:

```json
{
  "count": 223,
  "data": [
    {
      "country": "Cameroon",
      "vessel_count": 240,
      "risk_score": 0.684643817204301
    }
  ]
}
```

# Global-Vessel-Insurance-Agent

## Description
This repository contains the final project for Team 10 at UC Davis' Spring 2026 ECS 273 Course.

This project provides an estimate of the riskiness to insure a vessel flying the flag of any country. This visualized as a proportional symbol map using OpenLayers. The "risk level" is scored between 0 and 100, and considers 4 subfactors. It is possible to view and modify these subfactors on the project frontend - as well as view detailed data about a ship's riskiness.

![Recording of project](./public/Recording.gif)



## (Installation) First-Time Setup
The development build of this project has a completely seperate frontend (React x Vite) and backend (Flask). These each have to be setup and installed on their own.

### Setting Up Frontend

1. Install [NodeJS](https://nodejs.org/en)

2. cd `frontend`

3. Run `npm install`

### Setting Up the Backend

Flask is a Python program that requires Python to run. Create a local virtual
environment in the backend directory and install the backend dependencies there.

The backend assumes Python 3.12.

1. cd `backend`

2. **Install Tesseract OCR** — required by `parse_paris_mou.py` to read
   image-based PDF pages (2017, 2018, 2022, 2023 reports).
   This is a system binary and cannot be installed via `pip`.

   ```bash
   # Ubuntu / Debian
   sudo apt install tesseract-ocr

   # macOS (Homebrew)
   brew install tesseract
   ```

   Verify: `tesseract --version`

   > If Tesseract is missing, `parse_paris_mou.py` will raise
   > `TesseractNotFoundError` on image-based PDF pages.

3. Create a virtual environment: `python3 -m venv .venv`

4. Install the backend packages: `.venv/bin/pip install -r requirements.txt`

5. Run backend commands with `.venv/bin/python` or activate the environment with `source .venv/bin/activate`

#### One-time data preparation (run in order)

These steps are required before starting the API server for the first time.

1. **Download source data** — download the `data/` folder from Box and place it
   inside `backend/`:
   [https://ucdavis.box.com/s/nhxb0eb2jmloiw4ltdfzbw9b600o9n48](https://ucdavis.box.com/s/nhxb0eb2jmloiw4ltdfzbw9b600o9n48)

2. **Parse Paris MoU PDFs** — generates `data/paris_mou.csv`:
   ```bash
   .venv/bin/python parse_paris_mou.py
   ```

3. **Normalize country names** — canonicalizes flag names in all source CSVs:
   ```bash
   .venv/bin/python fix_country_names.py
   ```

See `backend/README.md` for full API documentation and methodology details.

## (Execution) Running the Project
As the frontend and backend are served seperately, you'll need to use two different terminals to ensure the project works. After both of these steps are taken, the website will work at `http://localhost:5173/`
Once the project makes it out of development into a production release, we'll be able to compile the React code into
pure HTML, but until then both servers are required.

### Spin Up the Frontend

1. cd `frontend`

2. `npm run dev`

### Spun Up the Backend

1. cd `backend`

2. `.venv/bin/python app.py`

```bash
**macOS note:** AirPlay Receiver uses port 5000 by default. Run on port 5001 instead
.venv/bin/python app.py --port 5001
```

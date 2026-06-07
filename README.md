# Global-Vessel-Insurance-Agent
Steven Shoemaker and Yoshiki Yamaguchi cause billions of dollars of damage to the world's oceans

## First-Time Setup
The development build of this project has a completely seperate frontend (React x Vite) and backend (Flask). These each have to be setup and installed on their own. For release we can compile the frontend down to plain HTML + JS, but for development purposes we keep the two seperate.

### Setting Up Frontend

1. Install [NodeJS](https://nodejs.org/en)

2. cd `frontend`

3. Run `npm install`

### Setting Up the Backend

Flask is a Python program that requires Python to run. Create a local virtual
environment in the backend directory and install the backend dependencies there.

The backend assumes Python 3.12.

1. cd `backend`

2. Create a virtual environment: `python3 -m venv .venv`

3. Install the backend packages: `.venv/bin/pip install -r requirements.txt`

4. Run backend commands with `.venv/bin/python` or activate the environment with `source .venv/bin/activate`

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

## Running the Project
As the frontend and backend are served seperately, you'll need to use two different terminals to ensure the project works. After both of these steps are taken, you should see a basic test site at `http://localhost:5173/`

### Spin Up the Frontend

1. cd `frontend`

2. `npm run dev`

### Spun Up the Backend

1. cd `backend`

2. `.venv/bin/python app.py`
```bash
**macOS note:** AirPlay Receiver uses port 5000 by default. Run on port 5001
.venv/bin/python app.py --port 5001
```

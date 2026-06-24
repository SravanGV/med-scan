# med-scan

MedScan AI MVP implementation using Flask + SQLite.

## Features

- Login with role-based users (`admin`, `doctor`, `technician`)
- Patient registration and search
- Image upload + mock analysis (X-ray/MRI/CT)
- Patient records/history table
- Dashboard cards (total patients, analyses, this week) + recent activity
- CSV report export

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Open `http://127.0.0.1:5000`.

Demo credentials:

- `admin / admin123`
- `doctor / doctor123`
- `tech / tech123`

## Tests

```bash
python -m unittest discover -s tests
```

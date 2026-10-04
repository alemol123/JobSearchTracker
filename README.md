# Job Search Tracker

A personal web app for tracking job applications through a hiring pipeline and finding which skills to improve based on the jobs applied to.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open http://localhost:8000.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8000` | Port the server listens on (always binds `0.0.0.0`) |
| `DATA_DIR` | `./data` | Folder where the SQLite database file is stored |
| `STALE_DAYS` | `14` | Days without stage movement before an application is flagged stale |
| `SECRET_KEY` | `dev-only-change-me` | Signs the session cookie used for flash messages; set a random value outside local use |

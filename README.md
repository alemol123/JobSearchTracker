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

The SQLite database is stored at `$DATA_DIR/jobtracker.db` (by default `./data/jobtracker.db`). The folder and all tables are created automatically on startup, so there is no setup or migration step, and restarting keeps existing data.

## Running the tests

With the virtual environment active:

```bash
pytest --cov=pipeline --cov=skills --cov-report=term-missing
```

Result (2026-10-07, 135 tests):

```
Name                     Stmts   Miss  Cover   Missing
------------------------------------------------------
pipeline/__init__.py         0      0   100%
pipeline/logic.py           80      0   100%
pipeline/repository.py      42      0   100%
pipeline/routes.py          49      0   100%
skills/__init__.py           0      0   100%
skills/logic.py             41      0   100%
skills/repository.py        52      0   100%
skills/routes.py            75      0   100%
------------------------------------------------------
TOTAL                      339      0   100%
135 passed
```

What the tests cover:

| Test file | What it checks |
|---|---|
| `tests/test_pipeline_logic.py` | Stage transition rules, days in stage, stale flag, conversion rates, form parsing |
| `tests/test_skills_logic.py` | Demand counts, missing skills, demand ranking, priority score, form parsing |
| `tests/test_pipeline_repo.py`, `tests/test_skills_repo.py` | SQL against a real temporary SQLite database (pytest `tmp_path`), including soft delete |
| `tests/test_pipeline_routes.py`, `tests/test_skills_routes.py` | A few end-to-end checks of each page through Flask's test client |
| `tests/test_app_config.py` | Deployment contract: `PORT`, `DATA_DIR` and `STALE_DAYS` come from environment variables, and the database file is created at `$DATA_DIR/jobtracker.db` |

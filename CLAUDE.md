# JobSearchTracker — Assignment 2

The assignment brief is `notes/assignment_2.md` and the day-by-day plan is `notes/a2-guide.md`. Read both before starting work. Assignment 1 rules no longer apply.

## What we are building
Split the Assignment 1 Flask monolith into two services along the ADR-2 seam:
- `services/pipeline/` owns the tables `applications` and `stage_history`. It never calls skills.
- `services/skills/` owns `skills`, `my_skills` and `application_skills`. `application_id` is a plain INT with no foreign key.
- Skills calls pipeline over HTTP (`PIPELINE_URL`, with a timeout from `PIPELINE_TIMEOUT_S`):
  - `GET /applications/active-ids` is used by `/skills/gap`. If pipeline is unavailable, return 200 with `pipeline_available: false` and a notice.
  - `GET /applications/{id}` is used when tagging. If pipeline is unavailable, fail closed with 503.
- `ui/` is a static HTML/JS site that reads `window.CONFIG` from `config.js`. Locally it is served by `nginx:alpine` in compose; on Azure, by a Static Web App.

## Stack
Python 3.12, Flask, raw SQL with pymssql (`as_dict=True`, `%s` placeholders), no ORM, gunicorn with 1 worker.
SQL Server 2022 locally (compose); Azure SQL serverless in production.

## Rules
- Each service reads `DATABASE_URL`, connects with retry and backoff (Azure error 40613), exposes `GET /health` (write + rollback on its own database; 200/503; never calls the other service), logs one line per request to stdout, and restricts CORS to `ALLOWED_ORIGIN`.
- Migrations are numbered files in `services/<name>/migrations/`, applied by `migrate.py` at startup and recorded in `schema_migrations`. NEVER edit an applied migration; write a new one. `001_init.sql` is the original schema plus the `health_check` table used by `/health`. The data-changing migration is `002_add_last_stage_change.sql`.
- Dockerfiles: `python:3.12-slim`, no `COPY . .`, pinned dependencies, non-root user. About 12 third-party packages per service at most.
- No secrets in any committed file. Local compose passwords are throwaway defaults; Azure secrets are GitHub Actions secrets only.
- Tests run against a local or CI SQL Server container, never Azure SQL. Coverage must be at least 70% per service.
- Azure: at most 2 Container Apps, 2 databases, 1 Static Web App. All names start with `<prefix>` (my IE username with dots replaced by hyphens — still to fill in). Resource group is `rg-sdd-3a` or `rg-sdd-3b` (still to fill in). Never create extra Azure resources.
- Changes reach `main` only through pull requests.

## How to work with me
- I must be able to explain every line at a written exam without notes. After writing a file, explain briefly what each part does and why.
- Ask before running `git commit`, `git push`, or any `az` command that creates or changes resources.
- When you write or substantially change a file, remind me to add a row to `AI_USAGE.md`.

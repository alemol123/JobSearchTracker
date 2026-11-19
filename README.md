# Job Search Tracker

A personal web app for tracking job applications through a hiring pipeline and finding which skills to improve based on the jobs applied to. Assignment 2 splits the Assignment 1 monolith into two services, each with its own database, deployed serverless on Azure.

**Live URL: https://amolinsieu2024ui.z1.web.core.windows.net**

The services scale to zero when nobody uses them. The first request after a break can take up to about a minute (the container starts, the database resumes, pending migrations run); the UI shows "Waking up the … service" and retries reads automatically.

## Features

**Application Pipeline** (pipeline service)
- Add applications with company, role, source (referral, job board, cold apply, other), date applied and an optional salary range.
- Move an application through the stages applied → phone screen → technical assessment → interview → final round → offer. Stages can be skipped forward but never moved backwards; rejected and withdrawn can be reached from any stage, and an offer can be accepted. All three close the application.
- Every stage change is recorded with a timestamp, and each application shows how many days it has been in its current stage.
- Applications with no movement for more than `STALE_DAYS` days are flagged as stale.
- Conversion rates between stages, grouped by source.

**Skill Gap Tracker** (skills service)
- Keep a list of skills and rate my own level from 1 to 5.
- Tag the skills each application requires.
- See which skills are missing, ranked by how many active applications want them, and a priority score (`applications wanting it × (5 − my level)`) for what to learn first. Only active applications count; the skills service asks the pipeline service which ones are active.
- Archiving a skill hides it from new tagging but keeps it on applications that already had it (soft delete).

## Architecture

```mermaid
flowchart LR
    Browser["Browser<br/>static UI (ui/)"]
    subgraph P["pipeline service (services/pipeline)"]
        PAPI["Flask + gunicorn<br/>/applications, /health"]
    end
    subgraph S["skills service (services/skills)"]
        SAPI["Flask + gunicorn<br/>/skills, /applications/{id}/skills, /health"]
    end
    PDB[("pipeline database<br/>applications, stage_history")]
    SDB[("skills database<br/>skills, my_skills, application_skills")]

    Browser -- "HTTPS + CORS" --> PAPI
    Browser -- "HTTPS + CORS" --> SAPI
    SAPI -- "HTTP, timeout PIPELINE_TIMEOUT_S<br/>GET /applications/active-ids<br/>GET /applications/{id}" --> PAPI
    PAPI --> PDB
    SAPI --> SDB
```

The seam is where ADR-2 put it (ADR-6). Only two facts cross it, and only from skills to pipeline: which applications are active (for the gap ranking) and whether an application exists (before tagging, replacing the foreign key lost in the split, ADR-7). Pipeline never calls skills. If pipeline is down, the gap page answers `pipeline_available: false` with a notice and tagging fails closed with 503; everything else in skills keeps working (see `evidence/partial_failure.txt`).

Each service has the same layers: `logic.py` (pure rules), `repository.py` (SQL), `routes.py` (JSON API), plus `app.py` (config, `/health`, request logs, CORS, JSON errors), `db.py` (connection with retry) and `migrate.py` (migrations at startup).

## Run locally (whole system)

Requirements: Docker Desktop (on Apple Silicon, turn on Rosetta emulation for the SQL Server image).

```bash
docker compose up --build
```

Then open **http://localhost:8080**.

| Container | What it is | Port |
|---|---|---|
| `sqlserver` | SQL Server 2022 holding both databases | 1433 |
| `db-init` | One-off: runs `db/init.sql` (creates the `pipeline` and `skills` databases and one login per service, idempotent), then exits | – |
| `pipeline` | Pipeline service | http://localhost:8001 |
| `skills` | Skills service (`PIPELINE_URL=http://pipeline:8000`) | http://localhost:8002 |
| `ui` | `nginx:alpine` serving `ui/` (no Dockerfile) | http://localhost:8080 |

Each service runs `python migrate.py` before gunicorn starts, so the schema is created or upgraded on every start. The passwords in `docker-compose.yml` are throwaway local defaults (`Local_..._Passw0rd!`); they can be overridden with `MSSQL_SA_PASSWORD`, `PIPELINE_DB_PASSWORD` and `SKILLS_DB_PASSWORD`. Azure uses different passwords, stored only as GitHub secrets.

To stop: `docker compose down` (keeps the data) or `docker compose down -v` (deletes the database volume).

## Run a single service

With compose, start only what the service needs:

```bash
docker compose up --build sqlserver db-init pipeline        # pipeline alone, on :8001
docker compose up --build sqlserver db-init skills          # skills alone, on :8002
```

Skills started alone shows the designed partial failure: `/skills/gap` returns the "pipeline unavailable" notice and tagging returns 503.

Without Docker for the service itself (SQL Server still from compose):

```bash
docker compose up -d sqlserver db-init
cd services/pipeline
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL='mssql://pipeline_user:Local_Pipeline_Passw0rd!@localhost:1433/pipeline'
python migrate.py && python app.py                          # serves on PORT (default 8000)
```

For skills, use `services/skills`, the `skills_user` / `Local_Skills_Passw0rd!` / `skills` URL and set `PIPELINE_URL=http://localhost:8001`.

## Configuration

| Variable | Service | Default | Azure value | Purpose |
|---|---|---|---|---|
| `DATABASE_URL` | both | none (secret) | Container Apps secret `db-url` | `mssql://user:password@host:1433/database` |
| `PORT` | both | `8000` | `8000` | Port gunicorn listens on |
| `ALLOWED_ORIGIN` | both | `http://localhost:8080` | the storage website URL | The only origin allowed by CORS |
| `GIT_SHA` | both | `unknown` | commit SHA | Reported by `/health` |
| `STALE_DAYS` | pipeline | `14` | `14` | Days without a stage change before an application is stale |
| `PIPELINE_URL` | skills | `http://pipeline:8000` | `https://<pipeline fqdn>` | Base URL of the pipeline service |
| `PIPELINE_TIMEOUT_S` | skills | `2` | `10` | Timeout for calls to pipeline (longer on Azure for cold starts) |

`system.yaml` describes the same configuration in machine-readable form, and `services/*/openapi.yaml` describe the two APIs.

## Tests and coverage

Tests run against a real SQL Server (the compose container locally, a GitHub Actions service container in CI), never against Azure SQL. Each service creates its own test database (`pipeline_test`, `skills_test`) and applies the migrations to it.

```bash
docker compose up -d sqlserver
cd services/pipeline                       # or services/skills
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
ruff check .
pytest --cov=pipeline --cov-report=term-missing --cov-fail-under=70   # --cov=skills for skills
```

Result (2026-11-19): **pipeline 109 tests, 100% coverage; skills 71 tests, 100% coverage.** CI fails below 70%.

| Test file | What it checks |
|---|---|
| `test_*_logic.py` | Pure rules: stage transitions, days in stage, stale flag, conversion rates, demand ranking, priority score, form parsing |
| `test_*_repo.py` | SQL against the SQL Server test database, including migration 002's `last_stage_change` |
| `test_*_routes.py` | JSON endpoints, status codes and error bodies through Flask's test client |
| `test_app_config.py` | `/health` (200 and 503), request logs, CORS, JSON errors, environment variables |
| `services/skills/tests/test_cross_seam.py` | The cross-seam flow with pipeline replaced by a `responses` stub: only active applications count, the gap degrades on timeout / 500 / bad JSON, tagging fails closed (503) or returns 404, the configured timeout is used (ADR-9) |

## Migrations

Numbered SQL files in `services/<name>/migrations/`, applied in order by `migrate.py` at container start and recorded in `schema_migrations`, so each runs exactly once. A migration and its record are committed in one transaction. Applied migrations are never edited (ADR-7).

| Service | Migration | What it does |
|---|---|---|
| pipeline | `001_init.sql` | `applications`, `stage_history`, `health_check` |
| pipeline | `002_add_last_stage_change.sql` | Adds `applications.last_stage_change`, backfills it from each application's newest `stage_history` row, then makes it `NOT NULL` |
| skills | `001_init.sql` | `skills`, `my_skills`, `application_skills` (`application_id` without a foreign key), `health_check` |

Migration 002 on Azure (evidence in `evidence/`): data captured before (`before_002.json`, 2026-11-17), deployed by [CD run 44552257328](https://github.com/alemol123/JobSearchTracker/actions/runs/44552257328), startup log `applied migration 002_add_last_stage_change.sql` (`migration_002_log.txt`), data after (`after_002.json`): the same four applications with every field unchanged, plus `last_stage_change`.

## How deployment works

```
branch → pull request → CI ──(merge)──> CI on main ──(passed)──> CD
```

- **CI** (`.github/workflows/ci.yml`, every push and pull request): for each service, install pinned dependencies, `ruff`, `pytest` with coverage ≥ 70% against a SQL Server service container; validate both OpenAPI documents and `system.yaml` against `system.schema.json`; build both Docker images. On `main` only, push the images to GHCR as `ghcr.io/alemol123/jst-<service>:<commit sha>`.
- **CD** (`.github/workflows/cd.yml`, after CI succeeds on a push to `main`):
  1. Sign in to Azure through OpenID Connect as the managed identity (no password stored).
  2. Create or update both Container Apps with the images CI built for that exact commit: min 0 / max 1 replicas, `DATABASE_URL` from a Container Apps secret, `ALLOWED_ORIGIN` = the UI's URL, `GIT_SHA`.
  3. Write `ui/config.js` with the live service URLs and upload `ui/` to the storage account's `$web` container.
  4. Call `/health` on both services until they return 200 with the new commit SHA, and fail the run if that takes more than 5 minutes.

`main` is protected: changes arrive only through pull requests with green CI.

## Initial Azure setup (done once, by hand)

Everything after this is done by CD; nothing is changed in the portal. Resource names and the reasons they differ from the brief are in ADR-8. Passwords are placeholders here and never committed.

```bash
az login
az account set --subscription "Azure for Students"
P=amolins-ieu2024; RG=rg-amolins; L=germanywestcentral
# My subscription allows only: germanywestcentral, polandcentral, austriaeast, spaincentral, switzerlandnorth
az policy assignment list --query "[].parameters.listOfAllowedLocations.value" -o tsv

# 0. Resource group and resource providers
az group create -n $RG -l $L
for NS in Microsoft.App Microsoft.Sql Microsoft.Storage Microsoft.ManagedIdentity; do
  az provider register --namespace $NS --wait
done

# 1. SQL server, firewall, two serverless databases on the free offer
az sql server create -g $RG -n $P-sql -l $L --admin-user sqladmin --admin-password '<ADMIN_PW>'
az sql server firewall-rule create -g $RG -s $P-sql -n AllowAllWindowsAzureIps \
    --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0
for S in pipeline skills; do
  az sql db create -g $RG -s $P-sql -n $P-$S-db \
    --edition GeneralPurpose --family Gen5 --compute-model Serverless \
    --capacity 1 --min-capacity 0.5 --backup-storage-redundancy Local \
    --use-free-limit true --free-limit-exhaustion-behavior AutoPause
done
```

**2. One user per database.** Temporarily allow my IP (portal: Query editor → "Allowlist IP", or `az sql server firewall-rule create ... -n TempMyIP`), open each database in the portal's Query editor as `sqladmin` and run (contained users, see ADR-8):

```sql
-- in amolins-ieu2024-pipeline-db
CREATE USER pipeline_user WITH PASSWORD = '<PIPELINE_PW>';
ALTER ROLE db_owner ADD MEMBER pipeline_user;
-- in amolins-ieu2024-skills-db
CREATE USER skills_user WITH PASSWORD = '<SKILLS_PW>';
ALTER ROLE db_owner ADD MEMBER skills_user;
```

Then remove my IP again (portal: SQL server → Networking → delete the rule → Save).

```bash
# 3. Container Apps environment (no Log Analytics workspace: live logs still work)
az extension add --name containerapp --upgrade
az containerapp env create -g $RG -n $P-env -l $L --logs-destination none

# 4. Storage account for the UI, with static website hosting
az storage account create -g $RG -n amolinsieu2024ui -l $L --sku Standard_LRS --kind StorageV2 \
    --https-only true --min-tls-version TLS1_2 --allow-blob-public-access false
az storage blob service-properties update --account-name amolinsieu2024ui --auth-mode key \
    --static-website --index-document index.html --404-document index.html

# 5. Managed identity for GitHub Actions (OIDC), Contributor on this resource group only
az identity create -g $RG -n $P-github-id -l $L
az role assignment create --assignee-object-id $(az identity show -g $RG -n $P-github-id --query principalId -o tsv) \
    --assignee-principal-type ServicePrincipal --role Contributor --scope $(az group show -n $RG --query id -o tsv)
# GitHub's OIDC subject includes the numeric owner and repo IDs:
#   curl -s https://api.github.com/repos/alemol123/JobSearchTracker  ->  .owner.id and .id
az identity federated-credential create -g $RG --identity-name $P-github-id -n github-main-ids \
    --issuer https://token.actions.githubusercontent.com \
    --subject 'repo:alemol123@177339378/JobSearchTracker@1399842449:ref:refs/heads/main' \
    --audiences api://AzureADTokenExchange
az identity show -g $RG -n $P-github-id --query "{clientId:clientId, tenantId:tenantId}"
az account show --query id -o tsv          # subscription ID
```

**6. GitHub secrets** (repo → Settings → Secrets and variables → Actions):

| Secret | Value |
|---|---|
| `AZURE_CLIENT_ID` | the identity's `clientId` |
| `AZURE_TENANT_ID` | the identity's `tenantId` |
| `AZURE_SUBSCRIPTION_ID` | the subscription ID |
| `PIPELINE_DATABASE_URL` | `mssql://pipeline_user:<PIPELINE_PW>@amolins-ieu2024-sql.database.windows.net:1433/amolins-ieu2024-pipeline-db` (no `< >`) |
| `SKILLS_DATABASE_URL` | `mssql://skills_user:<SKILLS_PW>@amolins-ieu2024-sql.database.windows.net:1433/amolins-ieu2024-skills-db` (no `< >`) |

**7. First deployment.** Merge to `main`. After CI pushes the images for the first time, make both GHCR packages public (github.com → Packages → `jst-pipeline` / `jst-skills` → Package settings → Change visibility → Public) so Container Apps can pull them, then re-run CD. The first CD run creates both Container Apps.

**8. Access for grading:** `az role assignment create --assignee <professor's email> --role Reader --scope $(az group show -n $RG --query id -o tsv)`

Useful afterwards:

```bash
az containerapp logs show -g rg-amolins -n amolins-ieu2024-pipeline --type console --follow
az containerapp show -g rg-amolins -n amolins-ieu2024-pipeline --query "properties.template.scale"
```

## Security incidents

None in the repository: no credential has been committed (checked over the whole Git history on 2026-11-19). Two related events, both handled the same day:

- 2026-11-17: the first database URL secrets contained the placeholder brackets around the passwords; CD's health check failed and the GitHub secrets were corrected. Nothing was exposed.
- 2026-11-17: the skills database password was visible in a screenshot shared with my AI assistant (not in GitHub). As a precaution it was rotated the same day (`ALTER USER skills_user WITH PASSWORD ...`), the `SKILLS_DATABASE_URL` secret was updated and CD redeployed.

## Project structure

```
services/
    pipeline/                 Pipeline service (owns applications, stage_history)
        app.py db.py migrate.py
        pipeline/             logic.py, repository.py, routes.py
        migrations/           001_init.sql, 002_add_last_stage_change.sql
        tests/                pytest suite
        Dockerfile .dockerignore requirements.txt requirements-dev.txt pytest.ini openapi.yaml
    skills/                   Skills service (owns skills, my_skills, application_skills)
        app.py db.py migrate.py
        skills/               logic.py, repository.py, routes.py, pipeline_client.py
        migrations/           001_init.sql
        tests/                pytest suite, including test_cross_seam.py
        Dockerfile .dockerignore requirements.txt requirements-dev.txt pytest.ini openapi.yaml
ui/                           Static UI: one HTML page per screen, app.js, config.js, style.css
db/init.sql                   Local only: databases and logins for compose
docker-compose.yml            Whole system locally
.github/workflows/            ci.yml, cd.yml
system.yaml                   Machine-readable description of services, config and Azure resources
evidence/                     Migration 002 and partial-failure evidence
ADR.md                        Architecture Decision Records 1-10
AI_USAGE.md                   AI usage log
```

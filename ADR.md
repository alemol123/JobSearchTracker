# Architecture Decision Records

## [1]. Backend language and framework: Python + Flask
Date: 2026-10-01
Status: Decided
Context: The app is a single-user, server-rendered tool with two small domains, and it must run as one process started by `python app.py`. I decided to use python as that is the language I feel most comfortable with. 
Decision: Use Python with Flask, Jinja templates and HTML form POSTs, and access SQLite directly through Python's built-in `sqlite3` module.
Alternatives considered: Django, rejected because its ORM, admin panel, auth and migration system solve problems this app doesn't have and add many files I'd have to justify. FastAPI, rejected because it's designed for JSON APIs with async and Pydantic models, while this app renders HTML pages from forms with no client-side JavaScript.
Consequences: Flask keeps the app small and lets me organise each domain as its own Blueprint, which maps cleanly onto a future service split. The cost is that I write the SQL and table setup myself instead of getting an ORM and migrations for free.

## [2]. Keeping the Application Pipeline and Skill Gap domains independently modular
Date: 2026-10-03
Status: Decided
Context: The app has two domains (Application Pipeline and Skill Gap Tracker) that will be split into separate services in Assignment 2. The skill gap ranking needs to know which applications are still active, which is information that belongs to the pipeline.
Decision: Each domain gets its own package (`pipeline/`, `skills/`) with pure `logic.py`, SQL-only `repository.py` and its own Flask Blueprint. The only shared table is `application_skills`; the skills domain never queries `applications` directly, and instead receives the set of active application IDs from `pipeline.repository.get_active_application_ids()`, passed in by the route.
Alternatives considered: Letting the skills SQL join `application_skills` with `applications` to filter on `status = 'active'`. It's one simpler query, but it makes the skills code depend on the pipeline's table and columns, so splitting the services later would mean rewriting the skills queries.
Consequences: In a future split, `get_active_application_ids()` becomes one HTTP call from the skills service to the pipeline service, and nothing else in the skills logic changes. The cost is one extra query per skills page and slightly more wiring in the routes.

## [3]. SQLite data model: append-only stage history and a single bridge table between domains
Date: 2026-10-04
Status: Decided
Context: The pipeline needs both the current stage of each application (for the list page) and the full timeline of stage changes (for days-in-stage and conversion rates). The skills domain needs to know which skills each application requires without owning the applications themselves.
Decision: `stage_history` is append-only, with one row per stage entered, and `applications.current_stage` and `status` are stored as well so the list page doesn't have to work them out from history every time. The two domains are linked only by the `application_skills` bridge table (application_id, skill_id) with a composite primary key, and `skills.archived` is used for soft delete.
Alternatives considered: Storing only `current_stage` with no history table, rejected because conversion rates and days-in-stage need to know when each stage was entered. Storing required skills as a comma-separated text column on `applications`, rejected because it can't be counted or joined in SQL, allows duplicates and typos, and would put skills data inside the pipeline's table.
Consequences: `current_stage` can drift from history if updated alone, so `change_stage()` always writes both in one transaction. In a future split, `application_skills` moves to the skills service and keeps `application_id` as a plain ID instead of a foreign key.

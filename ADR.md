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

## [4]. Testing approach: test-first pure logic, real temporary SQLite for repositories, thin route checks
Date: 2026-10-05
Status: Decided
Context: The assignment requires at least 70% coverage on the core business logic of both domains, and I have to be able to explain every rule on paper. The rules most likely to have bugs are the stage transitions, conversion rates and the skill priority score, not the Flask wiring.
Decision: Business rules live in pure functions in each domain's `logic.py` (no Flask, no SQL, `today` passed in as a parameter) and are written test-first with pytest, covering edge cases like stage skips, terminal states, ties and empty inputs. Repositories are tested against a real SQLite file in pytest's `tmp_path` (a fake), and routes only get a few smoke tests through Flask's test client to check the pages are wired up.
Alternatives considered: Mocking the `sqlite3` connection in repository tests, rejected because the mocks would only check that some SQL string was sent, not that the SQL is correct, and a temporary SQLite file is just as fast. Testing everything through the routes with the test client, rejected because a failing page test doesn't tell me which rule broke, and it would be slower to write edge cases that way.
Consequences: Coverage is well above the 70% bar and a failing test points straight at the broken rule. The thinner side is the templates: what the HTML looks like is only checked by a few text assertions and by using the app by hand.

## [5]. Not building automatic skill extraction from job postings
Date: 2026-10-06
Status: Decided
Context: The skill gap ranking depends on knowing which skills each application requires. Typing tags by hand is the slowest part of using the app, so the obvious feature to add was pasting a job posting (text or URL) and having the required skills detected automatically.
Decision: Skills are tagged on each application manually, choosing from my own skills list, and the app does not parse job postings in any way.
Alternatives considered: Keyword matching against my skills list, rejected because postings phrase the same skill many ways ("Postgres", "PostgreSQL", "relational databases") and also list "nice to have" skills, so the demand counts would be wrong without me checking them anyway. Sending the posting to an external AI or NLP API, rejected because it adds a runtime dependency on an outside service and an API key, which goes against keeping the app self-contained in one container, and its output would still need checking.
Consequences: Tagging takes a minute per application, but every tag is one I chose, so demand counts and priority scores are trustworthy and the skills logic stays simple and fully testable. If extraction is added later, it can sit in front of the existing `tag_application()` as a suggestion step without changing the schema or the scoring.

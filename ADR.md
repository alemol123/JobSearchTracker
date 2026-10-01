# Architecture Decision Records

## [1]. Backend language and framework: Python + Flask
Date: 2026-10-01
Status: Decided
Context: The app is a single-user, server-rendered tool with two small domains, and it must run as one process started by `python app.py`. I decided to use python as that is the language I feel most comfortable with. 
Decision: Use Python with Flask, Jinja templates and HTML form POSTs, and access SQLite directly through Python's built-in `sqlite3` module.
Alternatives considered: Django, rejected because its ORM, admin panel, auth and migration system solve problems this app doesn't have and add many files I'd have to justify. FastAPI, rejected because it's designed for JSON APIs with async and Pydantic models, while this app renders HTML pages from forms with no client-side JavaScript.
Consequences: Flask keeps the app small and lets me organise each domain as its own Blueprint, which maps cleanly onto a future service split. The cost is that I write the SQL and table setup myself instead of getting an ORM and migrations for free.

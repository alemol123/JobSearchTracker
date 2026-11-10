import os
import sqlite3

from flask import current_app, g

DB_FILENAME = "jobtracker.db"
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")


def db_path(data_dir):
    return os.path.join(data_dir, DB_FILENAME)


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row             # rows behave like dicts: row["company"]
    conn.execute("PRAGMA foreign_keys = ON")   # SQLite ignores REFERENCES unless enabled
    return conn


def init_db(path):
    with open(SCHEMA_PATH) as f:
        schema = f.read()
    conn = connect(path)
    conn.executescript(schema)
    conn.close()


def get_db():
    # One connection per request, reused if asked for twice in the same request.
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(exception=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()

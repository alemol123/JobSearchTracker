"""Tests run against a real SQL Server: the local compose container, or the CI service
container. Never Azure SQL: the default URL points at localhost.

The pipeline service is never really called: tests that need it replace it with
a stub using `responses` (see test_cross_seam.py)."""

import os
from urllib.parse import unquote, urlparse

import pymssql
import pytest

TEST_URL = os.environ.get("TEST_DATABASE_URL",
                          "mssql://sa:Local_Sa_Passw0rd!@localhost:1433/skills_test")
os.environ["DATABASE_URL"] = TEST_URL     # the app and db.connect() read this
os.environ["PIPELINE_URL"] = "http://pipeline:8000"   # the URL the stubs answer on

# Imported after the variables are set, so nothing can read them too early.
import db
import migrate
from app import create_app


@pytest.fixture(scope="session")
def database():
    """Once per test run: create the test database if needed and apply the migrations."""
    url = urlparse(TEST_URL)
    name = url.path.lstrip("/")
    master = pymssql.connect(server=url.hostname, port=url.port, user=unquote(url.username),
                             password=unquote(url.password), database="master", autocommit=True)
    master.cursor().execute(f"IF DB_ID('{name}') IS NULL CREATE DATABASE [{name}]")
    master.close()
    conn = db.connect()
    migrate.run(conn)                     # also tests that every migration applies cleanly
    conn.close()


@pytest.fixture
def conn(database):
    """A connection to the test database with empty tables, fresh for every test."""
    connection = db.connect()
    cur = connection.cursor()
    # Children first: both tables reference skills(id).
    cur.execute("DELETE FROM application_skills; DELETE FROM my_skills; DELETE FROM skills;")
    connection.commit()
    yield connection
    connection.close()


@pytest.fixture
def client(conn):
    """A Flask test client using the same (just emptied) test database."""
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()

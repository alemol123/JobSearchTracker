"""Deployment contract (assignment §7): everything is configured by environment
variables, with sane defaults, and the SQLite file lands at $DATA_DIR/jobtracker.db."""

import os

from app import create_app, get_port


def test_database_file_is_created_inside_data_dir(tmp_path, monkeypatch):
    data_dir = tmp_path / "nested" / "data"          # doesn't exist yet
    monkeypatch.setenv("DATA_DIR", str(data_dir))

    app = create_app()

    assert app.config["DATABASE"] == os.path.join(str(data_dir), "jobtracker.db")
    assert os.path.isfile(app.config["DATABASE"])


def test_stale_days_comes_from_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("STALE_DAYS", "30")

    assert create_app().config["STALE_DAYS"] == 30


def test_defaults_when_variables_are_not_set(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)                       # so ./data is created in a temp folder
    for name in ["DATA_DIR", "STALE_DAYS", "PORT"]:
        monkeypatch.delenv(name, raising=False)

    app = create_app()

    assert app.config["DATA_DIR"] == "./data"
    assert app.config["STALE_DAYS"] == 14
    assert get_port() == 8000


def test_port_comes_from_environment(monkeypatch):
    monkeypatch.setenv("PORT", "9000")

    assert get_port() == 9000


def test_starting_twice_on_the_same_database_is_safe(tmp_path, monkeypatch):
    # CREATE TABLE IF NOT EXISTS: a restart must not fail or wipe data.
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    client = create_app().test_client()
    client.post("/skills/", data={"name": "Python", "category": ""})

    restarted = create_app().test_client()

    assert b"Python" in restarted.get("/skills/").data

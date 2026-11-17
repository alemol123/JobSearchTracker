"""The service contract: configuration from environment variables, /health,
one log line per request, CORS for one origin only, and JSON errors."""

import logging

import pymssql

from app import create_app, get_port
from pipeline import repository as repo


def test_stale_days_comes_from_environment(monkeypatch):
    monkeypatch.setenv("STALE_DAYS", "30")

    assert create_app().config["STALE_DAYS"] == 30


def test_defaults_when_variables_are_not_set(monkeypatch):
    for name in ["STALE_DAYS", "PORT"]:
        monkeypatch.delenv(name, raising=False)

    assert create_app().config["STALE_DAYS"] == 14
    assert get_port() == 8000


def test_port_comes_from_environment(monkeypatch):
    monkeypatch.setenv("PORT", "9000")

    assert get_port() == 9000


# ---------- /health ----------

def test_health_is_200_when_the_database_is_writable(client, monkeypatch):
    monkeypatch.setenv("GIT_SHA", "abc123")

    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "db": "ok", "version": "abc123"}


def test_health_leaves_nothing_behind(client, conn):
    client.get("/health")

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS n FROM health_check")
    assert cur.fetchone()["n"] == 0                 # the insert was rolled back


def test_health_is_503_when_the_database_is_down(client, monkeypatch):
    def no_database():
        raise pymssql.OperationalError("connection refused")
    monkeypatch.setattr("app.connect", no_database)

    response = client.get("/health")

    assert response.status_code == 503
    assert response.get_json()["db"] == "unavailable"


# ---------- logs, CORS, errors ----------

def test_every_request_logs_one_line(client, caplog):
    with caplog.at_level(logging.INFO):
        client.get("/applications/999999")

    assert any("GET /applications/999999 404" in r.getMessage() for r in caplog.records)


def test_cors_headers_only_for_the_allowed_origin(client, monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGIN", "http://localhost:8080")

    allowed = client.get("/applications", headers={"Origin": "http://localhost:8080"})
    other = client.get("/applications", headers={"Origin": "http://evil.example"})

    assert allowed.headers["Access-Control-Allow-Origin"] == "http://localhost:8080"
    assert "Access-Control-Allow-Origin" not in other.headers


def test_unknown_url_and_wrong_method_are_json(client):
    not_found = client.get("/nope")
    wrong_method = client.delete("/applications")

    assert not_found.status_code == 404 and "error" in not_found.get_json()
    assert wrong_method.status_code == 405 and "error" in wrong_method.get_json()


def test_unexpected_error_is_a_json_500_without_details(client, monkeypatch):
    def broken(conn):
        raise RuntimeError("secret internal detail")
    monkeypatch.setattr(repo, "list_applications", broken)

    response = client.get("/applications")

    assert response.status_code == 500
    assert response.get_json() == {"error": "Internal error"}

"""The service contract: /health (which never calls pipeline), one log line per
request, CORS for one origin only, and JSON errors."""

import logging

import pymssql
import responses

from app import create_app, get_port
from skills import repository as repo


def test_port_default_and_from_environment(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    assert get_port() == 8000

    monkeypatch.setenv("PORT", "9000")
    assert get_port() == 9000


@responses.activate
def test_health_is_200_and_never_calls_pipeline(client):
    # responses is active with no stubs: any HTTP call from /health would raise.
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"
    assert len(responses.calls) == 0


def test_health_is_503_when_the_database_is_down(client, monkeypatch):
    def no_database():
        raise pymssql.OperationalError("connection refused")
    monkeypatch.setattr("app.connect", no_database)

    response = client.get("/health")

    assert response.status_code == 503
    assert response.get_json()["db"] == "unavailable"


def test_every_request_logs_one_line(client, caplog):
    with caplog.at_level(logging.INFO):
        client.get("/skills")

    assert any("GET /skills 200" in r.getMessage() for r in caplog.records)


def test_cors_headers_only_for_the_allowed_origin(client, monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGIN", "http://localhost:8080")

    allowed = client.get("/skills", headers={"Origin": "http://localhost:8080"})
    other = client.get("/skills", headers={"Origin": "http://evil.example"})

    assert allowed.headers["Access-Control-Allow-Origin"] == "http://localhost:8080"
    assert "Access-Control-Allow-Origin" not in other.headers


def test_unknown_url_is_json_404(client):
    response = client.get("/nope")

    assert response.status_code == 404 and "error" in response.get_json()


def test_unexpected_error_is_a_json_500_without_details(client, monkeypatch):
    def broken(conn, include_archived=False):
        raise RuntimeError("secret internal detail")
    monkeypatch.setattr(repo, "list_skills", broken)

    response = client.get("/skills")

    assert response.status_code == 500
    assert response.get_json() == {"error": "Internal error"}


def test_create_app_registers_both_blueprints():
    rules = {rule.rule for rule in create_app().url_map.iter_rules()}

    assert "/skills/gap" in rules and "/applications/<int:app_id>/skills" in rules

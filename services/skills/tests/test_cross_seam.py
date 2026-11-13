"""Integration tests across the seam: skills calling pipeline over HTTP.

The pipeline service is replaced by a stub with `responses`, which intercepts the
HTTP calls `requests` makes. This runs in CI without starting pipeline, and can
simulate what is hard to do with a real service: timeouts and error answers."""

import requests
import responses

from skills import repository as repo

ACTIVE = "http://pipeline:8000/applications/active-ids"


def _tag_sql_on_two_applications(conn):
    sql = repo.add_skill(conn, "SQL", None)
    repo.tag_application(conn, 1, sql)
    repo.tag_application(conn, 2, sql)
    return sql


@responses.activate
def test_gap_counts_only_active_applications_from_pipeline(client, conn):
    _tag_sql_on_two_applications(conn)
    responses.get(ACTIVE, json={"ids": [1]})          # pipeline says only app 1 is active

    body = client.get("/skills/gap").get_json()

    assert body["pipeline_available"] is True
    assert body["missing"] == [{"skill_id": body["missing"][0]["skill_id"], "demand": 1, "name": "SQL"}]
    assert body["priorities"][0]["score"] == 5        # demand 1 x gap 5 (I don't have SQL)


@responses.activate
def test_gap_degrades_when_pipeline_times_out(client, conn):
    _tag_sql_on_two_applications(conn)
    responses.get(ACTIVE, body=requests.exceptions.ConnectTimeout())

    response = client.get("/skills/gap")

    assert response.status_code == 200                # the page still works...
    body = response.get_json()
    assert body["pipeline_available"] is False        # ...but says it can't rank
    assert body["priorities"] == [] and body["missing"] == []
    assert "unavailable" in body["notice"]


@responses.activate
def test_gap_degrades_when_pipeline_errors(client, conn):
    responses.get(ACTIVE, status=500)

    assert client.get("/skills/gap").get_json()["pipeline_available"] is False


@responses.activate
def test_gap_degrades_when_pipeline_sends_bad_json(client, conn):
    responses.get(ACTIVE, json={"unexpected": "shape"})   # no "ids" key

    assert client.get("/skills/gap").get_json()["pipeline_available"] is False


@responses.activate
def test_tagging_fails_closed_when_pipeline_is_down(client, conn):
    sql = repo.add_skill(conn, "SQL", None)
    responses.get("http://pipeline:8000/applications/7", body=requests.exceptions.ConnectionError())

    response = client.post("/applications/7/skills", json={"skill_id": sql})

    assert response.status_code == 503
    assert repo.get_tags(conn) == []                  # nothing was tagged


@responses.activate
def test_tagging_fails_closed_when_pipeline_answers_with_an_error(client, conn):
    sql = repo.add_skill(conn, "SQL", None)
    responses.get("http://pipeline:8000/applications/7", status=500)

    assert client.post("/applications/7/skills", json={"skill_id": sql}).status_code == 503


@responses.activate
def test_tagging_rejects_unknown_application(client, conn):
    sql = repo.add_skill(conn, "SQL", None)
    responses.get("http://pipeline:8000/applications/7", status=404)

    assert client.post("/applications/7/skills", json={"skill_id": sql}).status_code == 404
    assert repo.get_tags(conn) == []


@responses.activate
def test_calls_use_the_configured_timeout(client, conn, monkeypatch):
    monkeypatch.setenv("PIPELINE_TIMEOUT_S", "0.5")
    responses.get(ACTIVE, json={"ids": []})

    client.get("/skills/gap")

    assert responses.calls[0].request.req_kwargs["timeout"] == 0.5

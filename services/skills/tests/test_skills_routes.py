"""The skills JSON API through Flask's test client. The rules themselves are tested
in test_skills_logic.py, and the calls to pipeline in test_cross_seam.py.

IDs come from the responses: SQL Server keeps counting IDENTITY values after a
DELETE, so the first skill of a test is not always id 1."""

import responses

PIPELINE = "http://pipeline:8000"


def _add_skill(client, name, category=None):
    response = client.post("/skills", json={"name": name, "category": category})
    assert response.status_code == 201
    return response.get_json()["id"]


def test_skills_list_is_empty_at_first(client):
    assert client.get("/skills").get_json() == {"skills": [], "max_level": 5}


def test_added_skill_is_in_the_list(client):
    skill_id = _add_skill(client, "Docker", "tool")

    [skill] = client.get("/skills").get_json()["skills"]

    assert skill == {"id": skill_id, "name": "Docker", "category": "tool",
                     "archived": False, "proficiency_level": None}


def test_duplicate_skill_is_409_and_blank_name_is_400(client):
    _add_skill(client, "Docker")

    duplicate = client.post("/skills", json={"name": "docker"})
    blank = client.post("/skills", json={"name": " "})

    assert duplicate.status_code == 409 and "already exists" in duplicate.get_json()["error"]
    assert blank.status_code == 400 and blank.get_json()["errors"] == ["Skill name is required."]


def test_set_and_clear_proficiency(client):
    skill_id = _add_skill(client, "Docker")
    url = f"/skills/{skill_id}/proficiency"

    assert client.put(url, json={"level": 3}).status_code == 200
    assert client.get("/skills").get_json()["skills"][0]["proficiency_level"] == 3

    assert client.put(url, json={"level": 9}).status_code == 400
    assert client.put(url, json={"level": ""}).status_code == 200     # blank = I don't have it
    assert client.get("/skills").get_json()["skills"][0]["proficiency_level"] is None


def test_proficiency_for_missing_skill_is_404(client):
    assert client.put("/skills/999999/proficiency", json={"level": 3}).status_code == 404


def test_archive_skill(client):
    skill_id = _add_skill(client, "Perl")

    assert client.post(f"/skills/{skill_id}/archive").get_json() == {"ok": True}
    assert client.get("/skills").get_json()["skills"][0]["archived"] is True


def test_archive_missing_skill_is_404(client):
    assert client.post("/skills/999999/archive").status_code == 404


@responses.activate
def test_tag_list_and_untag_skill_on_application(client):
    responses.get(f"{PIPELINE}/applications/1", json={"application": {"id": 1}})   # pipeline: it exists
    docker = _add_skill(client, "Docker")
    python = _add_skill(client, "Python")

    tagged = client.post("/applications/1/skills", json={"skill_id": docker})
    body = client.get("/applications/1/skills").get_json()

    assert tagged.status_code == 201
    assert [s["name"] for s in body["tagged"]] == ["Docker"]
    assert [s["name"] for s in body["available"]] == ["Python"]
    assert python not in [s["id"] for s in body["tagged"]]

    assert client.delete(f"/applications/1/skills/{docker}").status_code == 200
    assert client.get("/applications/1/skills").get_json()["tagged"] == []


@responses.activate
def test_tagging_unknown_or_archived_skill_is_400(client):
    responses.get(f"{PIPELINE}/applications/1", json={"application": {"id": 1}})
    perl = _add_skill(client, "Perl")
    client.post(f"/skills/{perl}/archive")

    unknown = client.post("/applications/1/skills", json={"skill_id": 999999})
    archived = client.post("/applications/1/skills", json={"skill_id": perl})
    not_a_number = client.post("/applications/1/skills", json={"skill_id": "abc"})

    assert unknown.status_code == 400 and "not found" in unknown.get_json()["error"]
    assert archived.status_code == 400 and "archived" in archived.get_json()["error"]
    assert not_a_number.status_code == 400


def test_tags_of_an_application_do_not_need_pipeline(client):
    # No stub registered: if this route called pipeline, the test would fail.
    assert client.get("/applications/5/skills").get_json() == {"tagged": [], "available": []}

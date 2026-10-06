"""A few end-to-end checks of the skills pages through Flask's test client.
The rules themselves are tested in test_skills_logic.py."""

APPLICATION = {
    "company": "Acme",
    "role": "Backend Developer",
    "source": "referral",
    "date_applied": "2026-10-01",
    "salary_range_min": "",
    "salary_range_max": "",
}


def _add_skill(client, name):
    return client.post("/skills/", data={"name": name, "category": ""}, follow_redirects=True)


def test_skills_page_loads_empty(client):
    response = client.get("/skills/")

    assert response.status_code == 200
    assert b"No skills yet" in response.data


def test_add_skill_shows_it_in_the_list(client):
    response = _add_skill(client, "Docker")

    assert b"Skill added" in response.data
    assert b"Docker" in response.data


def test_invalid_or_duplicate_skill_shows_error(client):
    _add_skill(client, "Docker")

    assert b"already exists" in _add_skill(client, "docker").data
    assert b"Skill name is required" in _add_skill(client, " ").data


def test_set_and_clear_proficiency(client):
    _add_skill(client, "Docker")

    saved = client.post("/skills/1/proficiency", data={"level": "3"}, follow_redirects=True)
    bad = client.post("/skills/1/proficiency", data={"level": "9"}, follow_redirects=True)
    cleared = client.post("/skills/1/proficiency", data={"level": ""}, follow_redirects=True)

    assert b"Proficiency saved" in saved.data
    assert b"between 1 and 5" in bad.data
    assert b"Removed from my skills" in cleared.data


def test_archive_skill_moves_it_to_archived_section(client):
    _add_skill(client, "Perl")

    response = client.post("/skills/1/archive", follow_redirects=True)

    assert b"archived" in response.data
    assert b'action="/skills/1/archive"' not in response.data


def test_archive_missing_skill_is_404(client):
    assert client.post("/skills/999/archive").status_code == 404


def test_tag_and_untag_skill_on_application(client):
    client.post("/applications/new", data=APPLICATION)
    _add_skill(client, "Docker")

    tagged = client.post("/skills/applications/1/tag", data={"skill_id": "1"}, follow_redirects=True)
    assert b"Docker" in tagged.data and b"Remove" in tagged.data

    untagged = client.post("/skills/applications/1/untag", data={"skill_id": "1"},
                           follow_redirects=True)
    assert b"No skills tagged yet" in untagged.data


def test_tagging_unknown_skill_shows_error(client):
    client.post("/applications/new", data=APPLICATION)

    response = client.post("/skills/applications/1/tag", data={"skill_id": "999"},
                           follow_redirects=True)

    assert b"not found" in response.data


def test_skills_page_for_missing_application_is_404(client):
    assert client.get("/skills/applications/999").status_code == 404


def test_gap_page_scores_only_active_applications(client):
    # Application 1 (active) wants Docker; application 2 (rejected) wants Perl.
    client.post("/applications/new", data=APPLICATION)
    client.post("/applications/new", data={**APPLICATION, "company": "Beta"})
    _add_skill(client, "Docker")
    _add_skill(client, "Perl")
    client.post("/skills/applications/1/tag", data={"skill_id": "1"})
    client.post("/skills/applications/2/tag", data={"skill_id": "2"})
    client.post("/applications/2/stage", data={"stage": "rejected"})

    response = client.get("/skills/gap")

    assert response.status_code == 200
    assert b"Docker" in response.data
    assert b"Perl" not in response.data


def test_proficiency_for_missing_skill_is_404(client):
    assert client.post("/skills/999/proficiency", data={"level": "3"}).status_code == 404

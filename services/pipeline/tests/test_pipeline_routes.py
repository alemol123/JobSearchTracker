"""A few end-to-end checks through Flask's test client. The rules themselves
are tested in test_pipeline_logic.py; these only check the pages are wired up."""

VALID_FORM = {
    "company": "Acme",
    "role": "Backend Developer",
    "source": "referral",
    "date_applied": "2026-10-01",
    "salary_range_min": "",
    "salary_range_max": "",
}


def test_home_redirects_to_applications(client):
    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/applications/")


def test_empty_list_page_loads(client):
    response = client.get("/applications/")

    assert response.status_code == 200
    assert b"No applications yet" in response.data


def test_new_application_form_loads(client):
    response = client.get("/applications/new")

    assert response.status_code == 200
    assert b'name="company"' in response.data


def test_adding_an_application_shows_it_in_the_list(client):
    response = client.post("/applications/new", data=VALID_FORM, follow_redirects=True)

    assert response.status_code == 200
    assert b"Acme" in client.get("/applications/").data


def test_invalid_form_is_shown_again_with_errors(client):
    response = client.post("/applications/new", data={**VALID_FORM, "company": ""})

    assert response.status_code == 400
    assert b"Company is required" in response.data


def test_stage_change_moves_application_forward(client):
    client.post("/applications/new", data=VALID_FORM)

    response = client.post("/applications/1/stage", data={"stage": "interview"},
                           follow_redirects=True)

    assert b"Stage updated" in response.data
    assert b"Current stage: <strong>interview</strong>" in response.data


def test_backward_stage_change_shows_error_and_changes_nothing(client):
    client.post("/applications/new", data=VALID_FORM)
    client.post("/applications/1/stage", data={"stage": "interview"})

    response = client.post("/applications/1/stage", data={"stage": "phone_screen"},
                           follow_redirects=True)

    assert b"Cannot move backwards" in response.data
    assert b"Current stage: <strong>interview</strong>" in response.data


def test_missing_application_is_404(client):
    assert client.get("/applications/999").status_code == 404
    assert client.post("/applications/999/stage", data={"stage": "offer"}).status_code == 404

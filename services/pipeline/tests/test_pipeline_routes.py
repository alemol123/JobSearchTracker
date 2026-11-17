"""The JSON API through Flask's test client. The rules themselves are tested in
test_pipeline_logic.py; these check status codes and the shape of the JSON.

IDs come from the responses: SQL Server keeps counting IDENTITY values after a
DELETE, so the first application of a test is not always id 1."""

VALID = {
    "company": "Acme",
    "role": "Backend Developer",
    "source": "referral",
    "date_applied": "2026-10-01",
}


def _create(client, **changes):
    response = client.post("/applications", json={**VALID, **changes})
    assert response.status_code == 201
    return response.get_json()["id"]


def test_empty_list(client):
    response = client.get("/applications")

    assert response.status_code == 200
    assert response.get_json() == {"applications": [], "stale_days": 14}


def test_created_application_is_in_the_list_with_iso_dates(client):
    app_id = _create(client)

    [application] = client.get("/applications").get_json()["applications"]

    assert application["id"] == app_id
    assert application["company"] == "Acme"
    assert application["date_applied"] == "2026-10-01"     # not an HTTP date string
    assert application["current_stage"] == "applied"
    assert "days_in_stage" in application and "stale" in application


def test_salaries_can_be_sent_as_json_numbers(client):
    app_id = _create(client, salary_range_min=40000, salary_range_max=50000)

    application = client.get(f"/applications/{app_id}").get_json()["application"]

    assert (application["salary_range_min"], application["salary_range_max"]) == (40000, 50000)


def test_invalid_application_returns_all_errors(client):
    response = client.post("/applications", json={**VALID, "company": "", "source": "x"})

    assert response.status_code == 400
    assert response.get_json()["errors"] == ["Company is required.", "Choose a valid source."]


def test_missing_body_is_a_400_not_a_crash(client):
    assert client.post("/applications", data="not json").status_code == 400


def test_detail_has_history_and_allowed_next_stages(client):
    app_id = _create(client)

    body = client.get(f"/applications/{app_id}").get_json()

    assert body["application"]["company"] == "Acme"
    assert [h["stage"] for h in body["history"]] == ["applied"]
    assert "phone_screen" in body["next_stages"] and "accepted" not in body["next_stages"]
    assert body["stage_order"]["applied"] == 1


def test_stage_change_moves_application_forward(client):
    app_id = _create(client)

    response = client.post(f"/applications/{app_id}/stage", json={"stage": "interview"})

    assert response.get_json() == {"ok": True}
    assert client.get(f"/applications/{app_id}").get_json()["application"]["current_stage"] == "interview"


def test_backward_stage_change_is_400_and_changes_nothing(client):
    app_id = _create(client)
    client.post(f"/applications/{app_id}/stage", json={"stage": "interview"})

    response = client.post(f"/applications/{app_id}/stage", json={"stage": "phone_screen"})

    assert response.status_code == 400
    assert "Cannot move backwards" in response.get_json()["error"]
    assert client.get(f"/applications/{app_id}").get_json()["application"]["current_stage"] == "interview"


def test_missing_application_is_404(client):
    assert client.get("/applications/999999").status_code == 404
    response = client.post("/applications/999999/stage", json={"stage": "offer"})
    assert response.status_code == 404
    assert response.get_json() == {"error": "Application not found"}


def test_active_ids_leave_out_closed_applications(client):
    active = _create(client)
    rejected = _create(client, company="Beta")
    client.post(f"/applications/{rejected}/stage", json={"stage": "rejected"})

    assert client.get("/applications/active-ids").get_json() == {"ids": [active]}


def test_conversion_rates_are_grouped_by_source(client):
    app_id = _create(client)
    client.post(f"/applications/{app_id}/stage", json={"stage": "phone_screen"})

    rates = client.get("/applications/conversion-rates").get_json()["rates"]

    first_step = rates["referral"][0]
    assert (first_step["from_stage"], first_step["advanced"], first_step["rate"]) == ("applied", 1, 1.0)

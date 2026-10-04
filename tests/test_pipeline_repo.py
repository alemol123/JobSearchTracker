from datetime import date, datetime

import pytest

from pipeline import repository as repo
from pipeline.logic import InvalidTransition


def _new_app(conn, company="Acme", source="referral", applied=date(2026, 10, 1)):
    return repo.create_application(conn, {
        "company": company,
        "role": "Backend Developer",
        "source": source,
        "date_applied": applied,
        "salary_range_min": 40000,
        "salary_range_max": 50000,
    })


# ---------- create_application ----------

def test_create_application_starts_in_applied_and_active(conn):
    app_id = _new_app(conn)

    app = repo.get_application(conn, app_id)

    assert app["company"] == "Acme"
    assert app["current_stage"] == "applied"
    assert app["status"] == "active"


def test_create_application_writes_first_history_row_on_date_applied(conn):
    app_id = _new_app(conn, applied=date(2026, 9, 15))

    history = repo.get_stage_history(conn, app_id)

    assert [h["stage"] for h in history] == ["applied"]
    assert history[0]["entered_at"] == "2026-09-15T00:00:00"


def test_get_application_returns_none_for_missing_id(conn):
    assert repo.get_application(conn, 999) is None


# ---------- change_stage ----------

def test_change_stage_forward_updates_stage_and_appends_history(conn):
    app_id = _new_app(conn)

    repo.change_stage(conn, app_id, "interview", now=datetime(2026, 10, 5, 9, 30))

    app = repo.get_application(conn, app_id)
    history = repo.get_stage_history(conn, app_id)
    assert app["current_stage"] == "interview"
    assert app["stage_entered_on"] == date(2026, 10, 5)
    assert [h["stage"] for h in history] == ["applied", "interview"]


def test_change_stage_backwards_raises_and_writes_nothing(conn):
    app_id = _new_app(conn)
    repo.change_stage(conn, app_id, "interview", now=datetime(2026, 10, 5))

    with pytest.raises(InvalidTransition):
        repo.change_stage(conn, app_id, "phone_screen", now=datetime(2026, 10, 6))

    assert repo.get_application(conn, app_id)["current_stage"] == "interview"
    assert len(repo.get_stage_history(conn, app_id)) == 2


@pytest.mark.parametrize("terminal", ["rejected", "withdrawn"])
def test_change_stage_to_terminal_sets_status(conn, terminal):
    app_id = _new_app(conn)

    repo.change_stage(conn, app_id, terminal, now=datetime(2026, 10, 5))

    assert repo.get_application(conn, app_id)["status"] == terminal


def test_change_stage_on_missing_application_raises_lookup_error(conn):
    with pytest.raises(LookupError):
        repo.change_stage(conn, 999, "interview")


# ---------- list / active ids / conversion input ----------

def test_list_applications_returns_newest_first(conn):
    _new_app(conn, company="Old", applied=date(2026, 9, 1))
    _new_app(conn, company="New", applied=date(2026, 10, 1))

    companies = [a["company"] for a in repo.list_applications(conn)]

    assert companies == ["New", "Old"]


def test_get_active_application_ids_excludes_closed_applications(conn):
    active_id = _new_app(conn)
    rejected_id = _new_app(conn)
    withdrawn_id = _new_app(conn)
    repo.change_stage(conn, rejected_id, "rejected")
    repo.change_stage(conn, withdrawn_id, "withdrawn")

    assert repo.get_active_application_ids(conn) == {active_id}


def test_get_stage_histories_with_source_lists_stages_in_order(conn):
    first = _new_app(conn, source="referral")
    _new_app(conn, source="job_board")
    repo.change_stage(conn, first, "phone_screen", now=datetime(2026, 10, 2))
    repo.change_stage(conn, first, "rejected", now=datetime(2026, 10, 3))

    histories = repo.get_stage_histories_with_source(conn)

    assert histories == [
        {"source": "referral", "stages": ["applied", "phone_screen", "rejected"]},
        {"source": "job_board", "stages": ["applied"]},
    ]

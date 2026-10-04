from datetime import date

import pytest

from pipeline.logic import (
    InvalidTransition,
    allowed_next_stages,
    conversion_rates_by_source,
    days_in_stage,
    is_stale,
    parse_application_form,
    status_for_stage,
    validate_transition,
)

ACTIVE_STAGES = ["applied", "phone_screen", "technical_assessment",
                 "interview", "final_round", "offer"]


# ---------- validate_transition ----------

def test_move_to_next_stage_is_allowed():
    # Arrange / Act / Assert: no exception means the move is allowed
    validate_transition("applied", "phone_screen")


def test_forward_skip_is_allowed():
    # Not every company uses every stage
    validate_transition("applied", "interview")


def test_backward_move_is_rejected():
    with pytest.raises(InvalidTransition, match="backwards"):
        validate_transition("interview", "phone_screen")


def test_same_stage_is_rejected():
    with pytest.raises(InvalidTransition, match="already"):
        validate_transition("interview", "interview")


@pytest.mark.parametrize("current", ACTIVE_STAGES)
@pytest.mark.parametrize("terminal", ["rejected", "withdrawn"])
def test_any_active_stage_can_move_to_terminal(current, terminal):
    validate_transition(current, terminal)


@pytest.mark.parametrize("current", ["rejected", "withdrawn"])
@pytest.mark.parametrize("new", ["applied", "offer", "rejected", "withdrawn"])
def test_cannot_move_out_of_terminal_stage(current, new):
    with pytest.raises(InvalidTransition, match="closed"):
        validate_transition(current, new)


def test_unknown_stage_is_rejected():
    with pytest.raises(InvalidTransition, match="Unknown stage"):
        validate_transition("applied", "coffee_chat")


# ---------- status_for_stage ----------

@pytest.mark.parametrize("stage", ACTIVE_STAGES)
def test_active_stages_keep_status_active(stage):
    assert status_for_stage(stage) == "active"


@pytest.mark.parametrize("stage", ["rejected", "withdrawn"])
def test_terminal_stage_sets_matching_status(stage):
    assert status_for_stage(stage) == stage


# ---------- days_in_stage ----------

TODAY = date(2026, 10, 20)


def test_days_in_stage_is_zero_on_the_day_it_entered():
    assert days_in_stage(date(2026, 10, 20), TODAY) == 0


def test_days_in_stage_counts_whole_days():
    assert days_in_stage(date(2026, 10, 1), TODAY) == 19


# ---------- is_stale ----------

def test_active_application_past_threshold_is_stale():
    assert is_stale("active", date(2026, 10, 1), TODAY, threshold_days=14) is True


def test_active_application_exactly_at_threshold_is_not_stale():
    assert is_stale("active", date(2026, 10, 6), TODAY, threshold_days=14) is False


def test_recent_active_application_is_not_stale():
    assert is_stale("active", date(2026, 10, 18), TODAY, threshold_days=14) is False


@pytest.mark.parametrize("status", ["rejected", "withdrawn"])
def test_closed_application_is_never_stale(status):
    assert is_stale(status, date(2026, 1, 1), TODAY, threshold_days=14) is False


# ---------- conversion_rates_by_source ----------

def _rate(rows, from_stage):
    """Find the row for one step, e.g. applied -> phone_screen."""
    return next(r for r in rows if r["from_stage"] == from_stage)


def test_conversion_rates_for_one_source():
    # Arrange: max stage reached = applied, phone_screen, interview (skip), phone_screen
    applications = [
        {"source": "referral", "stages": ["applied"]},
        {"source": "referral", "stages": ["applied", "phone_screen"]},
        {"source": "referral", "stages": ["applied", "interview"]},
        {"source": "referral", "stages": ["applied", "phone_screen", "rejected"]},
    ]

    # Act
    rows = conversion_rates_by_source(applications)["referral"]

    # Assert
    first = _rate(rows, "applied")
    assert (first["reached"], first["advanced"], first["rate"]) == (4, 3, 0.75)
    # The skip to interview counts as passing through phone_screen and technical_assessment
    assert _rate(rows, "phone_screen")["rate"] == pytest.approx(1 / 3)
    assert _rate(rows, "technical_assessment")["rate"] == 1.0
    assert _rate(rows, "interview")["rate"] == 0.0
    # Nobody reached final_round, so there is no rate to compute
    assert _rate(rows, "final_round")["rate"] is None


def test_conversion_rates_are_grouped_by_source():
    applications = [
        {"source": "referral", "stages": ["applied", "phone_screen"]},
        {"source": "job_board", "stages": ["applied"]},
        {"source": "job_board", "stages": ["applied"]},
    ]

    result = conversion_rates_by_source(applications)

    assert set(result) == {"referral", "job_board"}
    assert _rate(result["referral"], "applied")["rate"] == 1.0
    assert _rate(result["job_board"], "applied")["rate"] == 0.0


def test_terminal_stages_do_not_count_as_progress():
    applications = [{"source": "cold_apply", "stages": ["applied", "withdrawn"]}]

    rows = conversion_rates_by_source(applications)["cold_apply"]

    assert _rate(rows, "applied")["advanced"] == 0


def test_conversion_rates_with_no_applications():
    assert conversion_rates_by_source([]) == {}


# ---------- parse_application_form ----------

def _form(**overrides):
    form = {
        "company": "Acme",
        "role": "Backend Developer",
        "source": "referral",
        "date_applied": "2026-10-01",
        "salary_range_min": "40000",
        "salary_range_max": "50000",
    }
    form.update(overrides)
    return form


def test_valid_form_is_parsed_into_typed_values():
    data, errors = parse_application_form(_form(company="  Acme  "))

    assert errors == []
    assert data["company"] == "Acme"
    assert data["date_applied"] == date(2026, 10, 1)
    assert (data["salary_range_min"], data["salary_range_max"]) == (40000, 50000)


def test_blank_salaries_become_none():
    data, errors = parse_application_form(_form(salary_range_min="", salary_range_max=""))

    assert errors == []
    assert data["salary_range_min"] is None
    assert data["salary_range_max"] is None


@pytest.mark.parametrize("field, value, message", [
    ("company", "  ", "Company is required"),
    ("role", "", "Role is required"),
    ("source", "linkedin_dm", "valid source"),
    ("date_applied", "yesterday", "Date applied"),
    ("salary_range_min", "40k", "whole number"),
])
def test_invalid_field_reports_an_error(field, value, message):
    _, errors = parse_application_form(_form(**{field: value}))

    assert any(message in e for e in errors)


def test_min_salary_above_max_is_an_error():
    _, errors = parse_application_form(_form(salary_range_min="60000", salary_range_max="50000"))

    assert any("cannot be higher" in e for e in errors)


# ---------- allowed_next_stages ----------

def test_next_stages_from_applied_are_all_later_stages_plus_terminal():
    assert allowed_next_stages("applied") == [
        "phone_screen", "technical_assessment", "interview", "final_round", "offer",
        "rejected", "withdrawn",
    ]


def test_next_stages_from_offer_are_only_terminal():
    assert allowed_next_stages("offer") == ["rejected", "withdrawn"]


def test_closed_application_has_no_next_stages():
    assert allowed_next_stages("rejected") == []

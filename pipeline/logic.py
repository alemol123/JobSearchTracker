"""Pipeline business rules. Pure functions: no Flask, no SQL."""

from datetime import date

SOURCES = ("referral", "job_board", "cold_apply", "other")

# Active stages in the order an application normally moves through them.
STAGE_ORDER = {
    "applied": 1,
    "phone_screen": 2,
    "technical_assessment": 3,
    "interview": 4,
    "final_round": 5,
    "offer": 6,
}

# Reachable from any active stage; once here, the application is closed.
TERMINAL_STAGES = {"rejected", "withdrawn"}


class InvalidTransition(ValueError):
    """Raised when a stage change breaks the pipeline rules."""


def validate_transition(current_stage, new_stage):
    """Raise InvalidTransition if moving current_stage -> new_stage is not allowed."""
    if new_stage not in STAGE_ORDER and new_stage not in TERMINAL_STAGES:
        raise InvalidTransition(f"Unknown stage: {new_stage}")

    if current_stage in TERMINAL_STAGES:
        raise InvalidTransition(f"Application is closed ({current_stage}) and cannot move.")

    if new_stage in TERMINAL_STAGES:
        return  # rejected/withdrawn are allowed from any active stage

    if new_stage == current_stage:
        raise InvalidTransition(f"Application is already in {current_stage}.")

    if STAGE_ORDER[new_stage] < STAGE_ORDER[current_stage]:
        raise InvalidTransition(f"Cannot move backwards from {current_stage} to {new_stage}.")


def allowed_next_stages(current_stage):
    """Every stage validate_transition would accept from here, in pipeline order."""
    allowed = []
    for stage in list(STAGE_ORDER) + sorted(TERMINAL_STAGES):
        try:
            validate_transition(current_stage, stage)
            allowed.append(stage)
        except InvalidTransition:
            pass
    return allowed


def status_for_stage(stage):
    """The applications.status value that goes with a stage."""
    if stage in TERMINAL_STAGES:
        return stage
    return "active"


def days_in_stage(entered_on, today):
    """Whole days since the application entered its current stage (both are dates)."""
    return (today - entered_on).days


def is_stale(status, entered_on, today, threshold_days):
    """An active application with no stage movement for more than threshold_days."""
    if status != "active":
        return False
    return days_in_stage(entered_on, today) > threshold_days


def conversion_rates_by_source(applications):
    """For each source, the share of applications that moved past each active stage.

    applications: list of {"source": str, "stages": [every stage from stage_history]}
    Returns {source: [{"from_stage", "to_stage", "reached", "advanced", "rate"}, ...]}
    """
    # Highest active stage number each application reached, grouped by source.
    # Terminal rows (rejected/withdrawn) are ignored: they are exits, not progress.
    max_reached_by_source = {}
    for app in applications:
        numbers = [STAGE_ORDER[s] for s in app["stages"] if s in STAGE_ORDER]
        max_reached_by_source.setdefault(app["source"], []).append(max(numbers))

    ordered_stages = sorted(STAGE_ORDER, key=STAGE_ORDER.get)
    result = {}
    for source, max_reached in max_reached_by_source.items():
        rows = []
        for from_stage, to_stage in zip(ordered_stages, ordered_stages[1:]):
            # ">=" because skipping a stage still means you got past it.
            reached = sum(1 for m in max_reached if m >= STAGE_ORDER[from_stage])
            advanced = sum(1 for m in max_reached if m >= STAGE_ORDER[to_stage])
            rows.append({
                "from_stage": from_stage,
                "to_stage": to_stage,
                "reached": reached,
                "advanced": advanced,
                "rate": advanced / reached if reached else None,
            })
        result[source] = rows
    return result


def parse_application_form(form):
    """Turn the raw strings from the new-application form into typed values.

    Returns (data, errors). If errors is non-empty, data must not be saved.
    """
    errors = []

    company = form.get("company", "").strip()
    role = form.get("role", "").strip()
    source = form.get("source", "")
    if not company:
        errors.append("Company is required.")
    if not role:
        errors.append("Role is required.")
    if source not in SOURCES:
        errors.append("Choose a valid source.")

    try:
        date_applied = date.fromisoformat(form.get("date_applied", ""))
    except ValueError:
        date_applied = None
        errors.append("Date applied must be a date (YYYY-MM-DD).")

    salary_min = _parse_salary(form.get("salary_range_min", ""), "Minimum salary", errors)
    salary_max = _parse_salary(form.get("salary_range_max", ""), "Maximum salary", errors)
    if salary_min is not None and salary_max is not None and salary_min > salary_max:
        errors.append("Minimum salary cannot be higher than maximum salary.")

    data = {
        "company": company,
        "role": role,
        "source": source,
        "date_applied": date_applied,
        "salary_range_min": salary_min,
        "salary_range_max": salary_max,
    }
    return data, errors


def _parse_salary(text, label, errors):
    """Blank means 'not given' (None); anything else must be a whole number."""
    text = text.strip()
    if not text:
        return None
    if not text.isdigit():
        errors.append(f"{label} must be a whole number.")
        return None
    return int(text)

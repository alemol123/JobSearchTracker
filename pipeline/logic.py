"""Pipeline business rules. Pure functions: no Flask, no SQL."""

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


def status_for_stage(stage):
    """The applications.status value that goes with a stage."""
    if stage in TERMINAL_STAGES:
        return stage
    return "active"

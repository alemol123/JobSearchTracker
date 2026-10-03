import pytest

from pipeline.logic import InvalidTransition, status_for_stage, validate_transition

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

"""State machine tests — Golden Rule #2."""
import pytest
from core.models.return_model import Return


def make_return(status: str) -> Return:
    r = Return()
    r.status = status
    return r


def test_valid_transitions():
    r = make_return("draft")
    r.transition_to("pending")
    assert r.status == "pending"

    r.transition_to("approved")
    assert r.status == "approved"

    r.transition_to("label_generated")
    r.transition_to("in_transit")
    r.transition_to("received")
    r.transition_to("refund_initiated")
    r.transition_to("refunded")
    r.transition_to("closed")
    assert r.status == "closed"


def test_keep_it_path():
    r = make_return("pending")
    r.transition_to("keep_it")
    r.transition_to("refund_initiated")
    r.transition_to("refunded")
    assert r.status == "refunded"


def test_illegal_transition_raises():
    r = make_return("refunded")
    with pytest.raises(ValueError, match="Illegal return transition"):
        r.transition_to("pending")


def test_terminal_state_blocks_all():
    r = make_return("closed")
    with pytest.raises(ValueError):
        r.transition_to("pending")
    with pytest.raises(ValueError):
        r.transition_to("approved")


def test_regression_refunded_to_pending():
    """Golden Rule #2: refunded -> pending must be impossible."""
    r = make_return("refunded")
    with pytest.raises(ValueError):
        r.transition_to("pending")

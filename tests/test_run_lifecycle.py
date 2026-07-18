import pytest

from anthill.run_lifecycle import transition_run_status


@pytest.mark.parametrize(
    "payload, expected",
    [
        ({}, "completed"),
        ({"status": None}, "completed"),
        ({"status": ""}, "completed"),
        ({"status": "banana"}, "completed"),
        ({"status": "completed"}, "completed"),
        ({"status": "success"}, "completed"),
        ({"status": "failed"}, "failed"),
        ({"status": "error"}, "failed"),
        ({"status": "interrupted"}, "interrupted"),
        ({"status": "cancelled"}, "cancelled"),
        ({"status": "canceled"}, "cancelled"),
    ],
)
def test_completed_statuses_normalize_to_the_public_lifecycle(payload, expected):
    assert transition_run_status("running", "run.completed", payload) == expected


@pytest.mark.parametrize(
    "event_type, expected",
    [
        ("run.started", "running"),
        ("run.resumed", "running"),
        ("run.forked", "running"),
        ("run.paused", "paused"),
        ("run.cancelled", "cancelled"),
        ("error.fatal", "failed"),
        ("artifact.created", "unknown"),
    ],
)
def test_explicit_lifecycle_events_are_the_only_status_transitions(event_type, expected):
    assert transition_run_status("unknown", event_type, {}) == expected

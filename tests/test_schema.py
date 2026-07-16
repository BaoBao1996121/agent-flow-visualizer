from datetime import datetime

import pytest
from pydantic import ValidationError

from anthill.schema import (
    AgentRuntimeEvent,
    CoreEventType,
    EventClock,
    EventSource,
    Evidence,
    EvidenceLevel,
    EventLink,
    SourceFidelity,
)


def make_event(**updates) -> AgentRuntimeEvent:
    values = {
        "event_id": "evt-test",
        "event_type": CoreEventType.RUN_STARTED,
        "run_id": "run-test",
        "source": EventSource(
            adapter="tests",
            fidelity=SourceFidelity.NATIVE,
        ),
        "evidence": Evidence(
            level=EvidenceLevel.OBSERVED,
            confidence=1.0,
        ),
    }
    values.update(updates)
    return AgentRuntimeEvent(**values)


def test_core_enum_and_namespaced_extensions_are_supported():
    core = make_event(event_type=CoreEventType.COMPACTION_COMPLETED)
    extension = make_event(event_type="vendor.memory.promoted")

    assert core.event_type == "compaction.completed"
    assert extension.event_type == "vendor.memory.promoted"


@pytest.mark.parametrize("event_type", ["RUN", "run", "run started", ".run"])
def test_event_type_must_be_lowercase_and_namespaced(event_type):
    with pytest.raises(ValidationError):
        make_event(event_type=event_type)


def test_inferred_evidence_cannot_claim_perfect_certainty():
    with pytest.raises(ValidationError, match="cannot have confidence 1.0"):
        Evidence(level=EvidenceLevel.INFERRED, confidence=1.0)


def test_counterfactual_evidence_may_be_certain():
    evidence = Evidence(
        level=EvidenceLevel.COUNTERFACTUAL_VERIFIED,
        confidence=1.0,
    )
    assert evidence.confidence == 1.0


def test_event_timestamps_must_include_a_timezone():
    with pytest.raises(ValidationError, match="timezone-aware"):
        EventClock(occurred_at=datetime(2026, 1, 1))


def test_event_cannot_cause_or_link_to_itself():
    with pytest.raises(ValidationError, match="cause itself"):
        make_event(causation_id="evt-test")

    with pytest.raises(ValidationError, match="target itself"):
        make_event(links=[EventLink(type="related", event_id="evt-test")])


def test_hash_is_stable_for_the_same_canonical_event():
    event = make_event().with_ingest_metadata(
        ingest_seq=0,
        previous_event_hash=None,
    )
    round_tripped = AgentRuntimeEvent.model_validate_json(event.model_dump_json())

    assert event.integrity is not None
    assert event.integrity.event_hash == event.calculate_hash()
    assert round_tripped.calculate_hash() == event.calculate_hash()

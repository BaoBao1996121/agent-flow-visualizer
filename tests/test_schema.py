from datetime import datetime
import json
from pathlib import Path

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


ROOT = Path(__file__).resolve().parents[1]


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


def test_canonical_sample_batch_parses_as_current_runtime_events():
    payload = json.loads(
        (ROOT / "samples" / "canonical_event_batch.json").read_text(encoding="utf-8")
    )

    events = [AgentRuntimeEvent.model_validate(item) for item in payload["events"]]

    assert events
    assert all(event.schema_version == "0.2.0" for event in events)
    assert [event.event_id for event in events] == ["evt-tool-start"]


def test_core_enum_and_namespaced_extensions_are_supported():
    core = make_event(event_type=CoreEventType.COMPACTION_COMPLETED)
    extension = make_event(event_type="vendor.memory.promoted")

    assert core.event_type == "compaction.completed"
    assert extension.event_type == "vendor.memory.promoted"


@pytest.mark.parametrize("event_type", ["RUN", "run", "run started", ".run"])
def test_event_type_must_be_lowercase_and_namespaced(event_type):
    with pytest.raises(ValidationError):
        make_event(event_type=event_type)


@pytest.mark.parametrize("run_id", [" run-test", "run-test ", "   "])
def test_run_id_rejects_leading_or_trailing_whitespace(run_id):
    with pytest.raises(ValidationError, match="leading or trailing whitespace"):
        make_event(run_id=run_id)


@pytest.mark.parametrize("run_id", ["run\nidentity", "run\u202eidentity"])
def test_run_id_rejects_control_and_format_characters(run_id):
    with pytest.raises(ValidationError, match="control or format characters"):
        make_event(run_id=run_id)


@pytest.mark.parametrize(
    "run_id",
    [
        "team/run",
        "team\\run",
        "team?run",
        "team#run",
        "team%run",
        ".",
        "..",
    ],
)
def test_run_id_must_be_addressable_as_one_api_path_segment(run_id):
    with pytest.raises(ValidationError, match="addressable API path segment"):
        make_event(run_id=run_id)


def test_legacy_run_id_is_readable_only_with_explicit_storage_context():
    payload = make_event().model_dump(mode="json")
    payload["schema_version"] = "0.1.0"
    payload["run_id"] = " legacy-run "

    with pytest.raises(ValidationError, match="leading or trailing whitespace"):
        AgentRuntimeEvent.model_validate(payload)

    restored = AgentRuntimeEvent.model_validate(
        payload,
        context={"allow_legacy_run_id": True},
    )

    assert restored.run_id == " legacy-run "
    assert restored.schema_version == "0.1.0"


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

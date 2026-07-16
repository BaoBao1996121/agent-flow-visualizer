from concurrent.futures import ThreadPoolExecutor
import json

import pytest

from anthill.schema import (
    AgentRuntimeEvent,
    EventSource,
    Evidence,
    EvidenceLevel,
    SourceFidelity,
)
from anthill.store import DuplicateEventError, JsonlEventStore


def event(run_id: str, event_id: str, event_type: str = "test.observed"):
    return AgentRuntimeEvent(
        event_id=event_id,
        event_type=event_type,
        run_id=run_id,
        source=EventSource(adapter="tests", fidelity=SourceFidelity.NATIVE),
        evidence=Evidence(level=EvidenceLevel.OBSERVED, confidence=1.0),
    )


def test_append_assigns_contiguous_sequence_and_hash_chain(tmp_path):
    store = JsonlEventStore(tmp_path)
    stored = store.append_many(
        [event("run-1", "evt-1"), event("run-1", "evt-2")]
    )

    assert [item.clock.ingest_seq for item in stored] == [0, 1]
    assert stored[1].integrity.previous_event_hash == stored[0].integrity.event_hash
    assert store.verify_run("run-1")["valid"] is True


def test_duplicate_event_is_rejected_without_partial_batch(tmp_path):
    store = JsonlEventStore(tmp_path)
    store.append(event("run-1", "evt-1"))

    with pytest.raises(DuplicateEventError):
        store.append_many(
            [event("run-1", "evt-2"), event("run-1", "evt-1")]
        )

    assert [item.event_id for item in store.read_run("run-1")] == ["evt-1"]


def test_concurrent_appends_keep_a_single_contiguous_chain(tmp_path):
    store = JsonlEventStore(tmp_path)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(
            pool.map(
                store.append,
                [event("run-1", f"evt-{index}") for index in range(80)],
            )
        )

    events = list(store.read_run("run-1"))
    assert len(events) == 80
    assert [item.clock.ingest_seq for item in events] == list(range(80))
    assert store.verify_run("run-1")["valid"] is True


def test_tampered_payload_breaks_integrity_verification(tmp_path):
    store = JsonlEventStore(tmp_path)
    stored = store.append(event("run-1", "evt-1"))
    ledger = next(tmp_path.glob("*/events.jsonl"))
    payload = json.loads(ledger.read_text(encoding="utf-8"))
    payload["summary"] = "tampered"
    ledger.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    verification = JsonlEventStore(tmp_path).verify_run("run-1")
    assert verification["valid"] is False
    assert any("hash does not match" in item for item in verification["errors"])
    assert stored.event_id == "evt-1"


def test_runs_are_partitioned_and_queryable(tmp_path):
    store = JsonlEventStore(tmp_path)
    store.append(event("run-a", "evt-a", "agent.spawned"))
    store.append(event("run-b", "evt-b", "tool.execution.started"))

    manifests = store.list_runs()
    assert {item["run_id"] for item in manifests} == {"run-a", "run-b"}
    assert [item.event_id for item in store.read_run("run-a")] == ["evt-a"]
    assert [
        item.event_id
        for item in store.read_run("run-b", event_types=["tool.execution.started"])
    ] == ["evt-b"]


def test_manifest_is_reconstructed_from_authoritative_ledger(tmp_path):
    store = JsonlEventStore(tmp_path)
    store.append(event("run-1", "evt-1"))
    manifest_path = next(tmp_path.glob("*/manifest.json"))
    manifest_path.write_text("{broken", encoding="utf-8")

    manifest = JsonlEventStore(tmp_path).get_manifest("run-1")
    assert manifest is not None
    assert manifest["run_id"] == "run-1"
    assert manifest["event_count"] == 1
    assert manifest["last_event_type"] == "test.observed"

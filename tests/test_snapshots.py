import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from anthill.api import EventBroker, create_anthill_router
from anthill.demo import build_demo_events
from anthill.projection_service import WorldProjectionService
from anthill.projections.world import REDUCER_VERSION, WorldState
from anthill.schema import (
    AgentRuntimeEvent,
    EventSource,
    Evidence,
    EvidenceLevel,
    SourceFidelity,
)
from anthill.snapshots import CorruptSnapshotError, JsonWorldSnapshotStore, WorldSnapshot
from anthill.store import JsonlEventStore


def test_world_snapshot_create_inherits_state_reducer_version():
    state = WorldState(run_id="legacy-state", reducer_version="0.3.0")

    snapshot = WorldSnapshot.create(state, event_hash=None)

    assert snapshot.reducer_version == "0.3.0"
    assert snapshot.reducer_version == snapshot.state.reducer_version


def test_snapshot_store_rejects_reducer_version_that_differs_from_state(tmp_path):
    store = JsonWorldSnapshotStore(tmp_path)
    state = WorldState(run_id="mismatched-state")
    snapshot = WorldSnapshot.create(state, event_hash=None).model_copy(
        update={"reducer_version": "0.3.0"}
    )

    with pytest.raises(
        CorruptSnapshotError,
        match="snapshot reducer_version does not match state",
    ):
        store.save(snapshot)


def test_snapshot_accelerates_head_projection_and_never_changes_state(tmp_path):
    event_store = JsonlEventStore(tmp_path / "events")
    snapshot_store = JsonWorldSnapshotStore(tmp_path / "snapshots")
    event_store.append_many(build_demo_events("snapshot-run"))
    service = WorldProjectionService(
        event_store,
        snapshot_store,
        snapshot_interval=10,
    )

    first = service.project("snapshot-run")
    assert first is not None
    assert first.events_replayed == 44
    assert first.snapshot_seq == 43

    second = service.project("snapshot-run")
    assert second is not None
    assert second.events_replayed == 0
    assert second.snapshot_seq == 43
    assert second.state == first.state

    historical = service.project("snapshot-run", at_seq=20)
    assert historical is not None
    assert historical.snapshot_seq is None
    assert historical.events_replayed == 21
    assert historical.state.cursor_seq == 20


def test_corrupt_snapshot_is_ignored_and_ledger_is_replayed(tmp_path):
    event_store = JsonlEventStore(tmp_path / "events")
    snapshot_store = JsonWorldSnapshotStore(tmp_path / "snapshots")
    event_store.append_many(build_demo_events("tamper-run"))
    service = WorldProjectionService(
        event_store,
        snapshot_store,
        snapshot_interval=10,
    )
    original = service.project("tamper-run")
    assert original is not None

    snapshot_path = next((tmp_path / "snapshots").glob("**/*.json"))
    content = json.loads(snapshot_path.read_text(encoding="utf-8"))
    content["state"]["run_status"] = "tampered"
    snapshot_path.write_text(json.dumps(content), encoding="utf-8")

    recovered = service.project("tamper-run")
    assert recovered is not None
    assert recovered.state.run_status == "completed"
    assert recovered.events_replayed == 44
    assert recovered.warnings
    assert "snapshot ignored" in recovered.warnings[0]
    listed = snapshot_store.list_run("tamper-run")
    assert listed[0]["valid"] is False


def test_snapshot_from_wrong_version_directory_is_corrupt_and_falls_back(tmp_path):
    event_store = JsonlEventStore(tmp_path / "events")
    snapshot_store = JsonWorldSnapshotStore(tmp_path / "snapshots")
    event_store.append_many(build_demo_events("wrong-version-run"))
    service = WorldProjectionService(event_store, snapshot_store, snapshot_interval=10)
    original = service.project("wrong-version-run")
    assert original is not None

    snapshot_path = next((tmp_path / "snapshots").glob("**/*.json"))
    anchored = snapshot_store.latest(
        "wrong-version-run", reducer_version=REDUCER_VERSION
    )
    assert anchored is not None
    foreign_state = anchored.state.model_copy(update={"reducer_version": "0.3.0"})
    foreign_snapshot = WorldSnapshot.create(
        foreign_state,
        event_hash=anchored.event_hash,
    )
    snapshot_path.write_text(
        foreign_snapshot.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        CorruptSnapshotError,
        match="snapshot reducer_version does not match requested reducer_version",
    ):
        snapshot_store.latest(
            "wrong-version-run", reducer_version=REDUCER_VERSION
        )

    recovered = service.project("wrong-version-run")
    assert recovered is not None
    assert recovered.state.reducer_version == REDUCER_VERSION
    assert recovered.events_replayed == 44
    assert recovered.warnings
    assert "snapshot ignored" in recovered.warnings[0]
    assert snapshot_store.list_run("wrong-version-run")[0]["valid"] is False


def test_snapshot_api_is_versioned_and_inspectable(tmp_path):
    app = FastAPI()
    app.include_router(create_anthill_router(JsonlEventStore(tmp_path), EventBroker()))
    client = TestClient(app)
    run_id = client.post("/api/anthill/demo").json()["run_id"]

    created = client.post(f"/api/anthill/runs/{run_id}/snapshots")
    assert created.status_code == 201
    assert created.json()["seq"] == 43
    assert created.json()["reducer_version"] == "0.4.0"

    listing = client.get(f"/api/anthill/runs/{run_id}/snapshots")
    assert listing.status_code == 200
    assert listing.json()["count"] == 1
    assert listing.json()["items"][0]["valid"] is True

    world = client.get(f"/api/anthill/runs/{run_id}/world").json()
    assert world["projection"]["snapshot_seq"] == 43
    assert world["projection"]["events_replayed"] == 0


def test_snapshot_resume_preserves_unclassified_measurement_blocking_state(tmp_path):
    run_id = "measurement-snapshot"
    source = EventSource(adapter="tests", fidelity=SourceFidelity.NATIVE)
    evidence = Evidence(level=EvidenceLevel.OBSERVED, confidence=1.0)
    event_store = JsonlEventStore(tmp_path / "events")
    snapshot_store = JsonWorldSnapshotStore(tmp_path / "snapshots")
    service = WorldProjectionService(event_store, snapshot_store, snapshot_interval=1)
    unsafe = AgentRuntimeEvent(
        event_id="unsafe-input-before-snapshot",
        event_type="model.response.chunk",
        run_id=run_id,
        source=source,
        evidence=evidence,
        measurements={"input_tokens": 5},
    )
    unrelated = [
        AgentRuntimeEvent(
            event_id=f"snapshot-unrelated-{index}",
            event_type="model.response.chunk",
            run_id=run_id,
            source=source,
            evidence=evidence,
            measurements={f"unrelated_{index}": index},
        )
        for index in range(100)
    ]
    event_store.append_many([unsafe, *unrelated])

    before = service.project(run_id)
    assert before is not None
    assert before.snapshot_seq == 100
    assert before.state.unclassified_measurement_counts["input_tokens"] == 1
    assert all(
        issue.measurement_key != "input_tokens"
        for issue in before.state.measurement_issues
    )

    semantics = {
        "anthill.measurements": {
            "schema_version": "1.0.0",
            "items": {
                "input_tokens": {
                    "aggregate_key": "model_call.input_tokens",
                    "unit": "tokens",
                    "scope": "model_call",
                    "aggregation": "sum",
                    "temporality": "cumulative",
                    "owner_id": "model-call-after-snapshot",
                }
            },
        }
    }
    event_store.append(
        AgentRuntimeEvent(
            event_id="safe-input-after-snapshot",
            event_type="model.response.completed",
            run_id=run_id,
            source=source,
            evidence=evidence,
            measurements={"input_tokens": 10},
            extensions=semantics,
        )
    )

    resumed = service.project(run_id)
    assert resumed is not None
    assert resumed.events_replayed == 1
    assert resumed.snapshot_seq == 101
    aggregate = resumed.state.measurement_aggregates["model_call.input_tokens"]
    assert aggregate.unclassified_measurement_counts == {"input_tokens": 1}
    assert aggregate.status == "ambiguous"
    assert aggregate.value is None
    assert "input_tokens" not in resumed.state.totals

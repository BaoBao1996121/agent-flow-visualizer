import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from anthill.api import EventBroker, create_anthill_router
from anthill.demo import build_demo_events
from anthill.projection_service import WorldProjectionService
from anthill.snapshots import JsonWorldSnapshotStore
from anthill.store import JsonlEventStore


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


def test_snapshot_api_is_versioned_and_inspectable(tmp_path):
    app = FastAPI()
    app.include_router(create_anthill_router(JsonlEventStore(tmp_path), EventBroker()))
    client = TestClient(app)
    run_id = client.post("/api/anthill/demo").json()["run_id"]

    created = client.post(f"/api/anthill/runs/{run_id}/snapshots")
    assert created.status_code == 201
    assert created.json()["seq"] == 43
    assert created.json()["reducer_version"] == "0.3.0"

    listing = client.get(f"/api/anthill/runs/{run_id}/snapshots")
    assert listing.status_code == 200
    assert listing.json()["count"] == 1
    assert listing.json()["items"][0]["valid"] is True

    world = client.get(f"/api/anthill/runs/{run_id}/world").json()
    assert world["projection"]["snapshot_seq"] == 43
    assert world["projection"]["events_replayed"] == 0

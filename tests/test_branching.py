from fastapi import FastAPI
from fastapi.testclient import TestClient

from anthill.api import EventBroker, create_anthill_router
from anthill.branching import materialize_fork_events
from anthill.demo import build_demo_events
from anthill.projections import project_world
from anthill.schema import SourceFidelity
from anthill.snapshots import calculate_state_hash
from anthill.store import JsonlEventStore


def test_materialized_fork_copies_evidence_without_rerunning_side_effects(tmp_path):
    store = JsonlEventStore(tmp_path)
    parent = store.append_many(build_demo_events("parent-run"))
    prefix = parent[:21]
    parent_state = project_world(prefix, run_id="parent-run")

    fork_events = materialize_fork_events(
        prefix,
        parent_run_id="parent-run",
        new_run_id="branch-run",
        parent_state_hash=calculate_state_hash(parent_state),
        title="Investigate alternative plan",
    )
    branch = store.append_many(fork_events)

    assert len(branch) == 22
    assert branch[0].event_type == "manifest.snapshot"
    assert branch[0].payload["parent_run_id"] == "parent-run"
    assert branch[0].payload["synthetic"] is True
    assert branch[-1].event_type == "run.forked"
    assert branch[-1].payload["side_effects_replayed"] is False
    assert branch[-1].payload["parent_state_hash"] == calculate_state_hash(parent_state)
    assert all(event.run_id == "branch-run" for event in branch)
    assert {event.event_id for event in branch}.isdisjoint(
        {event.event_id for event in prefix}
    )

    copied = next(
        event for event in branch if event.event_type == "model.request.dispatched"
    )
    assert copied.source.fidelity == SourceFidelity.MAPPED
    assert copied.extensions["anthill.branch.origin"]["run_id"] == "parent-run"
    assert any(link.run_id == "parent-run" for link in copied.links)
    assert store.verify_run("branch-run")["valid"] is True

    world = project_world(store.read_run("branch-run"), run_id="branch-run")
    assert world.run_status == "running"
    assert world.event_type_counts["run.forked"] == 1
    assert len(list(store.read_run("parent-run"))) == 44


def test_fork_api_records_parent_cursor_and_rejects_existing_run_id(tmp_path):
    app = FastAPI()
    app.include_router(
        create_anthill_router(JsonlEventStore(tmp_path), EventBroker())
    )
    client = TestClient(app)
    parent = client.post("/api/anthill/demo").json()["run_id"]

    response = client.post(
        f"/api/anthill/runs/{parent}/fork",
        json={
            "at_seq": 20,
            "new_run_id": "branch-api",
            "title": "Branch at handoff",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["run_id"] == "branch-api"
    assert body["parent_seq"] == 20
    assert body["event_count"] == 22
    assert body["side_effects_replayed"] is False

    world = client.get("/api/anthill/runs/branch-api/world").json()["state"]
    assert world["run_status"] == "running"
    assert world["event_type_counts"]["run.forked"] == 1
    runs = client.get("/api/anthill/runs").json()["items"]
    branch_manifest = next(item for item in runs if item["run_id"] == "branch-api")
    assert branch_manifest["title"] == "Branch at handoff"

    duplicate = client.post(
        f"/api/anthill/runs/{parent}/fork",
        json={"at_seq": 20, "new_run_id": "branch-api"},
    )
    assert duplicate.status_code == 409

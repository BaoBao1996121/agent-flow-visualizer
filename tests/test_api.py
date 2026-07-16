import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from anthill.api import EventBroker, create_anthill_router
from anthill.schema import (
    AgentRuntimeEvent,
    EntityRef,
    EventSource,
    Evidence,
    EvidenceLevel,
    SourceFidelity,
)
from anthill.store import JsonlEventStore


AGUI_FIXTURE = Path(__file__).parent / "fixtures" / "agui_events.json"


def runtime_event(event_id, event_type, *, causation_id=None, payload=None):
    return AgentRuntimeEvent(
        event_id=event_id,
        event_type=event_type,
        run_id="api-run",
        causation_id=causation_id,
        subject=EntityRef(kind="agent", id="agent-1", name="Researcher"),
        source=EventSource(adapter="api-test", fidelity=SourceFidelity.NATIVE),
        evidence=Evidence(level=EvidenceLevel.OBSERVED, confidence=1.0),
        payload=payload or {},
    )


def client_for(tmp_path):
    app = FastAPI()
    app.include_router(
        create_anthill_router(JsonlEventStore(tmp_path), EventBroker())
    )
    return TestClient(app)


def test_schema_endpoint_publishes_truth_contract(tmp_path):
    client = client_for(tmp_path)
    response = client.get("/api/anthill/schema")

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "0.1.0"
    assert body["reducer_version"] == "0.1.0"
    assert body["coverage_contract_version"] == "0.1.0"
    assert "anthill.ag-ui" in body["adapter_coverage_contracts"]
    assert "compaction.completed" in body["event_types"]
    assert set(body["evidence_levels"]) == {
        "observed",
        "declared",
        "inferred",
        "counterfactual_verified",
    }


def test_one_click_demo_is_explicitly_synthetic_and_projects_all_core_chambers(tmp_path):
    client = client_for(tmp_path)
    created = client.post("/api/anthill/demo")

    assert created.status_code == 201
    assert created.json()["synthetic"] is True
    run_id = created.json()["run_id"]

    runs = client.get("/api/anthill/runs").json()["items"]
    manifest = next(item for item in runs if item["run_id"] == run_id)
    assert manifest["synthetic"] is True
    assert manifest["source_adapter"] == "anthill.demo.fixture"

    world = client.get(f"/api/anthill/runs/{run_id}/world").json()["state"]
    assert world["run_status"] == "completed"
    assert world["context"]["budget_tokens"] == 8192
    assert world["context"]["used_tokens"] == 3920
    assert world["context"]["overflow"] is False
    assert world["memory"]["hits"] == 1
    assert world["memory"]["semantic"] == 1
    assert world["compactions"]["compact.ctx-1"]["tokens_removed"] == 4540
    assert world["event_type_counts"]["handoff.completed"] == 2
    assert world["event_type_counts"]["tool.execution.failed"] == 1
    assert world["event_type_counts"]["checkpoint.created"] == 1
    assert world["evidence_counts"]["inferred"] == 2
    assert world["zone_activity"] == {}
    assert all(item["status"] == "recovered" for item in world["errors"])


def test_world_visibility_tracks_the_historical_cursor_without_absence_claims(tmp_path):
    client = client_for(tmp_path)
    run_id = client.post("/api/anthill/demo").json()["run_id"]

    historical = client.get(
        f"/api/anthill/runs/{run_id}/world", params={"at_seq": 20}
    ).json()
    head = client.get(f"/api/anthill/runs/{run_id}/world").json()

    historical_domains = {
        row["domain"]: row for row in historical["visibility"]["domains"]
    }
    head_domains = {row["domain"]: row for row in head["visibility"]["domains"]}
    assert historical_domains["tool"]["event_count"] == 1
    assert head_domains["tool"]["event_count"] == 6
    assert historical["visibility"]["score"] is None
    assert head["visibility"]["warnings"]


def test_agui_import_is_metadata_only_and_immediately_projectable(tmp_path):
    client = client_for(tmp_path)
    payload = json.loads(AGUI_FIXTURE.read_text(encoding="utf-8"))

    response = client.post(
        "/api/anthill/import/agui",
        json={"payload": payload, "format": "json"},
    )

    assert response.status_code == 201
    assert response.json()["run_id"] == "agui-run"
    assert response.json()["content_capture"] == "metadata_only"
    events = client.get("/api/anthill/runs/agui-run/events", params={"limit": 100}).json()
    serialized = json.dumps(events)
    assert events["count"] == len(payload["events"])
    assert "SECRET_" not in serialized
    world = client.get("/api/anthill/runs/agui-run/world").json()["state"]
    assert world["run_status"] == "completed"
    assert world["event_type_counts"]["tool.call.requested"] == 1


def test_ingest_query_world_replay_causality_and_integrity(tmp_path):
    client = client_for(tmp_path)
    events = [
        runtime_event("e0", "run.started"),
        runtime_event("e1", "agent.spawned", causation_id="e0"),
        runtime_event(
            "e2",
            "agent.state.changed",
            causation_id="e1",
            payload={"state": "working"},
        ),
        runtime_event(
            "e3",
            "run.completed",
            causation_id="e2",
            payload={"status": "success"},
        ),
    ]
    response = client.post(
        "/api/anthill/runs/api-run/events",
        json={"events": [event.model_dump(mode="json") for event in events]},
    )
    assert response.status_code == 201
    assert response.json()["first_seq"] == 0
    assert response.json()["last_seq"] == 3

    listing = client.get("/api/anthill/runs").json()
    assert listing["total"] == 1
    assert listing["items"][0]["run_id"] == "api-run"

    query = client.get(
        "/api/anthill/runs/api-run/events",
        params={"from_seq": 1, "limit": 2},
    ).json()
    assert [item["event_id"] for item in query["items"]] == ["e1", "e2"]
    assert query["has_more"] is True
    assert query["next_seq"] == 3

    detail = client.get("/api/anthill/runs/api-run/events/e2")
    assert detail.status_code == 200
    assert detail.json()["payload"]["state"] == "working"

    historical = client.get(
        "/api/anthill/runs/api-run/world", params={"at_seq": 2}
    ).json()
    assert historical["state"]["run_status"] == "running"
    assert historical["state"]["entities"]["agent-1"]["status"] == "working"
    assert historical["is_head"] is False

    head = client.get("/api/anthill/runs/api-run/world").json()
    assert head["state"]["run_status"] == "completed"
    assert head["head_seq"] == 3
    assert head["is_head"] is True

    replay = client.get(
        "/api/anthill/runs/api-run/replay",
        params={"from_seq": 2, "to_seq": 3},
    ).json()
    assert replay["initial_state"]["cursor_seq"] == 1
    assert [item["event_id"] for item in replay["events"]] == ["e2", "e3"]
    assert replay["final_state"]["run_status"] == "completed"

    causal = client.get(
        "/api/anthill/runs/api-run/causal/e3",
        params={"direction": "ancestors"},
    ).json()
    assert {node["event_id"] for node in causal["nodes"]} == {
        "e0",
        "e1",
        "e2",
        "e3",
    }

    integrity = client.get("/api/anthill/runs/api-run/integrity").json()
    assert integrity["valid"] is True
    assert integrity["event_count"] == 4


def test_ingest_rejects_run_mismatch_and_duplicate(tmp_path):
    client = client_for(tmp_path)
    event = runtime_event("e0", "run.started")

    mismatch = client.post(
        "/api/anthill/runs/wrong-run/events",
        json={"events": [event.model_dump(mode="json")]},
    )
    assert mismatch.status_code == 422

    first = client.post(
        "/api/anthill/runs/api-run/events",
        json={"events": [event.model_dump(mode="json")]},
    )
    duplicate = client.post(
        "/api/anthill/runs/api-run/events",
        json={"events": [event.model_dump(mode="json")]},
    )
    assert first.status_code == 201
    assert duplicate.status_code == 409


def test_unknown_run_returns_404(tmp_path):
    client = client_for(tmp_path)
    for path in [
        "/api/anthill/runs/missing/events",
        "/api/anthill/runs/missing/world",
        "/api/anthill/runs/missing/replay",
        "/api/anthill/runs/missing/integrity",
    ]:
        assert client.get(path).status_code == 404

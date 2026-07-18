import asyncio
from datetime import datetime
import hashlib
import json
from pathlib import Path
import threading
from urllib.parse import quote

import pytest
from httpx import ASGITransport, AsyncClient

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


OTLP_FIXTURE = Path(__file__).parent / "fixtures" / "otlp_openinference.json"
AGUI_FIXTURE = Path(__file__).parent / "fixtures" / "agui_events.json"
LANGGRAPH_FIXTURE = Path(__file__).parent / "fixtures" / "langgraph_stream_v2.json"


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


def client_for(tmp_path, *, raise_server_exceptions=True):
    app = FastAPI()
    app.include_router(create_anthill_router(JsonlEventStore(tmp_path), EventBroker()))
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


def test_request_validation_errors_do_not_echo_rejected_input(tmp_path):
    client = client_for(tmp_path, raise_server_exceptions=False)
    secret = "SECRET_REJECTED_REQUEST_INPUT"

    response = client.post(
        "/api/anthill/runs/example/events",
        json={"events": secret},
    )

    assert response.status_code == 422
    assert secret not in response.text
    assert response.json()["detail"]


def test_corrupt_ledger_api_error_is_stable_and_privacy_safe(tmp_path):
    client = client_for(tmp_path, raise_server_exceptions=False)
    created = client.post(
        "/api/anthill/runs/api-run/events",
        json={"events": [runtime_event("private-event", "run.started").model_dump(mode="json")]},
    )
    assert created.status_code == 201
    ledger = next(tmp_path.glob("*/events.jsonl"))
    secret = "SECRET_CORRUPT_LEDGER_VALUE"
    ledger.write_text(
        json.dumps({"schema_version": "0.2.0", "secret": secret}) + "\n",
        encoding="utf-8",
    )

    response = client.get("/api/anthill/runs/api-run/events")

    assert response.status_code == 409
    assert response.json() == {
        "detail": "ledger integrity check failed",
        "error_type": "invalid_event",
    }
    assert str(tmp_path) not in response.text
    assert secret not in response.text


def test_schema_endpoint_publishes_truth_contract(tmp_path):
    client = client_for(tmp_path)
    response = client.get("/api/anthill/schema")

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "0.2.0"
    assert body["reducer_version"] == "0.3.0"
    assert body["coverage_contract_version"] == "0.2.0"
    assert "anthill.ag-ui" in body["adapter_coverage_contracts"]
    assert "anthill.langgraph-v2" in body["adapter_coverage_contracts"]
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
    assert client.get(created.json()["world_url"]).status_code == 200
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


def test_run_listing_exposes_privacy_safe_corrupt_ledger_diagnostics(tmp_path):
    client = client_for(tmp_path)
    created = client.post("/api/anthill/demo")
    assert created.status_code == 201
    corrupt_dir = tmp_path / "corrupt-ledger"
    corrupt_dir.mkdir()
    (corrupt_dir / "events.jsonl").write_text("{broken\n", encoding="utf-8")
    opaque_ref = "ledger:" + hashlib.sha256(corrupt_dir.name.encode()).hexdigest()[:24]

    response = client.get("/api/anthill/runs")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["integrity_status"] == "not_checked"
    assert body["integrity_scope"] == "discovery_boundary"
    assert body["discovery_error_count"] == 1
    assert body["diagnostics_truncated"] is False
    assert body["discovery_errors"] == [
        {
            "ledger_ref": opaque_ref,
            "error_type": "invalid_first_event",
        }
    ]
    assert "corrupt_run_count" not in body
    assert "corrupt_runs" not in body


def test_run_listing_caps_discovery_diagnostic_payloads(tmp_path):
    client = client_for(tmp_path)
    for index in range(105):
        corrupt_dir = tmp_path / f"corrupt-{index:03d}"
        corrupt_dir.mkdir()
        (corrupt_dir / "events.jsonl").write_text("{broken\n", encoding="utf-8")

    response = client.get("/api/anthill/runs?limit=1")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["discovery_error_count"] == 105
    assert len(body["discovery_errors"]) == 100
    assert body["diagnostics_truncated"] is True
    assert body["integrity_status"] == "not_checked"


@pytest.mark.parametrize("ledger_state", ["shortened", "empty", "missing"])
@pytest.mark.parametrize("lookup", ["event", "replay", "causal", "compare"])
def test_valid_manifest_anchor_quarantines_damaged_ledgers_on_normal_reads(
    tmp_path,
    ledger_state,
    lookup,
):
    client = client_for(tmp_path, raise_server_exceptions=False)
    run_id = client.post("/api/anthill/demo").json()["run_id"]
    other_run_id = client.post("/api/anthill/demo").json()["run_id"]
    event_id = client.get(
        f"/api/anthill/runs/{run_id}/events",
        params={"limit": 1},
    ).json()["items"][0]["event_id"]
    ledger = next(tmp_path.glob(f"{run_id}-*/events.jsonl"))
    if ledger_state == "shortened":
        lines = ledger.read_bytes().splitlines(keepends=True)
        ledger.write_bytes(b"".join(lines[:-1]))
    elif ledger_state == "empty":
        ledger.write_bytes(b"")
    else:
        ledger.unlink()

    if lookup == "event":
        response = client.get(
            f"/api/anthill/runs/{run_id}/event",
            params={"event_id": event_id},
        )
    elif lookup == "replay":
        response = client.get(f"/api/anthill/runs/{run_id}/replay")
    elif lookup == "causal":
        response = client.get(
            f"/api/anthill/runs/{run_id}/causal",
            params={"event_id": event_id},
        )
    else:
        response = client.get(
            "/api/anthill/compare",
            params={
                "left_run_id": run_id,
                "right_run_id": other_run_id,
            },
        )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "ledger integrity check failed",
        "error_type": "truncated_ledger",
    }


def test_run_listing_folds_lifecycle_status_across_trailing_events(tmp_path):
    client = client_for(tmp_path)

    def observed_event(run_id, event_id, event_type, adapter, payload=None):
        return AgentRuntimeEvent(
            event_id=event_id,
            event_type=event_type,
            run_id=run_id,
            source=EventSource(adapter=adapter, fidelity=SourceFidelity.NATIVE),
            evidence=Evidence(level=EvidenceLevel.OBSERVED, confidence=1.0),
            payload=payload or {},
        )

    runs = {
        "identity-running": (
            "fixture.alpha",
            [
                observed_event(
                    "identity-running",
                    "running-start",
                    "run.started",
                    "fixture.alpha",
                    {"title": "同名任务"},
                ),
                observed_event(
                    "identity-running",
                    "running-agent",
                    "agent.spawned",
                    "fixture.alpha",
                ),
            ],
        ),
        "identity-completed": (
            "fixture.beta",
            [
                observed_event(
                    "identity-completed",
                    "completed-start",
                    "run.started",
                    "fixture.beta",
                    {"title": "同名任务"},
                ),
                observed_event(
                    "identity-completed",
                    "completed-run",
                    "run.completed",
                    "fixture.beta",
                    {"status": "success"},
                ),
                observed_event(
                    "identity-completed",
                    "completed-artifact",
                    "artifact.created",
                    "fixture.beta",
                ),
            ],
        ),
    }
    for run_id, (_, events) in runs.items():
        response = client.post(
            f"/api/anthill/runs/{run_id}/events",
            json={"events": [event.model_dump(mode="json") for event in events]},
        )
        assert response.status_code == 201

    listing = client.get("/api/anthill/runs").json()["items"]
    by_id = {item["run_id"]: item for item in listing}
    assert by_id["identity-running"]["run_status"] == "running"
    assert by_id["identity-completed"]["run_status"] == "completed"
    for run_id, (adapter, _) in runs.items():
        assert by_id[run_id]["title"] == "同名任务"
        assert by_id[run_id]["source_adapter"] == adapter
        created_at = datetime.fromisoformat(by_id[run_id]["created_at"])
        assert created_at.tzinfo is not None
        assert created_at.utcoffset().total_seconds() == 0


def test_terminal_error_alias_is_normalized_consistently_for_listing_and_world(tmp_path):
    client = client_for(tmp_path)
    events = [
        runtime_event("alias-start", "run.started"),
        runtime_event(
            "alias-complete",
            "run.completed",
            causation_id="alias-start",
            payload={"status": "error"},
        ),
    ]

    response = client.post(
        "/api/anthill/runs/api-run/events",
        json={"events": [event.model_dump(mode="json") for event in events]},
    )
    assert response.status_code == 201

    manifest = client.get("/api/anthill/runs").json()["items"][0]
    world = client.get("/api/anthill/runs/api-run/world").json()["state"]
    assert manifest["run_status"] == "failed"
    assert world["run_status"] == "failed"


def test_world_visibility_tracks_the_historical_cursor_without_absence_claims(tmp_path):
    client = client_for(tmp_path)
    run_id = client.post("/api/anthill/demo").json()["run_id"]

    historical = client.get(f"/api/anthill/runs/{run_id}/world", params={"at_seq": 20}).json()
    head = client.get(f"/api/anthill/runs/{run_id}/world").json()

    historical_domains = {row["domain"]: row for row in historical["visibility"]["domains"]}
    head_domains = {row["domain"]: row for row in head["visibility"]["domains"]}
    assert historical_domains["tool"]["event_count"] == 1
    assert head_domains["tool"]["event_count"] == 6
    assert historical["visibility"]["score"] is None
    assert head["visibility"]["warnings"]


def test_otlp_import_rejects_unaddressable_run_id_without_leaking_input(tmp_path):
    client = client_for(tmp_path, raise_server_exceptions=False)
    rejected_run_id = "SECRET/team"
    payload = json.loads(OTLP_FIXTURE.read_text(encoding="utf-8"))

    response = client.post(
        "/api/anthill/import/otlp",
        json={"payload": payload, "run_id": rejected_run_id},
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": [
            {
                "type": "value_error",
                "loc": ["body"],
                "msg": "Request validation failed",
            }
        ]
    }
    assert rejected_run_id not in response.text
    assert client.get("/api/anthill/runs").json()["total"] == 0


def test_otlp_import_returns_an_addressable_encoded_world_url(tmp_path):
    client = client_for(tmp_path)
    run_id = "研究 run 1"
    payload = json.loads(OTLP_FIXTURE.read_text(encoding="utf-8"))

    response = client.post(
        "/api/anthill/import/otlp",
        json={"payload": payload, "run_id": run_id},
    )

    assert response.status_code == 201
    assert response.json()["run_id"] == run_id
    world_url = response.json()["world_url"]
    assert world_url == f"/api/anthill/runs/{quote(run_id, safe='')}/world"
    assert client.get(world_url).status_code == 200


def test_agui_adapter_validation_error_is_a_privacy_safe_422(tmp_path):
    client = client_for(tmp_path, raise_server_exceptions=False)
    rejected_run_id = "SECRET/derived-run"
    payload = json.loads(AGUI_FIXTURE.read_text(encoding="utf-8"))
    for event in payload["events"]:
        if "runId" in event:
            event["runId"] = rejected_run_id

    response = client.post(
        "/api/anthill/import/agui",
        json={"payload": payload, "format": "json"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": [
            {
                "type": "value_error",
                "loc": ["request"],
                "msg": "Request validation failed",
            }
        ]
    }
    assert rejected_run_id not in response.text
    assert client.get("/api/anthill/runs").json()["total"] == 0


def test_agui_explicit_run_id_is_validated_at_the_request_boundary(tmp_path):
    client = client_for(tmp_path, raise_server_exceptions=False)
    rejected_run_id = "SECRET/explicit-run"
    payload = json.loads(AGUI_FIXTURE.read_text(encoding="utf-8"))
    for event in payload["events"]:
        if "runId" in event:
            event["runId"] = rejected_run_id

    response = client.post(
        "/api/anthill/import/agui",
        json={
            "payload": payload,
            "format": "json",
            "run_id": rejected_run_id,
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": [
            {
                "type": "value_error",
                "loc": ["body"],
                "msg": "Request validation failed",
            }
        ]
    }
    assert rejected_run_id not in response.text
    assert client.get("/api/anthill/runs").json()["total"] == 0


def test_agui_derived_run_id_returns_an_addressable_encoded_world_url(tmp_path):
    client = client_for(tmp_path)
    run_id = "协作 run 2"
    payload = json.loads(AGUI_FIXTURE.read_text(encoding="utf-8"))
    for event in payload["events"]:
        if "runId" in event:
            event["runId"] = run_id

    response = client.post(
        "/api/anthill/import/agui",
        json={"payload": payload, "format": "json"},
    )

    assert response.status_code == 201
    assert response.json()["run_id"] == run_id
    world_url = response.json()["world_url"]
    assert world_url == f"/api/anthill/runs/{quote(run_id, safe='')}/world"
    assert client.get(world_url).status_code == 200


@pytest.mark.parametrize(
    ("adapter", "fixture"),
    [
        ("otlp", OTLP_FIXTURE),
        ("agui", AGUI_FIXTURE),
        ("langgraph", LANGGRAPH_FIXTURE),
    ],
)
def test_duplicate_imports_return_one_stable_private_conflict(tmp_path, adapter, fixture):
    client = client_for(tmp_path)
    run_id = f"SECRET-{adapter}-duplicate"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    if adapter == "agui":
        for event in payload["events"]:
            if "runId" in event:
                event["runId"] = run_id
    elif adapter == "langgraph":
        payload["runId"] = run_id
    body = {"payload": payload, "run_id": run_id}

    first = client.post(
        f"/api/anthill/import/{adapter}",
        json=body,
    )
    conflict = client.post(
        f"/api/anthill/import/{adapter}",
        json=body,
    )

    assert first.status_code == 201
    assert conflict.status_code == 409
    assert conflict.json() == {"detail": "event conflict"}
    assert run_id not in conflict.text


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


def test_langgraph_v2_import_is_metadata_only_projectable_and_coverage_aware(tmp_path):
    client = client_for(tmp_path)
    payload = json.loads(LANGGRAPH_FIXTURE.read_text(encoding="utf-8"))

    response = client.post(
        "/api/anthill/import/langgraph",
        json={"payload": payload, "format": "json"},
    )

    assert response.status_code == 201
    assert response.json()["run_id"] == "langgraph-run"
    assert response.json()["stream_version"] == "v2"
    assert response.json()["content_capture"] == "metadata_only"
    events = client.get("/api/anthill/runs/langgraph-run/events", params={"limit": 100}).json()
    assert events["count"] == len(payload["parts"]) + 3
    assert "SECRET_" not in json.dumps(events)
    world = client.get("/api/anthill/runs/langgraph-run/world").json()
    assert world["state"]["run_status"] == "completed"
    assert world["state"]["event_type_counts"]["checkpoint.created"] == 2
    adapter = world["visibility"]["adapters"][0]
    assert adapter["adapter"] == "anthill.langgraph-v2"
    assert adapter["registered"] is True


def test_langgraph_invalid_mode_shape_returns_422_instead_of_server_error(tmp_path):
    client = client_for(tmp_path)
    response = client.post(
        "/api/anthill/import/langgraph",
        json={
            "run_id": "invalid-langgraph",
            "payload": [
                {
                    "type": "tasks",
                    "ns": [],
                    "data": {
                        "id": "task-1",
                        "name": "planner",
                        "input": {},
                        "triggers": 1,
                    },
                }
            ],
        },
    )

    assert response.status_code == 422
    assert "part 0" in response.json()["detail"]


def test_langgraph_oversized_mode_returns_422_instead_of_server_error(tmp_path):
    client = client_for(tmp_path, raise_server_exceptions=False)
    response = client.post(
        "/api/anthill/import/langgraph",
        json={
            "run_id": "invalid-mode",
            "payload": [{"type": "x" * 201, "ns": [], "data": {}}],
        },
    )

    assert response.status_code == 422
    assert "part 0 type" in response.json()["detail"]


def test_langgraph_api_accepts_an_explicit_terminal_run_status(tmp_path):
    client = client_for(tmp_path)
    response = client.post(
        "/api/anthill/import/langgraph",
        json={
            "run_id": "explicit-status",
            "stream_complete": True,
            "run_status": "failed",
            "payload": [{"type": "values", "ns": [], "data": {"phase": "done"}, "interrupts": []}],
        },
    )

    assert response.status_code == 201
    assert response.json()["run_status"] == "failed"
    events = client.get("/api/anthill/runs/explicit-status/events", params={"limit": 100}).json()[
        "items"
    ]
    assert events[-1]["event_type"] == "run.completed"
    assert events[-1]["payload"]["status"] == "failed"


def test_langgraph_long_interrupt_id_is_hashed_instead_of_becoming_a_500(tmp_path):
    client = client_for(tmp_path, raise_server_exceptions=False)
    long_interrupt_id = "interrupt-" + ("x" * 3_000)
    response = client.post(
        "/api/anthill/import/langgraph",
        json={
            "run_id": "long-interrupt-id",
            "payload": [
                {
                    "type": "values",
                    "ns": [],
                    "data": {"phase": "review"},
                    "interrupts": [{"id": long_interrupt_id, "value": "SECRET_REVIEW"}],
                }
            ],
        },
    )

    assert response.status_code == 201
    events_response = client.get(
        "/api/anthill/runs/long-interrupt-id/events", params={"limit": 100}
    )
    assert events_response.status_code == 200
    assert long_interrupt_id not in events_response.text
    interrupt = next(
        event
        for event in events_response.json()["items"]
        if event["event_type"] == "human.interrupt"
    )
    assert interrupt["payload"]["interrupt_id_hashed"] is True
    assert interrupt["payload"]["interrupt_id_chars"] == len(long_interrupt_id)


def test_langgraph_task_interrupt_identifier_is_never_persisted_unbounded(tmp_path):
    client = client_for(tmp_path, raise_server_exceptions=False)
    long_interrupt_id = "INTERRUPT_ID_SECRET_" + ("x" * 3_000)
    response = client.post(
        "/api/anthill/import/langgraph",
        json={
            "run_id": "long-task-interrupt-id",
            "payload": [
                {
                    "type": "tasks",
                    "ns": ["review"],
                    "data": {
                        "id": "task-1",
                        "name": "approval",
                        "error": None,
                        "result": {},
                        "interrupts": [{"id": long_interrupt_id, "value": "SECRET_REVIEW"}],
                    },
                }
            ],
        },
    )

    assert response.status_code == 201
    events_response = client.get(
        "/api/anthill/runs/long-task-interrupt-id/events", params={"limit": 100}
    )
    assert events_response.status_code == 200
    assert long_interrupt_id not in events_response.text
    events = events_response.json()["items"]
    task = next(event for event in events if event["event_type"] == "agent.step.interrupted")
    interrupt = next(event for event in events if event["event_type"] == "human.interrupt")
    assert task["payload"]["interrupt_ids"] == [interrupt["payload"]["interrupt_id"]]


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

    detail = client.get(
        "/api/anthill/runs/api-run/event",
        params={"event_id": "e2"},
    )
    assert detail.status_code == 200
    assert detail.json()["payload"]["state"] == "working"

    historical = client.get("/api/anthill/runs/api-run/world", params={"at_seq": 2}).json()
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
        "/api/anthill/runs/api-run/causal",
        params={"event_id": "e3", "direction": "ancestors"},
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


def test_deprecated_event_path_routes_preserve_url_delimiters_for_compatible_ids(tmp_path):
    client = client_for(tmp_path)
    event_id = "source/event?part#1%raw"
    event = runtime_event(event_id, "run.started")
    created = client.post(
        "/api/anthill/runs/api-run/events",
        json={"events": [event.model_dump(mode="json")]},
    )
    assert created.status_code == 201

    encoded_event_id = quote(event_id, safe="")
    fetched = client.get(
        f"/api/anthill/runs/api-run/events/{encoded_event_id}"
    )
    causal = client.get(
        f"/api/anthill/runs/api-run/causal/{encoded_event_id}"
    )

    assert fetched.status_code == 200
    assert fetched.json()["event_id"] == event_id
    assert causal.status_code == 200
    assert [node["event_id"] for node in causal.json()["nodes"]] == [event_id]


@pytest.mark.parametrize(
    "event_id",
    [".", "..", "source/event?part#1%raw"],
    ids=["dot", "dot-dot", "url-delimiters"],
)
def test_canonical_event_query_routes_address_any_event_id(tmp_path, event_id):
    client = client_for(tmp_path)
    event = runtime_event(event_id, "run.started")
    created = client.post(
        "/api/anthill/runs/api-run/events",
        json={"events": [event.model_dump(mode="json")]},
    )
    assert created.status_code == 201

    fetched = client.get(
        "/api/anthill/runs/api-run/event",
        params={"event_id": event_id},
    )
    causal = client.get(
        "/api/anthill/runs/api-run/causal",
        params={"event_id": event_id},
    )

    assert fetched.status_code == 200
    assert fetched.json()["event_id"] == event_id
    assert causal.status_code == 200
    assert [node["event_id"] for node in causal.json()["nodes"]] == [event_id]


@pytest.mark.parametrize(
    ("suffix", "params"),
    [
        ("/event", {"event_id": "SECRET/missing?part#1%raw"}),
        (
            f"/events/{quote('SECRET/missing?part#1%raw', safe='')}",
            None,
        ),
        ("/causal", {"event_id": "SECRET/missing?part#1%raw"}),
        (
            f"/causal/{quote('SECRET/missing?part#1%raw', safe='')}",
            None,
        ),
    ],
    ids=["event-query", "event-path", "causal-query", "causal-path"],
)
def test_event_lookup_misses_are_stable_and_do_not_reflect_event_id(
    tmp_path,
    suffix,
    params,
):
    client = client_for(tmp_path)
    run_id = client.post("/api/anthill/demo").json()["run_id"]

    response = client.get(
        f"/api/anthill/runs/{run_id}{suffix}",
        params=params,
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "event not found"}
    assert "SECRET" not in response.text


def test_event_query_routes_are_canonical_and_path_routes_are_deprecated(tmp_path):
    client = client_for(tmp_path)

    paths = client.get("/openapi.json").json()["paths"]

    assert paths["/api/anthill/runs/{run_id}/event"]["get"].get("deprecated") is not True
    assert paths["/api/anthill/runs/{run_id}/causal"]["get"].get("deprecated") is not True
    assert (
        paths["/api/anthill/runs/{run_id}/events/{event_id}"]["get"]["deprecated"] is True
    )
    assert (
        paths["/api/anthill/runs/{run_id}/causal/{event_id}"]["get"]["deprecated"] is True
    )


def test_ingest_rejects_run_mismatch_and_duplicate(tmp_path):
    client = client_for(tmp_path)
    event = runtime_event("SECRET_EVENT_IDENTIFIER", "run.started")

    mismatch = client.post(
        "/api/anthill/runs/wrong-run/events",
        json={"events": [event.model_dump(mode="json")]},
    )
    assert mismatch.status_code == 422
    assert mismatch.json() == {"detail": "run_id mismatch"}
    assert event.event_id not in mismatch.text

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
    assert duplicate.json() == {"detail": "event conflict"}
    assert event.event_id not in duplicate.text


def test_unknown_run_returns_404(tmp_path):
    client = client_for(tmp_path)
    for path in [
        "/api/anthill/runs/missing/events",
        "/api/anthill/runs/missing/event?event_id=missing",
        "/api/anthill/runs/missing/world",
        "/api/anthill/runs/missing/replay",
        "/api/anthill/runs/missing/causal?event_id=missing",
        "/api/anthill/runs/missing/integrity",
    ]:
        assert client.get(path).status_code == 404


def test_langgraph_envelope_run_id_must_be_a_string_without_leaking_values(tmp_path):
    client = client_for(tmp_path, raise_server_exceptions=False)
    secret = "SECRET_RUN_ID_VALUE"
    response = client.post(
        "/api/anthill/import/langgraph",
        json={
            "payload": {
                "runId": {"token": secret},
                "parts": [{"type": "values", "ns": [], "data": {}}],
            }
        },
    )

    assert response.status_code == 422
    assert secret not in response.text
    assert secret not in client.get("/api/anthill/runs").text


def test_langgraph_extreme_integer_timestamp_returns_422_without_a_ledger(tmp_path):
    client = client_for(tmp_path, raise_server_exceptions=False)
    body = {
        "run_id": "extreme-timestamp",
        "payload": [
            {
                "type": "values",
                "ns": [],
                "data": {},
                "timestamp": 10**400,
            }
        ],
    }

    response = client.post(
        "/api/anthill/import/langgraph",
        content=json.dumps(body),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert client.get("/api/anthill/runs/extreme-timestamp/integrity").status_code == 404


def test_langgraph_unpaired_unicode_surrogate_run_id_returns_422(tmp_path):
    client = client_for(tmp_path, raise_server_exceptions=False)
    body = {
        "run_id": chr(0xD800),
        "payload": [{"type": "values", "ns": [], "data": {}}],
    }

    response = client.post(
        "/api/anthill/import/langgraph",
        content=json.dumps(body).encode("utf-8"),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert client.get("/api/anthill/runs").json()["total"] == 0


@pytest.mark.parametrize(
    "field",
    ["thread_id", "framework_version", "format", "run_status"],
)
def test_langgraph_unpaired_surrogate_in_request_metadata_returns_422(tmp_path, field):
    client = client_for(tmp_path, raise_server_exceptions=False)
    body = {
        "run_id": "invalid-request-metadata",
        "payload": [{"type": "custom", "ns": [], "data": {}}],
    }
    body[field] = chr(0xD800)

    response = client.post(
        "/api/anthill/import/langgraph",
        content=json.dumps(body).encode("utf-8"),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert client.get("/api/anthill/runs").json()["total"] == 0


@pytest.mark.parametrize(
    ("label", "token_count"),
    [
        ("nan", float("nan")),
        ("positive-infinity", float("inf")),
        ("negative-infinity", float("-inf")),
    ],
)
def test_langgraph_non_finite_usage_is_rejected_without_integrity_damage(
    tmp_path, label, token_count
):
    client = client_for(tmp_path, raise_server_exceptions=False)
    run_id = f"non-finite-{label}"
    body = {
        "run_id": run_id,
        "payload": [
            {
                "type": "messages",
                "ns": [],
                "data": [
                    {
                        "id": "message-1",
                        "type": "ai",
                        "content": "safe",
                        "usage_metadata": {"input_tokens": token_count},
                    },
                    {},
                ],
            }
        ],
    }

    response = client.post(
        "/api/anthill/import/langgraph",
        content=json.dumps(body, allow_nan=True),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert client.get(f"/api/anthill/runs/{run_id}/integrity").status_code == 404


@pytest.mark.parametrize("run_id", ["team/run", "team?run", "team#run"])
def test_langgraph_run_id_rejects_path_and_url_delimiters(tmp_path, run_id):
    client = client_for(tmp_path, raise_server_exceptions=False)

    response = client.post(
        "/api/anthill/import/langgraph",
        json={
            "run_id": run_id,
            "payload": [{"type": "values", "ns": [], "data": {}}],
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]


def test_langgraph_explicit_run_id_uses_the_shared_privacy_safe_contract(tmp_path):
    client = client_for(tmp_path, raise_server_exceptions=False)
    rejected_run_id = "SECRET/langgraph-run"

    response = client.post(
        "/api/anthill/import/langgraph",
        json={
            "run_id": rejected_run_id,
            "payload": [{"type": "values", "ns": [], "data": {}, "interrupts": []}],
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": [
            {
                "type": "value_error",
                "loc": ["body"],
                "msg": "Request validation failed",
            }
        ]
    }
    assert rejected_run_id not in response.text
    assert client.get("/api/anthill/runs").json()["total"] == 0


def test_langgraph_safe_run_id_returns_a_usable_world_url(tmp_path):
    client = client_for(tmp_path)
    response = client.post(
        "/api/anthill/import/langgraph",
        json={
            "run_id": "team.run_1-attempt-2",
            "payload": [{"type": "values", "ns": [], "data": {}, "interrupts": []}],
        },
    )

    assert response.status_code == 201
    assert client.get(response.json()["world_url"]).status_code == 200


@pytest.mark.parametrize(
    "part",
    [
        {"type": chr(0xD800), "ns": [], "data": {}},
        {"type": "values", "ns": [chr(0xD800)], "data": {}},
        {
            "type": "tasks",
            "ns": [],
            "data": {
                "id": chr(0xD800),
                "name": "worker",
                "input": {},
                "triggers": [],
            },
        },
        {
            "type": "messages",
            "ns": [],
            "data": [
                {"id": chr(0xD800), "type": "ai", "content": "safe"},
                {},
            ],
        },
        {
            "type": "checkpoints",
            "ns": [],
            "data": {
                "config": {
                    "configurable": {
                        "checkpoint_id": chr(0xD800),
                        "checkpoint_ns": "safe",
                    }
                },
                "parent_config": None,
                "metadata": {},
                "values": {},
                "next": [],
                "tasks": [],
            },
        },
    ],
    ids=["mode", "namespace", "task-id", "message-id", "checkpoint-id"],
)
def test_langgraph_unpaired_surrogate_in_structural_text_returns_422(tmp_path, part):
    client = client_for(tmp_path, raise_server_exceptions=False)
    body = {"run_id": "invalid-structural-text", "payload": [part]}

    response = client.post(
        "/api/anthill/import/langgraph",
        content=json.dumps(body).encode("utf-8"),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    assert client.get("/api/anthill/runs").json()["total"] == 0


def test_langgraph_checkpoint_next_rejects_objects_without_stringifying_secrets(
    tmp_path,
):
    client = client_for(tmp_path, raise_server_exceptions=False)
    secret = "SECRET_NEXT_NODE_VALUE"
    response = client.post(
        "/api/anthill/import/langgraph",
        json={
            "run_id": "invalid-checkpoint-next",
            "payload": [
                {
                    "type": "checkpoints",
                    "ns": [],
                    "data": {
                        "config": {
                            "configurable": {
                                "checkpoint_id": "checkpoint-1",
                                "checkpoint_ns": "",
                            }
                        },
                        "parent_config": None,
                        "metadata": {},
                        "values": {},
                        "next": [{"token": secret}],
                        "tasks": [],
                    },
                }
            ],
        },
    )

    assert response.status_code == 422
    assert secret not in response.text
    assert secret not in client.get("/api/anthill/runs").text


@pytest.mark.parametrize(
    "part",
    [
        {"type": "tasks", "ns": [], "data": {}},
        {"type": "checkpoints", "ns": [], "data": {}},
        {
            "type": "tasks",
            "ns": [],
            "data": {
                "id": "task-start",
                "name": "worker",
                "input": {},
                "triggers": None,
            },
        },
        {
            "type": "tasks",
            "ns": [],
            "data": {
                "id": "task-result",
                "name": "worker",
                "error": None,
                "interrupts": None,
                "result": {},
            },
        },
        {
            "type": "checkpoints",
            "ns": [],
            "data": {
                "config": None,
                "metadata": {},
                "values": {},
                "next": None,
                "parent_config": None,
                "tasks": [],
            },
        },
        {
            "type": "checkpoints",
            "ns": [],
            "data": {
                "config": None,
                "metadata": {},
                "values": {},
                "next": [],
                "parent_config": None,
                "tasks": None,
            },
        },
    ],
    ids=[
        "empty-task",
        "empty-checkpoint",
        "task-start-null-triggers",
        "task-result-null-interrupts",
        "checkpoint-null-next",
        "checkpoint-null-tasks",
    ],
)
def test_langgraph_required_mode_records_cannot_invent_observed_facts(tmp_path, part):
    client = client_for(tmp_path, raise_server_exceptions=False)

    response = client.post(
        "/api/anthill/import/langgraph",
        json={
            "run_id": "invalid-required-mode-record",
            "payload": [part],
        },
    )

    assert response.status_code == 422
    assert client.get("/api/anthill/runs").json()["total"] == 0


@pytest.mark.parametrize(
    "part",
    [
        {"type": "values", "ns": [], "data": {}, "interrupts": [{}]},
        {"type": "updates", "ns": [], "data": {"__interrupt__": [{}]}},
        {
            "type": "tasks",
            "ns": [],
            "data": {
                "id": "task-result",
                "name": "worker",
                "error": None,
                "result": {},
                "interrupts": [{}],
            },
        },
        {
            "type": "checkpoints",
            "ns": [],
            "data": {
                "config": None,
                "metadata": {},
                "values": {},
                "next": [],
                "parent_config": None,
                "tasks": [
                    {
                        "id": "task-1",
                        "name": "worker",
                        "state": None,
                        "interrupts": [{}],
                    }
                ],
            },
        },
    ],
    ids=["values", "updates", "task-result", "checkpoint-task"],
)
def test_langgraph_empty_interrupt_records_return_422_without_a_ledger(tmp_path, part):
    client = client_for(tmp_path, raise_server_exceptions=False)

    response = client.post(
        "/api/anthill/import/langgraph",
        json={"run_id": "invalid-interrupt-record", "payload": [part]},
    )

    assert response.status_code == 422
    assert client.get("/api/anthill/runs").json()["total"] == 0


def test_langgraph_structured_checkpoint_interrupt_ids_do_not_conflict(tmp_path):
    client = client_for(tmp_path, raise_server_exceptions=False)
    response = client.post(
        "/api/anthill/import/langgraph",
        json={
            "run_id": "checkpoint-interrupt-framing-api",
            "payload": [
                {
                    "type": "checkpoints",
                    "ns": [],
                    "data": {
                        "config": {
                            "configurable": {
                                "checkpoint_id": "checkpoint-1",
                                "checkpoint_ns": "",
                            }
                        },
                        "parent_config": None,
                        "metadata": {},
                        "values": {},
                        "next": [],
                        "tasks": [
                            {
                                "id": "task:a",
                                "name": "first",
                                "state": None,
                                "interrupts": [{"id": "b", "value": "first"}],
                            },
                            {
                                "id": "task",
                                "name": "second",
                                "state": None,
                                "interrupts": [{"id": "a:b", "value": "second"}],
                            },
                        ],
                    },
                }
            ],
        },
    )

    assert response.status_code == 201
    events = client.get(
        "/api/anthill/runs/checkpoint-interrupt-framing-api/events",
        params={"limit": 100},
    ).json()["items"]
    snapshots = [event for event in events if event["event_type"] == "human.interrupt.snapshot"]
    assert len(snapshots) == 2
    assert snapshots[0]["event_id"] != snapshots[1]["event_id"]


def test_langgraph_duplicate_checkpoint_task_ids_return_422_without_a_ledger(tmp_path):
    client = client_for(tmp_path, raise_server_exceptions=False)
    task = {"id": "duplicate", "name": "worker", "state": None, "error": "failed"}
    part = {
        "type": "checkpoints",
        "ns": [],
        "data": {
            "config": None,
            "metadata": {},
            "values": {},
            "next": [],
            "parent_config": None,
            "tasks": [task, {**task, "name": "other"}],
        },
    }

    response = client.post(
        "/api/anthill/import/langgraph",
        json={"run_id": "duplicate-checkpoint-task", "payload": [part]},
    )

    assert response.status_code == 422
    assert client.get("/api/anthill/runs").json()["total"] == 0


def test_langgraph_conflicting_checkpoint_threads_return_422_without_a_ledger(tmp_path):
    client = client_for(tmp_path, raise_server_exceptions=False)

    def checkpoint(checkpoint_id, thread_id):
        return {
            "type": "checkpoints",
            "ns": [],
            "data": {
                "config": {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_id": checkpoint_id,
                        "checkpoint_ns": "",
                    }
                },
                "metadata": {},
                "values": {},
                "next": [],
                "parent_config": None,
                "tasks": [],
            },
        }

    response = client.post(
        "/api/anthill/import/langgraph",
        json={
            "run_id": "conflicting-checkpoint-threads",
            "payload": [
                checkpoint("checkpoint-a", "thread-a"),
                checkpoint("checkpoint-b", "thread-b"),
            ],
        },
    )

    assert response.status_code == 422
    assert client.get("/api/anthill/runs").json()["total"] == 0


@pytest.mark.parametrize(
    "payload",
    [
        "[" * 5_000 + "]" * 5_000,
        '{"type":"custom","ns":[],"data":' + "9" * 5_000 + "}",
    ],
    ids=["deep-nesting", "huge-integer"],
)
def test_langgraph_ndjson_parse_failures_return_422_without_a_ledger(tmp_path, payload):
    client = client_for(tmp_path, raise_server_exceptions=False)

    response = client.post(
        "/api/anthill/import/langgraph",
        json={
            "run_id": "invalid-ndjson-boundary",
            "format": "ndjson",
            "payload": payload,
        },
    )

    assert response.status_code == 422
    assert payload not in response.text
    assert client.get("/api/anthill/runs").json()["total"] == 0


@pytest.mark.parametrize(
    "body",
    [
        {
            "run_id": "forged-timeline",
            "payload": [
                {
                    "type": "tasks",
                    "ns": [],
                    "timestamp": "2000-01-01T00:00:00Z",
                    "data": {"id": "task-1", "name": "worker", "input": {}, "triggers": []},
                }
            ],
        },
        {
            "run_id": "replacement-run",
            "payload": {
                "runId": "source-run",
                "parts": [{"type": "custom", "ns": [], "data": {}}],
            },
        },
    ],
    ids=["non-debug-timestamp", "conflicting-run-id"],
)
def test_langgraph_run_and_timeline_identity_conflicts_return_422_without_a_ledger(tmp_path, body):
    client = client_for(tmp_path, raise_server_exceptions=False)

    response = client.post("/api/anthill/import/langgraph", json=body)

    assert response.status_code == 422


def test_langgraph_values_without_interrupts_returns_422_without_a_ledger(tmp_path):
    client = client_for(tmp_path, raise_server_exceptions=False)

    response = client.post(
        "/api/anthill/import/langgraph",
        json={
            "run_id": "missing-values-interrupts",
            "payload": [{"type": "values", "ns": [], "data": {}}],
        },
    )

    assert response.status_code == 422
    assert client.get("/api/anthill/runs").json()["total"] == 0
    assert client.get("/api/anthill/runs").json()["total"] == 0


def test_fork_new_run_id_is_validated_at_the_request_boundary(tmp_path):
    client = client_for(tmp_path, raise_server_exceptions=False)
    parent_run_id = client.post("/api/anthill/demo").json()["run_id"]
    rejected_run_id = "SECRET/fork-run"

    response = client.post(
        f"/api/anthill/runs/{parent_run_id}/fork",
        json={"at_seq": 2, "new_run_id": rejected_run_id},
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": [
            {
                "type": "value_error",
                "loc": ["body"],
                "msg": "Request validation failed",
            }
        ]
    }
    assert rejected_run_id not in response.text
    listing = client.get("/api/anthill/runs").json()
    assert listing["total"] == 1
    assert listing["items"][0]["run_id"] == parent_run_id


def test_concurrent_forks_with_the_same_run_id_return_a_stable_private_conflict(tmp_path):
    new_run_id = "SECRET-collision-fork"

    class BarrierStore(JsonlEventStore):
        def __init__(self, root):
            super().__init__(root)
            self.collision_barrier = threading.Barrier(2)

        def get_manifest(self, run_id):
            manifest = super().get_manifest(run_id)
            if run_id == new_run_id and manifest is None:
                self.collision_barrier.wait(timeout=3)
            return manifest

    app = FastAPI()
    app.include_router(create_anthill_router(BarrierStore(tmp_path), EventBroker()))

    async def exercise():
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            parent_run_id = (await client.post("/api/anthill/demo")).json()["run_id"]
            return await asyncio.gather(
                *(
                    client.post(
                        f"/api/anthill/runs/{parent_run_id}/fork",
                        json={"at_seq": 2, "new_run_id": new_run_id},
                    )
                    for _ in range(2)
                )
            )

    responses = asyncio.run(exercise())

    assert sorted(response.status_code for response in responses) == [201, 409]
    conflict = next(response for response in responses if response.status_code == 409)
    assert conflict.json() == {"detail": "run already exists"}
    assert new_run_id not in conflict.text


def test_fork_rejects_a_target_created_by_concurrent_direct_ingest(tmp_path):
    new_run_id = "SECRET-direct-ingest-wins"

    class DirectIngestWinsStore(JsonlEventStore):
        def __init__(self, root):
            super().__init__(root)
            self.arm_race = False
            self.fork_saw_empty_target = threading.Event()
            self.direct_ingest_committed = threading.Event()

        def get_manifest(self, run_id):
            manifest = super().get_manifest(run_id)
            if self.arm_race and run_id == new_run_id and manifest is None:
                self.fork_saw_empty_target.set()
                assert self.direct_ingest_committed.wait(timeout=3)
            return manifest

    store = DirectIngestWinsStore(tmp_path)
    app = FastAPI()
    app.include_router(create_anthill_router(store, EventBroker()))

    async def exercise():
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            parent_run_id = (await client.post("/api/anthill/demo")).json()["run_id"]
            store.arm_race = True

            async def fork():
                return await client.post(
                    f"/api/anthill/runs/{parent_run_id}/fork",
                    json={"at_seq": 2, "new_run_id": new_run_id},
                )

            async def ingest_directly():
                assert await asyncio.to_thread(store.fork_saw_empty_target.wait, 3)
                direct_event = runtime_event(
                    "non-overlapping-direct-event",
                    "run.started",
                ).model_copy(update={"run_id": new_run_id})
                try:
                    return await client.post(
                        f"/api/anthill/runs/{new_run_id}/events",
                        json={"events": [direct_event.model_dump(mode="json")]},
                    )
                finally:
                    store.direct_ingest_committed.set()

            fork_response, direct_response = await asyncio.gather(
                fork(),
                ingest_directly(),
            )
            events_response = await client.get(
                f"/api/anthill/runs/{new_run_id}/events",
                params={"limit": 100},
            )
            return fork_response, direct_response, events_response

    fork_response, direct_response, events_response = asyncio.run(exercise())

    assert direct_response.status_code == 201
    assert fork_response.status_code == 409
    assert fork_response.json() == {"detail": "run already exists"}
    assert new_run_id not in fork_response.text
    assert [item["event_id"] for item in events_response.json()["items"]] == [
        "non-overlapping-direct-event"
    ]


def test_direct_ingest_after_fork_starts_after_the_complete_fork_batch(tmp_path):
    client = client_for(tmp_path)
    parent_run_id = client.post("/api/anthill/demo").json()["run_id"]
    new_run_id = "fork-wins-before-direct-ingest"

    fork_response = client.post(
        f"/api/anthill/runs/{parent_run_id}/fork",
        json={"at_seq": 2, "new_run_id": new_run_id},
    )
    assert fork_response.status_code == 201
    fork_event_count = fork_response.json()["event_count"]

    direct_event = runtime_event(
        "direct-event-after-fork",
        "artifact.created",
    ).model_copy(update={"run_id": new_run_id})
    direct_response = client.post(
        f"/api/anthill/runs/{new_run_id}/events",
        json={"events": [direct_event.model_dump(mode="json")]},
    )
    events_response = client.get(
        f"/api/anthill/runs/{new_run_id}/events",
        params={"limit": 100},
    )

    assert direct_response.status_code == 201
    assert direct_response.json()["first_seq"] == fork_event_count
    items = events_response.json()["items"]
    assert len(items) == fork_event_count + 1
    assert items[0]["event_type"] == "manifest.snapshot"
    assert items[fork_event_count - 1]["event_type"] == "run.forked"
    assert items[-1]["event_id"] == "direct-event-after-fork"


@pytest.mark.parametrize(
    "rejected_run_id",
    ["SECRET/run", "SECRET\\run", "SECRET?run", "SECRET#run", "SECRET%2Frun", ".", ".."],
)
def test_direct_ingest_rejects_unaddressable_run_ids_without_leaking_input(
    tmp_path, rejected_run_id
):
    client = client_for(tmp_path, raise_server_exceptions=False)
    payload = runtime_event("invalid-run-id", "run.started").model_dump(mode="json")
    payload["run_id"] = rejected_run_id

    response = client.post(
        "/api/anthill/runs/api-run/events",
        json={"events": [payload]},
    )

    assert response.status_code == 422
    assert response.json()["detail"]
    assert rejected_run_id not in response.text
    assert client.get("/api/anthill/runs").json()["total"] == 0


@pytest.mark.parametrize(
    ("method", "suffix", "json_body"),
    [
        ("get", "/events", None),
        ("post", "/events", {"events": [runtime_event("path-event", "run.started").model_dump(mode="json")]}),
        ("get", "/events/path-event", None),
        ("get", "/event?event_id=path-event", None),
        ("get", "/world", None),
        ("post", "/fork", {}),
        ("post", "/snapshots", None),
        ("get", "/snapshots", None),
        ("get", "/replay", None),
        ("get", "/causal/path-event", None),
        ("get", "/causal?event_id=path-event", None),
        ("get", "/integrity", None),
        ("get", "/stream", None),
    ],
)
def test_every_run_path_rejects_an_unaddressable_segment_without_reflection(
    tmp_path, method, suffix, json_body
):
    client = client_for(tmp_path, raise_server_exceptions=False)
    response = client.request(
        method,
        f"/api/anthill/runs/private%25run{suffix}",
        json=json_body,
    )

    assert response.status_code == 422
    assert "private%run" not in response.text
    assert response.json()["detail"]


def test_compare_query_rejects_an_unaddressable_run_id_without_reflection(tmp_path):
    client = client_for(tmp_path, raise_server_exceptions=False)

    response = client.get(
        "/api/anthill/compare",
        params={"left_run_id": "private/run", "right_run_id": "safe-run"},
    )

    assert response.status_code == 422
    assert "private/run" not in response.text
    assert response.json()["detail"]


def test_fork_returns_an_addressable_encoded_world_url(tmp_path):
    client = client_for(tmp_path)
    parent_run_id = client.post("/api/anthill/demo").json()["run_id"]
    run_id = "分支 run 3"

    response = client.post(
        f"/api/anthill/runs/{parent_run_id}/fork",
        json={"at_seq": 2, "new_run_id": run_id},
    )

    assert response.status_code == 201
    assert response.json()["run_id"] == run_id
    world_url = response.json()["world_url"]
    assert world_url == f"/api/anthill/runs/{quote(run_id, safe='')}/world"
    assert client.get(world_url).status_code == 200


def test_blocking_append_does_not_stall_unrelated_api_requests(tmp_path):
    class BlockingAppendStore(JsonlEventStore):
        def __init__(self, root):
            super().__init__(root)
            self.append_started = threading.Event()
            self.release_append = threading.Event()

        def append_many(self, events):
            self.append_started.set()
            assert self.release_append.wait(2)
            return super().append_many(events)

    store = BlockingAppendStore(tmp_path)
    app = FastAPI()
    app.include_router(create_anthill_router(store, EventBroker()))

    async def exercise():
        transport = ASGITransport(app=app)
        release_timer = threading.Timer(1.5, store.release_append.set)
        release_timer.start()
        try:
            async with AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                create_task = asyncio.create_task(client.post("/api/anthill/demo"))
                assert await asyncio.to_thread(store.append_started.wait, 1)
                heartbeat = await client.get("/api/anthill/schema")
                heartbeat_preceded_release = not store.release_append.is_set()
                store.release_append.set()
                created = await create_task
        finally:
            store.release_append.set()
            release_timer.cancel()
        return heartbeat, created, heartbeat_preceded_release

    heartbeat, created, heartbeat_preceded_release = asyncio.run(exercise())

    assert heartbeat.status_code == 200
    assert created.status_code == 201
    assert heartbeat_preceded_release is True

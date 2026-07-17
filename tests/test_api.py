import json
from pathlib import Path

import pytest

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


def test_schema_endpoint_publishes_truth_contract(tmp_path):
    client = client_for(tmp_path)
    response = client.get("/api/anthill/schema")

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "0.1.0"
    assert body["reducer_version"] == "0.2.0"
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

    historical = client.get(f"/api/anthill/runs/{run_id}/world", params={"at_seq": 20}).json()
    head = client.get(f"/api/anthill/runs/{run_id}/world").json()

    historical_domains = {row["domain"]: row for row in historical["visibility"]["domains"]}
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

    detail = client.get("/api/anthill/runs/api-run/events/e2")
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

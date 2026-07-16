import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from anthill.adapters.otlp import OtlpImportError, otlp_json_to_events
from anthill.api import EventBroker, create_anthill_router
from anthill.projections import project_world
from anthill.schema import ContentCapture, EvidenceLevel, SourceFidelity
from anthill.store import JsonlEventStore


FIXTURE = Path(__file__).parent / "fixtures" / "otlp_openinference.json"


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_otlp_openinference_mapping_preserves_order_truth_and_parent_causality():
    events = otlp_json_to_events(
        load_fixture(),
        run_id="otlp-run",
        semantic_convention_version="openinference-test",
    )

    assert [event.event_type for event in events] == [
        "manifest.snapshot",
        "run.started",
        "agent.step.started",
        "model.request.dispatched",
        "model.response.completed",
        "tool.execution.started",
        "tool.execution.failed",
        "agent.step.completed",
        "run.completed",
    ]
    assert all(event.evidence.level == EvidenceLevel.OBSERVED for event in events)
    assert all(event.source.fidelity == SourceFidelity.MAPPED for event in events)

    agent_start = next(event for event in events if event.event_type == "agent.step.started")
    model_start = next(
        event for event in events if event.event_type == "model.request.dispatched"
    )
    tool_start = next(
        event for event in events if event.event_type == "tool.execution.started"
    )
    assert model_start.causation_id == agent_start.event_id
    assert tool_start.causation_id == agent_start.event_id
    assert tool_start.links[0].trace_id == "22222222222222222222222222222222"
    assert model_start.source.semantic_convention == "openinference"
    assert model_start.source.semantic_convention_version == "openinference-test"


def test_otlp_default_is_metadata_only_and_redacts_content_attributes():
    events = otlp_json_to_events(load_fixture(), run_id="private-otlp")
    serialized = "\n".join(event.model_dump_json() for event in events)

    assert "SECRET_PROMPT_MUST_NOT_PERSIST" not in serialized
    assert "SECRET_OUTPUT_MUST_NOT_PERSIST" not in serialized
    assert "SECRET_ARGUMENT_MUST_NOT_PERSIST" not in serialized
    assert "SECRET_ERROR_MESSAGE_MUST_NOT_PERSIST" not in serialized
    assert all(event.privacy.content == ContentCapture.METADATA_ONLY for event in events)

    model = next(event for event in events if event.event_type == "model.response.completed")
    assert model.measurements["input_tokens"] == 128
    assert model.measurements["output_tokens"] == 42
    assert model.measurements["duration_ms"] == 300
    tool = next(event for event in events if event.event_type == "tool.execution.failed")
    assert tool.payload["error_type"] == "RateLimit"
    assert "gen_ai.tool.call.arguments" in tool.privacy.redacted_fields


def test_otlp_plaintext_capture_requires_explicit_opt_in():
    events = otlp_json_to_events(
        load_fixture(),
        run_id="content-otlp",
        capture_content=True,
    )
    serialized = "\n".join(event.model_dump_json() for event in events)

    assert "SECRET_PROMPT_MUST_NOT_PERSIST" in serialized
    assert "SECRET_ERROR_MESSAGE_MUST_NOT_PERSIST" in serialized
    assert all(
        event.privacy.content == ContentCapture.PLAINTEXT_OPT_IN for event in events
    )


def test_otlp_mapping_is_idempotent_and_projects_into_the_same_world():
    first = otlp_json_to_events(load_fixture(), run_id="stable-run")
    second = otlp_json_to_events(load_fixture(), run_id="stable-run")
    assert [event.event_id for event in first] == [event.event_id for event in second]

    # Projection requires store-assigned ingest sequence; stamp without retaining
    # a repository-local fixture directory.
    previous_hash = None
    stamped = []
    for seq, event in enumerate(first):
        item = event.with_ingest_metadata(
            ingest_seq=seq,
            previous_event_hash=previous_hash,
        )
        previous_hash = item.integrity.event_hash
        stamped.append(item)
    world = project_world(stamped, run_id="stable-run")
    assert world.run_status == "completed"
    assert world.event_type_counts["model.response.completed"] == 1
    assert world.event_type_counts["tool.execution.failed"] == 1
    assert world.source_adapters == {"anthill.otlp-json": 9}


def test_otlp_rejects_payload_without_spans():
    with pytest.raises(OtlpImportError, match="no spans"):
        otlp_json_to_events({"resourceSpans": []}, run_id="empty")


def test_otlp_import_api_persists_and_exposes_world(tmp_path):
    app = FastAPI()
    app.include_router(
        create_anthill_router(JsonlEventStore(tmp_path), EventBroker())
    )
    client = TestClient(app)

    response = client.post(
        "/api/anthill/import/otlp",
        json={
            "run_id": "api-otlp",
            "semantic_convention_version": "1.41.0",
            "payload": load_fixture(),
        },
    )
    assert response.status_code == 201
    assert response.json()["span_count"] == 3
    assert response.json()["event_count"] == 9
    assert response.json()["content_capture"] == "metadata_only"

    world = client.get("/api/anthill/runs/api-otlp/world")
    assert world.status_code == 200
    assert world.json()["state"]["frameworks"] == ["checkout-agent"]
    assert client.get("/api/anthill/runs/api-otlp/integrity").json()["valid"] is True

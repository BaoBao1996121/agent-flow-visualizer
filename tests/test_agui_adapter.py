import json
from pathlib import Path

from anthill.adapters.agui import agui_json_to_events
from anthill.schema import ContentCapture, EvidenceLevel, LinkType, SourceFidelity


FIXTURE = Path(__file__).parent / "fixtures" / "agui_events.json"


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_agui_json_maps_run_lifecycle_lineage_and_source_truth():
    first = agui_json_to_events(load_fixture())
    second = agui_json_to_events(load_fixture())
    lifecycle = [event for event in first if event.event_type.startswith("run.")]

    assert [event.event_type for event in lifecycle] == ["run.started", "run.completed"]
    assert [event.event_id for event in first] == [event.event_id for event in second]
    assert all(event.run_id == "agui-run" for event in first)
    assert all(event.thread_id == "thread-demo" for event in first)
    assert all(event.evidence.level == EvidenceLevel.OBSERVED for event in first)
    assert all(event.source.fidelity == SourceFidelity.MAPPED for event in first)
    assert all(event.source.semantic_convention == "ag-ui" for event in first)
    assert all(event.source.semantic_convention_version == "0.0.42" for event in first)
    assert lifecycle[0].links[0].type == LinkType.DERIVED_FROM
    assert lifecycle[0].links[0].run_id == "parent-run"
    assert lifecycle[1].causation_id == lifecycle[0].event_id
    assert [event.clock.source_seq for event in first] == list(range(len(first)))


def test_agui_default_is_metadata_only_but_keeps_useful_structure():
    events = agui_json_to_events(load_fixture())
    serialized = "\n".join(event.model_dump_json() for event in events)

    assert "SECRET_" not in serialized
    assert all(event.privacy.content == ContentCapture.METADATA_ONLY for event in events)

    message = next(
        event for event in events if event.extensions["agui"]["source_type"] == "TEXT_MESSAGE_CONTENT"
    )
    assert message.payload["delta_chars"] == len("SECRET_MESSAGE")
    assert message.privacy.redacted_fields == ["delta"]

    state = next(
        event for event in events if event.extensions["agui"]["source_type"] == "STATE_SNAPSHOT"
    )
    assert state.payload["snapshot_keys"] == ["phase", "private"]
    assert state.privacy.redacted_fields == ["snapshot"]

    delta = next(
        event for event in events if event.extensions["agui"]["source_type"] == "STATE_DELTA"
    )
    assert delta.payload["patch"] == [{"op": "replace", "path": "/private"}]
    assert delta.privacy.redacted_fields == ["delta[].value"]

    messages = next(
        event for event in events if event.extensions["agui"]["source_type"] == "MESSAGES_SNAPSHOT"
    )
    assert messages.payload["message_count"] == 1
    assert messages.payload["role_counts"] == {"assistant": 1}


def test_agui_maps_protocol_families_without_inventing_implicit_causality():
    events = agui_json_to_events(load_fixture())

    assert [event.event_type for event in events] == [
        "run.started",
        "agent.step.started",
        "context.shared_state.snapshot",
        "agent.activity.snapshot",
        "agent.message.started",
        "agent.message.delta",
        "tool.call.requested",
        "tool.args.delta",
        "tool.call.arguments.completed",
        "tool.execution.succeeded",
        "agent.message.completed",
        "agent.activity.delta",
        "context.shared_state.delta",
        "context.messages.snapshot",
        "agent.reasoning.started",
        "agent.reasoning.summary.started",
        "agent.reasoning.summary.delta",
        "agent.reasoning.summary.completed",
        "agent.reasoning.encrypted.attached",
        "agent.reasoning.completed",
        "agent.step.completed",
        "agui.custom",
        "agui.raw",
        "run.completed",
    ]
    by_source = {event.extensions["agui"]["source_type"]: event for event in events}

    message_start = by_source["TEXT_MESSAGE_START"]
    assert by_source["TEXT_MESSAGE_CONTENT"].causation_id == message_start.event_id
    assert by_source["TEXT_MESSAGE_END"].causation_id == message_start.event_id

    tool_start = by_source["TOOL_CALL_START"]
    assert tool_start.causation_id == message_start.event_id
    assert by_source["TOOL_CALL_ARGS"].causation_id == tool_start.event_id
    assert by_source["TOOL_CALL_END"].causation_id == tool_start.event_id
    assert by_source["TOOL_CALL_RESULT"].causation_id == tool_start.event_id
    assert tool_start.subject.kind == "tool.call"
    assert tool_start.subject.name == "web_search"

    activity = by_source["ACTIVITY_SNAPSHOT"]
    assert by_source["ACTIVITY_DELTA"].causation_id == activity.event_id
    reasoning = by_source["REASONING_MESSAGE_START"]
    assert by_source["REASONING_MESSAGE_CONTENT"].causation_id == reasoning.event_id
    assert by_source["REASONING_MESSAGE_END"].causation_id == reasoning.event_id
    assert by_source["REASONING_ENCRYPTED_VALUE"].causation_id == reasoning.event_id
    assert by_source["REASONING_END"].causation_id == by_source["REASONING_START"].event_id
    assert by_source["STEP_FINISHED"].causation_id == by_source["STEP_STARTED"].event_id

    state_snapshot = by_source["STATE_SNAPSHOT"]
    state_delta = by_source["STATE_DELTA"]
    assert state_delta.causation_id is None
    assert state_delta.correlation_id == state_snapshot.correlation_id


def test_agui_ndjson_is_available_through_the_public_adapter_interface():
    from anthill.adapters import agui_ndjson_to_events

    fixture = load_fixture()
    ndjson = "\n".join(json.dumps(event) for event in fixture["events"])

    events = agui_ndjson_to_events(
        ndjson,
        protocol_version=fixture["protocolVersion"],
    )

    assert len(events) == len(fixture["events"])
    assert events[0].event_type == "run.started"
    assert events[-1].event_type == "run.completed"


def test_agui_run_error_is_fatal_and_plaintext_capture_is_explicit():
    payload = [
        {"type": "RUN_STARTED", "runId": "failed-run", "threadId": "thread-1"},
        {"type": "RUN_ERROR", "message": "SECRET_FAILURE", "code": "E_TOOL"},
    ]

    metadata_events = agui_json_to_events(payload)
    error = metadata_events[-1]
    assert error.event_type == "error.fatal"
    assert error.causation_id == metadata_events[0].event_id
    assert error.payload["status"] == "error"
    assert error.payload["message_chars"] == len("SECRET_FAILURE")
    assert error.privacy.redacted_fields == ["message"]
    assert "SECRET_FAILURE" not in error.model_dump_json()

    plaintext_error = agui_json_to_events(payload, capture_content=True)[-1]
    assert plaintext_error.payload["content"]["message"] == "SECRET_FAILURE"
    assert plaintext_error.privacy.content == ContentCapture.PLAINTEXT_OPT_IN
    assert plaintext_error.privacy.contains_sensitive_data is True


def test_agui_metadata_fields_cannot_smuggle_nested_content_or_freeform_roles():
    payload = [
        {"type": "RUN_STARTED", "runId": "hostile-run"},
        {
            "type": "MESSAGES_SNAPSHOT",
            "messages": [{"role": "SECRET_ROLE", "content": "SECRET_MESSAGE"}],
        },
        {
            "type": "RAW",
            "source": {"provider": "SECRET_SOURCE"},
            "event": {"payload": "SECRET_RAW"},
        },
    ]

    events = agui_json_to_events(payload)
    serialized = "\n".join(event.model_dump_json() for event in events)

    assert "SECRET_" not in serialized
    assert events[1].payload["role_counts"] == {"other": 1}
    assert events[2].payload["source_keys"] == ["provider"]
    assert "source" in events[2].privacy.redacted_fields

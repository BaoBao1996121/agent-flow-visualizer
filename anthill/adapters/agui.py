"""Offline AG-UI JSON/NDJSON normalizer."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ..schema import (
    AgentRuntimeEvent,
    ContentCapture,
    EntityRef,
    EventClock,
    EventLink,
    EventSource,
    Evidence,
    EvidenceLevel,
    EvidenceRef,
    LinkType,
    Privacy,
    SourceFidelity,
    utc_now,
)
from ._common import stable_id


class AguiImportError(ValueError):
    """Raised when an offline AG-UI event stream cannot be normalized."""


def agui_json_to_events(
    payload: dict[str, Any] | list[dict[str, Any]],
    *,
    run_id: str | None = None,
    protocol_version: str | None = None,
    capture_content: bool = False,
) -> list[AgentRuntimeEvent]:
    """Convert one JSON AG-UI run into canonical runtime events."""

    if isinstance(payload, list):
        raw_events = payload
        envelope: dict[str, Any] = {}
    elif isinstance(payload, dict) and isinstance(payload.get("events"), list):
        raw_events = payload["events"]
        envelope = payload
    elif isinstance(payload, dict) and payload.get("type"):
        raw_events = [payload]
        envelope = {}
    else:
        raise AguiImportError("expected an AG-UI event, event array, or events envelope")
    if not raw_events:
        raise AguiImportError("AG-UI payload contains no events")
    source_run_ids = {
        str(item["runId"])
        for item in raw_events
        if isinstance(item, dict) and item.get("runId")
    }
    candidate = run_id or envelope.get("runId")
    if candidate and source_run_ids and source_run_ids != {str(candidate)}:
        raise AguiImportError("run_id conflicts with AG-UI lifecycle events")
    if len(source_run_ids) > 1:
        raise AguiImportError("AG-UI payload contains multiple runId values")
    effective_run_id = str(candidate or next(iter(source_run_ids), ""))
    if not effective_run_id:
        raise AguiImportError("run_id is required when lifecycle events omit runId")
    version = protocol_version or envelope.get("protocolVersion")
    if len(effective_run_id) > 256:
        raise AguiImportError("run_id exceeds the canonical 256-character limit")
    for source_seq, raw in enumerate(raw_events):
        if not isinstance(raw, dict) or not raw.get("type"):
            raise AguiImportError(f"event {source_seq} must be an object with type")

    observed_at = utc_now()
    start_index = _build_start_index(raw_events, effective_run_id)
    result: list[AgentRuntimeEvent] = []
    for source_seq, raw in enumerate(raw_events):
        source_type = str(raw["type"]).upper()
        event_type = _EVENT_TYPES.get(source_type, "agui.event.observed")
        event_id = _event_id(effective_run_id, source_seq, source_type)
        subject = _subject(raw, source_type, effective_run_id, source_seq)
        event_payload, redacted = _event_payload(
            raw, source_type=source_type, capture_content=capture_content
        )
        event_payload.update(_status_payload(raw, source_type))
        known_fields = {"type", "timestamp", *_SAFE_FIELDS, *_CONTENT_FIELDS}
        omitted_fields = sorted(str(field) for field in raw if field not in known_fields)
        if omitted_fields:
            event_payload["unmapped_field_names"] = omitted_fields
        links = []
        if source_type == "RUN_STARTED" and raw.get("parentRunId"):
            links.append(
                EventLink(type=LinkType.DERIVED_FROM, run_id=str(raw["parentRunId"]))
            )
        thread_id = _bounded_identifier(
            raw.get("threadId") or envelope.get("threadId"), "thread_id"
        )
        agent_id = _bounded_identifier(
            raw.get("agentId") or envelope.get("agentId"), "agent_id"
        )
        result.append(
            AgentRuntimeEvent(
                event_id=event_id,
                event_type=event_type,
                run_id=effective_run_id,
                thread_id=thread_id,
                agent_id=agent_id,
                causation_id=_causation_id(
                    raw, source_type, source_seq, effective_run_id, start_index
                ),
                correlation_id=_correlation_id(
                    raw, source_type, effective_run_id
                ),
                links=links,
                clock=EventClock(
                    occurred_at=_timestamp(raw.get("timestamp"), observed_at),
                    observed_at=observed_at,
                    source_seq=source_seq,
                ),
                source=EventSource(
                    adapter="anthill.ag-ui",
                    adapter_version="0.2.0",
                    framework="ag-ui",
                    fidelity=SourceFidelity.MAPPED,
                    semantic_convention="ag-ui",
                    semantic_convention_version=_optional_text(version),
                    raw_event_ref=f"agui://{effective_run_id}/{source_seq}",
                ),
                subject=subject,
                evidence=Evidence(
                    level=EvidenceLevel.OBSERVED,
                    confidence=1.0,
                    refs=[
                        EvidenceRef(
                            kind="protocol_event",
                            uri=f"agui://{effective_run_id}/{source_seq}",
                            label=source_type,
                        )
                    ],
                    explanation="Deterministically mapped from an AG-UI event",
                ),
                summary=_summary(source_type, subject),
                payload=event_payload,
                privacy=Privacy(
                    content=(
                        ContentCapture.PLAINTEXT_OPT_IN
                        if capture_content
                        else ContentCapture.METADATA_ONLY
                    ),
                    contains_sensitive_data=(
                        capture_content
                        and any(field in raw for field in _CONTENT_FIELDS)
                    ),
                    redacted_fields=[] if capture_content else redacted,
                ),
                extensions={
                    "agui": {
                        "source_type": source_type,
                        "format": "json",
                        "protocol_version": version,
                        "source_field_names": sorted(str(field) for field in raw),
                    }
                },
            )
        )
    return result


def agui_ndjson_to_events(
    payload: str,
    *,
    run_id: str | None = None,
    protocol_version: str | None = None,
    capture_content: bool = False,
) -> list[AgentRuntimeEvent]:
    """Convert newline-delimited AG-UI event objects into canonical events."""

    raw_events: list[dict[str, Any]] = []
    for line_number, line in enumerate(payload.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AguiImportError(
                f"invalid AG-UI NDJSON at line {line_number}: {exc.msg}"
            ) from exc
        if not isinstance(item, dict):
            raise AguiImportError(
                f"AG-UI NDJSON line {line_number} must contain an object"
            )
        raw_events.append(item)
    return agui_json_to_events(
        raw_events,
        run_id=run_id,
        protocol_version=protocol_version,
        capture_content=capture_content,
    )


_EVENT_TYPES = {
    "RUN_STARTED": "run.started",
    "RUN_FINISHED": "run.completed",
    "RUN_ERROR": "error.fatal",
    "STEP_STARTED": "agent.step.started",
    "STEP_FINISHED": "agent.step.completed",
    "TEXT_MESSAGE_START": "agent.message.started",
    "TEXT_MESSAGE_CONTENT": "agent.message.delta",
    "TEXT_MESSAGE_END": "agent.message.completed",
    "TEXT_MESSAGE_CHUNK": "agent.message.chunk",
    "TOOL_CALL_START": "tool.call.requested",
    "TOOL_CALL_ARGS": "tool.args.delta",
    "TOOL_CALL_END": "tool.call.arguments.completed",
    "TOOL_CALL_RESULT": "tool.execution.succeeded",
    "STATE_SNAPSHOT": "context.shared_state.snapshot",
    "STATE_DELTA": "context.shared_state.delta",
    "MESSAGES_SNAPSHOT": "context.messages.snapshot",
    "ACTIVITY_SNAPSHOT": "agent.activity.snapshot",
    "ACTIVITY_DELTA": "agent.activity.delta",
    "REASONING_START": "agent.reasoning.started",
    "REASONING_MESSAGE_START": "agent.reasoning.summary.started",
    "REASONING_MESSAGE_CONTENT": "agent.reasoning.summary.delta",
    "REASONING_MESSAGE_END": "agent.reasoning.summary.completed",
    "REASONING_MESSAGE_CHUNK": "agent.reasoning.summary.chunk",
    "REASONING_ENCRYPTED_VALUE": "agent.reasoning.encrypted.attached",
    "REASONING_END": "agent.reasoning.completed",
    "THINKING_START": "agent.reasoning.started",
    "THINKING_TEXT_MESSAGE_START": "agent.reasoning.summary.started",
    "THINKING_TEXT_MESSAGE_CONTENT": "agent.reasoning.summary.delta",
    "THINKING_TEXT_MESSAGE_END": "agent.reasoning.summary.completed",
    "THINKING_END": "agent.reasoning.completed",
    "CUSTOM": "agui.custom",
    "RAW": "agui.raw",
}


def _event_id(run_id: str, source_seq: int, source_type: str) -> str:
    return stable_id("evt", run_id, "agui", source_seq, source_type)


def _build_start_index(
    raw_events: list[dict[str, Any]], run_id: str
) -> dict[tuple[str, str], list[tuple[int, str]]]:
    index: dict[tuple[str, str], list[tuple[int, str]]] = {}
    for source_seq, raw in enumerate(raw_events):
        source_type = str(raw.get("type", "")).upper()
        key = _start_key(raw, source_type, run_id)
        if key is not None:
            index.setdefault(key, []).append(
                (source_seq, _event_id(run_id, source_seq, source_type))
            )
    return index


def _start_key(
    raw: dict[str, Any], source_type: str, run_id: str
) -> tuple[str, str] | None:
    if source_type == "RUN_STARTED":
        return ("run", run_id)
    fields = {
        "STEP_STARTED": ("step", "stepName"),
        "TEXT_MESSAGE_START": ("message", "messageId"),
        "TOOL_CALL_START": ("tool", "toolCallId"),
        "ACTIVITY_SNAPSHOT": ("activity", "messageId"),
        "REASONING_START": ("reasoning", "messageId"),
        "THINKING_START": ("reasoning", "messageId"),
        "REASONING_MESSAGE_START": ("reasoning-message", "messageId"),
        "THINKING_TEXT_MESSAGE_START": ("reasoning-message", "messageId"),
    }
    family_field = fields.get(source_type)
    if family_field is None:
        return None
    family, field = family_field
    value = _logical_identifier(raw.get(field))
    return (family, value) if value else None


def _causation_key(
    raw: dict[str, Any], source_type: str, run_id: str
) -> tuple[str, str] | None:
    if source_type in {"RUN_FINISHED", "RUN_ERROR"}:
        return ("run", run_id)
    fields = {
        "TEXT_MESSAGE_CONTENT": ("message", "messageId"),
        "TEXT_MESSAGE_END": ("message", "messageId"),
        "TOOL_CALL_START": ("message", "parentMessageId"),
        "TOOL_CALL_ARGS": ("tool", "toolCallId"),
        "TOOL_CALL_END": ("tool", "toolCallId"),
        "TOOL_CALL_RESULT": ("tool", "toolCallId"),
        "ACTIVITY_DELTA": ("activity", "messageId"),
        "REASONING_MESSAGE_CONTENT": ("reasoning-message", "messageId"),
        "REASONING_MESSAGE_END": ("reasoning-message", "messageId"),
        "REASONING_ENCRYPTED_VALUE": ("reasoning-message", "entityId"),
        "REASONING_END": ("reasoning", "messageId"),
        "THINKING_TEXT_MESSAGE_CONTENT": ("reasoning-message", "messageId"),
        "THINKING_TEXT_MESSAGE_END": ("reasoning-message", "messageId"),
        "THINKING_END": ("reasoning", "messageId"),
        "STEP_FINISHED": ("step", "stepName"),
    }
    family_field = fields.get(source_type)
    if family_field is None:
        return None
    family, field = family_field
    value = _logical_identifier(raw.get(field))
    return (family, value) if value else None


def _causation_id(
    raw: dict[str, Any],
    source_type: str,
    source_seq: int,
    run_id: str,
    start_index: dict[tuple[str, str], list[tuple[int, str]]],
) -> str | None:
    key = _causation_key(raw, source_type, run_id)
    candidates = start_index.get(key, []) if key is not None else []
    if not candidates:
        return None
    prior = [candidate for candidate in candidates if candidate[0] <= source_seq]
    return (prior[-1] if prior else candidates[0])[1]


def _correlation_id(
    raw: dict[str, Any], source_type: str, run_id: str
) -> str | None:
    if source_type.startswith("STATE_"):
        return stable_id("corr", run_id, "agui", "shared-state")
    if source_type == "MESSAGES_SNAPSHOT":
        return stable_id("corr", run_id, "agui", "messages")
    family_fields = [
        ({"STEP_STARTED", "STEP_FINISHED"}, "step", "stepName"),
        ({"TEXT_MESSAGE_START", "TEXT_MESSAGE_CONTENT", "TEXT_MESSAGE_END", "TEXT_MESSAGE_CHUNK"}, "message", "messageId"),
        ({"TOOL_CALL_START", "TOOL_CALL_ARGS", "TOOL_CALL_END", "TOOL_CALL_RESULT"}, "tool", "toolCallId"),
        ({"ACTIVITY_SNAPSHOT", "ACTIVITY_DELTA"}, "activity", "messageId"),
        ({"REASONING_START", "REASONING_END", "THINKING_START", "THINKING_END"}, "reasoning", "messageId"),
        ({"REASONING_MESSAGE_START", "REASONING_MESSAGE_CONTENT", "REASONING_MESSAGE_END", "REASONING_MESSAGE_CHUNK", "THINKING_TEXT_MESSAGE_START", "THINKING_TEXT_MESSAGE_CONTENT", "THINKING_TEXT_MESSAGE_END"}, "reasoning-message", "messageId"),
        ({"REASONING_ENCRYPTED_VALUE"}, "reasoning-message", "entityId"),
    ]
    for event_types, family, field in family_fields:
        if source_type in event_types:
            value = _logical_identifier(raw.get(field))
            return stable_id("corr", run_id, "agui", family, value) if value else None
    if source_type.startswith("RUN_"):
        return stable_id("corr", run_id, "agui", "run")
    return None


def _subject(
    raw: dict[str, Any], source_type: str, run_id: str, source_seq: int
) -> EntityRef:
    if source_type.startswith("RUN_"):
        return EntityRef(kind="run", id=run_id)
    if source_type.startswith("STEP_"):
        kind, raw_id, name = "agent.step", raw.get("stepName"), raw.get("stepName")
    elif source_type.startswith("TOOL_CALL_"):
        kind, raw_id, name = "tool.call", raw.get("toolCallId"), raw.get("toolCallName")
    elif source_type.startswith("TEXT_MESSAGE_"):
        kind, raw_id, name = "message", raw.get("messageId"), raw.get("role")
    elif source_type in {"STATE_SNAPSHOT", "STATE_DELTA"}:
        kind, raw_id, name = "context.shared_state", "shared-state", "Shared state"
    elif source_type == "MESSAGES_SNAPSHOT":
        kind, raw_id, name = "context.messages", "messages", "Message history"
    elif source_type.startswith("ACTIVITY_"):
        kind, raw_id, name = "agent.activity", raw.get("messageId"), raw.get("activityType")
    elif source_type.startswith(("REASONING_", "THINKING_")):
        kind = "agent.reasoning"
        raw_id = raw.get("messageId") or raw.get("entityId")
        name = raw.get("subtype") or raw.get("role") or "Reasoning signal"
    else:
        kind, raw_id, name = "agui.event", source_seq, raw.get("name") or source_type
    logical_id = _logical_identifier(raw_id) or f"source-seq:{source_seq}"
    entity_id = stable_id("entity", run_id, "agui", kind, logical_id)
    return EntityRef(kind=kind, id=entity_id, name=_bounded_name(name))


def _status_payload(raw: dict[str, Any], source_type: str) -> dict[str, Any]:
    statuses = {
        "RUN_STARTED": "running",
        "RUN_ERROR": "error",
        "STEP_STARTED": "running",
        "STEP_FINISHED": "completed",
        "TEXT_MESSAGE_START": "streaming",
        "TEXT_MESSAGE_CONTENT": "streaming",
        "TEXT_MESSAGE_END": "completed",
        "TOOL_CALL_START": "requested",
        "TOOL_CALL_ARGS": "arguments_streaming",
        "TOOL_CALL_END": "arguments_completed",
        "TOOL_CALL_RESULT": "succeeded",
        "REASONING_START": "running",
        "REASONING_END": "completed",
        "THINKING_START": "running",
        "THINKING_END": "completed",
    }
    if source_type == "RUN_FINISHED":
        outcome = raw.get("outcome")
        outcome_type = outcome.get("type") if isinstance(outcome, dict) else None
        status = "interrupted" if outcome_type == "interrupt" else "success"
        return {"status": status, **({"outcome_type": outcome_type} if outcome_type else {})}
    return {"status": statuses[source_type]} if source_type in statuses else {}


def _summary(source_type: str, subject: EntityRef) -> str:
    label = source_type.lower().replace("_", " ")
    return f"AG-UI {label}: {subject.name or subject.kind}"


def _logical_identifier(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _bounded_identifier(value: Any, field: str) -> str | None:
    text = _optional_text(value)
    if text is not None and len(text) > 256:
        raise AguiImportError(f"{field} exceeds the canonical 256-character limit")
    return text


def _bounded_name(value: Any) -> str | None:
    text = _optional_text(value)
    return text[:240] if text else None


_SAFE_FIELDS = {
    "threadId": "source_thread_id",
    "runId": "source_run_id",
    "parentRunId": "parent_run_id",
    "messageId": "message_id",
    "toolCallId": "tool_call_id",
    "toolCallName": "tool_name",
    "parentMessageId": "parent_message_id",
    "role": "role",
    "stepName": "step_name",
    "code": "error_code",
    "activityType": "activity_type",
    "replace": "replace",
    "subtype": "subtype",
    "entityId": "entity_id",
    "source": "source",
    "name": "name",
}
_CONTENT_FIELDS = {
    "input",
    "result",
    "outcome",
    "message",
    "delta",
    "snapshot",
    "messages",
    "content",
    "patch",
    "value",
    "event",
    "rawEvent",
    "encryptedValue",
}
_AGUI_ROLES = {"developer", "system", "assistant", "user", "tool", "reasoning"}
_JSON_PATCH_OPS = {"add", "remove", "replace", "move", "copy", "test"}


def _event_payload(
    raw: dict[str, Any], *, source_type: str, capture_content: bool
) -> tuple[dict[str, Any], list[str]]:
    payload: dict[str, Any] = {}
    redacted: list[str] = []
    for source, target in _SAFE_FIELDS.items():
        if source not in raw or raw[source] is None:
            continue
        value = raw[source]
        if source == "role":
            role = value if isinstance(value, str) and value in _AGUI_ROLES else "other"
            payload[target] = role
            if role == "other":
                redacted.append(source)
        elif isinstance(value, str):
            if len(value) <= 512:
                payload[target] = value
            else:
                payload[f"{target}_chars"] = len(value)
                redacted.append(source)
        elif isinstance(value, (bool, int, float)):
            payload[target] = value
        elif isinstance(value, dict):
            payload[f"{target}_keys"] = sorted(str(key) for key in value)
            redacted.append(source)
        elif isinstance(value, list):
            payload[f"{target}_count"] = len(value)
            redacted.append(source)
        else:
            redacted.append(source)
    captured: dict[str, Any] = {}
    for field in _CONTENT_FIELDS:
        if field not in raw:
            continue
        value = raw[field]
        if capture_content:
            captured[field] = value
            continue
        if field in {"delta", "patch"} and isinstance(value, list):
            safe_patch, patch_redacted = _safe_patch(value, field)
            payload["patch"] = safe_patch
            redacted.extend(patch_redacted)
        elif field == "messages" and isinstance(value, list):
            payload["message_count"] = len(value)
            roles: dict[str, int] = {}
            for message in value:
                candidate = message.get("role") if isinstance(message, dict) else None
                role = candidate if candidate in _AGUI_ROLES else "other"
                roles[role] = roles.get(role, 0) + 1
            payload["role_counts"] = roles
            redacted.append("messages")
        elif isinstance(value, str):
            payload[f"{_snake(field)}_chars"] = len(value)
            redacted.append(field)
        elif isinstance(value, dict):
            payload[f"{_snake(field)}_keys"] = sorted(str(key) for key in value)
            redacted.append(field)
        elif isinstance(value, list):
            payload[f"{_snake(field)}_count"] = len(value)
            redacted.append(field)
        else:
            redacted.append(field)
    if captured:
        payload["content"] = captured
    return payload, sorted(set(redacted))


def _safe_patch(value: list[Any], field: str) -> tuple[list[dict[str, Any]], list[str]]:
    safe: list[dict[str, Any]] = []
    redacted: list[str] = []
    for operation in value:
        if not isinstance(operation, dict):
            redacted.append(f"{field}[]")
            continue
        safe_operation: dict[str, Any] = {}
        for key in ("op", "path", "from"):
            item = operation.get(key)
            if not isinstance(item, str):
                if key in operation:
                    redacted.append(f"{field}[].{key}")
                continue
            if key == "op" and item not in _JSON_PATCH_OPS:
                safe_operation[key] = "other"
                redacted.append(f"{field}[].op")
            elif len(item) <= 512:
                safe_operation[key] = item
            else:
                redacted.append(f"{field}[].{key}")
        safe.append(safe_operation)
        if "value" in operation:
            redacted.append(f"{field}[].value")
    return safe, redacted


def _snake(value: str) -> str:
    return "".join(f"_{char.lower()}" if char.isupper() else char for char in value).lstrip("_")


def _timestamp(value: Any, fallback: datetime) -> datetime:
    if value is None:
        return fallback
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AguiImportError("AG-UI timestamp must be a Unix number")
    seconds = float(value) / 1000 if abs(float(value)) >= 100_000_000_000 else float(value)
    try:
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    except (OverflowError, OSError, ValueError) as exc:
        raise AguiImportError("AG-UI timestamp is outside the supported range") from exc


def _optional_text(value: Any) -> str | None:
    return str(value) if value is not None and str(value) else None

"""LangGraph >=1.1 unified StreamPart v2 normalizer.

The module intentionally has no LangGraph import. It accepts JSON-compatible
StreamPart records or the equivalent runtime objects after their message values
have been converted through ``model_dump``.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from math import isfinite
from typing import Any

from ..measurements import (
    MeasurementSemantics,
    measurement_semantics_extension,
)
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


class LangGraphImportError(ValueError):
    """Raised when data is not a LangGraph unified StreamPart v2 stream."""


_MAX_STREAM_MODE_LENGTH = 160
_MAX_SOURCE_IDENTIFIER_LENGTH = 256
_MAX_NDJSON_NESTING = 256
_RESERVED_ID_SEPARATOR = "\x1f"
_RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._~-]{0,255}")
_RUN_STATUSES = frozenset({"completed", "success", "failed", "interrupted", "cancelled"})
_KNOWN_NON_DEBUG_STREAM_MODES = frozenset(
    {"tasks", "messages", "updates", "values", "checkpoints", "custom"}
)
_CHECKPOINT_SOURCES = frozenset({"input", "loop", "update", "fork"})


def langgraph_v2_to_events(
    payload: dict[str, Any] | list[dict[str, Any]],
    *,
    run_id: str | None = None,
    thread_id: str | None = None,
    framework_version: str | None = None,
    stream_complete: bool | None = None,
    run_status: str | None = None,
    capture_content: bool = False,
) -> list[AgentRuntimeEvent]:
    """Normalize one LangGraph StreamPart v2 run into canonical events."""

    if isinstance(payload, dict) and isinstance(payload.get("parts"), list):
        envelope = payload
        raw_parts = payload["parts"]
    elif isinstance(payload, dict) and "type" in payload:
        envelope = {}
        raw_parts = [payload]
    elif isinstance(payload, list):
        envelope = {}
        raw_parts = payload
    else:
        raise LangGraphImportError("expected a StreamPart v2 object, array, or parts envelope")
    if not raw_parts:
        raise LangGraphImportError("LangGraph stream contains no parts")
    for index, part in enumerate(raw_parts):
        if not isinstance(part, dict):
            raise LangGraphImportError(
                f"part {index} is not a StreamPart v2 object; legacy mode tuples are unsupported"
            )
        raw_type = part.get("type")
        if not isinstance(raw_type, str) or not raw_type:
            raise LangGraphImportError(f"part {index} type must be a non-empty string")
        if len(raw_type) > _MAX_STREAM_MODE_LENGTH:
            raise LangGraphImportError(
                f"part {index} type exceeds {_MAX_STREAM_MODE_LENGTH} characters"
            )
        _validate_identity_component(raw_type, f"part {index} type")
        if raw_type in _KNOWN_NON_DEBUG_STREAM_MODES and "timestamp" in part:
            raise LangGraphImportError(f"part {index} timestamp is only valid inside debug.data")
        if "data" not in part or "ns" not in part:
            raise LangGraphImportError(
                f"part {index} must use StreamPart v2 fields: type, ns, data"
            )
        if not isinstance(part["ns"], (list, tuple)):
            raise LangGraphImportError(f"part {index} ns must be an array")
        if raw_type == "debug":
            _validate_debug_wrapper(part, index)
        _validate_part_shape(_normalize_debug_part(part), index)

    version = str(envelope.get("streamVersion") or "v2")
    if version != "v2":
        raise LangGraphImportError("only LangGraph StreamPart v2 is supported")
    envelope_run_id = envelope.get("runId")
    if run_id is not None and envelope_run_id is not None:
        requested_run_id = _run_identifier(run_id)
        captured_run_id = _run_identifier(envelope_run_id)
        if requested_run_id != captured_run_id:
            raise LangGraphImportError(
                "conflicting run_id values were supplied by the request and envelope"
            )
    run_id_value = run_id if run_id is not None else envelope.get("runId")
    if run_id_value is None:
        raise LangGraphImportError("run_id is required when the envelope omits runId")
    effective_run_id = _run_identifier(run_id_value)
    thread_ids: set[str] = set()
    declared_thread_values = (thread_id, envelope.get("threadId"))
    for value in (*declared_thread_values, *_checkpoint_thread_ids(raw_parts)):
        if value is None:
            continue
        validated = _bounded_identifier(value, "thread_id")
        if validated is not None:
            thread_ids.add(validated)
    if len(thread_ids) > 1:
        raise LangGraphImportError(
            "conflicting thread_id values were supplied by the request, envelope, or checkpoints"
        )
    effective_thread_id = next(iter(thread_ids), None)
    effective_framework_version = _bounded_text(
        framework_version or envelope.get("frameworkVersion"), 64
    )
    complete_value = envelope.get("complete", False) if stream_complete is None else stream_complete
    if not isinstance(complete_value, bool):
        raise LangGraphImportError("stream_complete must be boolean")
    effective_run_status = envelope.get("runStatus") if run_status is None else run_status
    if effective_run_status is not None:
        if not isinstance(effective_run_status, str) or effective_run_status not in _RUN_STATUSES:
            allowed = ", ".join(sorted(_RUN_STATUSES))
            raise LangGraphImportError(f"run_status must be one of: {allowed}")
        if not complete_value:
            raise LangGraphImportError("run_status requires an explicitly complete stream")

    observed_at = utc_now()
    task_starts, checkpoints = _index_explicit_starts(raw_parts, effective_run_id)
    source = _source(
        effective_run_id,
        raw_ref=f"langgraph://{effective_run_id}/stream",
        framework_version=effective_framework_version,
    )
    boundary_privacy = Privacy(
        content=ContentCapture.METADATA_ONLY,
        contains_sensitive_data=True,
    )
    manifest_id = stable_id("evt", effective_run_id, "langgraph", "manifest")
    start_id = stable_id("evt", effective_run_id, "langgraph", "run.started")
    modes = sorted({str(part.get("type")) for part in raw_parts})
    title = _bounded_text(envelope.get("title"), 240) or "LangGraph StreamPart v2 run"
    common = {
        "run_id": effective_run_id,
        "thread_id": effective_thread_id,
        "source": source,
        "privacy": boundary_privacy,
    }
    events = [
        AgentRuntimeEvent(
            event_id=manifest_id,
            event_type="manifest.snapshot",
            clock=EventClock(observed_at=observed_at, source_seq=0),
            subject=EntityRef(kind="run", id=effective_run_id),
            evidence=Evidence(
                level=EvidenceLevel.OBSERVED,
                confidence=1.0,
                explanation="Observed the imported LangGraph StreamPart collection",
            ),
            summary=f"Imported {len(raw_parts)} LangGraph v2 stream parts",
            payload={
                "title": title,
                "synthetic": False,
                "part_count": len(raw_parts),
                "stream_modes": modes,
                "stream_complete": complete_value,
                "run_status": effective_run_status,
            },
            **common,
        ),
        AgentRuntimeEvent(
            event_id=start_id,
            event_type="run.started",
            clock=EventClock(observed_at=observed_at, source_seq=1),
            subject=EntityRef(kind="run", id=effective_run_id),
            evidence=Evidence(
                level=EvidenceLevel.INFERRED,
                confidence=0.9,
                explanation=(
                    "Inferred that a run was active because at least one StreamPart was captured; "
                    "LangGraph v2 emits no native run-start part"
                ),
            ),
            summary="LangGraph run activity inferred from captured stream parts",
            payload={"status": "running", "part_count": len(raw_parts)},
            **common,
        ),
    ]

    interrupt_observations: dict[tuple[tuple[str, ...], str], str] = {}
    for index, raw_part in enumerate(raw_parts):
        normalized = _normalize_debug_part(raw_part)
        events.extend(
            _part_to_events(
                normalized,
                original_type=str(raw_part["type"]),
                source_index=index,
                source_seq=len(events),
                run_id=effective_run_id,
                thread_id=effective_thread_id,
                framework_version=effective_framework_version,
                observed_at=observed_at,
                task_starts=task_starts,
                checkpoints=checkpoints,
                interrupt_observations=interrupt_observations,
                capture_content=capture_content,
            )
        )

    if complete_value:
        terminal_status = effective_run_status or "completed"
        events.append(
            AgentRuntimeEvent(
                event_id=stable_id("evt", effective_run_id, "langgraph", "run.completed"),
                event_type="run.completed",
                run_id=effective_run_id,
                thread_id=effective_thread_id,
                clock=EventClock(observed_at=observed_at, source_seq=len(events)),
                source=source,
                subject=EntityRef(kind="run", id=effective_run_id),
                evidence=Evidence(
                    level=EvidenceLevel.DECLARED,
                    confidence=1.0,
                    explanation=(
                        "Caller or import envelope explicitly declared the captured run terminal; "
                        "the outcome is preserved only when runStatus/run_status is explicit"
                    ),
                ),
                summary=f"LangGraph stream declared terminal: {terminal_status}",
                payload={"status": terminal_status, "part_count": len(raw_parts)},
                privacy=boundary_privacy,
            )
        )
    return events


def langgraph_ndjson_to_events(
    payload: str,
    *,
    run_id: str,
    thread_id: str | None = None,
    framework_version: str | None = None,
    stream_complete: bool = False,
    run_status: str | None = None,
    capture_content: bool = False,
) -> list[AgentRuntimeEvent]:
    parts: list[dict[str, Any]] = []
    for line_number, line in enumerate(payload.splitlines(), start=1):
        if not line.strip():
            continue
        _reject_excessive_json_nesting(line)
        try:
            part = json.loads(line)
        except json.JSONDecodeError as exc:
            raise LangGraphImportError(
                f"invalid LangGraph NDJSON at line {line_number}: {exc.msg}"
            ) from exc
        except RecursionError as exc:
            raise LangGraphImportError("LangGraph NDJSON is excessively nested") from exc
        except ValueError as exc:
            raise LangGraphImportError(
                "LangGraph NDJSON contains an invalid numeric value"
            ) from exc
        if not isinstance(part, dict):
            raise LangGraphImportError(
                f"LangGraph NDJSON line {line_number} must contain an object"
            )
        parts.append(part)
    return langgraph_v2_to_events(
        parts,
        run_id=run_id,
        thread_id=thread_id,
        framework_version=framework_version,
        stream_complete=stream_complete,
        run_status=run_status,
        capture_content=capture_content,
    )


def _reject_excessive_json_nesting(line: str) -> None:
    """Enforce one deterministic nesting limit before CPython's decoder diverges."""

    depth = 0
    in_string = False
    escaped = False
    for character in line:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "[{":
            depth += 1
            if depth > _MAX_NDJSON_NESTING:
                raise LangGraphImportError("LangGraph NDJSON is excessively nested")
        elif character in "]}":
            depth -= 1


def _part_to_events(
    part: dict[str, Any],
    **kwargs: Any,
) -> list[AgentRuntimeEvent]:
    """Map one source part while retaining simultaneous state and interrupt facts."""

    interrupt_observations = kwargs.pop("interrupt_observations")
    base = _part_to_event(part, **kwargs)
    source_seq = int(kwargs["source_seq"]) + 1
    source_index = int(kwargs["source_index"])
    run_id = str(kwargs["run_id"])
    thread_id = kwargs.get("thread_id")
    framework_version = kwargs.get("framework_version")
    observed_at = kwargs["observed_at"]
    capture_content = bool(kwargs["capture_content"])
    mode = str(part["type"])
    data = _plain(part.get("data"))
    namespace = tuple(str(item) for item in part.get("ns", []))
    related: list[AgentRuntimeEvent] = []

    interrupts: list[Any] = []
    if mode == "values":
        interrupts = _plain(part.get("interrupts") or [])
    elif mode == "updates" and isinstance(data, dict):
        interrupts = _plain(data.get("__interrupt__") or [])
    elif mode == "tasks" and isinstance(data, dict):
        interrupts = _plain(data.get("interrupts") or [])
    for ordinal, interrupt in enumerate(interrupts):
        interrupt_id = _interrupt_identifier(interrupt, source_index, ordinal)
        interrupt_key = (namespace, interrupt_id)
        primary_event_id = interrupt_observations.get(interrupt_key)
        observation = _interrupt_observation(
            interrupt,
            event_type=(
                "human.interrupt" if primary_event_id is None else "langgraph.interrupt.reobserved"
            ),
            mode=mode,
            ordinal=ordinal,
            source_index=source_index,
            source_seq=source_seq + len(related),
            run_id=run_id,
            thread_id=thread_id,
            framework_version=framework_version,
            observed_at=observed_at,
            timestamp=part.get("timestamp"),
            base_event=base,
            capture_content=capture_content,
            primary_event_id=primary_event_id,
        )
        if primary_event_id is None:
            interrupt_observations[interrupt_key] = observation.event_id
        related.append(observation)

    if mode == "checkpoints" and isinstance(data, dict):
        for task_ordinal, task_value in enumerate(data.get("tasks") or []):
            task = _plain(task_value)
            if not isinstance(task, dict):
                continue
            task_id = _identifier(task.get("id")) or f"checkpoint-task:{task_ordinal}"
            name = _bounded_text(task.get("name"), 240) or "LangGraph checkpoint task"
            subject = EntityRef(
                kind="agent.step",
                id=stable_id("entity", run_id, "langgraph", "task", *namespace, task_id),
                name=name,
            )
            if task.get("error") is not None:
                payload = {
                    "stream_mode": mode,
                    "task_id": task_id,
                    "node": name,
                    "status": "failed_in_checkpoint_snapshot",
                }
                related.append(
                    _related_observation(
                        event_type="error.task_snapshot",
                        identity=("task-error", task_id),
                        summary=f"Checkpoint snapshot contains task error: {name}",
                        payload=payload,
                        content_fields={"error": task.get("error")},
                        subject=subject,
                        mode=mode,
                        source_index=source_index,
                        source_seq=source_seq + len(related),
                        run_id=run_id,
                        thread_id=thread_id,
                        framework_version=framework_version,
                        observed_at=observed_at,
                        timestamp=part.get("timestamp"),
                        base_event=base,
                        capture_content=capture_content,
                    )
                )
            for interrupt_ordinal, interrupt in enumerate(task.get("interrupts") or []):
                related.append(
                    _interrupt_observation(
                        interrupt,
                        event_type="human.interrupt.snapshot",
                        mode=mode,
                        ordinal=interrupt_ordinal,
                        source_index=source_index,
                        source_seq=source_seq + len(related),
                        run_id=run_id,
                        thread_id=thread_id,
                        framework_version=framework_version,
                        observed_at=observed_at,
                        timestamp=part.get("timestamp"),
                        base_event=base,
                        capture_content=capture_content,
                        task_id=task_id,
                        task_name=name,
                    )
                )
    return [base, *related]


def _interrupt_observation(
    interrupt_value: Any,
    *,
    event_type: str,
    mode: str,
    ordinal: int,
    source_index: int,
    source_seq: int,
    run_id: str,
    thread_id: str | None,
    framework_version: str | None,
    observed_at: datetime,
    timestamp: Any,
    base_event: AgentRuntimeEvent,
    capture_content: bool,
    primary_event_id: str | None = None,
    task_id: str | None = None,
    task_name: str | None = None,
) -> AgentRuntimeEvent:
    interrupt = _plain(interrupt_value)
    record = interrupt if isinstance(interrupt, dict) else {"value": interrupt}
    interrupt_id = _interrupt_identifier(interrupt, source_index, ordinal)
    namespace = tuple(
        str(item) for item in base_event.extensions.get("langgraph", {}).get("namespace", [])
    )
    source_interrupt_id = _identifier(record.get("id"))
    payload: dict[str, Any] = {
        "stream_mode": mode,
        "interrupt_id": interrupt_id,
        "interrupt_ordinal": ordinal,
        "task_id": task_id,
        "node": task_name,
        "status": (
            "snapshot"
            if event_type.endswith(".snapshot")
            else "reobserved"
            if event_type.endswith(".reobserved")
            else "waiting"
        ),
    }
    if primary_event_id:
        payload["first_observation_event_id"] = primary_event_id
    if source_interrupt_id:
        payload.update(
            {
                "interrupt_id_chars": len(source_interrupt_id),
                "interrupt_id_hashed": source_interrupt_id != interrupt_id,
            }
        )
    public = {str(key): value for key, value in record.items() if key not in {"id", "value"}}
    content_fields = {"interrupt_value": record.get("value")}
    if public:
        content_fields["interrupt_metadata"] = public
    subject = EntityRef(
        kind="human.interrupt",
        id=stable_id("entity", run_id, "langgraph", "interrupt", *namespace, interrupt_id),
        name=task_name or "LangGraph interrupt",
    )
    display_name = _bounded_text(task_name or interrupt_id, 200) or "LangGraph interrupt"
    return _related_observation(
        event_type=event_type,
        identity=("interrupt", task_id or "", interrupt_id, ordinal),
        summary=(
            f"Checkpoint snapshot contains interrupt: {display_name}"
            if event_type.endswith(".snapshot")
            else f"LangGraph interrupt re-observed: {display_name}"
            if event_type.endswith(".reobserved")
            else f"LangGraph interrupt observed: {display_name}"
        ),
        payload=payload,
        content_fields=content_fields,
        subject=subject,
        mode=mode,
        source_index=source_index,
        source_seq=source_seq,
        run_id=run_id,
        thread_id=thread_id,
        framework_version=framework_version,
        observed_at=observed_at,
        timestamp=timestamp,
        base_event=base_event,
        capture_content=capture_content,
        related_event_id=primary_event_id,
    )


def _interrupt_identifier(interrupt_value: Any, source_index: int, ordinal: int) -> str:
    interrupt = _plain(interrupt_value)
    record = interrupt if isinstance(interrupt, dict) else {}
    source_identifier = _safe_interrupt_identifier(record.get("id"))
    return source_identifier or f"part:{source_index}:{ordinal}"


def _safe_interrupt_identifier(value: Any) -> str | None:
    source_identifier = _identifier(value)
    if source_identifier and len(source_identifier) > _MAX_SOURCE_IDENTIFIER_LENGTH:
        return stable_id("interrupt", source_identifier)
    return source_identifier


def _related_observation(
    *,
    event_type: str,
    identity: tuple[object, ...],
    summary: str,
    payload: dict[str, Any],
    content_fields: dict[str, Any],
    subject: EntityRef,
    mode: str,
    source_index: int,
    source_seq: int,
    run_id: str,
    thread_id: str | None,
    framework_version: str | None,
    observed_at: datetime,
    timestamp: Any,
    base_event: AgentRuntimeEvent,
    capture_content: bool,
    related_event_id: str | None = None,
) -> AgentRuntimeEvent:
    content: dict[str, Any] = {}
    redacted: list[str] = []
    for field, value in content_fields.items():
        _capture_or_summarize(payload, content, redacted, field, value, capture_content)
    if content:
        payload["content"] = content
    namespace = list(base_event.extensions.get("langgraph", {}).get("namespace", []))
    fragment = stable_id("observation", *identity)
    raw_ref = f"langgraph://{run_id}/{source_index}#{fragment}"
    links = [EventLink(type=LinkType.RELATED, event_id=base_event.event_id)]
    if related_event_id and related_event_id != base_event.event_id:
        links.append(EventLink(type=LinkType.RELATED, event_id=related_event_id))
    return AgentRuntimeEvent(
        event_id=stable_id("evt", run_id, "langgraph", source_index, *identity),
        event_type=event_type,
        run_id=run_id,
        thread_id=thread_id,
        correlation_id=base_event.correlation_id,
        links=links,
        clock=EventClock(
            occurred_at=_timestamp(timestamp, observed_at),
            observed_at=observed_at,
            source_seq=source_seq,
        ),
        source=_source(
            run_id,
            raw_ref=raw_ref,
            framework_version=framework_version,
        ),
        subject=subject,
        evidence=Evidence(
            level=EvidenceLevel.OBSERVED,
            confidence=1.0,
            refs=[EvidenceRef(kind="protocol_event", uri=raw_ref, label=event_type)],
            explanation=(
                "Observed as a second fact carried by the same LangGraph StreamPart; "
                "RELATED is a source-record relation, not an invented causal edge"
            ),
        ),
        summary=summary,
        payload={key: value for key, value in payload.items() if value is not None},
        privacy=Privacy(
            content=(
                ContentCapture.PLAINTEXT_OPT_IN if capture_content else ContentCapture.METADATA_ONLY
            ),
            contains_sensitive_data=True,
            redacted_fields=[] if capture_content else sorted(set(redacted)),
        ),
        extensions={
            "langgraph": {
                "stream_version": "v2",
                "mode": mode,
                "namespace": namespace,
                "source_part_index": source_index,
                "supplemental": True,
            }
        },
    )


def _part_to_event(
    part: dict[str, Any],
    *,
    original_type: str,
    source_index: int,
    source_seq: int,
    run_id: str,
    thread_id: str | None,
    framework_version: str | None,
    observed_at: datetime,
    task_starts: dict[tuple[tuple[str, ...], str], list[tuple[int, str]]],
    checkpoints: dict[tuple[tuple[str, ...], str, str], list[tuple[int, str]]],
    capture_content: bool,
) -> AgentRuntimeEvent:
    mode = str(part["type"])
    data = _plain(part.get("data"))
    namespace = [_bounded_text(item, 256) or "" for item in part.get("ns", [])]
    event_type, subject = _event_type_and_subject(
        mode,
        data,
        run_id=run_id,
        source_index=source_index,
        namespace=namespace,
    )
    event_id = _part_event_id(run_id, source_index, mode, data)
    payload, measurements, redacted = _safe_part_payload(
        mode, data, namespace=namespace, capture_content=capture_content
    )
    cause = None
    links: list[EventLink] = []
    if mode == "tasks" and _is_task_result(data):
        task_id = _identifier(data.get("id"))
        task_key = (tuple(namespace), task_id) if task_id else None
        cause = _nearest_start(task_starts.get(task_key, []), source_index) if task_key else None
    if mode == "checkpoints":
        config = data.get("config")
        parent_config = data.get("parent_config")
        checkpoint_id = _checkpoint_id(config)
        checkpoint_ns = _checkpoint_namespace(config) or ""
        parent_id = _checkpoint_id(parent_config)
        parent_ns = _checkpoint_namespace(parent_config)
        if parent_ns is None:
            parent_ns = checkpoint_ns
        checkpoint_key = (tuple(namespace), checkpoint_ns, checkpoint_id)
        parent_key = (tuple(namespace), parent_ns, parent_id)
        parent_event_id = (
            _nearest_start(checkpoints.get(parent_key, []), source_index)
            if parent_id and parent_key != checkpoint_key
            else None
        )
        if parent_event_id:
            links.append(EventLink(type=LinkType.DERIVED_FROM, event_id=parent_event_id))
    correlation = _correlation_id(mode, data, run_id, namespace)
    source_fields = sorted(str(key) for key in data) if isinstance(data, dict) else []
    extensions = {
        "langgraph": {
            "stream_version": "v2",
            "mode": mode,
            "original_mode": original_type,
            "namespace": namespace,
            "source_field_names": source_fields,
        }
    }
    stable_message_id = None
    if mode == "messages":
        message, _ = _message_parts(data)
        stable_message_id = _identifier(message.get("id"))
    if stable_message_id and measurements:
        extensions.update(_message_measurement_semantics(subject.id, measurements))
    return AgentRuntimeEvent(
        event_id=event_id,
        event_type=event_type,
        run_id=run_id,
        thread_id=thread_id,
        causation_id=cause,
        correlation_id=correlation,
        links=links,
        clock=EventClock(
            occurred_at=_timestamp(part.get("timestamp"), observed_at),
            observed_at=observed_at,
            source_seq=source_seq,
        ),
        source=_source(
            run_id,
            raw_ref=f"langgraph://{run_id}/{source_index}",
            framework_version=framework_version,
        ),
        subject=subject,
        evidence=Evidence(
            level=EvidenceLevel.OBSERVED,
            confidence=1.0,
            refs=[
                EvidenceRef(
                    kind="protocol_event",
                    uri=f"langgraph://{run_id}/{source_index}",
                    label=_bounded_text(f"{original_type}:{mode}", 200),
                )
            ],
            explanation=f"Deterministically mapped from LangGraph StreamPart v2 mode {mode}",
        ),
        summary=_summary(event_type, subject),
        payload=payload,
        measurements=measurements,
        privacy=Privacy(
            content=(
                ContentCapture.PLAINTEXT_OPT_IN if capture_content else ContentCapture.METADATA_ONLY
            ),
            # Metadata identifiers (node names, namespaces, state keys, IDs)
            # can still reveal business context even when values are removed.
            contains_sensitive_data=True,
            redacted_fields=[] if capture_content else sorted(set(redacted)),
        ),
        extensions=extensions,
    )


def _message_measurement_semantics(
    owner_id: str, measurements: dict[str, int | float]
) -> dict[str, Any]:
    aggregate_keys = {
        "input_tokens": "model_call.input_tokens",
        "output_tokens": "model_call.output_tokens",
        "total_tokens": "model_call.total_tokens",
    }
    semantics = {
        key: MeasurementSemantics(
            aggregate_key=aggregate_keys[key],
            unit="tokens",
            scope="model_call",
            aggregation="sum",
            temporality="unknown",
            owner_id=owner_id,
        )
        for key in measurements
        if key in aggregate_keys
    }
    return measurement_semantics_extension(semantics)


def _event_type_and_subject(
    mode: str,
    data: Any,
    *,
    run_id: str,
    source_index: int,
    namespace: list[str],
) -> tuple[str, EntityRef]:
    if mode == "tasks" and isinstance(data, dict):
        task_id = _identifier(data.get("id")) or f"part:{source_index}"
        name = _bounded_text(data.get("name"), 240) or "LangGraph task"
        subject = EntityRef(
            kind="agent.step",
            id=stable_id("entity", run_id, "langgraph", "task", *namespace, task_id),
            name=name,
        )
        if not _is_task_result(data):
            return "agent.step.started", subject
        if data.get("error") is not None:
            return "error.raised", subject
        if data.get("interrupts"):
            return "agent.step.interrupted", subject
        return "agent.step.completed", subject
    if mode == "messages":
        message, metadata = _message_parts(data)
        message_id = _identifier(message.get("id")) or f"part:{source_index}"
        model = _bounded_text(metadata.get("ls_model_name"), 240) or "LangGraph model stream"
        return "model.response.chunk", EntityRef(
            kind="model.call",
            id=stable_id("entity", run_id, "langgraph", "message", *namespace, message_id),
            name=model,
        )
    if mode == "updates":
        nodes = (
            [str(key) for key in data if not str(key).startswith("__")]
            if isinstance(data, dict)
            else []
        )
        for node in nodes:
            _validate_identity_component(node, "update node")
        if not nodes:
            return "langgraph.stream.observed", EntityRef(
                kind="langgraph.signal",
                id=stable_id("entity", run_id, "langgraph", "update", *namespace, source_index),
                name="LangGraph control update",
            )
        name = nodes[0] if len(nodes) == 1 else "Graph state update"
        return "agent.state.changed", EntityRef(
            kind="agent.step" if len(nodes) == 1 else "graph.state",
            id=stable_id(
                "entity",
                run_id,
                "langgraph",
                "update",
                *namespace,
                *nodes,
                source_index,
            ),
            name=_bounded_text(name, 240),
        )
    if mode == "checkpoints":
        config = data.get("config") if isinstance(data, dict) else None
        checkpoint_id = _checkpoint_id(config)
        checkpoint_id = checkpoint_id or f"part:{source_index}"
        checkpoint_ns = _checkpoint_namespace(config) or ""
        return "checkpoint.created", EntityRef(
            kind="checkpoint",
            id=stable_id(
                "entity",
                run_id,
                "langgraph",
                "checkpoint",
                *namespace,
                checkpoint_ns,
                checkpoint_id,
            ),
            name="LangGraph checkpoint",
        )
    if mode == "values":
        return "context.shared_state.snapshot", EntityRef(
            kind="graph.state",
            id=stable_id("entity", run_id, "langgraph", "state", *namespace),
            name="LangGraph state",
        )
    if mode == "custom":
        return "langgraph.custom", EntityRef(
            kind="langgraph.signal",
            id=stable_id("entity", run_id, "langgraph", "custom", *namespace, source_index),
            name="Custom stream signal",
        )
    return "langgraph.stream.observed", EntityRef(
        kind="langgraph.signal",
        id=stable_id("entity", run_id, "langgraph", mode, *namespace, source_index),
        name=_bounded_text(mode, 240),
    )


def _safe_part_payload(
    mode: str,
    data: Any,
    *,
    namespace: list[str],
    capture_content: bool,
) -> tuple[dict[str, Any], dict[str, int | float], list[str]]:
    payload: dict[str, Any] = {"stream_mode": mode, "namespace": namespace}
    measurements: dict[str, int | float] = {}
    redacted: list[str] = []
    content: dict[str, Any] = {}
    if mode == "tasks" and isinstance(data, dict):
        payload.update(
            {
                "task_id": _identifier(data.get("id")),
                "node": _bounded_text(data.get("name"), 240),
                "trigger_count": len(data.get("triggers") or []),
                "status": (
                    "failed"
                    if data.get("error") is not None
                    else "interrupted"
                    if data.get("interrupts")
                    else "completed"
                    if _is_task_result(data)
                    else "running"
                ),
            }
        )
        _capture_or_summarize(
            payload, content, redacted, "input", data.get("input"), capture_content
        )
        _capture_or_summarize(
            payload, content, redacted, "result", data.get("result"), capture_content
        )
        _capture_or_summarize(
            payload, content, redacted, "error", data.get("error"), capture_content
        )
        interrupts = data.get("interrupts") or []
        if interrupts:
            interrupt_ids: list[str] = []
            safe_interrupts: list[Any] = []
            for item in interrupts:
                if not isinstance(item, dict):
                    safe_interrupts.append(item)
                    continue
                interrupt_id = _safe_interrupt_identifier(item.get("id"))
                if interrupt_id:
                    interrupt_ids.append(interrupt_id)
                safe_item = dict(item)
                if "id" in safe_item:
                    if interrupt_id:
                        safe_item["id"] = interrupt_id
                    else:
                        safe_item.pop("id")
                safe_interrupts.append(safe_item)
            payload["interrupt_count"] = len(interrupts)
            payload["interrupt_ids"] = interrupt_ids
            _capture_or_summarize(
                payload, content, redacted, "interrupts", safe_interrupts, capture_content
            )
    elif mode == "messages":
        message, metadata = _message_parts(data)
        payload.update(
            {
                "message_id": _identifier(message.get("id")),
                "message_type": _bounded_text(message.get("type"), 80),
                "node": _bounded_text(metadata.get("langgraph_node"), 240),
                "step": _number(metadata.get("langgraph_step")),
                "provider": _bounded_text(metadata.get("ls_provider"), 120),
                "model": _bounded_text(metadata.get("ls_model_name"), 240),
                "trigger_count": len(metadata.get("langgraph_triggers") or []),
                "tag_count": len(metadata.get("tags") or []),
                "tool_call_count": len(message.get("tool_calls") or []),
            }
        )
        _capture_or_summarize(
            payload, content, redacted, "content", message.get("content"), capture_content
        )
        usage = message.get("usage_metadata") or {}
        if isinstance(usage, dict):
            for key in ("input_tokens", "output_tokens", "total_tokens"):
                value = _number(usage.get(key))
                if value is not None:
                    measurements[key] = value
    elif mode == "updates" and isinstance(data, dict):
        public_updates = {
            str(node): value for node, value in data.items() if not str(node).startswith("__")
        }
        payload["updates"] = {
            str(node): _mapping_keys(value) for node, value in public_updates.items()
        }
        payload["special_fields"] = sorted(str(node) for node in data if str(node).startswith("__"))
        _capture_or_summarize(
            payload,
            content,
            redacted,
            "state_updates",
            public_updates,
            capture_content,
        )
    elif mode == "checkpoints" and isinstance(data, dict):
        configurable = _configurable(data.get("config"))
        metadata = _plain(data.get("metadata"))
        payload.update(
            {
                "checkpoint_id": _identifier(configurable.get("checkpoint_id")),
                "checkpoint_ns": _bounded_text(configurable.get("checkpoint_ns"), 256),
                "step": _number(metadata.get("step")) if isinstance(metadata, dict) else None,
                "source": _bounded_text(metadata.get("source"), 80)
                if isinstance(metadata, dict)
                else None,
                "state_keys": _mapping_keys(data.get("values")),
                "next_nodes": [str(item)[:240] for item in (data.get("next") or [])],
                "task_count": len(data.get("tasks") or []),
                "parent_checkpoint_id": _checkpoint_id(data.get("parent_config")),
            }
        )
        _capture_or_summarize(
            payload, content, redacted, "values", data.get("values"), capture_content
        )
        if isinstance(metadata, dict) and metadata.get("writes") is not None:
            payload["write_nodes"] = _mapping_keys(metadata.get("writes"))
            _capture_or_summarize(
                payload, content, redacted, "writes", metadata.get("writes"), capture_content
            )
    else:
        field = "state" if mode == "values" else "data"
        _capture_or_summarize(payload, content, redacted, field, data, capture_content)
    if content:
        payload["content"] = content
    return (
        {key: value for key, value in payload.items() if value is not None},
        measurements,
        redacted,
    )


def _capture_or_summarize(
    payload: dict[str, Any],
    content: dict[str, Any],
    redacted: list[str],
    field: str,
    value: Any,
    capture_content: bool,
) -> None:
    if value is None:
        return
    plain = _plain(value)
    if capture_content:
        content[field] = plain
        return
    if isinstance(plain, dict):
        payload[f"{field}_keys"] = sorted(str(key) for key in plain)
    elif isinstance(plain, (list, tuple)):
        payload[f"{field}_count"] = len(plain)
    elif isinstance(plain, str):
        payload[f"{field}_chars"] = len(plain)
    else:
        payload[f"{field}_type"] = type(plain).__name__
    redacted.append(field)


def _index_explicit_starts(
    parts: list[dict[str, Any]], run_id: str
) -> tuple[
    dict[tuple[tuple[str, ...], str], list[tuple[int, str]]],
    dict[tuple[tuple[str, ...], str, str], list[tuple[int, str]]],
]:
    task_starts: dict[tuple[tuple[str, ...], str], list[tuple[int, str]]] = {}
    checkpoints: dict[tuple[tuple[str, ...], str, str], list[tuple[int, str]]] = {}
    for index, raw in enumerate(parts):
        part = _normalize_debug_part(raw)
        data = _plain(part.get("data"))
        mode = str(part.get("type"))
        namespace = tuple(_bounded_text(item, 256) or "" for item in part.get("ns", []))
        if mode == "tasks" and isinstance(data, dict) and not _is_task_result(data):
            task_id = _identifier(data.get("id"))
            if task_id:
                task_starts.setdefault((namespace, task_id), []).append(
                    (index, _part_event_id(run_id, index, mode, data))
                )
        elif mode == "checkpoints" and isinstance(data, dict):
            config = data.get("config")
            checkpoint_id = _checkpoint_id(config)
            if checkpoint_id:
                key = (namespace, _checkpoint_namespace(config) or "", checkpoint_id)
                checkpoints.setdefault(key, []).append(
                    (index, _part_event_id(run_id, index, mode, data))
                )
    return task_starts, checkpoints


def _part_event_id(run_id: str, index: int, mode: str, data: Any) -> str:
    logical = ""
    if isinstance(data, dict):
        logical = _identifier(data.get("id")) or _checkpoint_id(data.get("config")) or ""
    return stable_id("evt", run_id, "langgraph", index, mode, logical)


def _validate_part_shape(part: dict[str, Any], index: int) -> None:
    _validate_source_value(_plain(part), f"part {index}")
    namespace = part.get("ns")
    if not isinstance(namespace, (list, tuple)):
        raise LangGraphImportError(f"part {index} ns must be an array")
    for item_index, item in enumerate(namespace):
        if not isinstance(item, str):
            raise LangGraphImportError(f"part {index} ns[{item_index}] must be a string")
        if len(item) > 256:
            raise LangGraphImportError(f"part {index} ns[{item_index}] exceeds 256 characters")
        _validate_identity_component(item, f"part {index} ns[{item_index}]")

    mode = str(part.get("type"))
    data = _plain(part.get("data"))
    if mode in {"tasks", "updates", "checkpoints", "debug"} and not isinstance(data, dict):
        raise LangGraphImportError(f"part {index} {mode}.data must be an object")

    if mode == "tasks":
        _validate_task_shape(data, index)
    elif mode == "messages":
        if not isinstance(data, (list, tuple)) or len(data) != 2:
            raise LangGraphImportError(
                f"part {index} messages.data must be a [message, metadata] pair"
            )
        message, metadata = _message_parts(data)
        if not message or not isinstance(metadata, dict):
            raise LangGraphImportError(
                f"part {index} messages.data must contain message and metadata objects"
            )
        if "content" not in message or "type" not in message:
            raise LangGraphImportError(
                f"part {index} messages.message must contain content and type"
            )
        message_type = message.get("type")
        if not isinstance(message_type, str) or not message_type:
            raise LangGraphImportError(
                f"part {index} messages.message.type must be a non-empty string"
            )
        _validate_text(message_type, f"part {index} messages.message.type")
        content = _plain(message.get("content"))
        if not isinstance(content, (str, list, tuple)):
            raise LangGraphImportError(
                f"part {index} messages.message.content must be text or an array of content blocks"
            )
        if isinstance(content, (list, tuple)):
            for content_index, block in enumerate(content):
                if not isinstance(block, (str, dict)):
                    raise LangGraphImportError(
                        f"part {index} messages.message.content[{content_index}] must be text or an object"
                    )
        if message.get("id") is not None:
            _bounded_identifier(message.get("id"), f"part {index} messages.message.id")
        _require_sequence_field(message, "tool_calls", index, "messages.message")
        _require_sequence_field(metadata, "langgraph_triggers", index, "messages.metadata")
        _require_sequence_field(metadata, "tags", index, "messages.metadata")
        usage = message.get("usage_metadata")
        if usage is not None and not isinstance(usage, dict):
            raise LangGraphImportError(
                f"part {index} messages.message.usage_metadata must be an object"
            )
        if isinstance(usage, dict):
            required_usage = {"input_tokens", "output_tokens", "total_tokens"}
            missing_usage = sorted(required_usage - set(usage))
            if missing_usage:
                raise LangGraphImportError(
                    f"part {index} messages.message.usage_metadata is missing required fields: "
                    + ", ".join(missing_usage)
                )
            for name in sorted(required_usage):
                count = usage[name]
                if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                    raise LangGraphImportError(
                        f"part {index} messages.message.usage_metadata.{name} "
                        "must be a non-negative integer"
                    )
    elif mode == "updates":
        interrupts = _require_sequence_field(data, "__interrupt__", index, "updates.data")
        _validate_interrupt_records(interrupts, index, "updates.data.__interrupt__")
    elif mode == "values":
        if "interrupts" not in part:
            raise LangGraphImportError(f"part {index} values.interrupts is required")
        interrupts = _require_sequence_field(part, "interrupts", index, "values")
        _validate_interrupt_records(interrupts, index, "values.interrupts")
    elif mode == "checkpoints":
        _validate_checkpoint_shape(data, index)


def _validate_task_shape(data: dict[str, Any], index: int) -> None:
    common = {"id", "name"}
    start = {"input", "triggers"}
    result = {"error", "result", "interrupts"}
    keys = set(data)
    is_start = start <= keys and not (result & keys)
    is_result = result <= keys and not (start & keys)
    if not common <= keys or is_start == is_result:
        raise LangGraphImportError(
            f"part {index} tasks.data must match the LangGraph task start or result shape"
        )
    if _identifier(data.get("id")) is None or _bounded_text(data.get("name"), 240) is None:
        raise LangGraphImportError(f"part {index} tasks.data id and name must be non-empty strings")
    if is_start:
        triggers = _require_sequence_field(data, "triggers", index, "tasks.data")
        for trigger_index, trigger in enumerate(triggers):
            if not isinstance(trigger, str):
                raise LangGraphImportError(
                    f"part {index} tasks.data.triggers[{trigger_index}] must be a string"
                )
        if "metadata" in data and not isinstance(_plain(data.get("metadata")), dict):
            raise LangGraphImportError(f"part {index} tasks.data.metadata must be an object")
    else:
        interrupts = _require_sequence_field(data, "interrupts", index, "tasks.data")
        _validate_interrupt_records(interrupts, index, "tasks.data.interrupts")
        error = data.get("error")
        if error is not None and not isinstance(error, str):
            raise LangGraphImportError(f"part {index} tasks.data.error must be a string or null")
        if not isinstance(_plain(data.get("result")), dict):
            raise LangGraphImportError(f"part {index} tasks.data.result must be an object")


def _validate_checkpoint_config(value: Any, index: int, field: str) -> None:
    config = _plain(value)
    if config is None:
        return
    if not isinstance(config, dict):
        raise LangGraphImportError(
            f"part {index} checkpoints.data.{field} must be an object or null"
        )
    if "configurable" not in config:
        return
    configurable = _plain(config.get("configurable"))
    if not isinstance(configurable, dict):
        raise LangGraphImportError(
            f"part {index} checkpoints.data.{field}.configurable must be an object"
        )
    prefix = f"part {index} checkpoints.data.{field}.configurable"
    for name in ("thread_id", "checkpoint_id"):
        if name not in configurable:
            continue
        item = configurable[name]
        if not isinstance(item, str) or not item:
            raise LangGraphImportError(f"{prefix}.{name} must be a non-empty string")
        _validate_identity_component(item, f"{prefix}.{name}")
        if len(item) > _MAX_SOURCE_IDENTIFIER_LENGTH:
            raise LangGraphImportError(
                f"{prefix}.{name} exceeds {_MAX_SOURCE_IDENTIFIER_LENGTH} characters"
            )
    if "checkpoint_ns" in configurable:
        namespace = configurable["checkpoint_ns"]
        if not isinstance(namespace, str):
            raise LangGraphImportError(f"{prefix}.checkpoint_ns must be a string")
        _validate_identity_component(namespace, f"{prefix}.checkpoint_ns")
        if len(namespace) > _MAX_SOURCE_IDENTIFIER_LENGTH:
            raise LangGraphImportError(
                f"{prefix}.checkpoint_ns exceeds {_MAX_SOURCE_IDENTIFIER_LENGTH} characters"
            )


def _validate_checkpoint_shape(data: dict[str, Any], index: int) -> None:
    required = {"config", "metadata", "values", "next", "parent_config", "tasks"}
    missing = sorted(required - set(data))
    if missing:
        raise LangGraphImportError(
            f"part {index} checkpoints.data is missing required fields: {', '.join(missing)}"
        )
    for field in ("config", "parent_config"):
        _validate_checkpoint_config(data.get(field), index, field)
    metadata = _plain(data.get("metadata"))
    if not isinstance(metadata, dict):
        raise LangGraphImportError(f"part {index} checkpoints.data.metadata must be an object")
    _validate_checkpoint_metadata(metadata, index)
    next_nodes = _require_sequence_field(data, "next", index, "checkpoints.data")
    for node_index, node in enumerate(next_nodes):
        if not isinstance(node, str):
            raise LangGraphImportError(
                f"part {index} checkpoints.data.next[{node_index}] must be a string"
            )
        if len(node) > 240:
            raise LangGraphImportError(
                f"part {index} checkpoints.data.next[{node_index}] exceeds 240 characters"
            )
    tasks = _require_sequence_field(data, "tasks", index, "checkpoints.data")
    task_ids: set[str] = set()
    for task_index, task_value in enumerate(tasks):
        task = _plain(task_value)
        path = f"checkpoints.data.tasks[{task_index}]"
        if not isinstance(task, dict):
            raise LangGraphImportError(f"part {index} {path} must be an object")
        if not {"id", "name", "state"} <= set(task):
            raise LangGraphImportError(f"part {index} {path} must contain id, name, and state")
        task_id = _identifier(task.get("id"))
        if task_id is None or _bounded_text(task.get("name"), 240) is None:
            raise LangGraphImportError(f"part {index} {path} id and name must be non-empty strings")
        if task_id in task_ids:
            raise LangGraphImportError(f"part {index} {path} has a duplicate task id")
        task_ids.add(task_id)
        state_fields = set(task) & {"error", "result", "interrupts"}
        valid_state_shape = state_fields in (
            {"error"},
            {"result", "interrupts"},
            {"interrupts"},
        )
        if not valid_state_shape:
            raise LangGraphImportError(
                f"part {index} {path} must match one checkpoint task state shape"
            )
        if "error" in task and not isinstance(task.get("error"), str):
            raise LangGraphImportError(f"part {index} {path}.error must be a string")
        if "interrupts" in task:
            interrupts = _require_sequence_field(task, "interrupts", index, path)
            _validate_interrupt_records(interrupts, index, f"{path}.interrupts")


def _validate_checkpoint_metadata(metadata: dict[str, Any], index: int) -> None:
    prefix = f"part {index} checkpoints.data.metadata"
    if "source" in metadata and metadata["source"] not in _CHECKPOINT_SOURCES:
        raise LangGraphImportError(f"{prefix}.source must be input, loop, update, or fork")
    if "step" in metadata:
        step = metadata["step"]
        if not isinstance(step, int) or isinstance(step, bool):
            raise LangGraphImportError(f"{prefix}.step must be an integer")
    if "parents" in metadata:
        parents = _plain(metadata["parents"])
        if not isinstance(parents, dict):
            raise LangGraphImportError(f"{prefix}.parents must be an object")
        for namespace, checkpoint_id in parents.items():
            if not isinstance(namespace, str):
                raise LangGraphImportError(f"{prefix}.parents keys must be strings")
            _validate_identity_component(namespace, f"{prefix}.parents namespace")
            if not isinstance(checkpoint_id, str) or not checkpoint_id:
                raise LangGraphImportError(
                    f"{prefix}.parents checkpoint IDs must be non-empty strings"
                )
            _validate_identity_component(checkpoint_id, f"{prefix}.parents checkpoint ID")
    if "run_id" in metadata:
        value = metadata["run_id"]
        if not isinstance(value, str) or not value:
            raise LangGraphImportError(f"{prefix}.run_id must be a non-empty string")
        _validate_identity_component(value, f"{prefix}.run_id")
        if len(value) > _MAX_SOURCE_IDENTIFIER_LENGTH:
            raise LangGraphImportError(
                f"{prefix}.run_id exceeds {_MAX_SOURCE_IDENTIFIER_LENGTH} characters"
            )


def _validate_interrupt_records(
    interrupts: list[Any] | tuple[Any, ...], index: int, path: str
) -> None:
    for interrupt_index, interrupt in enumerate(interrupts):
        record = _plain(interrupt)
        record_path = f"{path}[{interrupt_index}]"
        if not isinstance(record, dict):
            raise LangGraphImportError(f"part {index} {path}[{interrupt_index}] must be an object")
        if not {"id", "value"} <= set(record):
            raise LangGraphImportError(f"part {index} {record_path} must contain id and value")
        if not isinstance(record.get("id"), str) or not record.get("id"):
            raise LangGraphImportError(f"part {index} {record_path}.id must be a non-empty string")
        _validate_identity_component(record["id"], f"part {index} {record_path}.id")


def _validate_debug_wrapper(part: dict[str, Any], index: int) -> None:
    wrapper = _plain(part.get("data"))
    if not isinstance(wrapper, dict):
        raise LangGraphImportError(f"part {index} debug.data must be an object")
    missing = {"step", "timestamp", "type", "payload"} - set(wrapper)
    if missing:
        raise LangGraphImportError(
            f"part {index} debug.data is missing required fields: {', '.join(sorted(missing))}"
        )
    step = wrapper.get("step")
    if not isinstance(step, int) or isinstance(step, bool):
        raise LangGraphImportError(f"part {index} debug.data.step must be an integer")
    timestamp = wrapper.get("timestamp")
    if not isinstance(timestamp, str):
        raise LangGraphImportError(
            f"part {index} debug.data.timestamp must be a timezone-aware ISO 8601 string"
        )
    try:
        _timestamp(timestamp, utc_now())
    except LangGraphImportError as exc:
        raise LangGraphImportError(
            f"part {index} debug.data.timestamp must be a timezone-aware ISO 8601 string"
        ) from exc
    subtype = wrapper.get("type")
    if subtype not in {"task", "task_result", "checkpoint"}:
        raise LangGraphImportError(
            f"part {index} debug.data.type must be task, task_result, or checkpoint"
        )
    if not isinstance(_plain(wrapper.get("payload")), dict):
        raise LangGraphImportError(f"part {index} debug.data.payload must be an object")


def _require_sequence_field(
    container: dict[str, Any],
    field: str,
    index: int,
    path: str,
) -> list[Any] | tuple[Any, ...]:
    if field not in container:
        return []
    value = container[field]
    plain = _plain(value)
    if not isinstance(plain, (list, tuple)):
        raise LangGraphImportError(f"part {index} {path}.{field} must be an array")
    return plain


def _normalize_debug_part(part: dict[str, Any]) -> dict[str, Any]:
    if part.get("type") != "debug" or not isinstance(part.get("data"), dict):
        return part
    wrapper = part["data"]
    subtype = wrapper.get("type")
    mapped = {"task": "tasks", "task_result": "tasks", "checkpoint": "checkpoints"}.get(subtype)
    if mapped and "payload" in wrapper:
        return {
            "type": mapped,
            "ns": part.get("ns", []),
            "data": wrapper["payload"],
            "timestamp": wrapper.get("timestamp"),
        }
    return part


def _source(run_id: str, *, raw_ref: str, framework_version: str | None) -> EventSource:
    return EventSource(
        adapter="anthill.langgraph-v2",
        adapter_version="0.1.0",
        framework="langgraph",
        framework_version=framework_version,
        language="python",
        fidelity=SourceFidelity.MAPPED,
        semantic_convention="langgraph.stream",
        semantic_convention_version="v2",
        raw_event_ref=raw_ref,
    )


def _correlation_id(mode: str, data: Any, run_id: str, namespace: list[str]) -> str:
    logical = ""
    if isinstance(data, dict):
        logical = _identifier(data.get("id")) or _checkpoint_id(data.get("config")) or ""
    elif mode == "messages":
        logical = _identifier(_message_parts(data)[0].get("id")) or ""
    return stable_id("corr", run_id, "langgraph", mode, logical, *namespace)


def _nearest_start(candidates: list[tuple[int, str]], source_index: int) -> str | None:
    if not candidates:
        return None
    prior = [candidate for candidate in candidates if candidate[0] < source_index]
    return prior[-1][1] if prior else None


def _is_task_result(data: dict[str, Any]) -> bool:
    return any(key in data for key in ("result", "error", "interrupts"))


def _message_parts(data: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    if isinstance(data, (list, tuple)) and len(data) == 2:
        message = _plain(data[0])
        metadata = _plain(data[1])
        return (
            message if isinstance(message, dict) else {},
            metadata if isinstance(metadata, dict) else {},
        )
    return {}, {}


def _checkpoint_thread_ids(parts: list[dict[str, Any]]) -> set[str]:
    values: set[str] = set()
    for raw in parts:
        part = _normalize_debug_part(raw)
        data = _plain(part.get("data"))
        if part.get("type") == "checkpoints" and isinstance(data, dict):
            for field in ("config", "parent_config"):
                value = _configurable(data.get(field)).get("thread_id")
                if value is not None:
                    identifier = _bounded_identifier(value, f"checkpoint {field} thread_id")
                    if identifier is not None:
                        values.add(identifier)
    return values


def _checkpoint_id(config: Any) -> str | None:
    return _identifier(_configurable(config).get("checkpoint_id"))


def _checkpoint_namespace(config: Any) -> str | None:
    configurable = _configurable(config)
    if "checkpoint_ns" not in configurable:
        return None
    value = configurable.get("checkpoint_ns")
    if not isinstance(value, str):
        return None
    _validate_identity_component(value, "checkpoint namespace")
    return value


def _configurable(config: Any) -> dict[str, Any]:
    plain = _plain(config)
    if not isinstance(plain, dict):
        return {}
    configurable = _plain(plain.get("configurable"))
    return configurable if isinstance(configurable, dict) else {}


def _mapping_keys(value: Any) -> list[str]:
    plain = _plain(value)
    return sorted(str(key) for key in plain) if isinstance(plain, dict) else []


def _plain(value: Any, _seen: set[int] | None = None) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    seen = _seen if _seen is not None else set()
    marker = id(value)
    if marker in seen:
        raise LangGraphImportError("LangGraph runtime object contains cyclic data")
    seen.add(marker)
    try:
        if isinstance(value, dict):
            return {str(key): _plain(item, seen) for key, item in value.items()}
        if isinstance(value, list):
            return [_plain(item, seen) for item in value]
        if isinstance(value, tuple):
            return tuple(_plain(item, seen) for item in value)
        if hasattr(value, "model_dump"):
            try:
                try:
                    dumped = value.model_dump(mode="json")
                except TypeError:
                    dumped = value.model_dump()
            except Exception as exc:
                raise LangGraphImportError("LangGraph runtime object model_dump failed") from exc
            return _plain(dumped, seen)
        if is_dataclass(value) and not isinstance(value, type):
            try:
                dumped = asdict(value)
            except Exception as exc:
                raise LangGraphImportError(
                    "LangGraph runtime object dataclass conversion failed"
                ) from exc
            return _plain(dumped, seen)
        return {}
    except RecursionError as exc:
        raise LangGraphImportError("LangGraph runtime object is excessively nested") from exc
    finally:
        seen.discard(marker)


def _summary(event_type: str, subject: EntityRef) -> str:
    return f"LangGraph {event_type.replace('.', ' ')}: {subject.name or subject.kind}"


def _identifier(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    _validate_identity_component(value, "identifier")
    return value


def _bounded_identifier(value: Any, field: str) -> str | None:
    text = _identifier(value)
    if value is not None and text is None:
        raise LangGraphImportError(f"{field} must be a non-empty string")
    if text is not None and len(text) > 256:
        raise LangGraphImportError(f"{field} exceeds the canonical 256-character limit")
    return text


def _bounded_text(value: Any, limit: int) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    _validate_text(value, "text field")
    return value[:limit]


def _number(value: Any) -> int | float | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    if isinstance(value, float) and not isfinite(value):
        raise LangGraphImportError("LangGraph numeric values must be finite")
    return value


def _run_identifier(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise LangGraphImportError("run_id must be a non-empty string")
    if _RUN_ID_PATTERN.fullmatch(value) is None:
        raise LangGraphImportError(
            "run_id must be a URL-safe ASCII identifier using letters, digits, '.', '_', '~', or '-'"
        )
    return value


def _validate_text(value: str, field: str) -> None:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise LangGraphImportError(f"{field} must contain valid Unicode text") from exc


def _validate_identity_component(value: str, field: str) -> None:
    _validate_text(value, field)
    if _RESERVED_ID_SEPARATOR in value:
        raise LangGraphImportError(f"{field} contains the reserved identity separator")


def _validate_source_value(value: Any, field: str) -> None:
    if isinstance(value, str):
        _validate_text(value, field)
        return
    if isinstance(value, float) and not isfinite(value):
        raise LangGraphImportError(f"{field} numeric values must be finite")
    if isinstance(value, dict):
        for key, item in value.items():
            _validate_text(str(key), f"{field} field name")
            _validate_source_value(item, field)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _validate_source_value(item, field)


def _timestamp(value: Any, fallback: datetime) -> datetime:
    if value is None:
        return fallback
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            seconds = float(value)
        except (OverflowError, ValueError) as exc:
            raise LangGraphImportError(
                "LangGraph timestamp is outside the supported range"
            ) from exc
        if not isfinite(seconds):
            raise LangGraphImportError("LangGraph timestamp must be finite")
        if abs(seconds) >= 100_000_000_000:
            seconds /= 1000
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OverflowError, OSError, ValueError) as exc:
            raise LangGraphImportError(
                "LangGraph timestamp is outside the supported range"
            ) from exc
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise LangGraphImportError("LangGraph timestamp must be ISO 8601 or Unix time") from exc
        if parsed.tzinfo is None:
            raise LangGraphImportError("LangGraph timestamp must be timezone-aware")
        return parsed
    raise LangGraphImportError("LangGraph timestamp must be ISO 8601 or Unix time")

"""Normalize ``sys.settrace`` output into trustworthy runtime events."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Mapping

from analyzer.pattern_detector import NodeClassification
from tracer.tracer import TraceEvent, TraceResult

from ..schema import (
    AgentRuntimeEvent,
    ContentCapture,
    CoreEventType,
    EntityRef,
    EventClock,
    EventSource,
    Evidence,
    EvidenceLevel,
    EvidenceRef,
    Privacy,
    SourceFidelity,
)
from ._common import repository_uri, stable_id


_SEMANTIC_EVENTS = {
    "llm_call": {
        "call": CoreEventType.MODEL_REQUEST_DISPATCHED.value,
        "return": CoreEventType.MODEL_RESPONSE_COMPLETED.value,
        "exception": CoreEventType.MODEL_FAILED.value,
    },
    "tool": {
        "call": CoreEventType.TOOL_EXECUTION_STARTED.value,
        "return": CoreEventType.TOOL_EXECUTION_SUCCEEDED.value,
        "exception": CoreEventType.TOOL_EXECUTION_FAILED.value,
    },
    "sub_agent": {
        "call": CoreEventType.AGENT_STEP_STARTED.value,
        "return": CoreEventType.AGENT_STEP_COMPLETED.value,
        "exception": CoreEventType.ERROR_RAISED.value,
    },
    "decision": {
        "call": "decision.started",
        "return": "decision.evaluated",
        "exception": CoreEventType.ERROR_RAISED.value,
    },
}


def trace_result_to_events(
    result: TraceResult,
    *,
    run_id: str,
    project_id: str | None = None,
    session_id: str | None = None,
    classifications: Mapping[str, NodeClassification] | None = None,
    capture_content: bool = False,
) -> list[AgentRuntimeEvent]:
    """Convert one trace to observed calls plus clearly marked semantic hints.

    Arguments, return values, and exception messages are omitted unless the
    caller explicitly opts in.  Function names, timing, and source locations
    remain available in metadata-only mode.
    """

    classifications = classifications or {}
    anchor = datetime.now(timezone.utc)
    first_monotonic = result.events[0].timestamp if result.events else 0.0
    trace_id = stable_id("trace", run_id)
    source = EventSource(
        adapter="anthill.python.sys_settrace",
        adapter_version="0.1.0",
        framework="python",
        language="python",
        fidelity=SourceFidelity.NATIVE,
    )
    inferred_source = source.model_copy(update={"fidelity": SourceFidelity.INFERRED})
    privacy = Privacy(
        content=(
            ContentCapture.PLAINTEXT_OPT_IN
            if capture_content
            else ContentCapture.METADATA_ONLY
        ),
        contains_sensitive_data=capture_content,
    )

    normalized: list[AgentRuntimeEvent] = []
    run_start_id = stable_id("evt", run_id, "run.started")
    normalized.append(
        AgentRuntimeEvent(
            event_id=run_start_id,
            event_type=CoreEventType.RUN_STARTED,
            run_id=run_id,
            session_id=session_id,
            project_id=project_id,
            trace_id=trace_id,
            clock=EventClock(
                occurred_at=anchor,
                observed_at=anchor,
                source_seq=0,
            ),
            source=source,
            evidence=Evidence(level=EvidenceLevel.OBSERVED, confidence=1.0),
            summary=f"Started Python entry point {result.entry_point}",
            payload={"entry_point": result.entry_point},
            privacy=privacy,
        )
    )

    active_calls: list[dict] = []
    source_seq = 1
    for raw_index, raw in enumerate(result.events):
        occurred_at = anchor + timedelta(seconds=raw.timestamp - first_monotonic)
        event_id = stable_id(
            "evt", run_id, "trace", raw_index, raw.event_type, raw.qualified_name
        )
        subject = EntityRef(
            kind="code.function",
            id=raw.qualified_name,
            name=raw.function_name,
        )
        refs = [
            EvidenceRef(
                kind="source",
                uri=repository_uri(raw.filepath),
                line_start=max(raw.lineno, 1),
                label=raw.qualified_name,
            )
        ]

        if raw.event_type == "call":
            parent_span_id = active_calls[-1]["span_id"] if active_calls else None
            span_id = stable_id("span", run_id, raw_index, raw.qualified_name, length=16)
            causal_id = active_calls[-1]["start_event_id"] if active_calls else run_start_id
            payload = {
                "function_name": raw.function_name,
                "qualified_name": raw.qualified_name,
                "filepath": raw.filepath,
                "lineno": raw.lineno,
                "argument_names": sorted(raw.args.keys()),
                "argument_count": len(raw.args),
            }
            if capture_content:
                payload["arguments"] = raw.args
            observed_type = CoreEventType.CODE_CALL_STARTED
            active_calls.append(
                {
                    "qualified_name": raw.qualified_name,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id,
                    "start_event_id": event_id,
                }
            )
        else:
            frame_index = _find_active_frame(active_calls, raw.qualified_name)
            frame = active_calls[frame_index] if frame_index is not None else None
            span_id = frame["span_id"] if frame else None
            parent_span_id = frame["parent_span_id"] if frame else None
            causal_id = frame["start_event_id"] if frame else run_start_id
            if raw.event_type == "return":
                observed_type = CoreEventType.CODE_CALL_RETURNED
                payload = {
                    "function_name": raw.function_name,
                    "qualified_name": raw.qualified_name,
                    "filepath": raw.filepath,
                    "lineno": raw.lineno,
                    "has_return_value": raw.return_value is not None,
                }
                if capture_content:
                    payload["return_value"] = raw.return_value
                if frame_index is not None:
                    del active_calls[frame_index:]
            else:
                observed_type = CoreEventType.CODE_CALL_RAISED
                exception_type = (
                    raw.exception.split(":", 1)[0] if raw.exception else "Exception"
                )
                payload = {
                    "function_name": raw.function_name,
                    "qualified_name": raw.qualified_name,
                    "filepath": raw.filepath,
                    "lineno": raw.lineno,
                    "exception_type": exception_type,
                }
                if capture_content:
                    payload["exception"] = raw.exception

        measurements = {}
        if raw.duration_ms is not None:
            measurements["duration_ms"] = raw.duration_ms

        observed = AgentRuntimeEvent(
            event_id=event_id,
            event_type=observed_type,
            run_id=run_id,
            session_id=session_id,
            project_id=project_id,
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            causation_id=causal_id,
            subject=subject,
            clock=EventClock(
                occurred_at=occurred_at,
                observed_at=anchor,
                monotonic_ns=max(int(raw.timestamp * 1_000_000_000), 0),
                source_seq=source_seq,
            ),
            source=source.model_copy(update={"raw_event_ref": f"python-trace:{raw_index}"}),
            evidence=Evidence(
                level=EvidenceLevel.OBSERVED,
                confidence=1.0,
                refs=refs,
            ),
            summary=f"{raw.event_type.title()} {raw.qualified_name}",
            payload=payload,
            measurements=measurements,
            privacy=privacy,
        )
        normalized.append(observed)
        source_seq += 1

        classification = classifications.get(raw.qualified_name)
        semantic_event = _semantic_companion(
            observed,
            raw,
            classification,
            source=inferred_source,
            source_seq=source_seq,
            capture_content=capture_content,
            privacy=privacy,
        )
        if semantic_event is not None:
            normalized.append(semantic_event)
            source_seq += 1

    terminal_id = stable_id("evt", run_id, "run.completed")
    normalized.append(
        AgentRuntimeEvent(
            event_id=terminal_id,
            event_type=CoreEventType.RUN_COMPLETED,
            run_id=run_id,
            session_id=session_id,
            project_id=project_id,
            trace_id=trace_id,
            causation_id=(normalized[-1].event_id if normalized else run_start_id),
            clock=EventClock(
                occurred_at=anchor
                + timedelta(milliseconds=max(result.total_duration_ms, 0.0)),
                observed_at=anchor,
                source_seq=source_seq,
            ),
            source=source,
            evidence=Evidence(level=EvidenceLevel.OBSERVED, confidence=1.0),
            summary=("Python run completed" if result.success else "Python run failed"),
            payload={
                "status": "success" if result.success else "error",
                "event_count": len(result.events),
                **(
                    {"error_type": result.error.split(":", 1)[0]}
                    if result.error
                    else {}
                ),
                **({"error": result.error} if capture_content and result.error else {}),
            },
            measurements={"duration_ms": result.total_duration_ms},
            privacy=privacy,
        )
    )
    return normalized


def _find_active_frame(active: list[dict], qualified_name: str) -> int | None:
    for index in range(len(active) - 1, -1, -1):
        if active[index]["qualified_name"] == qualified_name:
            return index
    return None


def _semantic_companion(
    observed: AgentRuntimeEvent,
    raw: TraceEvent,
    classification: NodeClassification | None,
    *,
    source: EventSource,
    source_seq: int,
    capture_content: bool,
    privacy: Privacy,
) -> AgentRuntimeEvent | None:
    if classification is None or classification.node_type not in _SEMANTIC_EVENTS:
        return None
    semantic_type = _SEMANTIC_EVENTS[classification.node_type].get(raw.event_type)
    if semantic_type is None:
        return None
    confidence = min(max(float(classification.confidence), 0.0), 0.99)
    payload = {
        "semantic_type": classification.node_type,
        "function_name": raw.function_name,
        "qualified_name": raw.qualified_name,
        "classification_reason": classification.reason,
    }
    if capture_content and raw.event_type == "exception":
        payload["exception"] = raw.exception
    return AgentRuntimeEvent(
        event_id=stable_id(
            "evt", observed.run_id, "semantic", observed.event_id, semantic_type
        ),
        event_type=semantic_type,
        run_id=observed.run_id,
        session_id=observed.session_id,
        project_id=observed.project_id,
        trace_id=observed.trace_id,
        span_id=observed.span_id,
        parent_span_id=observed.parent_span_id,
        causation_id=observed.event_id,
        subject=observed.subject,
        clock=observed.clock.model_copy(update={"source_seq": source_seq}),
        source=source.model_copy(
            update={"raw_event_ref": observed.source.raw_event_ref}
        ),
        evidence=Evidence(
            level=EvidenceLevel.INFERRED,
            confidence=confidence,
            refs=observed.evidence.refs,
            derived_from=[observed.event_id],
            explanation=classification.reason,
        ),
        summary=f"Inferred {semantic_type} from {raw.qualified_name}",
        payload=payload,
        measurements=observed.measurements,
        privacy=privacy,
    )

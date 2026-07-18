"""OTLP JSON and OpenInference span normalizer.

The importer accepts the official OTLP JSON trace shape and deliberately keeps
the input semantic convention/version in every canonical event. Span facts are
observed; their conversion is source fidelity ``mapped``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterator

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


_CONTENT_KEYS = (
    "input.value",
    "output.value",
    "input.messages",
    "output.messages",
    "input_messages",
    "output_messages",
    "system_instructions",
    "message.content",
    "prompt",
    "tool.call.arguments",
    "tool.call.result",
    "retrieval.documents",
    "document.content",
    "authorization",
    "api_key",
    "apikey",
    "cookie",
    "secret",
)


@dataclass(frozen=True)
class OtlpSpan:
    span: dict[str, Any]
    attributes: dict[str, Any]
    resource: dict[str, Any]
    scope: dict[str, Any]
    schema_url: str | None

    @property
    def trace_id(self) -> str:
        return str(self.span.get("traceId", ""))

    @property
    def span_id(self) -> str:
        return str(self.span.get("spanId", ""))

    @property
    def parent_span_id(self) -> str | None:
        value = str(self.span.get("parentSpanId", ""))
        return value or None

    @property
    def start_ns(self) -> int:
        return _integer(self.span.get("startTimeUnixNano")) or 0

    @property
    def end_ns(self) -> int:
        return _integer(self.span.get("endTimeUnixNano")) or self.start_ns


class OtlpImportError(ValueError):
    pass


def otlp_json_to_events(
    payload: dict[str, Any],
    *,
    run_id: str,
    semantic_convention_version: str | None = None,
    capture_content: bool = False,
) -> list[AgentRuntimeEvent]:
    """Convert an OTLP JSON export request/file into canonical events."""

    spans = list(_iter_otlp_spans(payload))
    if not spans:
        raise OtlpImportError("OTLP payload contains no spans")
    if any(not span.trace_id or not span.span_id for span in spans):
        raise OtlpImportError("every OTLP span must contain traceId and spanId")

    observed_at = utc_now()
    first_start = min((span.start_ns for span in spans if span.start_ns), default=0)
    last_end = max((span.end_ns for span in spans if span.end_ns), default=first_start)
    start_time = _from_unix_ns(first_start, observed_at)
    end_time = _from_unix_ns(last_end, observed_at)
    root_error = any(_is_error(span.span.get("status")) for span in spans if not span.parent_span_id)
    conventions = {_convention_name(span.attributes) for span in spans}
    convention_name = conventions.pop() if len(conventions) == 1 else "mixed-otel-ai"
    first_resource = spans[0].resource
    service_name = _text(first_resource.get("service.name")) or "OTLP trace"

    manifest_id = stable_id("evt", run_id, "otlp", "manifest")
    run_start_id = stable_id("evt", run_id, "otlp", "run.started")
    boundary_source = _event_source(
        spans[0],
        semantic_convention=convention_name,
        semantic_convention_version=semantic_convention_version,
        raw_ref="otlp:export",
    )
    privacy = Privacy(
        content=(
            ContentCapture.PLAINTEXT_OPT_IN
            if capture_content
            else ContentCapture.METADATA_ONLY
        ),
        contains_sensitive_data=capture_content,
    )
    prefix = [
        AgentRuntimeEvent(
            event_id=manifest_id,
            event_type="manifest.snapshot",
            run_id=run_id,
            project_id=service_name,
            clock=EventClock(occurred_at=start_time, observed_at=observed_at),
            source=boundary_source,
            evidence=Evidence(level=EvidenceLevel.OBSERVED, confidence=1.0),
            summary=f"Imported {len(spans)} OTLP spans from {service_name}",
            payload={
                "title": service_name,
                "synthetic": False,
                "span_count": len(spans),
                "semantic_conventions": sorted(conventions | {convention_name}),
            },
            privacy=privacy,
        ),
        AgentRuntimeEvent(
            event_id=run_start_id,
            event_type="run.started",
            run_id=run_id,
            project_id=service_name,
            causation_id=manifest_id,
            clock=EventClock(occurred_at=start_time, observed_at=observed_at),
            source=boundary_source,
            evidence=Evidence(level=EvidenceLevel.OBSERVED, confidence=1.0),
            summary=f"OTLP run started: {service_name}",
            payload={"status": "running", "span_count": len(spans)},
            privacy=privacy,
        ),
    ]

    start_ids = {
        (span.trace_id, span.span_id): stable_id(
            "evt", run_id, "otlp", span.trace_id, span.span_id, "start"
        )
        for span in spans
    }
    span_events: list[AgentRuntimeEvent] = []
    for span in spans:
        span_events.extend(
            _span_to_events(
                span,
                run_id=run_id,
                run_start_id=run_start_id,
                start_ids=start_ids,
                semantic_convention_version=semantic_convention_version,
                observed_at=observed_at,
                capture_content=capture_content,
            )
        )
    span_events.sort(
        key=lambda event: (
            event.clock.occurred_at,
            0 if event.event_type.endswith((".started", ".dispatched")) else 1,
            event.event_id,
        )
    )

    latest_event_id = span_events[-1].event_id if span_events else run_start_id
    terminal = AgentRuntimeEvent(
        event_id=stable_id("evt", run_id, "otlp", "run.completed"),
        event_type="run.completed",
        run_id=run_id,
        project_id=service_name,
        causation_id=latest_event_id,
        clock=EventClock(occurred_at=end_time, observed_at=observed_at),
        source=boundary_source,
        evidence=Evidence(level=EvidenceLevel.OBSERVED, confidence=1.0),
        summary=f"OTLP run {'failed' if root_error else 'completed'}: {service_name}",
        payload={"status": "error" if root_error else "success", "span_count": len(spans)},
        privacy=privacy,
    )

    events = prefix + span_events + [terminal]
    for source_seq, event in enumerate(events):
        events[source_seq] = event.model_copy(
            update={"clock": event.clock.model_copy(update={"source_seq": source_seq})}
        )
    return events


def _span_to_events(
    span: OtlpSpan,
    *,
    run_id: str,
    run_start_id: str,
    start_ids: dict[tuple[str, str], str],
    semantic_convention_version: str | None,
    observed_at: datetime,
    capture_content: bool,
) -> list[AgentRuntimeEvent]:
    category = _semantic_category(span.attributes)
    start_type, success_type, failure_type = _event_types(category)
    start_event_id = start_ids[(span.trace_id, span.span_id)]
    terminal_event_id = stable_id(
        "evt", run_id, "otlp", span.trace_id, span.span_id, "end"
    )
    parent_start = (
        start_ids.get((span.trace_id, span.parent_span_id))
        if span.parent_span_id
        else None
    )
    causation_id = parent_start or run_start_id
    error = _is_error(span.span.get("status"))
    terminal_type = failure_type if error else success_type
    subject = _subject(span, category)
    session_id = _first_text(
        span.attributes,
        "session.id",
        "conversation.id",
        "gen_ai.conversation.id",
    )
    agent_id = _first_text(
        span.attributes,
        "gen_ai.agent.id",
        "agent.id",
    )
    convention_name = _convention_name(span.attributes)
    raw_ref = f"otlp://{span.trace_id}/{span.span_id}"
    source = _event_source(
        span,
        semantic_convention=convention_name,
        semantic_convention_version=(
            semantic_convention_version or _schema_version(span.schema_url)
        ),
        raw_ref=raw_ref,
    )
    safe_attributes, redacted = _safe_attributes(
        span.attributes, capture_content=capture_content
    )
    safe_resource, resource_redacted = _safe_attributes(
        span.resource, capture_content=capture_content
    )
    redacted.extend(f"resource.{key}" for key in resource_redacted)
    privacy = Privacy(
        content=(
            ContentCapture.PLAINTEXT_OPT_IN
            if capture_content
            else ContentCapture.METADATA_ONLY
        ),
        contains_sensitive_data=capture_content,
        redacted_fields=sorted(set(redacted)),
    )
    refs = [EvidenceRef(kind="trace", uri=raw_ref, label=str(span.span.get("name", "span")))]
    links = _span_links(span.span.get("links", []))
    common = {
        "run_id": run_id,
        "session_id": session_id,
        "project_id": _text(span.resource.get("service.name")),
        "agent_id": agent_id,
        "trace_id": span.trace_id,
        "span_id": span.span_id,
        "parent_span_id": span.parent_span_id,
        "subject": subject,
        "source": source,
        "evidence": Evidence(
            level=EvidenceLevel.OBSERVED,
            confidence=1.0,
            refs=refs,
            explanation=f"Deterministically mapped from {convention_name} span attributes",
        ),
        "privacy": privacy,
        "extensions": {
            "otel.attributes": safe_attributes,
            "otel.resource": safe_resource,
            "otel.scope": span.scope,
        },
    }
    payload = {
        "span_name": str(span.span.get("name", "")),
        "span_kind": span.span.get("kind"),
        "semantic_category": category,
        "provider": _first_text(span.attributes, "gen_ai.provider.name", "llm.provider", "llm.system"),
        "model": _first_text(span.attributes, "gen_ai.response.model", "gen_ai.request.model", "llm.model_name"),
        "operation": _text(span.attributes.get("gen_ai.operation.name")),
        "status_code": _status_code(span.span.get("status")),
    }
    payload = {key: value for key, value in payload.items() if value is not None}
    start_event = AgentRuntimeEvent(
        event_id=start_event_id,
        event_type=start_type,
        causation_id=causation_id,
        links=links,
        clock=EventClock(
            occurred_at=_from_unix_ns(span.start_ns, observed_at),
            observed_at=observed_at,
        ),
        summary=f"{start_type}: {subject.name or subject.id}",
        payload=payload,
        measurements={},
        **common,
    )
    terminal_payload = dict(payload)
    if error:
        terminal_payload["error_type"] = _first_text(
            span.attributes, "error.type", "exception.type"
        ) or "otel.status.error"
        if capture_content:
            message = _text((span.span.get("status") or {}).get("message"))
            if message:
                terminal_payload["error_message"] = message
    terminal_measurements = _measurements(span, include_duration=True)
    terminal_common = {
        **common,
        "extensions": {
            **common["extensions"],
            **_measurement_semantics(
                category,
                f"otel-span:{span.trace_id}:{span.span_id}",
                terminal_measurements,
            ),
        },
    }
    terminal_event = AgentRuntimeEvent(
        event_id=terminal_event_id,
        event_type=terminal_type,
        causation_id=start_event_id,
        clock=EventClock(
            occurred_at=_from_unix_ns(span.end_ns, observed_at),
            observed_at=observed_at,
        ),
        summary=f"{terminal_type}: {subject.name or subject.id}",
        payload=terminal_payload,
        measurements=terminal_measurements,
        **terminal_common,
    )
    return [start_event, terminal_event]


def _iter_otlp_spans(payload: dict[str, Any]) -> Iterator[OtlpSpan]:
    resource_spans = payload.get("resourceSpans")
    if not isinstance(resource_spans, list):
        raise OtlpImportError("expected OTLP JSON field resourceSpans")
    for resource_group in resource_spans:
        resource = _attributes((resource_group.get("resource") or {}).get("attributes", []))
        group_schema = _text(resource_group.get("schemaUrl"))
        scope_groups = resource_group.get("scopeSpans") or resource_group.get(
            "instrumentationLibrarySpans"
        ) or []
        for scope_group in scope_groups:
            scope = scope_group.get("scope") or scope_group.get("instrumentationLibrary") or {}
            scope_info = {
                "name": scope.get("name"),
                "version": scope.get("version"),
                "attributes": _attributes(scope.get("attributes", [])),
            }
            schema_url = _text(scope_group.get("schemaUrl")) or group_schema
            for raw_span in scope_group.get("spans", []):
                yield OtlpSpan(
                    span=raw_span,
                    attributes=_attributes(raw_span.get("attributes", [])),
                    resource=resource,
                    scope=scope_info,
                    schema_url=schema_url,
                )


def _attributes(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    result: dict[str, Any] = {}
    for item in raw or []:
        if isinstance(item, dict) and "key" in item:
            result[str(item["key"])] = _any_value(item.get("value"))
    return result


def _any_value(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    for key in ("stringValue", "boolValue", "intValue", "doubleValue", "bytesValue"):
        if key in value:
            raw = value[key]
            return _integer(raw) if key == "intValue" else raw
    if "arrayValue" in value:
        return [_any_value(item) for item in (value["arrayValue"] or {}).get("values", [])]
    if "kvlistValue" in value:
        return _attributes((value["kvlistValue"] or {}).get("values", []))
    return value


def _semantic_category(attributes: dict[str, Any]) -> str:
    openinference_kind = _text(attributes.get("openinference.span.kind")).upper()
    if openinference_kind:
        mapping = {
            "LLM": "model",
            "TOOL": "tool",
            "RETRIEVER": "retrieval",
            "RERANKER": "reranker",
            "EMBEDDING": "embedding",
            "AGENT": "agent",
            "CHAIN": "agent",
            "GUARDRAIL": "guardrail",
            "EVALUATOR": "evaluation",
            "PROMPT": "prompt",
        }
        return mapping.get(openinference_kind, "telemetry")
    operation = _text(attributes.get("gen_ai.operation.name")).lower()
    if operation in {"invoke_agent", "invoke_workflow", "create_agent"}:
        return "agent"
    if operation == "execute_tool":
        return "tool"
    if operation in {"embeddings", "embedding"}:
        return "embedding"
    if operation or "gen_ai.request.model" in attributes:
        return "model"
    return "telemetry"


def _event_types(category: str) -> tuple[str, str, str]:
    return {
        "model": ("model.request.dispatched", "model.response.completed", "model.failed"),
        "tool": ("tool.execution.started", "tool.execution.succeeded", "tool.execution.failed"),
        "retrieval": ("retrieval.search.started", "retrieval.search.completed", "error.raised"),
        "reranker": ("retrieval.rerank.started", "retrieval.rerank.completed", "error.raised"),
        "embedding": ("embedding.started", "embedding.completed", "error.raised"),
        "agent": ("agent.step.started", "agent.step.completed", "error.raised"),
        "guardrail": ("guardrail.started", "guardrail.completed", "guardrail.failed"),
        "evaluation": ("evaluation.started", "evaluation.completed", "evaluation.failed"),
        "prompt": ("context.assembly.started", "context.assembly.completed", "error.raised"),
        "telemetry": ("telemetry.span.started", "telemetry.span.completed", "error.raised"),
    }[category]


def _subject(span: OtlpSpan, category: str) -> EntityRef:
    name = str(span.span.get("name") or category)
    identifier = span.span_id
    kind = {
        "model": "model.call",
        "tool": "tool.call",
        "retrieval": "retrieval",
        "reranker": "retrieval.reranker",
        "embedding": "embedding",
        "agent": "agent",
        "guardrail": "guardrail",
        "evaluation": "evaluation",
        "prompt": "context.assembly",
        "telemetry": "telemetry.span",
    }[category]
    if category == "tool":
        name = _first_text(span.attributes, "gen_ai.tool.name", "tool.name") or name
        identifier = _first_text(span.attributes, "gen_ai.tool.call.id") or identifier
    elif category == "agent":
        name = _first_text(span.attributes, "gen_ai.agent.name", "agent.name") or name
        identifier = _first_text(span.attributes, "gen_ai.agent.id", "agent.id") or identifier
    elif category == "model":
        name = _first_text(
            span.attributes,
            "gen_ai.response.model",
            "gen_ai.request.model",
            "llm.model_name",
        ) or name
    return EntityRef(kind=kind, id=identifier, name=name)


def _measurements(span: OtlpSpan, *, include_duration: bool) -> dict[str, int | float]:
    attributes = span.attributes
    result: dict[str, int | float] = {}
    mappings = {
        "input_tokens": ("gen_ai.usage.input_tokens", "llm.token_count.prompt"),
        "output_tokens": ("gen_ai.usage.output_tokens", "llm.token_count.completion"),
        "cached_tokens": ("gen_ai.usage.cache_read.input_tokens", "llm.token_count.cached"),
        "total_tokens": ("llm.token_count.total",),
        "cost_usd": ("llm.cost.total",),
    }
    for target, source_keys in mappings.items():
        value = _first_number(attributes, *source_keys)
        if value is not None:
            result[target] = value
    if include_duration and span.end_ns >= span.start_ns:
        result["duration_ms"] = (span.end_ns - span.start_ns) / 1_000_000
    return result


def _measurement_semantics(
    category: str,
    owner_id: str,
    measurements: dict[str, int | float],
) -> dict[str, Any]:
    semantics: dict[str, MeasurementSemantics] = {}
    if category == "model":
        token_keys = {
            "input_tokens": "model_call.input_tokens",
            "output_tokens": "model_call.output_tokens",
            "cached_tokens": "model_call.cached_tokens",
            "total_tokens": "model_call.total_tokens",
        }
        for measurement_key, aggregate_key in token_keys.items():
            if measurement_key in measurements:
                semantics[measurement_key] = MeasurementSemantics(
                    aggregate_key=aggregate_key,
                    unit="tokens",
                    scope="model_call",
                    aggregation="sum",
                    temporality="cumulative",
                    owner_id=owner_id,
                )
        if "duration_ms" in measurements:
            semantics["duration_ms"] = MeasurementSemantics(
                aggregate_key="model_call.duration_ms",
                unit="ms",
                scope="model_call",
                aggregation="sum",
                temporality="cumulative",
                owner_id=owner_id,
            )
    elif category == "tool" and "duration_ms" in measurements:
        semantics["duration_ms"] = MeasurementSemantics(
            aggregate_key="tool.duration_ms",
            unit="ms",
            scope="tool_call",
            aggregation="sum",
            temporality="cumulative",
            owner_id=owner_id,
        )
    return measurement_semantics_extension(semantics) if semantics else {}


def _event_source(
    span: OtlpSpan,
    *,
    semantic_convention: str,
    semantic_convention_version: str | None,
    raw_ref: str,
) -> EventSource:
    framework = _first_text(
        span.resource,
        "service.name",
        "telemetry.sdk.name",
    )
    framework_version = _first_text(
        span.resource,
        "service.version",
        "telemetry.sdk.version",
    )
    return EventSource(
        adapter="anthill.otlp-json",
        adapter_version="0.1.0",
        framework=framework,
        framework_version=framework_version,
        language=_text(span.resource.get("telemetry.sdk.language")),
        fidelity=SourceFidelity.MAPPED,
        semantic_convention=semantic_convention,
        semantic_convention_version=semantic_convention_version,
        raw_event_ref=raw_ref,
    )


def _convention_name(attributes: dict[str, Any]) -> str:
    if "openinference.span.kind" in attributes:
        return "openinference"
    if any(key.startswith("gen_ai.") for key in attributes):
        return "opentelemetry.gen_ai"
    return "opentelemetry"


def _safe_attributes(
    attributes: dict[str, Any], *, capture_content: bool
) -> tuple[dict[str, Any], list[str]]:
    safe: dict[str, Any] = {}
    redacted: list[str] = []
    for key, value in attributes.items():
        lowered = key.lower()
        if not capture_content and any(fragment in lowered for fragment in _CONTENT_KEYS):
            redacted.append(key)
            continue
        if not capture_content and isinstance(value, str) and len(value) > 1_000:
            redacted.append(key)
            safe[key] = f"<omitted string length={len(value)}>"
            continue
        safe[key] = value
    return safe, redacted


def _span_links(raw_links: Any) -> list[EventLink]:
    links: list[EventLink] = []
    for raw in raw_links or []:
        trace_id = _text(raw.get("traceId"))
        span_id = _text(raw.get("spanId"))
        if trace_id or span_id:
            links.append(
                EventLink(
                    type=LinkType.FOLLOWS_FROM,
                    trace_id=trace_id or None,
                    span_id=span_id or None,
                )
            )
    return links


def _is_error(status: Any) -> bool:
    code = _status_code(status)
    return code in {2, "2", "STATUS_CODE_ERROR", "ERROR"}


def _status_code(status: Any) -> Any:
    return status.get("code") if isinstance(status, dict) else status


def _from_unix_ns(value: int, fallback: datetime) -> datetime:
    if not value:
        return fallback
    return datetime.fromtimestamp(value / 1_000_000_000, tz=timezone.utc)


def _schema_version(schema_url: str | None) -> str | None:
    if not schema_url:
        return None
    candidate = schema_url.rstrip("/").rsplit("/", 1)[-1]
    return candidate[:64] or None


def _integer(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _first_text(attributes: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = _text(attributes.get(key))
        if value:
            return value
    return None


def _first_number(attributes: dict[str, Any], *keys: str) -> int | float | None:
    for key in keys:
        value = _number(attributes.get(key))
        if value is not None:
            return value
    return None

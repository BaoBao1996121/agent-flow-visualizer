"""Deterministic event-to-world projection.

This module is the contract between observability facts and visual metaphor.
It knows that a model call belongs in the model chamber, for example, but it
contains no pixels, animation timers, or browser state.  Replaying the same
ordered events with the same reducer version always produces the same world.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field

from ..schema import AgentRuntimeEvent, EvidenceLevel


REDUCER_VERSION = "0.2.0"
MAX_RECENT_EVENTS = 80
MAX_ERRORS = 100


ZONE_BY_FAMILY = {
    "run": "control",
    "agent": "control",
    "task": "control",
    "decision": "control",
    "policy": "control",
    "model": "model_engine",
    "tool": "tool_workshop",
    "retrieval": "retrieval_depot",
    "embedding": "retrieval_depot",
    "memory": "memory_vault",
    "context": "context_assembly",
    "compaction": "compaction_plant",
    "handoff": "handoff_bridge",
    "checkpoint": "checkpoint_station",
    "artifact": "artifact_foundry",
    "human": "inspection_gate",
    "evaluation": "inspection_gate",
    "guardrail": "inspection_gate",
    "error": "incident_bay",
    "usage": "meter_room",
    "cost": "meter_room",
    "budget": "meter_room",
    "manifest": "control",
    "code": "code_archive",
    "semantic": "control",
}


def _zone_for(event_type: str) -> str:
    return ZONE_BY_FAMILY.get(event_type.split(".", 1)[0], "unknown_fog")


class ProjectionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class TruthBadge(ProjectionModel):
    level: EvidenceLevel
    confidence: float = Field(ge=0.0, le=1.0)
    source_fidelity: str
    source_adapter: str


class WorldEntity(ProjectionModel):
    id: str
    kind: str
    name: str
    zone: str
    status: str = "known"
    active: bool = False
    first_event_id: str
    last_event_id: str
    first_seq: int
    last_seq: int
    truth: TruthBadge
    event_count: int = 0
    metrics: dict[str, int | float | str | bool | None] = Field(default_factory=dict)
    attributes: dict[str, Any] = Field(default_factory=dict)


class ContextState(ProjectionModel):
    status: str = "idle"
    budget_tokens: int | None = None
    used_tokens: int | None = None
    utilization: float | None = None
    overflow: bool = False
    policy: str | None = None
    items: dict[str, dict[str, Any]] = Field(default_factory=dict)
    last_event_id: str | None = None


class MemoryState(ProjectionModel):
    working: int = 0
    episodic: int = 0
    semantic: int = 0
    unknown: int = 0
    hits: int = 0
    misses: int = 0
    writes: int = 0
    evictions: int = 0
    conflicts: int = 0
    items: dict[str, dict[str, Any]] = Field(default_factory=dict)
    last_event_id: str | None = None


class CompactionJob(ProjectionModel):
    id: str
    status: str
    trigger: str | None = None
    policy: str | None = None
    tokens_before: int | None = None
    tokens_after: int | None = None
    tokens_removed: int | None = None
    reduction_ratio: float | None = None
    lossy: bool | None = None
    summary_hash: str | None = None
    kept_refs: list[str] = Field(default_factory=list)
    removed_refs: list[str] = Field(default_factory=list)
    first_event_id: str
    last_event_id: str


class ErrorRecord(ProjectionModel):
    event_id: str
    seq: int
    event_type: str
    subject_id: str | None = None
    error_type: str | None = None
    status: str
    summary: str | None = None
    truth: TruthBadge


class RecentEvent(ProjectionModel):
    event_id: str
    seq: int
    event_type: str
    zone: str
    subject_id: str | None
    summary: str | None
    truth: TruthBadge
    causation_id: str | None = None


class WorldState(ProjectionModel):
    reducer_version: str = REDUCER_VERSION
    run_id: str
    cursor_seq: int = -1
    cursor_event_id: str | None = None
    run_status: str = "unknown"
    started_at: str | None = None
    completed_at: str | None = None
    event_count: int = 0

    entities: dict[str, WorldEntity] = Field(default_factory=dict)
    zone_activity: dict[str, int] = Field(default_factory=dict)
    event_type_counts: dict[str, int] = Field(default_factory=dict)
    evidence_counts: dict[str, int] = Field(default_factory=dict)
    source_adapters: dict[str, int] = Field(default_factory=dict)
    frameworks: list[str] = Field(default_factory=list)

    context: ContextState = Field(default_factory=ContextState)
    memory: MemoryState = Field(default_factory=MemoryState)
    compactions: dict[str, CompactionJob] = Field(default_factory=dict)
    errors: list[ErrorRecord] = Field(default_factory=list)
    recent_events: list[RecentEvent] = Field(default_factory=list)

    totals: dict[str, int | float] = Field(default_factory=dict)
    active_event_ids: list[str] = Field(default_factory=list)
    unknown_event_types: list[str] = Field(default_factory=list)

    @classmethod
    def empty(cls, run_id: str) -> "WorldState":
        return cls(run_id=run_id)


def truth_badge(event: AgentRuntimeEvent) -> TruthBadge:
    return TruthBadge(
        level=event.evidence.level,
        confidence=event.evidence.confidence,
        source_fidelity=event.source.fidelity.value,
        source_adapter=event.source.adapter,
    )


def reduce_world(state: WorldState, event: AgentRuntimeEvent) -> WorldState:
    """Return a new state after applying one event.

    The input model is never mutated, which makes checkpoint verification and
    deterministic time travel straightforward.
    """

    if state.run_id != event.run_id:
        raise ValueError(f"cannot project event for run {event.run_id!r} into {state.run_id!r}")
    seq = event.clock.ingest_seq
    if seq is None:
        raise ValueError("world projection requires store-stamped ingest_seq")
    if seq <= state.cursor_seq:
        raise ValueError(f"event sequence {seq} is not after current cursor {state.cursor_seq}")

    next_state = state.model_copy(deep=True)
    zone = _zone_for(event.event_type)
    if event.subject and event.subject.kind == "human.interrupt":
        zone = "inspection_gate"
    family, _, action = event.event_type.partition(".")

    next_state.cursor_seq = seq
    next_state.cursor_event_id = event.event_id
    next_state.event_count += 1
    next_state.event_type_counts[event.event_type] = (
        next_state.event_type_counts.get(event.event_type, 0) + 1
    )
    evidence_key = event.evidence.level.value
    next_state.evidence_counts[evidence_key] = next_state.evidence_counts.get(evidence_key, 0) + 1
    next_state.source_adapters[event.source.adapter] = (
        next_state.source_adapters.get(event.source.adapter, 0) + 1
    )
    if event.source.framework and event.source.framework not in next_state.frameworks:
        next_state.frameworks.append(event.source.framework)
        next_state.frameworks.sort()

    _update_run(next_state, event)
    _update_entity(next_state, event, zone, action)
    _update_zone_activity(next_state, event, zone)
    _update_context(next_state, event)
    _update_memory(next_state, event)
    _update_compaction(next_state, event)
    _update_errors(next_state, event)
    _update_totals(next_state, event)
    _append_recent(next_state, event, zone)

    if zone == "unknown_fog" and event.event_type not in next_state.unknown_event_types:
        next_state.unknown_event_types.append(event.event_type)
        next_state.unknown_event_types.sort()

    return next_state


def project_world(
    events: Iterable[AgentRuntimeEvent],
    *,
    run_id: str,
    at_seq: int | None = None,
    initial_state: WorldState | None = None,
) -> WorldState:
    """Project an ordered event stream, optionally stopping at a time cursor."""

    state = initial_state or WorldState.empty(run_id)
    for event in events:
        seq = event.clock.ingest_seq
        if at_seq is not None and seq is not None and seq > at_seq:
            break
        state = reduce_world(state, event)
    return state


def _update_run(state: WorldState, event: AgentRuntimeEvent) -> None:
    if event.event_type == "run.started":
        state.run_status = "running"
        state.started_at = event.clock.occurred_at.isoformat()
    elif event.event_type == "run.paused":
        state.run_status = "paused"
    elif event.event_type == "run.resumed":
        state.run_status = "running"
    elif event.event_type == "run.forked":
        state.run_status = "running"
        state.completed_at = None
    elif event.event_type == "run.completed":
        status = str(event.payload.get("status", "completed"))
        state.run_status = "completed" if status == "success" else status
        state.completed_at = event.clock.occurred_at.isoformat()
    elif event.event_type == "run.cancelled":
        state.run_status = "cancelled"
        state.completed_at = event.clock.occurred_at.isoformat()
    elif event.event_type == "error.fatal":
        state.run_status = "failed"
        state.completed_at = event.clock.occurred_at.isoformat()


def _entity_identity(event: AgentRuntimeEvent) -> tuple[str, str, str] | None:
    if event.subject:
        return event.subject.id, event.subject.kind, event.subject.name or event.subject.id
    if event.agent_id:
        return event.agent_id, "agent", event.agent_id
    if event.task_id:
        return event.task_id, "task", event.task_id
    if event.span_id:
        family = event.event_type.split(".", 1)[0]
        if family in {"model", "tool", "retrieval", "handoff", "compaction"}:
            return event.span_id, family, event.span_id
    return None


def _entity_identities(state: WorldState, event: AgentRuntimeEvent) -> list[tuple[str, str, str]]:
    identities: list[tuple[str, str, str]] = []
    primary = _entity_identity(event)
    if primary is not None:
        identities.append(primary)
    if event.agent_id and all(item[0] != event.agent_id for item in identities):
        existing = state.entities.get(event.agent_id)
        identities.append(
            (
                event.agent_id,
                "agent",
                existing.name if existing else event.agent_id,
            )
        )
    return identities


def _status_for(event_type: str, payload: dict[str, Any]) -> tuple[str, bool]:
    terminal_success = (
        ".completed",
        ".succeeded",
        ".accepted",
        ".granted",
        ".committed",
        ".restored",
        ".created",
    )
    terminal_error = (
        ".failed",
        ".rejected",
        ".cancelled",
        ".timeout",
        ".invalidated",
    )
    active_markers = (
        ".started",
        ".requested",
        ".dispatched",
        ".progress",
        ".first_chunk",
        ".chunk",
        ".triggered",
        ".proposed",
    )
    if event_type == "human.interrupt":
        return str(payload.get("status", "waiting")), False
    if event_type == "agent.state.changed" or event_type == "task.state.changed":
        return str(payload.get("state", payload.get("status", "changed"))), False
    if event_type.endswith(terminal_error):
        return "error", False
    if event_type.endswith(terminal_success):
        return "completed", False
    if event_type.endswith(active_markers):
        return event_type.rsplit(".", 1)[-1], True
    return event_type.rsplit(".", 1)[-1], False


def _update_entity(state: WorldState, event: AgentRuntimeEvent, zone: str, action: str) -> None:
    identities = _entity_identities(state, event)
    if not identities:
        return
    seq = event.clock.ingest_seq
    assert seq is not None
    status, active = _status_for(event.event_type, event.payload)
    badge = truth_badge(event)
    previous_active_event_ids: set[str] = set()
    for entity_id, kind, name in identities:
        entity = state.entities.get(entity_id)
        if entity and entity.active:
            previous_active_event_ids.add(entity.last_event_id)
        if entity is None:
            entity = WorldEntity(
                id=entity_id,
                kind=kind,
                name=name,
                zone=zone,
                status=status,
                active=active,
                first_event_id=event.event_id,
                last_event_id=event.event_id,
                first_seq=seq,
                last_seq=seq,
                truth=badge,
                event_count=1,
                attributes=(
                    event.subject.attributes
                    if event.subject and event.subject.id == entity_id
                    else {}
                ),
            )
            state.entities[entity_id] = entity
        else:
            if (
                entity.kind == "human.interrupt"
                and entity.status == "waiting"
                and event.event_type
                in {"langgraph.interrupt.reobserved", "human.interrupt.snapshot"}
            ):
                status = entity.status
                active = entity.active
            entity.zone = zone
            entity.status = status
            entity.active = active
            entity.last_event_id = event.event_id
            entity.last_seq = seq
            entity.truth = badge
            entity.event_count += 1
            if event.subject and event.subject.id == entity_id:
                entity.name = event.subject.name or entity.name
                entity.attributes.update(event.subject.attributes)
        for key, value in event.measurements.items():
            entity.metrics[key] = value

    if active:
        if event.event_id not in state.active_event_ids:
            state.active_event_ids.append(event.event_id)
    else:
        state.active_event_ids = [
            item
            for item in state.active_event_ids
            if item not in ({event.causation_id} | previous_active_event_ids)
        ]


def _update_zone_activity(state: WorldState, event: AgentRuntimeEvent, zone: str) -> None:
    # Activity is a projection of currently active entities, not a counter of
    # start-like event names. Recomputing prevents a request/stream/response
    # sequence from leaving phantom workers behind after completion.
    counts: Counter[str] = Counter(
        entity.zone for entity in state.entities.values() if entity.active
    )
    state.zone_activity = dict(counts)


def _number(payload: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return int(value)
    return None


def _update_context(state: WorldState, event: AgentRuntimeEvent) -> None:
    if not event.event_type.startswith("context."):
        return
    ctx = state.context
    ctx.last_event_id = event.event_id
    payload = event.payload
    if event.event_type == "context.assembly.started":
        ctx.status = "assembling"
    elif event.event_type == "context.assembly.completed":
        ctx.status = "ready"
    elif event.event_type == "context.overflow.detected":
        ctx.status = "overflow"
        ctx.overflow = True
    elif event.event_type == "context.policy.applied":
        ctx.policy = str(payload.get("policy", payload.get("name", "unknown")))
    elif event.event_type == "context.item.added":
        item_id = event.subject.id if event.subject else str(payload.get("item_id", event.event_id))
        ctx.items[item_id] = {
            "status": "included",
            "source": payload.get("source"),
            "token_count": _number(payload, "token_count", "tokens"),
            "event_id": event.event_id,
        }
    elif event.event_type in {"context.item.removed", "context.item.truncated"}:
        item_id = event.subject.id if event.subject else str(payload.get("item_id", ""))
        if item_id:
            item = ctx.items.setdefault(item_id, {})
            item.update(
                {
                    "status": "removed" if event.event_type.endswith("removed") else "truncated",
                    "event_id": event.event_id,
                }
            )

    budget = _number(payload, "budget_tokens", "token_budget", "capacity_tokens")
    used = _number(payload, "used_tokens", "total_tokens", "tokens_used")
    if budget is not None:
        ctx.budget_tokens = budget
    if used is not None:
        ctx.used_tokens = used
    if ctx.budget_tokens and ctx.used_tokens is not None:
        ctx.utilization = min(ctx.used_tokens / ctx.budget_tokens, 10.0)
        if event.event_type == "context.budget.updated" and ctx.used_tokens <= ctx.budget_tokens:
            ctx.overflow = False
            ctx.status = "within_budget"


def _memory_layer(payload: dict[str, Any]) -> str:
    value = str(payload.get("layer", payload.get("memory_type", "unknown"))).lower()
    return value if value in {"working", "episodic", "semantic"} else "unknown"


def _update_memory(state: WorldState, event: AgentRuntimeEvent) -> None:
    if not event.event_type.startswith("memory."):
        return
    memory = state.memory
    memory.last_event_id = event.event_id
    item_id = ""
    if event.subject and event.subject.kind.startswith("memory"):
        item_id = event.subject.id
    elif event.payload.get("memory_id"):
        item_id = str(event.payload["memory_id"])
    layer = _memory_layer(event.payload)
    action = event.event_type.split(".")[-1]

    if action == "hit":
        memory.hits += 1
    elif action == "miss":
        memory.misses += 1
    elif action == "written":
        memory.writes += 1
        setattr(memory, layer, getattr(memory, layer) + 1)
    elif action == "evicted":
        memory.evictions += 1
        setattr(memory, layer, max(getattr(memory, layer) - 1, 0))
    elif action == "deleted":
        setattr(memory, layer, max(getattr(memory, layer) - 1, 0))
    elif action == "conflict.detected" or event.event_type == "memory.conflict.detected":
        memory.conflicts += 1

    if item_id:
        item = memory.items.setdefault(item_id, {})
        item.update(
            {
                "layer": layer,
                "status": action,
                "last_event_id": event.event_id,
                "score": event.payload.get("score"),
            }
        )


def _compaction_id(event: AgentRuntimeEvent) -> str:
    if event.subject:
        return event.subject.id
    return str(
        event.payload.get("compaction_id") or event.span_id or event.correlation_id or "current"
    )


def _update_compaction(state: WorldState, event: AgentRuntimeEvent) -> None:
    if not event.event_type.startswith("compaction."):
        return
    job_id = _compaction_id(event)
    action = event.event_type.split(".")[-1]
    status = {
        "triggered": "queued",
        "started": "running",
        "created": "summarizing",
        "replaced": "replacing",
        "completed": "completed",
        "failed": "failed",
    }.get(action, action)
    payload = event.payload
    job = state.compactions.get(job_id)
    if job is None:
        job = CompactionJob(
            id=job_id,
            status=status,
            first_event_id=event.event_id,
            last_event_id=event.event_id,
        )
        state.compactions[job_id] = job
    job.status = status
    job.last_event_id = event.event_id
    job.trigger = str(payload["trigger"]) if payload.get("trigger") is not None else job.trigger
    job.policy = str(payload["policy"]) if payload.get("policy") is not None else job.policy
    job.tokens_before = _number(payload, "tokens_before", "before_tokens") or job.tokens_before
    job.tokens_after = _number(payload, "tokens_after", "after_tokens") or job.tokens_after
    job.summary_hash = (
        str(payload["summary_hash"]) if payload.get("summary_hash") else job.summary_hash
    )
    if isinstance(payload.get("lossy"), bool):
        job.lossy = payload["lossy"]
    if isinstance(payload.get("kept_refs"), list):
        job.kept_refs = [str(item) for item in payload["kept_refs"]]
    if isinstance(payload.get("removed_refs"), list):
        job.removed_refs = [str(item) for item in payload["removed_refs"]]
    if job.tokens_before is not None and job.tokens_after is not None:
        job.tokens_removed = max(job.tokens_before - job.tokens_after, 0)
        if job.tokens_before > 0:
            job.reduction_ratio = job.tokens_removed / job.tokens_before


def _update_errors(state: WorldState, event: AgentRuntimeEvent) -> None:
    family = event.event_type.split(".", 1)[0]
    failed = event.event_type.endswith((".failed", ".timeout", ".rejected"))
    if family != "error" and not failed:
        return
    if event.event_type == "error.recovered":
        recovered_id = event.payload.get("recovered_event_id")
        subject_id = event.subject.id if event.subject else None
        for record in state.errors:
            if record.status != "open":
                continue
            if recovered_id and record.event_id == recovered_id:
                record.status = "recovered"
            elif subject_id and record.subject_id == subject_id:
                record.status = "recovered"
        return
    payload_status = str(event.payload.get("status", ""))
    is_snapshot = event.event_type.endswith((".snapshot", "_snapshot")) or payload_status in {
        "snapshot",
        "failed_in_checkpoint_snapshot",
    }
    status = "snapshot" if is_snapshot else "open"
    record = ErrorRecord(
        event_id=event.event_id,
        seq=event.clock.ingest_seq or 0,
        event_type=event.event_type,
        subject_id=event.subject.id if event.subject else None,
        error_type=(
            str(event.payload.get("error_type", event.payload.get("exception_type")))
            if event.payload.get("error_type", event.payload.get("exception_type"))
            else None
        ),
        status=status,
        summary=event.summary,
        truth=truth_badge(event),
    )
    state.errors.append(record)
    if len(state.errors) > MAX_ERRORS:
        state.errors = state.errors[-MAX_ERRORS:]


def _update_totals(state: WorldState, event: AgentRuntimeEvent) -> None:
    for key, value in event.measurements.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        if key.endswith("_total") or key in {
            "input_tokens",
            "output_tokens",
            "cached_tokens",
            "cost_usd",
        }:
            state.totals[key] = state.totals.get(key, 0) + value
        elif key in {"duration_ms", "latency_ms"}:
            state.totals[f"{key}_sum"] = state.totals.get(f"{key}_sum", 0) + value


def _append_recent(state: WorldState, event: AgentRuntimeEvent, zone: str) -> None:
    state.recent_events.append(
        RecentEvent(
            event_id=event.event_id,
            seq=event.clock.ingest_seq or 0,
            event_type=event.event_type,
            zone=zone,
            subject_id=event.subject.id if event.subject else None,
            summary=event.summary,
            truth=truth_badge(event),
            causation_id=event.causation_id,
        )
    )
    if len(state.recent_events) > MAX_RECENT_EVENTS:
        state.recent_events = state.recent_events[-MAX_RECENT_EVENTS:]

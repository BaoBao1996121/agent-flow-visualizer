"""A clearly labelled synthetic exhibit covering the complete event language."""

from __future__ import annotations

from datetime import timedelta

from .adapters._common import stable_id
from .schema import (
    AgentRuntimeEvent,
    EntityRef,
    EventClock,
    EventSource,
    Evidence,
    EvidenceLevel,
    Privacy,
    SourceFidelity,
    utc_now,
)


def build_demo_events(run_id: str) -> list[AgentRuntimeEvent]:
    """Build a deterministic narrative with no model or external side effects."""

    start = utc_now()
    events: list[AgentRuntimeEvent] = []

    coordinator = EntityRef(kind="agent", id="agent.coordinator", name="Coordinator")
    researcher = EntityRef(kind="agent", id="agent.researcher", name="Researcher")
    task = EntityRef(kind="task", id="task.incident-42", name="Explain checkout failures")
    system_context = EntityRef(kind="context.item", id="ctx.system", name="System policy")
    memory_item = EntityRef(kind="memory.item", id="mem.deploy-lesson", name="Prior deploy lesson")
    model_span = EntityRef(kind="model.call", id="model.plan-1", name="Planner call")
    tool_span = EntityRef(kind="tool.call", id="tool.logs-1", name="Query logs")
    retrieval_span = EntityRef(kind="retrieval", id="retrieval.logs-1", name="Incident evidence")
    compaction = EntityRef(kind="compaction", id="compact.ctx-1", name="Context compaction")
    checkpoint = EntityRef(kind="checkpoint", id="checkpoint.plan", name="Plan checkpoint")
    artifact = EntityRef(kind="artifact", id="artifact.report", name="Incident report")

    def add(
        event_type: str,
        *,
        subject: EntityRef | None = None,
        payload: dict | None = None,
        measurements: dict | None = None,
        cause: str | None = None,
        level: EvidenceLevel = EvidenceLevel.DECLARED,
        confidence: float = 1.0,
        agent_id: str | None = None,
        span_id: str | None = None,
        parent_span_id: str | None = None,
        delay_ms: int = 260,
    ) -> str:
        index = len(events)
        event_id = stable_id("evt", run_id, "demo", index, event_type)
        fidelity = (
            SourceFidelity.INFERRED
            if level == EvidenceLevel.INFERRED
            else SourceFidelity.NATIVE
        )
        events.append(
            AgentRuntimeEvent(
                event_id=event_id,
                event_type=event_type,
                run_id=run_id,
                session_id="demo-session",
                project_id="anthill-demo",
                task_id=task.id,
                agent_id=agent_id,
                trace_id=stable_id("trace", run_id),
                span_id=span_id,
                parent_span_id=parent_span_id,
                causation_id=cause,
                subject=subject,
                clock=EventClock(
                    occurred_at=start + timedelta(milliseconds=index * delay_ms),
                    observed_at=start,
                    source_seq=index,
                ),
                source=EventSource(
                    adapter="anthill.demo.fixture",
                    adapter_version="0.1.0",
                    framework="synthetic-fixture",
                    language="protocol",
                    fidelity=fidelity,
                    raw_event_ref=f"fixture:{index}",
                ),
                evidence=Evidence(
                    level=level,
                    confidence=confidence,
                    explanation=(
                        "Scripted demonstration event; not captured from a real Agent"
                        if level != EvidenceLevel.INFERRED
                        else "Synthetic semantic inference used to demonstrate truth styling"
                    ),
                    derived_from=[cause] if level == EvidenceLevel.INFERRED and cause else [],
                ),
                summary=_summary(event_type, subject),
                payload={"synthetic": True, **(payload or {})},
                measurements=measurements or {},
                privacy=Privacy(),
                extensions={"anthill.demo": True},
            )
        )
        return event_id

    manifest = add(
        "manifest.snapshot",
        payload={
            "title": "Checkout incident — full Anthill exhibit",
            "synthetic": True,
            "description": "A no-network fixture that exercises every core chamber",
            "scenario_version": "0.1.0",
        },
    )
    run = add(
        "run.started",
        payload={"title": "Checkout incident", "status": "running"},
        cause=manifest,
    )
    spawned = add("agent.spawned", subject=coordinator, cause=run, agent_id=coordinator.id)
    created = add("task.created", subject=task, cause=spawned, agent_id=coordinator.id)
    plan = add(
        "agent.plan.created",
        subject=coordinator,
        payload={"steps": 4, "strategy": "evidence-first"},
        cause=created,
        agent_id=coordinator.id,
    )
    assembly = add(
        "context.assembly.started",
        subject=coordinator,
        payload={"budget_tokens": 8192, "used_tokens": 820},
        cause=plan,
        agent_id=coordinator.id,
    )
    system_added = add(
        "context.item.added",
        subject=system_context,
        payload={"source": "system", "token_count": 620},
        cause=assembly,
        agent_id=coordinator.id,
    )
    memory_search = add(
        "memory.searched",
        subject=coordinator,
        payload={"layer": "episodic", "query_hash": "sha256:demo-query"},
        cause=system_added,
        agent_id=coordinator.id,
    )
    memory_hit = add(
        "memory.hit",
        subject=memory_item,
        payload={"layer": "episodic", "score": 0.93},
        cause=memory_search,
        agent_id=coordinator.id,
    )
    memory_context = add(
        "context.item.added",
        subject=memory_item,
        payload={"source": "memory", "token_count": 380, "retrieval_score": 0.93},
        cause=memory_hit,
        agent_id=coordinator.id,
    )
    context_ready = add(
        "context.assembly.completed",
        subject=coordinator,
        payload={"budget_tokens": 8192, "used_tokens": 1680, "item_count": 4},
        cause=memory_context,
        agent_id=coordinator.id,
    )

    model_prepared = add(
        "model.request.prepared",
        subject=model_span,
        payload={"model": "demo-reasoner", "purpose": "plan incident investigation"},
        measurements={"input_tokens": 1680},
        cause=context_ready,
        agent_id=coordinator.id,
        span_id=model_span.id,
    )
    model_sent = add(
        "model.request.dispatched",
        subject=model_span,
        payload={"model": "demo-reasoner"},
        cause=model_prepared,
        agent_id=coordinator.id,
        span_id=model_span.id,
    )
    model_chunk = add(
        "model.response.first_chunk",
        subject=model_span,
        cause=model_sent,
        agent_id=coordinator.id,
        span_id=model_span.id,
    )
    model_done = add(
        "model.response.completed",
        subject=model_span,
        payload={"finish_reason": "tool_call"},
        measurements={"output_tokens": 420, "duration_ms": 780, "cost_usd": 0.0062},
        cause=model_chunk,
        agent_id=coordinator.id,
        span_id=model_span.id,
    )
    decision_start = add(
        "decision.started",
        subject=coordinator,
        payload={"candidates": ["query_logs", "inspect_code", "ask_human"]},
        cause=model_done,
        level=EvidenceLevel.INFERRED,
        confidence=0.86,
        agent_id=coordinator.id,
    )
    decision = add(
        "decision.evaluated",
        subject=coordinator,
        payload={"selected": "query_logs", "reason_summary": "Errors began after deploy"},
        cause=decision_start,
        level=EvidenceLevel.INFERRED,
        confidence=0.86,
        agent_id=coordinator.id,
    )

    handoff = add(
        "handoff.proposed",
        subject=task,
        payload={"from": coordinator.id, "to": researcher.id, "context_items": 4},
        cause=decision,
        agent_id=coordinator.id,
    )
    researcher_spawned = add(
        "agent.spawned",
        subject=researcher,
        payload={"parent_agent_id": coordinator.id},
        cause=handoff,
        agent_id=researcher.id,
    )
    handoff_done = add(
        "handoff.completed",
        subject=task,
        payload={"from": coordinator.id, "to": researcher.id, "ownership": "transferred"},
        cause=researcher_spawned,
        agent_id=researcher.id,
    )

    tool_requested = add(
        "tool.call.requested",
        subject=tool_span,
        payload={"tool": "query_logs", "approval_required": False},
        cause=handoff_done,
        agent_id=researcher.id,
        span_id=tool_span.id,
    )
    tool_started = add(
        "tool.execution.started",
        subject=tool_span,
        payload={"tool": "query_logs"},
        cause=tool_requested,
        agent_id=researcher.id,
        span_id=tool_span.id,
    )
    retrieval_started = add(
        "retrieval.search.started",
        subject=retrieval_span,
        payload={"index": "service-logs", "time_range_minutes": 30},
        cause=tool_started,
        agent_id=researcher.id,
        span_id=retrieval_span.id,
        parent_span_id=tool_span.id,
    )
    tool_failed = add(
        "tool.execution.failed",
        subject=tool_span,
        payload={"error_type": "RateLimit", "retryable": True},
        measurements={"duration_ms": 340},
        cause=retrieval_started,
        agent_id=researcher.id,
        span_id=tool_span.id,
    )
    error = add(
        "error.raised",
        subject=tool_span,
        payload={"error_type": "RateLimit", "handled": True},
        cause=tool_failed,
        agent_id=researcher.id,
        span_id=tool_span.id,
    )
    retry = add(
        "tool.retry.scheduled",
        subject=tool_span,
        payload={"attempt": 2, "backoff_ms": 500},
        cause=error,
        agent_id=researcher.id,
        span_id=tool_span.id,
    )
    tool_restart = add(
        "tool.execution.started",
        subject=tool_span,
        payload={"tool": "query_logs", "attempt": 2},
        cause=retry,
        agent_id=researcher.id,
        span_id=tool_span.id,
    )
    candidates = add(
        "retrieval.candidates.returned",
        subject=retrieval_span,
        payload={"candidate_count": 128},
        cause=tool_restart,
        agent_id=researcher.id,
        span_id=retrieval_span.id,
        parent_span_id=tool_span.id,
    )
    selected = add(
        "retrieval.documents.selected",
        subject=retrieval_span,
        payload={"selected_count": 12, "top_score": 0.97},
        cause=candidates,
        agent_id=researcher.id,
        span_id=retrieval_span.id,
        parent_span_id=tool_span.id,
    )
    tool_done = add(
        "tool.execution.succeeded",
        subject=tool_span,
        payload={"tool": "query_logs", "result_ref": "artifact://log-slice"},
        measurements={"duration_ms": 610},
        cause=selected,
        agent_id=researcher.id,
        span_id=tool_span.id,
    )
    recovered = add(
        "error.recovered",
        subject=tool_span,
        payload={"recovered_event_id": error},
        cause=tool_done,
        agent_id=researcher.id,
    )

    context_near_full = add(
        "context.budget.updated",
        subject=researcher,
        payload={"budget_tokens": 8192, "used_tokens": 7990},
        cause=recovered,
        agent_id=researcher.id,
    )
    overflow = add(
        "context.overflow.detected",
        subject=researcher,
        payload={"budget_tokens": 8192, "used_tokens": 8460, "over_by": 268},
        cause=context_near_full,
        agent_id=researcher.id,
    )
    compact_trigger = add(
        "compaction.triggered",
        subject=compaction,
        payload={"trigger": "context_overflow", "policy": "evidence-preserving-summary"},
        cause=overflow,
        agent_id=researcher.id,
        span_id=compaction.id,
    )
    compact_start = add(
        "compaction.started",
        subject=compaction,
        payload={"tokens_before": 8460, "policy": "evidence-preserving-summary"},
        cause=compact_trigger,
        agent_id=researcher.id,
        span_id=compaction.id,
    )
    summary = add(
        "compaction.summary.created",
        subject=compaction,
        payload={"summary_hash": "sha256:demo-summary", "source_item_count": 18},
        cause=compact_start,
        agent_id=researcher.id,
        span_id=compaction.id,
    )
    replaced = add(
        "compaction.items.replaced",
        subject=compaction,
        payload={
            "kept_refs": ["ctx.system", "mem.deploy-lesson", "artifact://log-slice"],
            "removed_refs": ["ctx.turn.1", "ctx.turn.2", "ctx.raw-log-lines"],
        },
        cause=summary,
        agent_id=researcher.id,
        span_id=compaction.id,
    )
    compact_done = add(
        "compaction.completed",
        subject=compaction,
        payload={
            "tokens_before": 8460,
            "tokens_after": 3920,
            "lossy": True,
            "summary_hash": "sha256:demo-summary",
            "kept_refs": ["ctx.system", "mem.deploy-lesson", "artifact://log-slice"],
            "removed_refs": ["ctx.turn.1", "ctx.turn.2", "ctx.raw-log-lines"],
        },
        measurements={"duration_ms": 920},
        cause=replaced,
        agent_id=researcher.id,
        span_id=compaction.id,
    )
    context_after = add(
        "context.budget.updated",
        subject=researcher,
        payload={"budget_tokens": 8192, "used_tokens": 3920},
        cause=compact_done,
        agent_id=researcher.id,
    )
    checkpointed = add(
        "checkpoint.created",
        subject=checkpoint,
        payload={"state_hash": "sha256:demo-state", "parent_checkpoint_id": None},
        cause=context_after,
        agent_id=researcher.id,
    )
    report = add(
        "artifact.created",
        subject=artifact,
        payload={"mime_type": "text/markdown", "sha256": "demo-report-hash"},
        cause=checkpointed,
        agent_id=researcher.id,
    )
    remembered = add(
        "memory.written",
        subject=EntityRef(kind="memory.item", id="mem.checkout-root-cause", name="Checkout root cause"),
        payload={"layer": "semantic", "source_artifact_id": artifact.id},
        cause=report,
        agent_id=researcher.id,
    )
    handback = add(
        "handoff.completed",
        subject=task,
        payload={"from": researcher.id, "to": coordinator.id, "ownership": "returned"},
        cause=remembered,
        agent_id=coordinator.id,
    )
    add(
        "run.completed",
        payload={"status": "success", "result_artifact_id": artifact.id},
        measurements={"run_duration_ms": len(events) * 260},
        cause=handback,
        agent_id=coordinator.id,
    )
    return events


def _summary(event_type: str, subject: EntityRef | None) -> str:
    action = event_type.replace(".", " ")
    return f"{action}: {subject.name}" if subject else action

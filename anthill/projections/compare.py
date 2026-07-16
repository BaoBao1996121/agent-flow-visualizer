"""Deterministic, evidence-aware comparison between two run projections."""

from __future__ import annotations

from typing import Any, Iterable

from ..schema import AgentRuntimeEvent
from .world import WorldState, project_world


def compare_runs(
    left_events: Iterable[AgentRuntimeEvent],
    right_events: Iterable[AgentRuntimeEvent],
    *,
    left_run_id: str,
    right_run_id: str,
    progress: float = 1.0,
) -> dict[str, Any]:
    """Compare two runs at the same normalized ledger progress."""

    if not 0.0 <= progress <= 1.0:
        raise ValueError("progress must be between 0 and 1")
    left = list(left_events)
    right = list(right_events)
    if not left or not right:
        raise ValueError("both runs must contain events")

    left_head = left[-1].clock.ingest_seq or 0
    right_head = right[-1].clock.ingest_seq or 0
    left_seq = round(left_head * progress)
    right_seq = round(right_head * progress)
    left_world = project_world(left, run_id=left_run_id, at_seq=left_seq)
    right_world = project_world(right, run_id=right_run_id, at_seq=right_seq)
    left_summary = _summary(left_world)
    right_summary = _summary(right_world)

    event_types = sorted(
        set(left_world.event_type_counts) | set(right_world.event_type_counts)
    )
    event_type_diff = [
        {
            "event_type": event_type,
            "left": left_world.event_type_counts.get(event_type, 0),
            "right": right_world.event_type_counts.get(event_type, 0),
            "delta": right_world.event_type_counts.get(event_type, 0)
            - left_world.event_type_counts.get(event_type, 0),
        }
        for event_type in event_types
        if left_world.event_type_counts.get(event_type, 0)
        != right_world.event_type_counts.get(event_type, 0)
    ]
    event_type_diff.sort(key=lambda item: (-abs(item["delta"]), item["event_type"]))

    numeric_diffs = []
    for key in sorted(set(left_summary["metrics"]) | set(right_summary["metrics"])):
        left_value = left_summary["metrics"].get(key)
        right_value = right_summary["metrics"].get(key)
        if not isinstance(left_value, (int, float)) or not isinstance(
            right_value, (int, float)
        ):
            continue
        numeric_diffs.append(
            {
                "metric": key,
                "left": left_value,
                "right": right_value,
                "delta": right_value - left_value,
                "ratio": (
                    right_value / left_value
                    if left_value != 0
                    else None
                ),
            }
        )

    left_projects = {event.project_id for event in left if event.project_id}
    right_projects = {event.project_id for event in right if event.project_id}
    left_tasks = {event.task_id for event in left if event.task_id}
    right_tasks = {event.task_id for event in right if event.task_id}
    shared_projects = sorted(left_projects & right_projects)
    shared_tasks = sorted(left_tasks & right_tasks)
    warnings = []
    if not shared_projects:
        warnings.append(
            "Runs do not share a project_id; treat this as structural comparison."
        )
    if not shared_tasks:
        warnings.append(
            "Runs do not share a task_id; outcome differences are not controlled evidence."
        )

    return {
        "progress": progress,
        "cursor": {
            "left_seq": left_seq,
            "left_head": left_head,
            "right_seq": right_seq,
            "right_head": right_head,
        },
        "comparability": {
            "shared_project_ids": shared_projects,
            "shared_task_ids": shared_tasks,
            "controlled": bool(shared_projects and shared_tasks),
            "warnings": warnings,
        },
        "left": {
            "run_id": left_run_id,
            "summary": left_summary,
            "state": left_world.model_dump(mode="json"),
        },
        "right": {
            "run_id": right_run_id,
            "summary": right_summary,
            "state": right_world.model_dump(mode="json"),
        },
        "metric_differences": numeric_diffs,
        "event_type_differences": event_type_diff,
    }


def _summary(world: WorldState) -> dict[str, Any]:
    compactions = list(world.compactions.values())
    metrics: dict[str, int | float] = {
        "events": world.event_count,
        "agents": sum(1 for entity in world.entities.values() if entity.kind == "agent"),
        "open_errors": sum(1 for error in world.errors if error.status == "open"),
        "error_events": len(world.errors),
        "memory_hits": world.memory.hits,
        "memory_misses": world.memory.misses,
        "memory_writes": world.memory.writes,
        "memory_evictions": world.memory.evictions,
        "context_used_tokens": world.context.used_tokens or 0,
        "context_budget_tokens": world.context.budget_tokens or 0,
        "compactions": len(compactions),
        "compaction_tokens_removed": sum(
            job.tokens_removed or 0 for job in compactions
        ),
        "handoffs": world.event_type_counts.get("handoff.completed", 0),
        "checkpoints": world.event_type_counts.get("checkpoint.created", 0),
        "model_calls": world.event_type_counts.get("model.request.dispatched", 0),
        "tool_calls": world.event_type_counts.get("tool.execution.started", 0),
    }
    for key, value in world.totals.items():
        if isinstance(value, (int, float)):
            metrics[key] = value

    mechanisms = {
        "memory": any(
            event_type.startswith("memory.")
            for event_type in world.event_type_counts
        ),
        "context": any(
            event_type.startswith("context.")
            for event_type in world.event_type_counts
        ),
        "compaction": bool(compactions),
        "handoff": metrics["handoffs"] > 0,
        "checkpoint": metrics["checkpoints"] > 0,
        "recovery": world.event_type_counts.get("error.recovered", 0) > 0,
    }
    domain_counts: dict[str, int] = {}
    for event_type, count in world.event_type_counts.items():
        domain = event_type.split(".", 1)[0]
        domain_counts[domain] = domain_counts.get(domain, 0) + count
    return {
        "run_status": world.run_status,
        "frameworks": world.frameworks,
        "source_adapters": world.source_adapters,
        "evidence_counts": world.evidence_counts,
        "mechanisms": mechanisms,
        "domain_counts": domain_counts,
        "metrics": metrics,
    }

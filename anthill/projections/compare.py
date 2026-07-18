"""Deterministic, evidence-aware comparison between two run projections."""

from __future__ import annotations

import math
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
    left_visible = [
        event
        for event in left
        if event.clock.ingest_seq is not None and event.clock.ingest_seq <= left_seq
    ]
    right_visible = [
        event
        for event in right
        if event.clock.ingest_seq is not None and event.clock.ingest_seq <= right_seq
    ]
    left_world = project_world(left_visible, run_id=left_run_id)
    right_world = project_world(right_visible, run_id=right_run_id)
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
        left_observed = isinstance(left_value, (int, float)) and not isinstance(
            left_value, bool
        )
        right_observed = isinstance(right_value, (int, float)) and not isinstance(
            right_value, bool
        )
        if not left_observed or not right_observed:
            if left_observed != right_observed:
                numeric_diffs.append(
                    {
                        "metric": key,
                        "left": left_value,
                        "right": right_value,
                        "delta": None,
                        "ratio": None,
                        "comparison": "availability",
                    }
                )
            continue
        numeric_diffs.append(
            {
                "metric": key,
                "left": left_value,
                "right": right_value,
                "delta": right_value - left_value,
                "ratio": _finite_ratio(right_value, left_value),
                "comparison": "numeric",
            }
        )

    measurement_diffs = _measurement_differences(left_world, right_world)

    left_projects = {event.project_id for event in left_visible if event.project_id}
    right_projects = {event.project_id for event in right_visible if event.project_id}
    left_tasks = {event.task_id for event in left_visible if event.task_id}
    right_tasks = {event.task_id for event in right_visible if event.task_id}
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
        "measurement_differences": measurement_diffs,
        "event_type_differences": event_type_diff,
    }


def _event_count_or_none(world: WorldState, *event_types: str) -> int | None:
    if not any(event_type in world.event_type_counts for event_type in event_types):
        return None
    return sum(world.event_type_counts.get(event_type, 0) for event_type in event_types)


def _finite_ratio(
    numerator: int | float, denominator: int | float
) -> int | float | None:
    if denominator == 0:
        return None
    try:
        ratio = numerator / denominator
    except (OverflowError, ZeroDivisionError):
        return None
    return ratio if math.isfinite(ratio) else None


def _error_event_count_or_none(world: WorldState) -> int | None:
    count = sum(
        event_count
        for event_type, event_count in world.event_type_counts.items()
        if (
            event_type.split(".", 1)[0] == "error"
            and event_type != "error.recovered"
        )
        or event_type.endswith((".failed", ".timeout", ".rejected"))
    )
    return count or None


def _mechanism_observed(world: WorldState, family: str) -> bool | None:
    if any(event_type.startswith(f"{family}.") for event_type in world.event_type_counts):
        return True
    return None


def _measurement_contract(aggregate: Any) -> dict[str, Any]:
    basis_values = getattr(aggregate, "basis_values", [])
    estimated_values = getattr(aggregate, "estimated_values", [])
    basis_complete = getattr(aggregate, "basis_complete", False)
    estimated_complete = getattr(aggregate, "estimated_complete", False)
    basis = (
        basis_values[0]
        if basis_complete and len(basis_values) == 1
        else None
    )
    estimated = (
        estimated_values[0]
        if estimated_complete and len(estimated_values) == 1
        else None
    )
    return {
        "unit": aggregate.unit,
        "scope": aggregate.scope,
        "aggregation": aggregate.aggregation,
        "basis": basis,
        "basis_values": list(basis_values),
        "basis_complete": basis_complete,
        "estimated": estimated,
        "estimated_values": list(estimated_values),
        "estimated_complete": estimated_complete,
    }


def _measurement_sources(world: WorldState) -> dict[tuple[str, str], Any]:
    sources = {
        ("aggregate", key): aggregate
        for key, aggregate in world.measurement_aggregates.items()
    }
    sources.update(
        {
            ("calculated", key): calculated
            for key, calculated in world.calculated_measurements.items()
        }
    )
    return sources


def _measurement_differences(
    left_world: WorldState, right_world: WorldState
) -> list[dict[str, Any]]:
    differences: list[dict[str, Any]] = []
    left_sources = _measurement_sources(left_world)
    right_sources = _measurement_sources(right_world)
    for origin, key in sorted(set(left_sources) | set(right_sources)):
        left = left_sources.get((origin, key))
        right = right_sources.get((origin, key))
        left_contract = _measurement_contract(left) if left is not None else None
        right_contract = _measurement_contract(right) if right is not None else None
        row = {
            "measurement": key,
            "origin": origin,
            "left": left.value if left is not None else None,
            "right": right.value if right is not None else None,
            "delta": None,
            "ratio": None,
            "left_status": left.status if left is not None else "missing",
            "right_status": right.status if right is not None else "missing",
            "left_contract": left_contract,
            "right_contract": right_contract,
            "left_calculation": getattr(left, "calculation", None),
            "right_calculation": getattr(right, "calculation", None),
            "left_components": getattr(left, "components", None),
            "right_components": getattr(right, "components", None),
        }
        if left is None or right is None:
            missing_side = "left" if left is None else "right"
            differences.append(
                {
                    **row,
                    "comparison": "availability",
                    "reason": f"measurement missing on {missing_side}",
                }
            )
            continue
        not_observed_sides = [
            side
            for side, aggregate in (("left", left), ("right", right))
            if aggregate.status == "not_observed"
        ]
        if not_observed_sides:
            subject = " and ".join(not_observed_sides)
            differences.append(
                {
                    **row,
                    "comparison": "availability",
                    "reason": f"measurement not observed on {subject}",
                }
            )
            continue
        ambiguous_sides = [
            side
            for side, aggregate in (("left", left), ("right", right))
            if aggregate.status != "available" or aggregate.value is None
        ]
        if ambiguous_sides:
            subject = " and ".join(ambiguous_sides)
            noun = "measurement is" if len(ambiguous_sides) == 1 else "measurements are"
            differences.append(
                {
                    **row,
                    "comparison": "not_comparable",
                    "reason": f"{subject} {noun} ambiguous",
                }
            )
            continue
        incompatible_fields = [
            field
            for field in ("unit", "scope", "aggregation")
            if left_contract[field] != right_contract[field]
        ]
        if incompatible_fields:
            differences.append(
                {
                    **row,
                    "comparison": "not_comparable",
                    "reason": (
                        "measurement contract differs: "
                        + ", ".join(incompatible_fields)
                    ),
                }
            )
            continue
        if key == "model_call.cost_usd":
            incomplete_basis_sides = [
                side
                for side, contract in (
                    ("left", left_contract),
                    ("right", right_contract),
                )
                if not contract["basis_complete"]
                or len(contract["basis_values"]) != 1
            ]
            if incomplete_basis_sides:
                differences.append(
                    {
                        **row,
                        "comparison": "not_comparable",
                        "reason": (
                            "cost basis is not singular and complete on "
                            + " and ".join(incomplete_basis_sides)
                        ),
                    }
                )
                continue
            incomplete_estimate_sides = [
                side
                for side, contract in (
                    ("left", left_contract),
                    ("right", right_contract),
                )
                if not contract["estimated_complete"]
                or len(contract["estimated_values"]) != 1
            ]
            if incomplete_estimate_sides:
                differences.append(
                    {
                        **row,
                        "comparison": "not_comparable",
                        "reason": (
                            "cost estimate status is not singular and complete on "
                            + " and ".join(incomplete_estimate_sides)
                        ),
                    }
                )
                continue
        if key == "model_call.cost_usd" and (
            left_contract["basis"] != right_contract["basis"]
        ):
            differences.append(
                {
                    **row,
                    "comparison": "not_comparable",
                    "reason": "cost basis differs",
                }
            )
            continue
        if key == "model_call.cost_usd" and (
            left_contract["estimated"] != right_contract["estimated"]
        ):
            differences.append(
                {
                    **row,
                    "comparison": "not_comparable",
                    "reason": "cost estimate status differs",
                }
            )
            continue
        differences.append(
            {
                **row,
                "delta": right.value - left.value,
                "ratio": _finite_ratio(right.value, left.value),
                "comparison": "numeric",
                "reason": None,
            }
        )
    return differences


def _summary(world: WorldState) -> dict[str, Any]:
    compactions = list(world.compactions.values())
    agent_count = sum(
        1 for entity in world.entities.values() if entity.kind == "agent"
    )
    error_event_count = _error_event_count_or_none(world)
    metrics: dict[str, int | float | None] = {
        "events": world.event_count,
        "agents": agent_count or None,
        "open_errors": (
            sum(1 for error in world.errors if error.status == "open")
            if error_event_count is not None
            else None
        ),
        "error_events": error_event_count,
        "memory_hits": _event_count_or_none(world, "memory.hit"),
        "memory_misses": _event_count_or_none(world, "memory.miss"),
        "memory_writes": _event_count_or_none(world, "memory.written"),
        "memory_evictions": _event_count_or_none(world, "memory.evicted"),
        "context_used_tokens": world.context.used_tokens,
        "context_budget_tokens": world.context.budget_tokens,
        "compactions": len(compactions) or None,
        "compaction_tokens_removed": (
            sum(job.tokens_removed for job in compactions if job.tokens_removed is not None)
            if compactions
            and all(job.tokens_removed is not None for job in compactions)
            else None
        ),
        "handoffs": _event_count_or_none(world, "handoff.completed"),
        "checkpoints": _event_count_or_none(world, "checkpoint.created"),
        "model_requests_dispatched": _event_count_or_none(
            world, "model.request.dispatched"
        ),
        "model_response_first_chunk_events": _event_count_or_none(
            world, "model.response.first_chunk"
        ),
        "model_response_chunk_events": _event_count_or_none(
            world, "model.response.chunk"
        ),
        "model_calls_completed": _event_count_or_none(
            world, "model.response.completed"
        ),
        "model_calls_failed": _event_count_or_none(world, "model.failed"),
        "tool_calls": _event_count_or_none(world, "tool.execution.started"),
    }
    mechanisms = {
        "memory": _mechanism_observed(world, "memory"),
        "context": _mechanism_observed(world, "context"),
        "compaction": _mechanism_observed(world, "compaction"),
        "handoff": _mechanism_observed(world, "handoff"),
        "checkpoint": _mechanism_observed(world, "checkpoint"),
        "recovery": (
            True if "error.recovered" in world.event_type_counts else None
        ),
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
        "measurements": {
            key: aggregate.model_dump(mode="json", exclude={"owners"})
            for key, aggregate in sorted(world.measurement_aggregates.items())
        },
        "calculated_measurements": {
            key: measurement.model_dump(mode="json")
            for key, measurement in sorted(world.calculated_measurements.items())
        },
    }

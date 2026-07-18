"""Shared lifecycle folding for run projections and rebuildable indexes."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .schema import AgentRuntimeEvent


CANONICAL_RUN_STATUSES = frozenset(
    {"unknown", "running", "paused", "completed", "failed", "interrupted", "cancelled"}
)
_COMPLETED_STATUS_ALIASES = {
    "completed": "completed",
    "success": "completed",
    "failed": "failed",
    "error": "failed",
    "interrupted": "interrupted",
    "cancelled": "cancelled",
    "canceled": "cancelled",
}


def transition_run_status(
    current: str, event_type: str, payload: Mapping[str, Any]
) -> str:
    """Apply one explicit lifecycle fact without inferring from other events."""

    if event_type in {"run.started", "run.resumed", "run.forked"}:
        return "running"
    if event_type == "run.paused":
        return "paused"
    if event_type == "run.completed":
        raw_status = payload.get("status")
        status = raw_status.strip().lower() if isinstance(raw_status, str) else ""
        # The event type is the terminal fact. Unknown adapter-specific outcomes
        # must not create a non-terminal public state or keep animation running.
        return _COMPLETED_STATUS_ALIASES.get(status, "completed")
    if event_type == "run.cancelled":
        return "cancelled"
    if event_type == "error.fatal":
        return "failed"
    return current


def fold_run_status(
    events: Iterable[AgentRuntimeEvent], *, initial: str = "unknown"
) -> str:
    """Fold lifecycle facts in authoritative ingest order."""

    status = initial
    for event in events:
        status = transition_run_status(status, event.event_type, event.payload)
    return status

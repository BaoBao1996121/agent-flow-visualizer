"""Side-effect-free materialized run forks for time-travel experiments."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from .adapters._common import stable_id
from .schema import (
    AgentRuntimeEvent,
    EntityRef,
    EventClock,
    EventLink,
    EventSource,
    Evidence,
    EvidenceLevel,
    LinkType,
    Privacy,
    SourceFidelity,
)


def materialize_fork_events(
    parent_events: Iterable[AgentRuntimeEvent],
    *,
    parent_run_id: str,
    new_run_id: str,
    parent_state_hash: str,
    title: str | None = None,
) -> list[AgentRuntimeEvent]:
    """Copy a parent prefix into a new immutable ledger and record its origin.

    This function never calls a model or tool. A later runner may append new
    events to the branch under a separate, explicit execution policy.
    """

    parent = list(parent_events)
    if not parent:
        raise ValueError("cannot fork an empty run")
    if any(event.run_id != parent_run_id for event in parent):
        raise ValueError("parent event run_id does not match parent_run_id")
    if parent_run_id == new_run_id:
        raise ValueError("new_run_id must differ from parent_run_id")

    selected = [event for event in parent if event.event_type != "manifest.snapshot"]
    id_map = {
        event.event_id: stable_id(
            "evt", new_run_id, "branch-copy", event.event_id
        )
        for event in selected
    }
    fork_point = parent[-1]
    now = datetime.now(timezone.utc)
    project_id = next((event.project_id for event in parent if event.project_id), None)
    session_id = next((event.session_id for event in parent if event.session_id), None)
    synthetic = any(
        event.event_type == "manifest.snapshot"
        and bool(event.payload.get("synthetic", False))
        for event in parent
    )
    branch_title = title or f"Fork of {parent_run_id} at #{fork_point.clock.ingest_seq}"
    manifest_id = stable_id("evt", new_run_id, "branch", "manifest")
    manifest = AgentRuntimeEvent(
        event_id=manifest_id,
        event_type="manifest.snapshot",
        run_id=new_run_id,
        project_id=project_id,
        session_id=session_id,
        clock=EventClock(occurred_at=parent[0].clock.occurred_at, observed_at=now),
        source=EventSource(
            adapter="anthill.branch.materializer",
            adapter_version="0.1.0",
            framework="agent-anthill",
            fidelity=SourceFidelity.NATIVE,
            raw_event_ref=f"anthill://runs/{parent_run_id}",
        ),
        evidence=Evidence(level=EvidenceLevel.OBSERVED, confidence=1.0),
        summary=branch_title,
        payload={
            "title": branch_title,
            "synthetic": synthetic,
            "branch": True,
            "parent_run_id": parent_run_id,
            "parent_event_id": fork_point.event_id,
            "parent_seq": fork_point.clock.ingest_seq,
            "parent_state_hash": parent_state_hash,
            "materialized": True,
        },
        privacy=Privacy(),
    )

    copies: list[AgentRuntimeEvent] = []
    for original in selected:
        causation_id = (
            id_map.get(original.causation_id)
            if original.causation_id
            else None
        ) or manifest_id
        remapped_links = []
        for link in original.links:
            data = link.model_dump()
            if link.event_id in id_map:
                data["event_id"] = id_map[link.event_id]
                if not link.run_id or link.run_id == parent_run_id:
                    data["run_id"] = new_run_id
            remapped_links.append(EventLink.model_validate(data))
        remapped_links.append(
            EventLink(
                type=LinkType.DERIVED_FROM,
                event_id=original.event_id,
                run_id=parent_run_id,
            )
        )
        extensions = dict(original.extensions)
        extensions["anthill.branch.origin"] = {
            "run_id": parent_run_id,
            "event_id": original.event_id,
            "ingest_seq": original.clock.ingest_seq,
        }
        evidence = original.evidence.model_copy(
            update={
                "derived_from": list(
                    dict.fromkeys(
                        [*original.evidence.derived_from, original.event_id]
                    )
                )
            }
        )
        copies.append(
            original.model_copy(
                update={
                    "event_id": id_map[original.event_id],
                    "run_id": new_run_id,
                    "causation_id": causation_id,
                    "links": remapped_links,
                    "source": original.source.model_copy(
                        update={
                            "adapter": "anthill.branch.materializer",
                            "adapter_version": "0.1.0",
                            "fidelity": SourceFidelity.MAPPED,
                            "raw_event_ref": (
                                f"anthill://runs/{parent_run_id}/events/{original.event_id}"
                            ),
                        }
                    ),
                    "evidence": evidence,
                    "extensions": extensions,
                    "integrity": None,
                }
            )
        )

    mapped_fork_event_id = id_map.get(fork_point.event_id, manifest_id)
    fork_event = AgentRuntimeEvent(
        event_id=stable_id("evt", new_run_id, "branch", "forked"),
        event_type="run.forked",
        run_id=new_run_id,
        project_id=project_id,
        session_id=session_id,
        causation_id=mapped_fork_event_id,
        links=[
            EventLink(
                type=LinkType.DERIVED_FROM,
                event_id=fork_point.event_id,
                run_id=parent_run_id,
            )
        ],
        subject=EntityRef(kind="run", id=new_run_id, name=branch_title),
        clock=EventClock(occurred_at=now, observed_at=now),
        source=EventSource(
            adapter="anthill.branch.materializer",
            adapter_version="0.1.0",
            framework="agent-anthill",
            fidelity=SourceFidelity.NATIVE,
            raw_event_ref=f"anthill://runs/{parent_run_id}/events/{fork_point.event_id}",
        ),
        evidence=Evidence(
            level=EvidenceLevel.OBSERVED,
            confidence=1.0,
            derived_from=[fork_point.event_id],
            explanation="Materialized fork; no model or tool was rerun",
        ),
        summary=f"Forked {parent_run_id} at event #{fork_point.clock.ingest_seq}",
        payload={
            "parent_run_id": parent_run_id,
            "parent_event_id": fork_point.event_id,
            "parent_seq": fork_point.clock.ingest_seq,
            "parent_state_hash": parent_state_hash,
            "materialized": True,
            "side_effects_replayed": False,
        },
        privacy=Privacy(),
    )
    return [manifest, *copies, fork_event]

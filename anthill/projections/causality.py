"""Evidence-preserving causal graph queries."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Iterable

from ..schema import AgentRuntimeEvent


def build_causal_slice(
    events: Iterable[AgentRuntimeEvent],
    *,
    event_id: str,
    direction: str = "both",
    max_depth: int = 12,
) -> dict:
    """Return the bounded causal neighborhood around an event.

    ``causation_id`` creates a directed edge. Event links with explicit event
    targets are preserved with their declared relationship. Temporal adjacency
    is deliberately *not* converted into causation.
    """

    if direction not in {"ancestors", "descendants", "both"}:
        raise ValueError("direction must be ancestors, descendants, or both")
    if max_depth < 0 or max_depth > 100:
        raise ValueError("max_depth must be between 0 and 100")

    items = {event.event_id: event for event in events}
    if event_id not in items:
        raise KeyError(event_id)

    incoming: dict[str, list[tuple[str, str]]] = defaultdict(list)
    outgoing: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for event in items.values():
        if event.causation_id and event.causation_id in items:
            incoming[event.event_id].append((event.causation_id, "caused_by"))
            outgoing[event.causation_id].append((event.event_id, "caused"))
        for link in event.links:
            if link.event_id and link.event_id in items:
                relationship = link.type.value if hasattr(link.type, "value") else str(link.type)
                incoming[event.event_id].append((link.event_id, relationship))
                outgoing[link.event_id].append((event.event_id, relationship))

    visited_depth = {event_id: 0}
    queue = deque([event_id])
    edge_keys: set[tuple[str, str, str]] = set()
    edges: list[dict] = []
    while queue:
        current = queue.popleft()
        depth = visited_depth[current]
        if depth >= max_depth:
            continue
        neighbors: list[tuple[str, str, str, str]] = []
        if direction in {"ancestors", "both"}:
            neighbors.extend(
                (target, target, current, relation)
                for target, relation in incoming.get(current, [])
            )
        if direction in {"descendants", "both"}:
            neighbors.extend(
                (target, current, target, relation)
                for target, relation in outgoing.get(current, [])
            )
        for target, source_id, target_id, relation in neighbors:
            key = (source_id, target_id, relation)
            if key not in edge_keys:
                edge_keys.add(key)
                edges.append(
                    {"source": source_id, "target": target_id, "relation": relation}
                )
            if target not in visited_depth:
                visited_depth[target] = depth + 1
                queue.append(target)

    nodes = []
    for node_id, depth in sorted(
        visited_depth.items(),
        key=lambda item: (item[1], items[item[0]].clock.ingest_seq or 0),
    ):
        event = items[node_id]
        nodes.append(
            {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "seq": event.clock.ingest_seq,
                "depth": depth,
                "summary": event.summary,
                "subject": event.subject.model_dump(mode="json") if event.subject else None,
                "evidence": event.evidence.model_dump(mode="json"),
                "source": event.source.model_dump(mode="json"),
            }
        )

    return {
        "root_event_id": event_id,
        "direction": direction,
        "max_depth": max_depth,
        "nodes": nodes,
        "edges": edges,
    }

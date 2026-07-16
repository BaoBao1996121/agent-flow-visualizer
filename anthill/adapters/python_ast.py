"""Normalize the existing Python AST graph into declared and inferred events."""

from __future__ import annotations

from datetime import datetime, timezone

from analyzer.graph_builder import FlowGraph

from ..schema import (
    AgentRuntimeEvent,
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


def flow_graph_to_events(
    graph: FlowGraph,
    *,
    run_id: str,
    project_id: str | None = None,
    session_id: str | None = None,
) -> list[AgentRuntimeEvent]:
    """Emit source declarations separately from semantic classifications.

    This distinction matters: AST proves that a function exists, while labels
    such as ``llm_call`` are heuristic interpretations.  The UI must be able to
    draw those two facts differently.
    """

    now = datetime.now(timezone.utc)
    mapped_source = EventSource(
        adapter="anthill.python.ast",
        adapter_version="0.1.0",
        framework="python",
        language="python",
        fidelity=SourceFidelity.MAPPED,
    )
    inferred_source = mapped_source.model_copy(
        update={"fidelity": SourceFidelity.INFERRED}
    )
    events: list[AgentRuntimeEvent] = []
    source_seq = 0

    for node in graph.nodes:
        entity_event_id = stable_id("evt", run_id, "entity", node.id)
        subject = EntityRef(
            kind="code.function",
            id=node.id,
            name=node.label,
            attributes={
                "class_name": node.class_name,
                "is_async": node.is_async,
            },
        )
        source_ref = EvidenceRef(
            kind="source",
            uri=repository_uri(node.filepath),
            line_start=max(node.lineno, 1),
            label=node.label,
        )
        events.append(
            AgentRuntimeEvent(
                event_id=entity_event_id,
                event_type=CoreEventType.CODE_ENTITY_DECLARED,
                run_id=run_id,
                session_id=session_id,
                project_id=project_id,
                subject=subject,
                clock=EventClock(
                    occurred_at=now,
                    observed_at=now,
                    source_seq=source_seq,
                ),
                source=mapped_source,
                evidence=Evidence(
                    level=EvidenceLevel.DECLARED,
                    confidence=1.0,
                    refs=[source_ref],
                ),
                summary=f"Declared function {node.label}",
                payload={
                    "filepath": node.filepath,
                    "lineno": node.lineno,
                    "parameters": node.parameters,
                    "decorators": node.decorators,
                    "has_branches": node.has_branches,
                    "branch_count": node.branch_count,
                    "has_prompt_like_text": node.has_prompts,
                },
                privacy=Privacy(),
            )
        )
        source_seq += 1

        confidence = min(max(float(node.confidence), 0.0), 0.99)
        events.append(
            AgentRuntimeEvent(
                event_id=stable_id("evt", run_id, "classification", node.id),
                event_type="semantic.entity.classified",
                run_id=run_id,
                session_id=session_id,
                project_id=project_id,
                causation_id=entity_event_id,
                subject=subject,
                clock=EventClock(
                    occurred_at=now,
                    observed_at=now,
                    source_seq=source_seq,
                ),
                source=inferred_source,
                evidence=Evidence(
                    level=EvidenceLevel.INFERRED,
                    confidence=confidence,
                    refs=[source_ref],
                    derived_from=[entity_event_id],
                    explanation=node.reason,
                ),
                summary=f"Classified {node.label} as {node.node_type}",
                payload={
                    "semantic_type": node.node_type,
                    "reason": node.reason,
                    "frameworks": graph.metadata.get("detected_frameworks", []),
                },
                privacy=Privacy(),
            )
        )
        source_seq += 1

    for edge in graph.edges:
        evidence_level = (
            EvidenceLevel.INFERRED
            if edge.edge_type == "call"
            else EvidenceLevel.DECLARED
        )
        confidence = 0.9 if evidence_level == EvidenceLevel.INFERRED else 1.0
        events.append(
            AgentRuntimeEvent(
                event_id=stable_id(
                    "evt", run_id, "relation", edge.source, edge.target, edge.id
                ),
                event_type=CoreEventType.CODE_RELATION_DECLARED,
                run_id=run_id,
                session_id=session_id,
                project_id=project_id,
                subject=EntityRef(kind="code.function", id=edge.source),
                clock=EventClock(
                    occurred_at=now,
                    observed_at=now,
                    source_seq=source_seq,
                ),
                source=(
                    inferred_source
                    if evidence_level == EvidenceLevel.INFERRED
                    else mapped_source
                ),
                evidence=Evidence(
                    level=evidence_level,
                    confidence=confidence,
                    explanation="Resolved from a Python call expression",
                ),
                summary=f"{edge.source} may call {edge.target}",
                payload={
                    "relation": edge.edge_type,
                    "source_entity_id": edge.source,
                    "target_entity_id": edge.target,
                    "condition": edge.condition,
                },
                privacy=Privacy(),
            )
        )
        source_seq += 1

    return events

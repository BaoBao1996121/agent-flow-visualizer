from anthill.projections import build_causal_slice, project_world, reduce_world
from anthill.adapters.langgraph import langgraph_v2_to_events
from anthill.schema import (
    AgentRuntimeEvent,
    EntityRef,
    EventSource,
    Evidence,
    EvidenceLevel,
    SourceFidelity,
)


def event(
    event_id: str,
    event_type: str,
    *,
    payload=None,
    measurements=None,
    subject=None,
    causation_id=None,
    level=EvidenceLevel.OBSERVED,
    confidence=1.0,
):
    fidelity = SourceFidelity.INFERRED if level == EvidenceLevel.INFERRED else SourceFidelity.NATIVE
    return AgentRuntimeEvent(
        event_id=event_id,
        event_type=event_type,
        run_id="run-world",
        causation_id=causation_id,
        subject=subject,
        source=EventSource(adapter="tests", fidelity=fidelity),
        evidence=Evidence(level=level, confidence=confidence),
        payload=payload or {},
        measurements=measurements or {},
    )


def stamp(events):
    result = []
    previous_hash = None
    for seq, item in enumerate(events):
        stored = item.with_ingest_metadata(
            ingest_seq=seq,
            previous_event_hash=previous_hash,
        )
        result.append(stored)
        previous_hash = stored.integrity.event_hash
    return result


def rich_run():
    context_item = EntityRef(kind="context.item", id="ctx-1", name="system prompt")
    memory_item = EntityRef(kind="memory.item", id="mem-1", name="preference")
    compaction = EntityRef(kind="compaction", id="cmp-1", name="context compaction")
    tool = EntityRef(kind="code.function", id="tools.search", name="search")
    return stamp(
        [
            event("e0", "run.started"),
            event(
                "e1",
                "tool.execution.started",
                subject=tool,
                causation_id="e0",
                level=EvidenceLevel.INFERRED,
                confidence=0.82,
            ),
            event(
                "e2",
                "tool.execution.succeeded",
                subject=tool,
                causation_id="e1",
                measurements={"duration_ms": 12.5},
                level=EvidenceLevel.INFERRED,
                confidence=0.82,
            ),
            event(
                "e3",
                "context.budget.updated",
                payload={"budget_tokens": 1000, "used_tokens": 700},
                causation_id="e0",
            ),
            event(
                "e4",
                "context.item.added",
                payload={"token_count": 120, "source": "system"},
                subject=context_item,
                causation_id="e3",
            ),
            event(
                "e5",
                "memory.written",
                payload={"layer": "episodic"},
                subject=memory_item,
                causation_id="e4",
            ),
            event(
                "e6",
                "memory.hit",
                payload={"layer": "episodic", "score": 0.91},
                subject=memory_item,
                causation_id="e5",
            ),
            event(
                "e7",
                "compaction.started",
                payload={"tokens_before": 900, "policy": "summarize-oldest"},
                subject=compaction,
                causation_id="e3",
            ),
            event(
                "e8",
                "compaction.completed",
                payload={
                    "tokens_after": 410,
                    "lossy": True,
                    "kept_refs": ["ctx-1"],
                    "removed_refs": ["ctx-old"],
                    "summary_hash": "abc",
                },
                subject=compaction,
                causation_id="e7",
            ),
            event("e9", "run.completed", payload={"status": "success"}, causation_id="e8"),
        ]
    )


def test_world_projection_exposes_truth_context_memory_and_compaction():
    state = project_world(rich_run(), run_id="run-world")

    assert state.run_status == "completed"
    assert state.cursor_seq == 9
    assert state.evidence_counts == {"observed": 8, "inferred": 2}
    assert state.entities["tools.search"].truth.level == EvidenceLevel.INFERRED
    assert state.entities["tools.search"].active is False
    assert state.active_event_ids == []
    assert state.context.budget_tokens == 1000
    assert state.context.used_tokens == 700
    assert state.context.utilization == 0.7
    assert state.context.items["ctx-1"]["status"] == "included"
    assert state.memory.episodic == 1
    assert state.memory.writes == 1
    assert state.memory.hits == 1
    assert state.memory.items["mem-1"]["score"] == 0.91
    assert state.compactions["cmp-1"].status == "completed"
    assert state.compactions["cmp-1"].tokens_removed == 490
    assert round(state.compactions["cmp-1"].reduction_ratio, 3) == 0.544


def test_resuming_a_terminal_run_clears_the_current_completion_time():
    state = project_world(
        stamp(
            [
                event("resume-1", "run.started"),
                event("resume-2", "run.completed", payload={"status": "success"}),
                event("resume-3", "run.resumed"),
            ]
        ),
        run_id="run-world",
    )

    assert state.run_status == "running"
    assert state.completed_at is None


def test_time_travel_stops_at_the_requested_ingest_sequence():
    events = rich_run()
    before_compaction = project_world(events, run_id="run-world", at_seq=6)
    during_compaction = project_world(events, run_id="run-world", at_seq=7)

    assert before_compaction.cursor_seq == 6
    assert before_compaction.compactions == {}
    assert during_compaction.compactions["cmp-1"].status == "running"
    assert during_compaction.run_status == "running"


def test_reducer_rejects_out_of_order_events():
    events = rich_run()
    state = reduce_world(project_world(events[:2], run_id="run-world"), events[2])

    try:
        reduce_world(state, events[1])
    except ValueError as exc:
        assert "not after current cursor" in str(exc)
    else:
        raise AssertionError("out-of-order event should be rejected")


def test_causal_slice_uses_explicit_links_not_temporal_adjacency():
    events = rich_run()
    graph = build_causal_slice(
        events,
        event_id="e8",
        direction="ancestors",
        max_depth=4,
    )

    node_ids = {node["event_id"] for node in graph["nodes"]}
    assert node_ids == {"e0", "e3", "e7", "e8"}
    assert "e6" not in node_ids
    assert all(edge["relation"] == "caused_by" for edge in graph["edges"])


def test_checkpoint_error_snapshot_is_historical_evidence_not_an_open_incident():
    parts = [
        {
            "type": "checkpoints",
            "ns": [],
            "data": {
                "config": None,
                "metadata": {},
                "values": {},
                "next": [],
                "parent_config": None,
                "tasks": [
                    {
                        "id": "failed-task",
                        "name": "worker",
                        "state": None,
                        "error": "historical failure",
                    }
                ],
            },
        }
    ]
    events = stamp(langgraph_v2_to_events(parts, run_id="historical-error"))

    world = project_world(events, run_id="historical-error")

    snapshot = next(item for item in world.errors if item.event_type == "error.task_snapshot")
    assert snapshot.status == "snapshot"
    assert sum(item.status == "open" for item in world.errors) == 0


def test_interrupt_reobservation_preserves_waiting_entity_and_inspection_zone():
    interrupt = {"id": "approval-1", "value": "review"}
    parts = [
        {"type": "updates", "ns": ["review"], "data": {"__interrupt__": [interrupt]}},
        {"type": "values", "ns": ["review"], "data": {}, "interrupts": [interrupt]},
        {
            "type": "tasks",
            "ns": ["review"],
            "data": {
                "id": "task-1",
                "name": "review",
                "error": None,
                "result": {},
                "interrupts": [interrupt],
            },
        },
    ]
    events = stamp(langgraph_v2_to_events(parts, run_id="interrupt-reobservation"))
    primary = next(event for event in events if event.event_type == "human.interrupt")

    world = project_world(events, run_id="interrupt-reobservation")
    entity = world.entities[primary.subject.id]

    assert entity.kind == "human.interrupt"
    assert entity.zone == "inspection_gate"
    assert entity.status == "waiting"
    assert "langgraph.interrupt.reobserved" not in world.unknown_event_types


def test_checkpoint_snapshot_does_not_downgrade_live_waiting_interrupt():
    interrupt = {"id": "approval-1", "value": "review"}
    parts = [
        {
            "type": "tasks",
            "ns": ["review"],
            "data": {
                "id": "task-1",
                "name": "review",
                "error": None,
                "result": {},
                "interrupts": [interrupt],
            },
        },
        {
            "type": "checkpoints",
            "ns": ["review"],
            "data": {
                "config": None,
                "metadata": {},
                "values": {},
                "next": [],
                "parent_config": None,
                "tasks": [
                    {
                        "id": "task-1",
                        "name": "review",
                        "state": None,
                        "interrupts": [interrupt],
                    }
                ],
            },
        },
    ]
    events = stamp(langgraph_v2_to_events(parts, run_id="live-then-snapshot"))
    primary = next(event for event in events if event.event_type == "human.interrupt")

    assert any(event.event_type == "human.interrupt.snapshot" for event in events)

    world = project_world(events, run_id="live-then-snapshot")
    entity = world.entities[primary.subject.id]

    assert entity.kind == "human.interrupt"
    assert entity.zone == "inspection_gate"
    assert entity.status == "waiting"

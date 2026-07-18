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
    extensions=None,
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
        extensions=extensions or {},
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
    assert state.context.overflow is False
    assert state.context.items["ctx-1"]["status"] == "included"
    assert set(state.memory.layer_operations) == {"episodic"}
    assert state.memory.writes == 1
    assert state.memory.hits == 1
    assert state.memory.items["mem-1"]["score"] == 0.91
    assert state.compactions["cmp-1"].status == "completed"
    assert state.compactions["cmp-1"].tokens_removed == 490
    assert round(state.compactions["cmp-1"].reduction_ratio, 3) == 0.544


def test_memory_layers_expose_recorded_operations_and_not_invented_population():
    state = project_world(rich_run(), run_id="run-world")

    assert set(state.memory.layer_operations) == {"episodic"}
    episodic = state.memory.layer_operations["episodic"]
    assert episodic.event_count == 2
    assert episodic.event_type_counts == {"memory.written": 1, "memory.hit": 1}
    assert episodic.first_event_id == "e5"
    assert episodic.last_event_id == "e6"
    assert episodic.last_seq == 6
    assert episodic.truth.level == EvidenceLevel.OBSERVED
    assert episodic.truth.source_adapter == "tests"
    assert state.memory.layer_population == {}
    assert not {"working", "episodic", "semantic"} & state.memory.model_dump().keys()


def test_zone_event_counts_keep_full_cursor_history_beyond_recent_window():
    events = [event("zone-start", "run.started")]
    events.extend(
        event(f"zone-model-{index}", "model.response.chunk")
        for index in range(90)
    )

    state = project_world(stamp(events), run_id="run-world")

    assert len(state.recent_events) == 80
    assert state.zone_event_counts == {"control": 1, "model_engine": 90}
    assert state.zone_latest_events["model_engine"].event_id == "zone-model-89"
    assert state.zone_latest_events["model_engine"].seq == 90


def measurement_semantics(
    aggregate_key: str,
    *,
    owner_id: str,
    temporality: str = "unknown",
) -> dict:
    return {
        "anthill.measurements": {
            "schema_version": "1.0.0",
            "items": {
                "input_tokens": {
                    "aggregate_key": aggregate_key,
                    "unit": "tokens",
                    "scope": "model_call",
                    "aggregation": "sum",
                    "temporality": temporality,
                    "owner_id": owner_id,
                }
            }
        }
    }


def test_empty_world_context_status_is_unknown_not_idle():
    state = project_world(
        stamp([event("context-unobserved", "run.started")]),
        run_id="run-world",
    )

    assert state.context.last_event_id is None
    assert state.context.status == "unknown"
    assert state.context.overflow is None


def test_delta_owner_overflow_is_persistently_ambiguous():
    state = project_world(
        stamp(
            [
                event(
                    "usage-delta-overflow-1",
                    "model.response.chunk",
                    measurements={"input_tokens": 1e308},
                    extensions=measurement_semantics(
                        "model_call.input_tokens",
                        owner_id="model-call-delta-overflow",
                        temporality="delta",
                    ),
                ),
                event(
                    "usage-delta-overflow-2",
                    "model.response.chunk",
                    measurements={"input_tokens": 1e308},
                    extensions=measurement_semantics(
                        "model_call.input_tokens",
                        owner_id="model-call-delta-overflow",
                        temporality="delta",
                    ),
                ),
                event(
                    "usage-delta-after-overflow",
                    "model.response.completed",
                    measurements={"input_tokens": 1},
                    extensions=measurement_semantics(
                        "model_call.input_tokens",
                        owner_id="model-call-delta-overflow",
                        temporality="delta",
                    ),
                ),
            ]
        ),
        run_id="run-world",
    )
    aggregate = state.measurement_aggregates["model_call.input_tokens"]
    owner = aggregate.owners["model-call-delta-overflow"]

    assert aggregate.status == "ambiguous"
    assert aggregate.value is None
    assert owner.status == "ambiguous"
    assert owner.contribution is None
    assert any("non-finite" in reason for reason in aggregate.conflict_reasons)
    assert "input_tokens" not in state.totals


def test_cross_owner_aggregate_overflow_is_persistently_ambiguous():
    events = [
        event(
            f"usage-owner-overflow-{owner_id}",
            "model.response.completed",
            measurements={"input_tokens": 1e308},
            extensions=measurement_semantics(
                "model_call.input_tokens",
                owner_id=owner_id,
                temporality="cumulative",
            ),
        )
        for owner_id in ("model-call-overflow-a", "model-call-overflow-b")
    ]
    events.append(
        event(
            "usage-owner-after-overflow",
            "model.response.completed",
            measurements={"input_tokens": 1},
            extensions=measurement_semantics(
                "model_call.input_tokens",
                owner_id="model-call-overflow-c",
                temporality="cumulative",
            ),
        )
    )

    state = project_world(stamp(events), run_id="run-world")
    aggregate = state.measurement_aggregates["model_call.input_tokens"]

    assert aggregate.status == "ambiguous"
    assert aggregate.value is None
    assert any("non-finite" in reason for reason in aggregate.conflict_reasons)
    assert "input_tokens" not in state.totals


def test_calculated_total_overflow_is_ambiguous_not_infinite():
    extensions = {
        "anthill.measurements": {
            "schema_version": "1.0.0",
            "items": {
                key: {
                    "aggregate_key": f"model_call.{key}",
                    "unit": "tokens",
                    "scope": "model_call",
                    "aggregation": "sum",
                    "temporality": "cumulative",
                    "owner_id": "model-call-calculated-overflow",
                }
                for key in ("input_tokens", "output_tokens")
            },
        }
    }
    state = project_world(
        stamp(
            [
                event(
                    "usage-calculated-overflow",
                    "model.response.completed",
                    measurements={
                        "input_tokens": 1e308,
                        "output_tokens": 1e308,
                    },
                    extensions=extensions,
                )
            ]
        ),
        run_id="run-world",
    )
    calculated = state.calculated_measurements["model_call.total_tokens"]

    assert calculated.status == "ambiguous"
    assert calculated.value is None
    assert any("non-finite" in reason for reason in calculated.conflict_reasons)


def test_unrepresentable_huge_integer_measurement_is_ambiguous():
    state = project_world(
        stamp(
            [
                event(
                    "usage-huge-integer",
                    "model.response.completed",
                    measurements={"input_tokens": 10**400},
                    extensions=measurement_semantics(
                        "model_call.input_tokens",
                        owner_id="model-call-huge-integer",
                        temporality="cumulative",
                    ),
                )
            ]
        ),
        run_id="run-world",
    )
    aggregate = state.measurement_aggregates["model_call.input_tokens"]

    assert aggregate.status == "ambiguous"
    assert aggregate.value is None
    assert aggregate.invalid_sample_count == 1
    assert state.measurement_issues[-1].reason == "invalid non-negative finite value"
    assert "input_tokens" not in state.totals


def test_latest_measurement_with_multiple_owners_is_persistently_ambiguous():
    def run_elapsed_semantics(owner_id: str) -> dict:
        return {
            "anthill.measurements": {
                "schema_version": "1.0.0",
                "items": {
                    "run_duration_ms": {
                        "aggregate_key": "run.elapsed_ms",
                        "unit": "ms",
                        "scope": "run",
                        "aggregation": "latest",
                        "temporality": "cumulative",
                        "owner_id": owner_id,
                    }
                },
            }
        }

    state = project_world(
        stamp(
            [
                event(
                    "run-elapsed-owner-a",
                    "run.started",
                    measurements={"run_duration_ms": 100},
                    extensions=run_elapsed_semantics("run-world"),
                ),
                event(
                    "run-elapsed-owner-b",
                    "run.paused",
                    measurements={"run_duration_ms": 110},
                    extensions=run_elapsed_semantics("external-run-alias"),
                ),
                event(
                    "run-elapsed-after-conflict",
                    "run.completed",
                    measurements={"run_duration_ms": 120},
                    extensions=run_elapsed_semantics("run-world"),
                ),
            ]
        ),
        run_id="run-world",
    )
    aggregate = state.measurement_aggregates["run.elapsed_ms"]

    assert aggregate.owner_count == 2
    assert aggregate.status == "ambiguous"
    assert aggregate.value is None
    assert "latest aggregation has multiple owners" in aggregate.conflict_reasons
    assert "run_duration_ms" not in state.totals


def test_measurement_aggregate_does_not_guess_repeated_unknown_temporality():
    events = stamp(
        [
            event(
                "usage-1",
                "model.response.chunk",
                measurements={"input_tokens": 10},
                extensions=measurement_semantics(
                    "model_call.input_tokens", owner_id="model-call-1"
                ),
            ),
            event(
                "usage-2",
                "model.response.chunk",
                measurements={"input_tokens": 12},
                extensions=measurement_semantics(
                    "model_call.input_tokens", owner_id="model-call-1"
                ),
            ),
        ]
    )

    state = project_world(events, run_id="run-world")
    aggregate = state.measurement_aggregates["model_call.input_tokens"]

    assert "input_tokens" not in state.totals
    assert aggregate.status == "ambiguous"
    assert aggregate.value is None
    assert aggregate.sample_count == 2
    assert aggregate.owner_count == 1
    assert aggregate.first_event_id == "usage-1"
    assert aggregate.last_event_id == "usage-2"
    assert "unknown temporality" in aggregate.warnings[0]


def test_measurement_aggregate_sums_one_safe_sample_per_owner_with_provenance():
    events = stamp(
        [
            event(
                "usage-a",
                "model.response.chunk",
                measurements={"input_tokens": 10, "total_tokens": 10},
                extensions=measurement_semantics(
                    "model_call.input_tokens", owner_id="model-call-a"
                ),
            ),
            event(
                "usage-b",
                "model.response.chunk",
                measurements={"input_tokens": 12},
                extensions=measurement_semantics(
                    "model_call.input_tokens", owner_id="model-call-b"
                ),
            ),
        ]
    )

    state = project_world(events, run_id="run-world")
    aggregate = state.measurement_aggregates["model_call.input_tokens"]

    assert state.totals["input_tokens"] == 22
    assert "total_tokens" not in state.totals
    assert aggregate.status == "available"
    assert aggregate.value == 22
    assert aggregate.sample_count == 2
    assert aggregate.owner_count == 2
    assert aggregate.evidence_counts == {"observed": 2}
    assert aggregate.source_adapters == ["tests"]


def test_measurement_aggregate_uses_latest_cumulative_sample_per_owner():
    events = stamp(
        [
            event(
                "usage-cumulative-1",
                "model.response.chunk",
                measurements={"input_tokens": 10},
                extensions=measurement_semantics(
                    "model_call.input_tokens",
                    owner_id="model-call-cumulative",
                    temporality="cumulative",
                ),
            ),
            event(
                "usage-cumulative-2",
                "model.response.chunk",
                measurements={"input_tokens": 12},
                extensions=measurement_semantics(
                    "model_call.input_tokens",
                    owner_id="model-call-cumulative",
                    temporality="cumulative",
                ),
            ),
        ]
    )

    state = project_world(events, run_id="run-world")
    aggregate = state.measurement_aggregates["model_call.input_tokens"]

    assert aggregate.status == "available"
    assert aggregate.value == 12
    assert aggregate.sample_count == 2


def test_cumulative_measurement_decrease_is_an_explicit_conflict():
    state = project_world(
        stamp(
            [
                event(
                    "usage-cumulative-high",
                    "model.response.chunk",
                    measurements={"input_tokens": 12},
                    extensions=measurement_semantics(
                        "model_call.input_tokens",
                        owner_id="model-call-decreasing",
                        temporality="cumulative",
                    ),
                ),
                event(
                    "usage-cumulative-low",
                    "model.response.completed",
                    measurements={"input_tokens": 9},
                    extensions=measurement_semantics(
                        "model_call.input_tokens",
                        owner_id="model-call-decreasing",
                        temporality="cumulative",
                    ),
                ),
            ]
        ),
        run_id="run-world",
    )
    aggregate = state.measurement_aggregates["model_call.input_tokens"]

    assert aggregate.status == "ambiguous"
    assert aggregate.value is None
    assert "input_tokens" not in state.totals
    assert any(
        "cumulative value decreased" in reason
        for reason in aggregate.conflict_reasons
    )


def test_measurement_owner_temporality_change_is_a_conflict():
    events = stamp(
        [
            event(
                "usage-delta",
                "model.response.chunk",
                measurements={"input_tokens": 10},
                extensions=measurement_semantics(
                    "model_call.input_tokens",
                    owner_id="model-call-changing",
                    temporality="delta",
                ),
            ),
            event(
                "usage-cumulative",
                "model.response.chunk",
                measurements={"input_tokens": 18},
                extensions=measurement_semantics(
                    "model_call.input_tokens",
                    owner_id="model-call-changing",
                    temporality="cumulative",
                ),
            ),
        ]
    )

    state = project_world(events, run_id="run-world")
    aggregate = state.measurement_aggregates["model_call.input_tokens"]

    assert aggregate.status == "ambiguous"
    assert aggregate.value is None
    assert "temporality changed" in aggregate.conflict_reasons[0]
    assert "input_tokens" not in state.totals


def test_unclassified_matching_measurement_hides_a_partial_safe_total():
    state = project_world(
        stamp(
            [
                event(
                    "usage-safe",
                    "model.response.chunk",
                    measurements={"input_tokens": 10},
                    extensions=measurement_semantics(
                        "model_call.input_tokens", owner_id="model-call-safe"
                    ),
                ),
                event(
                    "usage-unclassified",
                    "model.response.chunk",
                    measurements={"input_tokens": 5},
                ),
            ]
        ),
        run_id="run-world",
    )
    aggregate = state.measurement_aggregates["model_call.input_tokens"]

    assert aggregate.status == "ambiguous"
    assert aggregate.value is None
    assert "unclassified input_tokens" in aggregate.conflict_reasons[0]
    assert "input_tokens" not in state.totals


def test_unclassified_measurement_remains_blocking_after_issue_tail_truncation():
    events = [
        event(
            "usage-unclassified-early",
            "model.response.chunk",
            measurements={"input_tokens": 5},
        )
    ]
    events.extend(
        event(
            f"unrelated-issue-{index}",
            "model.response.chunk",
            measurements={f"unrelated_{index}": index},
        )
        for index in range(100)
    )
    events.append(
        event(
            "usage-safe-late",
            "model.response.completed",
            measurements={"input_tokens": 10},
            extensions=measurement_semantics(
                "model_call.input_tokens", owner_id="model-call-safe-late"
            ),
        )
    )

    state = project_world(stamp(events), run_id="run-world")
    aggregate = state.measurement_aggregates["model_call.input_tokens"]

    assert len(state.measurement_issues) == 100
    assert all(
        issue.measurement_key != "input_tokens" for issue in state.measurement_issues
    )
    assert state.unclassified_measurement_counts["input_tokens"] == 1
    assert aggregate.unclassified_measurement_counts == {"input_tokens": 1}
    assert aggregate.status == "ambiguous"
    assert aggregate.value is None
    assert "input_tokens" not in state.totals


def test_snapshot_resume_preserves_cumulative_owner_contribution():
    events = stamp(
        [
            event(
                "usage-before-snapshot",
                "model.response.chunk",
                measurements={"input_tokens": 10},
                extensions=measurement_semantics(
                    "model_call.input_tokens",
                    owner_id="model-call-snapshot",
                    temporality="cumulative",
                ),
            ),
            event(
                "usage-after-snapshot",
                "model.response.chunk",
                measurements={"input_tokens": 12},
                extensions=measurement_semantics(
                    "model_call.input_tokens",
                    owner_id="model-call-snapshot",
                    temporality="cumulative",
                ),
            ),
        ]
    )
    snapshot_state = project_world(events[:1], run_id="run-world")
    restored = type(snapshot_state).model_validate_json(snapshot_state.model_dump_json())
    resumed = project_world(events[1:], run_id="run-world", initial_state=restored)

    assert resumed.measurement_aggregates["model_call.input_tokens"].value == 12
    assert resumed.totals["input_tokens"] == 12


def test_safe_total_tokens_is_not_dropped_from_aggregate_or_legacy_alias():
    extensions = measurement_semantics(
        "model_call.input_tokens", owner_id="model-call-total"
    )
    extensions["anthill.measurements"]["items"] = {
        "total_tokens": {
            "aggregate_key": "model_call.total_tokens",
            "unit": "tokens",
            "scope": "model_call",
            "aggregation": "sum",
            "temporality": "cumulative",
            "owner_id": "model-call-total",
        }
    }
    state = project_world(
        stamp(
            [
                event(
                    "safe-total",
                    "model.response.completed",
                    measurements={"total_tokens": 19},
                    extensions=extensions,
                )
            ]
        ),
        run_id="run-world",
    )

    assert state.measurement_aggregates["model_call.total_tokens"].value == 19
    assert state.totals["total_tokens"] == 19


def test_calculated_total_tokens_is_a_separate_derived_view():
    extensions = {
        "anthill.measurements": {
            "schema_version": "1.0.0",
            "items": {
                "input_tokens": {
                    "aggregate_key": "model_call.input_tokens",
                    "unit": "tokens",
                    "scope": "model_call",
                    "aggregation": "sum",
                    "temporality": "cumulative",
                    "owner_id": "model-call-calculated",
                },
                "output_tokens": {
                    "aggregate_key": "model_call.output_tokens",
                    "unit": "tokens",
                    "scope": "model_call",
                    "aggregation": "sum",
                    "temporality": "cumulative",
                    "owner_id": "model-call-calculated",
                },
            },
        }
    }
    state = project_world(
        stamp(
            [
                event(
                    "usage-calculated",
                    "model.response.completed",
                    measurements={"input_tokens": 10, "output_tokens": 4},
                    extensions=extensions,
                )
            ]
        ),
        run_id="run-world",
    )

    calculated = state.calculated_measurements["model_call.total_tokens"]
    assert calculated.key == "model_call.total_tokens"
    assert calculated.status == "available"
    assert calculated.value == 14
    assert calculated.unit == "tokens"
    assert calculated.scope == "model_call"
    assert calculated.aggregation == "derived"
    assert calculated.calculation == (
        "model_call.input_tokens + model_call.output_tokens"
    )
    assert calculated.components == {
        "model_call.input_tokens": 10,
        "model_call.output_tokens": 4,
    }
    assert calculated.component_statuses == {
        "model_call.input_tokens": "available",
        "model_call.output_tokens": "available",
    }
    assert calculated.explicit_consistency == "not_observed"
    assert calculated.explicit_value is None
    assert calculated.evidence_event_ids == ["usage-calculated"]
    assert calculated.last_event_id == "usage-calculated"


def test_calculated_total_conflicts_with_a_mismatched_explicit_total():
    extensions = {
        "anthill.measurements": {
            "schema_version": "1.0.0",
            "items": {
                key: {
                    "aggregate_key": f"model_call.{key}",
                    "unit": "tokens",
                    "scope": "model_call",
                    "aggregation": "sum",
                    "temporality": "cumulative",
                    "owner_id": "model-call-total-conflict",
                }
                for key in ("input_tokens", "output_tokens", "total_tokens")
            },
        }
    }
    state = project_world(
        stamp(
            [
                event(
                    "usage-total-conflict",
                    "model.response.completed",
                    measurements={
                        "input_tokens": 10,
                        "output_tokens": 4,
                        "total_tokens": 15,
                    },
                    extensions=extensions,
                )
            ]
        ),
        run_id="run-world",
    )

    explicit = state.measurement_aggregates["model_call.total_tokens"]
    calculated = state.calculated_measurements["model_call.total_tokens"]
    assert explicit.status == "available"
    assert explicit.value == 15
    assert state.totals["total_tokens"] == 15
    assert calculated.status == "ambiguous"
    assert calculated.value is None
    assert calculated.explicit_value == 15
    assert calculated.explicit_consistency == "conflict"
    assert calculated.conflict_reasons == [
        "explicit model_call.total_tokens 15 does not match calculated 14"
    ]


def test_matching_explicit_total_is_not_added_to_calculated_total():
    extensions = {
        "anthill.measurements": {
            "schema_version": "1.0.0",
            "items": {
                key: {
                    "aggregate_key": f"model_call.{key}",
                    "unit": "tokens",
                    "scope": "model_call",
                    "aggregation": "sum",
                    "temporality": "cumulative",
                    "owner_id": "model-call-total-match",
                }
                for key in ("input_tokens", "output_tokens", "total_tokens")
            },
        }
    }
    state = project_world(
        stamp(
            [
                event(
                    "usage-total-match",
                    "model.response.completed",
                    measurements={
                        "input_tokens": 10,
                        "output_tokens": 4,
                        "total_tokens": 14,
                    },
                    extensions=extensions,
                )
            ]
        ),
        run_id="run-world",
    )

    calculated = state.calculated_measurements["model_call.total_tokens"]
    assert calculated.status == "available"
    assert calculated.value == 14
    assert calculated.explicit_consistency == "matches"
    assert state.measurement_aggregates["model_call.total_tokens"].value == 14
    assert state.totals["total_tokens"] == 14


def test_measurement_without_semantics_is_not_promoted_to_safe_aggregate():
    state = project_world(
        stamp(
            [
                event(
                    "unsafe-usage",
                    "model.response.chunk",
                    measurements={"input_tokens": 10},
                )
            ]
        ),
        run_id="run-world",
    )

    assert state.measurement_aggregates == {}
    assert state.measurement_issues[0].event_id == "unsafe-usage"
    assert state.measurement_issues[0].measurement_key == "input_tokens"
    assert state.measurement_issues[0].reason == "missing or invalid semantics"


def test_invalid_measurement_semantics_are_counted_as_unclassified():
    invalid_extensions = measurement_semantics(
        "model_call.input_tokens", owner_id="model-call-invalid-semantics"
    )
    invalid_extensions["anthill.measurements"]["items"]["input_tokens"][
        "scope"
    ] = "tool_call"
    state = project_world(
        stamp(
            [
                event(
                    "invalid-semantics",
                    "model.response.completed",
                    measurements={"input_tokens": 0},
                    extensions=invalid_extensions,
                )
            ]
        ),
        run_id="run-world",
    )

    assert state.measurement_aggregates == {}
    assert state.unclassified_measurement_counts == {"input_tokens": 1}
    assert state.measurement_issues[0].reason == "missing or invalid semantics"


def test_zero_measurement_with_valid_semantics_is_available():
    state = project_world(
        stamp(
            [
                event(
                    "zero-usage",
                    "model.response.completed",
                    measurements={"input_tokens": 0},
                    extensions=measurement_semantics(
                        "model_call.input_tokens",
                        owner_id="model-call-zero",
                        temporality="cumulative",
                    ),
                )
            ]
        ),
        run_id="run-world",
    )
    aggregate = state.measurement_aggregates["model_call.input_tokens"]

    assert aggregate.status == "available"
    assert aggregate.value == 0
    assert state.totals["input_tokens"] == 0
    assert state.unclassified_measurement_counts == {}


def test_invalid_numeric_measurement_remains_blocking_after_issue_tail_truncation():
    events = [
        event(
            "invalid-negative-usage",
            "model.response.chunk",
            measurements={"input_tokens": -1},
            extensions=measurement_semantics(
                "model_call.input_tokens",
                owner_id="model-call-invalid-numeric",
                temporality="cumulative",
            ),
        )
    ]
    events.extend(
        event(
            f"invalid-tail-noise-{index}",
            "model.response.chunk",
            measurements={f"invalid_tail_noise_{index}": index},
        )
        for index in range(100)
    )
    events.append(
        event(
            "valid-after-invalid-numeric",
            "model.response.completed",
            measurements={"input_tokens": 10},
            extensions=measurement_semantics(
                "model_call.input_tokens",
                owner_id="model-call-valid-after-invalid",
                temporality="cumulative",
            ),
        )
    )

    state = project_world(stamp(events), run_id="run-world")
    aggregate = state.measurement_aggregates["model_call.input_tokens"]

    assert aggregate.invalid_sample_count == 1
    assert aggregate.status == "ambiguous"
    assert aggregate.value is None
    assert any("invalid numeric input_tokens" in reason for reason in aggregate.conflict_reasons)
    assert "input_tokens" not in state.totals


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

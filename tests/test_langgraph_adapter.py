import json
from pathlib import Path

import pytest

from anthill.adapters.langgraph import LangGraphImportError, langgraph_v2_to_events
from anthill.schema import ContentCapture, EvidenceLevel, LinkType, SourceFidelity


FIXTURE = Path(__file__).parent / "fixtures" / "langgraph_stream_v2.json"


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_langgraph_v2_maps_tasks_state_messages_checkpoints_and_boundaries():
    first = langgraph_v2_to_events(load_fixture())
    second = langgraph_v2_to_events(load_fixture())

    assert [event.event_id for event in first] == [event.event_id for event in second]
    assert [event.event_type for event in first] == [
        "manifest.snapshot",
        "run.started",
        "agent.step.started",
        "model.response.chunk",
        "agent.state.changed",
        "agent.step.completed",
        "agent.step.started",
        "langgraph.custom",
        "agent.step.completed",
        "checkpoint.created",
        "checkpoint.created",
        "context.shared_state.snapshot",
        "run.completed",
    ]
    assert all(event.run_id == "langgraph-run" for event in first)
    assert all(event.thread_id == "langgraph-thread" for event in first)
    assert first[0].evidence.level == EvidenceLevel.OBSERVED
    assert first[1].evidence.level == EvidenceLevel.INFERRED
    assert all(event.evidence.level == EvidenceLevel.OBSERVED for event in first[2:-1])
    assert first[-1].evidence.level == EvidenceLevel.DECLARED
    assert all(event.source.fidelity == SourceFidelity.MAPPED for event in first)
    assert all(event.source.semantic_convention == "langgraph.stream" for event in first)
    assert all(event.source.semantic_convention_version == "v2" for event in first)
    assert all(event.source.framework_version == "1.1.0" for event in first)

    task_start = next(
        event
        for event in first
        if event.subject
        and event.subject.name == "planner"
        and event.event_type.endswith("started")
    )
    task_end = next(
        event
        for event in first
        if event.subject
        and event.subject.name == "planner"
        and event.event_type.endswith("completed")
    )
    assert task_end.causation_id == task_start.event_id

    checkpoints = [event for event in first if event.event_type == "checkpoint.created"]
    assert checkpoints[1].links[0].type == LinkType.DERIVED_FROM
    assert checkpoints[1].links[0].event_id == checkpoints[0].event_id
    assert first[-1].event_type == "run.completed"
    assert first[-1].payload["status"] == "completed"


def test_langgraph_default_redacts_all_state_message_task_and_custom_content():
    events = langgraph_v2_to_events(load_fixture())
    serialized = "\n".join(event.model_dump_json() for event in events)

    assert "SECRET_" not in serialized
    assert all(event.privacy.content == ContentCapture.METADATA_ONLY for event in events)

    task = next(event for event in events if event.event_type == "agent.step.started")
    assert task.payload["input_keys"] == ["question"]
    message = next(event for event in events if event.event_type == "model.response.chunk")
    assert message.payload["content_chars"] == len("SECRET_MODEL_TOKEN")
    assert message.payload["tag_count"] == 1
    update = next(event for event in events if event.event_type == "agent.state.changed")
    assert update.payload["updates"] == {"planner": ["plan"]}
    custom = next(event for event in events if event.event_type == "langgraph.custom")
    assert custom.payload["data_keys"] == ["percent", "progress"]
    checkpoint = next(event for event in events if event.event_type == "checkpoint.created")
    assert checkpoint.payload["state_keys"] == ["plan"]


def test_langgraph_partial_stream_never_invents_completion_and_rejects_v1_tuples():
    payload = load_fixture()
    payload["complete"] = False
    events = langgraph_v2_to_events(payload)

    assert events[-1].event_type == "context.shared_state.snapshot"
    assert not any(event.event_type == "run.completed" for event in events)

    with pytest.raises(LangGraphImportError, match="StreamPart v2"):
        langgraph_v2_to_events([("updates", {"planner": {"answer": "x"}})], run_id="legacy")


def test_langgraph_ndjson_is_available_from_the_public_adapter_interface():
    from anthill.adapters import langgraph_ndjson_to_events

    payload = load_fixture()
    ndjson = "\n".join(json.dumps(part) for part in payload["parts"])
    events = langgraph_ndjson_to_events(
        ndjson,
        run_id="ndjson-run",
        thread_id="langgraph-thread",
        framework_version="1.1.0",
        stream_complete=True,
    )

    assert events[0].event_type == "manifest.snapshot"
    assert events[-1].event_type == "run.completed"
    assert all(event.run_id == "ndjson-run" for event in events)


def test_langgraph_never_links_a_task_result_to_a_future_start():
    payload = {
        "streamVersion": "v2",
        "runId": "out-of-order-run",
        "complete": False,
        "parts": [
            {
                "type": "tasks",
                "ns": [],
                "data": {
                    "id": "task-1",
                    "name": "planner",
                    "error": None,
                    "interrupts": [],
                    "result": {"answer": "SECRET_RESULT"},
                },
            },
            {
                "type": "tasks",
                "ns": [],
                "data": {
                    "id": "task-1",
                    "name": "planner",
                    "input": {"question": "SECRET_INPUT"},
                    "triggers": ["start:planner"],
                },
            },
        ],
    }

    result = next(
        event
        for event in langgraph_v2_to_events(payload)
        if event.event_type == "agent.step.completed"
    )

    assert result.causation_id is None


def test_langgraph_checkpoint_lineage_only_links_to_a_prior_distinct_checkpoint():
    def checkpoint(checkpoint_id, parent_id=None):
        return {
            "type": "checkpoints",
            "ns": [],
            "data": {
                "config": {"configurable": {"checkpoint_id": checkpoint_id}},
                "parent_config": (
                    {"configurable": {"checkpoint_id": parent_id}} if parent_id else None
                ),
                "metadata": {},
                "values": {},
                "next": [],
                "tasks": [],
            },
        }

    events = langgraph_v2_to_events(
        [
            checkpoint("parent"),
            checkpoint("child", "parent"),
            checkpoint("parent"),
            checkpoint("self", "self"),
        ],
        run_id="checkpoint-lineage",
    )
    checkpoints = [event for event in events if event.event_type == "checkpoint.created"]

    assert checkpoints[1].links[0].event_id == checkpoints[0].event_id
    assert checkpoints[3].links == []


def test_langgraph_synthetic_run_boundaries_do_not_invent_causation():
    events = langgraph_v2_to_events(
        [{"type": "values", "ns": [], "data": {"phase": "done"}, "interrupts": []}],
        run_id="boundary-causation",
        stream_complete=True,
    )

    assert events[1].event_type == "run.started"
    assert events[1].causation_id is None
    assert events[-1].event_type == "run.completed"
    assert events[-1].causation_id is None


def test_langgraph_deduplicates_the_same_interrupt_across_requested_modes():
    interrupt = {"id": "interrupt-1", "value": {"question": "SECRET_REVIEW"}}
    events = langgraph_v2_to_events(
        [
            {
                "type": "updates",
                "ns": [],
                "data": {"__interrupt__": [interrupt]},
            },
            {
                "type": "values",
                "ns": [],
                "data": {"phase": "review"},
                "interrupts": [interrupt],
            },
            {
                "type": "tasks",
                "ns": [],
                "data": {
                    "id": "task-1",
                    "name": "review",
                    "error": None,
                    "result": {},
                    "interrupts": [interrupt],
                },
            },
        ],
        run_id="interrupt-deduplication",
    )

    primary = [event for event in events if event.event_type == "human.interrupt"]
    reobserved = [event for event in events if event.event_type == "langgraph.interrupt.reobserved"]
    assert len(primary) == 1
    assert len(reobserved) == 2
    assert all(
        any(
            link.type == LinkType.RELATED and link.event_id == primary[0].event_id
            for link in event.links
        )
        for event in reobserved
    )
    assert "SECRET_REVIEW" not in "\n".join(event.model_dump_json() for event in events)


def test_langgraph_completion_outcome_requires_an_explicit_status():
    payload = {
        "streamVersion": "v2",
        "runId": "resumed-run",
        "complete": True,
        "parts": [
            {
                "type": "values",
                "ns": [],
                "data": {"phase": "review"},
                "interrupts": [{"id": "interrupt-1", "value": "SECRET_REVIEW"}],
            },
            {
                "type": "tasks",
                "ns": [],
                "data": {
                    "id": "task-2",
                    "name": "review",
                    "error": None,
                    "result": {"approved": True},
                    "interrupts": [],
                },
            },
        ],
    }

    assert langgraph_v2_to_events(payload)[-1].payload["status"] == "completed"
    payload["runStatus"] = "success"
    assert langgraph_v2_to_events(payload)[-1].payload["status"] == "success"


def test_langgraph_explicit_completion_preserves_observed_failure_status():
    payload = {
        "streamVersion": "v2",
        "runId": "failed-run",
        "complete": True,
        "runStatus": "failed",
        "parts": [
            {
                "type": "tasks",
                "ns": [],
                "data": {
                    "id": "task-1",
                    "name": "planner",
                    "error": "SECRET_FAILURE",
                    "interrupts": [],
                    "result": {},
                },
            }
        ],
    }

    events = langgraph_v2_to_events(payload)

    assert events[-2].event_type == "error.raised"
    assert events[-1].event_type == "run.completed"
    assert events[-1].payload["status"] == "failed"
    assert "SECRET_FAILURE" not in events[-2].model_dump_json()


def test_langgraph_expands_interrupts_and_checkpoint_task_failures_without_losing_state():
    payload = {
        "streamVersion": "v2",
        "runId": "interrupt-run",
        "complete": False,
        "parts": [
            {
                "type": "values",
                "ns": [],
                "data": {"phase": "SECRET_STATE"},
                "interrupts": [{"id": "interrupt-values", "value": "SECRET_REVIEW_REQUEST"}],
            },
            {
                "type": "updates",
                "ns": [],
                "data": {
                    "planner": {"phase": "SECRET_UPDATE"},
                    "__interrupt__": [{"id": "interrupt-update", "value": "SECRET_UPDATE_REVIEW"}],
                    "__metadata__": {"cached": False},
                },
            },
            {
                "type": "checkpoints",
                "ns": [],
                "data": {
                    "config": {
                        "configurable": {
                            "thread_id": "thread-1",
                            "checkpoint_id": "checkpoint-1",
                            "checkpoint_ns": "",
                        }
                    },
                    "metadata": {"step": 1, "source": "loop", "writes": None},
                    "values": {"phase": "SECRET_CHECKPOINT"},
                    "next": ["review"],
                    "parent_config": None,
                    "tasks": [
                        {
                            "id": "failed-task",
                            "name": "worker",
                            "state": None,
                            "error": "SECRET_CHECKPOINT_ERROR",
                        },
                        {
                            "id": "paused-task",
                            "name": "review",
                            "state": None,
                            "interrupts": [
                                {
                                    "id": "interrupt-checkpoint",
                                    "value": "SECRET_CHECKPOINT_REVIEW",
                                }
                            ],
                        },
                    ],
                },
            },
        ],
    }

    events = langgraph_v2_to_events(payload)
    event_types = [event.event_type for event in events]

    assert event_types == [
        "manifest.snapshot",
        "run.started",
        "context.shared_state.snapshot",
        "human.interrupt",
        "agent.state.changed",
        "human.interrupt",
        "checkpoint.created",
        "error.task_snapshot",
        "human.interrupt.snapshot",
    ]
    assert "SECRET_" not in "\n".join(event.model_dump_json() for event in events)
    assert [event.clock.source_seq for event in events] == list(range(len(events)))
    supplemental = [
        event
        for event in events
        if event.event_type
        in {"human.interrupt", "error.task_snapshot", "human.interrupt.snapshot"}
    ]
    assert all(event.links[0].type == LinkType.RELATED for event in supplemental)


@pytest.mark.parametrize(
    "part",
    [
        {
            "type": "tasks",
            "ns": [],
            "data": {"id": "task", "name": "node", "input": {}, "triggers": 1},
        },
        {
            "type": "messages",
            "ns": [],
            "data": [{"id": "message", "content": "x"}, {"tags": 1}],
        },
        {
            "type": "checkpoints",
            "ns": [],
            "data": {"config": {}, "metadata": {}, "values": {}, "next": 1, "tasks": []},
        },
    ],
)
def test_langgraph_rejects_invalid_mode_shapes_as_import_errors(part):
    with pytest.raises(LangGraphImportError, match="part 0"):
        langgraph_v2_to_events([part], run_id="invalid-shape")


def test_langgraph_metadata_identifiers_are_explicitly_flagged_as_sensitive():
    payload = {
        "streamVersion": "v2",
        "runId": "sensitive-metadata-run",
        "complete": False,
        "parts": [
            {
                "type": "custom",
                "ns": ["SECRET_NAMESPACE"],
                "data": {"SECRET_FIELD_NAME": "SECRET_VALUE"},
            }
        ],
    }

    events = langgraph_v2_to_events(payload)

    assert all(event.privacy.contains_sensitive_data is True for event in events)
    assert "SECRET_VALUE" not in events[-1].model_dump_json()
    assert "SECRET_NAMESPACE" in events[-1].model_dump_json()


@pytest.mark.parametrize("mode", [1, "x" * 201])
def test_langgraph_rejects_non_string_or_oversized_stream_modes(mode):
    with pytest.raises(LangGraphImportError, match="part 0 type"):
        langgraph_v2_to_events(
            [{"type": mode, "ns": [], "data": {}}],
            run_id="invalid-mode",
        )


def test_langgraph_interrupt_identity_is_scoped_to_namespace():
    interrupt = {"id": "shared-id", "value": "SECRET_REVIEW"}
    events = langgraph_v2_to_events(
        [
            {
                "type": "updates",
                "ns": ["parent"],
                "data": {"__interrupt__": [interrupt]},
            },
            {
                "type": "values",
                "ns": ["child"],
                "data": {"phase": "review"},
                "interrupts": [interrupt],
            },
        ],
        run_id="interrupt-namespace",
    )

    primary = [event for event in events if event.event_type == "human.interrupt"]
    assert len(primary) == 2
    assert all(event.event_type != "langgraph.interrupt.reobserved" for event in events)
    assert primary[0].subject.id != primary[1].subject.id


def test_langgraph_plaintext_capture_hashes_oversized_interrupt_ids_everywhere():
    oversized_id = "INTERRUPT_ID_SECRET_" + ("x" * 3_000)
    interrupt_value = "SECRET_REVIEW_VALUE"
    events = langgraph_v2_to_events(
        [
            {
                "type": "tasks",
                "ns": ["review"],
                "data": {
                    "id": "task-1",
                    "name": "approval",
                    "error": None,
                    "result": {},
                    "interrupts": [{"id": oversized_id, "value": interrupt_value}],
                },
            }
        ],
        run_id="plaintext-oversized-interrupt",
        capture_content=True,
    )

    serialized = "\n".join(event.model_dump_json() for event in events)
    assert oversized_id not in serialized

    task = next(event for event in events if event.event_type == "agent.step.interrupted")
    interrupt = next(event for event in events if event.event_type == "human.interrupt")
    hashed_id = task.payload["interrupt_ids"][0]

    assert hashed_id != oversized_id
    assert interrupt.payload["interrupt_id"] == hashed_id
    assert task.payload["content"]["interrupts"] == [{"id": hashed_id, "value": interrupt_value}]
    assert interrupt.payload["content"]["interrupt_value"] == interrupt_value


class _ExplodingRuntimeObject:
    def model_dump(self, **_kwargs):
        raise RuntimeError("SECRET_RUNTIME_DUMP_FAILURE")


class _SelfReturningRuntimeObject:
    def model_dump(self, **_kwargs):
        return self


@pytest.mark.parametrize(
    "runtime_object",
    [_ExplodingRuntimeObject(), _SelfReturningRuntimeObject()],
)
def test_langgraph_runtime_object_dump_failures_are_controlled_import_errors(
    runtime_object,
):
    with pytest.raises(LangGraphImportError, match="runtime object"):
        langgraph_v2_to_events(
            [{"type": "custom", "ns": [], "data": runtime_object}],
            run_id="invalid-runtime-object",
        )


def test_langgraph_task_causation_is_scoped_to_namespace():
    parts = [
        {
            "type": "tasks",
            "ns": ["parent"],
            "data": {
                "id": "shared-task",
                "name": "parent-node",
                "input": {},
                "triggers": [],
            },
        },
        {
            "type": "tasks",
            "ns": ["child"],
            "data": {
                "id": "shared-task",
                "name": "child-node",
                "input": {},
                "triggers": [],
            },
        },
        {
            "type": "tasks",
            "ns": ["parent"],
            "data": {
                "id": "shared-task",
                "name": "parent-node",
                "error": None,
                "result": {},
                "interrupts": [],
            },
        },
    ]

    events = langgraph_v2_to_events(parts, run_id="task-namespace-causation")
    starts = {
        tuple(event.extensions["langgraph"]["namespace"]): event
        for event in events
        if event.event_type == "agent.step.started"
    }
    result = next(event for event in events if event.event_type == "agent.step.completed")

    assert result.causation_id == starts[("parent",)].event_id
    assert result.causation_id != starts[("child",)].event_id
    assert starts[("parent",)].subject.id != starts[("child",)].subject.id


def test_langgraph_checkpoint_lineage_is_scoped_to_namespace():
    def checkpoint(namespace, checkpoint_id, parent_id=None):
        return {
            "type": "checkpoints",
            "ns": [namespace],
            "data": {
                "config": {
                    "configurable": {
                        "checkpoint_id": checkpoint_id,
                        "checkpoint_ns": namespace,
                    }
                },
                "parent_config": (
                    {
                        "configurable": {
                            "checkpoint_id": parent_id,
                            "checkpoint_ns": namespace,
                        }
                    }
                    if parent_id
                    else None
                ),
                "metadata": {},
                "values": {},
                "next": [],
                "tasks": [],
            },
        }

    events = langgraph_v2_to_events(
        [
            checkpoint("parent", "shared-checkpoint"),
            checkpoint("child", "shared-checkpoint"),
            checkpoint("parent", "child-checkpoint", "shared-checkpoint"),
        ],
        run_id="checkpoint-namespace-causation",
    )
    checkpoints = [event for event in events if event.event_type == "checkpoint.created"]

    assert [link.event_id for link in checkpoints[2].links] == [checkpoints[0].event_id]
    assert checkpoints[2].links[0].event_id != checkpoints[1].event_id
    assert checkpoints[0].subject.id != checkpoints[1].subject.id


def test_langgraph_empty_error_text_still_records_failure():
    events = langgraph_v2_to_events(
        [
            {
                "type": "tasks",
                "ns": ["worker"],
                "data": {
                    "id": "failed-task",
                    "name": "worker",
                    "error": "",
                    "result": {},
                    "interrupts": [],
                },
            }
        ],
        run_id="empty-error-text",
    )

    failure = next(event for event in events if event.clock.source_seq == 2)
    assert failure.event_type == "error.raised"
    assert failure.payload["status"] == "failed"


class _RuntimeCheckpointData:
    def model_dump(self, **_kwargs):
        return {
            "config": {
                "configurable": {
                    "thread_id": "runtime-thread",
                    "checkpoint_id": "runtime-checkpoint",
                    "checkpoint_ns": "runtime",
                }
            },
            "parent_config": None,
            "metadata": {},
            "values": {},
            "next": [],
            "tasks": [],
        }


def test_langgraph_runtime_checkpoint_supplies_thread_identity():
    events = langgraph_v2_to_events(
        [
            {
                "type": "checkpoints",
                "ns": ["runtime"],
                "data": _RuntimeCheckpointData(),
            }
        ],
        run_id="runtime-checkpoint-thread",
    )

    assert all(event.thread_id == "runtime-thread" for event in events)


def test_langgraph_rejects_nested_non_finite_plaintext_content():
    with pytest.raises(LangGraphImportError, match="finite"):
        langgraph_v2_to_events(
            [
                {
                    "type": "custom",
                    "ns": [],
                    "data": {"nested": {"value": float("nan")}},
                }
            ],
            run_id="nested-non-finite",
            capture_content=True,
        )


def test_langgraph_rejects_reserved_identity_separator_in_namespace():
    with pytest.raises(LangGraphImportError, match="reserved identity separator"):
        langgraph_v2_to_events(
            [{"type": "values", "ns": ["parent\x1fchild"], "data": {}}],
            run_id="namespace-component-framing",
        )


@pytest.mark.parametrize(
    "part",
    [
        {
            "type": "tasks",
            "ns": [],
            "data": {
                "id": "task\x1fchild",
                "name": "worker",
                "input": {},
                "triggers": [],
            },
        },
        {
            "type": "messages",
            "ns": [],
            "data": [
                {"id": "message\x1fchild", "type": "AIMessageChunk", "content": "x"},
                {},
            ],
        },
        {
            "type": "checkpoints",
            "ns": [],
            "data": {
                "config": {
                    "configurable": {
                        "checkpoint_id": "checkpoint\x1fchild",
                        "checkpoint_ns": "safe",
                    }
                },
                "parent_config": None,
                "metadata": {},
                "values": {},
                "next": [],
                "tasks": [],
            },
        },
        {
            "type": "checkpoints",
            "ns": [],
            "data": {
                "config": {
                    "configurable": {
                        "checkpoint_id": "checkpoint-safe",
                        "checkpoint_ns": "parent\x1fchild",
                    }
                },
                "parent_config": None,
                "metadata": {},
                "values": {},
                "next": [],
                "tasks": [],
            },
        },
        {
            "type": "values",
            "ns": [],
            "data": {},
            "interrupts": [{"id": "interrupt\x1fchild", "value": "review"}],
        },
    ],
    ids=["task-id", "message-id", "checkpoint-id", "checkpoint-ns", "interrupt-id"],
)
def test_langgraph_rejects_reserved_separator_in_structural_identity(part):
    with pytest.raises(LangGraphImportError, match="reserved identity separator"):
        langgraph_v2_to_events(
            [part],
            run_id="structural-identity-framing",
        )


def test_langgraph_checkpoint_interrupt_event_identity_is_structured():
    events = langgraph_v2_to_events(
        [
            {
                "type": "checkpoints",
                "ns": [],
                "data": {
                    "config": {
                        "configurable": {
                            "checkpoint_id": "checkpoint-1",
                            "checkpoint_ns": "",
                        }
                    },
                    "parent_config": None,
                    "metadata": {},
                    "values": {},
                    "next": [],
                    "tasks": [
                        {
                            "id": "task:a",
                            "name": "first",
                            "state": None,
                            "interrupts": [{"id": "b", "value": "first"}],
                        },
                        {
                            "id": "task",
                            "name": "second",
                            "state": None,
                            "interrupts": [{"id": "a:b", "value": "second"}],
                        },
                    ],
                },
            }
        ],
        run_id="checkpoint-interrupt-framing",
    )

    snapshots = [event for event in events if event.event_type == "human.interrupt.snapshot"]
    assert len(snapshots) == 2
    assert snapshots[0].event_id != snapshots[1].event_id


def test_langgraph_message_correlation_uses_message_identity():
    def message(message_id, content):
        return {
            "type": "messages",
            "ns": ["model"],
            "data": [
                {
                    "id": message_id,
                    "type": "AIMessageChunk",
                    "content": content,
                },
                {},
            ],
        }

    events = langgraph_v2_to_events(
        [
            message("message-a", "first"),
            message("message-b", "second"),
            message("message-a", "third"),
        ],
        run_id="message-correlation-identity",
    )
    chunks = [event for event in events if event.event_type == "model.response.chunk"]

    assert chunks[0].correlation_id != chunks[1].correlation_id
    assert chunks[0].correlation_id == chunks[2].correlation_id


@pytest.mark.parametrize(
    "part",
    [
        {
            "type": "tasks",
            "ns": [],
            "data": {
                "id": "task-start",
                "name": "worker",
                "input": {},
                "triggers": None,
            },
        },
        {
            "type": "tasks",
            "ns": [],
            "data": {
                "id": "task-result",
                "name": "worker",
                "error": None,
                "result": {},
                "interrupts": None,
            },
        },
        {
            "type": "checkpoints",
            "ns": [],
            "data": {
                "config": None,
                "metadata": {},
                "values": {},
                "next": None,
                "parent_config": None,
                "tasks": [],
            },
        },
        {
            "type": "checkpoints",
            "ns": [],
            "data": {
                "config": None,
                "metadata": {},
                "values": {},
                "next": [],
                "parent_config": None,
                "tasks": None,
            },
        },
    ],
    ids=[
        "task-start-triggers",
        "task-result-interrupts",
        "checkpoint-next",
        "checkpoint-tasks",
    ],
)
def test_langgraph_required_sequence_fields_reject_null(part):
    with pytest.raises(LangGraphImportError, match="must be an array"):
        langgraph_v2_to_events(
            [part],
            run_id="null-required-sequence",
        )


def _task_result_part(**overrides):
    data = {
        "id": "task-result",
        "name": "worker",
        "error": None,
        "result": {},
        "interrupts": [],
    }
    data.update(overrides)
    return {"type": "tasks", "ns": [], "data": data}


def _checkpoint_task_part(**overrides):
    task = {"id": "task-1", "name": "worker", "state": None}
    if "error" in overrides:
        task["error"] = overrides.pop("error")
    else:
        task["result"] = {}
        task["interrupts"] = []
    task.update(overrides)
    return {
        "type": "checkpoints",
        "ns": [],
        "data": {
            "config": None,
            "metadata": {},
            "values": {},
            "next": [],
            "parent_config": None,
            "tasks": [task],
        },
    }


@pytest.mark.parametrize(
    "part",
    [
        {"type": "values", "ns": [], "data": {}, "interrupts": [{}]},
        {"type": "updates", "ns": [], "data": {"__interrupt__": [{}]}},
        _task_result_part(interrupts=[{}]),
        _checkpoint_task_part(interrupts=[{}]),
    ],
    ids=["values", "updates", "task-result", "checkpoint-task"],
)
def test_langgraph_interrupt_records_require_official_id_and_value(part):
    with pytest.raises(LangGraphImportError, match="must contain id and value"):
        langgraph_v2_to_events([part], run_id="invalid-interrupt-record")


@pytest.mark.parametrize(
    "interrupt, message",
    [
        ({"value": "review"}, "must contain id and value"),
        ({"id": "interrupt-1"}, "must contain id and value"),
        ({"id": "", "value": "review"}, "id must be a non-empty string"),
        ({"id": 1, "value": "review"}, "id must be a non-empty string"),
    ],
    ids=["missing-id", "missing-value", "empty-id", "non-string-id"],
)
def test_langgraph_interrupt_id_is_a_required_non_empty_string(interrupt, message):
    part = {"type": "values", "ns": [], "data": {}, "interrupts": [interrupt]}

    with pytest.raises(LangGraphImportError, match=message):
        langgraph_v2_to_events([part], run_id="invalid-interrupt-id")


@pytest.mark.parametrize(
    "part, message",
    [
        (_task_result_part(result=[]), "result must be an object"),
        (_task_result_part(result=None), "result must be an object"),
        (_task_result_part(error={}), "error must be a string or null"),
        (_task_result_part(error=[]), "error must be a string or null"),
        (_checkpoint_task_part(error=None), "error must be a string"),
        (_checkpoint_task_part(error={}), "error must be a string"),
    ],
    ids=[
        "task-result-list",
        "task-result-null",
        "task-error-object",
        "task-error-list",
        "checkpoint-error-null",
        "checkpoint-error-object",
    ],
)
def test_langgraph_task_result_fields_match_official_runtime_types(part, message):
    with pytest.raises(LangGraphImportError, match=message):
        langgraph_v2_to_events([part], run_id="invalid-task-result-type")


def _checkpoint_identity_part(
    checkpoint_id="checkpoint-1",
    *,
    thread_id=None,
    parent_checkpoint_id=None,
    parent_thread_id=None,
    tasks=None,
):
    configurable = {"checkpoint_id": checkpoint_id, "checkpoint_ns": ""}
    if thread_id is not None:
        configurable["thread_id"] = thread_id
    parent_config = None
    if parent_checkpoint_id is not None or parent_thread_id is not None:
        parent = {"checkpoint_ns": ""}
        if parent_checkpoint_id is not None:
            parent["checkpoint_id"] = parent_checkpoint_id
        if parent_thread_id is not None:
            parent["thread_id"] = parent_thread_id
        parent_config = {"configurable": parent}
    return {
        "type": "checkpoints",
        "ns": [],
        "data": {
            "config": {"configurable": configurable},
            "metadata": {},
            "values": {},
            "next": [],
            "parent_config": parent_config,
            "tasks": tasks or [],
        },
    }


def test_langgraph_checkpoint_rejects_duplicate_task_ids_within_one_snapshot():
    part = _checkpoint_identity_part(
        tasks=[
            {"id": "duplicate", "name": "first", "state": None, "error": "one"},
            {"id": "duplicate", "name": "second", "state": None, "error": "two"},
        ]
    )

    with pytest.raises(LangGraphImportError, match="duplicate task id"):
        langgraph_v2_to_events([part], run_id="duplicate-checkpoint-task")


@pytest.mark.parametrize(
    "parts, explicit_thread",
    [
        (
            [
                _checkpoint_identity_part("checkpoint-a", thread_id="thread-a"),
                _checkpoint_identity_part("checkpoint-b", thread_id="thread-b"),
            ],
            None,
        ),
        (
            [
                _checkpoint_identity_part(
                    "checkpoint-b",
                    thread_id="thread-b",
                    parent_checkpoint_id="checkpoint-a",
                    parent_thread_id="thread-a",
                )
            ],
            None,
        ),
        ([_checkpoint_identity_part(thread_id="thread-b")], "thread-a"),
    ],
    ids=["checkpoint-configs", "config-parent", "explicit-checkpoint"],
)
def test_langgraph_rejects_conflicting_thread_identity(parts, explicit_thread):
    with pytest.raises(LangGraphImportError, match="conflicting thread_id"):
        langgraph_v2_to_events(
            parts,
            run_id="thread-conflict",
            thread_id=explicit_thread,
        )


def test_langgraph_envelope_thread_must_match_checkpoint_thread():
    payload = {
        "runId": "envelope-thread-conflict",
        "threadId": "thread-a",
        "parts": [_checkpoint_identity_part(thread_id="thread-b")],
    }

    with pytest.raises(LangGraphImportError, match="conflicting thread_id"):
        langgraph_v2_to_events(payload)


@pytest.mark.parametrize(
    "field, value, message",
    [
        ("configurable", [], "config.configurable must be an object"),
        ("thread_id", 1, "thread_id must be a non-empty string"),
        ("thread_id", "", "thread_id must be a non-empty string"),
        ("checkpoint_id", 1, "checkpoint_id must be a non-empty string"),
        ("checkpoint_id", "", "checkpoint_id must be a non-empty string"),
        ("checkpoint_ns", 1, "checkpoint_ns must be a string"),
    ],
    ids=[
        "configurable-array",
        "thread-non-string",
        "thread-empty",
        "checkpoint-non-string",
        "checkpoint-empty",
        "namespace-non-string",
    ],
)
def test_langgraph_checkpoint_config_present_fields_have_structural_types(field, value, message):
    part = _checkpoint_identity_part()
    if field == "configurable":
        part["data"]["config"]["configurable"] = value
    else:
        part["data"]["config"]["configurable"][field] = value

    with pytest.raises(LangGraphImportError, match=message):
        langgraph_v2_to_events([part], run_id="malformed-checkpoint-config")


def test_langgraph_parent_config_present_fields_have_structural_types():
    part = _checkpoint_identity_part(parent_checkpoint_id="checkpoint-parent")
    part["data"]["parent_config"]["configurable"] = []

    with pytest.raises(LangGraphImportError, match="parent_config.configurable must be an object"):
        langgraph_v2_to_events([part], run_id="malformed-parent-config")


@pytest.mark.parametrize(
    "message",
    [
        {"type": "ai"},
        {"content": "hello"},
        {"type": "ai", "content": {}},
    ],
    ids=["missing-content", "missing-type", "invalid-content"],
)
def test_langgraph_message_requires_official_base_message_shape(message):
    part = {"type": "messages", "ns": [], "data": [message, {}]}

    with pytest.raises(LangGraphImportError, match="messages.message"):
        langgraph_v2_to_events([part], run_id="invalid-message-shape")


@pytest.mark.parametrize(
    "wrapper",
    [
        {
            "timestamp": "2026-07-17T00:00:00Z",
            "type": "task",
            "payload": {"id": "task-1", "name": "worker", "input": {}, "triggers": []},
        },
        {
            "step": 1,
            "type": "task",
            "payload": {"id": "task-1", "name": "worker", "input": {}, "triggers": []},
        },
        {
            "step": True,
            "timestamp": "2026-07-17T00:00:00Z",
            "type": "task",
            "payload": {"id": "task-1", "name": "worker", "input": {}, "triggers": []},
        },
        {
            "step": 1,
            "timestamp": "not-a-timestamp",
            "type": "task",
            "payload": {"id": "task-1", "name": "worker", "input": {}, "triggers": []},
        },
        {
            "step": 1,
            "timestamp": "2026-07-17T00:00:00Z",
            "type": "future-debug",
            "payload": {},
        },
    ],
    ids=["missing-step", "missing-timestamp", "boolean-step", "bad-timestamp", "unknown-type"],
)
def test_langgraph_debug_wrapper_requires_official_discriminated_shape(wrapper):
    part = {"type": "debug", "ns": [], "data": wrapper}

    with pytest.raises(LangGraphImportError, match="debug.data"):
        langgraph_v2_to_events([part], run_id="invalid-debug-wrapper")


def test_langgraph_valid_debug_task_wrapper_reuses_task_shape_validation():
    part = {
        "type": "debug",
        "ns": [],
        "data": {
            "step": 1,
            "timestamp": "2026-07-17T00:00:00Z",
            "type": "task",
            "payload": {"id": "task-1", "name": "worker", "input": {}, "triggers": []},
        },
    }

    events = langgraph_v2_to_events([part], run_id="valid-debug-wrapper")

    assert any(event.event_type == "agent.step.started" for event in events)


@pytest.mark.parametrize(
    "payload, message",
    [
        ("[" * 5_000 + "]" * 5_000, "excessively nested"),
        ('{"type":"custom","ns":[],"data":' + "9" * 5_000 + "}", "invalid numeric value"),
    ],
    ids=["deep-nesting", "huge-integer"],
)
def test_langgraph_ndjson_parser_contains_non_decoder_value_errors(payload, message):
    from anthill.adapters import langgraph_ndjson_to_events

    with pytest.raises(LangGraphImportError, match=message):
        langgraph_ndjson_to_events(payload, run_id="invalid-ndjson-boundary")


def test_langgraph_ndjson_rejects_excessive_nesting_before_decoder_behavior_diverges():
    from anthill.adapters import langgraph_ndjson_to_events

    payload = (
        '{"type":"custom","ns":[],"data":'
        + "[" * 256
        + "0"
        + "]" * 256
        + "}"
    )

    with pytest.raises(LangGraphImportError, match="excessively nested"):
        langgraph_ndjson_to_events(payload, run_id="bounded-ndjson-depth")


def test_langgraph_ndjson_nesting_guard_ignores_brackets_inside_json_strings():
    from anthill.adapters import langgraph_ndjson_to_events

    payload = json.dumps(
        {"type": "custom", "ns": [], "data": "[{}]\\\"" * 512},
        separators=(",", ":"),
    )

    events = langgraph_ndjson_to_events(payload, run_id="string-brackets")

    assert any(event.event_type == "langgraph.custom" for event in events)


@pytest.mark.parametrize("message_type", ["", 1], ids=["empty", "non-string"])
def test_langgraph_message_type_is_a_required_non_empty_string(message_type):
    part = {
        "type": "messages",
        "ns": [],
        "data": [{"type": message_type, "content": "hello"}, {}],
    }

    with pytest.raises(LangGraphImportError, match="messages.message.type"):
        langgraph_v2_to_events([part], run_id="invalid-message-type")


@pytest.mark.parametrize("content", ["", []], ids=["empty-text", "empty-blocks"])
def test_langgraph_message_allows_valid_empty_content(content):
    part = {"type": "messages", "ns": [], "data": [{"type": "ai", "content": content}, {}]}

    events = langgraph_v2_to_events([part], run_id="valid-empty-message-content")

    assert any(event.event_type == "model.response.chunk" for event in events)


def test_langgraph_parent_checkpoint_namespace_must_be_a_string_when_present():
    part = _checkpoint_identity_part(parent_checkpoint_id="checkpoint-parent")
    part["data"]["parent_config"]["configurable"]["checkpoint_ns"] = 1

    with pytest.raises(LangGraphImportError, match="parent_config.*checkpoint_ns must be a string"):
        langgraph_v2_to_events([part], run_id="malformed-parent-namespace")


@pytest.mark.parametrize(
    "task",
    [
        {
            "id": "task-1",
            "name": "worker",
            "state": None,
            "error": "failed",
            "interrupts": [],
        },
        {"id": "task-1", "name": "worker", "state": None, "result": {}},
        {
            "id": "task-1",
            "name": "worker",
            "state": None,
            "error": "failed",
            "result": {},
            "interrupts": [],
        },
    ],
    ids=["error-plus-interrupts", "result-without-interrupts", "error-plus-result"],
)
def test_langgraph_checkpoint_task_matches_one_official_state_shape(task):
    part = _checkpoint_identity_part(tasks=[task])

    with pytest.raises(LangGraphImportError, match="checkpoint task state shape"):
        langgraph_v2_to_events([part], run_id="invalid-checkpoint-task-shape")


@pytest.mark.parametrize(
    "task",
    [
        {"id": "error", "name": "worker", "state": None, "error": "failed"},
        {
            "id": "result",
            "name": "worker",
            "state": None,
            "result": {},
            "interrupts": [],
        },
        {"id": "pending", "name": "worker", "state": None, "interrupts": []},
    ],
    ids=["error", "result", "pending"],
)
def test_langgraph_checkpoint_task_accepts_each_official_state_shape(task):
    part = _checkpoint_identity_part(tasks=[task])

    events = langgraph_v2_to_events([part], run_id=f"valid-checkpoint-task-{task['id']}")

    assert any(event.event_type == "checkpoint.created" for event in events)


def test_langgraph_explicit_run_id_must_match_envelope_run_id():
    payload = {
        "runId": "source-run",
        "parts": [{"type": "custom", "ns": [], "data": {}}],
    }

    with pytest.raises(LangGraphImportError, match="conflicting run_id"):
        langgraph_v2_to_events(payload, run_id="replacement-run")


def test_langgraph_known_non_debug_modes_reject_top_level_timestamp():
    part = {
        "type": "tasks",
        "ns": [],
        "timestamp": "2000-01-01T00:00:00Z",
        "data": {"id": "task-1", "name": "worker", "input": {}, "triggers": []},
    }

    with pytest.raises(LangGraphImportError, match="timestamp is only valid inside debug.data"):
        langgraph_v2_to_events([part], run_id="forged-timeline")


@pytest.mark.parametrize(
    "metadata, field",
    [
        ({"source": "invented"}, "source"),
        ({"step": True}, "step"),
        ({"step": 1.5}, "step"),
        ({"parents": []}, "parents"),
        ({"parents": {"": 1}}, "parents"),
        ({"run_id": 1}, "run_id"),
    ],
    ids=[
        "source",
        "boolean-step",
        "float-step",
        "parents-container",
        "parents-id",
        "run-id",
    ],
)
def test_langgraph_checkpoint_metadata_present_fields_match_official_types(metadata, field):
    part = _checkpoint_identity_part()
    part["data"]["metadata"] = metadata

    with pytest.raises(LangGraphImportError, match=f"metadata.{field}"):
        langgraph_v2_to_events([part], run_id="invalid-checkpoint-metadata")


@pytest.mark.parametrize(
    "usage",
    [
        {"input_tokens": 1, "output_tokens": 2},
        {"input_tokens": 1.5, "output_tokens": 2, "total_tokens": 3},
        {"input_tokens": 1, "output_tokens": -1, "total_tokens": 0},
        {"input_tokens": 1, "output_tokens": 2, "total_tokens": True},
    ],
    ids=["missing-total", "float", "negative", "boolean"],
)
def test_langgraph_usage_metadata_cannot_pollute_token_measurements(usage):
    part = {
        "type": "messages",
        "ns": [],
        "data": [{"type": "ai", "content": "hello", "usage_metadata": usage}, {}],
    }

    with pytest.raises(LangGraphImportError, match="usage_metadata"):
        langgraph_v2_to_events([part], run_id="invalid-token-usage")


def test_langgraph_valid_zero_usage_metadata_remains_measurable():
    usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    part = {
        "type": "messages",
        "ns": [],
        "data": [{"type": "ai", "content": "", "usage_metadata": usage}, {}],
    }

    events = langgraph_v2_to_events([part], run_id="zero-token-usage")
    message = next(event for event in events if event.event_type == "model.response.chunk")

    assert message.measurements == usage


def test_langgraph_values_requires_the_official_interrupts_field():
    part = {"type": "values", "ns": [], "data": {}}

    with pytest.raises(LangGraphImportError, match="values.interrupts is required"):
        langgraph_v2_to_events([part], run_id="missing-values-interrupts")

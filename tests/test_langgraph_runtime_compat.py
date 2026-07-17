from importlib.metadata import PackageNotFoundError, version
from importlib.util import find_spec
from typing import TypedDict

import pytest

from anthill.adapters.langgraph import langgraph_v2_to_events
from anthill.schema import ContentCapture, EvidenceLevel, SourceFidelity


def _installed_langgraph_version() -> str | None:
    if find_spec("langgraph") is None:
        return None
    try:
        return version("langgraph")
    except PackageNotFoundError:
        return None


def _major_minor(raw: str) -> tuple[int, int]:
    major, minor, *_rest = raw.split(".")
    return int(major), int(minor)


def test_real_langgraph_v2_stream_is_accepted_without_content_leakage():
    framework_version = _installed_langgraph_version()
    if framework_version is None:
        pytest.skip("optional LangGraph runtime is not installed")
    if _major_minor(framework_version) < (1, 1):
        pytest.skip("LangGraph <1.1 exposes the unsupported legacy tuple boundary")

    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.config import get_stream_writer
    from langgraph.graph import END, START, StateGraph

    class State(TypedDict):
        prompt: str
        answer: str

    def worker(state: State) -> dict[str, str]:
        get_stream_writer()({"phase": "SECRET_CUSTOM"})
        response = FakeListChatModel(responses=["SECRET_ANSWER"]).invoke(state["prompt"])
        return {"answer": str(response.content)}

    builder = StateGraph(State)
    builder.add_node("worker", worker)
    builder.add_edge(START, "worker")
    builder.add_edge("worker", END)
    graph = builder.compile(checkpointer=InMemorySaver())

    parts = list(
        graph.stream(
            {"prompt": "SECRET_PROMPT", "answer": ""},
            {"configurable": {"thread_id": "compat-thread"}},
            stream_mode=[
                "tasks",
                "messages",
                "custom",
                "updates",
                "values",
                "checkpoints",
            ],
            version="v2",
        )
    )

    assert all(isinstance(part, dict) and {"type", "ns", "data"} <= set(part) for part in parts)
    assert {
        "tasks",
        "messages",
        "custom",
        "updates",
        "values",
        "checkpoints",
    } <= {part["type"] for part in parts}

    events = langgraph_v2_to_events(
        parts,
        run_id="runtime-compat-run",
        framework_version=framework_version,
        stream_complete=True,
    )

    expected_event_types = {
        "tasks": {"agent.step.started", "agent.step.completed"},
        "messages": {"model.response.chunk"},
        "custom": {"langgraph.custom"},
        "updates": {"agent.state.changed"},
        "values": {"context.shared_state.snapshot"},
        "checkpoints": {"checkpoint.created"},
    }
    event_types_by_mode: dict[str, set[str]] = {}
    for event in events:
        mode = event.payload.get("stream_mode")
        if isinstance(mode, str):
            event_types_by_mode.setdefault(mode, set()).add(event.event_type)

    assert set(expected_event_types) <= set(event_types_by_mode)
    assert all(
        expected_types <= event_types_by_mode[mode]
        for mode, expected_types in expected_event_types.items()
    )
    assert all(event.source.fidelity == SourceFidelity.MAPPED for event in events)
    assert all(event.source.framework_version == framework_version for event in events)
    assert all(event.privacy.content == ContentCapture.METADATA_ONLY for event in events)
    assert "SECRET_" not in "\n".join(event.model_dump_json() for event in events)

    completed = next(event for event in events if event.event_type == "run.completed")
    assert completed.evidence.level == EvidenceLevel.DECLARED
    assert completed.payload["status"] == "completed"

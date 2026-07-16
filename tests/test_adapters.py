from collections import Counter

from analyzer.ast_parser import parse_project
from analyzer.graph_builder import build_graph
from analyzer.pattern_detector import detect_patterns
from anthill.adapters import flow_graph_to_events, trace_result_to_events
from anthill.schema import ContentCapture, EvidenceLevel, SourceFidelity
from anthill.store import JsonlEventStore
from tracer.tracer import trace_project_entry


def sample_analysis():
    parsed = parse_project("samples")
    detection = detect_patterns(parsed)
    graph = build_graph(parsed, detection)
    return detection, graph


def test_ast_adapter_separates_declarations_from_inference():
    _, graph = sample_analysis()
    events = flow_graph_to_events(graph, run_id="analysis-run")

    declarations = [
        item for item in events if item.event_type == "code.entity.declared"
    ]
    classifications = [
        item for item in events if item.event_type == "semantic.entity.classified"
    ]

    assert len(declarations) == len(graph.nodes)
    assert len(classifications) == len(graph.nodes)
    assert all(item.evidence.level == EvidenceLevel.DECLARED for item in declarations)
    assert all(item.evidence.confidence == 1.0 for item in declarations)
    assert all(item.evidence.level == EvidenceLevel.INFERRED for item in classifications)
    assert all(item.source.fidelity == SourceFidelity.INFERRED for item in classifications)
    assert all(item.evidence.confidence < 1.0 for item in classifications)


def test_trace_adapter_preserves_observed_facts_and_marks_semantics_inferred():
    detection, _ = sample_analysis()
    result = trace_project_entry("samples", "sample_agent", "main")
    events = trace_result_to_events(
        result,
        run_id="trace-run",
        classifications=detection.classifications,
    )
    counts = Counter(item.event_type for item in events)

    assert events[0].event_type == "run.started"
    assert events[-1].event_type == "run.completed"
    assert counts["code.call.started"] == counts["code.call.returned"]
    assert counts["code.call.started"] > 0

    observed = [item for item in events if item.event_type.startswith("code.call")]
    inferred = [item for item in events if item.source.fidelity == SourceFidelity.INFERRED]
    assert all(item.evidence.level == EvidenceLevel.OBSERVED for item in observed)
    assert all(item.evidence.confidence == 1.0 for item in observed)
    assert inferred
    assert all(item.evidence.level == EvidenceLevel.INFERRED for item in inferred)
    assert all(item.evidence.confidence < 1.0 for item in inferred)


def test_trace_defaults_to_metadata_only_and_does_not_store_values():
    detection, _ = sample_analysis()
    result = trace_project_entry("samples", "sample_agent", "main")
    events = trace_result_to_events(
        result,
        run_id="private-run",
        classifications=detection.classifications,
    )

    assert all(
        item.privacy.content == ContentCapture.METADATA_ONLY for item in events
    )
    serialized = "\n".join(item.model_dump_json() for item in events)
    assert "你们的退货政策是什么" not in serialized
    assert '"arguments"' not in serialized
    assert '"return_value"' not in serialized


def test_adapted_trace_can_be_persisted_and_verified(tmp_path):
    detection, _ = sample_analysis()
    result = trace_project_entry("samples", "sample_agent", "main")
    events = trace_result_to_events(
        result,
        run_id="persisted-run",
        classifications=detection.classifications,
    )
    store = JsonlEventStore(tmp_path)
    stored = store.append_many(events)

    assert len(stored) == len(events)
    assert store.verify_run("persisted-run")["valid"] is True

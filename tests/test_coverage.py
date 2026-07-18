import json
from pathlib import Path

from anthill.adapters import agui_json_to_events
from anthill.coverage import build_instrumentation_visibility
from anthill.demo import build_demo_events
from anthill.measurements import MeasurementSemantics, measurement_semantics_extension
from anthill.projections import project_world
from anthill.schema import (
    AgentRuntimeEvent,
    EventSource,
    Evidence,
    EvidenceLevel,
    SourceFidelity,
)
from anthill.store import JsonlEventStore


AGUI_FIXTURE = Path(__file__).parent / "fixtures" / "agui_events.json"


def test_visibility_separates_observed_from_observable_but_not_seen(tmp_path):
    store = JsonlEventStore(tmp_path)
    events = store.append_many(build_demo_events("coverage-run"))
    state = project_world(events, run_id="coverage-run")

    visibility = build_instrumentation_visibility(state)
    by_domain = {row["domain"]: row for row in visibility["domains"]}

    assert by_domain["tool"]["status"] == "observed"
    assert by_domain["tool"]["event_count"] == 6
    assert by_domain["usage"]["status"] == "observed"
    assert "model_call.input_tokens" in by_domain["usage"]["measurement_keys"]
    assert by_domain["policy"]["status"] == "observable_not_seen"
    assert visibility["unregistered_adapters"] == []
    assert visibility["score"] is None
    assert any("not prove" in warning for warning in visibility["warnings"])


def test_agui_visibility_keeps_protocol_blind_spots_explicit(tmp_path):
    payload = json.loads(AGUI_FIXTURE.read_text(encoding="utf-8"))
    store = JsonlEventStore(tmp_path)
    events = store.append_many(agui_json_to_events(payload))
    state = project_world(events, run_id="agui-run")

    visibility = build_instrumentation_visibility(state)
    by_domain = {row["domain"]: row for row in visibility["domains"]}

    assert by_domain["tool"]["status"] == "observed"
    assert by_domain["context"]["status"] == "observed"
    assert by_domain["model"]["status"] == "outside_adapter_contract"
    assert visibility["adapters"][0]["registered"] is True
    assert any("model" in item for item in visibility["blind_spots"])


def test_unregistered_adapter_is_never_assigned_guessed_capabilities(tmp_path):
    event = AgentRuntimeEvent(
        event_id="third-party-event",
        event_type="vendor.special.signal",
        run_id="third-party-run",
        source=EventSource(adapter="vendor.adapter", fidelity=SourceFidelity.MAPPED),
        evidence=Evidence(level=EvidenceLevel.OBSERVED, confidence=1.0),
    )
    store = JsonlEventStore(tmp_path)
    stored = store.append_many([event])
    state = project_world(stored, run_id="third-party-run")

    visibility = build_instrumentation_visibility(state)
    extension = next(row for row in visibility["domains"] if row["domain"] == "extension")

    assert visibility["unregistered_adapters"] == ["vendor.adapter"]
    assert visibility["adapters"][0]["can_observe"] == []
    assert extension["status"] == "observed"
    assert visibility["extension_families"] == ["vendor"]


def test_raw_measurement_signal_is_visible_without_becoming_a_safe_aggregate(tmp_path):
    event = AgentRuntimeEvent(
        event_id="raw-usage-event",
        event_type="model.response.completed",
        run_id="raw-usage-run",
        source=EventSource(
            adapter="anthill.langgraph-v2", fidelity=SourceFidelity.MAPPED
        ),
        evidence=Evidence(level=EvidenceLevel.OBSERVED, confidence=1.0),
        measurements={"input_tokens": 99},
    )
    store = JsonlEventStore(tmp_path)
    stored = store.append_many([event])
    state = project_world(stored, run_id="raw-usage-run")

    visibility = build_instrumentation_visibility(state)
    usage = next(row for row in visibility["domains"] if row["domain"] == "usage")

    assert usage["status"] == "observed"
    assert usage["measurement_keys"] == []
    assert usage["unaggregated_measurement_keys"] == ["input_tokens"]
    assert visibility["unsafe_measurements"] == [
        {
            "measurement_key": "input_tokens",
            "issue_count": 1,
            "recent_reasons": ["missing or invalid semantics"],
        }
    ]


def test_available_measurement_aggregates_drive_safe_domain_signals(tmp_path):
    run_id = "safe-measurement-domains"
    code_duration = AgentRuntimeEvent(
        event_id="safe-code-duration",
        event_type="telemetry.measurement",
        run_id=run_id,
        source=EventSource(adapter="tests", fidelity=SourceFidelity.NATIVE),
        evidence=Evidence(level=EvidenceLevel.OBSERVED, confidence=1.0),
        measurements={"duration_ms": 4},
        extensions=measurement_semantics_extension(
            {
                "duration_ms": MeasurementSemantics(
                    aggregate_key="code_call.duration_ms",
                    unit="ms",
                    scope="code_call",
                    aggregation="sum",
                    temporality="delta",
                    owner_id="safe-code-duration",
                )
            }
        ),
    )
    store = JsonlEventStore(tmp_path)
    events = store.append_many([*build_demo_events(run_id), code_duration])
    state = project_world(events, run_id=run_id)
    state.event_type_counts = {}
    state.totals = {"input_tokens": 999, "cost_usd": 999}

    visibility = build_instrumentation_visibility(state)
    by_domain = {row["domain"]: row for row in visibility["domains"]}

    assert by_domain["usage"]["measurement_keys"] == [
        "model_call.input_tokens",
        "model_call.output_tokens",
    ]
    assert by_domain["cost"]["measurement_keys"] == ["model_call.cost_usd"]
    assert by_domain["model"]["measurement_keys"] == [
        "model_call.cost_usd",
        "model_call.duration_ms",
        "model_call.input_tokens",
        "model_call.output_tokens",
    ]
    assert by_domain["tool"]["measurement_keys"] == ["tool.duration_ms"]
    assert by_domain["code"]["measurement_keys"] == ["code_call.duration_ms"]
    assert by_domain["compaction"]["measurement_keys"] == [
        "compaction.duration_ms"
    ]
    assert by_domain["run"]["measurement_keys"] == ["run.elapsed_ms"]


def test_ambiguous_measurement_aggregate_is_not_a_safe_domain_signal(tmp_path):
    semantics = measurement_semantics_extension(
        {
            "input_tokens": MeasurementSemantics(
                aggregate_key="model_call.input_tokens",
                unit="tokens",
                scope="model_call",
                aggregation="sum",
                temporality="unknown",
                owner_id="unknown-owner",
            )
        }
    )
    events = [
        AgentRuntimeEvent(
            event_id=f"unknown-temporality-{index}",
            event_type="telemetry.measurement",
            run_id="ambiguous-measurement",
            source=EventSource(adapter="tests", fidelity=SourceFidelity.NATIVE),
            evidence=Evidence(level=EvidenceLevel.OBSERVED, confidence=1.0),
            measurements={"input_tokens": value},
            extensions=semantics,
        )
        for index, value in enumerate((5, 8), start=1)
    ]
    store = JsonlEventStore(tmp_path)
    stored = store.append_many(events)
    state = project_world(stored, run_id="ambiguous-measurement")
    state.event_type_counts = {}
    assert state.measurement_aggregates["model_call.input_tokens"].status == (
        "ambiguous"
    )

    visibility = build_instrumentation_visibility(state)
    by_domain = {row["domain"]: row for row in visibility["domains"]}

    assert by_domain["usage"]["measurement_keys"] == []
    assert by_domain["model"]["measurement_keys"] == []
    assert by_domain["usage"]["status"] == "outside_adapter_contract"
    assert by_domain["model"]["status"] == "outside_adapter_contract"

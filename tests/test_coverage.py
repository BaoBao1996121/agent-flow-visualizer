import json
from pathlib import Path

from anthill.adapters import agui_json_to_events
from anthill.coverage import build_instrumentation_visibility
from anthill.demo import build_demo_events
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
    assert "input_tokens" in by_domain["usage"]["measurement_keys"]
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

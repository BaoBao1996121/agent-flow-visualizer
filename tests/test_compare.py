from copy import deepcopy

from fastapi import FastAPI
from fastapi.testclient import TestClient

from anthill.api import EventBroker, create_anthill_router
from anthill.demo import build_demo_events
from anthill.projections import compare_runs
from anthill.store import JsonlEventStore


def _with_cost_contract(events, *, basis: str, estimated: bool):
    updated = []
    for event in events:
        if "cost_usd" not in event.measurements:
            updated.append(event)
            continue
        extensions = deepcopy(event.extensions)
        semantics = extensions["anthill.measurements"]["items"]["cost_usd"]
        semantics["basis"] = basis
        semantics["estimated"] = estimated
        updated.append(event.model_copy(update={"extensions": extensions}))
    return updated


def _without_measurement(events, measurement_key: str):
    updated = []
    for event in events:
        if measurement_key not in event.measurements:
            updated.append(event)
            continue
        measurements = dict(event.measurements)
        measurements.pop(measurement_key)
        extensions = deepcopy(event.extensions)
        extension = extensions.get("anthill.measurements")
        if extension:
            extension["items"].pop(measurement_key, None)
            if not extension["items"]:
                extensions.pop("anthill.measurements")
        updated.append(
            event.model_copy(
                update={"measurements": measurements, "extensions": extensions}
            )
        )
    return updated


def _with_measurement_value(events, measurement_key: str, value: int | float):
    updated = []
    for event in events:
        if measurement_key not in event.measurements:
            updated.append(event)
            continue
        measurements = dict(event.measurements)
        measurements[measurement_key] = value
        updated.append(event.model_copy(update={"measurements": measurements}))
    return updated


def _with_repeated_unknown_cost(events):
    updated = []
    for event in events:
        if "cost_usd" not in event.measurements:
            updated.append(event)
            continue
        extensions = deepcopy(event.extensions)
        cost_semantics = extensions["anthill.measurements"]["items"]["cost_usd"]
        cost_semantics["temporality"] = "unknown"
        observed = event.model_copy(update={"extensions": extensions})
        updated.append(observed)
        updated.append(
            observed.model_copy(
                update={
                    "event_id": "compare-cost-repeat",
                    "measurements": {"cost_usd": 0.0064},
                    "extensions": {
                        "anthill.measurements": {
                            "schema_version": "1.0.0",
                            "items": {"cost_usd": deepcopy(cost_semantics)},
                        }
                    },
                }
            )
        )
    return updated


def _with_additional_cost_owner(
    events, *, event_id: str, basis: str, estimated: bool = True
):
    updated = []
    for event in events:
        updated.append(event)
        if "cost_usd" not in event.measurements:
            continue
        cost_semantics = deepcopy(
            event.extensions["anthill.measurements"]["items"]["cost_usd"]
        )
        cost_semantics["owner_id"] = f"{cost_semantics['owner_id']}:additional"
        cost_semantics["basis"] = basis
        cost_semantics["estimated"] = estimated
        updated.append(
            event.model_copy(
                update={
                    "event_id": event_id,
                    "measurements": {"cost_usd": 0.001},
                    "extensions": {
                        "anthill.measurements": {
                            "schema_version": "1.0.0",
                            "items": {"cost_usd": cost_semantics},
                        }
                    },
                }
            )
        )
    return updated


def _with_explicit_total(events, total_tokens: int):
    updated = []
    for event in events:
        if "output_tokens" not in event.measurements:
            updated.append(event)
            continue
        measurements = dict(event.measurements)
        measurements["total_tokens"] = total_tokens
        extensions = deepcopy(event.extensions)
        output_semantics = extensions["anthill.measurements"]["items"][
            "output_tokens"
        ]
        extensions["anthill.measurements"]["items"]["total_tokens"] = {
            **deepcopy(output_semantics),
            "aggregate_key": "model_call.total_tokens",
        }
        updated.append(
            event.model_copy(
                update={"measurements": measurements, "extensions": extensions}
            )
        )
    return updated


def test_compare_runs_highlights_mechanism_and_metric_differences(tmp_path):
    store = JsonlEventStore(tmp_path)
    store.append_many(build_demo_events("left-run"))
    right = [
        event
        for event in build_demo_events("right-run")
        if not event.event_type.startswith(("memory.", "compaction."))
    ]
    store.append_many(right)

    result = compare_runs(
        store.read_run("left-run"),
        store.read_run("right-run"),
        left_run_id="left-run",
        right_run_id="right-run",
    )

    assert result["comparability"]["controlled"] is True
    assert result["comparability"]["shared_project_ids"] == ["anthill-demo"]
    assert result["comparability"]["shared_task_ids"] == ["task.incident-42"]
    assert result["left"]["summary"]["mechanisms"]["memory"] is True
    assert result["right"]["summary"]["mechanisms"]["memory"] is None
    assert result["left"]["summary"]["metrics"]["compactions"] == 1
    assert result["right"]["summary"]["metrics"]["compactions"] is None
    assert any(
        item["event_type"] == "compaction.completed" and item["delta"] == -1
        for item in result["event_type_differences"]
    )


def test_compare_reports_unobserved_context_quantities_as_availability(tmp_path):
    store = JsonlEventStore(tmp_path)
    store.append_many(
        [
            event
            for event in build_demo_events("left-run")
            if not event.event_type.startswith("context.")
        ]
    )
    store.append_many(build_demo_events("right-run"))

    result = compare_runs(
        store.read_run("left-run"),
        store.read_run("right-run"),
        left_run_id="left-run",
        right_run_id="right-run",
    )
    left_metrics = result["left"]["summary"]["metrics"]

    assert left_metrics["context_used_tokens"] is None
    assert left_metrics["context_budget_tokens"] is None
    for metric in ("context_used_tokens", "context_budget_tokens"):
        difference = next(
            item
            for item in result["metric_differences"]
            if item["metric"] == metric
        )
        assert difference["comparison"] == "availability"
        assert difference["left"] is None
        assert isinstance(difference["right"], int)


def test_compare_reports_unobserved_compaction_reduction_as_availability(tmp_path):
    store = JsonlEventStore(tmp_path)
    left_events = []
    for event in build_demo_events("left-run"):
        if not event.event_type.startswith("compaction."):
            left_events.append(event)
            continue
        payload = dict(event.payload)
        payload.pop("tokens_before", None)
        payload.pop("tokens_after", None)
        left_events.append(event.model_copy(update={"payload": payload}))
    store.append_many(left_events)
    store.append_many(build_demo_events("right-run"))

    result = compare_runs(
        store.read_run("left-run"),
        store.read_run("right-run"),
        left_run_id="left-run",
        right_run_id="right-run",
    )
    left_metrics = result["left"]["summary"]["metrics"]
    difference = next(
        item
        for item in result["metric_differences"]
        if item["metric"] == "compaction_tokens_removed"
    )

    assert left_metrics["compactions"] == 1
    assert left_metrics["compaction_tokens_removed"] is None
    assert difference["comparison"] == "availability"
    assert difference["left"] is None
    assert difference["right"] == 4540


def test_compare_keeps_missing_operational_signals_unobserved(tmp_path):
    store = JsonlEventStore(tmp_path)
    store.append_many([build_demo_events("left-run")[0]])
    store.append_many(build_demo_events("right-run"))

    result = compare_runs(
        store.read_run("left-run"),
        store.read_run("right-run"),
        left_run_id="left-run",
        right_run_id="right-run",
    )
    left_summary = result["left"]["summary"]
    right_summary = result["right"]["summary"]

    for metric in (
        "agents",
        "open_errors",
        "error_events",
        "memory_hits",
        "memory_misses",
        "memory_writes",
        "memory_evictions",
        "compactions",
        "compaction_tokens_removed",
        "handoffs",
        "checkpoints",
        "tool_calls",
    ):
        assert left_summary["metrics"][metric] is None
    assert right_summary["metrics"]["open_errors"] == 0
    assert right_summary["metrics"]["error_events"] == 2
    assert all(value is None for value in left_summary["mechanisms"].values())
    assert all(value is True for value in right_summary["mechanisms"].values())


def test_compare_names_model_requests_completions_and_chunks_separately(tmp_path):
    store = JsonlEventStore(tmp_path)
    left_events = build_demo_events("left-run")
    first_chunk = next(
        event for event in left_events if event.event_type == "model.response.first_chunk"
    )
    completed_index = next(
        index
        for index, event in enumerate(left_events)
        if event.event_type == "model.response.completed"
    )
    left_events.insert(
        completed_index,
        first_chunk.model_copy(
            update={
                "event_id": "compare-model-chunk",
                "event_type": "model.response.chunk",
            }
        ),
    )
    store.append_many(left_events)
    store.append_many(build_demo_events("right-run"))

    result = compare_runs(
        store.read_run("left-run"),
        store.read_run("right-run"),
        left_run_id="left-run",
        right_run_id="right-run",
    )
    metrics = result["left"]["summary"]["metrics"]
    right_metrics = result["right"]["summary"]["metrics"]

    assert metrics["model_requests_dispatched"] == 1
    assert metrics["model_calls_completed"] == 1
    assert metrics["model_response_first_chunk_events"] == 1
    assert metrics["model_response_chunk_events"] == 1
    assert metrics["model_calls_failed"] is None
    assert right_metrics["model_response_chunk_events"] is None
    assert "model_calls" not in metrics
    assert any(
        item["metric"] == "model_response_chunk_events"
        and item["comparison"] == "availability"
        and item["left"] == 1
        and item["right"] is None
        for item in result["metric_differences"]
    )


def test_compare_comparability_uses_only_evidence_visible_at_each_cursor(tmp_path):
    store = JsonlEventStore(tmp_path)
    for run_id in ("left-run", "right-run"):
        events = build_demo_events(run_id)
        events[0] = events[0].model_copy(
            update={"project_id": None, "task_id": None}
        )
        store.append_many(events)

    start = compare_runs(
        store.read_run("left-run"),
        store.read_run("right-run"),
        left_run_id="left-run",
        right_run_id="right-run",
        progress=0,
    )
    head = compare_runs(
        store.read_run("left-run"),
        store.read_run("right-run"),
        left_run_id="left-run",
        right_run_id="right-run",
        progress=1,
    )

    assert start["comparability"]["shared_project_ids"] == []
    assert start["comparability"]["shared_task_ids"] == []
    assert start["comparability"]["controlled"] is False
    assert head["comparability"]["shared_project_ids"] == ["anthill-demo"]
    assert head["comparability"]["shared_task_ids"] == ["task.incident-42"]
    assert head["comparability"]["controlled"] is True


def test_compare_rejects_costs_with_different_pricing_basis(tmp_path):
    store = JsonlEventStore(tmp_path)
    store.append_many(build_demo_events("left-run"))
    store.append_many(
        _with_cost_contract(
            build_demo_events("right-run"),
            basis="synthetic-fixture:alternate-pricing-v2",
            estimated=True,
        )
    )

    result = compare_runs(
        store.read_run("left-run"),
        store.read_run("right-run"),
        left_run_id="left-run",
        right_run_id="right-run",
    )
    difference = next(
        item
        for item in result["measurement_differences"]
        if item["measurement"] == "model_call.cost_usd"
    )

    assert difference["comparison"] == "not_comparable"
    assert difference["delta"] is None
    assert difference["ratio"] is None
    assert difference["reason"] == "cost basis differs"
    assert difference["left_contract"]["basis"] == (
        "synthetic-fixture:demo-pricing-v1"
    )
    assert difference["right_contract"]["basis"] == (
        "synthetic-fixture:alternate-pricing-v2"
    )


def test_compare_rejects_estimated_cost_against_observed_cost(tmp_path):
    store = JsonlEventStore(tmp_path)
    store.append_many(build_demo_events("left-run"))
    store.append_many(
        _with_cost_contract(
            build_demo_events("right-run"),
            basis="synthetic-fixture:demo-pricing-v1",
            estimated=False,
        )
    )

    result = compare_runs(
        store.read_run("left-run"),
        store.read_run("right-run"),
        left_run_id="left-run",
        right_run_id="right-run",
    )
    difference = next(
        item
        for item in result["measurement_differences"]
        if item["measurement"] == "model_call.cost_usd"
    )

    assert difference["comparison"] == "not_comparable"
    assert difference["reason"] == "cost estimate status differs"
    assert difference["left_contract"]["estimated"] is True
    assert difference["right_contract"]["estimated"] is False


def test_compare_reports_measurement_missing_on_one_side_as_availability(tmp_path):
    store = JsonlEventStore(tmp_path)
    store.append_many(build_demo_events("left-run"))
    store.append_many(
        _without_measurement(build_demo_events("right-run"), "cost_usd")
    )

    result = compare_runs(
        store.read_run("left-run"),
        store.read_run("right-run"),
        left_run_id="left-run",
        right_run_id="right-run",
    )
    difference = next(
        item
        for item in result["measurement_differences"]
        if item["measurement"] == "model_call.cost_usd"
    )

    assert "cost_usd" not in result["left"]["summary"]["metrics"]
    assert difference["comparison"] == "availability"
    assert difference["left"] == 0.0062
    assert difference["right"] is None
    assert difference["left_status"] == "available"
    assert difference["right_status"] == "missing"
    assert difference["delta"] is None
    assert difference["reason"] == "measurement missing on right"


def test_compare_marks_ambiguous_measurement_not_comparable(tmp_path):
    store = JsonlEventStore(tmp_path)
    store.append_many(build_demo_events("left-run"))
    store.append_many(_with_repeated_unknown_cost(build_demo_events("right-run")))

    result = compare_runs(
        store.read_run("left-run"),
        store.read_run("right-run"),
        left_run_id="left-run",
        right_run_id="right-run",
    )
    difference = next(
        item
        for item in result["measurement_differences"]
        if item["measurement"] == "model_call.cost_usd"
    )

    assert difference["comparison"] == "not_comparable"
    assert difference["left"] == 0.0062
    assert difference["right"] is None
    assert difference["left_status"] == "available"
    assert difference["right_status"] == "ambiguous"
    assert difference["reason"] == "right measurement is ambiguous"
    assert difference["delta"] is None
    assert result["right"]["summary"]["measurements"][
        "model_call.cost_usd"
    ]["status"] == "ambiguous"


def test_compare_keeps_calculated_total_separate_with_components(tmp_path):
    store = JsonlEventStore(tmp_path)
    store.append_many(build_demo_events("left-run"))
    store.append_many(build_demo_events("right-run"))

    result = compare_runs(
        store.read_run("left-run"),
        store.read_run("right-run"),
        left_run_id="left-run",
        right_run_id="right-run",
    )
    calculated = result["left"]["summary"]["calculated_measurements"][
        "model_call.total_tokens"
    ]
    difference = next(
        item
        for item in result["measurement_differences"]
        if item["measurement"] == "model_call.total_tokens"
        and item["origin"] == "calculated"
    )

    assert calculated["value"] == 2100
    assert calculated["aggregation"] == "derived"
    assert calculated["calculation"] == (
        "model_call.input_tokens + model_call.output_tokens"
    )
    assert calculated["components"] == {
        "model_call.input_tokens": 1680,
        "model_call.output_tokens": 420,
    }
    assert difference["comparison"] == "numeric"
    assert difference["left"] == 2100
    assert difference["right"] == 2100
    assert difference["left_contract"]["aggregation"] == "derived"
    assert difference["left_components"] == calculated["components"]


def test_compare_does_not_emit_non_finite_measurement_ratio(tmp_path):
    store = JsonlEventStore(tmp_path)
    store.append_many(
        _with_measurement_value(
            build_demo_events("left-run"), "input_tokens", 5e-324
        )
    )
    store.append_many(
        _with_measurement_value(
            build_demo_events("right-run"), "input_tokens", 1e308
        )
    )

    result = compare_runs(
        store.read_run("left-run"),
        store.read_run("right-run"),
        left_run_id="left-run",
        right_run_id="right-run",
    )
    difference = next(
        item
        for item in result["measurement_differences"]
        if item["measurement"] == "model_call.input_tokens"
    )

    assert difference["comparison"] == "numeric"
    assert difference["ratio"] is None


def test_compare_rejects_cost_with_multiple_internal_pricing_bases(tmp_path):
    store = JsonlEventStore(tmp_path)
    store.append_many(
        _with_additional_cost_owner(
            build_demo_events("left-run"),
            event_id="left-additional-cost",
            basis="synthetic-fixture:alternate-pricing-v2",
        )
    )
    store.append_many(
        _with_additional_cost_owner(
            build_demo_events("right-run"),
            event_id="right-additional-cost",
            basis="synthetic-fixture:alternate-pricing-v2",
        )
    )

    result = compare_runs(
        store.read_run("left-run"),
        store.read_run("right-run"),
        left_run_id="left-run",
        right_run_id="right-run",
    )
    difference = next(
        item
        for item in result["measurement_differences"]
        if item["measurement"] == "model_call.cost_usd"
    )

    assert difference["comparison"] == "not_comparable"
    assert difference["reason"] == (
        "cost basis is not singular and complete on left and right"
    )
    assert difference["left_contract"]["basis_values"] == [
        "synthetic-fixture:alternate-pricing-v2",
        "synthetic-fixture:demo-pricing-v1",
    ]


def test_compare_rejects_cost_with_mixed_internal_estimate_status(tmp_path):
    store = JsonlEventStore(tmp_path)
    store.append_many(
        _with_additional_cost_owner(
            build_demo_events("left-run"),
            event_id="left-observed-cost",
            basis="synthetic-fixture:demo-pricing-v1",
            estimated=False,
        )
    )
    store.append_many(
        _with_additional_cost_owner(
            build_demo_events("right-run"),
            event_id="right-observed-cost",
            basis="synthetic-fixture:demo-pricing-v1",
            estimated=False,
        )
    )

    result = compare_runs(
        store.read_run("left-run"),
        store.read_run("right-run"),
        left_run_id="left-run",
        right_run_id="right-run",
    )
    difference = next(
        item
        for item in result["measurement_differences"]
        if item["measurement"] == "model_call.cost_usd"
    )

    assert difference["comparison"] == "not_comparable"
    assert difference["reason"] == (
        "cost estimate status is not singular and complete on left and right"
    )
    assert difference["left_contract"]["estimated_values"] == [False, True]


def test_compare_does_not_treat_conflicting_calculated_total_as_observed(tmp_path):
    store = JsonlEventStore(tmp_path)
    store.append_many(build_demo_events("left-run"))
    store.append_many(
        _with_explicit_total(build_demo_events("right-run"), total_tokens=9999)
    )

    result = compare_runs(
        store.read_run("left-run"),
        store.read_run("right-run"),
        left_run_id="left-run",
        right_run_id="right-run",
    )
    calculated_difference = next(
        item
        for item in result["measurement_differences"]
        if item["measurement"] == "model_call.total_tokens"
        and item["origin"] == "calculated"
    )
    explicit_difference = next(
        item
        for item in result["measurement_differences"]
        if item["measurement"] == "model_call.total_tokens"
        and item["origin"] == "aggregate"
    )
    right_calculated = result["right"]["summary"]["calculated_measurements"][
        "model_call.total_tokens"
    ]

    assert calculated_difference["comparison"] == "not_comparable"
    assert calculated_difference["right"] is None
    assert calculated_difference["reason"] == "right measurement is ambiguous"
    assert explicit_difference["comparison"] == "availability"
    assert explicit_difference["left_status"] == "missing"
    assert explicit_difference["right"] == 9999
    assert right_calculated["explicit_consistency"] == "conflict"
    assert len(right_calculated["conflict_reasons"]) == 1
    assert "does not match calculated" in right_calculated["conflict_reasons"][0]


def test_compare_api_synchronizes_by_normalized_progress(tmp_path):
    app = FastAPI()
    app.include_router(
        create_anthill_router(JsonlEventStore(tmp_path), EventBroker())
    )
    client = TestClient(app)
    left = client.post("/api/anthill/demo").json()["run_id"]
    right = client.post("/api/anthill/demo").json()["run_id"]

    response = client.get(
        "/api/anthill/compare",
        params={
            "left_run_id": left,
            "right_run_id": right,
            "progress": 0.5,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["progress"] == 0.5
    assert body["cursor"]["left_seq"] == body["cursor"]["right_seq"]
    assert body["left"]["summary"]["metrics"] == body["right"]["summary"]["metrics"]
    assert body["event_type_differences"] == []
    assert body["comparability"]["controlled"] is True

    assert client.get(
        "/api/anthill/compare",
        params={"left_run_id": left, "right_run_id": left},
    ).status_code == 422

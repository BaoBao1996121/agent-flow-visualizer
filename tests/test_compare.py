from fastapi import FastAPI
from fastapi.testclient import TestClient

from anthill.api import EventBroker, create_anthill_router
from anthill.demo import build_demo_events
from anthill.projections import compare_runs
from anthill.store import JsonlEventStore


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
    assert result["right"]["summary"]["mechanisms"]["memory"] is False
    assert result["left"]["summary"]["metrics"]["compactions"] == 1
    assert result["right"]["summary"]["metrics"]["compactions"] == 0
    assert any(
        item["event_type"] == "compaction.completed" and item["delta"] == -1
        for item in result["event_type_differences"]
    )


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

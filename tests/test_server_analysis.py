from fastapi.testclient import TestClient

import server
from anthill.store import JsonlEventStore


def test_cached_analysis_still_honors_a_later_persist_request(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "agent.py").write_text(
        "def helper():\n    return 1\n\ndef entry():\n    return helper()\n",
        encoding="utf-8",
    )
    ledger = JsonlEventStore(tmp_path / "ledger")
    monkeypatch.setattr(server, "event_store", ledger)
    server._analysis_cache.clear()
    client = TestClient(server.app)

    first = client.post("/api/analyze", json={"project_dir": str(project)})
    second = client.post(
        "/api/analyze",
        json={
            "project_dir": str(project),
            "persist_events": True,
            "run_id": "cached-analysis-run",
        },
    )

    assert first.status_code == 200
    assert "anthill" not in first.json()
    assert second.status_code == 200
    assert second.json()["anthill"]["run_id"] == "cached-analysis-run"
    assert list(ledger.read_run("cached-analysis-run"))


def test_cached_analysis_never_leaks_prior_persistence_metadata(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "agent.py").write_text("def entry():\n    return 1\n", encoding="utf-8")
    ledger = JsonlEventStore(tmp_path / "ledger")
    monkeypatch.setattr(server, "event_store", ledger)
    server._analysis_cache.clear()
    client = TestClient(server.app)

    persisted = client.post(
        "/api/analyze",
        json={
            "project_dir": str(project),
            "persist_events": True,
            "run_id": "first-run",
        },
    )
    cached_read = client.post("/api/analyze", json={"project_dir": str(project)})

    assert persisted.status_code == 200
    assert persisted.json()["anthill"]["run_id"] == "first-run"
    assert cached_read.status_code == 200
    assert "anthill" not in cached_read.json()

from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_anthill_frontend_exposes_langgraph_v2_json_and_ndjson_import():
    html = (ROOT / "static" / "anthill.html").read_text(encoding="utf-8")
    javascript = (ROOT / "static" / "js" / "anthill.js").read_text(encoding="utf-8")

    assert 'id="langgraph-button"' in html
    assert 'id="langgraph-file"' in html
    assert 'id="empty-langgraph-button"' in html
    assert "importLangGraphFile" in javascript
    assert "`${API}/import/langgraph`" in javascript
    assert "stream_complete: false" in javascript
    assert "run_id: runId" in javascript

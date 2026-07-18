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


def test_phase0_cutaway_lab_is_isolated_and_has_no_remote_asset_dependency():
    html = (ROOT / "static" / "labs" / "phase0-cutaway.html").read_text(encoding="utf-8")
    css = (ROOT / "static" / "css" / "labs" / "phase0-cutaway.css").read_text(
        encoding="utf-8"
    )
    modules = [
        (ROOT / "static" / "js" / "labs" / "phase0" / name).read_text(encoding="utf-8")
        for name in ("bootstrap.mjs", "study-scene.mjs", "cutaway-svg.mjs")
    ]
    combined = "\n".join([html, css, *modules])

    assert 'data-testid="study-disclaimer"' in html
    assert "EXPLORATION" in html
    assert "NOT PRODUCTION" in html
    assert 'type="module"' in html
    assert "/static/js/anthill.js" not in html
    assert "http://" not in combined
    assert "https://" not in combined
    assert "innerHTML" not in "\n".join(modules)

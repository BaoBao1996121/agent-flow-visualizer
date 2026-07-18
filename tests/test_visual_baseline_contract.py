from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMAGE = (
    "mcr.microsoft.com/playwright:v1.61.1-noble-amd64@"
    "sha256:cf0daee9b994042e011bc29f20cdff1a9f682a039b43fcd738f7d8a9d3bcd9d6"
)


def test_visual_baseline_has_an_isolated_deterministic_playwright_contract():
    config = (ROOT / "playwright.visual.config.mjs").read_text(encoding="utf-8")
    spec = (ROOT / "tests/visual/anthill.visual.spec.mjs").read_text(encoding="utf-8")

    for required in (
        "tests/visual",
        "width: 1600",
        "height: 1000",
        "deviceScaleFactor: 1",
        "locale: 'en-US'",
        "timezoneId: 'UTC'",
        "colorScheme: 'dark'",
        "reducedMotion: 'reduce'",
        "ANTHILL_UPDATE_VISUALS",
        "process.argv",
        IMAGE,
    ):
        assert required in config

    for scene in ("overview.png", "evidence.png", "coverage.png", "compare.png"):
        assert scene in spec
    assert "visual_rich_v1.json" in spec
    assert "document.fonts.ready" in spec
    assert "?static=1" in spec


def test_visual_candidate_job_is_pinned_and_cannot_block_browser_contracts():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "visual-baseline-canary:" in workflow
    assert "continue-on-error: true" in workflow
    assert f'image: "{IMAGE}"' in workflow
    assert "options: --ipc=host --init" in workflow
    assert 'ANTHILL_UPDATE_VISUALS: "1"' in workflow
    assert "npm run test:visual" in workflow
    assert "visual-baseline-candidate" in workflow


def test_visual_candidate_job_requires_all_four_non_empty_pngs():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "Verify all visual candidates exist" in workflow
    for scene in ("overview.png", "evidence.png", "coverage.png", "compare.png"):
        assert f"test -s tests/visual/goldens/chromium-noble/{scene}" in workflow


def test_visual_candidate_uses_an_exact_python_runtime_lock():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    requirements = (ROOT / "requirements-visual.txt").read_text(encoding="utf-8")
    visual_job = workflow.split("  visual-baseline-canary:\n", 1)[1].split(
        "\n  container:\n", 1
    )[0]

    assert "python -m pip install -r requirements-visual.txt" in visual_job
    assert "cache: pip" not in visual_job
    assert "cache-dependency-path: requirements-visual.txt" not in visual_job
    assert 'python-version: "3.12.13"' in visual_job
    for requirement in (
        "fastapi==0.136.0",
        "pydantic==2.12.5",
        "starlette==0.50.0",
        "uvicorn==0.38.0",
    ):
        assert requirement in requirements.splitlines()
    assert all(
        not line or line.startswith("#") or "==" in line
        for line in requirements.splitlines()
    )


def test_visual_harness_stabilizes_synthetic_manifest_time_before_navigation():
    spec = (ROOT / "tests/visual/anthill.visual.spec.mjs").read_text(encoding="utf-8")

    install_call = "await installVisualResponseNormalization(page);"
    first_navigation = "await page.goto('/anthill?static=1');"
    assert "run?.synthetic === true" in spec
    assert "created_at: VISUAL_INGEST_AT" in spec
    assert "updated_at: VISUAL_INGEST_AT" in spec
    assert "last_event_hash:" in spec
    assert "localeCompare" in spec
    assert install_call in spec
    assert spec.index(install_call) < spec.index(first_navigation)


def test_visual_harness_stabilizes_synthetic_event_integrity_for_display():
    spec = (ROOT / "tests/visual/anthill.visual.spec.mjs").read_text(encoding="utf-8")

    for required in (
        "event?.payload?.synthetic === true",
        "TEST-HARNESS:visual-integrity",
        "sha256-test-harness-display",
        "previous_event_hash",
        "event_hash",
        "observed_at: VISUAL_INGEST_AT",
        "pathname.endsWith('/events')",
        "pathname.endsWith('/event')",
    ):
        assert required in spec

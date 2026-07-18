import re
import shlex
from pathlib import Path

import yaml


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _expression(value: str) -> str:
    inner = value.removeprefix("${{").removesuffix("}}")
    return re.sub(r"\s+", "", inner)


def _shell_commands(script: str) -> list[list[str]]:
    logical = script.replace("\\\n", " ")
    return [shlex.split(line) for line in logical.splitlines() if line.strip()]


def test_exploration_fast_gate_provides_a_bounded_vertical_signal():
    document = _workflow()
    triggers = document["on"] if "on" in document else document[True]
    fast_gate = document["jobs"]["exploration-fast"]
    pytest_step = next(
        step
        for step in fast_gate["steps"]
        if step.get("name") == "Check Python and staged-validation contracts"
    )
    node_step = next(
        step for step in fast_gate["steps"] if step.get("name") == "Check primary frontend modules"
    )
    pytest_commands = _shell_commands(pytest_step["run"])
    node_commands = _shell_commands(node_step["run"])
    actions = {step.get("uses") for step in fast_gate["steps"]}
    activities = {
        "opened",
        "synchronize",
        "reopened",
        "ready_for_review",
        "converted_to_draft",
    }

    assert "workflow_dispatch" in triggers
    assert activities <= set(triggers["pull_request"]["types"])
    assert fast_gate["name"] == "Exploration fast gate"
    assert fast_gate["timeout-minutes"] == 5
    assert "continue-on-error" not in fast_gate
    assert "actions/setup-python@v6" in actions
    assert "actions/setup-node@v6" in actions
    install_step = next(
        step
        for step in fast_gate["steps"]
        if step.get("name") == "Install focused validation dependencies"
    )
    assert _shell_commands(install_step["run"]) == [
        ["python", "-m", "pip", "install", "-r", "requirements-dev.txt"]
    ]
    expected_tests = [
        "tests/test_version_contract.py",
        "tests/test_frontend_contract.py",
        "tests/test_visual_fixtures.py",
        "tests/test_visual_baseline_contract.py",
        "tests/test_ci_staging_contract.py",
        "tests/test_validation_runner.py",
        "tests/test_validation_cli.py",
        "tests/test_documentation_contract.py",
    ]
    assert pytest_commands == [
        ["ruff", "check", "--no-cache", "."],
        ["python", "-m", "pytest", "-q", *expected_tests],
    ]
    assert node_commands == [
        ["node", "--check", "static/js/anthill.js"],
        ["node", "--check", "static/js/app.js"],
        ["node", "--check", "static/js/graph.js"],
        ["node", "--check", "static/js/simulation.js"],
    ]


def test_main_trigger_and_protected_context_identities_are_frozen():
    document = _workflow()
    triggers = document["on"] if "on" in document else document[True]
    jobs = document["jobs"]

    assert triggers["push"]["branches"] == ["main"]
    assert jobs["python"].get("name") is None
    assert jobs["python"]["strategy"]["matrix"]["python-version"] == [
        "3.11",
        "3.12",
        "3.13",
    ]
    assert jobs["langgraph-compat"]["name"] == ("LangGraph StreamPart v2 (${{ matrix.label }})")
    assert [
        entry["label"] for entry in jobs["langgraph-compat"]["strategy"]["matrix"]["include"]
    ] == [
        "1.1.0 floor",
        "supported 1.x",
    ]
    assert jobs["frontend"].get("name") is None
    assert jobs["browser"]["name"] == "Chromium observatory contract"
    assert jobs["container"].get("name") is None
    assert jobs["visual-regression"]["name"] == "Pinned Chromium visual regression"
    assert jobs["exploration-fast"]["name"] == "Exploration fast gate"
    assert jobs["protected-main-gate"]["name"] == "Protected main validation gate"


def test_protected_main_gate_rejects_drafts_and_requires_every_stage():
    jobs = _workflow()["jobs"]
    protected_gate = jobs["protected-main-gate"]
    draft_step = next(s for s in protected_gate["steps"] if "exit 1" in s.get("run", ""))
    result_step = next(s for s in protected_gate["steps"] if "NEEDS_JSON" in s.get("env", {}))

    assert protected_gate["name"] == "Protected main validation gate"
    assert (
        sum(
            job.get("name", job_id) == "Protected main validation gate"
            for job_id, job in jobs.items()
        )
        == 1
    )
    assert _expression(protected_gate["if"]) == "always()"
    assert set(protected_gate["needs"]) == {
        "exploration-fast",
        "python",
        "langgraph-compat",
        "frontend",
        "browser",
        "visual-regression",
        "container",
    }
    assert "continue-on-error" not in protected_gate
    assert _expression(draft_step["if"]) == (
        "github.event_name=='pull_request'&&github.event.pull_request.draft"
    )
    assert "continue-on-error" not in draft_step
    assert "|| true" not in draft_step["run"]
    assert _expression(result_step["env"]["NEEDS_JSON"]) == "toJSON(needs)"
    assert "if" not in result_step
    assert "continue-on-error" not in result_step
    assert "jq -e" in result_step["run"]
    assert "length == 7" in result_step["run"]
    assert 'all(.[]; .result == "success")' in result_step["run"]
    assert "|| true" not in result_step["run"]

    for full_job in (
        "python",
        "langgraph-compat",
        "frontend",
        "browser",
        "visual-regression",
        "container",
    ):
        assert _expression(jobs[full_job]["if"]) == (
            "github.event_name!='pull_request'||!github.event.pull_request.draft"
        )

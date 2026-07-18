from __future__ import annotations

import io
import json
from pathlib import Path
from subprocess import run
import sys

import pytest

import validation.__main__ as cli
from validation.runner import build_plan, load_policy


ROOT = Path(__file__).parents[1]
POLICY = ROOT / "validation" / "impact-map.v1.json"
POLICY_SHA256 = load_policy(POLICY)["_impact_map_sha256"]


def _invoke(*arguments: str) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = cli.main(list(arguments), repo=ROOT, stdout=stdout, stderr=stderr)
    return code, stdout.getvalue(), stderr.getvalue()


def test_explicit_plan_is_stable_json_and_does_not_require_a_resolvable_base():
    arguments = (
        "plan",
        "--base-ref",
        "definitely-missing",
        "--path",
        "anthill/adapters/langgraph.py",
    )

    first = _invoke(*arguments)
    second = _invoke(*arguments)

    assert first == second
    assert first[0] == 0
    assert first[2] == ""
    payload = json.loads(first[1])
    assert payload["change_source"] == "explicit"
    assert payload["required_stage"] == "S1"
    assert first[1] == json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def test_unknown_explicit_path_is_inconclusive_and_cannot_be_a_command():
    code, stdout, stderr = _invoke(
        "plan",
        "--base-ref",
        "unused",
        "--path",
        "odd ; $().bin",
    )

    payload = json.loads(stdout)
    assert code == 2
    assert stderr == ""
    assert payload["unknown_paths"] == ["odd ; $().bin"]
    assert payload["required_stage"] == "S2"
    assert "odd ; $().bin" not in json.dumps(payload["checks"])


def test_automatic_plan_uses_the_union_discovery_result(monkeypatch):
    discovery = {
        "base_ref": "origin/main",
        "base_sha": "1" * 40,
        "head_sha": "2" * 40,
        "merge_base_sha": "1" * 40,
        "changes": [
            {
                "path": "anthill/schema.py",
                "statuses": ["M"],
                "sources": ["unstaged"],
            }
        ],
        "skip_worktree_paths": [],
        "assume_unchanged_paths": [],
        "workspace_visibility": "complete",
        "complete_change_detection": True,
        "input_sha256": "3" * 64,
        "base_policy_sha256": POLICY_SHA256,
        "worktree_policy_sha256": POLICY_SHA256,
        "protected_base_policy_match": True,
    }
    monkeypatch.setattr(cli, "discover_git_changes", lambda repo, base_ref: discovery)

    code, stdout, stderr = _invoke("plan", "--base-ref", "origin/main")

    payload = json.loads(stdout)
    assert code == 0
    assert stderr == ""
    assert payload["change_source"] == "git"
    assert payload["changed_paths"] == ["anthill/schema.py"]
    assert payload["input_context"]["changes"] == discovery["changes"]


def test_run_writes_exactly_the_report_it_prints(monkeypatch, tmp_path):
    report_path = tmp_path / "reports" / "s0.json"

    def fake_execute(plan, repo, previous_report=None, run_command=None):
        assert repo == ROOT
        assert previous_report is None
        assert run_command is cli._run_quietly
        return {
            "schema_version": "anthill.validation-run/1.0.0",
            "plan": plan,
            "attempts": [],
            "current_run_attempt": 1,
            "deferred_checks": [],
            "feedback_conclusion": "passed",
            "promotion_eligible": False,
        }

    monkeypatch.setattr(cli, "execute_plan", fake_execute)

    code, stdout, stderr = _invoke(
        "run",
        "--base-ref",
        "unused",
        "--path",
        "anthill/schema.py",
        "--report",
        str(report_path),
    )

    assert code == 0
    assert stderr == ""
    assert json.loads(report_path.read_text(encoding="utf-8")) == json.loads(stdout)


def test_run_rejects_a_repository_report_that_would_change_validated_input(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    (repo / "validation").mkdir(parents=True)
    (repo / "validation" / "impact-map.v1.json").write_text(
        POLICY.read_text(encoding="utf-8"), encoding="utf-8"
    )
    run(["git", "init", "-q"], cwd=repo, check=True)
    report = repo / "anthill" / "new.py"
    monkeypatch.setattr(
        cli,
        "execute_plan",
        lambda plan, *args, **kwargs: {
            "schema_version": "anthill.validation-run/1.0.0",
            "plan": plan,
            "attempts": [],
            "current_run_attempt": 1,
            "deferred_checks": [],
            "feedback_conclusion": "passed",
            "promotion_eligible": False,
        },
    )
    stdout = io.StringIO()
    stderr = io.StringIO()

    code = cli.main(
        [
            "run",
            "--base-ref",
            "unused",
            "--path",
            "anthill/schema.py",
            "--report",
            str(report),
        ],
        repo=repo,
        stdout=stdout,
        stderr=stderr,
    )

    assert code == 3
    assert stdout.getvalue() == ""
    assert "must be Git-ignored" in json.loads(stderr.getvalue())["error"]
    assert not report.exists()


def test_automatic_run_fails_when_inputs_change_during_execution(monkeypatch, tmp_path):
    def discovery(input_sha256: str):
        return {
            "base_ref": "origin/main",
            "base_sha": "1" * 40,
            "head_sha": "2" * 40,
            "merge_base_sha": "1" * 40,
            "changes": [
                {
                    "path": "anthill/schema.py",
                    "statuses": ["M"],
                    "sources": ["unstaged"],
                }
            ],
            "skip_worktree_paths": [],
            "assume_unchanged_paths": [],
            "workspace_visibility": "complete",
            "complete_change_detection": True,
            "input_sha256": input_sha256,
            "base_policy_sha256": POLICY_SHA256,
            "worktree_policy_sha256": POLICY_SHA256,
            "protected_base_policy_match": True,
        }

    discoveries = iter((discovery("3" * 64), discovery("4" * 64)))
    monkeypatch.setattr(cli, "discover_git_changes", lambda repo, base_ref: next(discoveries))

    def fake_execute(plan, repo, previous_report=None, run_command=None):
        assert run_command is cli._run_quietly
        return {
            "schema_version": "anthill.validation-run/1.0.0",
            "plan": plan,
            "attempts": [],
            "current_run_attempt": 1,
            "deferred_checks": [],
            "feedback_conclusion": "passed",
            "promotion_eligible": False,
        }

    monkeypatch.setattr(cli, "execute_plan", fake_execute)

    code, stdout, stderr = _invoke(
        "run",
        "--base-ref",
        "origin/main",
        "--report",
        str(tmp_path / "s0.json"),
    )

    report = json.loads(stdout)
    assert code == 1
    assert stderr == ""
    assert report["feedback_conclusion"] == "stale_input"
    assert report["input_stability"] == {
        "status": "stale",
        "before_sha256": "3" * 64,
        "after_sha256": "4" * 64,
    }


def test_quiet_command_runner_captures_child_output():
    result = cli._run_quietly(
        [sys.executable, "-c", "print('child noise')"],
        check=False,
        shell=False,
    )

    assert result.returncode == 0
    assert result.stdout.strip() == b"child noise"


@pytest.mark.parametrize(
    ("conclusion", "coverage", "expected"),
    [
        ("passed_after_retry", "complete", 0),
        ("failed", "complete", 1),
        ("inconclusive", "partial", 2),
        ("passed", "partial", 2),
    ],
)
def test_run_exit_codes_distinguish_failure_from_incomplete_feedback(
    monkeypatch, tmp_path, conclusion, coverage, expected
):
    policy = load_policy(POLICY)
    plan = build_plan(policy, ["anthill/schema.py"], change_source="explicit")
    plan["feedback_coverage"] = coverage

    monkeypatch.setattr(cli, "_create_plan", lambda *args, **kwargs: (plan, None))
    monkeypatch.setattr(
        cli,
        "execute_plan",
        lambda *args, **kwargs: {
            "schema_version": "anthill.validation-run/1.0.0",
            "plan": plan,
            "attempts": [],
            "current_run_attempt": 1,
            "deferred_checks": [],
            "feedback_conclusion": conclusion,
            "promotion_eligible": False,
        },
    )

    code, _, _ = _invoke(
        "run",
        "--base-ref",
        "unused",
        "--path",
        "anthill/schema.py",
        "--report",
        str(tmp_path / f"{conclusion}.json"),
    )

    assert code == expected


def test_discovery_or_configuration_error_is_json_on_stderr(monkeypatch):
    monkeypatch.setattr(
        cli,
        "discover_git_changes",
        lambda repo, base_ref: (_ for _ in ()).throw(cli.DiscoveryError("base ref is unavailable")),
    )

    code, stdout, stderr = _invoke("plan", "--base-ref", "missing")

    assert code == 3
    assert stdout == ""
    assert json.loads(stderr) == {
        "error": "base ref is unavailable",
        "error_type": "DiscoveryError",
    }


def test_malformed_previous_report_is_a_controlled_configuration_error(tmp_path):
    report = tmp_path / "s0.json"
    report.write_text('{"schema_version":"wrong"}\n', encoding="utf-8")

    code, stdout, stderr = _invoke(
        "run",
        "--base-ref",
        "unused",
        "--path",
        "README.md",
        "--report",
        str(report),
    )

    assert code == 3
    assert stdout == ""
    assert json.loads(stderr)["error"] == "unsupported validation report schema"


def test_parser_exposes_no_force_or_skip_bypass():
    parser = cli.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "run",
                "--base-ref",
                "origin/main",
                "--report",
                "s0.json",
                "--force",
            ]
        )
    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "run",
                "--base-ref",
                "origin/main",
                "--report",
                "s0.json",
                "--skip",
            ]
        )

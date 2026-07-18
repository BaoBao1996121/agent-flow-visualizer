import json
from pathlib import Path
from subprocess import CompletedProcess, run
import sys

import pytest

from validation.runner import (
    DiscoveryError,
    IMPACT_MAP_PATH,
    STAGE_ORDER,
    _name_status,
    build_plan,
    commands_for_plan,
    discover_git_changes,
    execute_plan,
    load_policy,
    write_manifest_atomic,
)


ROOT = Path(__file__).parents[1]
POLICY = ROOT / "validation" / "impact-map.v1.json"


def test_known_adapter_change_has_a_stable_auditable_plan():
    policy = load_policy(POLICY)

    first = build_plan(policy, ["anthill/adapters/langgraph.py"], change_source="explicit")
    second = build_plan(policy, ["anthill/adapters/langgraph.py"], change_source="explicit")

    assert first == second
    assert first["required_stage"] == "S1"
    assert first["feedback_coverage"] == "complete"
    assert first["changed_paths"] == ["anthill/adapters/langgraph.py"]
    assert "adapter-langgraph" in first["matched_rules"]
    assert {check["id"] for check in first["checks"]} >= {
        "ruff-all",
        "pytest-langgraph",
    }
    assert "pytest-all" not in {check["id"] for check in first["checks"]}
    assert len(first["impact_map_sha256"]) == 64
    assert len(first["plan_sha256"]) == 64


def test_unknown_path_fails_closed_to_hosted_s2():
    plan = build_plan(load_policy(POLICY), ["future/new-boundary.bin"], change_source="explicit")

    assert plan["required_stage"] == "S2"
    assert plan["feedback_coverage"] == "none"
    assert plan["unknown_paths"] == ["future/new-boundary.bin"]
    assert {check["id"] for check in plan["checks"]} == {"s2-hosted"}


def test_drive_relative_windows_paths_are_not_repository_paths():
    with pytest.raises(ValueError, match="repository-relative"):
        build_plan(load_policy(POLICY), ["C:relative.py"], change_source="explicit")


@pytest.mark.parametrize(
    "path",
    [
        "docs/tool.py",
        "samples/tool.js",
        "anthill/projections/tool.js",
        "analyzer/tool.js",
        "tracer/tool.bin",
    ],
)
def test_known_directories_do_not_whitelist_future_file_kinds(path):
    plan = build_plan(load_policy(POLICY), [path], change_source="explicit")

    assert plan["required_stage"] == "S2"
    assert plan["feedback_coverage"] == "none"
    assert plan["unknown_paths"] == [path]


def test_storage_change_selects_bounded_storage_vertical_checks():
    plan = build_plan(load_policy(POLICY), ["anthill/store.py"], change_source="explicit")
    check_ids = {check["id"] for check in plan["checks"]}

    assert plan["required_stage"] == "S1"
    assert {"pytest-api-vertical", "pytest-storage", "ruff-all"} <= check_ids
    assert "pytest-core" not in check_ids
    assert "pytest-all" not in check_ids


def test_server_entrypoint_runs_its_own_contract_and_browser_vertical():
    plan = build_plan(load_policy(POLICY), ["server.py"], change_source="explicit")
    check_ids = {check["id"] for check in plan["checks"]}

    assert plan["required_stage"] == "S1"
    assert plan["feedback_coverage"] == "complete"
    assert {"pytest-server", "browser-s0", "ruff-all"} <= check_ids


def test_control_plane_cannot_use_a_modified_policy_to_downgrade_itself():
    policy = load_policy(POLICY)
    policy["rules"] = [
        {
            "id": "unsafe-self-downgrade",
            "match": {"prefix": ["validation/"]},
            "minimum_stage": "S0",
            "feedback_coverage": "complete",
            "checks": ["ruff-all"],
        }
    ]

    plan = build_plan(policy, ["validation/runner.py"], change_source="explicit")

    assert plan["required_stage"] == "S2"
    assert "hardcoded-control-plane" in plan["matched_rules"]
    assert {check["id"] for check in plan["checks"]} >= {"ruff-all", "s2-hosted"}


def _git(repo: Path, *args: str) -> str:
    result = run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def test_git_discovery_unions_committed_staged_unstaged_untracked_and_rename(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "s0@example.test")
    _git(repo, "config", "user.name", "S0")
    for name in ("old.py", "staged.py", "work.py"):
        (repo / name).write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "tag", "base")
    _git(repo, "mv", "old.py", "new.py")
    _git(repo, "commit", "-qm", "rename")
    (repo / "staged.py").write_text("staged\n", encoding="utf-8")
    _git(repo, "add", "staged.py")
    (repo / "work.py").write_text("work\n", encoding="utf-8")
    (repo / "odd ; name.py").write_text("untracked\n", encoding="utf-8")
    (repo / "换行 $().py").write_text("untracked\n", encoding="utf-8")

    discovery = discover_git_changes(repo, base_ref="base")

    assert [change["path"] for change in discovery["changes"]] == sorted(
        ["new.py", "odd ; name.py", "old.py", "staged.py", "work.py", "换行 $().py"]
    )
    assert discovery["complete_change_detection"] is True
    assert discovery["workspace_visibility"] == "complete"
    assert discovery["merge_base_sha"] == _git(repo, "rev-parse", "base")
    assert len(discovery["input_sha256"]) == 64


def test_protected_base_policy_drift_escalates_automatic_plans_to_s2(tmp_path):
    repo = tmp_path / "repo"
    (repo / "validation").mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.name", "Anthill Tests")
    _git(repo, "config", "user.email", "anthill@example.invalid")
    policy_path = repo / "validation" / "impact-map.v1.json"
    policy_path.write_text('{"policy":"old"}\n', encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "checkout", "-qb", "feature")
    (repo / "anthill").mkdir()
    (repo / "anthill" / "schema.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "feature")
    _git(repo, "checkout", "-q", "main")
    policy_path.write_text('{"policy":"stronger"}\n', encoding="utf-8")
    _git(repo, "commit", "-qam", "strengthen policy")
    _git(repo, "checkout", "-q", "feature")

    discovery = discover_git_changes(repo, base_ref="main")
    plan = build_plan(
        load_policy(POLICY),
        [change["path"] for change in discovery["changes"]],
        change_source="git",
        input_context=discovery,
    )

    assert discovery["protected_base_policy_match"] is False
    assert discovery["base_policy_sha256"] != discovery["worktree_policy_sha256"]
    assert plan["required_stage"] == "S2"
    assert "protected-base-policy-mismatch" in plan["matched_rules"]


@pytest.mark.parametrize("discovered_digest", [None, "0" * 64])
def test_loaded_policy_must_match_the_automatically_discovered_worktree_digest(
    discovered_digest,
):
    policy = load_policy(POLICY)
    input_context = {
        "complete_change_detection": True,
        "protected_base_policy_match": True,
        "worktree_policy_sha256": discovered_digest,
    }

    plan = build_plan(
        policy,
        ["anthill/schema.py"],
        change_source="git",
        input_context=input_context,
    )

    assert plan["required_stage"] == "S2"
    assert plan["feedback_coverage"] == "partial"
    assert "loaded-policy-input-mismatch" in plan["matched_rules"]


def test_nul_git_parser_preserves_newlines_unicode_and_shell_metacharacters():
    path = "line\n换行 ; $().py"

    assert _name_status(b"M\0" + path.encode("utf-8") + b"\0") == [("M", path)]


@pytest.mark.parametrize("domain", ["staged", "unstaged", "untracked"])
def test_input_fingerprint_changes_for_same_size_content_rewrites(tmp_path, domain):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "s0@example.test")
    _git(repo, "config", "user.name", "S0")
    (repo / "tracked.txt").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "tracked.txt")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "tag", "base")
    target = repo / ("new.txt" if domain == "untracked" else "tracked.txt")
    target.write_text("left\n", encoding="utf-8")
    if domain == "staged":
        _git(repo, "add", "tracked.txt")
    first = discover_git_changes(repo, base_ref="base")

    target.write_text("rght\n", encoding="utf-8")
    if domain == "staged":
        _git(repo, "add", "tracked.txt")
    second = discover_git_changes(repo, base_ref="base")

    assert first["input_sha256"] != second["input_sha256"]


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"max_untracked_files": 1}, "untracked file count"),
        ({"max_untracked_bytes": 3}, "untracked byte count"),
        ({"max_changed_bytes": 3}, "changed content byte count"),
    ],
)
def test_untracked_discovery_bounds_fail_closed(tmp_path, kwargs, message):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "s0@example.test")
    _git(repo, "config", "user.name", "S0")
    (repo / "tracked.py").write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "tag", "base")
    (repo / "one.txt").write_text("12", encoding="utf-8")
    (repo / "two.txt").write_text("34", encoding="utf-8")

    with pytest.raises(DiscoveryError, match=message):
        discover_git_changes(repo, base_ref="base", **kwargs)


def test_changed_gitlink_fails_closed_instead_of_looking_like_a_regular_add(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "s0@example.test")
    _git(repo, "config", "user.name", "S0")
    (repo / "tracked.py").write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "tag", "base")
    object_id = _git(repo, "rev-parse", "HEAD")
    _git(
        repo,
        "update-index",
        "--add",
        "--cacheinfo",
        f"160000,{object_id},vendor/submodule",
    )

    with pytest.raises(DiscoveryError, match="special Git entry"):
        discover_git_changes(repo, base_ref="base")


def test_every_tracked_or_untracked_workspace_path_has_an_explicit_impact_rule():
    policy = load_policy(POLICY)
    workspace_paths = (
        _git(
            ROOT,
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
        )
        .rstrip("\0")
        .split("\0")
    )

    unmapped = [
        path
        for path in workspace_paths
        if build_plan(policy, [path], change_source="census")["unknown_paths"]
    ]

    assert unmapped == []


def test_phase0_visual_lab_has_a_dedicated_one_test_browser_and_syntax_path():
    policy = load_policy(POLICY)
    plan = build_plan(
        policy,
        ["static/js/labs/phase0/bootstrap.mjs"],
        change_source="contract",
    )

    assert plan["required_stage"] == "S1"
    assert plan["feedback_coverage"] == "complete"
    assert [check["id"] for check in plan["checks"]] == [
        "browser-visual-lab-s0",
        "frontend-contracts",
        "node-visual-lab",
    ]


def test_va1_concept_board_has_a_dedicated_s1_browser_docs_and_syntax_path():
    policy = load_policy(POLICY)
    plan = build_plan(
        policy,
        ["docs/visual-lab/va1/board.css"],
        change_source="contract",
    )

    assert plan["required_stage"] == "S1"
    assert plan["feedback_coverage"] == "complete"
    assert [check["id"] for check in plan["checks"]] == [
        "browser-va1-s0",
        "docs-contracts",
        "node-va1",
    ]


def test_server_entrypoint_runs_both_production_and_visual_lab_browser_smokes():
    plan = build_plan(load_policy(POLICY), ["server.py"], change_source="contract")
    check_ids = {check["id"] for check in plan["checks"]}

    assert "browser-s0" in check_ids
    assert "browser-visual-lab-s0" in check_ids


def test_policy_rejects_duplicate_rules_and_unknown_check_references(tmp_path):
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    policy["rules"].append(
        {
            "id": policy["rules"][0]["id"],
            "match": {"exact": ["duplicate.txt"]},
            "minimum_stage": "S0",
            "feedback_coverage": "complete",
            "checks": ["not-a-registered-check"],
        }
    )
    candidate = tmp_path / "impact.json"
    candidate.write_text(json.dumps(policy), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate rule id"):
        load_policy(candidate)


def test_policy_rejects_invalid_historical_replay_metadata(tmp_path):
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    policy["historical_replays"][0]["required_checks"] = ["not-registered"]
    candidate = tmp_path / "impact.json"
    candidate.write_text(json.dumps(policy), encoding="utf-8")

    with pytest.raises(ValueError, match="historical replay.*unknown checks"):
        load_policy(candidate)


def test_policy_requires_a_non_empty_playwright_grep(tmp_path):
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    policy["checks"]["browser-s0"]["grep"] = ""
    candidate = tmp_path / "impact.json"
    candidate.write_text(json.dumps(policy), encoding="utf-8")

    with pytest.raises(ValueError, match="playwright grep"):
        load_policy(candidate)


def test_policy_rejects_complete_rules_with_only_deferred_evidence(tmp_path):
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    complete_rule = next(
        rule for rule in policy["rules"] if rule["feedback_coverage"] == "complete"
    )
    complete_rule["checks"] = ["s2-hosted"]
    candidate = tmp_path / "impact.json"
    candidate.write_text(json.dumps(policy), encoding="utf-8")

    with pytest.raises(ValueError, match="complete rule.*executable check"):
        load_policy(candidate)


def test_policy_rejects_node_checks_without_targets(tmp_path):
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    policy["checks"]["node-anthill"]["targets"] = []
    candidate = tmp_path / "impact.json"
    candidate.write_text(json.dumps(policy), encoding="utf-8")

    with pytest.raises(ValueError, match="node-check.*non-empty targets"):
        load_policy(candidate)


def test_policy_rejects_non_string_historical_check_ids_as_configuration(tmp_path):
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    policy["historical_replays"][0]["required_checks"] = [{"id": "pytest-langgraph"}]
    candidate = tmp_path / "impact.json"
    candidate.write_text(json.dumps(policy), encoding="utf-8")

    with pytest.raises(ValueError, match="historical replay.*requires checks"):
        load_policy(candidate)


def test_command_plan_merges_pytest_targets_and_never_uses_changed_paths_as_commands():
    policy = load_policy(POLICY)
    plan = build_plan(
        policy,
        ["anthill/adapters/langgraph.py", "validation/runner.py", "odd ; $().py"],
        change_source="explicit",
    )

    command_plan = commands_for_plan(plan, ROOT, which=lambda name: f"/tools/{name}")

    pytest_commands = [
        command for command in command_plan["commands"] if command["kind"] == "pytest"
    ]
    assert len(pytest_commands) == 1
    assert pytest_commands[0]["argv"] == [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--",
        "tests/test_api.py",
        "tests/test_ci_staging_contract.py",
        "tests/test_langgraph_adapter.py",
        "tests/test_validation_cli.py",
        "tests/test_validation_runner.py",
        "tests/test_version_contract.py",
    ]
    assert set(pytest_commands[0]["check_ids"]) == {
        "policy-contracts",
        "pytest-langgraph",
    }
    assert all("odd ; $().py" not in argument for argument in pytest_commands[0]["argv"])
    assert command_plan["deferred_checks"] == ["s2-hosted"]


def test_command_targets_are_separated_from_tool_options():
    plan = {
        "checks": [
            {
                "id": "pytest-sentinel",
                "kind": "pytest",
                "targets": ["--version"],
                "timeout_seconds": 1,
            },
            {
                "id": "node-sentinel",
                "kind": "node-check",
                "targets": ["--eval"],
                "timeout_seconds": 1,
            },
        ]
    }

    command_plan = commands_for_plan(
        plan,
        ROOT,
        which=lambda name: f"/tools/{name}",
        find_spec=lambda name: object(),
    )

    argv_by_kind = {command["kind"]: command["argv"] for command in command_plan["commands"]}
    assert argv_by_kind["pytest"][-2:] == ["--", "--version"]
    assert argv_by_kind["node-check"][-2:] == ["--", "--eval"]


def test_deferred_checks_cannot_conclude_passed_even_if_a_plan_claims_complete():
    plan = build_plan(load_policy(POLICY), ["future/new-boundary.bin"], change_source="explicit")
    plan["feedback_coverage"] = "complete"

    report = execute_plan(plan, ROOT)

    assert report["deferred_checks"] == ["s2-hosted"]
    assert report["attempts"] == []
    assert report["feedback_conclusion"] == "inconclusive"


def test_playwright_zero_exit_must_still_report_the_one_selected_test_passed(tmp_path):
    plan = build_plan(load_policy(POLICY), ["server.py"], change_source="explicit")
    playwright_cli = tmp_path / "node_modules" / "@playwright" / "test" / "cli.js"
    playwright_cli.parent.mkdir(parents=True)
    playwright_cli.write_text("// isolated prerequisite sentinel\n", encoding="utf-8")

    def skipped_browser(argv, **kwargs):
        output = (
            b"Running 1 test using 1 worker\n  1 skipped\n"
            if "node_modules/@playwright/test/cli.js" in argv
            else b"passed\n"
        )
        return CompletedProcess(argv, 0, stdout=output)

    report = execute_plan(plan, tmp_path, run_command=skipped_browser)
    browser_attempt = next(
        attempt for attempt in report["attempts"] if attempt["command_id"] == "browser-s0"
    )

    assert browser_attempt["result"] == "failed"
    assert "did not report exactly one passed test" in browser_attempt["reason"]
    assert report["feedback_conclusion"] == "failed"


def test_selected_missing_prerequisites_are_explicit_failures(tmp_path):
    plan = build_plan(
        load_policy(POLICY),
        ["static/js/anthill.js", "validation/runner.py"],
        change_source="explicit",
    )

    command_plan = commands_for_plan(
        plan,
        tmp_path,
        which=lambda name: "C:/tools/node.exe" if name == "node" else None,
        find_spec=lambda name: None,
        path_exists=lambda path: False,
    )

    assert {error["tool"] for error in command_plan["prerequisite_errors"]} == {
        "pytest",
        "ruff",
        "node_modules/@playwright/test/cli.js",
    }
    assert all(
        command["kind"] not in {"pytest", "ruff", "playwright"}
        for command in command_plan["commands"]
    )


def test_every_registered_file_target_exists():
    policy = load_policy(POLICY)

    missing = sorted(
        target
        for check in policy["checks"].values()
        for target in check.get("targets", [])
        if not (ROOT / target.split("::", 1)[0]).is_file()
    )
    node_targets = sorted(
        target
        for check in policy["checks"].values()
        for target in check.get("targets", [])
        if "::" in target
    )

    assert missing == []
    if node_targets:
        collection = run(
            [sys.executable, "-m", "pytest", "--collect-only", "-q", *node_targets],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert collection.returncode == 0, collection.stdout + collection.stderr


def test_versioned_historical_replays_select_their_regression_contracts():
    policy = load_policy(POLICY)
    assert policy["historical_replays"] == [
        {
            "id": "langgraph-deep-ndjson-29570924390",
            "source_url": "https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29570924390",
            "changed_paths": ["anthill/adapters/langgraph.py"],
            "minimum_stage": "S1",
            "required_checks": ["pytest-langgraph"],
            "canary_targets": [
                "tests/test_langgraph_adapter.py::test_langgraph_ndjson_parser_contains_non_decoder_value_errors",
                "tests/test_langgraph_adapter.py::test_langgraph_ndjson_rejects_excessive_nesting_before_decoder_behavior_diverges",
            ],
        },
        {
            "id": "visual-container-pip-cache-29638437349",
            "source_url": "https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29638437349",
            "changed_paths": [".github/workflows/ci.yml"],
            "minimum_stage": "S2",
            "required_checks": ["policy-contracts", "s2-hosted", "visual-contracts"],
            "canary_targets": [
                "tests/test_visual_baseline_contract.py::test_visual_regression_uses_an_exact_python_runtime_lock"
            ],
        },
    ]

    for replay in policy["historical_replays"]:
        plan = build_plan(
            policy,
            replay["changed_paths"],
            change_source=f"historical-replay:{replay['id']}",
        )

        assert STAGE_ORDER[plan["required_stage"]] >= STAGE_ORDER[replay["minimum_stage"]]
        assert set(replay["required_checks"]) <= {check["id"] for check in plan["checks"]}
        selected_files = {
            target.split("::", 1)[0]
            for check in plan["checks"]
            for target in check.get("targets", [])
        }
        assert {target.split("::", 1)[0] for target in replay["canary_targets"]} <= selected_files

    canaries = [
        target for replay in policy["historical_replays"] for target in replay["canary_targets"]
    ]
    collection = run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", *canaries],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert collection.returncode == 0, collection.stdout + collection.stderr


def test_retry_appends_attempts_and_preserves_the_first_failure(tmp_path):
    plan = build_plan(
        load_policy(POLICY), ["anthill/adapters/langgraph.py"], change_source="explicit"
    )
    first_calls = 0

    def first_run(argv, **kwargs):
        nonlocal first_calls
        first_calls += 1
        assert kwargs["shell"] is False
        return CompletedProcess(argv, 1 if first_calls == 1 else 0)

    first = execute_plan(plan, ROOT, run_command=first_run)
    second = execute_plan(
        plan,
        ROOT,
        previous_report=first,
        run_command=lambda argv, **kwargs: CompletedProcess(argv, 0),
    )
    manifest = tmp_path / "nested" / "s0.json"
    write_manifest_atomic(manifest, second)

    assert first["feedback_conclusion"] == "failed"
    assert second["feedback_conclusion"] == "passed_after_retry"
    assert [attempt["run_attempt"] for attempt in second["attempts"]] == [1, 1, 2, 2]
    assert second["attempts"][0]["result"] == "failed"
    assert json.loads(manifest.read_text(encoding="utf-8")) == second
    assert list(manifest.parent.glob("*.tmp")) == []


def test_atomic_manifest_failure_preserves_the_previous_report(monkeypatch, tmp_path):
    manifest = tmp_path / "s0.json"
    manifest.write_text('{"previous":true}\n', encoding="utf-8")

    def fail_replace(source, destination):
        raise OSError("simulated replace failure")

    monkeypatch.setattr("validation.runner.os.replace", fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        write_manifest_atomic(manifest, {"replacement": True})

    assert manifest.read_text(encoding="utf-8") == '{"previous":true}\n'
    assert list(tmp_path.glob(".s0.json.*.tmp")) == []


def test_command_output_is_retained_but_bounded_for_diagnostics():
    plan = build_plan(
        load_policy(POLICY), ["anthill/adapters/langgraph.py"], change_source="explicit"
    )
    payload = b"prefix-should-be-truncated--useful-tail"

    report = execute_plan(
        plan,
        ROOT,
        run_command=lambda argv, **kwargs: CompletedProcess(argv, 1, stdout=payload),
        max_output_bytes=12,
    )

    assert report["feedback_conclusion"] == "failed"
    assert all(attempt["output"] == "-useful-tail" for attempt in report["attempts"])
    assert all(attempt["output_bytes"] == len(payload) for attempt in report["attempts"])
    assert all(attempt["output_truncated"] is True for attempt in report["attempts"])


def test_visibility_limited_workspace_is_explicit_and_requires_s2(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "s0@example.test")
    _git(repo, "config", "user.name", "S0")
    (repo / "validation").mkdir()
    (repo / IMPACT_MAP_PATH).write_bytes(POLICY.read_bytes())
    (repo / "tracked.py").write_text("value = 1\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "tag", "base")
    _git(repo, "update-index", "--skip-worktree", "tracked.py")

    discovery = discover_git_changes(repo, base_ref="base")
    plan = build_plan(
        load_policy(POLICY),
        ["anthill/schema.py"],
        change_source="git",
        input_context=discovery,
    )

    assert discovery["workspace_visibility"] == "limited"
    assert discovery["skip_worktree_paths"] == ["tracked.py"]
    assert discovery["complete_change_detection"] is False
    assert plan["required_stage"] == "S2"
    assert plan["input_context"]["complete_change_detection"] is False
    assert "workspace-visibility-limited" in plan["matched_rules"]


def test_clean_complete_discovery_produces_an_explicit_no_change_plan(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "s0@example.test")
    _git(repo, "config", "user.name", "S0")
    (repo / "validation").mkdir()
    (repo / IMPACT_MAP_PATH).write_bytes(POLICY.read_bytes())
    (repo / "tracked.py").write_text("value = 1\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "tag", "base")

    discovery = discover_git_changes(repo, base_ref="base")
    plan = build_plan(
        load_policy(POLICY),
        [],
        change_source="git",
        input_context=discovery,
    )

    assert discovery["complete_change_detection"] is True
    assert plan["no_changes"] is True
    assert plan["required_stage"] == "S0"
    assert plan["feedback_coverage"] == "complete"
    assert plan["checks"] == []


def test_discovery_records_the_peeled_commit_for_an_annotated_base_tag(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "s0@example.test")
    _git(repo, "config", "user.name", "S0")
    (repo / "tracked.py").write_text("value = 1\n", encoding="utf-8")
    _git(repo, "add", "tracked.py")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "tag", "-a", "base", "-m", "annotated base")

    discovery = discover_git_changes(repo, base_ref="base")

    assert discovery["base_sha"] == _git(repo, "rev-parse", "base^{commit}")
    assert discovery["base_sha"] != _git(repo, "rev-parse", "base")


def test_empty_explicit_path_list_cannot_claim_a_no_change_green_plan():
    with pytest.raises(ValueError, match="complete discovery context"):
        build_plan(load_policy(POLICY), [], change_source="explicit")


@pytest.mark.parametrize("status", ["U", "T", "X", "R100"])
def test_git_hazard_statuses_fail_closed(status):
    raw = status.encode("ascii") + b"\0dangerous.py\0"

    with pytest.raises(DiscoveryError, match="unsupported Git change status"):
        _name_status(raw)

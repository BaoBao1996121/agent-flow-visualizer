from __future__ import annotations

import argparse
import inspect
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence, TextIO

from validation.runner import (
    STAGE_ORDER,
    DiscoveryError,
    build_plan,
    discover_git_changes,
    execute_plan,
    load_policy,
    write_manifest_atomic,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m validation",
        description="Plan or run Anthill's advisory staged validation.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "run"):
        command = commands.add_parser(name)
        command.add_argument(
            "--base-ref",
            required=True,
            help="Git base used when --path is omitted.",
        )
        command.add_argument(
            "--path",
            action="append",
            dest="paths",
            metavar="REPOSITORY_PATH",
            help="Explicit changed path; repeat for multiple paths.",
        )
        if name == "run":
            command.add_argument(
                "--report",
                required=True,
                type=Path,
                help="Atomic JSON report destination.",
            )
    return parser


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _emit(stream: TextIO, value: Any) -> None:
    stream.write(_stable_json(value))


def _create_plan(
    arguments: argparse.Namespace,
    repo: Path,
    policy: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if arguments.paths:
        return (
            build_plan(policy, arguments.paths, change_source="explicit"),
            None,
        )

    discovery = discover_git_changes(repo, base_ref=arguments.base_ref)
    paths = [change["path"] for change in discovery["changes"]]
    keywords: dict[str, Any] = {"change_source": "git"}
    if "input_context" in inspect.signature(build_plan).parameters:
        keywords["input_context"] = discovery
    return build_plan(policy, paths, **keywords), discovery


def _plan_exit_code(plan: dict[str, Any]) -> int:
    incomplete = plan["feedback_coverage"] != "complete" or bool(plan.get("unknown_paths"))
    hosted = STAGE_ORDER[plan["required_stage"]] >= STAGE_ORDER["S2"]
    return 2 if incomplete or hosted else 0


def _run_exit_code(report: dict[str, Any]) -> int:
    conclusion = report["feedback_conclusion"]
    if conclusion in {"failed", "stale_input"}:
        return 1
    plan = report["plan"]
    if (
        conclusion not in {"passed", "passed_after_retry"}
        or plan["feedback_coverage"] != "complete"
        or STAGE_ORDER[plan["required_stage"]] >= STAGE_ORDER["S2"]
    ):
        return 2
    return 0


def _load_previous_report(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError("existing validation report must be a JSON object")
    if report.get("schema_version") != "anthill.validation-run/1.0.0":
        raise ValueError("unsupported validation report schema")
    plan = report.get("plan")
    if not isinstance(plan, dict) or not isinstance(plan.get("plan_sha256"), str):
        raise ValueError("existing validation report has an invalid plan")
    attempts = report.get("attempts")
    if not isinstance(attempts, list) or any(
        not isinstance(attempt, dict)
        or not isinstance(attempt.get("run_attempt"), int)
        or attempt["run_attempt"] < 1
        or not isinstance(attempt.get("result"), str)
        for attempt in attempts
    ):
        raise ValueError("existing validation report has invalid attempts")
    return report


def _validated_report_path(repository: Path, requested: Path) -> Path:
    destination = requested if requested.is_absolute() else repository / requested
    destination = destination.resolve()
    try:
        relative = destination.relative_to(repository)
    except ValueError:
        return destination
    if relative.parts and relative.parts[0] == ".git":
        raise ValueError("validation report cannot be written inside .git")
    ignored = subprocess.run(
        ["git", "-C", str(repository), "check-ignore", "-q", "--", relative.as_posix()],
        check=False,
        capture_output=True,
        shell=False,
    )
    if ignored.returncode == 0:
        return destination
    if ignored.returncode == 1:
        raise ValueError("validation report inside the repository must be Git-ignored")
    message = ignored.stderr.decode("utf-8", errors="replace").strip()
    raise ValueError(message or "could not verify validation report ignore status")


def _run_quietly(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        argv,
        **kwargs,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def _mark_input_stability(
    report: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
) -> None:
    stale = before["input_sha256"] != after["input_sha256"]
    report["input_stability"] = {
        "status": "stale" if stale else "stable",
        "before_sha256": before["input_sha256"],
        "after_sha256": after["input_sha256"],
    }
    if stale:
        report["feedback_conclusion"] = "stale_input"
        report["promotion_eligible"] = False


def main(
    argv: Sequence[str] | None = None,
    *,
    repo: Path | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    output = stdout or sys.stdout
    errors = stderr or sys.stderr
    repository = (repo or Path.cwd()).resolve()
    arguments = build_parser().parse_args(argv)

    try:
        policy = load_policy(repository / "validation" / "impact-map.v1.json")
        plan, discovery = _create_plan(arguments, repository, policy)
        if arguments.command == "plan":
            _emit(output, plan)
            return _plan_exit_code(plan)

        report_path = _validated_report_path(repository, arguments.report)
        previous = _load_previous_report(report_path)
        report = execute_plan(
            plan,
            repository,
            previous_report=previous,
            run_command=_run_quietly,
        )
        if discovery is not None:
            after = discover_git_changes(repository, base_ref=arguments.base_ref)
            _mark_input_stability(report, discovery, after)
        _validated_report_path(repository, report_path)
        write_manifest_atomic(report_path, report)
        _emit(output, report)
        return _run_exit_code(report)
    except (DiscoveryError, json.JSONDecodeError, OSError, UnicodeError, ValueError) as error:
        _emit(
            errors,
            {"error": str(error), "error_type": type(error).__name__},
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())

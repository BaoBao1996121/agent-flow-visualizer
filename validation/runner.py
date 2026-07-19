from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath
from typing import Any


STAGE_ORDER = {"S0": 0, "S1": 1, "S2": 2, "S3": 3, "S4": 4}
DEFAULT_MAX_UNTRACKED_FILES = 1_000
DEFAULT_MAX_UNTRACKED_BYTES = 16 * 1024 * 1024
DEFAULT_MAX_CHANGED_BYTES = 64 * 1024 * 1024
IMPACT_MAP_PATH = "validation/impact-map.v1.json"
HARD_S2_PREFIXES = (".github/", "tests/browser/", "tests/visual/", "validation/")
HARD_S2_EXACT = {
    ".dockerignore",
    ".gitattributes",
    ".gitignore",
    "Dockerfile",
    "compose.yaml",
    "package-lock.json",
    "package.json",
    "playwright.config.mjs",
    "playwright.visual.config.mjs",
    "pyproject.toml",
    "requirements-dev.txt",
    "requirements-visual.txt",
    "requirements.txt",
    "scripts/generate_visual_fixtures.py",
    "tests/test_ci_staging_contract.py",
    "tests/test_validation_cli.py",
    "tests/test_validation_runner.py",
    "tests/test_visual_baseline_contract.py",
}


class DiscoveryError(RuntimeError):
    """Raised when the runner cannot conservatively discover repository changes."""


def _git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        shell=False,
    )
    if result.returncode:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise DiscoveryError(message or f"git {' '.join(args)} failed")
    return result.stdout


def _decode_git_path(raw: bytes) -> str:
    try:
        return _normalize_path(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as error:
        raise DiscoveryError("Git returned an unsafe or non-UTF-8 path") from error


def _name_status(raw: bytes) -> list[tuple[str, str]]:
    if not raw:
        return []
    fields = raw.rstrip(b"\0").split(b"\0")
    if len(fields) % 2:
        raise DiscoveryError("Git name-status output had an unexpected shape")
    changes = []
    for offset in range(0, len(fields), 2):
        try:
            status = fields[offset].decode("ascii")
        except UnicodeDecodeError as error:
            raise DiscoveryError("Git returned a non-ASCII change status") from error
        if status not in {"A", "D", "M"}:
            raise DiscoveryError(f"unsupported Git change status: {status}")
        changes.append((status, _decode_git_path(fields[offset + 1])))
    return changes


def _visibility_flags(repo: Path) -> tuple[list[str], list[str]]:
    skip_worktree = []
    assume_unchanged = []
    for field in _git(repo, "ls-files", "-v", "-z").rstrip(b"\0").split(b"\0"):
        if not field:
            continue
        if len(field) < 3 or field[1:2] != b" ":
            raise DiscoveryError("Git visibility output had an unexpected shape")
        tag = chr(field[0])
        path = _decode_git_path(field[2:])
        if tag == "S":
            skip_worktree.append(path)
        if tag.islower():
            assume_unchanged.append(path)
    return sorted(skip_worktree), sorted(assume_unchanged)


def _special_git_entries(raw: bytes) -> dict[str, str]:
    special = {}
    for field in raw.rstrip(b"\0").split(b"\0") if raw else []:
        try:
            metadata, raw_path = field.split(b"\t", 1)
            mode = metadata.split(b" ", 1)[0].decode("ascii")
        except (UnicodeDecodeError, ValueError) as error:
            raise DiscoveryError("Git mode output had an unexpected shape") from error
        if mode in {"120000", "160000"}:
            special[_decode_git_path(raw_path)] = mode
    return special


def _base_blob_sha256(repo: Path, commit: str, path: str) -> str | None:
    raw = _git(repo, "ls-tree", "-z", commit, "--", path).rstrip(b"\0")
    if not raw:
        return None
    entries = raw.split(b"\0")
    if len(entries) != 1:
        raise DiscoveryError(f"protected-base policy path is ambiguous: {path}")
    try:
        metadata, raw_path = entries[0].split(b"\t", 1)
        mode, kind, object_id = metadata.split(b" ")
    except ValueError as error:
        raise DiscoveryError("protected-base policy metadata had an unexpected shape") from error
    if raw_path.decode("utf-8", errors="strict") != path:
        raise DiscoveryError("protected-base policy path did not round-trip")
    if kind != b"blob" or mode not in {b"100644", b"100755"}:
        raise DiscoveryError("protected-base policy is not a regular Git blob")
    content = _git(repo, "cat-file", "blob", object_id.decode("ascii"))
    return hashlib.sha256(content).hexdigest()


def _worktree_file_sha256(repo: Path, path: str) -> str | None:
    candidate = repo.joinpath(*PurePosixPath(path).parts)
    if not candidate.exists():
        return None
    try:
        if candidate.is_symlink() or not candidate.is_file():
            raise DiscoveryError(f"worktree policy is not a regular file: {path}")
        before = candidate.stat()
        content = candidate.read_bytes()
        after = candidate.stat()
    except OSError as error:
        raise DiscoveryError(f"could not read worktree policy: {path}") from error
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise DiscoveryError(f"worktree policy moved while reading: {path}")
    return hashlib.sha256(content).hexdigest()


def _changed_content_fingerprint(
    repo: Path, paths: list[str], *, max_changed_bytes: int
) -> tuple[str, int]:
    digest = hashlib.sha256()
    total_bytes = 0
    for path in paths:
        encoded_path = path.encode("utf-8")
        digest.update(len(encoded_path).to_bytes(8, "big"))
        digest.update(encoded_path)
        candidate = repo.joinpath(*PurePosixPath(path).parts)
        if not candidate.exists():
            digest.update(b"\0missing\0")
            continue
        try:
            if candidate.is_symlink() or not candidate.is_file():
                raise DiscoveryError(f"changed path is not a regular file: {path}")
            before = candidate.stat()
            total_bytes += before.st_size
            if total_bytes > max_changed_bytes:
                raise DiscoveryError(
                    f"changed content byte count exceeds the {max_changed_bytes} byte bound"
                )
            digest.update(before.st_size.to_bytes(8, "big"))
            with candidate.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            after = candidate.stat()
        except OSError as error:
            raise DiscoveryError(f"could not fingerprint changed path: {path}") from error
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise DiscoveryError(f"changed path moved during fingerprinting: {path}")
    return digest.hexdigest(), total_bytes


def discover_git_changes(
    repo: Path,
    *,
    base_ref: str,
    max_untracked_files: int = DEFAULT_MAX_UNTRACKED_FILES,
    max_untracked_bytes: int = DEFAULT_MAX_UNTRACKED_BYTES,
    max_changed_bytes: int = DEFAULT_MAX_CHANGED_BYTES,
) -> dict[str, Any]:
    repo = repo.resolve()
    if min(max_untracked_files, max_untracked_bytes, max_changed_bytes) < 1:
        raise ValueError("change discovery bounds must be positive")
    merge_bases = _git(repo, "merge-base", "--all", "HEAD", base_ref).decode().splitlines()
    if len(merge_bases) != 1:
        raise DiscoveryError("change discovery requires exactly one merge base")
    merge_base = merge_bases[0]
    head_sha = _git(repo, "rev-parse", "HEAD").decode().strip()
    base_sha = _git(repo, "rev-parse", f"{base_ref}^{{commit}}").decode().strip()
    by_path: dict[str, dict[str, set[str]]] = {}

    def record(status: str, path: str, source: str) -> None:
        entry = by_path.setdefault(path, {"statuses": set(), "sources": set()})
        entry["statuses"].add(status)
        entry["sources"].add(source)

    diff_args = ("--name-status", "-z", "--no-renames", "--no-ext-diff")
    for status, path in _name_status(_git(repo, "diff", *diff_args, merge_base, "HEAD", "--")):
        record(status, path, "committed")
    for status, path in _name_status(_git(repo, "diff", "--cached", *diff_args, "HEAD", "--")):
        record(status, path, "staged")
    for status, path in _name_status(_git(repo, "diff", *diff_args, "--")):
        record(status, path, "unstaged")
    changed_tracked_paths = set(by_path)
    index_state = _git(repo, "ls-files", "--stage", "-z")
    special_entries = {}
    for source, raw in (
        ("merge-base", _git(repo, "ls-tree", "-r", "-z", merge_base)),
        ("HEAD", _git(repo, "ls-tree", "-r", "-z", "HEAD")),
        ("index", index_state),
    ):
        for path, mode in _special_git_entries(raw).items():
            if path in changed_tracked_paths:
                special_entries[path] = {"mode": mode, "source": source}
    if special_entries:
        details = ", ".join(
            f"{path} ({entry['mode']} in {entry['source']})"
            for path, entry in sorted(special_entries.items())
        )
        raise DiscoveryError(f"changed path uses a special Git entry: {details}")
    untracked = _git(repo, "ls-files", "--others", "--exclude-standard", "-z")
    untracked_paths = [
        _decode_git_path(field) for field in untracked.rstrip(b"\0").split(b"\0") if field
    ]
    if len(untracked_paths) > max_untracked_files:
        raise DiscoveryError(f"untracked file count exceeds the {max_untracked_files} file bound")
    untracked_bytes = 0
    for path in untracked_paths:
        candidate = repo.joinpath(*PurePosixPath(path).parts)
        try:
            if candidate.is_symlink() or not candidate.is_file():
                raise DiscoveryError(f"untracked path is not a regular file: {path}")
            untracked_bytes += candidate.stat().st_size
        except OSError as error:
            raise DiscoveryError(f"could not inspect untracked path: {path}") from error
        if untracked_bytes > max_untracked_bytes:
            raise DiscoveryError(
                f"untracked byte count exceeds the {max_untracked_bytes} byte bound"
            )
        record("?", path, "untracked")

    skip_worktree, assume_unchanged = _visibility_flags(repo)
    base_policy_sha256 = _base_blob_sha256(repo, base_sha, IMPACT_MAP_PATH)
    worktree_policy_sha256 = _worktree_file_sha256(repo, IMPACT_MAP_PATH)
    changed_paths = sorted(by_path)
    content_sha256, changed_content_bytes = _changed_content_fingerprint(
        repo, changed_paths, max_changed_bytes=max_changed_bytes
    )
    changes = [
        {
            "path": path,
            "statuses": sorted(details["statuses"]),
            "sources": sorted(details["sources"]),
        }
        for path, details in sorted(by_path.items())
    ]
    stable = {
        "base_sha": base_sha,
        "head_sha": head_sha,
        "merge_base_sha": merge_base,
        "changes": changes,
        "index_sha256": hashlib.sha256(index_state).hexdigest(),
        "changed_content_sha256": content_sha256,
        "changed_content_bytes": changed_content_bytes,
        "base_policy_sha256": base_policy_sha256,
        "worktree_policy_sha256": worktree_policy_sha256,
        "protected_base_policy_match": base_policy_sha256 == worktree_policy_sha256,
        "untracked_file_count": len(untracked_paths),
        "untracked_byte_count": untracked_bytes,
        "skip_worktree_paths": skip_worktree,
        "assume_unchanged_paths": assume_unchanged,
    }
    encoded = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    limited = bool(skip_worktree or assume_unchanged)
    return {
        "base_ref": base_ref,
        **stable,
        "workspace_visibility": "limited" if limited else "complete",
        "complete_change_detection": not limited,
        "input_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
    }


def load_policy(path: Path) -> dict[str, Any]:
    raw_policy = path.read_bytes()
    policy = json.loads(raw_policy.decode("utf-8"))
    if not isinstance(policy, dict):
        raise ValueError("validation impact map must be a JSON object")
    if policy.get("schema_version") != "anthill.validation-impact/1.0.0":
        raise ValueError("unsupported validation impact-map schema")
    _validate_policy(policy)
    policy["_impact_map_sha256"] = hashlib.sha256(raw_policy).hexdigest()
    return policy


def _validate_policy(policy: dict[str, Any]) -> None:
    checks = policy.get("checks")
    rules = policy.get("rules")
    if not isinstance(policy.get("policy_version"), str) or not policy["policy_version"]:
        raise ValueError("policy_version must be a non-empty string")
    if not isinstance(checks, dict) or not checks:
        raise ValueError("checks must be a non-empty object")
    allowed_kinds = {"deferred", "node-check", "playwright", "pytest", "ruff"}
    for check_id, check in checks.items():
        if not isinstance(check_id, str) or not check_id:
            raise ValueError("check ids must be non-empty strings")
        if not isinstance(check, dict):
            raise ValueError(f"check {check_id!r} must be an object")
        if check.get("kind") not in allowed_kinds:
            raise ValueError(f"check {check_id!r} has an unsupported kind")
        if check.get("kind") == "playwright" and not isinstance(check.get("grep"), str):
            raise ValueError(f"check {check_id!r} must define a playwright grep")
        if check.get("kind") == "playwright" and not check["grep"].strip():
            raise ValueError(f"check {check_id!r} must define a non-empty playwright grep")
        if check.get("kind") == "playwright":
            expected_tests = check.get("expected_tests", 1)
            if (
                isinstance(expected_tests, bool)
                or not isinstance(expected_tests, int)
                or expected_tests < 1
            ):
                raise ValueError(
                    f"check {check_id!r} has an invalid playwright expected_tests"
                )
        timeout = check.get("timeout_seconds")
        if not isinstance(timeout, int) or timeout < 0:
            raise ValueError(f"check {check_id!r} has an invalid timeout")
        targets = check.get("targets", [])
        if not isinstance(targets, list) or any(
            not isinstance(target, str) or _normalize_path(target) != target for target in targets
        ):
            raise ValueError(f"check {check_id!r} has invalid targets")
        if check["kind"] == "node-check" and not targets:
            raise ValueError(f"node-check {check_id!r} must define non-empty targets")
    replays = policy.get("historical_replays")
    if not isinstance(replays, list) or not replays:
        raise ValueError("historical_replays must be a non-empty array")
    replay_ids = set()
    for replay in replays:
        if not isinstance(replay, dict):
            raise ValueError("historical replay entries must be objects")
        replay_id = replay.get("id")
        if not isinstance(replay_id, str) or not replay_id or replay_id in replay_ids:
            raise ValueError("historical replay ids must be unique non-empty strings")
        replay_ids.add(replay_id)
        if replay.get("minimum_stage") not in STAGE_ORDER:
            raise ValueError(f"historical replay {replay_id!r} has an invalid stage")
        changed_paths = replay.get("changed_paths")
        if (
            not isinstance(changed_paths, list)
            or not changed_paths
            or any(
                not isinstance(path, str) or _normalize_path(path) != path for path in changed_paths
            )
        ):
            raise ValueError(f"historical replay {replay_id!r} has invalid changed paths")
        required_checks = replay.get("required_checks")
        if (
            not isinstance(required_checks, list)
            or not required_checks
            or any(not isinstance(check_id, str) or not check_id for check_id in required_checks)
        ):
            raise ValueError(f"historical replay {replay_id!r} requires checks")
        unknown_replay_checks = set(required_checks) - set(checks)
        if unknown_replay_checks:
            raise ValueError(
                f"historical replay {replay_id!r} references unknown checks: "
                f"{sorted(unknown_replay_checks)}"
            )
        canary_targets = replay.get("canary_targets")
        if (
            not isinstance(canary_targets, list)
            or not canary_targets
            or any(
                not isinstance(target, str) or _normalize_path(target) != target
                for target in canary_targets
            )
        ):
            raise ValueError(f"historical replay {replay_id!r} has invalid canary targets")
    if not isinstance(rules, list) or not rules:
        raise ValueError("rules must be a non-empty array")
    seen_ids = set()
    for rule in rules:
        if not isinstance(rule, dict):
            raise ValueError("rule entries must be objects")
        rule_id = rule.get("id")
        if not isinstance(rule_id, str) or not rule_id:
            raise ValueError("rule ids must be non-empty strings")
        if rule_id in seen_ids:
            raise ValueError(f"duplicate rule id: {rule_id}")
        seen_ids.add(rule_id)
        if rule.get("minimum_stage") not in STAGE_ORDER:
            raise ValueError(f"rule {rule_id!r} has an invalid stage")
        if rule.get("feedback_coverage") not in {"none", "partial", "complete"}:
            raise ValueError(f"rule {rule_id!r} has invalid feedback coverage")
        match = rule.get("match")
        if not isinstance(match, dict) or not any(
            match.get(key) for key in ("exact", "prefix", "suffix")
        ):
            raise ValueError(f"rule {rule_id!r} must match at least one path")
        for key in ("exact", "prefix", "suffix"):
            values = match.get(key, [])
            if not isinstance(values, list) or any(
                not isinstance(value, str) or not value for value in values
            ):
                raise ValueError(f"rule {rule_id!r} has invalid {key} matches")
        rule_checks = rule.get("checks")
        if not isinstance(rule_checks, list) or any(
            not isinstance(check_id, str) or not check_id for check_id in rule_checks
        ):
            raise ValueError(f"rule {rule_id!r} has invalid checks")
        unknown_checks = set(rule_checks) - set(checks)
        if unknown_checks:
            raise ValueError(
                f"rule {rule_id!r} references unknown checks: {sorted(unknown_checks)}"
            )
        if rule["feedback_coverage"] == "complete" and not any(
            checks[check_id]["kind"] != "deferred" for check_id in rule_checks
        ):
            raise ValueError(f"complete rule {rule_id!r} requires an executable check")
    fallback = policy.get("fallback", {})
    if not isinstance(fallback, dict):
        raise ValueError("fallback must be an object")
    if fallback.get("minimum_stage") not in STAGE_ORDER:
        raise ValueError("fallback has an invalid stage")
    if fallback.get("feedback_coverage") not in {"none", "partial", "complete"}:
        raise ValueError("fallback has invalid feedback coverage")
    fallback_checks = fallback.get("checks")
    if not isinstance(fallback_checks, list) or any(
        not isinstance(check_id, str) or not check_id for check_id in fallback_checks
    ):
        raise ValueError("fallback has invalid checks")
    if set(fallback_checks) - set(checks):
        raise ValueError("fallback references unknown checks")
    if fallback["feedback_coverage"] == "complete" and not any(
        checks[check_id]["kind"] != "deferred" for check_id in fallback_checks
    ):
        raise ValueError("complete fallback requires an executable check")


def _normalize_path(raw: str) -> str:
    if not raw or "\0" in raw or raw.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", raw):
        raise ValueError(f"path must be repository-relative: {raw!r}")
    path = raw.replace("\\", "/").removeprefix("./")
    if any(part == ".." for part in PurePosixPath(path).parts):
        raise ValueError(f"path cannot escape the repository: {raw!r}")
    return path


def _matches(rule: dict[str, Any], path: str) -> bool:
    match = rule.get("match", {})
    return (
        path in match.get("exact", [])
        or any(path.startswith(prefix) for prefix in match.get("prefix", []))
        or any(path.endswith(suffix) for suffix in match.get("suffix", []))
    )


def _coverage(matched: list[dict[str, Any]]) -> str:
    levels = {"none": 0, "partial": 1, "complete": 2}
    return min((rule.get("feedback_coverage", "none") for rule in matched), key=levels.get)


def _hardcoded_control_rule(paths: list[str]) -> dict[str, Any] | None:
    if not any(path in HARD_S2_EXACT or path.startswith(HARD_S2_PREFIXES) for path in paths):
        return None
    return {
        "id": "hardcoded-control-plane",
        "minimum_stage": "S2",
        "feedback_coverage": "partial",
        "checks": ["ruff-all", "s2-hosted"],
    }


def build_plan(
    policy: dict[str, Any],
    paths: list[str],
    *,
    change_source: str,
    input_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    changed_paths = sorted({_normalize_path(path) for path in paths})
    if not changed_paths and input_context is None:
        raise ValueError("an empty path list requires complete discovery context")
    matched = [
        rule for rule in policy["rules"] if any(_matches(rule, path) for path in changed_paths)
    ]
    control_rule = _hardcoded_control_rule(changed_paths)
    if control_rule:
        matched.append(control_rule)
    if input_context and not input_context.get("complete_change_detection", False):
        matched.append(
            {
                "id": "workspace-visibility-limited",
                "minimum_stage": "S2",
                "feedback_coverage": "partial",
                "checks": ["s2-hosted"],
            }
        )
    if input_context and input_context.get("protected_base_policy_match") is False:
        matched.append(
            {
                "id": "protected-base-policy-mismatch",
                "minimum_stage": "S2",
                "feedback_coverage": "partial",
                "checks": ["s2-hosted"],
            }
        )
    if (
        input_context
        and change_source == "git"
        and input_context.get("worktree_policy_sha256") != policy["_impact_map_sha256"]
    ):
        matched.append(
            {
                "id": "loaded-policy-input-mismatch",
                "minimum_stage": "S2",
                "feedback_coverage": "partial",
                "checks": ["s2-hosted"],
            }
        )
    elif not changed_paths:
        matched.append(
            {
                "id": "no-changes",
                "minimum_stage": "S0",
                "feedback_coverage": "complete",
                "checks": [],
            }
        )
    unknown = [
        path for path in changed_paths if not any(_matches(rule, path) for rule in policy["rules"])
    ]
    if unknown:
        matched.append(
            {
                "id": "unknown-path",
                "minimum_stage": policy["fallback"]["minimum_stage"],
                "feedback_coverage": "none",
                "checks": policy["fallback"]["checks"],
            }
        )
    check_ids = sorted({check for rule in matched for check in rule.get("checks", [])})
    stage = max((rule["minimum_stage"] for rule in matched), key=STAGE_ORDER.get)
    plan = {
        "schema_version": "anthill.validation-plan/1.0.0",
        "policy_version": policy["policy_version"],
        "impact_map_sha256": policy["_impact_map_sha256"],
        "change_source": change_source,
        "changed_paths": changed_paths,
        "no_changes": not changed_paths,
        "matched_rules": sorted({rule["id"] for rule in matched}),
        "unknown_paths": unknown,
        "required_stage": stage,
        "feedback_coverage": _coverage(matched),
        "checks": [{"id": check_id, **policy["checks"][check_id]} for check_id in check_ids],
    }
    if input_context is not None:
        plan["input_context"] = {
            key: input_context[key]
            for key in (
                "base_ref",
                "base_sha",
                "head_sha",
                "merge_base_sha",
                "input_sha256",
                "changes",
                "workspace_visibility",
                "complete_change_detection",
                "skip_worktree_paths",
                "assume_unchanged_paths",
                "untracked_file_count",
                "untracked_byte_count",
                "index_sha256",
                "changed_content_sha256",
                "changed_content_bytes",
                "base_policy_sha256",
                "worktree_policy_sha256",
                "protected_base_policy_match",
            )
            if key in input_context
        }
    canonical = json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    plan["plan_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return plan


def commands_for_plan(
    plan: dict[str, Any],
    repo: Path,
    *,
    which=shutil.which,
    find_spec=importlib.util.find_spec,
    path_exists=Path.exists,
) -> dict[str, Any]:
    checks = {check["id"]: check for check in plan["checks"]}
    deferred = sorted(check_id for check_id, check in checks.items() if check["kind"] == "deferred")
    commands = []
    prerequisite_errors = []

    pytest_checks = {
        check_id: check for check_id, check in checks.items() if check["kind"] == "pytest"
    }
    if pytest_checks:
        if find_spec("pytest") is None:
            prerequisite_errors.extend(
                {"check_id": check_id, "tool": "pytest"} for check_id in sorted(pytest_checks)
            )
        else:
            all_targets = any(not check.get("targets", []) for check in pytest_checks.values())
            targets = (
                []
                if all_targets
                else sorted(
                    {
                        target
                        for check in pytest_checks.values()
                        for target in check.get("targets", [])
                    }
                )
            )
            commands.append(
                {
                    "id": "pytest",
                    "kind": "pytest",
                    "check_ids": sorted(pytest_checks),
                    "argv": [
                        sys.executable,
                        "-m",
                        "pytest",
                        "-q",
                        *(["--", *targets] if targets else []),
                    ],
                    "timeout_seconds": max(
                        check["timeout_seconds"] for check in pytest_checks.values()
                    ),
                }
            )

    ruff_checks = sorted(check_id for check_id, check in checks.items() if check["kind"] == "ruff")
    if ruff_checks:
        if find_spec("ruff") is None:
            prerequisite_errors.extend(
                {"check_id": check_id, "tool": "ruff"} for check_id in ruff_checks
            )
        else:
            commands.append(
                {
                    "id": "ruff",
                    "kind": "ruff",
                    "check_ids": ruff_checks,
                    "argv": [sys.executable, "-m", "ruff", "check", "--no-cache", "."],
                    "timeout_seconds": max(
                        checks[check_id]["timeout_seconds"] for check_id in ruff_checks
                    ),
                }
            )

    node = which("node")
    for check_id, check in sorted(checks.items()):
        if check["kind"] == "node-check":
            if not node:
                prerequisite_errors.append({"check_id": check_id, "tool": "node"})
                continue
            for target in check["targets"]:
                commands.append(
                    {
                        "id": f"{check_id}:{target}",
                        "kind": "node-check",
                        "check_ids": [check_id],
                        "argv": [node, "--check", "--", target],
                        "timeout_seconds": check["timeout_seconds"],
                    }
                )
        elif check["kind"] == "playwright":
            if not node:
                prerequisite_errors.append({"check_id": check_id, "tool": "node"})
                continue
            playwright_cli = repo / "node_modules" / "@playwright" / "test" / "cli.js"
            if not path_exists(playwright_cli):
                prerequisite_errors.append(
                    {
                        "check_id": check_id,
                        "tool": "node_modules/@playwright/test/cli.js",
                    }
                )
                continue
            commands.append(
                {
                    "id": check_id,
                    "kind": "playwright",
                    "check_ids": [check_id],
                    "argv": [
                        node,
                        "node_modules/@playwright/test/cli.js",
                        "test",
                        "--grep",
                        check["grep"],
                    ],
                    "expected_tests": check.get("expected_tests", 1),
                    "timeout_seconds": check["timeout_seconds"],
                }
            )
    represented = set(deferred)
    represented.update(error["check_id"] for error in prerequisite_errors)
    represented.update(
        check_id for command in commands for check_id in command.get("check_ids", [])
    )
    missing_representation = sorted(set(checks) - represented)
    if missing_representation:
        raise ValueError(
            f"selected checks have no command representation: {missing_representation}"
        )
    return {
        "commands": sorted(commands, key=lambda command: command["id"]),
        "deferred_checks": deferred,
        "prerequisite_errors": prerequisite_errors,
    }


def execute_plan(
    plan: dict[str, Any],
    repo: Path,
    *,
    previous_report: dict[str, Any] | None = None,
    run_command=subprocess.run,
    budget_seconds: float = 30,
    max_output_bytes: int = 16 * 1024,
) -> dict[str, Any]:
    if max_output_bytes < 1:
        raise ValueError("max_output_bytes must be positive")
    if previous_report and previous_report["plan"]["plan_sha256"] != plan["plan_sha256"]:
        raise ValueError("cannot append attempts for a different validation plan")
    previous_attempts = list(previous_report.get("attempts", [])) if previous_report else []
    run_attempt = max((item["run_attempt"] for item in previous_attempts), default=0) + 1
    command_plan = commands_for_plan(plan, repo)
    current_attempts = []
    run_started = time.perf_counter()

    for error in command_plan["prerequisite_errors"]:
        current_attempts.append(
            {
                "run_attempt": run_attempt,
                "command_id": error["check_id"],
                "check_ids": [error["check_id"]],
                "argv": [],
                "duration_ms": 0,
                "returncode": None,
                "result": "prerequisite_missing",
                "reason": f"missing tool: {error['tool']}",
            }
        )

    for command in command_plan["commands"]:
        elapsed = time.perf_counter() - run_started
        remaining = budget_seconds - elapsed
        if remaining <= 0:
            current_attempts.append(
                {
                    "run_attempt": run_attempt,
                    "command_id": command["id"],
                    "check_ids": command["check_ids"],
                    "argv": command["argv"],
                    "duration_ms": 0,
                    "returncode": None,
                    "result": "budget_exceeded",
                }
            )
            continue
        started = time.perf_counter()
        raw_output = None
        try:
            result = run_command(
                command["argv"],
                cwd=repo,
                timeout=min(command["timeout_seconds"], remaining),
                check=False,
                shell=False,
            )
            returncode = result.returncode
            outcome = "passed" if returncode == 0 else "failed"
            reason = None
            raw_output = getattr(result, "stdout", None)
            if returncode == 0 and command["kind"] == "playwright":
                playwright_output = (
                    raw_output.decode("utf-8", errors="replace")
                    if isinstance(raw_output, bytes)
                    else raw_output or ""
                )
                plain_output = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", playwright_output)
                expected_tests = command["expected_tests"]
                noun = "test" if expected_tests == 1 else "tests"
                run_pattern = re.compile(
                    r"[ \t]*Running (?P<count>[1-9]\d*) (?P<noun>tests?) "
                    r"using (?P<workers>[1-9]\d*) (?P<worker_noun>workers?)"
                    r"(?:, shard (?P<shard>[1-9]\d*) of (?P<shards>[1-9]\d*))?[ \t]*"
                )
                pass_pattern = re.compile(
                    r"[ \t]*(?P<count>[1-9]\d*) passed"
                    r"(?:[ \t]+\([^()\r\n]+\))?[ \t]*"
                )
                negative_pattern = re.compile(
                    r"[ \t]*[1-9]\d* (?:"
                    r"(?:failed|interrupted|flaky|skipped|did not run)"
                    r"(?:[ \t]+\([^()\r\n]+\))?"
                    r"|errors?(?:[ \t]+(?:was|were) not a part of any test, "
                    r"see above for details)?"
                    r")[ \t]*",
                    re.IGNORECASE,
                )
                lines = plain_output.splitlines()
                run_summaries = [
                    match
                    for line in lines
                    if (match := run_pattern.fullmatch(line)) is not None
                ]
                pass_summaries = [
                    match
                    for line in lines
                    if (match := pass_pattern.fullmatch(line)) is not None
                ]
                negative_summaries = [
                    line for line in lines if negative_pattern.fullmatch(line) is not None
                ]
                exact_run = (
                    len(run_summaries) == 1
                    and int(run_summaries[0].group("count")) == expected_tests
                    and run_summaries[0].group("noun") == noun
                    and run_summaries[0].group("worker_noun")
                    == ("worker" if int(run_summaries[0].group("workers")) == 1 else "workers")
                )
                exact_pass = (
                    len(pass_summaries) == 1
                    and int(pass_summaries[0].group("count")) == expected_tests
                )
                if not exact_run or not exact_pass or negative_summaries:
                    outcome = "failed"
                    count = "one" if expected_tests == 1 else str(expected_tests)
                    reason = f"Playwright did not report exactly {count} passed {noun}"
        except subprocess.TimeoutExpired:
            returncode = None
            outcome = "timed_out"
            reason = "command exceeded its S0 timeout"
        except (FileNotFoundError, OSError) as error:
            returncode = None
            outcome = "prerequisite_missing"
            reason = str(error)
        attempt = {
            "run_attempt": run_attempt,
            "command_id": command["id"],
            "check_ids": command["check_ids"],
            "argv": command["argv"],
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "returncode": returncode,
            "result": outcome,
        }
        if raw_output is not None:
            encoded_output = (
                raw_output.encode("utf-8", errors="replace")
                if isinstance(raw_output, str)
                else bytes(raw_output)
            )
            attempt.update(
                {
                    "output": encoded_output[-max_output_bytes:].decode("utf-8", errors="replace"),
                    "output_bytes": len(encoded_output),
                    "output_truncated": len(encoded_output) > max_output_bytes,
                }
            )
        if reason:
            attempt["reason"] = reason
        current_attempts.append(attempt)

    failed_now = any(item["result"] != "passed" for item in current_attempts)
    failed_before = any(item["result"] != "passed" for item in previous_attempts)
    if failed_now:
        conclusion = "failed"
    elif plan["feedback_coverage"] != "complete" or command_plan["deferred_checks"]:
        conclusion = "inconclusive"
    elif failed_before:
        conclusion = "passed_after_retry"
    else:
        conclusion = "passed"
    return {
        "schema_version": "anthill.validation-run/1.0.0",
        "plan": plan,
        "attempts": [*previous_attempts, *current_attempts],
        "current_run_attempt": run_attempt,
        "deferred_checks": command_plan["deferred_checks"],
        "feedback_conclusion": conclusion,
        "promotion_eligible": False,
    }


def write_manifest_atomic(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw_temp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    temp_path = Path(raw_temp)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)

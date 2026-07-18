import re
import subprocess
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
STAGE_LOG = ROOT / "docs" / "STAGE_LOG.md"
LINK_OPEN = re.compile(r"(?P<image>!)?\[(?:\\.|[^]\\\n])*\]\(")
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def _workspace_markdown_paths(root: Path) -> tuple[Path, ...]:
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            "*.md",
        ],
        cwd=root,
        check=True,
        capture_output=True,
    )
    paths = (Path(raw.decode("utf-8")) for raw in result.stdout.split(b"\0") if raw)
    return tuple(path for path in paths if (root / path).is_file())


def _strip_inline_code(line: str) -> str:
    output: list[str] = []
    cursor = 0
    while cursor < len(line):
        if line[cursor] != "`":
            output.append(line[cursor])
            cursor += 1
            continue
        end = cursor
        while end < len(line) and line[end] == "`":
            end += 1
        marker = line[cursor:end]
        close = line.find(marker, end)
        if close == -1:
            output.append(marker)
            cursor = end
            continue
        output.append(" " * (close + len(marker) - cursor))
        cursor = close + len(marker)
    return "".join(output)


def _without_code(text: str) -> str:
    output: list[str] = []
    fence_character: str | None = None
    fence_length = 0
    for line in text.splitlines(keepends=True):
        fence = re.match(r"^\s*(`{3,}|~{3,})", line)
        if fence_character is None and fence:
            marker = fence.group(1)
            fence_character = marker[0]
            fence_length = len(marker)
            output.append("\n" if line.endswith("\n") else "")
            continue
        if fence_character is not None:
            closing = re.match(rf"^\s*{re.escape(fence_character)}{{{fence_length},}}\s*$", line)
            if closing:
                fence_character = None
                fence_length = 0
            output.append("\n" if line.endswith("\n") else "")
            continue
        output.append(_strip_inline_code(line))
    return "".join(output)


def _destination(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("<"):
        closing = raw.find(">", 1)
        return raw[1:closing] if closing != -1 else ""

    escaped = False
    end = len(raw)
    for index, character in enumerate(raw):
        if escaped:
            escaped = False
            continue
        if character == "\\":
            escaped = True
            continue
        if character.isspace():
            end = index
            break
    return re.sub(r"\\([\\ ()])", r"\1", raw[:end])


def _markdown_links(text: str):
    text = _without_code(text)
    for match in LINK_OPEN.finditer(text):
        depth = 1
        escaped = False
        cursor = match.end()
        while cursor < len(text):
            character = text[cursor]
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0:
                    yield bool(match.group("image")), _destination(text[match.end() : cursor])
                    break
            cursor += 1


def validate_documentation_contract(
    root: Path, markdown_paths: tuple[Path, ...] | None = None
) -> list[str]:
    root = root.resolve()
    paths = markdown_paths if markdown_paths is not None else _workspace_markdown_paths(root)
    violations: list[str] = []

    for relative_source in paths:
        source = root / relative_source
        try:
            text = source.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            violations.append(f"{relative_source.as_posix()}: unreadable UTF-8 Markdown ({error})")
            continue

        for is_image, destination in _markdown_links(text):
            if (
                not destination
                or destination.startswith(("#", "/", "//"))
                or SCHEME.match(destination)
            ):
                continue
            path_text = unquote(destination.split("#", 1)[0].split("?", 1)[0])
            if not path_text:
                continue
            target = source.parent.joinpath(*PurePosixPath(path_text).parts).resolve()
            try:
                target.relative_to(root)
            except ValueError:
                violations.append(
                    f"{relative_source.as_posix()}: relative target escapes repository: {destination}"
                )
                continue
            if not target.exists():
                violations.append(
                    f"{relative_source.as_posix()}: relative target does not exist: {destination}"
                )
                continue
            if not is_image:
                continue
            if not target.is_file():
                violations.append(
                    f"{relative_source.as_posix()}: local image is not a file: {destination}"
                )
                continue
            try:
                with target.open("rb") as image_file:
                    has_content = bool(image_file.read(1))
                if target.stat().st_size == 0 or not has_content:
                    violations.append(
                        f"{relative_source.as_posix()}: local image is empty: {destination}"
                    )
            except OSError as error:
                violations.append(
                    f"{relative_source.as_posix()}: local image is unreadable: {destination} ({error})"
                )

    return violations


def test_tracked_markdown_links_and_images_are_valid():
    violations = validate_documentation_contract(ROOT)

    assert not violations, "\n".join(violations)


def test_contract_skips_remote_and_anchor_checks_but_reads_local_images(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "target.md").write_text("# Target\n", encoding="utf-8")
    image = tmp_path / "docs" / "pixel.bin"
    image.write_bytes(b"pixel")
    (tmp_path / "README.md").write_text(
        """[local](docs/target.md#target) [anchor](#target)
[remote](https://example.invalid/not-requested) ![pixel](docs/pixel.bin)
`[inline code](missing.md)`
```md
[fenced code](missing.md)
```
""",
        encoding="utf-8",
    )

    paths = (Path("README.md"), Path("docs/target.md"))
    assert validate_documentation_contract(tmp_path, paths) == []

    image.write_bytes(b"")
    violations = validate_documentation_contract(tmp_path, paths)
    assert any("local image is empty: docs/pixel.bin" in item for item in violations)


def test_default_workspace_scan_includes_untracked_markdown_and_skips_deleted(tmp_path):
    tracked = tmp_path / "tracked.md"
    tracked.write_text("# Tracked\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "tracked.md"], cwd=tmp_path, check=True)
    tracked.unlink()
    (tmp_path / "new.md").write_text("[broken](missing.md)\n", encoding="utf-8")

    violations = validate_documentation_contract(tmp_path)

    assert any("new.md: relative target does not exist: missing.md" in item for item in violations)
    assert not any("tracked.md: unreadable" in item for item in violations)


def test_stage_log_rows_are_machine_auditable_and_mark_screenshot_status():
    lines = STAGE_LOG.read_text(encoding="utf-8").splitlines()
    table = [line for line in lines if line.startswith("|")]

    def cells(line: str) -> list[str]:
        return [cell.strip() for cell in line.strip("|").split("|")]

    assert cells(table[0]) == [
        "Time (Asia/Shanghai)",
        "Stage / evidence level",
        "Action",
        "Demonstrated effect",
        "Evidence and limits",
        "Screenshot status",
    ]
    timestamps = []
    for line in table[2:]:
        row = cells(line)
        assert len(row) == 6
        timestamp = datetime.fromisoformat(row[0])
        assert timestamp.utcoffset() is not None
        timestamps.append(timestamp)
        assert "/" in row[1]
        assert all(len(value) >= 10 for value in row[2:5])
        assert (
            row[5] == "N/A — non-frontend stage"
            or ("hosted" in row[5].lower() and "pending" in row[5].lower())
            or row[5].startswith("[Hosted screenshot]")
        )
        if re.search(r"\b(browser|UI|frontend|interaction)\b", row[1], re.IGNORECASE):
            assert row[5] != "N/A — non-frontend stage"

    assert timestamps == sorted(timestamps)

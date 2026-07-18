# ruff: noqa: E731 -- T4 requires this disposable spike to stay under 20 code lines.
from pathlib import Path
from subprocess import check_output


root = Path(__file__).resolve().parents[2]
paths = check_output(["git", "-C", str(root), "ls-files", "-z"]).decode().rstrip("\0").split("\0")
prefixes = (".github/", "analyzer/", "anthill/", "docs/", "samples/", "scripts/", "static/", "tests/", "tracer/", "validation/")
root_files = {".dockerignore", ".gitattributes", ".gitignore", "CODE_OF_CONDUCT.md", "CONTRIBUTING.md", "Dockerfile", "LICENSE", "NOTICE", "README.md", "SECURITY.md", "compose.yaml", "package-lock.json", "package.json", "playwright.config.mjs", "playwright.visual.config.mjs", "pyproject.toml", "requirements-dev.txt", "requirements-visual.txt", "requirements.txt", "server.py"}
covered = lambda path: path in root_files or path.startswith(prefixes)
unmapped = [path for path in paths if not covered(path)]
high_risk = [".github/workflows/ci.yml", "package-lock.json", "Dockerfile", "playwright.config.mjs", "tests/visual/goldens/chromium-noble/overview.png"]
assert not unmapped and all(covered(path) for path in high_risk) and not covered("future/new-boundary.bin")
print(f"PASS tracked={len(paths)} high_risk={len(high_risk)} unknown=fallback-S2")

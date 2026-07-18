import json
from pathlib import Path

import server
from anthill import __version__


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "0.7.0"


def test_application_release_version_is_consistent():
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    package_lock = json.loads((ROOT / "package-lock.json").read_text(encoding="utf-8"))

    assert __version__ == EXPECTED_VERSION
    assert server.app.version == EXPECTED_VERSION
    assert package["version"] == EXPECTED_VERSION
    assert package_lock["version"] == EXPECTED_VERSION
    assert package_lock["packages"][""]["version"] == EXPECTED_VERSION
    assert f"ARG APP_VERSION={EXPECTED_VERSION}" in (ROOT / "Dockerfile").read_text(
        encoding="utf-8"
    )
    assert f"application `{EXPECTED_VERSION}`" in (ROOT / "README.md").read_text(
        encoding="utf-8"
    )
    assert f"Agent Anthill `{EXPECTED_VERSION}`" in (
        ROOT / "docs/PROGRESS.md"
    ).read_text(encoding="utf-8")

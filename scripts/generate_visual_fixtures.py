"""Regenerate deterministic, synthetic browser-visual fixtures."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from anthill.demo import build_demo_events  # noqa: E402


OUTPUT = ROOT / "tests" / "fixtures" / "visual_rich_v1.json"
BASE_TIME = datetime(2026, 7, 18, 0, 0, tzinfo=timezone.utc)


def build_fixture() -> dict:
    run_id = "visual-rich-v1"
    records = []
    for index, event in enumerate(build_demo_events(run_id)):
        occurred_at = BASE_TIME + timedelta(milliseconds=index * 260)
        clock = event.clock.model_copy(
            update={"occurred_at": occurred_at, "observed_at": BASE_TIME}
        )
        records.append(
            event.model_copy(update={"clock": clock}).model_dump(
                mode="json", exclude_none=True
            )
        )
    canonical = json.dumps(
        records, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        "fixture_version": "1.0.0",
        "run_id": run_id,
        "synthetic": True,
        "source": "anthill.demo.build_demo_events",
        "license": "Apache-2.0",
        "events_sha256": hashlib.sha256(canonical).hexdigest(),
        "events": records,
    }


if __name__ == "__main__":
    OUTPUT.write_text(
        json.dumps(build_fixture(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUTPUT.relative_to(ROOT)}")

import hashlib
import json
from pathlib import Path

from anthill.schema import AgentRuntimeEvent


FIXTURE = Path(__file__).parent / "fixtures" / "visual_rich_v1.json"


def test_rich_visual_fixture_is_stable_valid_and_explicitly_synthetic():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    canonical = json.dumps(
        payload["events"],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    events = [AgentRuntimeEvent.model_validate(event) for event in payload["events"]]

    assert payload["fixture_version"] == "1.0.0"
    assert payload["run_id"] == "visual-rich-v1"
    assert payload["synthetic"] is True
    assert payload["license"] == "Apache-2.0"
    assert hashlib.sha256(canonical).hexdigest() == payload["events_sha256"]
    assert len(events) == 44
    assert all(event.run_id == payload["run_id"] for event in events)
    assert all(event.payload.get("synthetic") is True for event in events)
    assert events[0].clock.observed_at.isoformat() == "2026-07-18T00:00:00+00:00"

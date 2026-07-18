import json
from pathlib import Path

from anthill.adapters.otlp import otlp_json_to_events
from anthill.projections import project_world

payload = json.loads((Path(__file__).parents[2] / "tests/fixtures/otlp_openinference.json").read_text())
events = otlp_json_to_events(payload, run_id="spike-measurements")
stamped, previous = [], None
for seq, event in enumerate(events):
    event = event.with_ingest_metadata(ingest_seq=seq, previous_event_hash=previous)
    stamped.append(event)
    previous = event.integrity.event_hash
world = project_world(stamped, run_id="spike-measurements")
assert next(e for e in events if e.event_type == "model.request.dispatched").measurements == {}
assert world.totals["input_tokens"] == 128 and world.totals["output_tokens"] == 42
print("PASS: terminal-owned OTLP usage projects once as 128 input / 42 output")

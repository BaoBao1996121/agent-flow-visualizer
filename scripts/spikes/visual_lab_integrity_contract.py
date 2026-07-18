from pathlib import Path
from tempfile import TemporaryDirectory

from anthill.demo import build_demo_events
from anthill.store import JsonlEventStore

with TemporaryDirectory() as directory:
    store = JsonlEventStore(Path(directory))
    stored = store.append_many(build_demo_events("visual-lab-integrity"))
    result = store.verify_run("visual-lab-integrity")
assert result["valid"] is True
assert result["event_count"] == len(stored) == 44
print("PASS", result["valid"], result["event_count"])

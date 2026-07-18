from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory

from anthill.demo import build_demo_events
from anthill.projections.world import project_world
from anthill.store import JsonlEventStore

with TemporaryDirectory() as directory:
    store = JsonlEventStore(Path(directory))
    events = store.append_many(build_demo_events("visual-lab-density"))
world = project_world(events, run_id="visual-lab-density")
counts = Counter(entity.zone for entity in world.entities.values())
assert max(counts.values()) <= 4
print("PASS", dict(sorted(counts.items())))

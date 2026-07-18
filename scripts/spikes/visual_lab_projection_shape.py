from pathlib import Path
from tempfile import TemporaryDirectory

from anthill.demo import build_demo_events
from anthill.projections.world import project_world
from anthill.store import JsonlEventStore


with TemporaryDirectory() as directory:
    store = JsonlEventStore(Path(directory))
    events = store.append_many(build_demo_events("visual-lab-shape"))
    world = project_world(events, run_id="visual-lab-shape")
required = {"id", "kind", "name", "zone", "status", "truth", "last_event_id", "event_count"}
assert len(world.entities) == 12
assert all(required <= set(entity.model_dump()) for entity in world.entities.values())
assert all(entity.last_event_id for entity in world.entities.values())
print("PASS", len(world.entities), sorted(required))

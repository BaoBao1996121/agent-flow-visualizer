from tempfile import TemporaryDirectory

from anthill.demo import build_demo_events
from anthill.projections import project_world
from anthill.store import JsonlEventStore

with TemporaryDirectory() as directory:
    store = JsonlEventStore(directory)
    store.append_many(build_demo_events("spike-mirror"))
    world = project_world(store.read_run("spike-mirror"), run_id="spike-mirror")
required = {"id", "kind", "name", "zone", "status", "truth", "event_count", "last_event_id"}
assert world.entities and all(required <= entity.model_dump().keys() for entity in world.entities.values())
assert all(entity.last_event_id for entity in world.entities.values())
print(f"PASS: {len(world.entities)} entities expose stable semantic-mirror fields")

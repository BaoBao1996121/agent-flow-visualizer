from pathlib import Path
from tempfile import TemporaryDirectory
from anthill.schema import AgentRuntimeEvent, EventSource, Evidence
from anthill.store import JsonlEventStore

SOURCE = EventSource(adapter="spike", fidelity="native")
EVIDENCE = Evidence(level="observed", confidence=1)
def event(name, kind, payload=None):
    return AgentRuntimeEvent(event_id=name, event_type=kind, run_id="spike-run", source=SOURCE, evidence=EVIDENCE, payload=payload or {})

with TemporaryDirectory() as root:
    store = JsonlEventStore(root)
    store.append_many([event("start", "run.started"), event("done", "run.completed", {"status": "success"})])
    next(Path(root).glob("*/manifest.json")).write_text("{broken", encoding="utf-8")
    store.append(event("artifact", "artifact.created"))
    assert store.get_manifest("spike-run")["run_status"] == "completed"
print("PASS: torn manifest is repaired from the complete ledger")

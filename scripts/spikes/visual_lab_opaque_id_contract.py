from anthill.demo import build_demo_events
from anthill.schema import AgentRuntimeEvent

payload = build_demo_events("visual-lab-opaque")[0].model_dump()
payload["event_id"] = " event  id "
payload["subject"] = {"kind": "agent", "id": " agent  id ", "name": "Opaque Agent"}
event = AgentRuntimeEvent.model_validate(payload)
assert event.event_id == " event  id "
assert event.subject and event.subject.id == " agent  id "
print("PASS", repr(event.event_id), repr(event.subject.id))

from anthill.demo import build_demo_events


events = build_demo_events("visual-lab-spike")
expected = {24: "error.raised", 30: "error.recovered", 37: "compaction.completed", 43: "run.completed"}
assert len(events) == 44
assert {index: events[index].event_type for index in expected} == expected
print("PASS", len(events), expected)

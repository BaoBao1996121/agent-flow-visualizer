from anthill.run_lifecycle import transition_run_status

status = "unknown"
for event_type, payload in [
    ("run.started", {}),
    ("run.completed", {"status": "success"}),
    ("artifact.created", {}),
]:
    status = transition_run_status(status, event_type, payload)

assert status == "completed"
print("PASS: terminal lifecycle survives trailing non-lifecycle events")

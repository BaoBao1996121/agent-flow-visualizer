# Assumption validation log

This file records bounded spikes that gate changes large enough to depend on
unverified external or architectural assumptions.

## 2026-07-16 — AG-UI semantic adapter

Sources checked before the spike:

- AG-UI event reference: <https://docs.ag-ui.com/concepts/events>
- AG-UI SDK event types: <https://docs.ag-ui.com/sdk/js/core/events>
- AG-UI serialization and lineage: <https://docs.ag-ui.com/concepts/serialization>

| Assumption | Validation | Result |
|---|---|---|
| The canonical schema accepts renderer-independent, namespaced AG-UI projection events and correlation IDs. | Constructed and validated an `agent.message.started` event with a `message` subject through `AgentRuntimeEvent`. | PASS. The first spike invocation omitted the required source fidelity and failed in the test harness; the corrected schema-complete invocation passed. |
| AG-UI's explicit `messageId`, `toolCallId`, `entityId`, and `stepName` data is sufficient for the fixture's causal/correlation links without temporal adjacency inference. | Checked every message/activity/reasoning reference against an explicit stream start and every tool reference against `TOOL_CALL_START`. | PASS for the golden fixture. Out-of-order and malformed streams must still remain unlinked rather than guessed. |
| Metadata-only conversion can preserve structural counts/paths while excluding content-bearing fixture values. | Serialized every canonical event from the fixture and searched for all `SECRET_` sentinels. | PASS. Plaintext remains an explicit opt-in and requires separate tests. |

These results validate implementation assumptions, not full protocol
conformance. AG-UI draft events and future protocol versions remain subject to
change and are retained with their source type/version for reprocessing.

## 2026-07-16 — instrumentation visibility projection

| Assumption | Validation | Result |
|---|---|---|
| Historical `WorldState` contains enough authoritative aggregate data to build a cursor-specific visibility view. | Projected the 44-event exhibit through the ledger and proved `sum(event_type_counts) == event_count == 44`. | PASS. The projection must use the requested cursor state, never the head manifest. |
| Current built-in adapters have stable identities suitable for a versioned capability registry. | Normalized demo, AG-UI, and OTLP fixtures and checked their adapter names against all built-in adapter identities. | PASS. Unregistered third-party adapters must be shown as unregistered, not assigned guessed capabilities. |
| A bounded domain taxonomy covers every stable core event family. | Compared every `CoreEventType` prefix with the proposed domain set. | PASS for protocol `0.1.0`; extension families remain visible as extensions rather than being silently coerced. |

The visibility model deliberately has no aggregate “coverage percentage.” It
distinguishes `observed`, `observable_not_seen`, and
`outside_adapter_contract`; none of those labels proves that an unobserved
operation did or did not happen.

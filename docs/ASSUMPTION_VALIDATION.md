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

## 2026-07-17 — LangGraph StreamPart v2 adapter

Sources checked before the spike:

- LangGraph streaming: <https://docs.langchain.com/oss/python/langgraph/streaming>
- Official `StreamPart`, `TaskPayload`, and `CheckpointPayload` definitions: <https://github.com/langchain-ai/langgraph/blob/main/libs/langgraph/langgraph/types.py>

| Assumption | Validation | Result |
|---|---|---|
| LangGraph 1.x has a usable discriminated StreamPart v2 boundary from `1.1.0`. | Ran the same real `StateGraph` under isolated LangGraph `1.1.0` and `1.2.9`; both emitted dictionary parts with `type`, `ns`, and `data` across all six supported modes. | PASS for both tested versions; the configured supported lane is `>=1.2,<2`, and future releases remain a compatibility boundary. |
| Canonical events can preserve LangGraph task, state, message, checkpoint, custom, and interrupt signals without changing the envelope. | Normalized real and golden parts into core events plus `langgraph.custom`/`langgraph.interrupt.reobserved`, then validated every event through `AgentRuntimeEvent`. | PASS. Task interrupt lifecycle, first observation, repeated observation, and checkpoint snapshot remain distinct facts. |
| Offline normalization need not import LangGraph. | Parsed the fixture under `python -S` using only the standard library and verified explicit checkpoint IDs. | PASS for the JSON boundary. |
| Capture completion can be represented without inventing an outcome. | Declared a stream complete without `runStatus` and checked the terminal event. | PASS. The terminal status is `completed`; success/failure/interruption require an explicit status. |
| Unbounded external interrupt identifiers can cross the adapter without violating canonical limits or leaking a duplicate. | Imported 3,000+ character interrupt IDs through both state and task-result paths, then queried every persisted event. | PASS. Every base/supplemental reference uses the same deterministic hash, source length is recorded, the original ID is absent, and the API returns `201` rather than `500`. |
| Malformed runtime objects fail through the adapter boundary. | Supplied one object whose `model_dump()` raises and one whose dump returns itself. | PASS. Both become `LangGraphImportError`; neither a runtime exception nor recursion failure escapes. |
| Official payload shapes can be enforced without importing LangGraph into the application. | Compared 1.1.0/1.2.9 runtime definitions and exercised invalid task-result branches, checkpoint tasks, messages, debug wrappers, interrupts, values, token usage, and cross-source identities. | PASS for the tested boundary. Malformed input fails as a controlled import error rather than being guessed. |
| Historical checkpoint observations can coexist with a live approval without corrupting current state. | Ran RED/GREEN reducer probes for live interrupt followed by checkpoint snapshot, snapshot-only interrupt, reobservation, and historical task error. | PASS under reducer `0.2.0`; live waiting state wins over later historical evidence, while snapshot-only evidence remains `snapshot`. |

The workstation's pre-existing LangGraph `1.0.4` returned the legacy tuple shape
even when called with `version="v2"`, confirming the lower-bound failure mode.
Isolated `1.1.0` and `1.2.9` environments emitted the documented dictionary
boundary and passed metadata-only normalization. The adapter rejects legacy
tuples rather than silently mis-mapping them. This proves the tested runtime
boundary, not every future `1.x` release. The optional compatibility matrix is
configured to keep that claim executable, but no hosted matrix result exists
yet.

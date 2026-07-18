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
| A bounded domain taxonomy covers every stable core event family. | Compared every `CoreEventType` prefix with the proposed domain set. | PASS originally under protocol `0.1.0`. Protocol `0.2.0` changes new-write run-ID validation, not the `CoreEventType` families; extension families remain visible rather than being silently coerced. |

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
| Historical checkpoint observations can coexist with a live approval without corrupting current state. | Ran RED/GREEN reducer probes for live interrupt followed by checkpoint snapshot, snapshot-only interrupt, reobservation, and historical task error. | PASS originally under reducer `0.2.0`; reducer `0.3.0` retains this behavior while moving explicit run-lifecycle transitions into the shared fold. Snapshots remain isolated by reducer version. |

The workstation's pre-existing LangGraph `1.0.4` returned the legacy tuple shape
even when called with `version="v2"`, confirming the lower-bound failure mode.
Isolated `1.1.0` and `1.2.9` environments emitted the documented dictionary
boundary and passed metadata-only normalization. The adapter rejects legacy
tuples rather than silently mis-mapping them. This proves the tested runtime
boundary, not every future `1.x` release. The optional compatibility matrix is
configured to keep that claim executable. The first hosted matrix ran in
[GitHub Actions run 29570924390](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29570924390): both LangGraph jobs reached test execution but were red because the same shared deep-NDJSON error-classification assertion failed. The corrected `1.1.0` floor and supported-1.x jobs both passed in [run 29629916726](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29629916726).

The current NDJSON guard rejects structural nesting deeper than 256 before
decoder behavior can diverge across supported Python versions, while ignoring
brackets inside strings. The value 256 is an initial conservative validation
limit, not a benchmark result; body, structure, cardinality, emitted-event, and
backpressure budgets still require calibration before untrusted hosted use.

## 2026-07-17 — Phase -1 inspector tab accessibility

Three bounded spikes gate the tab ARIA and keyboard slice before further changes to the already-large frontend bundle.

| Assumption | Validation | Result |
|---|---|---|
| Every inspector tab has one stable panel target. | Parsed `static/anthill.html` and compared the four `data-tab` values with the four `*-panel` IDs. | PASS after correcting the spike's first over-specific assumption that panels were `<section>` elements; the actual element tag is not part of the contract. |
| A tab-local arrow-key handler can avoid the page-level timeline shortcut. | Dispatched `ArrowRight` in real Chromium with a bubbling window listener and a tab listener that calls `stopPropagation()`. | PASS. The window listener received zero events. |
| Native `hidden` provides both visual and accessibility hiding for inactive panels. | Rendered one visible and one hidden `role="tabpanel"` in real Chromium and checked `isHidden()` plus the default role locator. | PASS. The hidden panel was not exposed by the role query. |

Executable evidence:

- `node scripts/spikes/phase1_tab_map.mjs`
- `node scripts/spikes/phase1_tab_stop_propagation.mjs`
- `node scripts/spikes/phase1_hidden_panel.mjs`

All three spike files are 14 lines or fewer. These results validate the browser primitives and current tab/panel topology, not the completed application behavior; Playwright still supplies the RED/GREEN acceptance proof.

## 2026-07-17 — run identity and lifecycle foundations

Three bounded spikes gated the shared lifecycle and selector identity work.

| Assumption | Validation | Result |
|---|---|---|
| Explicit lifecycle folding remains authoritative when non-lifecycle events trail a terminal event. | Folded `run.started`, explicit successful `run.completed`, then `artifact.created` through the shared transition helper. | PASS. The final status remains `completed`; manifest HEAD and reducer `0.3.0` use the same transition semantics. |
| A torn manifest can be repaired without using its stale last event as lifecycle truth. | Persisted start/completion, replaced `manifest.json` with malformed JSON, appended an artifact, and read the rebuilt manifest. | PASS. Reconstruction folds the complete ledger and restores `completed`. |
| Selector ingest timestamps can be deterministic without treating an unzoned value as UTC. | Normalized an explicit `+08:00` value to UTC and tested the zone suffix guard against the same wall time without a zone. | PASS. The aware value becomes `2026-07-17 08:30Z`; the unzoned value is rejected by the guard. |

Executable evidence:

- `python -m scripts.spikes.run_identity_lifecycle`
- `python -m scripts.spikes.run_identity_manifest_repair`
- `node scripts/spikes/run_identity_utc.mjs`

These spikes establish bounded primitives. Lifecycle aliases, missing facts,
short-ID collisions, hostile display text, stale response ordering, and the
ledger-HEAD-versus-history-cursor contract are covered by regression tests, not
by these three spikes alone.

## 2026-07-17 — JSONL discovery and compatibility foundations

Three bounded spikes gated the large store refactor.

| Assumption | Validation | Result |
|---|---|---|
| A bounded tail read can find the last non-empty JSONL record despite trailing blank lines. | Memory-mapped a two-record temporary ledger with trailing blank lines and decoded the last non-empty slice. | PASS. The returned sequence was `1`; the primitive supports lightweight HEAD reconciliation, not full integrity verification. |
| One re-entrant lock can protect nested same-run operations while serializing another thread. | Held an `RLock`, started a second thread, and nested the same lock inside the writer after release. | PASS. The writer could not finish while the outer holder owned the lock and completed after release. |
| Legacy validation can be restricted to explicit storage reads without weakening new input. | Parsed an edge-whitespace JSON value with Pydantic validation context, then validated the same shape without context. | PASS after correcting the first attempt to handle `ValidationInfo.context is None` with `info.context or {}`. Legacy storage input is readable; new input stays strict. |

The validation-context spike proves isolation of the compatibility switch, not
the complete production validator. Protocol `0.2.0` regression tests additionally
reject Unicode `Cc`/`Cf`, `/`, `\`, `?`, `#`, `%`, and the exact dot segments
`.` and `..`, so a newly written run ID is one addressable API path segment.
Store regressions, separate from the three spikes, also fix the discovery
classification boundary: given a valid checksummed manifest with a positive
event count, a shortened, empty, or missing ledger is reported as
`truncated_ledger`, and a missing ledger is not recreated.

Executable evidence:

- `python scripts/spikes/store_tail_boundary.py`
- `python scripts/spikes/store_rlock_serialization.py`
- `python scripts/spikes/store_validation_context.py`

The resulting process-local append index is keyed by an unkeyed SHA-256 digest
of the complete ledger bytes. Every append scans those bytes before deciding
whether the cached index is reusable; only first access or changed content
performs full JSON, sequence, duplicate-ID, and event-hash-chain validation.
That statement is specific to append-index reuse: a missing, malformed,
checksum-invalid, or stale-behind manifest may separately trigger a complete
ledger rebuild. A checksum-valid manifest ahead of the ledger is a
`truncated_ledger` anchor, while an equal-count manifest with a different HEAD
hash is a `divergent_ledger` anchor; both are quarantined rather than rebuilt.
The digest is refreshed after append. It is a change detector, not a MAC or
authenticity proof. Repeated single-event appends still have cumulative `O(k²)`
byte-scanning cost even when unchanged-ledger appends avoid repeated JSON
parsing. The per-run integrity endpoint remains the explicit full-verification
boundary.

# Agent Runtime Event protocol 0.2

## Design goals

- Preserve source truth before semantic interpretation.
- Support concurrent multi-Agent runs as causal DAGs.
- Keep the envelope stable while allowing namespaced extensions.
- Make privacy policy and evidence quality queryable.
- Make a run replayable without relying on UI state.
- Align with OpenTelemetry/OpenInference without freezing their evolving vocabulary into the core.

The normative Python model is [`anthill/schema.py`](../anthill/schema.py).

The current write schema is `0.2.0`. It rejects a `run_id` with leading or
trailing whitespace or Unicode control/format characters in categories `Cc`
and `Cf`. It also rejects `/`, `\`, `?`, `#`, `%`, and the exact dot segments
`.` and `..`, so every new run ID is one stable API path segment. The JSONL
store may read an existing `0.1.0` event only through an explicit storage-only
compatibility context. That context is never enabled for new API input or
append operations, and an unsafe legacy run ID is quarantined from normal run
discovery.

`event_id` has a different contract: it is an opaque 1–256 character
idempotency key and may contain exact dot segments or URL-reserved characters.
Canonical event-detail and causal HTTP lookups therefore carry it in the
`event_id` query parameter; path-segment lookup is deprecated compatibility.
Opaque means the server does not interpret the value. It does not mean the
value is anonymous, secret, or safe for URL logs.

## Envelope

| Field | Meaning |
|---|---|
| `schema_version` | Semantic version of this envelope |
| `event_id` | Opaque 1–256 character idempotency identity; ordering must not depend on it; canonical HTTP lookup uses a query parameter |
| `event_type` | Lowercase namespace such as `tool.execution.started` |
| `run_id` | Required, display-stable API path segment; protocol `0.2.0` forbids edge whitespace, Unicode `Cc`/`Cf`, `/`, `\`, `?`, `#`, `%`, `.` and `..` on new writes |
| `thread_id`, `session_id`, `project_id`, `task_id`, `agent_id` | Optional scopes |
| `trace_id`, `span_id`, `parent_span_id` | Distributed trace structure |
| `causation_id` | Direct causing event when explicitly known |
| `correlation_id` | Non-causal grouping identity |
| `links` | Typed cross-event/run/span relationships |
| `clock` | Occurrence, observation, monotonic, source, and ingest order |
| `source` | Adapter/framework/version/fidelity and raw reference |
| `subject` | Entity the event is about |
| `evidence` | Truth level, confidence, refs, derivation, explanation |
| `summary` | Short safe description, not private reasoning |
| `payload` | Event-specific metadata/content under privacy policy |
| `measurements` | Source-preserved scalar telemetry; aggregation requires the versioned semantics extension below |
| `artifacts` | URI/hash/type/size references for large content |
| `privacy` | Capture mode, sensitive-data flag, redacted fields, retention |
| `extensions` | Namespaced adapter/project fields |
| `integrity` | Store-assigned previous hash and event hash |

Unknown top-level keys are rejected. Unknown event types are preserved and rendered in Unknown Fog until a projector understands them.

The OTLP JSON importer stores safe unmapped attributes under `extensions.otel.*`, records `mapped` source fidelity, and removes known content-bearing attributes unless plaintext capture is explicitly enabled.

## Truth levels vs source fidelity

These are related but not identical.

### Evidence level

- `observed`: captured during execution by an appropriate source.
- `declared`: explicit in source, configuration, or a labelled fixture.
- `inferred`: derived by a fallible classifier or heuristic; confidence must be below `1.0`.
- `counterfactual_verified`: supported by a recorded intervention and downstream rerun.

### Source fidelity

- `native`: emitted at the original semantic boundary.
- `mapped`: deterministically translated from another explicit convention.
- `inferred`: reconstructed from indirect signals.

An OTLP span deterministically mapped into a model event can be `observed` evidence with `mapped` source fidelity. An AST heuristic may be `inferred` evidence with `inferred` fidelity.

## Ordering

Do not sort only by wall-clock time.

1. The store assigns contiguous `ingest_seq` inside a run.
2. `source_seq` preserves source order when provided.
3. `monotonic_ns` helps order events from the same process.
4. `occurred_at` and `observed_at` remain useful for latency and clock-skew analysis.
5. Causality is represented separately.

## Integrity boundary

Stored events form an unkeyed SHA-256 chain over canonical event content and the
previous event hash. Verification recalculates every event hash, checks the
previous-hash link, contiguous `ingest_seq`, and duplicate IDs. This detects
accidental or uncoordinated ledger changes; it is not a MAC, signature, or proof
against an actor that can rewrite the ledger and all of its hashes. The
process-local whole-ledger SHA-256 used to decide whether a validated append
index can be reused is likewise an unkeyed change detector, not an
authentication mechanism.

A valid checksummed manifest that records a non-empty prior head makes a
shortened, empty, or missing `events.jsonl` the same loss-of-history condition:
`truncated_ledger`. Discovery must not silently treat any of those cases as a
new empty run or recreate a missing ledger. A malformed or checksum-invalid
manifest remains a disposable cache and cannot establish that prior head.

## Core event families

The complete enum is in `CoreEventType`. Important groups are:

- Run/Agent/Task: lifecycle, state, plan, and step.
- Model: prepared, dispatched, chunks, completed, cache, retry, fallback, failure.
- Tool: request, args, approval, execution, progress, retry, side-effect commit.
- Retrieval: query, rewrite, search, candidates, rerank, selected documents.
- Memory: search/read/hit/miss/write/update/delete/consolidate/decay/evict/conflict.
- Context: assembly, item add/remove/truncate, budget, overflow, policy.
- Compaction: trigger/start/summary/items replaced/complete/fail.
- Handoff: proposal/accept/reject/start/complete.
- Checkpoint: create/restore/fork/commit/invalidate.
- Error: raised/caught/retry/recovered/fatal/timeout/cancelled.
- Usage/cost/budget, artifacts, human interrupts, manifests, policies.
- Code declarations/relations/calls for the Source Archive.

## Compaction example

```json
{
  "schema_version": "0.2.0",
  "event_id": "evt-compact-done",
  "event_type": "compaction.completed",
  "run_id": "run-42",
  "span_id": "compact-7",
  "causation_id": "evt-items-replaced",
  "source": {
    "adapter": "framework-native-hook",
    "adapter_version": "1.2.0",
    "framework": "example",
    "framework_version": "4.0.0",
    "fidelity": "native"
  },
  "subject": {"kind": "compaction", "id": "compact-7"},
  "evidence": {"level": "observed", "confidence": 1.0},
  "payload": {
    "policy": "evidence-preserving-summary",
    "trigger": "context_overflow",
    "tokens_before": 8460,
    "tokens_after": 3920,
    "lossy": true,
    "summary_hash": "sha256:...",
    "kept_refs": ["ctx-system", "artifact-log-slice"],
    "removed_refs": ["ctx-turn-1", "ctx-raw-log-lines"]
  },
  "privacy": {"content": "metadata_only"}
}
```

The summary text itself can remain encrypted or absent. The lineage and hashes still make the mechanism inspectable.

## Measurement conventions

`measurements` preserves source scalar fields, but a numeric field is not safe to
sum merely because its key contains `tokens`, `duration`, or `cost`. Adapters can
report the same cumulative usage at several lifecycle events, and parent/child
span durations overlap. The reducer therefore promotes a value only when the
same event carries `extensions["anthill.measurements"]` schema `1.0.0`.

Each item binds one raw measurement key to:

| Field | Contract |
|---|---|
| `aggregate_key` | One key in the closed registry published by `GET /api/anthill/schema` |
| `unit` / `scope` / `aggregation` | Must exactly match that registry entry |
| `temporality` | `delta`, `cumulative`, or `unknown` |
| `owner_id` | Stable identity of the model call, tool call, code call, compaction, or run that owns the sample |
| `basis` / `estimated` | Required together for `model_call.cost_usd`; the basis identifies the pricing source/version |

`owner_id` and pricing `basis` reject surrounding whitespace plus Unicode
control/format characters. These values are rendered as operational identity and
cost evidence, so accepting bidi or control-text spoofing would weaken the truth
contract even when HTML escaping is correct.

The initial registry contains model input/output/cached/explicit-total tokens,
model/tool/code/compaction scoped duration, model cost, and run elapsed time.
There is deliberately no generic `duration_ms_sum`: nested model, tool, and run
time cannot be added into one latency number without double-counting.

Arithmetic is owner-aware:

- `delta` samples add within their owner;
- `cumulative` samples replace the prior contribution and a decrease makes the
  aggregate ambiguous;
- one `unknown` sample may represent its owner, but a repeated sample for the
  same owner is ambiguous rather than guessed as delta or cumulative;
- a temporality change for one owner is a conflict;
- `latest` is available only with one owner; multiple owners are ambiguous
  rather than silently choosing the last arrival;
- non-finite, negative, non-numeric, missing-semantics, and invalid-semantics
  samples stay visible as unaggregated diagnostics and never enter Meter or
  numeric Compare. Arithmetic that overflows after otherwise finite inputs is
  also persisted as an ambiguous conflict.

`model_call.total_tokens` from a source remains an explicit aggregate. The world
also exposes a separate `calculated_measurements["model_call.total_tokens"]`
view when safe input and output aggregates are both available. It is labelled
`aggregation="derived"`; a mismatch with an explicit total makes that calculated
view ambiguous instead of overwriting either value.

Cost comparison additionally requires one complete basis and one consistent
`estimated` value on each side, with both sides equal. Otherwise Compare returns
`NOT COMPARABLE` and a reason. This extension adds no top-level event field, so
legacy event hash canonicalization remains unchanged.

## Privacy

`metadata_only` is the default. `plaintext_opt_in` must be a conscious caller choice. `redacted` identifies removed fields; `encrypted` requires an external key-management and access-control implementation.

Never place credentials in summary, identifiers, or source URIs. A field-level redactor should run before persistence, not only before rendering.

## Versioning

- Patch: clarifications and backward-compatible validators.
- Minor: optional fields and new core event types.
- Major: incompatible envelope meaning or required fields.

Protocol `0.2.0` adds stricter validation for newly written run identities while
retaining the explicit storage-only `0.1.0` read path above. Adapters declare
their own version. Projectors declare `reducer_version`; the current world
reducer is `0.4.0`. Snapshots are isolated by reducer version, and reprojection
after an upgrade must never rewrite the original ledger.

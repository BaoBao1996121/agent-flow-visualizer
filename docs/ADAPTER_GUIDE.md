# Adapter guide

An adapter is a trust boundary. Its job is to normalize evidence, not to make the UI exciting.

## Minimum adapter contract

Every adapter must provide:

1. a stable adapter name and semantic version;
2. source framework/version and semantic-convention version when available;
3. `native`, `mapped`, or `inferred` source fidelity;
4. idempotent event IDs for re-imported source records;
5. source ordering, clocks, trace/span identity, and explicit causal links when known;
6. metadata-only behavior by default;
7. a golden trace fixture and conformance tests;
8. a documented instrumentation-coverage map and known blind spots.

## Preserve facts and interpretations separately

Bad:

```text
Function name contains “search” → store observed retrieval event
```

Good:

```text
code.call.started       evidence=observed confidence=1.0
retrieval.search.started evidence=inferred confidence=0.72 derived_from=<code event>
```

The observed call survives if classification improves later.

## Identity and idempotency

Prefer the source event/span ID. If none exists, derive an opaque stable ID from immutable source identity—not from mutable display text. The Python adapters use a SHA-256-based `stable_id` helper.

Never use timestamp alone as an event ID. Retries, concurrent events, and clock skew make collisions likely.

## Causality

Set `causation_id` only when the source provides a real dependency or the adapter has a defensible deterministic mapping. Do not connect consecutive log lines merely because they are adjacent.

Use links for handoff, retrieval source, replacement lineage, cross-run fork, and other non-tree relationships.

## Privacy checklist

- Are prompt, arguments, returns, exception text, and memory values omitted by default?
- Are secret-bearing identifiers and URIs redacted?
- Can large content become an artifact hash/reference?
- Does the fixture contain only synthetic or explicitly licensed data?
- Does `privacy.content` match what is actually stored?

## Golden fixture structure

A framework contribution should include:

```text
fixtures/<adapter>/
  source-event.jsonl
  canonical-event.jsonl
  expected-world.json
  README.md              # framework version, task, coverage, blind spots
```

Tests should prove:

- stable IDs and deterministic mapping;
- event schema conformance;
- evidence/fidelity correctness;
- default content omission;
- causal and span links;
- known unknowns remain unmapped;
- world projection at key sequences;
- no secret-shaped fixture values.

## Current Python examples

- `anthill/adapters/python_ast.py` separates declared entities from inferred semantic classifications.
- `anthill/adapters/python_trace.py` converts `sys.settrace` calls/returns/exceptions into observed code events and optional inferred companion events.

The Python tracer sees only code in the target project directory and does not automatically capture subprocesses, other processes, GPU work, remote model internals, or every framework semantic boundary. These are coverage limits, not absence proofs.

## Protocol adapters

### OpenTelemetry / OpenInference

- The current `anthill/adapters/otlp.py` importer accepts official OTLP JSON `resourceSpans → scopeSpans → spans` and maps OpenInference kinds plus OTel GenAI operations.
- store input convention and exact version;
- map span kind/attributes deterministically;
- retain unmapped attributes under a namespaced extension;
- handle development-status GenAI conventions through a locked adapter, never as the internal schema.

Current limit: this is explicit JSON import, not an OTLP protobuf receiver or continuously batched collector. It emits run boundaries for one imported payload and therefore rejects an idempotent re-import into the same run.

### AG-UI

- `anthill/adapters/agui.py` accepts an event object, event array, envelope, or NDJSON stream through `POST /api/anthill/import/agui`;
- run, step, text-message, tool-call, shared-state, activity, and public reasoning-summary boundaries map deterministically into namespaced canonical events;
- `messageId`, `toolCallId`, `entityId`, and `stepName` form opaque correlation IDs and explicit lifecycle causation. Missing IDs remain unlinked; event adjacency is never promoted to causality;
- `parentRunId` becomes a `derived_from` run link;
- state values, message content, tool arguments/results, custom/raw payloads, error text, and encrypted reasoning values are metadata-only by default;
- the source event type, field names, input protocol version, and raw-event reference remain available for reprocessing after an adapter upgrade.

The mapping follows the current official [AG-UI event reference](https://docs.ag-ui.com/concepts/events) and [serialization model](https://docs.ag-ui.com/concepts/serialization). Deprecated `THINKING_*` events are accepted as reasoning aliases, while draft/new event types survive as `agui.event.observed` instead of being discarded.

Current limit: this is offline JSON/NDJSON import. It is not yet an AG-UI HTTP/SSE client, and metadata-only state deltas preserve RFC 6902 operation/path structure rather than reconstructing private state values.

### Native framework hooks

Native hooks are required to make context item selection, memory consolidation, compaction, checkpoint, or ownership transitions observable when generic spans cannot see them.

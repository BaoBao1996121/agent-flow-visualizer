# Verification record

Last verified: 2026-07-17 (Asia/Shanghai).

This is a dated evidence record, not a permanent quality claim. Hosted results
must be linked from the repository's current Actions page after publication.

## Current-code release gates

| Boundary | Command / method | Result |
|---|---|---|
| Core Python suite | `python -m pytest -q` | 204 passed; one optional real-runtime test skipped in the ambient environment because its installed LangGraph is `1.0.4` |
| World projection contract | API, snapshot, and reducer regression assertions | Reducer `0.2.0`; cached snapshots remain isolated by reducer version |
| Python lint | `python -m ruff check --no-cache .` | PASS |
| Changed Python formatting | `python -m ruff format --check` over every Python file changed for `0.6.0` | PASS; unrelated baseline files remain outside this release diff |
| Frontend syntax | `node --check` over `anthill.js`, `app.js`, `graph.js`, and `simulation.js` | PASS for all four files |
| Structured fixtures/config | Python JSON parsing for both LangGraph and canonical-ingest fixtures; PyYAML parse for `.github/workflows/ci.yml` | PASS |
| Patch hygiene | `git diff --check` | PASS |

The optional runtime test is not counted among the 204 passes. Its two
supported runtime executions are recorded separately below.

## LangGraph StreamPart v2 compatibility

The exact current adapter and strict shape validator were exercised through
`test_real_langgraph_v2_stream_is_accepted_without_content_leakage` in two
isolated environments:

| LangGraph | Real source | Modes | Result |
|---|---|---|---|
| `1.1.0` compatibility floor | A compiled `StateGraph` | `tasks`, `messages`, `updates`, `values`, `checkpoints`, `custom` | PASS |
| `1.2.9` current tested 1.x | A compiled `StateGraph` | The same six modes | PASS |

Both runs produced the discriminated `{type, ns, data}` StreamPart v2 boundary,
mapped every requested mode to canonical events, and kept persisted content
metadata-only. The ambient `1.0.4` runtime produced the legacy tuple boundary and
was rejected by design. Future 1.x releases remain a CI compatibility boundary;
these two passes do not prove compatibility with every future version.

Required task/result/checkpoint, message, debug-wrapper, interrupt, values, and
usage-metadata shapes were checked against the official runtime definitions
present in both tested versions. Empty records, invalid result branches,
duplicate task IDs, explicit `null` for required arrays, invalid Unicode,
non-finite numbers, conflicting run/thread/namespace identities, oversized or
malformed NDJSON values, and malformed runtime objects have regression coverage.

## Manual browser evidence

Latest-code local manual smoke (not hosted CI):

- Chromium `150.0.0.0` through Playwright CLI on Windows;
- viewport `1920×1080`, device-pixel ratio `1`;
- test server `http://127.0.0.1:8877/anthill`; the user-facing `8765` process was
  not restarted or modified;
- a synthetic LangGraph v2 JSON file was selected through the real import menu
  after the strict shape/identity and reducer changes; the selected value was
  `browser-current-20260717-final`;
- the new run projected `8` events and displayed `COMPLETED`,
  `HASH CHAIN VALID`, reducer `0.2.0`, coverage contract `0.2.0`, one registered
  `anthill.langgraph-v2` adapter, and its declared blind spots;
- browser console result: `0` errors and `0` warnings;
- local-only screenshot, ignored by Git and not included in the release artifact:
  `output/playwright/langgraph-060-latest-code-import.png`.

Earlier manual checks on 2026-07-17 exercised LangGraph NDJSON, AG-UI import,
Demo, historical seek, Fork, and Compare. The final current-code rerun above was
specifically the LangGraph JSON import and projection path. Browser automation is
not yet part of hosted CI, so these results are labelled manual rather than
continuous evidence.

## Explicitly pending

- The local workstation has no Docker CLI. Compose validation, image build,
  non-root identity, read-only root, health, and ledger-write smoke are configured
  in CI but remain pending a hosted Actions result.
- Automated cross-browser and assistive-technology CI is not implemented.
- OTLP protobuf/live collection, AG-UI live subscription, and a LangGraph live
  capture bridge are not implemented.
- Hosted/untrusted ingestion still needs benchmark-derived body, structure,
  cardinality, emitted-event, and backpressure limits.
- Authentication, tenant isolation, TLS, and sandboxed Python trace execution are
  not provided by the local alpha.

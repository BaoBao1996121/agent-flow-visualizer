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
| Frontend syntax | `node --check` over application modules, Playwright config/spec, and the three bounded spike scripts | PASS |
| Chromium observatory contract | `npm run test:browser` | 13 passed in 34.3s at the explicit `1600x1000` viewport |
| Browser order isolation | `npx playwright test --repeat-each=2` | 26 passed in 1.2m; the empty-state fixture does not depend on suite ledger order |
| Structured fixtures/config | Python JSON parsing for both LangGraph and canonical-ingest fixtures; PyYAML parse for `.github/workflows/ci.yml` | PASS |
| Patch hygiene | `git diff --check` | PASS |

The optional runtime test is not counted among the 204 passes. Its two
supported runtime executions are recorded separately below.

## Automated Chromium observatory contract

The local Windows run used Node.js `22.14.0`, npm `10.9.2`,
`@playwright/test 1.61.1`, and Chromium `149.0.7827.55`. The contract verifies:

1. deterministic synthetic empty state with no browser console/page errors;
2. an explicit `1600x1000` desktop viewport for reproducible visual evidence;
3. ledger head, follow/pause, and transport connection are not labelled `LIVE`;
4. terminal unresolved chamber work is static and labelled `UNRESOLVED`;
5. `interrupted` is treated as terminal and leaves no Canvas ticker running;
6. terminal context overflow keeps a static warning without an infinite pulse;
7. absent cognition telemetry remains `NOT OBSERVED`, never `0` or `IDLE`;
8. completed-run Canvas pixels and animation-frame count remain stable;
9. the timeline cursor event is the default explicit-causality root;
10. an already-open Causal panel follows timeline seek;
11. a stale causal-direction response cannot overwrite the latest request;
12. a delayed world response cannot overwrite a newly selected run; and
13. Inspector tabs expose tab/tabpanel semantics and roving arrow-key navigation.

The harness owns `127.0.0.1:8878`, sets an isolated ignored
`ANTHILL_DATA_DIR`, and uses `reuseExistingServer: false`; it neither connects
to nor modifies the user-facing `8765` process. The GitHub Actions Chromium job
is configured with strict focused/flaky-test failure and seven-day diagnostics,
but no hosted Actions execution exists yet. This is Chromium coverage, not
cross-browser or real assistive-technology evidence.

Only synthetic fixtures were used. HTML reports, traces, and screenshots may
retain page/request data; introducing real traces requires a fresh artifact
privacy review.

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

## Earlier manual browser evidence

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
specifically the LangGraph JSON import and projection path. These remain manual
historical checks; the current Chromium contract is automated locally and wired
into the workflow, while its first hosted run remains pending.

## Explicitly pending

- The local workstation has no Docker CLI. Compose validation, image build,
  non-root identity, read-only root, health, and ledger-write smoke are configured
  in CI but remain pending a hosted Actions result.
- The configured Chromium browser job remains pending its first hosted Actions result.
- Automated cross-browser and assistive-technology CI is not implemented.
- OTLP protobuf/live collection, AG-UI live subscription, and a LangGraph live
  capture bridge are not implemented.
- Hosted/untrusted ingestion still needs benchmark-derived body, structure,
  cardinality, emitted-event, and backpressure limits.
- Authentication, tenant isolation, TLS, and sandboxed Python trace execution are
  not provided by the local alpha.

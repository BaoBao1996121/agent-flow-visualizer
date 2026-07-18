# Verification record

Last verified: 2026-07-18 (Asia/Shanghai).

This is a dated evidence record, not a permanent quality claim. Hosted results
must be linked from the repository's current Actions page after publication.

## Current-code release gates

| Boundary | Command / method | Result |
|---|---|---|
| Core Python suite | `python -m pytest -q` | 326 passed; one optional real-runtime test skipped because the ambient LangGraph exposes the unsupported pre-1.1 tuple boundary |
| Schema and world contract | API, snapshot, lifecycle, storage, and reducer regressions | Event protocol `0.2.0`; reducer `0.3.0`; old snapshots remain isolated by reducer version; legacy `0.1.0` read compatibility is storage-only |
| Python lint | `python -m ruff check --no-cache .` | PASS |
| Frontend syntax | `node --check` over application modules, Playwright config/spec, and JavaScript spikes | PASS |
| Chromium observatory contract | `npm run test:browser` | 29 passed in 1.5m at the explicit `1600x1000` viewport |
| Browser order isolation | `npx playwright test --repeat-each=2` | 58 passed in 2.7m; selector collision assertions and route teardown are independent of prior executions |
| Structured fixtures/config | Python JSON parsing for both LangGraph and canonical-ingest fixtures; PyYAML parse for `.github/workflows/ci.yml` | PASS |
| Patch hygiene | `git diff --check` | PASS |

The optional runtime test is not counted among the 326 passes. Its two
supported runtime executions are recorded separately below.

## Automated Chromium observatory contract

The local Windows run used Node.js `22.14.0`, npm `10.9.2`,
`@playwright/test 1.61.1`, and Chromium `149.0.7827.55`. The contract verifies:

1. deterministic synthetic empty state with no browser console/page errors;
2. an explicit `1600x1000` desktop viewport for reproducible visual evidence;
3. ledger head, follow/pause, and transport connection are not labelled `LIVE`;
4. terminal unresolved chamber work is static and labelled `UNRESOLVED`;
5. `interrupted` is terminal and leaves no Canvas ticker running;
6. terminal context overflow keeps a static warning without an infinite pulse;
7. absent cognition telemetry remains `NOT OBSERVED`, never `0` or `IDLE`;
8. completed-run Canvas pixels and animation-frame count remain stable;
9. the timeline cursor event is the default explicit-causality root;
10. an already-open Causal panel follows timeline seek;
11. a stale causal-direction response cannot overwrite the latest request;
12. a delayed world response cannot overwrite a newly selected run;
13. failed run selection atomically restores the prior selector, world, state, timeline, integrity result, and live stream;
14. Run and Compare selectors expose the same source/HEAD-status/UTC-ingest/stable-ID identity;
15. colliding shortened IDs expand to full IDs in both selectors;
16. absent or invalid manifest facts stay visibly `UNKNOWN`;
17. HEAD lifecycle refresh does not rewrite historical cursor truth;
18. offset timestamps normalize to UTC, unzoned timestamps are rejected, and four-digit years remain stable;
19. selector, main title, and Compare card identity neutralize control, bidi, forged delimiters, and DOM injection;
20. only the newest manifest refresh response can update labels;
21. a missing active manifest preserves the selector and marks its identity `[STALE]`;
22. a hidden Compare candidate cannot block the active run refresh;
23. entering Compare refreshes the background run identity snapshot;
24. left and right Compare cards recompute at the same normalized progress after lifecycle and non-lifecycle events;
25. switching the primary run cancels and invalidates the older Compare pair;
26. a superseded Compare request cannot surface a stale error; and
27. Inspector tabs expose tab/tabpanel semantics and roving arrow-key navigation;
28. a failed selection after an in-flight selection restores the last successfully committed run; and
29. exact dot-segment event IDs use query-form detail and causal routes without browser URL normalization.

The harness owns `127.0.0.1:8878`, sets an isolated ignored
`ANTHILL_DATA_DIR`, and uses `reuseExistingServer: false`; it neither connects
to nor modifies the user-facing `8765` process. The workflow rejects focused or
flaky tests and retains seven-day diagnostics. Feature branches run through the
pull-request trigger instead of a duplicate push trigger, while superseded runs
in the same concurrency group are cancelled. The initial hosted 13-contract job
passed, but it predates the current 29-contract suite. This is Chromium coverage,
not cross-browser or real assistive-technology evidence.

Only synthetic fixtures were used. HTML reports, traces, and screenshots may
retain page/request data; introducing real traces requires a fresh artifact
privacy review.

## Storage, identity, and event-loop regressions

The current suite additionally proves these boundaries:

- manifest repair is serialized with append; malformed, missing, stale-behind,
  and semantically inconsistent caches rebuild from the validated ledger;
- a checksum-valid non-empty manifest acts as an accidental-damage HEAD anchor:
  deleting the last record, multiple records, all bytes, or the ledger file is
  diagnosed as `truncated_ledger`, and append does not overwrite or recreate it;
- same-length ledger changes with preserved mtime invalidate the append index
  because reuse is keyed by the complete ledger-byte SHA-256, not file metadata;
- first use or changed bytes revalidates JSON, contiguous sequence, duplicate
  IDs, and the event hash chain; unchanged bytes may reuse the in-process index;
- normal `/runs` discovery does not build the append event-ID index or claim a
  full integrity verdict. It returns `not_checked` / `discovery_boundary`, caps
  diagnostic records at 100, preserves the total, and exposes only a 24-hex
  (96-bit) opaque correlation reference;
- malformed, misplaced, unsafe legacy, shortened, empty, and missing ledgers
  do not hide healthy runs or reflect rejected identifiers/paths in diagnostics;
- every new API/body/path/Compare-query `run_id` uses one addressable-segment
  contract, and every returned 201 `world_url` is path-encoded and immediately
  resolves for supported Unicode/space IDs;
- canonical event-detail and causal query routes preserve exact `.`, `..`, and
  URL-reserved event IDs, while compatibility path routes are deprecated and
  missing-ID responses do not reflect the submitted value;
- a valid manifest damage anchor is enforced consistently by normal ledger
  reads, so event, replay, causal, comparison, and integrity boundaries cannot
  downgrade a known truncated/divergent run to an ordinary 404 or stale prefix;
- Fork's empty-target precondition and complete materialized batch share one
  per-run lock. A deterministic race proves direct-ingest-first yields Fork
  `409`, while Fork-first keeps the complete branch prefix before later events;
- blocking normalization, storage, projection, comparison, integrity, and SSE
  backlog/gap reads execute off the event-loop thread; a responsiveness test
  holds a store operation and proves `/schema` still responds.

The whole-ledger digest, event chain, and manifest checksum are unkeyed. They
detect accidental or uncoordinated changes; none is a MAC, signature, tenant
boundary, or proof against a writer that can recompute every value. Every append
still scans the growing ledger bytes, so repeated single-event appends have
cumulative `O(k²)` byte-scanning cost. That is a source-derived complexity
statement, not a throughput benchmark.

## Hosted GitHub Actions evidence

| Run / commit | Workflow generation | Result |
|---|---|---|
| [29570924390](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29570924390), `55fae916…` | Initial published workflow; 13 browser contracts; before schema `0.2.0`, reducer `0.3.0`, NDJSON depth fix, store hardening, and Node 24 action majors | Overall FAIL. PASS: browser 13/13, container, frontend, Python 3.11. FAIL: Python 3.12/3.13 and both LangGraph jobs, all from the same deep-NDJSON error-classification assertion. |
| [29629916726](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29629916726), `c39c70a…` | `actions/checkout@v6`, `setup-python@v6`, `setup-node@v6`, `upload-artifact@v7`; action runtime Node 24, project test runtime Node 22; 29 browser contracts | Overall PASS: Python 3.11/3.12/3.13, LangGraph 1.1.0/supported 1.x, frontend, Chromium, and hardened container. |

The workflow currently follows action major tags, not immutable commit-SHA pins.
SHA pinning plus automated dependency updates remains a supply-chain hardening
task; no stronger claim is made here.

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

## Earlier manual browser evidence (pre-reducer-0.3)

Historical local manual smoke retained for provenance (not current-code or hosted CI):

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
Demo, historical seek, Fork, and Compare. They predate reducer `0.3.0`, schema
`0.2.0`, the current storage contract, and the 29-test browser suite, so they do
not validate current HEAD. They remain useful only as historical interaction
evidence.

## Explicitly pending

- The local workstation has no Docker CLI, so local container execution remains
  unavailable. The current hosted container job passed Compose validation,
  image build, non-root identity, read-only root, health, and a real ledger write.
- Automated cross-browser and assistive-technology CI is not implemented.
- OTLP protobuf/live collection, AG-UI live subscription, and a LangGraph live
  capture bridge are not implemented.
- Hosted/untrusted ingestion still needs benchmark-derived body, structure,
  cardinality, emitted-event, and backpressure limits.
- Authentication, tenant isolation, TLS, and sandboxed Python trace execution are
  not provided by the local alpha.

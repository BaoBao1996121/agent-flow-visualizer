# Verification record

Last verified: 2026-07-19 (Asia/Shanghai).

This is a dated evidence record, not a permanent quality claim. Hosted results
must be linked from the repository's current Actions page after publication.

## Protected-main pre-Phase-C baseline

These values describe the published/protected baseline before the advisory S0
branch. Current branch-only evidence is recorded separately below.

| Boundary | Command / method | Result |
|---|---|---|
| Core Python suite | `python -m pytest -q` | 387 passed in 19.68s; one optional real-runtime test skipped because the ambient LangGraph exposes the unsupported pre-1.1 tuple boundary |
| Schema and world contract | API, snapshot, lifecycle, storage, and reducer regressions | Event protocol `0.2.0`; reducer `0.4.0`; measurement extension `1.0.0`; coverage contract `0.3.0`; old snapshots remain isolated by reducer version; legacy `0.1.0` read compatibility is storage-only |
| Python lint | `python -m ruff check --no-cache .` | Full repository PASS |
| Frontend syntax | `node --check` over four application files, two Playwright configs, two specs, and the motion spike | 9/9 PASS |
| Chromium observatory contract | `npm run test:browser` | 49/49 passed in 2.0m at the explicit `1600x1000` viewport |
| Browser order isolation | `npx playwright test --repeat-each=2` | 98/98 passed in 4.4m; the two complete executions are independent of prior test order |
| Visual fixture and contract | Targeted visual fixture/contract Pytest files | 7/7 passed |
| Visual scene functionality | `npx playwright test --config=playwright.visual.config.mjs --ignore-snapshots` | 4/4 passed; every scene reached its screenshot boundary, but snapshots were deliberately ignored and this is not golden comparison |
| Pinned-Linux visual regression | Required `Pinned Chromium visual regression` job | Protected-main run 29639913312 PASS against all four reviewed committed goldens with update mode disabled; the context is required by `main` protection |
| Structured fixtures/config | Python JSON parsing for LangGraph, canonical-ingest, and deterministic visual fixtures; PyYAML parse for `.github/workflows/ci.yml` | PASS |
| Patch hygiene | `git diff --check` | PASS |

The optional runtime test is not counted among the 387 passes. Its two
supported runtime executions are recorded separately below.

## Staged-validation baseline and shadow evidence

The pre-change Actions API baseline contains seven successful PR runs across
three correlated branch families: `29629916726`, `29630097193`, `29638437349`,
`29638608292`, `29639244683`, `29639799405`, and `29643593709`. It is enough to
size the first shadow loop, but not enough to claim a stable p95 or service level:

| Observation | Result |
|---|---|
| Time to first completed job | median 13s; mean 14.3s; observed sample maximum 25s |
| Total workflow wall time | median 81s; mean 80.9s; observed sample maximum 93s |
| Summed executor time | median 4.33 runner-min; observed sample maximum 4.68 runner-min |
| Parallelism cost | 28.8 total runner-min versus 9.43 total workflow-wall minutes across the seven runs, or 3.05× |
| Current critical tail | Chromium contract: median 77s; observed sample maximum 89s |

The evidence therefore rejects “hosted full CI wall time is presently slow” as
the main premise. The maintained hypothesis is narrower: repeated Draft pushes
spend avoidable runner time, and future renderer/browser/performance matrices
need room to grow.

Local shadow evidence:

- one sequential Windows execution of the exact shadow fast command (full Ruff,
  five focused Pytest files, and four primary JavaScript syntax checks) passed in
  5.50 seconds; this is one warm local sample, not hosted timing or a p95;
- `python -m pytest tests/test_ci_staging_contract.py -q`: `2 passed` after
  separate RED failures proved the missing fast job, transition triggers, and
  aggregate were observable;
- PyYAML `6.0.3` semantically parses the workflow and verifies exact aggregate
  dependencies, Draft failure, `always()`, `toJSON(needs)`, bounded fast work,
  and one exact job-level Draft condition across all six S2 job definitions.

Hosted Phase A evidence:

| Run / revision | Mode | Result |
|---|---|---|
| [29645134489](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29645134489), `641280e…` | Draft PR #13 | Fast PASS in 13s; every legacy S2 context PASS; aggregate explicit FAILURE in 3s with the Ready instruction. |
| [29645207017](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29645207017), same `641280e…` | `ready_for_review` | New run ID; fast PASS in 18s; every S2 context PASS; aggregate PASS in 2s after all dependencies. |
| [29645305313](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29645305313), resulting main `4dbd68b…` | Protected-main push | Fast PASS in 18s; complete S2 PASS; aggregate PASS in 2s. |

After the main run, branch protection was changed monotonically from nine to ten
required contexts. API readback retained `strict=true`, administrator enforcement,
all original contexts, GitHub Actions app ID `15368`, and every unrelated
protection field. The first stdin-based PATCH attempt returned HTTP 400 before
mutation; the reviewed-file retry succeeded and was read back. This is recorded
because failed control-plane attempts must not disappear from evidence.

Phase B's local RED→GREEN contract skips the six complete S2 job definitions only
for Draft PR events. The hosted state machine was then exercised on one unchanged
candidate, `aa0afb7`:

| Run | Transition | Result |
|---|---|---|
| [29645940777](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29645940777) | Open as Draft | Fast PASS 15s; six S2 definitions SKIPPED; aggregate explicit FAIL; wall 26s. |
| [29645986711](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29645986711) | Draft → Ready | All original S2 contexts and aggregate PASS; PR became clean. |
| [29646051103](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29646051103) | Ready → Draft | Fast PASS 19s; S2 SKIPPED; a new aggregate failure returned the PR to blocked. |
| [29646089291](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29646089291) | Draft → Ready | Complete S2 and aggregate PASS on the final candidate. |
| [29646265724](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29646265724) | Squash result on protected `main` | Commit `9a74764`; complete S2 plus aggregate PASS in 91s wall time. |

Live protection readback after the main run retained strict status checks,
administrator enforcement, the original nine contexts plus the aggregate, and
GitHub Actions app ID `15368`. Matrix-member failure propagation, dependency
skip/cancel canaries, historical replay, manifest completeness, and the rollback
drill remain pending.

## Automated Chromium observatory contract

The local Windows run used Node.js `22.14.0`, npm `10.9.2`,
`@playwright/test 1.61.1`, and Chromium `149.0.7827.55`. The contract verifies:

1. deterministic synthetic empty state with no browser console/page errors;
2. an explicit `1600x1000` desktop viewport for reproducible visual evidence;
3. ledger head, follow/pause, and transport connection are not labelled `LIVE`;
4. terminal unresolved chamber work is static and labelled `UNRESOLVED`;
5. chamber counts use full cursor history rather than the bounded recent-event feed;
6. the deterministic Canvas entity cap retains failed and unknown objects;
7. `interrupted` is terminal and leaves no Canvas ticker running;
8. terminal context overflow keeps a static warning without an infinite pulse;
9. absent cognition telemetry remains `NOT OBSERVED`, never `0` or `IDLE`;
10. event rows print evidence level instead of relying on color alone;
11. safe Meter readouts expose scoped values, derivation, pricing basis, estimated status, and evidence routes;
12. unsafe raw Meter signals do not become aggregate values, remain visible through Coverage, and have control/bidi characters in their measurement identities neutralized before display;
13. a repeated unknown-temporality measurement owner is `ambiguous`, not summed;
14. memory layers expose only recorded operations with an evidence route;
15. completed-run Canvas pixels and animation-frame count remain stable;
16. the timeline cursor event is the default explicit-causality root;
17. an already-open Causal panel follows timeline seek;
18. a stale causal-direction response cannot overwrite the latest request;
19. causal direction exposes its selected state without relying on color;
20. exact dot-segment event IDs use query-form detail and causal routes without browser URL normalization;
21. a delayed world response cannot overwrite a newly selected run;
22. failed run selection atomically restores the prior selector, world, state, timeline, integrity result, and live stream;
23. a failed selection after an in-flight selection restores the last successfully committed run;
24. Run and Compare selectors expose the same source/HEAD-status/UTC-ingest/stable-ID identity;
25. colliding shortened IDs expand to full IDs in both selectors;
26. absent or invalid manifest facts stay visibly `UNKNOWN`;
27. HEAD lifecycle refresh does not rewrite historical cursor truth;
28. offset timestamps normalize to UTC, unzoned timestamps are rejected, and four-digit years remain stable;
29. selector, main title, and Compare card identity neutralize control, bidi, forged delimiters, and DOM injection;
30. only the newest manifest refresh response can update labels;
31. a missing active manifest preserves the selector and marks its identity `[STALE]`;
32. a hidden Compare candidate cannot block the active run refresh;
33. entering Compare refreshes the background run identity snapshot;
34. left and right Compare cards recompute at the same normalized progress after lifecycle and non-lifecycle events;
35. Compare mechanisms render observed `true` as `ON` and missing/`null` as `NOT OBSERVED` with a matching semantic data attribute; missing evidence never becomes `OFF`;
36. Compare separates model chunks from completed calls without inventing numeric zero;
37. Compare emits numeric measurement deltas only for compatible contracts and marks incompatible pricing `not_comparable`;
38. switching the primary run cancels and invalidates the older Compare pair;
39. a superseded Compare request cannot surface a stale error;
40. Inspector tabs expose tab/tabpanel semantics and roving arrow-key navigation;
41. the semantic object mirror covers every current world entity and opens evidence by keyboard;
42. important presentation state is semantic and live announcements remain bounded;
43. application motion preference overrides the OS without reload and stops ambient RAF/CSS work;
44. tested core observatory labels meet the 12 CSS-pixel floor and selected normal-text pairs meet 4.5:1 contrast;
45. State keeps unobserved memory operations `NOT OBSERVED` instead of rendering default zero counters;
46. State keeps an unobserved Context header, budget, policy, and status `NOT OBSERVED` and does not apply a healthy class;
47. State preserves an explicitly observed zero context budget as `0 / 0 tokens` instead of treating zero as missing;
48. State keeps an unobserved latest compaction `NOT OBSERVED` instead of rendering a default zero; and
49. State labels the entity count `OBSERVED AGENTS` so zero cannot be read as proof that the external system has no Agent.

The harness owns `127.0.0.1:8878`, sets an isolated ignored
`ANTHILL_DATA_DIR`, and uses `reuseExistingServer: false`; it neither connects
to nor modifies the user-facing `8765` process. The workflow rejects focused or
flaky tests and retains seven-day diagnostics. Feature branches run through the
pull-request trigger instead of a duplicate push trigger, while superseded runs
in the same concurrency group are cancelled. The latest hosted ordinary browser
job covered all 49 contracts in protected-main run 29639913312. This is Chromium coverage, not
cross-browser or real assistive-technology evidence.

Only synthetic fixtures were used. HTML reports, traces, and screenshots may
retain page/request data; introducing real traces requires a fresh artifact
privacy review.

## Deterministic visual-regression promotion

Reproducible candidate generation, reviewed baseline promotion, and enforced
visual-regression comparison are implemented. The isolated suite in
`tests/visual/` fixes a synthetic
44-event fixture, Playwright `1.61.1`, a digest-pinned Noble container,
Python `3.12.13`, exact server dependencies, `1600x1000` at device scale factor
1, `en-US`, UTC, dark scheme, reduced motion, static capture, and font readiness.
The harness removes synthetic-only wall-clock/hash display pixels and disables
static Compare refresh. Its four scenes are overview, explicit error
evidence, instrumentation coverage, and Compare against a deterministic
pre-compaction prefix.

Current local functional evidence is `7/7` passing visual fixture/contract
tests plus `4/4` scenes reaching their screenshot boundary with
`--ignore-snapshots`. The latter deliberately bypasses pixel comparison: it
proves scene setup and capture flow, not image stability or acceptance.

[Run 29638608292](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29638608292)
passed all nine candidate-stage jobs and generated the four Linux images. Its
artifact digest and the reviewed per-file hashes are recorded in
[VISUAL_BASELINES.md](VISUAL_BASELINES.md). All four PNGs were inspected and
promoted in commit `6a96011`; reports and traces were not promoted.
The workflow now sets `ANTHILL_UPDATE_VISUALS=0`, has no
`continue-on-error`, and uploads diagnostics only after a failed comparison.
The initial pixel thresholds remain configurable values pending repeat
calibration. Windows screenshots are diagnostic only and cannot be promoted.

[Run 29639244683](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29639244683)
passed all nine jobs at commit `6a96011`; the visual lane compared the four
committed PNGs with update mode disabled. `main` protection was then read back
with `strict=true`, administrator enforcement enabled, and
`Pinned Chromium visual regression` present as the ninth required GitHub Actions
context. This completes the Phase -1 visual truth release gate. It does not prove
cross-browser rendering, real assistive-technology behavior, or user
comprehension.

[Run 29639913312](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29639913312)
repeated all nine required jobs after PR #9 was squash-merged to protected
`main` at `6b503a6`. Release `v0.7.0` points to that exact commit. This is the
published release verification; run 29639244683 remains the earlier promotion
and branch-protection evidence.

## Measurement truth and projection regressions

Numeric observability claims are now governed by a versioned contract rather
than frontend arithmetic. The Python and browser suites prove these boundaries:

- the `anthill.measurements` `1.0.0` extension validates registered unit, scope,
  aggregation, temporality, and owner semantics without adding top-level event
  fields or changing legacy event hashes;
- the world projection distinguishes `available`, `ambiguous`, and
  `not_observed`, retains evidence event IDs, persists ambiguity through
  snapshots, and records conflicts instead of selecting a convenient value;
- repeated unknown-temporality owners, cumulative decreases, and invalid
  numerics block the affected safe aggregate; an explicit-versus-derived
  mismatch makes the calculated total ambiguous while retaining the recorded
  explicit aggregate separately;
- calculated model total tokens remain a backend derivation with component
  status, while Meter renders only safe aggregates and keeps cost basis plus
  estimated status visible;
- raw/unregistered or unsafe signals remain discoverable through coverage
  contract `0.3.0` as `RAW · UNSAFE`; and
- Compare computes a numeric delta only when both sides are available and their
  key, unit, scope, aggregation, and relevant cost semantics match. Missing or
  incompatible claims remain explicitly unavailable or `not_comparable`.

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
| [29638437349](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29638437349), `ce6511f…` | First current-contract run with the non-blocking pinned-Linux candidate lane | Eight required jobs PASS. The tolerated candidate lane failed before screenshot generation because `setup-python` tried to spawn the container-only `/__t/.../pip` path while initializing its optional pip cache. |
| [29638608292](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29638608292), `a3b2a7e…` | Candidate-stage reducer/measurement/coverage contracts; 49 browser contracts; deterministic pinned-Linux generation | Overall PASS across all nine jobs. The visual lane generated the reviewed artifact; this run predates the switch to required compare mode. |
| [29639244683](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29639244683), `6a96011…` | Reviewed Linux goldens committed; visual job in blocking compare mode with updates disabled | Overall PASS across all nine jobs. The visual comparison passed without rewriting the baselines; the check was subsequently added to strict, administrator-enforced `main` protection. |
| [29639913312](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29639913312), `6b503a6…` | Protected-main post-merge run for release `v0.7.0`; all nine contexts required | Overall PASS across all nine jobs, including pinned-Linux visual comparison with updates disabled. The release tag points to this commit. |

Run 29639913312 is the published `v0.7.0` release evidence for the product
contracts, all ordinary CI lanes, and the required visual comparison. Run
29639244683 records the preceding promotion and protection step.

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

## Advisory S0 evidence

These 2026-07-18/19 local results established the Phase C candidate before its
separate hosted and protected-main evidence:

| Boundary | Command/evidence | Result |
|---|---|---|
| Selector/CLI/docs/CI/schema contracts | focused pytest slice | 93/93 passed in 33.44s after serialization; one earlier concurrent Windows launch produced Git DLL-initialization exits rather than assertion failures |
| Complete Python preflight | `python -m pytest -q` | 455 passed, one documented LangGraph compatibility skip, in 46.86s |
| UI vertical | Playwright `--grep '@s0'` | One pass in 8.9s through fixture load, history `seq 0`, Objects, keyboard Evidence, console/page/HTTP-5xx capture, and screenshot attachment; runner rejects skipped or non-exact execution even when the child exits zero |
| Python impact domains | CLI-selected pytest plus Ruff | LangGraph, storage, schema, projections, analysis, and API command-time observations all below 18s; these are warm local samples, not p95/SLA values |
| Historical mutation replay | runs 29570924390 and 29638437349 as provenance | Current selected sets passed; injecting each former fault produced the exact expected RED |
| Static gates | Ruff plus fixed Node syntax set | PASS |

The complete suite's 46.86-second result rejects full pytest as S0. Local persisted
PNG files are rewritten by endpoint DLP, so the earlier manually driven screenshot
was illustrative only. Protected-main run
[29653577169](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29653577169)
uploaded the exact test attachment. Its GitHub artifact digest is
`sha256:e99bf8a4d8616b10e0f64761796d3b037cd472f0fe03d2148799f4fd911d394c`;
the 257,184-byte screenshot plaintext was reviewed in memory at `1600×1000` with
SHA-256 `6a4a190afd51cd7b4fd939626d0a9db0604c1030173e2056576526373820df37`
before DLP rewrote the disk copy. It shows `HISTORY · SEQ 0`, `run.started`,
observed evidence, and the fixture Agent selected. Detailed chronological evidence
is in [STAGE_LOG.md](STAGE_LOG.md).

Hosted Phase C promotion evidence:

| Run / candidate | Transition | Result |
|---|---|---|
| [29652870258](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29652870258), `757d241…` | First Draft | RED: fast contracts exposed an ambient local `node_modules` test prerequisite; aggregate also failed as designed. |
| [29653112545](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29653112545), `1335e71…` | Final Draft candidate | Fast PASS; six S2 definitions SKIPPED; aggregate explicit FAIL with Ready instruction. |
| [29653151908](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29653151908), same `1335e71…` | Draft → Ready | All 11 jobs PASS in 100s wall, including three Python versions, both LangGraph lanes, Chromium, pinned visual comparison, hardened container, and aggregate; Playwright artifact uploaded. |
| [29653471568](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29653471568), `4dd4564…` | Final evidence-record candidate | All 11 jobs PASS in 93s wall; aggregate PASS; final Ready artifact uploaded. |
| [29653577169](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29653577169), squash `6b36444…` | Protected-main push | All 11 jobs PASS in 91s wall; aggregate PASS last; exact browser attachment uploaded. |

## Explicitly pending

- Staged validation still needs representative observation-window samples,
  dependency and matrix-member failure/skip/cancel canaries, S3 nightly breadth,
  S4 exact-release-commit evidence, rollback drill, and an escaped-defect window.
- Measured comprehension, information-density, and recognition studies have not
  run. Automated cross-browser, screen-reader, high-contrast-mode, and real
  assistive-technology verification is not implemented.
- The renderer-independent `VisualModel`, art-direction study, PixiJS 8 vertical
  slice, and same-scene Phaser 4.2.1 benchmark are planned work, not current
  product capabilities.
- The local workstation has no Docker CLI, so local container execution remains
  unavailable. Protected-main run 29639913312 passed Compose validation, image
  build, non-root identity, read-only root, health, and a real ledger write.
- OTLP protobuf/live collection, AG-UI live subscription, and a LangGraph live
  capture bridge are not implemented.
- Hosted/untrusted ingestion still needs benchmark-derived body, structure,
  cardinality, emitted-event, and backpressure limits.
- Authentication, tenant isolation, TLS, and sandboxed Python trace execution are
  not provided by the local alpha.

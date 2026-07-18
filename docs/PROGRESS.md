# Project progress

## Current state

Agent Anthill `0.6.0` is a runnable local alpha with event protocol `0.2.0`, a tamper-evident JSONL reference ledger, deterministic projection/snapshots under reducer `0.4.0`, explicit causal inspection, historical playback, no-side-effect materialized forks, normalized run comparison, Python/OTLP/OpenInference/AG-UI/LangGraph v2 inputs, cursor-specific instrumentation visibility, and a Canvas + semantic-DOM observatory UI.

Current working-branch verified baseline:

- Python, OTLP/OpenInference, AG-UI JSON/NDJSON, and LangGraph StreamPart v2 JSON/NDJSON adapters;
- metadata-only default with explicit truth/fidelity levels;
- 12 semantic chambers plus Source Archive, Quality Gate, and Unknown Fog;
- live SSE, gap recovery, time travel, compare, snapshot fallback, branch provenance, and hash verification;
- Apache-2.0 community files, multi-version CI configuration, and a hardened Docker/Compose definition; the last published all-green evidence is historical [run 29629916726](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29629916726) at commit `c39c70a`, which predates reducer `0.4.0` and the current Phase -1 branch;
- 384 tests passed locally in 19.87 seconds; one optional real-LangGraph runtime test was skipped because the ambient environment exposes the unsupported pre-1.1 tuple boundary, while isolated LangGraph `1.1.0` and `1.2.9` probes passed separately;
- 49/49 local Chromium observatory contracts passed in 2.0 minutes, with all 98/98 executions passing in 4.4 minutes under a two-repeat order-isolation run;
- full-repository Ruff, nine JavaScript syntax checks, and `git diff --check` passed;
- the deterministic visual fixture/contract tests passed 7/7 and all four visual scenes reached their screenshot boundary with `--ignore-snapshots`; the pinned-Linux job remains a non-blocking candidate generator and no reviewed goldens are committed, so visual-regression protection is not yet claimed;
- latest-code manual Chromium verification of LangGraph JSON import; NDJSON, AG-UI, Demo, sequence-20 seek, Fork, and Compare remain earlier same-day manual evidence;
- real LangGraph `1.1.0` and `1.2.9` runtime probes across `tasks`, `messages`, `updates`, `values`, `checkpoints`, and `custom`.

## Next milestones

1. Run the pinned-Linux visual candidate job, review all four PNGs, commit only accepted goldens, change the job from non-blocking update mode to required comparison mode, and prove it passes without rewriting the baseline. This is the remaining Phase -1 release gate in [VISUAL_BASELINES.md](VISUAL_BASELINES.md).
2. Measure Phase 0 comprehension, density, recognition, accessibility, and art-direction candidates; then build the renderer-independent `VisualModel`, deterministic animation contract, PixiJS 8 vertical slice, and same-scene Phaser 4.2.1 benchmark. Publish measurements before selecting the migration path.
3. Add standard live OTLP collection plus AG-UI and LangGraph stream bridges with bounded ingestion/backpressure.
4. Add native Claude Code and Codex hooks with published capability contracts.
5. Add queryable monitoring exports, very-long-run pagination, and reference-based parent snapshot + tail DAG storage.
6. Add sandboxed stub replay before considering any real rerun.

## Session log

### 2026-07-16 — evidence-first alpha foundation

- Replaced the entertainment-only projection with a canonical truth-aware runtime event model and append-only ledger.
- Added reducers, snapshots, branching, comparison, causal slices, OTLP/OpenInference, synthetic fixture, and the new Anthill UI.
- Added AG-UI JSON/NDJSON mapping and browser import, including explicit ID-based causality and default redaction of messages/state/tools/errors/reasoning values.
- Found and fixed the timeline slider race through a real Playwright RED→GREEN path; historical and Compare cursors now use the requested value.
- Found and fixed cached Source X-Ray analysis skipping later persistence requests and leaking prior persistence metadata.
- Added non-root/read-only Docker/Compose configuration and a configured CI container smoke job. Neither local Docker execution nor a hosted Actions run has been completed.
- Added environment and assumption-validation records.
- Added a fourth `COVERAGE` inspection layer that distinguishes observed domains, observable-but-not-seen domains, contract-external domains, blind spots, unregistered adapters, and Unknown Fog types without manufacturing a percentage.
- Initialized local Git history on `main`; no remote or public repository has been created.

### 2026-07-17 — LangGraph StreamPart v2 offline milestone

- Added the dependency-free LangGraph 1.x StreamPart v2 normalizer, import API, JSON/NDJSON file-import UI, golden fixture, and versioned capability contract; the tested floor is `1.1.0` and the configured supported lane is `>=1.2,<2`.
- Preserved task interruption as `agent.step.interrupted`; emitted one namespace-scoped `human.interrupt`, linked later observations as `langgraph.interrupt.reobserved`, and kept checkpoint snapshots separate.
- Made capture completion outcome-neutral: absent explicit `runStatus`/`run_status`, a complete capture records `completed` instead of inferred success or failure.
- Stabilized oversized external interrupt identifiers through deterministic hashes in both task lifecycle and supplemental events, retaining source length without persisting the unbounded value.
- Converted failing or self-referential runtime-object dumps into controlled import errors instead of leaking runtime/recursion exceptions.
- Kept state, message, task, checkpoint, custom, error, and interrupt values metadata-only by default while documenting that identifiers and structural metadata can remain sensitive.
- Exercised real LangGraph `1.1.0` and `1.2.9` graphs across all six supported modes. The latest-code local manual Chromium rerun covered JSON import; NDJSON was earlier same-day manual evidence.
- Hardened official task/result/checkpoint/message/debug/interrupt/values shapes, cross-source run/thread/namespace identity checks, and controlled NDJSON parser failures.
- Bumped the world reducer to `0.2.0`: historical error and interrupt snapshots no longer masquerade as open/current incidents, and a later checkpoint snapshot cannot downgrade a live waiting approval.
- Recorded the remaining ingestion-budget gap: local alpha imports still need benchmark-derived part/namespace/task/interrupt/emitted-event quotas before untrusted hosted use.
- Added [VISUAL_SYSTEM.md](VISUAL_SYSTEM.md) with the Phase -1 truth cleanup, `VisualModel`, PixiJS 8 recommendation, Phaser 4.2.1 benchmark, accessibility, provenance, costs, and explicit exit conditions. Its performance budgets remain unmeasured gates.

### 2026-07-17 — Phase -1 observatory contract milestone

- Added an isolated Playwright 1.61.1 Chromium harness on `127.0.0.1:8878`, an official-registry exact lock file, and an independent GitHub Actions browser job. At that milestone hosted execution was pending; the then-current 29-contract job is recorded in the 2026-07-18 milestone below.
- Established an explicit `1600x1000` viewport after a RED test proved the device descriptor had silently produced `1280x720`.
- Split transport connection from timeline head/history and follow/pause: terminal runs no longer show or blink as `LIVE`.
- Marked completed, failed, interrupted, and cancelled worlds as terminal; unresolved chamber activity is static and explicit, while terminal Canvas/ticker motion is frozen.
- Preserved terminal context-overflow warnings while disabling their infinite CSS pulse.
- Replaced initial and runtime missing cognition telemetry with `NOT OBSERVED` rather than synthetic `0/IDLE` values.
- Made timeline cursor events the default causal root, refreshed an open Causal panel on seek, and rejected stale cross-run/event/direction responses.
- Added run/request epochs plus cancellation so delayed world responses cannot overwrite a newly selected run.
- Added ARIA tab/tabpanel state plus roving left/right keyboard navigation for the Inspector.
- Proved browser order isolation with a two-repeat run: 26/26 executions passed. The ordinary suite passed 13/13 in 34.3 seconds.
- At that milestone, remaining Phase -1 work included selector identity/status labels, per-layer memory observation provenance, full reduced-motion CSS, panel/view/follow keyboard semantics, a Canvas entity DOM mirror, and screenshot baselines. The next session completed the selector identity work.

### 2026-07-18 — run identity, lifecycle, and ledger discovery hardening

- Bumped the canonical write schema to `0.2.0`. New `run_id` values must be one display-stable API path segment; explicit store-only context keeps safe access to legacy `0.1.0` records without weakening new writes.
- Bumped the world reducer to `0.3.0` and made the reducer and manifest cache share one lifecycle fold. A terminal event remains authoritative when non-lifecycle events follow it.
- Added collision-aware Run/Compare identities with title, first-event source adapter, ledger-HEAD lifecycle status, first ingest observation in UTC, stable ID, and a `[DEMO]` marker only for explicit synthetic runs. HEAD identity never rewrites historical cursor truth.
- Added request epochs, abortable single-flight Compare work, left/right SSE refresh, atomic run-selection rollback, visible stale identity state, and uniform control/bidi/delimiter neutralization across selectors, titles, and Compare cards.
- Hardened discovery with a checksummed rebuildable manifest cache, 100-record privacy-safe diagnostics, a 96-bit opaque correlation reference, striped re-entrant locks, storage-only legacy validation, and content-verified append-index reuse.
- A checksum-valid non-empty manifest now quarantines a shortened, emptied, or missing ledger as `truncated_ledger`; it never recreates or overwrites the damaged ledger. `/runs` remains a lightweight `discovery_boundary`, not a full integrity verdict.
- Enforced the same valid-manifest damage anchor on normal event, replay, causal, comparison, and integrity reads, while preserving the established `invalid_event` classification for a malformed ledger record.
- Each append hashes the current ledger bytes and performs full JSON/sequence/duplicate/hash-chain validation on first use or changed content. Repeated single-event appends still accumulate `O(k²)` byte scanning; the local JSONL backend is not the production multi-process store.
- Moved blocking API storage, adapter normalization, projection, comparison, integrity, and SSE backlog/gap reads off the event-loop thread. All import bodies, route path parameters, Compare query IDs, and returned `world_url` values now share the addressable run-ID contract.
- Added canonical query-form event-detail and causal routes for opaque IDs, deprecated path-form compatibility, and removed event-ID reflection from 404/409/422 errors. Fork target creation now performs its empty-ledger check and complete batch write under one run lock: a competing direct write cannot create a second origin, and concurrent same-ID forks return one `201` plus one stable `409`.
- Made failed run selection restore the last successfully committed run even across an intervening in-flight selection; the frontend now uses the canonical query routes so exact `.`/`..` IDs cannot be rewritten by browser path normalization.
- Added a quote/escape-aware NDJSON nesting guard at 256 levels. This is an initial conservative validation limit, not a measured ingestion budget.
- Upgraded workflow action major tags to checkout/setup Python/setup Node `v6` and upload-artifact `v7`; these actions use a Node 24 action runtime while project tests remain Node 22. The upgraded workflow passed all eight jobs in run 29629916726.
- Milestone-local gates at that point: `326 passed, 1 skipped`; Ruff and JavaScript syntax checks passed; Playwright `29/29` and repeated `58/58` passed on the isolated `8878` service. These counts are historical and have been superseded by the working-branch evidence above.
- Milestone hosted gates: run 29629916726 passed Python 3.11/3.12/3.13, LangGraph 1.1.0/supported 1.x, frontend, Chromium, and hardened container jobs for commit `c39c70a`. This remains historical evidence, not verification of the current working branch.
- Initial hosted run [29570924390](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29570924390) is retained as historical evidence: browser 13/13, container, frontend, and Python 3.11 passed; Python 3.12/3.13 and both LangGraph jobs failed on the same now-fixed deep-NDJSON error classification. It predates every current-branch claim above.

### 2026-07-18 — Phase -1 visual truth and measurement milestone

- Bumped the world reducer to `0.4.0`, added the versioned `anthill.measurements` `1.0.0` extension, and bumped instrumentation coverage to `0.3.0` so raw/unaggregated measurement signals remain visible as unsafe instead of becoming trusted totals.
- Added owner-aware safe measurement projection with `available`, `ambiguous`, and `not_observed` states, evidence event IDs, calculation components, explicit-versus-derived consistency, cost pricing basis, and estimated status. Repeated unknown-temporality owners, cumulative decreases, invalid numerics, and explicit-versus-derived conflicts are surfaced instead of silently reconciled.
- Reconciled Meter, Memory, Context, and Compare: Meter reads only safe backend aggregates; Memory exposes recorded layer operations with evidence routes; absent cognition remains `NOT OBSERVED`; Compare separates model chunks from completed calls and emits numeric measurement deltas only for compatible contracts.
- Made full cursor history authoritative for chamber counts, preserved selected/failed/unknown entities under the deterministic Canvas cap, printed evidence and tri-state Compare semantics (`ON`, explicit `OFF`, `NOT OBSERVED`), and added explicit no-signal/unknown patterns so color is redundant information.
- Added a per-cursor semantic object mirror, keyboard evidence routes, bounded live announcements, tested ARIA state, application and OS motion controls, terminal/static RAF shutdown, 12 px core-label checks, and selected 4.5:1 contrast regressions. Real assistive-technology and comprehension testing remain pending.
- Added a deterministic 44-event synthetic fixture and four pinned-Linux visual scenes: overview, explicit error evidence, coverage, and Compare. The CI job still generates non-blocking candidates; no Linux golden has been reviewed or promoted.
- Current local evidence: Python `384 passed, 1 skipped` in 19.87 seconds; ordinary Chromium `49/49` in 2.0 minutes; repeated Chromium `98/98` in 4.4 minutes; full-repository Ruff, nine JavaScript syntax checks, and `git diff --check` passed. Visual fixture/contract tests passed `7/7`, and four scenes passed functionally with `--ignore-snapshots`. Current-branch hosted verification remains pending, and functional scene execution is not golden comparison.
- All eight Phase -1 semantic corrections now have implementation coverage, but Phase -1 is not release-complete until the reviewed pinned-Linux goldens run as a blocking comparison job. Measured user comprehension and real assistive-technology validation remain later evidence gates.

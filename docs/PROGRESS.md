# Project progress

## Current state

Agent Anthill `0.7.0` is a runnable local alpha with event protocol `0.2.0`, a tamper-evident JSONL reference ledger, deterministic projection/snapshots under reducer `0.4.0`, explicit causal inspection, historical playback, no-side-effect materialized forks, normalized run comparison, Python/OTLP/OpenInference/AG-UI/LangGraph v2 inputs, cursor-specific instrumentation visibility, and a Canvas + semantic-DOM observatory UI.

Published `v0.7.0` / protected-`main` verified baseline:

- Python, OTLP/OpenInference, AG-UI JSON/NDJSON, and LangGraph StreamPart v2 JSON/NDJSON adapters;
- metadata-only default with explicit truth/fidelity levels;
- 12 semantic chambers plus Source Archive, Quality Gate, and Unknown Fog;
- live SSE, gap recovery, time travel, compare, snapshot fallback, branch provenance, and hash verification;
- Apache-2.0 community files, multi-version CI configuration, and a hardened Docker/Compose definition; the protected-main [run 29639913312](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29639913312) at release commit `6b503a6` passed all nine jobs, including the 49-contract Chromium lane and required pinned-Linux visual comparison;
- 385 tests passed locally in 20.28 seconds; one optional real-LangGraph runtime test was skipped because the ambient environment exposes the unsupported pre-1.1 tuple boundary, while isolated LangGraph `1.1.0` and `1.2.9` probes passed separately;
- 49/49 local Chromium observatory contracts passed in 2.0 minutes, with all 98/98 executions passing in 4.4 minutes under a two-repeat order-isolation run;
- full-repository Ruff, nine JavaScript syntax checks, and `git diff --check` passed;
- the deterministic visual fixture/contract tests passed 7/7, all four scenes reached their screenshot boundary with `--ignore-snapshots`, and run 29639913312 compared the four reviewed Linux goldens with updates disabled; strict, administrator-enforced `main` protection requires that visual check;
- latest-code manual Chromium verification of LangGraph JSON import; NDJSON, AG-UI, Demo, sequence-20 seek, Fork, and Compare remain earlier same-day manual evidence;
- real LangGraph `1.1.0` and `1.2.9` runtime probes across `tasks`, `messages`, `updates`, `values`, `checkpoints`, and `custom`.

Protected `main` now includes the Phase C advisory S0 impact runner and chronological
[stage log](STAGE_LOG.md). Its candidate-local preflight was `455 passed, 1 skipped`,
Ruff, seven fixed Node syntax checks, and one 8.9-second screenshot-attaching
Chromium vertical. PR #16 proved Draft/Ready routing; protected-main run 29653577169
then passed all 11 jobs on `6b36444` in 91 seconds.

## Next milestones

1. Continue the [staged-validation contract](VALIDATION_STAGES.md) tracked in [issue #12](https://github.com/BaoBao1996121/agent-flow-visualizer/issues/12): collect the observation window, failure/skip/cancel and matrix-member canaries, manual-dispatch sample, S3 breadth, and rollback evidence. Keep the runner advisory and all ten protected contexts intact until those data justify change.
2. Execute the [Phase 0 visual evidence plan](PHASE0_VISUAL_EVIDENCE_PLAN.md) tracked in [issue #10](https://github.com/BaoBao1996121/agent-flow-visualizer/issues/10); then build the renderer-independent `VisualModel`, deterministic animation contract, PixiJS 8 vertical slice, and same-scene Phaser 4.2.1 benchmark. Publish measurements before selecting the migration path.
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
- Added a deterministic 44-event synthetic fixture and four pinned-Linux visual scenes: overview, explicit error evidence, coverage, and Compare. Candidate-stage run 29638608292 generated all four images; each PNG was reviewed, its artifact provenance was recorded, and only the accepted files were promoted in commit `6a96011`.
- Diagnosed run 29638437349's tolerated visual-lane failure as a `setup-python` pip-cache host/container path mismatch after Python 3.12.13 had installed successfully. Removed only that visual job's optional pip cache, retained the exact interpreter and dependency lock, added a regression contract, and proved the corrected candidate lane in run 29638608292.
- Current local evidence: Python `385 passed, 1 skipped` in 20.28 seconds; ordinary Chromium `49/49` in 2.0 minutes; repeated Chromium `98/98` in 4.4 minutes; full-repository Ruff, nine JavaScript syntax checks, and `git diff --check` passed. Visual fixture/contract tests passed `7/7`, and four scenes passed functionally with `--ignore-snapshots`. Candidate-stage run 29638608292 passed all nine then-configured jobs before required comparison was enabled.
- Switched the pinned visual lane to required compare mode, disabled baseline updates, and added failure-only diagnostics. Run 29639244683 passed all nine jobs without rewriting the reviewed goldens; `main` protection now requires that ninth check with strict and administrator enforcement. This completes the Phase -1 visual truth release gate. Measured user comprehension and real assistive-technology validation remain Phase 0 evidence gates.
- Bumped the application release to `0.7.0` and added a synchronization contract across the Python package, FastAPI metadata, frontend package/lock, container label default, README, and progress record.

### 2026-07-18 — v0.7.0 release and Phase 0 evidence kickoff

- Squash-merged [PR #9](https://github.com/BaoBao1996121/agent-flow-visualizer/pull/9) to protected `main` at `6b503a6`; issue #2 closed against its complete acceptance contract.
- Protected-main run 29639913312 passed all nine required jobs. Published [Agent Anthill 0.7.0 — Visual Truth Foundation](https://github.com/BaoBao1996121/agent-flow-visualizer/releases/tag/v0.7.0) from that exact commit.
- Closed the now-complete `v0.7 - Visual truth foundation` milestone and resequenced the public roadmap to `v0.8 - Visual evidence lab`, `v0.9 - Live observability`, and `v0.10 - Production path`.
- Created issue #10 and preregistered [Phase 0 plan v2.2](PHASE0_VISUAL_EVIDENCE_PLAN.md) before recruitment: the 44-event control obligations, atomic eight-question/W1–W8 rubric, staged planned-target/operable-route manifest, two pilots, eight Canvas/A/B/C static screeners with W/X/Y/Z rotation, balanced 12-person Canvas-versus-two-candidate study, three formal isomorphic fixtures, operational accessibility/density tasks, failure/no-response rules, asset spike, engine boundary, and fixed stratum-specific decision order.
- Verified the official npm registry resolves `pixi.js@8.19.0` and `phaser@4.2.1` with integrity metadata. The workstation's configured npm mirror returns 404 for Phaser 4.2.1; future benchmark installs must use an explicit isolated registry without changing global configuration.
- Official public documentation retrieved 2026-07-18 shows that [Langfuse already offers Agent Graphs](https://langfuse.com/docs/observability/features/agent-graphs), [Phoenix organizes Agent work around traces and spans](https://arize.com/docs/phoenix/tracing/concepts-tracing/what-are-traces), and [AgentOps exposes session waterfall views](https://docs.agentops.ai/v2/usage/dashboard-info). Therefore the maintained product-position inference is that generic trace graphs are not a moat; Anthill differentiates through causal proof, epistemic truth, capture blind spots, mechanism-level Compare, and evidence routes.
- Reforecast Phase 0 after independent preregistration audit from 5–8 to 8–14 engineer-days, plus 4–7 artist/UX-days and 5–8 separate research/facilitation-days. Participant compensation, equipment, venue, and recruitment lead time remain unpriced until approved before recruitment.
- Attempted built-in image generation for Phase 0 concept material twice. Both attempts failed at the service network layer and produced no artifact; no API-key CLI fallback or unreviewed asset entered the repository.

### 2026-07-18 — staged-validation shadow implementation

- Added [issue #12](https://github.com/BaoBao1996121/agent-flow-visualizer/issues/12) and the normative [S0–S4 validation contract](VALIDATION_STAGES.md), making exploration feedback time, runner cost, PR-candidate plus resulting-main evidence, and explicit rollback first-class project goals.
- Added an unconditional, non-matrix `Exploration fast gate` with Ruff, five focused Python contract files, and four primary JavaScript syntax checks. It began as a conservative shadow S1 and is now enforced transitively by the required aggregate; it is not yet an impact-selected gate.
- Added explicit Draft/Ready workflow activities plus an `always()` aggregate that fails Draft pull requests and accepts only `success` from S1 and every existing S2 dependency. Semantic PyYAML contract tests were developed RED→GREEN.
- Design review: 5/5 passed for verified external dependencies, source-labelled performance observations, failure/rollback paths, provisional thresholds, and unchanged Phase 0/product boundaries.
- Working-branch local gates passed: `387 passed, 1 skipped` in 19.68 seconds, full-repository Ruff, four primary JavaScript syntax checks, semantic workflow parsing, and `git diff --check`.
- Kept all nine strict, administrator-enforced required contexts and their every-PR execution unchanged during Phase A. After hosted Draft-to-Ready and protected-main evidence passed, the aggregate was added as a tenth required context without removing any original context.
- At that milestone, S0 commands/manifests, impact-map replay, Draft suppression of S2, S3, and S4 remained pending. No staged-validation completion or CI speedup was claimed from local contract tests alone.

### 2026-07-18 — staged-validation aggregate promotion and Draft optimization

- Draft run 29645134489 preserved the explicit aggregate failure after fast S1 passed in 13 seconds and every legacy S2 context passed. `ready_for_review` created run 29645207017 on the same PR candidate; complete S2 passed and the aggregate passed in 2 seconds.
- Squash-merged PR #13 to protected-main commit `4dbd68b`; run 29645305313 repeated fast S1, complete S2, and aggregate successfully on the resulting commit.
- Added `Protected main validation gate` as a tenth required context only after that main evidence. API readback retained strict/admin protection, all original nine contexts, app ID `15368`, and every unrelated protection field. The rejected HTTP-400 stdin attempt caused no mutation and remains recorded.
- On the next branch, developed the exact six-job Draft condition RED→GREEN: complete S2 skips only for Draft PR events, while Ready, main push, and manual events still run. The aggregate remains an explicit required failure in Draft.
- Design review: 5/5 passed for official dependency/event semantics, run-linked measurements, skip/failure/rollback paths, provisional threshold rationale, and unchanged Phase 0/product boundaries.
- PR #14 exercised Draft → Ready → Draft → Ready on unchanged candidate `aa0afb7`: Draft runs 29645940777/29646051103 executed only fast plus the explicit failing aggregate, while Ready runs 29645986711/29646089291 restored and passed complete S2.
- Squash-merged PR #14 to `9a74764`; protected-main run 29646265724 passed fast, every original S2 context, and the aggregate. API readback again retained strict/admin protection and all ten app-bound contexts.
- The two hosted Draft samples used approximately 0.30/0.38 runner-min and 26s/32s wall time. These beat the provisional Draft thresholds but are observations, not p95 or long-window claims.
- Post-canary design review: 5/5 passed. External/event behavior is hosted-proven; measurements are run-linked; failure and rollback boundaries remain explicit; thresholds remain provisional; product scope is unchanged.
- At that milestone, failure/skip/cancel and matrix-member canaries, historical replay, impact manifests, deterministic S0, S3, and S4 remained pending. The original nine contexts remain required; no 9→1 collapse occurred.

### 2026-07-18 — advisory S0 impact runner candidate

- Design review: 5/5 passed for exercised dependencies, source-labelled timings, explicit error/escalation paths, provisional thresholds, and unchanged advisory-versus-protected boundaries.
- Added a versioned repository impact map, NUL-safe Git union discovery, bounded content/index fingerprints, fail-closed special-entry and visibility handling, stable plans, fixed command registry, global/per-command budgets, retained retries, and atomic machine-readable reports. The runner never grants promotion authority.
- Added a JSON-only `python -m validation plan/run` interface with explicit exit codes for pass, failure/stale input, incomplete/S2 evidence, and discovery/configuration errors. Policy-selected targets are separated from tool options and run with `shell=False`.
- Mapped all tracked and non-ignored untracked workspace paths, sent unknown and control-plane paths to S2, added a canonical-sample schema contract, and put the runner/CLI/documentation contracts into the fixed Draft fast gate without allowing PR content to choose whether S2 runs.
- Added a fixture-driven `@s0` Chromium path through run truth, historical `seq 0`, Objects, keyboard Evidence activation, and browser-error capture. It attaches the exact exercised screenshot. Ready run 29653151908 produced and uploaded the unmodified `HISTORY · SEQ 0` / `run.started` attachment; its in-memory 1600×1000 bytes were reviewed before local DLP rewrote the materialized file.
- Rejected “full pytest fits 30 seconds” after a 30.043-second timeout. Bounded LangGraph, storage, schema, projections, analysis, and API verticals instead measured 5.683–17.072 seconds of local command time; the complete suite remains S1/S2.
- Replayed the deep-NDJSON and visual pip-cache incidents against versioned selectors. Each current set passed, and each injected former fault produced the expected RED. Hosted cross-platform evidence still governs promotion.
- Local candidate re-freeze passed 93/93 focused contracts in 33.44 seconds, `455 passed, 1 skipped` in 46.86 seconds, Ruff, seven fixed Node syntax checks, and `@s0` in 8.9 seconds. It includes loaded-policy digest attestation, skipped-browser rejection, and HTTP 5xx capture. A concurrent Windows launch produced Git DLL initialization exits; the unchanged focused command passed when isolated, so local Git-heavy tests remain serialized.
- Added the append-only [stage breakthrough log](STAGE_LOG.md): every bounded gain records time, action, measured effect, and evidence/limit; frontend stages also require the exercised screenshot. PR #16 proved the Draft fast-only state; final Ready run 29653471568 passed all 11 jobs in 93 seconds; squash commit `6b36444` repeated all 11 on protected main in 91 seconds and uploaded the exact browser attachment.

### 2026-07-19 — Phase 0 orthographic Visual Lab VA0 candidate

- Selected an isolated DOM/SVG orthographic cutaway as the first executable art-direction candidate. It reads explicit ledger APIs and leaves the production Canvas and unfrozen `VisualModel` boundary unchanged.
- Added a bounded asset path from programmatic glyphs through AI-assisted concept references, deterministic Pixelorama production, a maximum-one-day Blender comparison, and a same-scene PixiJS/Phaser benchmark. All duration and engine-selection values remain estimates or preliminary measurements until the named stages run.
- Recorded the launch, truth contract, staged regression policy, engine ownership boundary, provenance rules, costs, stop conditions, and known limits in [the Visual Lab record](PHASE0_VISUAL_LAB.md).
- Design review: 5/5 passed. External versions and APIs were checked against primary sources; the 57.8% signal is explicitly a gzip-6 ESM-file comparison and all forecasts are labelled; invalid identity, stale cursor, integrity, timeout/retry, over-density, motion, and evidence failures are fail-closed. The 5,000-event guard is enforced, while response-byte and sensitive-field limits remain a separate gate before public or sensitive-run use. Thresholds retain their initial/experimental status; the lab does not claim production or Phase 0 victory.
- Independent stable local Chromium passed 25/25 Visual Lab cases in 1.1 minutes (68.720 seconds process wall); the exact final `@visual-lab-s0` selector passed 1/1 in 10.2 seconds, four Node syntax checks passed, and `git diff --check` passed. The first anchored grep selected no tests; the corrected repository tag selected exactly one, so the command correction is recorded without mislabelling it as a product failure.
- The final browser-memory screenshot is 1600×1000, 249,107 bytes, SHA-256 `07154927e9ab15980ba4596b50b2e8f7766de78b20388420fa26687709e176cd`. It shows 12 zones, 12 entities, event 44 at sequence 43, the exact addressed run without clipping, and zero clipped entity labels.
- Truth review found and closed three pre-PR blockers with RED/GREEN evidence: display failure can no longer invent run or ledger invalidity; a superseded seek failure can no longer erase a newer verified HEAD; and a late old HEAD can no longer poison the cache used by a later seek. The same pass added sibling-request cancellation, browser `no-store`, and honest disabled state for initially unbound HEAD controls. Public or sensitive-run response-byte/field minimization remains an explicit future gate.
- The advisory impact runner passed the explicit Visual Lab S1 vertical with complete feedback. The full worktree correctly requires S2 because the impact policy itself changed, protected-base policy therefore differs, and skip-worktree DLP paths limit local visibility; local evidence remains non-promotional by design.
- Final local design review: 5/5 passed. External dependencies remain verified; timings and package-size observations are source-labelled; timeout, retry, abort, stale generation, dirty data, integrity, density, accessibility, and evidence paths are explicit; thresholds remain initial; scope remains an isolated VA0 precursor. Hosted engineering S2, exact unmodified attachments, PR review, and protected-main replay remain required, so no promotion is claimed yet.

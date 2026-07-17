# Project progress

## Current state

Agent Anthill `0.6.0` is a runnable local alpha with a versioned canonical event protocol, tamper-evident JSONL ledger, deterministic projection/snapshots under reducer `0.2.0`, explicit causal inspection, historical playback, no-side-effect materialized forks, normalized run comparison, Python/OTLP/OpenInference/AG-UI/LangGraph v2 inputs, cursor-specific instrumentation visibility, and a Canvas + DOM observatory UI.

Current verified baseline:

- Python, OTLP/OpenInference, AG-UI JSON/NDJSON, and LangGraph StreamPart v2 JSON/NDJSON adapters;
- metadata-only default with explicit truth/fidelity levels;
- 12 semantic chambers plus Source Archive, Quality Gate, and Unknown Fog;
- live SSE, gap recovery, time travel, compare, snapshot fallback, branch provenance, and hash verification;
- Apache-2.0 community files, multi-version CI configuration, and a hardened Docker/Compose definition; hosted CI/container execution remains pending;
- 204 tests passed in the ambient suite; one optional real-LangGraph runtime test was skipped, while isolated LangGraph `1.1.0` and `1.2.9` probes passed separately;
- 13 local Chromium observatory contracts passed, with all 26 executions passing under a two-repeat order-isolation run; the hosted browser job is configured but has not run;
- latest-code manual Chromium verification of LangGraph JSON import; NDJSON, AG-UI, Demo, sequence-20 seek, Fork, and Compare remain earlier same-day manual evidence;
- real LangGraph `1.1.0` and `1.2.9` runtime probes across `tasks`, `messages`, `updates`, `values`, `checkpoints`, and `custom`.

## Next milestones

1. Finish visual Phase -1: add run identity labels, per-field memory observation provenance, complete reduced-motion/keyboard/DOM mirrors, and checked-in visual baselines described in [VISUAL_SYSTEM.md](VISUAL_SYSTEM.md).
2. Build the renderer-independent `VisualModel`, deterministic animation contract, PixiJS 8 vertical slice, and same-scene Phaser 4.2.1 benchmark. Publish measurements before selecting the migration path.
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

- Added an isolated Playwright 1.61.1 Chromium harness on `127.0.0.1:8878`, an official-registry exact lock file, and an independent GitHub Actions browser job. Hosted execution remains pending.
- Established an explicit `1600x1000` viewport after a RED test proved the device descriptor had silently produced `1280x720`.
- Split transport connection from timeline head/history and follow/pause: terminal runs no longer show or blink as `LIVE`.
- Marked completed, failed, interrupted, and cancelled worlds as terminal; unresolved chamber activity is static and explicit, while terminal Canvas/ticker motion is frozen.
- Preserved terminal context-overflow warnings while disabling their infinite CSS pulse.
- Replaced initial and runtime missing cognition telemetry with `NOT OBSERVED` rather than synthetic `0/IDLE` values.
- Made timeline cursor events the default causal root, refreshed an open Causal panel on seek, and rejected stale cross-run/event/direction responses.
- Added run/request epochs plus cancellation so delayed world responses cannot overwrite a newly selected run.
- Added ARIA tab/tabpanel state plus roving left/right keyboard navigation for the Inspector.
- Proved browser order isolation with a two-repeat run: 26/26 executions passed. The ordinary suite passed 13/13 in 34.3 seconds.
- Remaining Phase -1 work is explicit: selector identity/status labels, per-layer memory observation provenance, full reduced-motion CSS, panel/view/follow keyboard semantics, Canvas entity DOM mirror, and screenshot baselines.

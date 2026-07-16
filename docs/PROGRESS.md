# Project progress

## Current state

Agent Anthill `0.5.0` is a runnable local alpha with a versioned canonical event protocol, tamper-evident JSONL ledger, deterministic projection/snapshots, explicit causal inspection, historical playback, no-side-effect materialized forks, normalized run comparison, Python/OTLP/OpenInference/AG-UI inputs, cursor-specific instrumentation visibility, and a Canvas + DOM observatory UI.

Current verified baseline:

- Python, OTLP/OpenInference, and AG-UI JSON/NDJSON adapters;
- metadata-only default with explicit truth/fidelity levels;
- 12 semantic chambers plus Source Archive, Quality Gate, and Unknown Fog;
- live SSE, gap recovery, time travel, compare, snapshot fallback, branch provenance, and hash verification;
- Apache-2.0 community files, multi-version CI, and hardened Docker/Compose definition;
- real browser verification of Demo, sequence-20 time travel, Fork, 50% Compare, and AG-UI file import.

## Next milestones

1. Add a standard live OTLP receiver and AG-UI stream bridge with bounded ingestion/backpressure.
2. Add native LangGraph, Claude Code, and Codex hooks with published capability contracts.
3. Add queryable monitoring rules/exports and very-long-run server-side pagination.
4. Replace materialized long-run branches with reference-based parent snapshot + tail DAG storage.
5. Add sandboxed stub replay before considering any real rerun.

## Session log

### 2026-07-16 — evidence-first alpha foundation

- Replaced the entertainment-only projection with a canonical truth-aware runtime event model and append-only ledger.
- Added reducers, snapshots, branching, comparison, causal slices, OTLP/OpenInference, synthetic fixture, and the new Anthill UI.
- Added AG-UI JSON/NDJSON mapping and browser import, including explicit ID-based causality and default redaction of messages/state/tools/errors/reasoning values.
- Found and fixed the timeline slider race through a real Playwright RED→GREEN path; historical and Compare cursors now use the requested value.
- Found and fixed cached Source X-Ray analysis skipping later persistence requests and leaking prior persistence metadata.
- Added non-root/read-only Docker/Compose configuration and a CI container smoke job. Local Docker execution remains pending because Docker is unavailable on this workstation.
- Added environment and assumption-validation records.
- Added a fourth `COVERAGE` inspection layer that distinguishes observed domains, observable-but-not-seen domains, contract-external domains, blind spots, unregistered adapters, and Unknown Fog types without manufacturing a percentage.
- Initialized local Git history on `main`; no remote or public repository has been created.

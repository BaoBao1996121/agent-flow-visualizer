# Product principles

## North star

Agent Anthill exists to reduce **Time to Correct Mental Model**: the time needed for a user to correctly explain how an Agent system entered, planned, routed, called tools, assembled context, used memory, compacted information, delegated work, recovered, and produced an artifact.

The target evaluation is not “did users enjoy the animation?” It is:

- after 20 minutes, can a user answer at least 7 of 8 mechanism questions correctly;
- is that at least 50% faster than README + logs + source alone;
- do 100% of emitted semantic objects pass a machine-verified route to an
  event/event set, declaration, derived projection, or Coverage/Unknown
  explanation;
- can users complete at least 95% of preregistered evidence-route tasks inside
  their time budget;
- does core semantic classification reach at least 90% precision on human-labelled golden traces;
- are unknown and inferred areas recognizable without opening a manual;
- does tracing stay below 5% overhead for supported native adapters under the published benchmark fixture.

These are product hypotheses until repeated user studies publish the evidence.

## Five non-negotiable principles

### 1. Truth before theatre

Every semantic animation must answer a real question. If a visual state has no
event/event set, declaration, or documented derived projection, it must be shown as unknown. A
beautiful false state is a bug. Decorative motion carries no Agent state, is
not interactive, is hidden from assistive technology, and never enters an
Evidence denominator.

The renderer decision, deterministic animation contract, LOD, accessibility, asset provenance, benchmark, cost, and rollback gates are specified in [VISUAL_SYSTEM.md](VISUAL_SYSTEM.md). Its performance targets remain initial gates until measured evidence is published.

### 2. Metaphor must be reversible

The user can move from chamber → entity → typed Evidence target. Event-backed
targets may continue to explicit causal parents/spans, source references, and
raw artifacts. A Coverage/Unknown target instead explains why evidence is
absent or outside the capture contract; it never invents a parent, span, or
source. The metaphor can compress information but cannot erase provenance.

### 3. Sequence is not causality

Timeline order, span parentage, inferred dependency, and counterfactually verified causality use different visual grammar and different data fields.

### 4. Static potential and executed reality coexist

AST/configuration explains what may happen. Runtime trace explains what did happen in one path. Neither replaces the other, and their coverage must be visible.

### 5. Local-first is the default trust boundary

Prompt, memory, tool result, and source content remain local unless a user explicitly opts into another deployment model. Metadata-only capture is the default.

## Primary users

1. Engineers evaluating several Agent repositories per week.
2. Framework maintainers debugging instrumentation and state transitions.
3. Researchers comparing Agent mechanisms on reproducible tasks.
4. Course authors and teams onboarding engineers into unfamiliar Agent systems.

Production operations is a later user group. The semantic layer must prove accuracy before the product becomes an alerting authority.

## Four product modes

### Learn

Fixed commit + fixed task + fixed trace + guided chapters. Users pause, predict the next transition, inspect evidence, and compare their model with the recorded mechanism.

### Live

Native hooks, canonical events, or telemetry adapters update the same world reducer. Instrumentation coverage and gaps are part of the UI.

The current LangGraph integration imports captured StreamPart v2 files. File import is an inspection workflow, not a live framework connection; a capture bridge remains future work.

### Compare

Two Agents receive the same task/tool fixture and replay in synchronized time. The product highlights genuine differences in state ownership, context, checkpoints, cost, and outcomes.

The current implementation compares recorded runs by normalized ledger progress and marks whether `project_id` and `task_id` overlap. Matching IDs improve comparability but do not alone prove that model, tool fixture, code, or environment were controlled.

### X-Ray / causal

Users inspect raw events and explicit causal links. A later sandboxed mode will intervene at a checkpoint and rerun only downstream work; one replay will never be presented as universal causal proof.

## Semantic zoom

- **L0 — World:** chambers, aggregate flows, run status, alerts, uncertainty.
- **L1 — Stage:** Agent lanes and grouped model, tool, context, memory, and
  checkpoint work.
- **L2 — Operation:** individual tasks, calls, state changes, measurements, and
  explicit causal edges.
- **L3 — Evidence:** the typed event/event set, declaration, derived projection,
  or Coverage/Unknown target, plus available payload structure, source, span,
  artifact, and ledger-hash links.

Long traces must collapse by semantic stage before they become graph hairballs.

## Current scope

The current implementation proves the event kernel, Python,
OTLP/OpenInference, AG-UI JSON/NDJSON, and LangGraph StreamPart v2 offline
paths; event schema `0.2.0`; a single-process local ledger; snapshot-accelerated
deterministic projection under reducer `0.4.0`; time travel, comparison,
explicit causal slicing, cursor-specific instrumentation visibility, and the
first pixel observatory. LangGraph `1.1.0` and `1.2.9` pass isolated real-runtime
probes.

Selector identity is a ledger-HEAD monitoring aid, not a historical
projection. Cursor-specific world and Compare states remain the authority for
“what was true at this point.” Lightweight run discovery maximizes observatory
availability around damaged ledgers; it reports `not_checked` and is not an
integrity authority. Full per-run integrity remains an explicit operation.

The current local evidence is 387 passing Python tests in 19.68 seconds (plus
one optional skip), 49/49 Chromium contracts in 2.0 minutes, and 98/98 browser
executions in 4.4 minutes under two repeats. Full-repository Ruff, nine
JavaScript syntax checks, and patch hygiene pass. Visual fixture/contract tests
pass 7/7, and all four scenes reach their screenshot boundary with
`--ignore-snapshots`; that is local functional scene evidence, not Linux golden
comparison.

Protected-main release GitHub Actions
[run 29639913312](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29639913312)
at `v0.7.0` commit `6b503a6` passed all nine jobs, including the current 49-contract suite,
hardened container, and pinned-Linux comparison against the four reviewed
goldens. It did not update the files, and the check is now required by strict,
administrator-enforced `main` protection. The earlier promotion, failed, and candidate-stage
runs remain recorded for provenance in
[the verification record](VERIFICATION.md), as do the exact dated commands,
timings, and limitations.

It does not yet prove:

- arbitrary repository import;
- production multi-process ingestion;
- complete framework coverage;
- framework-native LangGraph live capture;
- low-latency operation on very long ledgers (the JSONL reference store scans
  growing bytes on every append);
- deterministic real-model rerun;
- counterfactual causality;
- multi-tenant authorization or hosted trace storage.

## Explicit non-goals

- A visual workflow editor.
- A replacement for source code or raw telemetry.
- Displaying private chain-of-thought.
- Copying the visual identity or assets of a commercial game.
- Pretending all frameworks share identical semantics.
- Calling an LLM once per event to guess labels.

## Community quality signal

Stars are a distribution outcome, not a quality metric. The healthier milestone is five external adapters or exhibits with golden fixtures, known-blind-spot documentation, and conformance tests. A gallery full of reproducible traces matters more than a gallery full of screenshots.

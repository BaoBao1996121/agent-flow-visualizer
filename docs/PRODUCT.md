# Product principles

## North star

Agent Anthill exists to reduce **Time to Correct Mental Model**: the time needed for a user to correctly explain how an Agent system entered, planned, routed, called tools, assembled context, used memory, compacted information, delegated work, recovered, and produced an artifact.

The target evaluation is not “did users enjoy the animation?” It is:

- after 20 minutes, can a user answer at least 7 of 8 mechanism questions correctly;
- is that at least 50% faster than README + logs + source alone;
- can at least 95% of visible semantic objects reach a source event or explicit source declaration;
- does core semantic classification reach at least 90% precision on human-labelled golden traces;
- are unknown and inferred areas recognizable without opening a manual;
- does tracing stay below 5% overhead for supported native adapters under the published benchmark fixture.

These are product hypotheses until repeated user studies publish the evidence.

## Five non-negotiable principles

### 1. Truth before theatre

Every animation must answer a real question. If a visual state has no event or declaration, it must be shown as unknown. A beautiful false state is a bug.

### 2. Metaphor must be reversible

The user can move from chamber → entity → event → causal parent/span → source reference/raw artifact. The metaphor can compress information but cannot erase provenance.

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

### Compare

Two Agents receive the same task/tool fixture and replay in synchronized time. The product highlights genuine differences in state ownership, context, checkpoints, cost, and outcomes.

The current implementation compares recorded runs by normalized ledger progress and marks whether `project_id` and `task_id` overlap. Matching IDs improve comparability but do not alone prove that model, tool fixture, code, or environment were controlled.

### X-Ray / causal

Users inspect raw events and explicit causal links. A later sandboxed mode will intervene at a checkpoint and rerun only downstream work; one replay will never be presented as universal causal proof.

## Semantic zoom

- **L0 — World:** chambers, actors, bottlenecks, context pressure, incidents.
- **L1 — Stage:** plan step, model call, tool execution, handoff, compaction job.
- **L2 — Event:** canonical envelope, state diff, measurement, evidence level.
- **L3 — Source:** raw telemetry/artifact hash, span, source file and line.

Long traces must collapse by semantic stage before they become graph hairballs.

## Current scope

The current implementation proves the event kernel, Python, OTLP/OpenInference, and AG-UI JSON/NDJSON paths, local ledger, snapshot-accelerated deterministic projection, time travel, comparison, explicit causal slicing, cursor-specific instrumentation visibility, and the first pixel observatory. It does not yet prove:

- arbitrary repository import;
- production multi-process ingestion;
- complete framework coverage;
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

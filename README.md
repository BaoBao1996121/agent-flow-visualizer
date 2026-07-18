# Agent Anthill

**A truth-aware, time-travel observatory for AI agents.**
把 Agent 的任务、工具、上下文、记忆、压缩、协作与错误恢复，投影成一个可以逐层钻取证据的像素蚁巢。

![Agent Anthill overview](docs/assets/anthill-overview.png)

> Alpha · application `0.6.0` · event protocol `0.2.0` · reducer `0.4.0` · measurement contract `1.0.0` · coverage contract `0.3.0`
> Python runtime tracing plus OTLP/OpenInference, AG-UI, and LangGraph StreamPart v2 offline import work today. Framework-native live bridges remain the next expansion, not a claim hidden behind the UI.

Most agent visualizers answer “what looks busy?” Agent Anthill is built to answer harder questions:

- What **actually happened**, in authoritative ingest order?
- Which state is observed, declared in code, inferred, or counterfactually verified?
- Why did an agent move from planning to a tool, hand off work, compact context, or recover from an error?
- What did compaction keep, replace, and remove?
- Can every visual object lead back to its event, span, source line, payload, and hash-chain evidence?
- What did the system look like at event 17—not only at the end?

The pixel world is a semantic projection over an append-only event ledger. It is not the source of truth.

## What works now

- Original 12-chamber pixel world rendered locally with Canvas; no copied game assets.
- Four truth levels with distinct visual grammar:
  - `observed` — captured directly at runtime;
  - `declared` — explicit in source/configuration;
  - `inferred` — fallible interpretation, always below 100% confidence;
  - `counterfactual_verified` — validated by a recorded intervention and rerun.
- Canonical, versioned `AgentRuntimeEvent` envelope with causal links, clocks, source fidelity, privacy policy, artifacts, measurements, and extensions.
- Python AST importer that keeps code declarations separate from semantic classification.
- Python `sys.settrace` runtime adapter that preserves observed calls and emits semantic hints as separate inferred events.
- OTLP JSON/OpenInference importer for `AGENT`, `LLM`, `TOOL`, `RETRIEVER`, `RERANKER`, `EMBEDDING`, `GUARDRAIL`, and `EVALUATOR` spans, with convention/version retention and content redaction.
- AG-UI JSON/NDJSON importer for run, step, message, tool, shared state, activity, and public reasoning-summary lifecycles. Explicit stream IDs become causal/correlation links; content and encrypted reasoning values are redacted by default.
- LangGraph StreamPart v2 JSON/NDJSON importer for `tasks`, `messages`, `updates`, `values`, `checkpoints`, and `custom`. Its LangGraph 1.x compatibility floor is `1.1.0`; the configured supported lane is `>=1.2,<2`, with real probes at `1.1.0` and `1.2.9`.
- Truth-preserving LangGraph interruption mapping: task interruption stays `agent.step.interrupted`; the first explicit interrupt ID in a namespace becomes `human.interrupt`; repeated observations become linked `langgraph.interrupt.reobserved` events; checkpoint interrupt snapshots remain separate evidence.
- In-process thread-safe, single-process JSONL reference ledger with duplicate rejection, monotonic ingest sequence, a SHA-256 event chain, and explicit integrity verification. Every append hashes the current ledger bytes; full JSON/sequence/duplicate/hash-chain validation runs on first access or changed content. Very long and multi-process production ingestion still requires a transactional store.
- Rebuildable per-run manifest caches with an unkeyed cache checksum, lifecycle-derived HEAD status, and privacy-safe discovery diagnostics. A checksum-valid non-empty manifest quarantines a shortened, emptied, or missing ledger instead of silently reusing sequence numbers. The run-list endpoint reports `integrity_status: not_checked`; full-chain health belongs to the per-run integrity endpoint.
- Deterministic world reducer and historical projection at any ingest sequence.
- Immutable, reducer-versioned world snapshots anchored to ledger event hashes; corrupt caches are ignored and recomputed from the ledger.
- Side-effect-free materialized forks from any timeline cursor, with parent event/state hashes and remapped provenance links.
- Explicit causal slices that never turn temporal adjacency into causation.
- Cursor-specific instrumentation visibility: domains with recorded signals, registered adapter capabilities, declared blind spots, unregistered adapters, and Unknown Fog types—without a misleading aggregate score.
- Synchronized two-run comparison with normalized progress, mechanism/metric diffs, and comparability warnings when project/task keys do not match.
- Context budget, memory layers, compaction lineage, handoff, checkpoint, artifacts, usage, and incident projections.
- Owner-aware safe measurement aggregation: raw usage remains inspectable, while Meter and numeric Compare accept only versioned scope/unit/temporality/owner semantics; incompatible pricing is `NOT COMPARABLE`.
- FastAPI ingestion/query/replay/integrity APIs plus live SSE with gap detection and ledger resync.
- Source X-Ray view for the original static call graph and real Python execution trace.
- Collision-aware run selectors that show source, ledger-head lifecycle status, UTC ingest date, stable ID, and an explicit synthetic marker; historical world status remains tied to the selected cursor rather than being rewritten by head metadata.
- One-click, clearly labelled **synthetic fixture** covering all core chambers without network or model calls.
- Metadata-only persistence by default; prompt, argument, return, and exception content require explicit opt-in. Metadata identifiers and structural names may still be sensitive.
- The core suite plus an optional real-runtime compatibility test cover schema invariants, privacy, adapters, time travel, snapshots, branching, comparison, causality, instrumentation visibility, tamper detection, concurrent append, API behavior, malformed runtime objects, and StreamPart v2 compatibility. The dated count and commands live in [the verification record](docs/VERIFICATION.md).

## Quick start

The supported Python matrix is 3.11–3.13.

```bash
python -m venv .venv
```

Activate it with the command for your shell:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```bat
:: Windows Command Prompt
.venv\Scripts\activate.bat
```

```bash
# macOS, Linux, or Git Bash
source .venv/bin/activate
```

Then install and run:

```bash
python -m pip install -r requirements.txt
python server.py
```

Open <http://127.0.0.1:8765> and click **一键展品**. The fixture is marked `SYNTHETIC FIXTURE` in both its manifest and every event.

For a real local Python trace, open <http://127.0.0.1:8765/graph>, analyze `samples`, select an entry point, and run **实时运行**. The trace endpoint persists a metadata-only Anthill run by default.

To inspect a captured LangGraph run, open the Anthill import menu and select **LANGGRAPH v2**. This imports an existing capture; it does not subscribe to a running graph. Dated local and hosted evidence, including the exact commit and workflow version covered, lives in [verification](docs/VERIFICATION.md).

Or run the hardened local container profile:

```bash
docker compose up --build
```

The Compose profile binds only to `127.0.0.1:8765`, runs as a non-root user with a read-only root filesystem, and persists ledgers in the `anthill-data` volume. CI validates the Compose model, builds the image, and exercises a runtime smoke on GitHub's Ubuntu runner. Dated local and hosted results belong in [the environment checklist](docs/ENVIRONMENT_CHECKLIST.md), not in this long-lived capability statement.

## The trust contract

```text
pixel object
  └─ world projection @ reducer_version + ingest_seq
      └─ canonical event_id + explicit causation/link
          └─ source adapter + fidelity + confidence
              └─ raw event / trace span / source line / artifact hash
```

Unknown information stays in **Unknown Fog**. Missing telemetry never becomes a confident animation. The project does not expose private chain-of-thought; it only renders framework-provided plans, reasoning summaries, and observable operations.

## Visibility without absence claims

![Agent Anthill instrumentation visibility](docs/assets/anthill-coverage.png)

The `COVERAGE` inspector answers two separate questions: which semantic domains have evidence at this timeline cursor, and which domains each registered adapter is designed to observe. It also lists declared blind spots, unregistered adapters, and unmapped event types. It intentionally emits no aggregate percentage: “observable but not seen” is not proof that an operation did not occur.

## Architecture

```mermaid
flowchart LR
    A[Native hooks / Python trace] --> N[Adapter + normalizer]
    B[Canonical HTTP events] --> N
    C[OTLP / OpenInference / AG-UI / LangGraph v2] --> N
    N --> V[Schema validation / privacy / ordering]
    V --> L[Append-only event ledger]
    L --> I[Integrity verifier]
    L --> R[Versioned world reducer]
    R --> W[Pixel world / timeline / inspector]
    L --> T[Time-travel replay]
    L --> G[Explicit causal slice]
    L --> S[SSE live stream]
```

The current local store is JSONL for inspection and shareable exhibits. Its interface is deliberately small so a PostgreSQL + outbox backend can replace it for multi-process production ingestion. Kafka is not required for the local-first product.

Read [architecture](docs/ARCHITECTURE.md), [event protocol](docs/EVENT_PROTOCOL.md), [adapter guide](docs/ADAPTER_GUIDE.md), and [visual system](docs/VISUAL_SYSTEM.md) before adding a framework or renderer integration.

## Ingest canonical events

Any runtime can integrate today by posting canonical events. Native adapters should preserve the original semantic-convention version in `source`.

The repository includes a validated request body at `samples/canonical_event_batch.json`.
Protocol `0.2.0` requires each newly written `run_id` to be a display-stable,
single API path segment: no edge whitespace, Unicode control/format characters,
path separators, URL delimiters `/`, `\`, `?`, `#`, `%`, or exact `.`/`..`
segments. Existing `0.1.0` ledgers remain readable only through the store's
private compatibility path; compatibility never weakens new API writes.
On macOS, Linux, or Git Bash:

```bash
curl --request POST http://127.0.0.1:8765/api/anthill/runs/example/events --header "Content-Type: application/json" --data-binary @samples/canonical_event_batch.json
```

On Windows PowerShell or Command Prompt, call the executable explicitly so PowerShell does not resolve the historical `curl` alias:

```powershell
curl.exe --request POST http://127.0.0.1:8765/api/anthill/runs/example/events --header "Content-Type: application/json" --data-binary "@samples/canonical_event_batch.json"
```

Useful endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /api/anthill/schema` | Protocol vocabulary and truth contract |
| `GET /api/anthill/runs` | Lightweight HEAD discovery with bounded diagnostics; not a full integrity verdict |
| `POST /api/anthill/runs/{run_id}/events` | Validated batch ingestion |
| `POST /api/anthill/import/otlp` | OTLP JSON/OpenInference span import |
| `POST /api/anthill/import/agui` | AG-UI JSON or NDJSON event import |
| `POST /api/anthill/import/langgraph` | LangGraph 1.x StreamPart v2 JSON or NDJSON import; floor `1.1.0`, tested `1.1.0` and `1.2.9` |
| `GET /api/anthill/runs/{run_id}/events` | Ordered, paginated event query |
| `GET /api/anthill/runs/{run_id}/event?event_id={opaque_id}` | Canonical single-event lookup for any 1–256 character event ID |
| `GET /api/anthill/runs/{run_id}/world?at_seq=17` | Historical world plus cursor-specific instrumentation visibility |
| `POST/GET /api/anthill/runs/{run_id}/snapshots` | Create/inspect projection snapshots |
| `POST /api/anthill/runs/{run_id}/fork` | Materialize a no-rerun branch at a cursor |
| `GET /api/anthill/runs/{run_id}/replay` | Replay window with initial/final state |
| `GET /api/anthill/runs/{run_id}/causal?event_id={opaque_id}` | Canonical explicit causal neighborhood lookup |
| `GET /api/anthill/runs/{run_id}/integrity` | Full hash-chain verification |
| `GET /api/anthill/runs/{run_id}/stream` | SSE live events with sequence-gap recovery |
| `GET /api/anthill/compare` | Normalized two-run mechanism comparison |
| `POST /api/anthill/demo` | No-network synthetic exhibit |

The deprecated `/events/{event_id}` and `/causal/{event_id}` forms remain for
path-safe client compatibility, but new clients must use the query forms. An
opaque event ID may legally be `.`, `..`, or contain URL-reserved characters;
browsers normalize some such path segments before the request reaches the API.
Query encoding is routing, not encryption: sensitive source IDs should be
stably hashed by an adapter because URLs can enter browser history and access,
proxy, or APM logs.

Interactive API documentation is available at `/docs`.

## Semantic chambers

| Chamber | Canonical domains |
|---|---|
| Control Nest | run, agent, task, plan, decision, policy |
| Context Assembly | manifest items, token budget, truncation, overflow |
| Model Engine | request, stream, cache, retry, fallback, usage |
| Tool Workshop | request, approval, execution, side effect, retry |
| Retrieval Depot | query, candidates, rerank, selected documents |
| Memory Vault | working, episodic, semantic memory operations |
| Compaction Plant | trigger, summary, replacements, kept/removed lineage |
| Handoff Bridge | proposal, acceptance, ownership, context manifest |
| Checkpoint Station | create, restore, fork, commit, invalidate |
| Artifact Foundry | files, reports, code, structured outputs |
| Incident Bay | failure, timeout, cancellation, recovery |
| Meter Room | token, duration, cost, and budget measurements |

Source Archive shows code-level events; unmapped extensions remain in Unknown Fog until an adapter or projector explicitly understands them.

## Compare without causal overclaiming

![Agent Anthill synchronized comparison](docs/assets/anthill-compare.png)

Compare mode synchronizes two ledgers by normalized progress and reports mechanism, metric, and event-vocabulary differences. Shared `project_id` and `task_id` are surfaced as comparability keys; a mismatch produces a warning. Matching keys still do not prove that model version, tool fixture, code, or environment were controlled.

## Development

```bash
python -m pip install -r requirements-dev.txt
npm ci
npx playwright install chromium
python -m pytest -q
python -m ruff check --no-cache .
node --check static/js/anthill.js
node --check static/js/app.js
node --check static/js/graph.js
node --check static/js/simulation.js
node --check playwright.config.mjs
node --check tests/browser/anthill-phase1.spec.mjs
npm run test:browser
```

The browser contract starts its own loopback server at `127.0.0.1:8878`, refuses
to reuse an existing process, and writes to an isolated ignored ledger under
`output/playwright/`. It does not connect to or modify the user-facing `8765`
service. Linux and CI should install the browser plus system dependencies with
`npx playwright install --with-deps chromium`.

Playwright HTML reports, traces, and screenshots can contain page and request
data. Browser fixtures must therefore be synthetic, public, or explicitly
licensed/approved; do not point the suite at a private real trace.

The dependency-free Chrome DevTools helper can capture the UI for visual review with Node.js 22+:

```bash
node scripts/cdp_capture.mjs <websocket-url> output.png http://127.0.0.1:8765/?static=1
```

See the checked [environment matrix](docs/ENVIRONMENT_CHECKLIST.md) for verified versions and explicitly pending runtime dependencies, and [the dated verification record](docs/VERIFICATION.md) for commands, results, and evidence limits.

The renderer migration is governed by the [visual-system decision](docs/VISUAL_SYSTEM.md). Its performance budgets are initial gates marked for measurement; the project does not claim unmeasured PixiJS or Phaser performance.

## Roadmap

Near-term, in order:

1. Finish the Phase -1 release gate: review the four digest-pinned Linux candidates, commit only accepted goldens, switch CI from non-blocking update mode to required comparison mode, and prove it passes without rewriting them. All eight semantic corrections in [VISUAL_SYSTEM.md](docs/VISUAL_SYSTEM.md) have implementation coverage; pixel-regression protection is not claimed until this promotion succeeds.
2. Introduce a renderer-independent `VisualModel` and deterministic animation-intent contract; build the bounded PixiJS 8 vertical slice and same-scene Phaser 4.2.1 benchmark before choosing a migration path.
3. Add OTLP protobuf/live collection plus AG-UI and LangGraph live stream bridges with bounded ingestion and backpressure.
4. Add native Claude Code and Codex hook providers with published capability contracts.
5. Add reference-based branch DAG storage, snapshot compaction, queryable monitoring exports, and very-long-run pagination.
6. Add sandboxed stub replay before considering any real rerun.
7. Add PostgreSQL/outbox storage for multi-process deployment and a contributor gallery of reproducible Agent exhibits.

See [product principles](docs/PRODUCT.md) for success criteria and explicit non-goals, and [visual system](docs/VISUAL_SYSTEM.md) for renderer gates, accessibility, provenance, costs, and exit conditions.

## Security and privacy

Agent traces can contain secrets, personal data, source code, and side effects. Agent Anthill is local-first and defaults to metadata-only persistence. Metadata-only is not anonymous: identifiers, namespaces, node names, field names, and source references may still expose private context. Real replay is not implemented yet; recorded tool results are visualization evidence, not permission to repeat an external operation.

Read [security and privacy](docs/SECURITY_AND_PRIVACY.md) and report vulnerabilities according to [SECURITY.md](SECURITY.md).

## Contributing

The most valuable contribution is not another animation. It is a well-specified adapter with:

- a golden trace fixture;
- schema conformance tests;
- known blind spots and instrumentation coverage;
- explicit fidelity and confidence mapping;
- no unlicensed art or private trace content.

Start with [CONTRIBUTING.md](CONTRIBUTING.md).

## License and name

Code is licensed under Apache-2.0. Original UI graphics are generated from project code and covered by the same repository license unless an asset manifest says otherwise.

Agent Anthill is an independent open-source project and is not affiliated with Anthill AI, AnthillPro, or the historical Anthill P2P framework. “Agent Anthill” is the complete project name used here.

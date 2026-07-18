# Environment checklist

Last verified: 2026-07-18 (Asia/Shanghai).

Historical hosted reference: [GitHub Actions run 29629916726](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29629916726) for commit `c39c70a`; all eight jobs passed. It predates reducer `0.4.0` and the current Phase -1 working branch. Current-branch hosted verification and pinned-Linux golden promotion remain pending.

| Dependency / boundary | Required | Local current evidence | Hosted evidence / status |
|---|---:|---|---|
| Python | 3.11–3.13 | Local `Python 3.13.1`; `384 passed, 1 skipped` in 19.87s | Historical run 29629916726: 3.11, 3.12, and 3.13 PASS; current branch pending. |
| FastAPI | `>=0.115,<1` | Imported locally as `0.136.0`; the 384-test suite and browser suite pass | Historical run 29629916726: Python, browser, and container jobs PASS; current branch pending. |
| Pydantic | `>=2.8,<3` | Imported locally as `2.12.5`; schema/API suite passes | Historical run 29629916726: Python matrix PASS; current branch pending. |
| Uvicorn | `>=0.30,<1` | Imported locally as `0.38.0`; isolated loopback browser server passes | Historical run 29629916726: browser and container jobs PASS; current branch pending. |
| Node.js / npm | Node 22+ for project tooling | Node `v22.14.0`, npm `10.9.2`; nine syntax checks, Chromium 49/49, and repeat 98/98 pass | Historical run 29629916726: frontend and 29-contract browser jobs PASS with project Node 22; current branch pending. |
| GitHub action runtime | Current major tags | Workflow uses checkout/setup-python/setup-node `v6` and upload-artifact `v7`; these action majors use Node 24 | Historical run 29629916726 PASS. Tags are not immutable SHA pins; current branch pending. |
| npm lock provenance | Exact package lock with integrity | `package-lock.json` resolves through `https://registry.npmjs.org/`; no npmmirror entry | Historical run 29629916726 completed `npm ci` and passed; current branch pending. |
| Playwright / Chromium | `@playwright/test 1.61.1`, Chromium | Local Chromium `149.0.7827.55`; 49/49 in 2.0m at `1600x1000`, 98/98 in 4.4m under two repeats | Historical run 29629916726: 29-contract job PASS; current 49-contract branch pending. |
| Deterministic visual suite | Playwright 1.61.1, Python 3.12.13, exact server dependencies, and digest-pinned Noble image | Fixture/contract tests 7/7; four scenes pass functionally with `--ignore-snapshots` | Current pinned-Linux candidate run and reviewed goldens pending; no visual-regression protection claimed. |
| AG-UI semantic input | Version retained per payload | Golden JSON/NDJSON and API tests pass | Historical run 29629916726: Python matrix PASS; current branch pending. |
| LangGraph StreamPart v2 | Floor `1.1.0`; supported lane `>=1.2,<2`; optional dependency | Isolated `1.1.0` and `1.2.9` `StateGraph` probes emit all six supported modes and pass normalization | Historical run 29629916726: `1.1.0` floor and supported-1.x jobs PASS; current branch pending. |
| NDJSON structure guard | Maximum nesting 256 | Quote/escape-aware lexical guard and regressions pass | Historical run 29629916726: Python and both LangGraph jobs PASS; current branch pending. Limit remains initial, not benchmark-derived. |
| OTLP JSON/OpenInference | Explicit JSON export | Golden fixture, adapter, encoded-URL, and API tests pass | Historical run 29629916726: Python matrix PASS; current branch pending. |
| JSONL reference store | Single process | Content-digest reuse, full changed-content validation, truncation anchors, and event-loop offload regressions pass | Historical run 29629916726: Python, browser, and container jobs PASS; current branch pending. Not a production throughput or multi-process claim. |
| Docker / Compose | Optional local deployment | Docker CLI unavailable on this workstation | Historical run 29629916726: Compose, build, non-root/read-only, health, and ledger write PASS; current branch pending. |
| External network/model | Not required after install for core demo/replay/tests | Synthetic exhibit, projection, Compare, Fork, and browser tests use no model/network calls | First package/browser installation still requires package-source access. |

Runtime caveats:

- Python tracing executes trusted target code in the server process.
- The JSONL ledger is a single-process local backend. Every append scans the
  current ledger bytes; first use or changed content also performs complete
  JSON/sequence/duplicate/hash-chain validation. Repeated single-event appends
  therefore accumulate `O(k²)` byte scanning.
- `/api/anthill/runs` is lightweight discovery with
  `integrity_status=not_checked`, not a full ledger verification endpoint.
- OTLP protobuf/live collection, AG-UI live subscription, and a LangGraph live capture bridge are not implemented.
- LangGraph `1.0.x` exposes the legacy tuple boundary and is intentionally rejected by the v2 adapter.
- Hosted or multi-tenant deployment requires the controls listed in `SECURITY_AND_PRIVACY.md`.
- Playwright reports, traces, and screenshots may retain page/request data; committed browser fixtures must remain synthetic, public, or explicitly approved.
- Local visual scenes passed only with snapshot comparison disabled. Reviewed pinned-Linux goldens and a required comparison job remain pending.
- Only Chromium is automated; cross-browser and real assistive-technology verification remain pending.

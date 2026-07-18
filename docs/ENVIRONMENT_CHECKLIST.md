# Environment checklist

Last verified: 2026-07-18 (Asia/Shanghai).

Current hosted reference: [GitHub Actions run 29629916726](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29629916726) for commit `c39c70a`; all eight jobs passed.

| Dependency / boundary | Required | Local current evidence | Hosted evidence / status |
|---|---:|---|---|
| Python | 3.11–3.13 | Local `Python 3.13.1`; `326 passed, 1 skipped` | Current run: 3.11, 3.12, and 3.13 PASS. |
| FastAPI | `>=0.115,<1` | Imported locally as `0.136.0`; API and browser suites pass | Current Python, browser, and container jobs PASS. |
| Pydantic | `>=2.8,<3` | Imported locally as `2.12.5`; schema/API suite passes | Current Python matrix PASS. |
| Uvicorn | `>=0.30,<1` | Imported locally as `0.38.0`; isolated loopback browser server passes | Current browser and container jobs PASS. |
| Node.js / npm | Node 22+ for project tooling | Node `v22.14.0`, npm `10.9.2`; syntax and Playwright pass | Current frontend and browser jobs PASS with project Node 22. |
| GitHub action runtime | Current major tags | Workflow uses checkout/setup-python/setup-node `v6` and upload-artifact `v7`; these action majors use Node 24 | Current workflow PASS. Tags are not immutable SHA pins. |
| npm lock provenance | Exact package lock with integrity | `package-lock.json` resolves through `https://registry.npmjs.org/`; no npmmirror entry | Current browser job completed `npm ci` and PASS. |
| Playwright / Chromium | `@playwright/test 1.61.1`, Chromium | Local Chromium `149.0.7827.55`; 29/29 at `1600x1000`, 58/58 under two repeats | Current hosted 29-contract job PASS. |
| AG-UI semantic input | Version retained per payload | Golden JSON/NDJSON and API tests pass | Current Python matrix PASS. |
| LangGraph StreamPart v2 | Floor `1.1.0`; supported lane `>=1.2,<2`; optional dependency | Isolated `1.1.0` and `1.2.9` `StateGraph` probes emit all six supported modes and pass normalization | Current `1.1.0` floor and supported-1.x jobs PASS. |
| NDJSON structure guard | Maximum nesting 256 | Quote/escape-aware lexical guard and regressions pass | Current Python and both LangGraph jobs PASS; limit remains initial, not benchmark-derived. |
| OTLP JSON/OpenInference | Explicit JSON export | Golden fixture, adapter, encoded-URL, and API tests pass | Current Python matrix PASS. |
| JSONL reference store | Single process | Content-digest reuse, full changed-content validation, truncation anchors, and event-loop offload regressions pass | Current Python, browser, and container jobs PASS; not a production throughput or multi-process claim. |
| Docker / Compose | Optional local deployment | Docker CLI unavailable on this workstation | Current container job PASS: Compose, build, non-root/read-only, health, and ledger write. |
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
- Only Chromium is automated; cross-browser and real assistive-technology verification remain pending.

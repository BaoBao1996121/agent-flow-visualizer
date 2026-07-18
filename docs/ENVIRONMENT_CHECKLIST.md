# Environment checklist

Last verified: 2026-07-18 (Asia/Shanghai).

| Dependency / boundary | Required | Local current evidence | Hosted evidence / status |
|---|---:|---|---|
| Python | 3.11–3.13 | Local `Python 3.13.1`; `326 passed, 1 skipped` | Initial run: 3.11 PASS, 3.12/3.13 old-code FAIL on one shared NDJSON assertion. Current branch pending. |
| FastAPI | `>=0.115,<1` | Imported locally as `0.136.0`; API and browser suites pass | Exercised by initial browser/container jobs; current branch pending. |
| Pydantic | `>=2.8,<3` | Imported locally as `2.12.5`; schema/API suite passes | Covered by Python matrix; current branch pending. |
| Uvicorn | `>=0.30,<1` | Imported locally as `0.38.0`; isolated loopback browser server passes | Initial browser/container jobs PASS; current branch pending. |
| Node.js / npm | Node 22+ for project tooling | Node `v22.14.0`, npm `10.9.2`; syntax and Playwright pass | Project runtime remains Node 22. Current branch pending. |
| GitHub action runtime | Current major tags | Workflow uses checkout/setup-python/setup-node `v6` and upload-artifact `v7`; these action majors use Node 24 | Initial run predates the upgrade; current workflow pending hosted verification. Tags are not immutable SHA pins. |
| npm lock provenance | Exact package lock with integrity | `package-lock.json` resolves through `https://registry.npmjs.org/`; no npmmirror entry | Browser job uses `npm ci`; initial old-code job PASS. |
| Playwright / Chromium | `@playwright/test 1.61.1`, Chromium | Local Chromium `149.0.7827.55`; 29/29 at `1600x1000`, 58/58 under two repeats | Initial 13-contract job PASS. Current 29-contract job pending. |
| AG-UI semantic input | Version retained per payload | Golden JSON/NDJSON and API tests pass | Covered indirectly by Python matrix; current branch pending. |
| LangGraph StreamPart v2 | Floor `1.1.0`; supported lane `>=1.2,<2`; optional dependency | Isolated `1.1.0` and `1.2.9` `StateGraph` probes emit all six supported modes and pass normalization | Initial two jobs reached tests but failed on the same now-fixed shared NDJSON assertion; no current green hosted result yet. |
| NDJSON structure guard | Maximum nesting 256 | Quote/escape-aware lexical guard and regressions pass | Initial conservative limit, not benchmark-derived; current matrix pending. |
| OTLP JSON/OpenInference | Explicit JSON export | Golden fixture, adapter, encoded-URL, and API tests pass | Covered indirectly by Python matrix; current branch pending. |
| JSONL reference store | Single process | Content-digest reuse, full changed-content validation, truncation anchors, and event-loop offload regressions pass | Not a production throughput or multi-process claim. Current matrix pending. |
| Docker / Compose | Optional local deployment | Docker CLI unavailable on this workstation | Initial hosted container job PASS, including non-root/read-only/health/ledger write. Current branch pending. |
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

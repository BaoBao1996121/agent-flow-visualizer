# Environment checklist

Last verified: 2026-07-17 (Asia/Shanghai).

| Dependency / boundary | Required | Verification evidence | Status |
|---|---:|---|---|
| Python | 3.11–3.13 | Local `Python 3.13.1`; CI matrix declares 3.11, 3.12, 3.13 | Local PASS; CI pending first push |
| FastAPI | `>=0.115,<1` | Imported locally as `0.136.0`; API/browser smoke passed | PASS |
| Pydantic | `>=2.8,<3` | Imported locally as `2.12.5`; schema suite passed | PASS |
| Uvicorn | `>=0.30,<1` | Imported locally as `0.38.0`; loopback server smoke passed | PASS |
| Node.js / npm | Node 22+ for static/browser tooling | Local Node `v22.14.0`, npm `10.9.2`; syntax checks and `npm ci --ignore-scripts` passed | PASS |
| npm lock provenance | Exact package lock with integrity | `package-lock.json` resolves through `https://registry.npmjs.org/`; no npmmirror entry | PASS |
| Playwright / Chromium | `@playwright/test 1.61.1`, Chromium project | Local Chromium `149.0.7827.55`; 13/13 contracts passed at `1600x1000`, and 26/26 passed under two repeats | Local PASS |
| Hosted browser boundary | GitHub Ubuntu, Python 3.12, Node 22, Chromium | `browser` job installs runtime/npm/browser dependencies, rejects focused/flaky tests, and uploads seven-day diagnostics | CONFIGURED; hosted run PENDING |
| AG-UI semantic input | Version retained per payload | Official event/serialization references fetched; golden JSON and NDJSON tests passed | PASS for offline import |
| LangGraph StreamPart v2 | LangGraph 1.x only for producing a v2 capture; floor `1.1.0`, configured supported lane `>=1.2,<2`, not a core dependency | Isolated real `StateGraph` probes under `1.1.0` and `1.2.9` emitted all six supported modes; adapter/API tests passed; latest-code local manual Chromium covered JSON, while NDJSON is earlier same-day manual evidence | PASS for offline import; hosted run pending |
| OTLP JSON/OpenInference | Explicit JSON export | Golden OTLP fixture and adapter/API tests passed | PASS for JSON import |
| Docker / Compose | Optional local deployment | Docker CLI is not installed on this workstation; the workflow is configured to build and smoke-test the image on GitHub's Ubuntu runner, but no hosted run exists yet | PENDING first hosted CI/runtime verification |
| External network/model | Not required to execute installed core demo/replay/tests | Synthetic exhibit, projection, compare, fork, and browser tests use no model/network calls; first npm/Chromium installation still requires package-source access | PASS with install-time network caveat |

Runtime caveats:

- Python tracing executes trusted target code in the server process.
- The JSONL ledger is a single-process local backend.
- OTLP protobuf/live collection, AG-UI live subscription, and a LangGraph live capture bridge are not implemented.
- LangGraph `1.0.x` exposes the legacy tuple boundary and is intentionally rejected by the v2 adapter.
- Hosted or multi-tenant deployment requires the controls listed in `SECURITY_AND_PRIVACY.md`.
- Playwright reports, traces, and screenshots may retain page/request data; committed browser fixtures must remain synthetic, public, or explicitly approved.
- Only Chromium is automated; cross-browser and real assistive-technology verification remain pending.

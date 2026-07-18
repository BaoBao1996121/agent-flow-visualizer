# Environment checklist

Last verified: 2026-07-19 (Asia/Shanghai).

Published release reference: [GitHub Actions run 29639913312](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29639913312) for protected-main commit `6b503a6`; all nine jobs passed, including the 49-contract Chromium lane, hardened container, and pinned-Linux visual comparison with updates disabled. `main` protection was read back with strict status checks, administrator enforcement, and all nine GitHub Actions contexts required. Release `v0.7.0` points to that exact commit.

| Dependency / boundary | Required | Local current evidence | Hosted evidence / status |
|---|---:|---|---|
| Python | 3.11–3.13 | Local `Python 3.13.1`; Phase C candidate `455 passed, 1 skipped` in 46.86s | Protected-main run [29653577169](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29653577169): 3.11, 3.12, and 3.13 PASS on `6b36444`. |
| PyYAML test parser | `>=6.0.3,<7` | Local `6.0.3`; semantic staged-workflow contract tests pass | PyPI lists 6.0.3 wheels/classifiers for Python 3.11–3.13; protected-main run [29645305313](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29645305313) installed `requirements-dev.txt` and passed the semantic contract. |
| FastAPI | `>=0.115,<1` | Imported locally as `0.136.0`; the Phase C 455-test branch suite and `@s0` browser vertical pass | Protected-main run 29653577169: Python, Chromium, visual regression, and container jobs PASS. |
| Pydantic | `>=2.8,<3` | Imported locally as `2.12.5`; schema/API suite passes | Run 29639913312: Python matrix PASS. |
| Uvicorn | `>=0.30,<1` | Imported locally as `0.38.0`; isolated loopback browser server passes | Run 29639913312: browser, visual regression, and container jobs PASS. |
| Node.js / npm | Node 22+ for project tooling | Node `v22.14.0`, npm `10.9.2`; nine syntax checks, Chromium 49/49, and repeat 98/98 pass | Run 29639913312: frontend and 49-contract browser jobs PASS with project Node 22. |
| GitHub action runtime | Current major tags | Workflow uses checkout/setup-python/setup-node `v6` and upload-artifact `v7`; these action majors use Node 24 | Run 29639913312: all nine jobs PASS. Tags are not immutable SHA pins. |
| GitHub aggregate shell | Bash plus `jq` | Not required by local product runtime | Official Ubuntu 24.04 runner inventory currently includes `jq 1.7`; the aggregate fails closed if the tool is unavailable. |
| npm lock provenance | Exact package lock with integrity | `package-lock.json` resolves through `https://registry.npmjs.org/`; no npmmirror entry | Run 29639913312 completed `npm ci` in frontend, browser, and visual jobs. |
| Renderer dependency preflight | Candidate `pixi.js@8.19.0`; peer `phaser@4.2.1` | Both resolve with integrity through explicit `https://registry.npmjs.org/`; configured workstation mirror returns 404 for Phaser 4.2.1 | No renderer dependency is committed yet. A future isolated benchmark must commit its lockfile and resolved URL/integrity evidence. |
| Phase 0 Visual Lab VA0 | No new runtime renderer or asset-tool dependency | Isolated DOM/SVG lab loads from canonical APIs. Stable Chromium 25/25, exact S0 1/1, affected Python 58/58, Ruff/spikes/Node syntax PASS. Final local 1600x1000 screenshot is 249,107 bytes, SHA-256 `07154927e9ab15980ba4596b50b2e8f7766de78b20388420fa26687709e176cd`; 12 zones and 12 entities render, the addressed run is not clipped, and entity label clipping is zero. | Ready run 29659548968 and protected-main run [29659786458](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29659786458) passed all 11 jobs. Six exact 1600×1000 attachments were reviewed; artifact digest is `4ba200b7ed5fd53ed643986951e7451f59096cd932867e62a3db573247b71519`. |
| Phase 0 Visual Lab VA1 | Pinned Chromium plus local HTML/CSS/SVG; no runtime route or engine | `file:`/Grid/`color-mix()`/clip-path preflight PASS; exact S0 1/1 and complete concept-board slice 2/2 PASS. Three directions make only local requests. Corrected focus screenshot is 1600×1000, 218,786 bytes, SHA-256 `4f0eff7130bbce47bf496ca8a9c85d97f0ddba1d8e522057ab4730ebb83c906a`; no answer-label clipping or horizontal overflow. | Hosted unmodified screenshots and independent human readability review are pending. The built-in image-generation request returned a network error and no asset; no CLI/API-key fallback was used. |
| Future asset-authoring tools | Pixelorama `1.1.10` first; Blender `5.2 LTS` bounded comparison | Neither executable is installed on this workstation. VA0 and the code-native VA1 board require neither tool. | Installation and export reproducibility remain future VA2/VA3 evidence, not a VA0/VA1 prerequisite. |
| Playwright / Chromium | `@playwright/test 1.61.1`, Chromium | Local Chromium `149.0.7827.55`; 49/49 in 2.0m at `1600x1000`, 98/98 in 4.4m under two repeats | Run 29639913312: current 49-contract browser job PASS. |
| Deterministic visual suite | Playwright 1.61.1, Python 3.12.13, exact server dependencies, and digest-pinned Noble image | Fixture/contract tests 7/7; four scenes pass functionally with `--ignore-snapshots` | Run 29639913312 compared all four reviewed goldens with updates disabled and PASS; the check is required on `main`. |
| AG-UI semantic input | Version retained per payload | Golden JSON/NDJSON and API tests pass | Run 29639913312: Python matrix PASS. |
| LangGraph StreamPart v2 | Floor `1.1.0`; supported lane `>=1.2,<2`; optional dependency | Isolated `1.1.0` and `1.2.9` `StateGraph` probes emit all six supported modes and pass normalization | Run 29639913312: `1.1.0` floor and supported-1.x jobs PASS. |
| NDJSON structure guard | Maximum nesting 256 | Quote/escape-aware lexical guard and regressions pass | Run 29639913312: Python and both LangGraph jobs PASS. Limit remains initial, not benchmark-derived. |
| OTLP JSON/OpenInference | Explicit JSON export | Golden fixture, adapter, encoded-URL, and API tests pass | Run 29639913312: Python matrix PASS. |
| JSONL reference store | Single process | Content-digest reuse, full changed-content validation, truncation anchors, and event-loop offload regressions pass | Run 29639913312: Python, browser, visual regression, and container jobs PASS. Not a production throughput or multi-process claim. |
| Docker / Compose | Optional local deployment | Docker CLI unavailable on this workstation | Run 29639913312: Compose, build, non-root/read-only, health, and ledger write PASS. |
| External network/model | Not required after install for core demo/replay/tests | Synthetic exhibit, projection, Compare, Fork, and browser tests use no model/network calls | First package/browser installation still requires package-source access. |
| Staged validation runner | Python 3.12+ and Node 22 for local S0/S1 | Advisory runner has a versioned impact map, NUL-safe Git discovery, protected-base and loaded-policy attestation, input fingerprint, atomic manifest, and bounded browser/Python verticals. Focused contracts passed 93/93 in 33.44s; domain command-time observations span 5.683–17.072s; one concurrent Windows launch caused Git DLL initialization failures and passed unchanged when isolated. | Final Draft run [29653112545](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29653112545) passed fast work, skipped six S2 definitions, and explicitly failed the aggregate; Ready and protected-main runs 29653471568/29653577169 passed complete S2 in 93s/91s wall. These are observations, not p95. |
| GitHub validation control plane | Strict status checks, admin enforcement, GitHub Actions app contexts | Personal-account repository; no ruleset/merge queue | Live API readback after protected-main run [29653577169](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29653577169): strict/admin/linear-history/conversation-resolution enabled; force-push/deletion disabled; original nine plus aggregate required; all ten bound to app `15368`. |

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
- Local visual scenes passed with snapshot comparison disabled; the authoritative protected-main pinned-Linux comparison passed in run 29639913312.
- The workstation's configured npm mirror does not currently carry `phaser@4.2.1`; use an explicit registry only inside the future benchmark install. Do not silently change global npm configuration.
- This workstation has no Docker CLI. A local command that omits the container boundary must not report complete S2; the hosted container job remains required.
- This maintainer workstation's data-loss-prevention policy rewrites materialized PNG worktree bytes after download. Promotion therefore verified artifact plaintext hashes and staged Git blob IDs before the policy rewrite, then relied on a clean hosted checkout for the authoritative comparison. Never restage those rewritten local PNG paths during an unrelated change.
- Only Chromium is automated; cross-browser and real assistive-technology verification remain pending.

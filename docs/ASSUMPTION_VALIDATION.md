# Assumption validation log

This file records bounded spikes that gate changes large enough to depend on
unverified external or architectural assumptions.

## 2026-07-16 — AG-UI semantic adapter

Sources checked before the spike:

- AG-UI event reference: <https://docs.ag-ui.com/concepts/events>
- AG-UI SDK event types: <https://docs.ag-ui.com/sdk/js/core/events>
- AG-UI serialization and lineage: <https://docs.ag-ui.com/concepts/serialization>

| Assumption | Validation | Result |
|---|---|---|
| The canonical schema accepts renderer-independent, namespaced AG-UI projection events and correlation IDs. | Constructed and validated an `agent.message.started` event with a `message` subject through `AgentRuntimeEvent`. | PASS. The first spike invocation omitted the required source fidelity and failed in the test harness; the corrected schema-complete invocation passed. |
| AG-UI's explicit `messageId`, `toolCallId`, `entityId`, and `stepName` data is sufficient for the fixture's causal/correlation links without temporal adjacency inference. | Checked every message/activity/reasoning reference against an explicit stream start and every tool reference against `TOOL_CALL_START`. | PASS for the golden fixture. Out-of-order and malformed streams must still remain unlinked rather than guessed. |
| Metadata-only conversion can preserve structural counts/paths while excluding content-bearing fixture values. | Serialized every canonical event from the fixture and searched for all `SECRET_` sentinels. | PASS. Plaintext remains an explicit opt-in and requires separate tests. |

These results validate implementation assumptions, not full protocol
conformance. AG-UI draft events and future protocol versions remain subject to
change and are retained with their source type/version for reprocessing.

## 2026-07-16 — instrumentation visibility projection

| Assumption | Validation | Result |
|---|---|---|
| Historical `WorldState` contains enough authoritative aggregate data to build a cursor-specific visibility view. | Projected the 44-event exhibit through the ledger and proved `sum(event_type_counts) == event_count == 44`. | PASS. The projection must use the requested cursor state, never the head manifest. |
| Current built-in adapters have stable identities suitable for a versioned capability registry. | Normalized demo, AG-UI, and OTLP fixtures and checked their adapter names against all built-in adapter identities. | PASS. Unregistered third-party adapters must be shown as unregistered, not assigned guessed capabilities. |
| A bounded domain taxonomy covers every stable core event family. | Compared every `CoreEventType` prefix with the proposed domain set. | PASS originally under protocol `0.1.0`. Protocol `0.2.0` changes new-write run-ID validation, not the `CoreEventType` families; extension families remain visible rather than being silently coerced. |

The visibility model deliberately has no aggregate “coverage percentage.” It
distinguishes `observed`, `observable_not_seen`, and
`outside_adapter_contract`; none of those labels proves that an unobserved
operation did or did not happen.

## 2026-07-17 — LangGraph StreamPart v2 adapter

Sources checked before the spike:

- LangGraph streaming: <https://docs.langchain.com/oss/python/langgraph/streaming>
- Official `StreamPart`, `TaskPayload`, and `CheckpointPayload` definitions: <https://github.com/langchain-ai/langgraph/blob/main/libs/langgraph/langgraph/types.py>

| Assumption | Validation | Result |
|---|---|---|
| LangGraph 1.x has a usable discriminated StreamPart v2 boundary from `1.1.0`. | Ran the same real `StateGraph` under isolated LangGraph `1.1.0` and `1.2.9`; both emitted dictionary parts with `type`, `ns`, and `data` across all six supported modes. | PASS for both tested versions; the configured supported lane is `>=1.2,<2`, and future releases remain a compatibility boundary. |
| Canonical events can preserve LangGraph task, state, message, checkpoint, custom, and interrupt signals without changing the envelope. | Normalized real and golden parts into core events plus `langgraph.custom`/`langgraph.interrupt.reobserved`, then validated every event through `AgentRuntimeEvent`. | PASS. Task interrupt lifecycle, first observation, repeated observation, and checkpoint snapshot remain distinct facts. |
| Offline normalization need not import LangGraph. | Parsed the fixture under `python -S` using only the standard library and verified explicit checkpoint IDs. | PASS for the JSON boundary. |
| Capture completion can be represented without inventing an outcome. | Declared a stream complete without `runStatus` and checked the terminal event. | PASS. The terminal status is `completed`; success/failure/interruption require an explicit status. |
| Unbounded external interrupt identifiers can cross the adapter without violating canonical limits or leaking a duplicate. | Imported 3,000+ character interrupt IDs through both state and task-result paths, then queried every persisted event. | PASS. Every base/supplemental reference uses the same deterministic hash, source length is recorded, the original ID is absent, and the API returns `201` rather than `500`. |
| Malformed runtime objects fail through the adapter boundary. | Supplied one object whose `model_dump()` raises and one whose dump returns itself. | PASS. Both become `LangGraphImportError`; neither a runtime exception nor recursion failure escapes. |
| Official payload shapes can be enforced without importing LangGraph into the application. | Compared 1.1.0/1.2.9 runtime definitions and exercised invalid task-result branches, checkpoint tasks, messages, debug wrappers, interrupts, values, token usage, and cross-source identities. | PASS for the tested boundary. Malformed input fails as a controlled import error rather than being guessed. |
| Historical checkpoint observations can coexist with a live approval without corrupting current state. | Ran RED/GREEN reducer probes for live interrupt followed by checkpoint snapshot, snapshot-only interrupt, reobservation, and historical task error. | PASS originally under reducer `0.2.0`; reducer `0.3.0` retained this behavior while moving explicit run-lifecycle transitions into the shared fold, and current reducer `0.4.0` retains it. Snapshots remain isolated by reducer version. |

The workstation's pre-existing LangGraph `1.0.4` returned the legacy tuple shape
even when called with `version="v2"`, confirming the lower-bound failure mode.
Isolated `1.1.0` and `1.2.9` environments emitted the documented dictionary
boundary and passed metadata-only normalization. The adapter rejects legacy
tuples rather than silently mis-mapping them. This proves the tested runtime
boundary, not every future `1.x` release. The optional compatibility matrix is
configured to keep that claim executable. The first hosted matrix ran in
[GitHub Actions run 29570924390](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29570924390): both LangGraph jobs reached test execution but were red because the same shared deep-NDJSON error-classification assertion failed. The corrected `1.1.0` floor and supported-1.x jobs both passed in [run 29629916726](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29629916726).

The current NDJSON guard rejects structural nesting deeper than 256 before
decoder behavior can diverge across supported Python versions, while ignoring
brackets inside strings. The value 256 is an initial conservative validation
limit, not a benchmark result; body, structure, cardinality, emitted-event, and
backpressure budgets still require calibration before untrusted hosted use.

## 2026-07-17 — Phase -1 inspector tab accessibility

Three bounded spikes gate the tab ARIA and keyboard slice before further changes to the already-large frontend bundle.

| Assumption | Validation | Result |
|---|---|---|
| Every inspector tab has one stable panel target. | Parsed `static/anthill.html` and compared the four `data-tab` values with the four `*-panel` IDs. | PASS after correcting the spike's first over-specific assumption that panels were `<section>` elements; the actual element tag is not part of the contract. |
| A tab-local arrow-key handler can avoid the page-level timeline shortcut. | Dispatched `ArrowRight` in real Chromium with a bubbling window listener and a tab listener that calls `stopPropagation()`. | PASS. The window listener received zero events. |
| Native `hidden` provides both visual and accessibility hiding for inactive panels. | Rendered one visible and one hidden `role="tabpanel"` in real Chromium and checked `isHidden()` plus the default role locator. | PASS. The hidden panel was not exposed by the role query. |

Executable evidence:

- `node scripts/spikes/phase1_tab_map.mjs`
- `node scripts/spikes/phase1_tab_stop_propagation.mjs`
- `node scripts/spikes/phase1_hidden_panel.mjs`

All three spike files are 14 lines or fewer. These results validate the browser primitives and current tab/panel topology, not the completed application behavior; Playwright still supplies the RED/GREEN acceptance proof.

## 2026-07-17 — run identity and lifecycle foundations

Three bounded spikes gated the shared lifecycle and selector identity work.

| Assumption | Validation | Result |
|---|---|---|
| Explicit lifecycle folding remains authoritative when non-lifecycle events trail a terminal event. | Folded `run.started`, explicit successful `run.completed`, then `artifact.created` through the shared transition helper. | PASS. The final status remains `completed`; manifest HEAD and reducer `0.3.0` introduced the shared transition semantics, which current reducer `0.4.0` retains. |
| A torn manifest can be repaired without using its stale last event as lifecycle truth. | Persisted start/completion, replaced `manifest.json` with malformed JSON, appended an artifact, and read the rebuilt manifest. | PASS. Reconstruction folds the complete ledger and restores `completed`. |
| Selector ingest timestamps can be deterministic without treating an unzoned value as UTC. | Normalized an explicit `+08:00` value to UTC and tested the zone suffix guard against the same wall time without a zone. | PASS. The aware value becomes `2026-07-17 08:30Z`; the unzoned value is rejected by the guard. |

Executable evidence:

- `python -m scripts.spikes.run_identity_lifecycle`
- `python -m scripts.spikes.run_identity_manifest_repair`
- `node scripts/spikes/run_identity_utc.mjs`

These spikes establish bounded primitives. Lifecycle aliases, missing facts,
short-ID collisions, hostile display text, stale response ordering, and the
ledger-HEAD-versus-history-cursor contract are covered by regression tests, not
by these three spikes alone.

## 2026-07-17 — JSONL discovery and compatibility foundations

Three bounded spikes gated the large store refactor.

| Assumption | Validation | Result |
|---|---|---|
| A bounded tail read can find the last non-empty JSONL record despite trailing blank lines. | Memory-mapped a two-record temporary ledger with trailing blank lines and decoded the last non-empty slice. | PASS. The returned sequence was `1`; the primitive supports lightweight HEAD reconciliation, not full integrity verification. |
| One re-entrant lock can protect nested same-run operations while serializing another thread. | Held an `RLock`, started a second thread, and nested the same lock inside the writer after release. | PASS. The writer could not finish while the outer holder owned the lock and completed after release. |
| Legacy validation can be restricted to explicit storage reads without weakening new input. | Parsed an edge-whitespace JSON value with Pydantic validation context, then validated the same shape without context. | PASS after correcting the first attempt to handle `ValidationInfo.context is None` with `info.context or {}`. Legacy storage input is readable; new input stays strict. |

The validation-context spike proves isolation of the compatibility switch, not
the complete production validator. Protocol `0.2.0` regression tests additionally
reject Unicode `Cc`/`Cf`, `/`, `\`, `?`, `#`, `%`, and the exact dot segments
`.` and `..`, so a newly written run ID is one addressable API path segment.
Store regressions, separate from the three spikes, also fix the discovery
classification boundary: given a valid checksummed manifest with a positive
event count, a shortened, empty, or missing ledger is reported as
`truncated_ledger`, and a missing ledger is not recreated.

Executable evidence:

- `python scripts/spikes/store_tail_boundary.py`
- `python scripts/spikes/store_rlock_serialization.py`
- `python scripts/spikes/store_validation_context.py`

The resulting process-local append index is keyed by an unkeyed SHA-256 digest
of the complete ledger bytes. Every append scans those bytes before deciding
whether the cached index is reusable; only first access or changed content
performs full JSON, sequence, duplicate-ID, and event-hash-chain validation.
That statement is specific to append-index reuse: a missing, malformed,
checksum-invalid, or stale-behind manifest may separately trigger a complete
ledger rebuild. A checksum-valid manifest ahead of the ledger is a
`truncated_ledger` anchor, while an equal-count manifest with a different HEAD
hash is a `divergent_ledger` anchor; both are quarantined rather than rebuilt.
The digest is refreshed after append. It is a change detector, not a MAC or
authenticity proof. Repeated single-event appends still have cumulative `O(k²)`
byte-scanning cost even when unchanged-ledger appends avoid repeated JSON
parsing. The per-run integrity endpoint remains the explicit full-verification
boundary.

## 2026-07-18 — Phase -1 semantic mirror and motion foundations

Three bounded spikes gate the frontend restructuring and measurement-backed visual work.

| Assumption | Validation | Result |
|---|---|---|
| OTLP span usage can be owned by the terminal mapped event without changing the recorded aggregate. | Normalized the public synthetic OTLP fixture, confirmed the request-start measurement map is empty, stamped the events, and projected the cursor-specific world. | PASS. The final projection contains exactly 128 input and 42 output tokens, not the former doubled 256/84. |
| The current world projection exposes enough stable public fields to build a renderer-independent entity DOM mirror. | Projected the synthetic exhibit and checked every entity for ID, kind, name, zone, status, truth, event count, and last-event route. | PASS for all 12 exhibit entities. This validates the current entity boundary, not future virtualization or `VisualModel` parity. |
| Chromium reports a runtime reduced-motion media change without a page reload. | Started Playwright Chromium with reduce enabled, attached a `MediaQueryList` change listener, switched to no-preference, and observed exactly one change. | PASS. Application override precedence and complete animation shutdown still require browser acceptance tests. |

Executable evidence:

- `python -m scripts.spikes.phase1_measurement_ownership`
- `python -m scripts.spikes.phase1_entity_mirror_shape`
- `node scripts/spikes/phase1_motion_change.mjs`

All three spike files are 17 lines or fewer. Direct path invocation of the two
Python modules initially failed because Python placed `scripts/spikes` rather
than the repository root on `sys.path`; the documented module-form invocations
above passed and are the supported commands.

## 2026-07-18 — Phase -1 safe measurement aggregation foundations

Three bounded spikes gate the reducer and snapshot changes required before Meter can show values.

| Assumption | Validation | Result |
|---|---|---|
| A closed registry can accept supported token ownership while rejecting cost without pricing provenance. | Validated `MeasurementSemantics` for model input tokens, then attempted model cost without `basis` and `estimated`. | PASS. The token contract parsed and the unpriced cost contract raised a validation error. |
| Per-owner temporality keeps delta, cumulative, and unknown samples arithmetically distinct. | Reduced two samples under each rule. | PASS. Delta summed to 12, cumulative selected 12, and repeated unknown temporality returned no value. |
| Nested owner state survives the projection snapshot boundary. | Serialized a typed aggregate with one owner to JSON, restored it, then deep-copied it. | PASS. Owner value and sample count survived both operations. |

Executable evidence:

- `python -m scripts.spikes.phase1_measurement_semantics`
- `python -m scripts.spikes.phase1_measurement_temporality`
- `python -m scripts.spikes.phase1_measurement_snapshot`

All three spike files are 18 lines or fewer. They validate the required
primitives, not the production reducer; RED/GREEN projection, snapshot, adapter,
API, Compare, and browser tests remain the acceptance boundary.

## 2026-07-18 — Phase 0 study-design preflight

| Assumption | Validation | Result |
|---|---|---|
| The ownership question has one full-credit path. | Inspected both completed handoffs in `visual_rich_v1.json`: Coordinator → Researcher has `ownership=transferred`; Researcher → Coordinator has `ownership=returned`. Reworded Q1 to require initial, post-transfer, and post-return owners. | PASS. The atom key is Coordinator → Researcher → Coordinator and no longer accepts the ambiguous phrase “after the handoff.” |
| Static Canvas/A/B/C screening can balance order without repeating the same packet facts. | Enumerated S1–S4 condition and packet Williams orders plus the W/X/Y/Z modular assignment. | PASS. Every condition and packet occupies each position once per stratum; all 12 directed carryover pairs occur once; every condition/packet uses all four variants; no screener repeats one packet's variant facts. |
| Six schedules balance condition order, position, and fixture pairing inside each participant stratum. | Enumerated the frozen O/V1/V2 × X/Y/Z schedule matrix. | PASS. It contains all six unique condition orders; all nine condition/fixture pairs occur exactly twice; each condition occurs exactly twice in each position. |
| The frozen control fixture identity is stable. | Recomputed whole-file SHA-256 and event count before publishing preregistration v2.2. | PASS. SHA-256 is `6ae35e714fb6c99d98b8598e0d7f18ccfac8f305c655b294fb67d10d6a360ac2`; event count is 44. |

These checks prove the written allocation and control identity, not equal
difficulty of fixture variants Y/Z or user comprehension. Y/Z parity review and
pilot evidence remain blocking before recruitment.

## 2026-07-18 — Phase 0 renderer dependency preflight

| Assumption | Validation | Result |
|---|---|---|
| Current production-candidate packages exist with registry integrity metadata. | Queried the official npm registry explicitly for `pixi.js@8.19.0` and `phaser@4.2.1`. | PASS. Both returned exact versions, tarball URLs, and SHA-512 integrity values. No dependency was installed or committed. |
| The maintainer's configured npm mirror can supply both benchmark packages. | Queried the configured registry for the same exact versions. | REJECTED. PixiJS resolved, but Phaser 4.2.1 returned 404; an explicit official-registry query succeeded. Future benchmark setup must isolate the registry override and commit the resulting lock evidence rather than changing global configuration. |
| PixiJS's native Canvas renderer is a stable independent fallback. | Compared the current official renderer guide with the official 8.16.0 release note. | REJECTED as a production assumption. The release calls Canvas experimental while the guide still marks it coming soon. Anthill retains its own Canvas and semantic-DOM fallback. |

Exact official-registry evidence captured on 2026-07-18 with npm `10.9.2`:

| Package | Version | Tarball URL | SHA-512 integrity | SHA-1 shasum |
|---|---:|---|---|---|
| `pixi.js` | `8.19.0` | `https://registry.npmjs.org/pixi.js/-/pixi.js-8.19.0.tgz` | `sha512-pq1O6emA/GFjjeF+8d3Pb5t7knD8FsnfWGqQcRjYjsqFZ7QdzG1XgjLDUu0DFJRbafjV5+g8iNLFBx0b9649lg==` | `4a0e9056f88ee61293f092723c8cbc2e083c8a7f` |
| `phaser` | `4.2.1` | `https://registry.npmjs.org/phaser/-/phaser-4.2.1.tgz` | `sha512-WUNwCPJpdjvZiuT6SgCfYVW8Qw/3j0jJ4ws7P2QkhFLFu74sbGuyHJcbFueGkY/AYO4Pi47bNQXn1OCJeLX//w==` | `5512f23d348e6fb5c48ce71a9fbddd200ef919ea` |

Both official metadata and tarball endpoints returned HTTP 200. The configured
registry remained `https://registry.npmmirror.com/` before and after the
preflight. Its PixiJS checksums matched the official values; its Phaser query
returned npm/HTTP E404. No package was installed and no npm configuration was
changed.

Executable evidence:

- `npm view pixi.js@8.19.0 version dist.tarball dist.integrity dist.shasum --json --registry=https://registry.npmjs.org/`
- `npm view phaser@4.2.1 version dist.tarball dist.integrity dist.shasum --json --registry=https://registry.npmjs.org/`
- `npm view pixi.js@8.19.0 version dist.tarball dist.integrity dist.shasum --json`
- `npm view phaser@4.2.1 version dist.tarball dist.integrity dist.shasum --json`

The resolved versions are dependency preflight only, not performance or
compatibility evidence. Installation remains blocked on the committed Phase 0
information contract and the issue #3 `VisualModel` boundary.

## 2026-07-18 — staged-validation preflight

Sources checked before implementation:

- GitHub required-check and job-condition documentation linked from
  [VALIDATION_STAGES.md](VALIDATION_STAGES.md);
- live `main` protection and recent Actions runs through the GitHub API;
- [PyPI PyYAML 6.0.3](https://pypi.org/project/PyYAML/), released 2025-09-25
  with Python 3.11–3.13 classifiers and verified publisher details;
- the official [Ubuntu 24.04 runner inventory](https://github.com/actions/runner-images/blob/main/images/ubuntu/Ubuntu2404-Readme.md),
  which currently lists `jq 1.7`.

| Assumption | Validation | Result |
|---|---|---|
| Hosted full-CI wall time is the present exploration bottleneck. | Inspected seven successful PR runs across three correlated branch families: total wall median 81 seconds; time to first completed job median 13 seconds. | REJECTED for current hosted wall time. Runner work and future matrix growth remain valid reasons to stage validation. The sample is too small and correlated for a stable p95 claim. |
| A repository-owned impact map can safely select the smallest sufficient regression set. | The implementation maps every tracked and non-ignored untracked workspace path, versions two historical selectors and their exact canary nodes, sends unmatched/control-plane paths to S2, and killed both former faults under in-memory mutation. Draft/Ready/protected-main runs passed its contracts, but the observation window and failure canaries remain pending. | PARTIAL. The selector is advisory and cannot downgrade protected checks. Two seeded replays are evidence, not proof against every future regression. |
| A feature branch cannot silently ignore a stronger protected-base impact policy. | Created diverged `main`/feature histories where only `main` strengthened the policy. Discovery recorded distinct base/worktree policy SHA-256 values and the plan added `protected-base-policy-mismatch`. | PASS for advisory automatic discovery: the plan escalates to S2. A future promotion-capable runner still needs CI-injected trusted-base authority. |
| A validation report cannot make the post-run repository differ from the validated input. | Reproduced an unignored in-repository report that previously returned exit 0 and created a new source path; then required Git-ignore proof both before execution and immediately before atomic replacement. | PASS. Unignored/tracked repository destinations now return configuration exit 3 without writing; ignored or out-of-repository reports remain allowed. |
| One vertical smoke can cover startup, deterministic fixture load, seek, Evidence, and semantic snapshot. | A dedicated `@s0` test went from “No tests found” to one pass in 9.84 seconds, covering fixed fixture → history `seq 0` → Objects → keyboard Evidence with browser-error capture; the candidate freeze repeated it in 8.5 seconds with an attached screenshot. | PASS for the bounded local path. It cannot replace complete hosted Chromium, and DLP prevents the local attachment from serving as durable image evidence. |
| Full Python pytest remains inside the provisional 30-second S0 budget. | A real CLI attempt timed out at 30.043 seconds before Ruff. The revised LangGraph + public API vertical set ran 217 tests in 14.019 seconds and Ruff in 0.279 seconds. | REJECTED. S0 uses bounded domain checks; complete Python remains S1/S2. |
| The aggregate can preserve an explicit Draft failure and accept a later Ready run on the same PR candidate. | Draft run 29645134489 failed only the aggregate; `ready_for_review` created run 29645207017 on the same head SHA and passed every dependency plus the aggregate; protected-main run 29645305313 repeated the full path. | PASS for Draft→Ready and resulting-main success. The first failure remains in history. The aggregate is now the tenth required context; the original nine remain required. |
| Job-level conditions can skip complete S2 in Draft and reliably restore it on Ready/main/manual events. | Draft runs 29645940777 and 29646051103 skipped all six S2 definitions and failed the aggregate; Ready runs 29645986711 and 29646089291 restored every S2 context on the same candidate; protected-main run 29646265724 restored complete S2 after squash. `workflow_dispatch` remains covered semantically, not by a hosted sample. | PASS for Draft/Ready/main hosted behavior and manual-event contract. Keep the original nine contexts during the observation window; manual dispatch remains a residual hosted sample. |
| A personal-account repository can use merge queue as the first migration mechanism. | Live repository owner type is `User`; current repository settings expose no merge queue or ruleset. | REJECTED for the current repository. Reassess after organization transfer and add `merge_group` support before enabling. |
| Semantic CI contract tests can use a maintained parser without narrowing supported Python versions. | Local PyYAML `6.0.3` parsed the workflow; PyPI metadata lists Python 3.11, 3.12, and 3.13 support. | PASS for the test boundary. GitHub Actions expression behavior still requires real hosted runs. |

Historical replay seeds are run `29570924390` for the deep-NDJSON classification
regression and run `29638437349` for the pinned-visual host/container pip-cache
path regression. Their current selectors were replayed locally: the LangGraph
set passed 217 tests before an injected former classification produced the exact
RED, and restoring the visual job's former `cache: pip` setting produced the
exact visual-contract RED. Cross-platform execution of the new candidate remains
hosted S2 evidence.

## 2026-07-18 — S0 impact-runner preimplementation spikes

Three critical assumptions were checked with repository scripts under 20 nonblank
lines before production implementation:

| Assumption | Spike and observation | Result |
|---|---|---|
| NUL-safe Git discovery can union committed, staged, unstaged, and untracked changes while retaining both rename paths. | `scripts/spikes/s0_git_union.py` created a temporary repository and recovered exactly `old.txt`, `new.txt`, `staged.txt`, `work.txt`, and `odd ; name.txt` using argv-only Git calls with `--no-renames --no-ext-diff -z`. Production tests now reject conflict/type/unknown status and changed gitlinks, bound untracked input, preserve special names, and mark skip-worktree visibility incomplete; those contracts passed on hosted Linux in run 29653577169. | PASS for local Windows plus hosted Linux contracts. Shallow-history replay remains pending. |
| A compact explicit census can cover the current repository without treating future paths as known. | The first `scripts/spikes/s0_path_census.py` run failed because `.gitattributes` was absent from the proposed control-plane set. After adding it, the script classified all 125 then-tracked paths, kept five high-risk examples explicit, and left `future/new-boundary.bin` unmatched for S2 fallback. | PASS after one visible failed attempt. The production contract now includes tracked plus non-ignored untracked workspace paths and fails whenever a future path lacks an explicit rule. |
| A real browser-level demo, time-travel, and Evidence signal fits the provisional warm S0 budget. | The first `npx` attempt failed before test execution because this worktree lacked the lock-installed `@playwright/test`; `npm ci` was required. After two non-matching filter failures, existing probes passed in 11.61s and 11.94s. The dedicated `@s0` path later passed in 9.84s; a CLI-selected UI run completed browser, syntax, and frontend checks in about 13.9s. | PASS as warm directional evidence only. Missing dependencies are explicit failures; cold/repeat samples are still insufficient for p95 or SLA claims. |

Design review: 5/5 passed. External tools and versions are already pinned or
hosted-proven; performance values above are explicit observations; missing tools,
unknown paths, stale input, limited visibility, and rollback remain fail-closed;
the 30-second threshold remains provisional; S1/S2 protection is unchanged.

## 2026-07-19 — orthographic visual-lab preimplementation spikes

Three bounded spikes gate the isolated visual-lab vertical slice. They validate
the existing fixture/projection/browser seam; they do not select an art direction
or prove a future PixiJS renderer.

| Assumption | Spike and observation | Result |
|---|---|---|
| The frozen exhibit has stable incident, recovery, compaction, and terminal cursors for a visible time-travel slice. | `scripts/spikes/visual_lab_fixture_contract.py` built the exhibit and checked all 44 events plus exact event types at indices 24, 30, 37, and 43. | PASS. The lab can use those four named presets without inventing story state. |
| The current projection exposes a bounded entity/evidence seam without introducing a renderer-owned domain model. | `scripts/spikes/visual_lab_projection_shape.py` store-stamped and projected the exhibit, then checked all 12 entities for ID, kind, name, zone, status, truth, event count, and a last-event route. | PASS for this fixture. This is not future virtualization, LOD, or canonical `VisualModel` parity evidence. |
| Current Chromium can render the proposed SVG/clip-path grammar and completely stop ambient CSS animation under reduced motion. | `scripts/spikes/visual_lab_browser.mjs` checked SVG semantics, polygon clip-path support, and running animations under reduced motion. The first two attempts failed because the reduced-motion rule preceded an equal-specificity base animation rule; moving the media override after the base rule produced zero animations. | PASS after two visible failures. Production CSS must keep reduced-motion overrides after animated declarations and browser tests must check the result. |

All three spike files contain fewer than 20 lines. No renderer package, remote
asset, global npm setting, or production Canvas path was changed.

## 2026-07-19 — visual-lab truth and accessibility hardening

T4 reused three bounded preimplementation spikes, each under 20 lines. Direct
path invocation first failed because `scripts/spikes` replaced the repository
root on `sys.path`; the supported module-form invocations then passed.

| Assumption | Executable evidence | Result |
|---|---|---|
| Opaque event and entity IDs survive schema validation without whitespace normalization. | `python -m scripts.spikes.visual_lab_opaque_id_contract` | PASS with exact `' event  id '` and `' agent  id '`. |
| The frozen exhibit fits the VA0 maximum of four visible entities per chamber. | `python -m scripts.spikes.visual_lab_density_contract` | PASS; the observed fixture maximum is two. The browser now rejects any addressed projection above four instead of overlapping it. |
| Full-chain integrity and the loaded fixture count agree before the lab makes visual truth claims. | `python -m scripts.spikes.visual_lab_integrity_contract` | PASS with `valid=true` and 44 events. |

RED/GREEN browser evidence was kept vertical:

| Behavior | RED observation | GREEN observation |
|---|---|---|
| Entity evidence reconciliation | A forged `last_seq=0` still rendered `READY`. | The scene fails closed unless every entity `lastEventId` resolves to an event at exactly `lastSeq` and not beyond the cursor. An attempted `event.subject.id == entity.id` rule was rejected: legitimate actor/run updates can own an entity's latest projection without using that entity as the event subject. |
| Query and cursor identity | Repeated query keys silently selected the first value; `cursor_seq=99` silently sought HEAD 0. | Repeated `run_id`, `cursor_seq`, `static`, or `timeout_ms` fails before fetch; an explicit cursor beyond HEAD fails instead of being clamped. |
| Provenance | Mixed input displayed `RECORDED RUN`; loading displayed a synthetic claim. | Initial state is `PENDING`; complete ledgers display `SYNTHETIC RUN`, `CONTAINS SYNTHETIC EVENTS`, or `RECORDED RUN`. |
| Revalidation | A failed HEAD integrity refresh left the old entities visible and the chip `VERIFIED`. | Old SVG, entities, cursor facts, and Evidence are invalidated while HEAD remains the retry path. Integrity becomes `FAILED` only when the integrity endpoint explicitly proves invalid; other display failures become `UNVERIFIED`. |
| Truth vocabulary | The legend exposed three labels and no shared five-state style contract. | `observed`, `declared`, `inferred`, `counterfactual_verified`, and `unknown` have explicit text plus five distinct non-color border/pattern signatures. |
| 1600×1000 readability | 22 of the 24 demo name/meta labels reported overflow, and the addressed run ID was ellipsized. | Zero demo name/meta labels report horizontal or vertical clipping; the full addressed run is directly visible with `scrollWidth == clientWidth == 482`. |
| Evidence drawer | The first useful state was `Select an entity`; disabled Evidence retained `href="#"`. | The current cursor event is the default, entity selection overrides it, an independent polite live region announces changes, and unavailable Evidence has neither `href` nor a tab stop. |
| Motion, density, and contrast | Reduced-motion used `static=1`; five entities could overlap; three small-label pairs were below 4.5:1. | The test first observes running animation with `static=false`, then zero under reduce; density above four fails closed; all three measured pairs are at least 4.5:1. |

The final stable Chromium file passed 25/25 in 1.1 minutes (68.720 seconds of
independent process wall time) at the configured
1600×1000 viewport in an independent run. The exact final `@visual-lab-s0`
selector passed 1/1 in 10.2 seconds of Playwright-reported time, and four Node
syntax checks passed again after the final patch. These are local Chromium observations, not
cross-browser or real assistive-technology evidence.

The design review then found one uncovered exception path: an initial projection
request could remain `LOADING` forever. A focused browser test delayed the world
response for 300 ms while requesting `timeout_ms=100`; RED reached `READY`
because the parameter was ignored. GREEN aborts the request after 100 ms,
invalidates semantic output, shows the exact timeout in `ERROR`, exposes
`RETRY LOAD`, and reaches `READY` after the delayed route is released. Runtime
configuration is bounded to 100–30,000 ms with an initial 10,000 ms default;
these are initial study values pending hosted latency calibration.

The final truth-boundary review then found two misleading failure paths and one
avoidable request-cost path. Each received an explicit RED before the fix:

| Behavior | RED observation | GREEN observation |
|---|---|---|
| Display failure semantics | Timeout and projection failures rewrote run lifecycle to `INVALID` and ledger health to `STALE INVALID`. | The scene is cleared as `SCENE INVALIDATED`, run lifecycle is `UNAVAILABLE`, and integrity is `UNVERIFIED`; only an explicit invalid full-chain result may say `FAILED`. |
| Superseded failure ordering | A transport deliberately ignoring abort returned a malformed old seek after a newer HEAD reached `READY`; the stale catch erased the verified scene and changed the page to `ERROR`. | Both success and exception branches check the request generation. The newer HEAD remains `READY`, `VERIFIED`, and at `run.completed`. |
| Superseded HEAD cache ownership | A late old HEAD was blocked from the DOM but still replaced the shared cache; the next INCIDENT silently changed the head denominator from 2 to 1. | Each HEAD loads through an isolated candidate client. Only the winning generation commits it; after the late old load, INCIDENT remains `1 / 2`. |
| Batch cancellation and caching | A bad world response left its parallel integrity request pending, and fetch used the default browser cache mode. | The load owns a batch controller, aborts sibling requests on failure, and every lab GET uses `cache: 'no-store'`. |
| Unbound initial controls | Initial query/timeout errors displayed an enabled HEAD button even though controls had never bound. | HEAD is disabled until one successful initialization binds controls; after a successful retry it becomes available. |

The final local screenshot was emitted directly from browser memory after these
changes: 1600×1000, 249,107 bytes, SHA-256
`07154927e9ab15980ba4596b50b2e8f7766de78b20388420fa26687709e176cd`,
12 zones, 12 entities, zero entity-label clipping, and a fully visible addressed
run ID. Hosted attachments remain the promotion evidence because materialized
local PNGs are rewritten by endpoint protection.

Final design review: 5/5 passed. External dependencies and exact ESM distribution
measurements are reproducible; performance and effort values are labelled as
observed or estimated; invalid identity, dirty/mismatched data, integrity,
disconnect/HTTP failure, superseded success/failure, isolated HEAD-cache commit,
timeout/retry, motion, and density paths are explicit; every threshold is
identified as protocol-derived or an initial value pending calibration; public
or sensitive-run response minimization remains a named later gate; the direction
precursor remains outside the frozen study conditions and production Canvas.

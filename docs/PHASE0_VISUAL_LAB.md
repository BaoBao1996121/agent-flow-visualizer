# Phase 0 orthographic cutaway Visual Lab

Status: exploratory direction-A precursor; not a frozen Phase 0 stimulus or
study condition; production Canvas is unchanged; hosted engineering-validation
S2 evidence pending.

Last reviewed: 2026-07-19 (Asia/Shanghai).

## Outcome

The lab is an isolated, ledger-addressed study scene for testing whether an
orthographic Agent “anthill” can carry more operational information without
turning the observatory into decoration. It renders a bounded subset of
cursor-specific facts from the canonical projections as a semantic DOM plus
programmatic SVG chamber shell at
`/labs/phase0-cutaway`.

This is not a renderer decision, a production replacement, a preregistered
Phase 0 stimulus, or a study winner. It is the first executable art-direction
precursor used to discover
truth, accessibility, density, and asset-pipeline problems before a game engine
is allowed to own presentation work.

VA0 is not yet in the frozen A/B/C packet manifest. A static screener condition
must first satisfy the plan's equal-information, planned-target, object-census,
density, and static-frame gates; a later V1/V2 candidate must also satisfy the
operable-route gates. A conforming stimulus is published and frozen under the
existing plan. An amendment is required only if the preregistered protocol,
obligations, or already frozen materials change.

## Run it

Start the local service:

```bash
python server.py
```

Create the explicit synthetic exhibit and open the addressed lab in PowerShell:

```powershell
$demo = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/api/anthill/demo
Start-Process "http://127.0.0.1:8765/labs/phase0-cutaway?run_id=$($demo.run_id)&cursor_seq=43"
```

The page never creates or guesses a run. `run_id` is required; `cursor_seq` is
optional. Add `static=1` only for deterministic screenshot review. API reads use
an initial 10,000 ms timeout; `timeout_ms` can be set from 100 to 30,000 for a
bounded study or test. Those values are initial and pending hosted latency
calibration. The initial VA0 fixture contains 44 synthetic events, so its final
event is event number 44 at zero-based ingest sequence 43.

## Information contract

The chamber metaphor is presentation. The following values must come from the
addressed APIs and fail closed when they disagree:

| Visual claim | Canonical basis |
|---|---|
| Run identity and lifecycle | cursor-specific world projection |
| Event number and ingest sequence | projection `event_count`, `projected_seq`, and contiguous ledger reconciliation |
| Entity identity, status, chamber, and latest evidence | cursor-specific `world.entities` projection |
| Event type, summary, source, and truth | exact opaque event ID resolved from the ledger response |
| `HEAD`, `INCIDENT`, and `COMPACTION` controls | refreshed HEAD or exact matching ledger event types; never fixed narrative labels over arbitrary sequences |
| Synthetic/recorded classification | all loaded events, with mixed event provenance labelled separately within the run |
| Ledger health | `/integrity` full-chain result and event-count reconciliation |

`EVENT #` is one-based for human reading; `INGEST SEQ` remains the authoritative
zero-based order. The sequence rail states that order is not causality. A visual
edge may claim causality only when later work projects a canonical causal link.

The truth legend keeps `observed`, `declared`, `inferred`,
`counterfactual_verified`, and `unknown` distinguishable without relying on
color alone. Every interactive entity is a real button with an accessible name
containing kind, status, truth level, event count, and the evidence action. The
SVG chamber shell is contextual artwork; the semantic DOM is authoritative for
keyboard and assistive-technology access.

### Failure behavior

| Failure | Lab behavior |
|---|---|
| Missing, repeated, or invalid `run_id` / cursor | Show `ERROR`; do not create, guess, or switch a run |
| World/event run identity, sequence, count, or evidence mismatch | Reject the scene instead of rendering an approximate fact |
| Hash-chain verification explicitly returns invalid | Mark ledger integrity `FAILED` and reject truth claims |
| Projection, identity, timeout, response, or reconciliation fails without proof of ledger corruption | Clear the scene and show run `UNAVAILABLE` plus integrity `UNVERIFIED`; never rewrite run lifecycle or ledger health from a display failure |
| More than 5,000 events or more than four visible entities in one chamber | Refuse this VA0 density rather than overlap or silently omit objects; both are initial layout/response guards pending calibration |
| A cursor request is superseded | Abort it and ignore both its success and failure paths by generation so stale state cannot win |
| One request in a parallel load batch fails | Abort the sibling requests; all run-data GETs use browser `no-store` |
| Evidence is unavailable | Remove the canonical-event link from the tab order and label the evidence unavailable |
| Request hangs | Abort after the bounded timeout, invalidate any rendered facts, show `ERROR`, and expose `RETRY LOAD` |

The four-entity guard comes from the current chamber's measured two-column by
two-row card capacity; it is not a product maximum. The 5,000-event guard mirrors
the current bounded request and does not bound bytes or sensitive fields.

## Why this implementation is isolated

Three paths were considered:

| Path | Benefit | Cost / risk | Decision |
|---|---|---|---|
| Static concept image | Fast visual reaction | Cannot prove cursor, evidence, keyboard, or API truth | Rejected as the executable candidate |
| Immediate PixiJS scene | Exercises the likely renderer | Crosses the still-unfrozen `VisualModel` and can hide semantic drift behind engine state | Deferred to the engine slice |
| DOM/SVG cutaway lab | Uses current ledger APIs, is inspectable, and adds no runtime dependency | Not a performance proxy for a sprite renderer | Selected for VA0 |

No PixiJS, Phaser, Blender, Pixelorama, or generated-image dependency enters the
runtime in VA0. The existing Canvas observatory remains the current production
control. VA0 does not join the preregistered comparison merely by existing or by
passing engineering tests.

## Visual and asset pipeline

The recommended path separates information semantics from visual production:

| Stage | Output | Initial effort estimate | Promotion evidence |
|---|---|---:|---|
| VA0 — programmatic cutaway | SVG chambers, CSS/DOM characters, exact evidence drawer | 4–8 engineer-hours | Browser truth, keyboard, reduced-motion, integrity, and screenshot checks |
| VA1 — concept board | AI-assisted silhouettes, palettes, room language; exploration only | 2–4 artist/UX-hours | Provenance record plus independent readability review; no direct runtime import |
| VA2 — pixel production | Pixelorama source, deterministic sprites/atlas/manifest | 1 artist/UX-day | Reproducible export, asset hashes, six readable action silhouettes at 32–48 px |
| VA3 — 3D-to-2D comparison | Blender orthographic rig/render for hard multi-angle motion | Maximum 1 artist/UX-day | Same action inventory and measured cleanup/reuse cost versus VA2 |
| VA4 — asset parity smoke | Load the same approved atlas into already-built PixiJS and Phaser slices | 1–2 engineer-days after both slices exist | Same asset IDs, frames, facts, clock, LOD, and DOM labels |

All durations are estimates, not observed throughput. VA2/VA3 must record real
creation, cleanup, export, and reuse time before the forecast is trusted.
VA0–VA3 are work packets within the existing Phase 0 allowance of 8–14
engineer-days plus 4–7 artist/UX-days, not costs to add on top of it. VA4 belongs
inside the renderer-slice forecasts described below, not a third engine budget.

AI-generated images are reference material until their prompt, model/version,
date, source inputs, license/provenance, review status, and human edits are in
the asset manifest. They must not generate labels, status, truth, causality, or
other runtime facts. Image-to-animation shortcuts are acceptable only for visual
concept discovery; deterministic production sprites still require reviewed
frames and reproducible export.

Pixelorama is the recommended first production tool because the target is a
small, readable sprite vocabulary rather than cinematic animation. Its project
JSON is not assumed to be a Pixi atlas; VA2 must provide a deterministic
converter/export contract instead of hand-maintained coordinates.

Blender is a bounded comparison, not the default. The following are initial
experimental stop values pending the first measured asset run. Stop VA3 after
eight hours if
any of the following is true: no reusable rig plus six actions; more than 20% of
frames require pixel redraw; cleanup is not lower than VA2; the 32–48 px
silhouette is worse; or export cannot be reproduced from source and settings.

## Engine recommendation

PixiJS `8.19.0` remains the leading renderer candidate because Anthill needs a
rendering layer, not a game-owned scene/state system. Phaser `4.2.1` is the
mandatory same-scene benchmark because its camera, scene, input, and animation
tooling may reduce implementation cost. A reproducible local comparison of the
exact minified ESM distributions measured `pixi.min.mjs` at 798,434 raw /
225,312 gzip-6 bytes and `phaser.esm.min.js` at 1,377,611 raw / 355,528 gzip-6
bytes, making the Phaser file 57.8% larger in this one comparison. The files
came from official-registry `npm pack` for the versions above; Python gzip with
zlib 1.3.1, `mtime=0`, and the recorded SHA-256 values were used. Reproduce the
measurement with [the distribution-size spike](../scripts/spikes/engine_distribution_size.py).
This is a distribution-file signal, not an application-bundle result; granular
imports and the production builder can change it.

Godot Web remains an architecture boundary, not a first-round candidate: its
editor and game systems are attractive, but the WebAssembly/WebGL payload,
semantic-DOM bridge, and integration with the existing observatory impose a
second application runtime. The project reconsiders it only under the
[visual-system exit conditions](VISUAL_SYSTEM.md), such as a roadmap that
materially requires native application delivery. Blender stays an offline asset
authoring tool and never becomes the browser runtime.

Measured input hashes: Pixi `28fefb52eeb15bb3e087533456bafc53e91af70932af4dd046ff2938ec3edd0e`;
Phaser `f4c5fd140d118c10fa9090641a03c17303bab9bfdc28e0626296777db1bb1bde`.
After extracting the two official tarballs, the measurement command is:

```bash
python -m scripts.spikes.engine_distribution_size <pixi>/dist/pixi.min.mjs <phaser>/dist/phaser.esm.min.js
```

The 1–2 day VA4 value covers only shared-asset integration after the renderer
slices exist. It does not replace the current [visual-system forecast](VISUAL_SYSTEM.md)
of 10–16 engineer-days for the bounded PixiJS slice and 4–7 for the same-scene
Phaser benchmark; those forecasts also remain unmeasured.

The engine is never allowed to own facts. `VisualModel`, asset registry,
deterministic clock, LOD rules, and semantic DOM stay shared. Engine registries,
timers, tweens, and scene callbacks are replaceable adapters. Selection waits
for the same production builder, scene, asset set, and measurement harness.

Primary sources checked on 2026-07-19:

- [PixiJS renderer guide](https://pixijs.com/8.x/guides/components/renderers)
- [PixiJS accessibility guide](https://pixijs.com/8.x/guides/components/accessibility)
- [PixiJS 8.19.0 release](https://github.com/pixijs/pixijs/releases/tag/v8.19.0)
- [Phaser 4.2.1 release](https://github.com/phaserjs/phaser/releases/tag/v4.2.1)
- [Pixelorama 1.1.10 release](https://github.com/Orama-Interactive/Pixelorama/releases/tag/v1.1.10)
- [Pixelorama CLI manual](https://pixelorama.org/user_manual/cli/)
- [Blender 5.2 LTS release](https://www.blender.org/download/releases/5-2/)

## Engineering validation stages

Exploration stays fast without weakening promotion:

These engineering S0-S4 boundaries are separate from the Phase 0 screening
schedule's similarly named study steps. They describe code confidence and
promotion authority, not experimental-condition order.

| Boundary | Purpose | Current VA0 requirement |
|---|---|---|
| S0 | seconds-scale feedback while editing | one exact Chromium fixture path, frontend contracts, JS syntax |
| S1 | bounded vertical confidence | all Visual Lab browser cases, projection/fixture spikes, affected Python/API contracts, Ruff |
| engineering S2 | promotion authority | complete protected GitHub Actions matrix plus exact hosted Playwright screenshot attachment |
| S3/S4 | periodic breadth and release evidence | cross-browser, real assistive technology, comprehension study, density/performance and engine parity |

A local in-memory screenshot is illustrative. Endpoint protection rewrites
materialized PNG bytes on this workstation, so only an unmodified hosted
Playwright artifact can promote the candidate.

### Current local candidate evidence

- Stable Chromium: 25/25 in 1.1 minutes (68.720 seconds process wall).
- Exact engineering S0: 1/1 `@visual-lab-s0` in 10.2 seconds.
- Affected Python/document/control-plane contracts: 58/58 in 37.80 seconds;
  Ruff, five Python preimplementation spikes, and four final Node syntax checks pass.
- Browser-memory screenshot: 1600×1000, 249,107 bytes, SHA-256
  `07154927e9ab15980ba4596b50b2e8f7766de78b20388420fa26687709e176cd`;
  12 zones, 12 entities, complete addressed run ID, and zero measured entity
  label clipping.
- The suite declares exact-state attachments for overview, invalidation,
  superseded seek, superseded HEAD cache, timeout, and recovery. Hosted review
  is still pending.

Truth/security review reports zero remaining P0/P1 for the synthetic VA0 path.
This evidence freezes a local candidate only; it does not satisfy engineering
S2, freeze an experimental condition, or choose a production renderer.

## Known limits

- VA0 is a single desktop-density slice; small-screen and 200% zoom behavior are
  not yet a release claim.
- Twelve entities in a 44-event synthetic fixture do not validate long-run
  pagination, aggregation, or 28+ object density.
- The page currently loads bounded event details for study projection. A future
  public or sensitive-run version needs a server-side scene/metadata endpoint
  with response-byte limits, field minimization, and explicit response cache
  policy; “5,000 events” and browser `no-store` are not server-side data-volume
  or sensitivity bounds.
- Chromium keyboard and reduced-motion automation does not replace real screen
  reader, forced-colors, magnification, or comprehension testing.
- The cutaway may be visually attractive, but Phase 0 selects on correct answers,
  evidence retrieval, recognition, density, accessibility, and measured cost—not
  screenshot preference.

The normative comparison and stopping rules remain in
[the preregistered Phase 0 evidence plan](PHASE0_VISUAL_EVIDENCE_PLAN.md). The
long-term renderer, truth grammar, animation, asset provenance, accessibility,
and cost constraints remain in [the visual-system decision](VISUAL_SYSTEM.md).

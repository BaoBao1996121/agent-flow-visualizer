# Phase 0 visual evidence plan

Status: preregistered v2.2; no recruitment or participant result exists yet
Registered: 2026-07-18; amended before recruitment on 2026-07-18
Public tracker: [issue #10](https://github.com/BaoBao1996121/agent-flow-visualizer/issues/10)
Public v2.2 amendment: [issue comment](https://github.com/BaoBao1996121/agent-flow-visualizer/issues/10#issuecomment-5011144923)
Candidate control release: [v0.7.0](https://github.com/BaoBao1996121/agent-flow-visualizer/releases/tag/v0.7.0)

## Decision this study must produce

Phase 0 selects, revises, or rejects a production visual direction before the
project implements `VisualModel` or adds a second renderer. The winner must make
the recorded Agent mechanisms easier to understand without weakening truth,
evidence, accessibility, density, or deterministic replay.

This is a formative study and engineering evidence plan. It cannot by itself
prove the long-term product hypothesis that Anthill is 50% faster than README,
logs, and source code. It is allowed to reject all new directions and retain the
current Canvas information grammar.

## Frozen control material

The semantic template is
[`tests/fixtures/visual_rich_v1.json`](../tests/fixtures/visual_rich_v1.json):

- fixture version: `1.0.0`;
- event count: `44`;
- whole-file SHA-256: `6ae35e714fb6c99d98b8598e0d7f18ccfac8f305c655b294fb67d10d6a360ac2`;
- content policy: explicitly synthetic and safe for public study artifacts;
- control UI: application `0.7.0`, reducer `0.4.0`, measurement contract
  `1.0.0`, coverage contract `0.3.0`.

P0-1 must enumerate every semantic Canvas object and resolve 100% of its routes
before recruitment. If v0.7.0 misses that gate, recruitment is blocked: repair
the control or downgrade the unsupported visual claim to an explicit
Unknown/diagnostic state, pass protected CI, and freeze the new release/commit,
object manifest, and screenshot hashes in an amendment. P0-3 never compares a
known-unreachable Canvas control with candidates.

Within each matched packet/fixture version, every candidate receives the same
answer-bearing facts, labels, evidence entry points, viewport, and truth
grammar; the study allocation balances versions across conditions. A direction
cannot improve its screenshot by omitting information.

## Eight scored mechanism questions

Each fully correct answer is one point. Partial-credit notes are retained for
diagnosis, but Time to Correct Mental Model (TCMM) stops only at the first fully
correct `7/8` submission. The `7/8` threshold is an initial formative operating
point, chosen so one wording slip does not dominate the timing measure; it is
not a candidate pass gate. Exact `8/8`, per-question results, and every final
wrong inference are reported alongside it. Timing starts after the task prompt
is read, includes answer revisions, and is right-censored at the initial
20-minute session budget rather than imputed as a success.

1. **Ownership:** Who owned the incident task initially, immediately after the
   first completed transfer from Coordinator to Researcher, and immediately
   after the later completed return from Researcher to Coordinator?
   Expected: Coordinator, then Researcher, then Coordinator; ownership was
   transferred and later returned.
2. **Memory and context:** Which prior memory influenced the run, and where did
   it enter active context?
   Expected: episodic `Prior deploy lesson`; it was retrieved and then added as
   a context item.
3. **Failure and recovery:** Why did the log tool fail, and what proves recovery
   rather than a hidden reset?
   Expected: retryable `RateLimit`, scheduled retry, second execution success,
   then explicit `error.recovered` linked to the incident.
4. **Context and compaction:** What exceeded the budget, what changed, and was
   the transformation lossless?
   Expected: 8,460 used versus 8,192 budget; compaction reduced it to 3,920; it
   was explicitly lossy and exposes kept/removed references.
5. **Truth status:** Which cognition claims are inferred rather than
   source-declared, and how can the user tell?
   Expected: `decision.started` and `decision.evaluated`; truth styling and
   Evidence expose inferred fidelity and derivation.
6. **Measurement safety:** Is USD 0.0062 a measured fact, and when is it safe to
   compare?
   Expected: it is estimated under
   `synthetic-fixture:demo-pricing-v1`; comparison requires compatible scope,
   unit, aggregation, basis, and estimated status.
7. **Durable result:** What artifact was produced, and which memory write
   followed?
   Expected: Markdown Incident report, then semantic memory `Checkout root
   cause` with an explicit source-artifact link.
8. **Lifecycle and unknowns:** At the final cursor, is the run live, and what
   may `NOT OBSERVED` prove?
   Expected: no; the run completed successfully. `NOT OBSERVED` means no
   supporting signal was recorded, not that the mechanism did not occur.

## Wrong-inference taxonomy

| Code | Wrong inference |
|---|---|
| W1 | Temporal adjacency is claimed as causality. |
| W2 | Not observed is claimed as did not happen. |
| W3 | Capture or transport state is claimed as run lifecycle. |
| W4 | Decorative motion is claimed as recorded execution. |
| W5 | An inferred claim is repeated as an observed fact. |
| W6 | A recovered incident is interpreted as deleted history. |
| W7 | Estimated or incompatible measurements are treated as directly comparable. |
| W8 | Task ownership or handoff direction is confused. |

Record the first occurrence, correction time, final state, and participant
confidence for every code. Confidence without correctness is a calibration
failure, not a successful explanation.

## Frozen scoring and timing protocol

Full credit requires every atom below and no contradictory claim. Synonyms are
accepted only when they preserve the same identity, direction, truth status,
and measurement meaning. Partial atoms are retained for diagnosis but do not
produce the question's one point.

| Question | Required full-credit atoms for control fixture X |
|---:|---|
| 1 | Initial Coordinator; first transfer to Researcher; later return to Coordinator; both ownership transitions are stated. |
| 2 | Episodic memory; `Prior deploy lesson`; retrieval; subsequent active-context addition. |
| 3 | Retryable `RateLimit`; retry scheduled; second execution succeeded; explicit `error.recovered` for the same incident. |
| 4 | 8,460 used exceeded 8,192; result 3,920; compaction was lossy; kept/removed lineage is exposed. |
| 5 | `decision.started` and `decision.evaluated`; both are inferred; the interface exposes truth styling and derivation. |
| 6 | USD 0.0062 is estimated; basis is `synthetic-fixture:demo-pricing-v1`; scope, unit, aggregation, basis, and estimated status must be compatible. |
| 7 | Markdown Incident report; it precedes semantic memory `Checkout root cause`; explicit source-artifact link. |
| 8 | Run completed successfully and is not live; `NOT OBSERVED` means no supporting signal; it cannot prove non-occurrence. |

The X/Y/Z answer-key manifest freezes the corresponding variant values, allowed
synonyms, atom IDs, and W1–W8 contradictions before recruitment. The study UI
shows the prompt first and reveals the interface only after the participant
confirms it has been read; that reveal starts a monotonic client timer. Every
navigation, answer submission, confidence value, and elapsed time is appended
to the anonymized study log with a UTC audit timestamp.

Each condition permits an initial submission and at most two participant-led
revisions. The interface and facilitator give no correctness, score, or answer
hint during a condition. TCMM is the elapsed time of the earliest submission
that independent later scoring finds to be at least `7/8`; final accuracy and
wrong-inference state come from the last submission. If no submission reaches
`7/8` by 20 minutes, record `not_reached` with right-censoring at 20 minutes,
not a successful TCMM of 20 minutes.

If an otherwise continuing participant makes no initial submission by the
20-minute cap, record a frozen no-response checkpoint: `not_reached`, initial
and final exact score `0/8`, no W code because no positive assertion exists,
and calibration MAE `1.0` as an explicit conservative selection penalty rather
than a claimed confidence observation. Report its eight confidence values as
missing, not zero. The participant still completes the later Evidence and
assigned accessibility blocks; refusal or withdrawal follows the replacement
rule below. Any candidate no-response checkpoint fails that candidate's
first-submission gate in that stratum; a Canvas no-response remains a `0/8`
reference. Thus a candidate cannot use missing responses to reach the W or
calibration tie-breakers.

Two raters independently score every submission against the frozen atom keys
before the neutral interface-code mapping is unlocked. A named third reviewer
adjudicates disagreements. If response content reveals an interface, flag that
response as unblinded rather than silently treating it as blind. Report raw
agreement and disagreement counts; the rubric cannot change after unblinding.
Code W1–W8 only for a positive wrong assertion—omission or `not sure` is not a
wrong inference. Confidence is recorded from 0 to 100 in ten-point increments
for each answer; calibration error is the mean absolute difference between
confidence/100 and binary full correctness.

## Visual-object and task operations

### Object census and evidence reachability

Before P0-2, Canvas O exports the full interactive manifest and route contract
below. Every static A/B/C frame exports a static manifest with the same object
classification and obligation fields, but uses a 100%-complete
`planned_evidence_target` mapping instead of claiming an operable route. Before
P0-3, V1/V2 replace every planned target with the full typed, operable
`evidence_route`; O/V1/V2 then export that full contract for every
fixture/cursor combination:

- `information_role=decorative` objects encode no domain fact or status, are not interactive,
  are hidden from assistive technology, and are excluded from evidence
  denominators;
- `information_role=semantic` objects encode identity, state, truth, lifecycle, measurement,
  topology, or relationship; every one must map to a canonical event, explicit
  declaration/source, documented derivation, or explicit unknown/not-observed
  explanation, and every interactive object must resolve that mapping through
  an operable route;
- `answer_bearing=true` marks the semantic subset required by one or more of
  the eight `answer_obligation_ids`. It implies `information_role=semantic`.
  These objects must preserve equal information; interactive O/V1/V2 objects
  additionally expose a bounded keyboard/DOM route to the frozen answer key.

An evidence target is typed as `event`, `event_set`, `declaration`,
`derived_projection`, or `coverage_unknown`. Its resolver verifies the current
run and `ingest_seq <= cursor_seq`, lists source events and reducer/schema
version for derivations,
preserves aggregate membership under LOD, and routes missing capture to a
Coverage/Unknown explanation. A broken target degrades the visual claim to an
explicit diagnostic/unknown state; it cannot leave the original semantic claim
on screen.

Static planned targets use the same target types and canonical identities, but
their resolver and interaction checks become mandatory only if the direction
advances to V1/V2.

Structural reachability is a 100% hard gate for interactive O/V1/V2 semantic
objects, including offscreen and LOD-aggregated objects. Static A/B/C instead
require 100% canonical target mapping; P0-2 does not pretend that a still image
has DOM, keyboard, or click behavior. The product's separate 95% target is human
completion of sampled interactive evidence-route tasks; it never permits 5% of
semantic objects to lack a mapping or route. A supposedly decorative object
that participants interpret as execution state is logged. If at least two
independent participants give the same domain-state interpretation, treat the
object as semantic for the frozen analysis. Missing planned mapping fails a
static direction; a missing operable route fails interactive O/V1/V2. Any
subsequent reclassification/repair requires an amendment and separate retest.

The current v0.7 test proves that every `world.entities` item has a DOM-mirror
entry and samples selected Meter/Memory evidence routes. It does not yet prove
a complete census of every Canvas zone, packet, aggregate, and hard-coded
semantic glyph. P0-1 must publish that missing census instead of treating the
current implementation as already complete.

### Evidence-route task

After all three comprehension conditions and their final TCMM submissions,
run Evidence blocks in the participant's scheduled condition order. Within
each block, give four targets in a preregistered seeded-random order: completed
ownership transfer (`handoff.completed`); recovered RateLimit
incident (`error.raised` plus linked `error.recovered`); lossy compaction
(`compaction.completed` with kept and removed references); and estimated cost
(derived projection with pricing basis). One attempt succeeds when the
participant opens the exact frozen target and states its required field within
60 seconds without a hint. The compaction route must use keyboard only and has
90 seconds; pointer use, lost focus, or a keyboard trap fails it. Wrong targets
may be corrected inside the budget and are counted. Record time, target ID,
route, input method, wrong selections, and failure reason. This yields 48 trials
per condition and 144 P0-3 trials. A condition meets the initial 95% human target
at `46/48` or better. Each candidate must also have at least as many successes
as Canvas inside each 24-trial participant stratum.

### Five-second recognition

Screen the current static Canvas control `O` beside A/B/C. Freeze four packet
types with two forced-choice obligations each:

| Packet | Frozen frame | Recognition obligations |
|---|---|---|
| P1 | Cursor 17, Causal view rooted at `decision.evaluated` | Truth class is `inferred`; selected relation is backed by explicit `causation_id`/`derived_from`, not temporal adjacency. |
| P2 | Cursor 25, incident open | Acting Agent is Researcher; lifecycle is retryable failure raised. |
| P3 | Cursor 38 static outcome, not a five-second replay | Chamber/mechanism is Compaction Plant; transformation is lossy. |
| P4 | Cursor 44 terminal overview with frozen healthy transport | Run completed successfully; transport is `LEDGER CONNECTED` and does not mean the run is live. |

The table gives X's answer wording. W/Y/Z substitute their frozen safe
identities, labels, and values while preserving the same two semantic
obligations and four-choice difficulty.

Use eight screeners, four Agent engineers and four technical learners. Inside
each stratum use a recorded preregistered random seed to assign one person
without replacement to each balanced order:

| Screening schedule | Interface order | Packet order within every interface |
|---|---|---|
| S1 | O → A → C → B | P1 → P2 → P4 → P3 |
| S2 | A → B → O → C | P2 → P3 → P1 → P4 |
| S3 | B → C → A → O | P3 → P4 → P2 → P1 |
| S4 | C → O → B → A | P4 → P1 → P3 → P2 |

Create static isomorphic packet set `W` in addition to formal fixtures X/Y/Z.
Index O/A/B/C, P1/P2/P3/P4, S1/S2/S3/S4, and W/X/Y/Z from zero. For a
condition/packet/schedule, use packet variant
`(condition_index + packet_index + schedule_index) mod 4`. Thus a participant
never sees the same packet facts twice, and every condition/packet pair uses
all four variants once per stratum. Freeze all W/X/Y/Z packet keys before
screening.

Show a frame for exactly five seconds, mask it, and collect its two answers.
Each item has four seeded-randomized choices plus `Not sure`; `Not sure` is
incorrect. There is no replay or correctness feedback. Each interface has 64
item attempts and 32 all-correct-frame attempts across the eight screeners.
Human screeners see the normal rendering at 100% zoom; monochrome/pattern and
forced-contrast variants remain frozen reviewer/engineering gates and are not
mixed into the recognition outcome.

P0-2 static-admissibility gates are separate from the later interactive hard
gates. Before ranking, both truth reviewers independently score all 96
obligation cells per interface (four packets × four variants × two obligations
× normal, monochrome/pattern, and forced-contrast renderings); a third reviewer
adjudicates disagreement, and the adjudicated result must be `96/96`. Every
manifest-listed answer-bearing label must be
fully readable with zero clipping or overlap in all 48 frames. A label is
occluded when its bounds are clipped/masked or overlap another label/semantic
target enough to prevent exact reading at 100% zoom; reviewers count occluded
non-answer semantic labels over the manifest denominator.

Before ranking, every static A/B/C manifest must also classify every emitted
object and map 100% of its semantic objects to a canonical planned Evidence
target and, when answer-bearing, a frozen obligation ID. This is a provenance
and information-parity gate, not a claim that static frames already implement
interaction.

If Canvas misses any static truth, readability, or answer-bearing-label gate,
P0-2 stops until the control/packet is repaired, protected evidence passes, and
the new control hashes are frozen in an amendment. A defective Canvas baseline
cannot lower the bar for A/B/C.

A candidate advances only if it passes those static gates, reaches at least
`48/64` exact items and `16/32` all-correct frames overall, and in each stratum
is no worse than Canvas with floors of `24/32` exact items and `8/16`
all-correct frames.
Rank passing A/B/C candidates by exact-item total, all-correct-frame total, then
lower non-answer semantic-label occlusion rate. If fewer than two pass or a tie
remains, revise and amend rather than choosing by preference. The 75% item and
50% frame gates are initial preregistered formative thresholds: with four
choices they prevent relative-only advancement far above chance, but they are
not population estimates.

### Keyboard, contrast, motion, and assistive-technology boundary

The frozen engineering-parity script has exactly nine checkpoints:

- C1 select the study run;
- C2 seek cursor 25;
- C3 focus the named cursor-25 object, open its Evidence target, and return;
- C4 seek cursor 38;
- C5 focus the named cursor-38 object, open its Evidence target, and return;
- C6 seek cursor 44;
- C7 focus the named cursor-44 object, open its Evidence target, and return;
- C8 pause playback;
- C9 resume playback.

C3/C5/C7 are compound checkpoints and fail when any substep fails. Keyboard
mode must complete `9/9` on two fresh loads with visible focus and no trap.
Forced-colors/high-contrast mode at 200% zoom must complete `9/9` once without
clipped answer-bearing content or color-only meaning. Reduced-motion mode must
complete `9/9`, preserve the same semantic snapshots at all three cursors, and
leave no non-essential RAF/CSS animation running 500 ms after pause or terminal
settlement.

For human validation, schedules 1, 3, and 5 in each stratum receive the
high-contrast block and schedules 2, 4, and 6 receive reduced motion. Each
condition therefore has six participants per block, split three engineers and
three learners. Under the frozen platform/browser high-contrast setting, the
participant must identify the variant-key post-transfer owner, distinguish its
inferred decision from the completed handoff without color, and open both
Evidence targets within 120 seconds; the hard gate is `6/6` complete tasks per
condition. In the reduced-motion block, activate the application setting
without reload, replay the variant's transfer and compaction intervals, identify
the keyed owner transition and keyed lossy before/after values, and retain the
static evidence while travel, pan, parallax, bounce, shake, scale, particles,
and ambient loops are absent; the hard gate is `6/6` per condition.

Phase 0 validates DOM/ARIA structure, keyboard operation, forced contrast,
zoom, and reduced motion. It is not NVDA, VoiceOver, screen-reader support, or
WCAG conformance evidence; the manual assistive-technology matrix remains a
later release gate. A future renderer must expose one authoritative semantic
assistive-technology path: when the DOM mirror owns that path, its canvas is
hidden from assistive technology to avoid a duplicate unlabeled world.

### Density ladder operation

The engineering density matrix is mandatory for O, V1, and V2 before the
selection decision. At input levels 12, 28, 64, and 128, run three frozen
deterministic layout seeds and record requested objects, emitted individual and
aggregate semantic objects, LOD membership, discoverable DOM objects, and
resolved Evidence targets. Structural reachability remains 100%, and the
C1–C9 keyboard script must pass at every level. A failure blocks/fixes the
Canvas control or eliminates a candidate; culling objects to shrink the
denominator is not a pass. The current Canvas visual cap above 28 is recorded as
a baseline behavior while its DOM/aggregate obligations still remain.

For every condition/density/seed on the frozen reference desktop, capture a
30-second deterministic replay window after ten seconds of warm-up. A window
fails when frame p95 exceeds 16.7 ms or p99 exceeds 33.3 ms; stable frame loss
is the first density with at least two of three failed windows. A candidate must
meet both initial budgets at all four levels. These are engineering gates, not
validated human thresholds.

Acceptance is per window: all 12 windows for each condition must pass both
budgets. The two-of-three stable-loss level is a diagnostic summary and does
not forgive one failed seed.

Only if candidates remain tied after the earlier criteria, reuse the 12 P0-3
participants for the human ladder and test at most those two directions. At the
same levels in ascending order, freeze a primary and equivalent alternate
layout/target seed. Per level, discovery must find a named target within 30
seconds; classification must state kind, state, and truth class (`3/3`) within
30 seconds; evidence routing must open and name the expected event within 60
seconds; keyboard operation must reach a fresh target and event within 90
seconds without pointer, focus loss, or trap.

Inside each stratum, formal schedules 1/3/5 run V1 then V2 and schedules 2/4/6
run V2 then V1. Odd schedules use seed Alpha as V1 primary and Beta as V2
primary; even schedules use Alpha as V2 primary and Beta as V1 primary. The
other seed is that direction's alternate on a failed measure. This gives each
direction three Alpha-first and three Beta-first participants per stratum.
Complete ascending densities for the first direction before the second, give no
correctness feedback until both finish, and preserve direction/order/seed in
the raw results.

Repeat only a failed measure with its alternate seed. A participant's `stable
loss` for that measure is two failures at the same density; otherwise the first
failure is isolated. Stop that measure after stable loss and record `>128` when
none occurs. For tie-breaking only, rank `12, 28, 64, 128, >128` as 1–5 and
do not extrapolate an object count. A participant's overall semantic density
limit is the earliest stable loss among discovery, classification, evidence
routing, and keyboard operation. Compare that median rank separately by
stratum; only if both strata point the same way may it break the tie. Equal or
opposed stratum ranks remain `revise`; engineering frame data is reported but
does not become an unregistered extra tie-breaker.

## Candidate directions

### A — orthographic cutaway technical anthill (recommended hypothesis)

Front-on or weak-perspective chambers preserve label space and prevent depth
from implying a causal hierarchy. Small Agents provide identity; machines and
rooms encode mechanisms. Low-pixel or low-poly character is permitted only
when status remains readable at L0–L3.

### B — 2.5D isometric anthill factory

This is the strongest game-like candidate. It must pay the full occlusion,
camera, label, and accessibility cost. Screen-facing labels and evidence routes
cannot be hidden by scenery.

### C — dense engineering schematic

This is the information-density control and a possible future monitoring mode.
Ant-colony motifs may aid memory, but the view remains a flat technical systems
map.

Each direction and the static Canvas control contain the same four scene
packets:

- inferred decision and selected explicit link at sequence 17;
- incident open at sequence 25 (`error.raised`);
- context pressure and compaction across sequences 33–38;
- terminal overview at sequence 44 with identical Evidence, Coverage, metric,
  and timeline entry points.

Raw AI-generated mockups are concept material, not study stimuli or production
assets. Before testing, a human must repair text, information parity, unwanted
marks, silhouette consistency, and provenance.

## Study sequence

### P0-1 — current Canvas baseline

Verify the TCMM instrumentation, question rubric, W1–W8 coding,
evidence-route tasks, identity/state recognition, keyboard/reduced-motion
completion, and repeatable performance artifacts on the v0.7.0 control. This
is an instrumentation and task pilot, not the formal candidate comparison. If
the census contingency above triggers, repeat the pilot against the amended,
refrozen control before any later stage.
Use two pilot participants, one Agent engineer and one technical learner.
Anyone exposed to an answer-bearing fixture in P0-1 is excluded from P0-2 and
P0-3, and pilot results are reported separately rather than pooled. A further
pilot requires a preregistration amendment.

### P0-2 — equal-information static screening

Use eight screening participants, four Agent engineers and four technical
learners, under frozen S1–S4 Canvas/A/B/C and packet orders. Test the four-frame
five-second recognition, monochrome/pattern, forced contrast, manifest-based
label occlusion, and independent truth review defined above. W/X/Y/Z packet
rotation prevents identical answer facts from repeating; question-type learning
remains balanced by the interface orders. Screeners do not enter P0-3.

### P0-3 — interactive formative comparison

The current Canvas control (`O`) and the top two screened directions (renamed
`V1` and `V2` regardless of their A/B/C source label) advance together. Retain
`visual_rich_v1.json` as `X`; before recruitment, build `Y` and `Z` and freeze
all three synthetic, human-validated isomorphic fixtures with the same mechanism
graph, truth obligations, difficulty target, and eight-question schema but
different safe entities and values. Publish their hashes, parity review, and
variant-specific answer keys. No participant sees the same story twice.

Use a three-condition within-participant comparison with 12 participants: six
Agent engineers and six technical learners. Within each stratum, assign the
six participants by a recorded preregistered random seed, without replacement,
to these schedules:

| Schedule | Condition order | Fixture order | Exposures |
|---|---|---|---|
| 1 | O → V1 → V2 | X → Y → Z | OX, V1Y, V2Z |
| 2 | V1 → V2 → O | Z → X → Y | V1Z, V2X, OY |
| 3 | V2 → O → V1 | Y → Z → X | V2Y, OZ, V1X |
| 4 | O → V2 → V1 | X → Y → Z | OX, V2Y, V1Z |
| 5 | V2 → V1 → O | Z → X → Y | V2Z, V1X, OY |
| 6 | V1 → O → V2 | Y → Z → X | V1Y, OZ, V2X |

All six condition orders occur once per stratum, and every condition/fixture
pair occurs twice per stratum. If a participant withdraws before completing
all three conditions, exclude that incomplete triplet from paired summaries
and recruit a replacement into the missing stratum/schedule. Preserve and
report condition order, fixture mapping, first-condition results, carryover
patterns, and exclusions. Score free-text answers against frozen keys without
showing the scorer the condition when the response itself does not reveal it.
Present all interfaces under neutral randomized study codes; participants and
answer scorers do not receive the recommended-hypothesis or A/B/C labels.

Question-type familiarity can still carry over even though story facts do not.
The balanced orders control that risk descriptively; they do not make this
small formative study a powered confirmatory experiment.

Every participant completes tasks in this fixed order: all three scheduled
comprehension conditions and revisions; all evidence-route tasks; the assigned
contrast or reduced-motion block; then preference and qualitative interview.
No later task may change an earlier answer or TCMM checkpoint. A condition
becomes an attempt when its prompt and operable interface are shown. A fault
before that point may be repeated and remains logged; any condition-specific
O/V1/V2 renderer or input failure after that point is an interface-reliability
hard-gate failure: Canvas O blocks the study until repair, protected CI,
refreeze, and amendment; V1/V2 is eliminated. Do not replace that participant
to erase the failure or impute comprehension, W, calibration, Evidence, or
accessibility results for the broken condition; publish the partial attempt and
failure artifact separately. An unrelated study-platform fault after start
invalidates the complete triplet, which is reported and replaced under the same
stratum/schedule rather than selectively replaying one condition.

### P0-4 — density ladder

Run the mandatory engineering matrix for O/V1/V2 at 12, 28, 64, and 128 input
semantic objects; 28 is the current Canvas visual cap, not an acceptance
threshold. Only tied candidates enter the human ladder. Record structural/LOD
parity and frame budgets for every condition, plus the first stable human loss
of discovery, classification, evidence routing, and keyboard operability when
that tie-break is required.

### P0-5 — asset-pipeline spike

Create one Agent, one machine, and five to seven semantic actions. Compare
original drawing with AI concept → human review → optional Blender orthographic
normalization → Pixelorama cleanup/export. Stop the Blender path if cleanup
time exceeds a comparable original asset.

### P0-6 — freeze the downstream contract

Publish the selected direction, representative atlas, asset inventory,
bottom-up art estimate, serialized information obligations, and the shared
`VisualModel`/animation/renderer benchmark contract for issues
[#3](https://github.com/BaoBao1996121/agent-flow-visualizer/issues/3),
[#4](https://github.com/BaoBao1996121/agent-flow-visualizer/issues/4), and
[#5](https://github.com/BaoBao1996121/agent-flow-visualizer/issues/5).

## Participants and claims

Recruit 12 P0-3 formative participants: six Agent engineers and six technical
learners. Report individual paired results and separate stratum medians/ranges
before any combined descriptive summary, plus condition and fixture order,
device, prior familiarity, withdrawals, and exclusions. Do not use p-values or
broad population claims for this sample. Pilot and screening participants are
separate and do not count toward these 12.

The later confirmatory sample size must be calculated from Phase 0 variance and
the effect size worth shipping. A prettier screenshot, participant preference,
or GitHub reaction is not a comprehension result.

## Hard gates

P0-2 static directions use only the explicitly listed static-admissibility
gates; they are not rejected for lacking interaction that has not yet been
built. After the top two become click-through V1/V2, the full gates below apply
to the formal interfaces. A Canvas miss blocks recruitment until the control is
repaired/refrozen; a V1/V2 miss eliminates that candidate.

A candidate is eliminated when it:

- emits an object without `information_role` classification;
- marks an object decorative while it carries domain meaning, accepts focus or
  input, or remains in the assistive-technology tree;
- gives any semantic object a missing, broken, wrong-run, or future-cursor
  evidence route instead of 100% structural reachability;
- gives an answer-bearing object no frozen obligation ID, equal-information DOM
  equivalent, or bounded keyboard evidence route;
- weakens truth, causal, unknown, lifecycle, or measurement semantics;
- requires color as the only semantic channel;
- misses any checkpoint in the frozen keyboard, forced-contrast, zoom, or
  reduced-motion scripts;
- misses structural, keyboard, LOD-membership, or reference-frame budgets in
  the mandatory engineering density matrix;
- adds motion that implies unrecorded activity;
- hides critical information behind depth, scenery, animation, or LOD;
- lacks a reviewable right to distribute its assets.

After hard gates pass, compare each candidate with Canvas separately in both
six-person strata. Items 1–6 below must pass independently in each stratum; one
failed stratum fails the candidate. Do not create a weighted composite. For
this formative selection only, use 1,200 seconds as the ranking value for a
right-censored `not_reached` exposure while continuing to report it as censored.
Every earlier item passes before the next is considered:

1. `not_reached` count is no higher than Canvas and median paired
   candidate-minus-Canvas ranking time is below zero;
2. the candidate has no no-response checkpoint in that stratum and its median
   paired first-submission exact-score difference is at least zero;
3. median paired final exact-score difference is at least zero;
4. final positive participant × W-code cells (maximum 48 per stratum) are no
   higher than Canvas;
5. the candidate reaches at least `46/48` Evidence-route successes overall and
   is no lower than Canvas in each 24-trial stratum;
6. high-contrast and reduced-motion blocks each pass `3/3` in each stratum and
   `6/6` overall, in addition to engineering parity gates.

If exactly one candidate advances through item 6, select it. If neither
advances, retain the Canvas information grammar and publish the failures.
If both candidates advance, apply the same partial-order rule at each
tie-breaker: one candidate wins only when it is no worse in either stratum and
strictly better in at least one; opposite stratum directions immediately yield
`revise`. The stratum scalars are frozen as: median of six paired TCMM ranking
differences; total positive cells across six participants × eight final W codes;
and median of six participant calibration MAEs, where each MAE uses that
participant's eight final answers. Compare those scalars in that order. If still
tied, run the human density ladder and use the median of six participants'
earliest-loss ranks per stratum under the same partial-order rule. Any remaining
tie is `revise`, not a preference-based winner. Preference remains diagnostic
only. This is a formative selection rule, not a population-level superiority
claim.

## Engine boundary

Phase 0 does not select an engine by screenshot. The current dependency
preflight is:

- official npm registry resolves `pixi.js@8.19.0` and `phaser@4.2.1` with
  integrity metadata;
- this maintainer workstation's configured npm mirror currently returns 404
  for Phaser 4.2.1;
- benchmark installs must use an explicit isolated registry, committed lockfile,
  resolved URL, and integrity hash without changing global npm configuration;
- PixiJS WebGL is the default candidate; WebGPU, physics, particles, and
  renderer-owned domain state are out of scope;
- PixiJS experimental Canvas is not the product fallback; the existing Canvas
  and semantic DOM remain independent.

## Artifacts required for a decision

- preregistration version and amendment log;
- environment and participant manifests without personal data;
- raw anonymized timing, answers, confidence, W1–W8, recognition, and density
  results;
- current-control and candidate screenshots, interaction recordings, and
  semantic snapshots;
- candidate information-parity checklist;
- accessibility and reduced-motion results;
- asset source, authoring tool/version, review, distribution basis, and SHA-256;
- explicit select / revise / keep-Canvas decision;
- raw performance artifacts kept separate from comprehension results.

Because this maintainer workstation rewrites materialized PNG bytes under its
data-loss-prevention policy, candidate review and golden promotion use immutable
Linux CI artifacts. Local rewritten images must never be promoted by accident.

## Cost boundary

Planning estimate, pending measurement:

| Work | Remaining estimate |
|---|---:|
| Phase 0 instrumentation, W static packets, X/Y/Z fixtures, directions, and report | 8–14 engineer-days |
| Representative direction and assets | 4–7 artist/UX-days |
| Study operations | 5–8 research/facilitation-days for two pilots, eight screeners, 12 P0-3 participants, scheduling, anonymization, double scoring, and adjudication |
| Participant compensation, equipment, and venue | cash budget pending before recruitment; quote and actual spend must be published separately |
| Optional AI concepts | hard cap US$50 for the milestone |

Engineering, participant time, facilitation, double scoring, and human asset
review dominate cost. Research/facilitation-days, recruitment lead time, and
participant cash costs are not included in the engineer/UX-day estimates: the
per-participant amount, total approved budget, actual spend, and calendar lead
time must be recorded before recruitment. The AI image service failed twice at
the network layer on 2026-07-18 and produced no artifact; no API-key CLI
fallback was introduced.

## Amendment log

| Version | Date | Change | Data impact |
|---|---|---|---|
| v1 | 2026-07-18 | Initial eight-question and W1–W8 preregistration. | No data collected. |
| v2 | 2026-07-18 | Removed ambiguous ownership wording; included Canvas in the balanced comparison; fixed three isomorphic fixtures, cohorts and schedules, atomic/blind scoring, object/evidence taxonomy, operational recognition/accessibility/density tasks, fixed decision order, and revised cost. | Supersedes v1 before recruitment; no data collected. |
| v2.1 | 2026-07-18 | Added Canvas and absolute static-recognition gates, eight balanced screeners with W/X/Y/Z packet rotation, symmetric condition failures, mandatory engineering density evidence, explicit C1–C9, Canvas preflight repair branch, and fully stratum-specific decision rules. | Supersedes v2 before recruitment; no data collected. |
| v2.2 | 2026-07-18 | Separated static planned Evidence targets from interactive routes; froze no-response scoring and condition-specific failure hard gates; required adjudicated static truth, normal-mode screening, per-window density acceptance, and explicit single-candidate selection. | Supersedes v2.1 before recruitment; no data collected. |

## Amendment rule

Any change after this version requires a dated issue comment and a committed
document revision explaining the reason. Results gathered under different
versions remain separate unless a published analysis justifies pooling them.

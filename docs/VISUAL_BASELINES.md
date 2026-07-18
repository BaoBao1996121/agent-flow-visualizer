# Deterministic visual baselines

## Status

The first four pinned-Linux goldens are reviewed, committed, and protected by a
required compare job with update mode disabled. The first required comparison
passed without rewriting them in
[run 29639244683](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29639244683).
The same check is required by `main` branch protection. Windows output remains
diagnostic only and must not be promoted as the Linux baseline.

## Reproducibility contract

The visual suite is isolated from the ordinary browser contracts by
`playwright.visual.config.mjs` and `tests/visual/`.

| Boundary | Frozen value |
|---|---|
| Input | `tests/fixtures/visual_rich_v1.json`, synthetic Apache-2.0 fixture |
| Browser package | `@playwright/test` 1.61.1 from `package-lock.json` |
| Python server runtime | Python 3.12.13 plus exact package versions in `requirements-visual.txt` |
| Runtime image | `mcr.microsoft.com/playwright:v1.61.1-noble-amd64@sha256:cf0daee9b994042e011bc29f20cdff1a9f682a039b43fcd738f7d8a9d3bcd9d6` |
| Viewport | 1600 × 1000 CSS pixels, device scale factor 1 |
| Context | `en-US`, UTC, dark color scheme, reduced motion |
| Application | `?static=1`, app motion override `reduce`, `document.fonts.ready` |
| Comparison | Playwright threshold 0.2 and max differing-pixel ratio 0.001 |

The pixel ratio is an initial conservative value, pending calibration from repeat
runs in the pinned container. System fallback fonts are controlled by the pinned
image but are not vendored; changing the image digest therefore requires visual
review even when the Playwright package version is unchanged.
Python 3.12.13 is pinned as the visual server interpreter; it is an official
3.12 security release ([Python.org](https://www.python.org/downloads/release/python-31213/)).

The four scenes are overview, explicit error evidence, instrumentation coverage,
and comparison of the complete fixture with its deterministic pre-compaction
prefix. The prefix contains events 0–30 and changes only `run_id`; it does not
invent a second event stream.

### Browser-only display normalization

The production JSONL store deliberately stamps `observed_at` with the actual
append time. That real ingestion fact feeds `manifest.created_at` and the
tamper-evident event hash chain, so neither production value is changed for a
visual test.

Before its first navigation, the visual harness installs a page-scoped response
route. Only synthetic `visual-*` runs are normalized: the run selector receives
the fixture's fixed creation/update time and a stable run ordering. Event
responses receive the fixed fixture `observed_at` plus deterministic 64-character
display hashes derived from
`TEST-HARNESS:visual-integrity:<run_id>:<ingest_seq>` and the explicit algorithm
label `sha256-test-harness-display`. Ingestion requests, ledger files, projection
responses, and the real `/integrity` verification endpoint are untouched. The
normalization removes wall-clock pixels; it is not evidence that the placeholder
hashes are production ledger hashes.

Static capture also suppresses Compare's background manifest refresh. The visual
test asserts that switching to Compare issues no second run-list request before
capture, preventing a transient `REFRESHING` banner from entering a golden.

The image digest was read from the MCR Registry v2 manifest endpoint on
2026-07-18. Playwright recommends an exact matching image/package version and
`--ipc=host` for Chromium. Sources: [Playwright Docker](https://playwright.dev/docs/docker),
[GitHub job containers](https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/run-jobs-in-a-container).

## Reviewed baseline provenance

[GitHub Actions run 29638608292](https://github.com/BaoBao1996121/agent-flow-visualizer/actions/runs/29638608292)
at commit `a3b2a7e` passed all nine jobs and generated the
`visual-baseline-candidate` artifact with digest
`sha256:b8fb562de19ecd32ef449505e0178395abf6e68b4559708c6124ea7e15467c71`.
All four 1600 x 1000 images were reviewed before promotion. The plaintext PNG
hashes read from that artifact are:

| Scene | SHA-256 |
|---|---|
| `overview.png` | `daf0013ed457e3f7e826a63b7eb8916fd3c51b16af1432bf3efff76627f9598a` |
| `evidence.png` | `cb2900851940a0b44072d8d9d1001b7a994af80960fb361150e05d16b19674c6` |
| `coverage.png` | `00e2c2e6550529b09a2e6f22bc302209eb871ef5467d2fbe4abaa623590f2a53` |
| `compare.png` | `54a78b72a9bb56ceb8f3f0de60c5a56573cd428d19cf3d2c4ab7fb3477e8309e` |

The artifact contains only synthetic fixture output. Reports and traces were not
promoted. At commit `6a96011`, run 29639244683 passed all nine jobs; its
`Pinned Chromium visual regression` lane compared the committed files with
`ANTHILL_UPDATE_VISUALS=0`. Repository protection was then verified with
`strict=true`, administrator enforcement enabled, and that check registered as
the ninth required context.

## Intentional baseline updates

For an intentional later UI change, temporarily generate a candidate in a review
PR, inspect the artifact, commit only accepted PNGs, and return the job to compare
mode before merge. Never update goldens from a developer OS. The visual config
prevents accidental updates by requiring Linux plus the workflow's expected-image
marker. That environment variable is self-reported, not runtime attestation; the
actual environment boundary is the workflow's digest-pinned `container.image`
plus review of workflow changes.

## Verification commands

These checks are safe on the current Windows workstation and do not create
goldens:

```powershell
python -m pytest -q tests/test_visual_fixtures.py tests/test_visual_baseline_contract.py
node --check playwright.visual.config.mjs
node --check tests/visual/anthill.visual.spec.mjs
npx playwright test --config=playwright.visual.config.mjs --list
```

`npm run test:visual` is the compare-mode command. The authoritative result is
the required pinned-Linux CI job. Candidate generation is reserved for an
explicit review change in the digest-pinned CI environment through
`ANTHILL_UPDATE_VISUALS=1`; it must never remain enabled in a mergeable change.

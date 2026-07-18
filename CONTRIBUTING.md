# Contributing to Agent Anthill

Thank you for helping make Agent systems easier to inspect and understand.

## Before opening code

For significant protocol, projector, storage, or visual-language changes, open a design discussion first. State:

- the user question the change answers;
- the authoritative evidence available;
- what remains unknown;
- how a user can drill back to source;
- privacy and compatibility impact.

## Local setup

```bash
python -m venv .venv
```

Activate with one shell-appropriate command:

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

Validation depth is staged so exploration stays fast without weakening protected
`main`. During S0 exploration, run the narrow test file and syntax check for the
module being changed. Opening or updating a pull request runs the current
fixed-subset `Exploration fast gate`; before merge, the complete S2 matrix remains
mandatory. The canonical runner,
change-impact map, and manifests are still under development, so unknown-impact,
workflow, dependency, container, browser-harness, and visual-golden changes must
wait for hosted S2; run the broad local preflight below before publishing. See
[validation stages](docs/VALIDATION_STAGES.md) for current versus planned behavior.

The advisory S0 candidate can produce a deterministic plan or run manifest:

```bash
python -m validation plan --base-ref origin/main
python -m validation run --base-ref origin/main --report output/validation/s0.json
```

An explicit repeated `--path` is useful for a caller-scoped local check, but it
does not claim complete Git discovery or merge evidence. Exit code `2` means the
feedback is incomplete or requires hosted S2; it is not a green promotion signal.
Reports written inside the repository must be Git-ignored; the CLI rejects a
tracked or unignored destination so its own output cannot alter validated input.

Run the broad local preflight toward S2; authoritative complete S2 remains hosted:

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

The hosted container and pinned-Linux visual jobs remain authoritative boundaries
that this workstation may not reproduce. A Draft PR can therefore show a green
`Exploration fast gate` and an intentionally red `Protected main validation gate`.
The six complete S2 job definitions are skipped in Draft; the red required
aggregate means full merge validation has not been requested. Mark the PR Ready
to trigger the complete matrix. A product-test failure remains a real failure
and must not be relabelled as this expected Draft state.

On Linux or CI, use `npx playwright install --with-deps chromium`. The browser
suite owns `127.0.0.1:8878` and an ignored ledger under `output/playwright/`; it
does not reuse or modify a developer's `8765` service.

Browser fixtures must be synthetic, public, or explicitly licensed/approved.
Failure traces, screenshots, and HTML reports can retain DOM, page, and request
data, so never run the committed suite against a private real trace.

## Breakthrough records

Every bounded stage breakthrough must be appended to
[the stage log](docs/STAGE_LOG.md) in the same working session. Record the ISO
timestamp, evidence level, action, measured effect, evidence link, and important
limit, plus the machine-audited screenshot-status field. Frontend or interaction
stages must also attach a screenshot of the exact state under test, preferably as
a hosted Playwright attachment. A screenshot is supporting evidence, never a
replacement for semantic and accessibility checks.

## Pull-request expectations

- Keep the canonical event envelope renderer-independent.
- Never label inferred behavior as observed.
- Add or update tests for every protocol/reducer behavior.
- Preserve metadata-only defaults.
- Document migrations and known blind spots.
- Do not include real private traces, credentials, proprietary prompts, or unlicensed art.
- Keep legacy Source X-Ray behavior working unless the PR includes a documented migration.
- Include a screenshot for deliberate UI changes and test at 1600×1000 plus one narrow viewport.

## Adapter contributions

Read [the adapter guide](docs/ADAPTER_GUIDE.md). An adapter PR is incomplete without a synthetic/licensed golden fixture, expected canonical output, projection assertions, coverage notes, and privacy tests.

## Event vocabulary changes

Prefer a namespaced extension first. Promote it to `CoreEventType` when at least two sources share stable semantics. A new event should define:

- semantic boundary;
- subject identity;
- lifecycle peers;
- causal expectations;
- minimum payload and measurements;
- privacy considerations;
- projection behavior.

## Visual changes

The pixel world is an information projection. New animation must have an event/source path and a non-animated accessibility fallback in the DOM inspector. Do not imitate copyrighted game characters, maps, music, or sprites.

## Commit and review hygiene

- Keep changes focused and explain tradeoffs.
- Do not rewrite unrelated user work.
- Run the full test and lint commands.
- Treat reviewer requests about evidence quality, privacy, and replay safety as release blockers.
- Escalate unknown impact to the complete S2 matrix; never let generated code or model output choose its own validation depth.

By contributing, you agree that your contribution is licensed under Apache-2.0.

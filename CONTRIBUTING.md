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
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest -q
ruff check --no-cache anthill analyzer tracer tests server.py
node --check static/js/anthill.js
```

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

By contributing, you agree that your contribution is licensed under Apache-2.0.

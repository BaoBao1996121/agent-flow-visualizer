import { expect, test } from '@playwright/test';

function canonicalEvent(runId, eventId, eventType, extra = {}) {
  return {
    schema_version: '0.1.0',
    event_id: `${runId}:${eventId}`,
    event_type: eventType,
    run_id: runId,
    source: { adapter: 'playwright.fixture', fidelity: 'native' },
    evidence: { level: 'observed', confidence: 1 },
    ...extra,
  };
}

async function ingestRun(request, runId, events) {
  const response = await request.post(`/api/anthill/runs/${runId}/events`, {
    data: { events },
  });
  expect(response.status(), await response.text()).toBe(201);
}

async function createDemo(page) {
  await page.goto('/anthill');
  const select = page.locator('#run-select');
  const previousRunId = await select.inputValue();
  const button = page.getByRole('button', { name: '＋ 一键展品' });
  await button.click();
  await expect(select).not.toHaveValue(previousRunId);
  await expect(button).toBeEnabled();
  await expect(page.locator('#run-status')).toHaveText('COMPLETED');
  return select.inputValue();
}

test('isolated observatory loads without browser errors', async ({ page }) => {
  await page.route(
    url => url.pathname === '/api/anthill/runs',
    route => route.fulfill({ json: [] }),
  );
  const errors = [];
  page.on('console', message => {
    if (message.type() === 'error') errors.push(message.text());
  });
  page.on('pageerror', error => errors.push(error.message));

  await page.goto('/anthill');

  await expect(page).toHaveTitle('Agent Anthill — Runtime Observatory');
  await expect(page.getByRole('button', { name: '＋ 一键展品' })).toBeVisible();
  await expect(page.getByRole('heading', { name: '事件账本还是空的' })).toBeVisible();
  await expect(page.locator('.cognition-section .section-code')).toHaveText('AT CURSOR');
  for (const selector of [
    '#memory-working', '#memory-episodic', '#memory-semantic', '#compact-status',
  ]) {
    await expect(page.locator(selector)).toHaveText('NOT OBSERVED');
  }
  expect(errors).toEqual([]);
});

test('visual contract uses the canonical desktop viewport', async ({ page }) => {
  expect(page.viewportSize()).toEqual({ width: 1600, height: 1000 });
});

test('completed run at the ledger head is not described as live', async ({ page }) => {
  await createDemo(page);

  await expect(page.locator('#run-status')).toHaveText('COMPLETED');
  await expect(page.locator('#world-mode')).toHaveText('AT HEAD · FOLLOWING');
  await expect(page.locator('#follow-live')).toHaveText('FOLLOW HEAD');
  await expect(page.locator('#connection-state')).toHaveAttribute('data-state', 'connected');
  await expect(page.locator('#connection-label')).toHaveText('LEDGER CONNECTED');
  await expect(page.locator('#world-mode')).not.toContainText('LIVE');
  await expect(page.locator('#follow-live')).not.toContainText('LIVE');
  await expect(page.locator('#connection-state')).not.toContainText('LIVE');
  const indicatorAnimation = await page.locator('.connection-dot').evaluate(
    dot => getComputedStyle(dot).animationName,
  );
  expect(indicatorAnimation).toBe('none');
});

test('completed run labels unfinished chamber activity as unresolved', async ({ page, request }) => {
  const runId = `phase1-unresolved-${Date.now()}`;
  await ingestRun(request, runId, [
    canonicalEvent(runId, 'run-started', 'run.started'),
    canonicalEvent(runId, 'agent-started', 'agent.started', {
      agent_id: 'agent-open',
      subject: {
        kind: 'agent',
        id: 'agent-open',
        name: 'Open Worker',
      },
    }),
    canonicalEvent(runId, 'run-completed', 'run.completed', {
      payload: { status: 'success' },
    }),
  ]);

  await page.goto('/anthill');
  await page.locator('#run-select').selectOption(runId);

  await expect(page.locator('#run-status')).toHaveText('COMPLETED');
  const unresolvedChamber = page.locator('#chamber-list .chamber-item.unresolved');
  await expect(unresolvedChamber).toHaveCount(1);
  await expect(unresolvedChamber.locator('b')).toHaveText('1 UNRESOLVED');
  await expect(unresolvedChamber).not.toHaveClass(/active/);
  const indicatorAnimation = await unresolvedChamber.locator('i').evaluate(
    dot => getComputedStyle(dot).animationName,
  );
  expect(indicatorAnimation).toBe('none');
  await expect(page.locator('#chamber-list')).not.toContainText('LIVE');
});

test('interrupted run is terminal and leaves no activity ticker running', async ({ page, request }) => {
  await page.addInitScript(() => {
    const requestFrame = window.requestAnimationFrame.bind(window);
    window.__anthillRafCalls = 0;
    window.requestAnimationFrame = callback => {
      window.__anthillRafCalls += 1;
      return requestFrame(callback);
    };
  });
  const runId = `phase1-interrupted-${Date.now()}`;
  await ingestRun(request, runId, [
    canonicalEvent(runId, 'run-started', 'run.started'),
    canonicalEvent(runId, 'agent-started', 'agent.started', {
      agent_id: 'agent-interrupted',
      subject: { kind: 'agent', id: 'agent-interrupted', name: 'Interrupted Worker' },
    }),
    canonicalEvent(runId, 'run-completed', 'run.completed', {
      payload: { status: 'interrupted' },
    }),
  ]);

  await page.goto('/anthill');
  await page.locator('#run-select').selectOption(runId);
  await expect(page.locator('#run-status')).toHaveText('INTERRUPTED');
  await expect(page.locator('#chamber-list .chamber-item.unresolved b')).toHaveText('1 UNRESOLVED');
  const before = await page.locator('#anthill-canvas').evaluate(canvas => ({
    frame: canvas.toDataURL(), rafCalls: window.__anthillRafCalls,
  }));
  await page.waitForTimeout(350);
  const after = await page.locator('#anthill-canvas').evaluate(canvas => ({
    frame: canvas.toDataURL(), rafCalls: window.__anthillRafCalls,
  }));
  expect(after).toEqual(before);
});

test('terminal context overflow keeps its warning but stops pulsing', async ({ page, request }) => {
  const runId = `phase1-terminal-overflow-${Date.now()}`;
  await ingestRun(request, runId, [
    canonicalEvent(runId, 'run-started', 'run.started'),
    canonicalEvent(runId, 'budget', 'context.budget.updated', {
      payload: { budget_tokens: 100, used_tokens: 120 },
    }),
    canonicalEvent(runId, 'overflow', 'context.overflow.detected', {
      payload: { budget_tokens: 100, used_tokens: 120 },
    }),
    canonicalEvent(runId, 'run-completed', 'run.completed', {
      payload: { status: 'success' },
    }),
  ]);

  await page.goto('/anthill');
  await page.locator('#run-select').selectOption(runId);
  await expect(page.locator('#run-status')).toHaveText('COMPLETED');
  await expect(page.locator('body')).toHaveAttribute('data-run-terminal', 'true');
  await expect(page.locator('#context-fill')).toHaveClass(/overflow/);
  const animationName = await page.locator('#context-fill').evaluate(
    fill => getComputedStyle(fill).animationName,
  );
  expect(animationName).toBe('none');
});

test('missing cognition telemetry is not rendered as zero or idle', async ({ page, request }) => {
  const runId = `phase1-no-cognition-${Date.now()}`;
  await ingestRun(request, runId, [
    canonicalEvent(runId, 'run-started', 'run.started'),
    canonicalEvent(runId, 'run-completed', 'run.completed', {
      payload: { status: 'success' },
    }),
  ]);

  await page.goto('/anthill');
  await page.locator('#run-select').selectOption(runId);

  const unobservedValues = [
    '#context-label', '#memory-working', '#memory-episodic',
    '#memory-semantic', '#compact-status',
  ];
  for (const selector of unobservedValues) {
    await expect(page.locator(selector)).toHaveText('NOT OBSERVED');
  }
});

test('completed run freezes decorative canvas motion and its ticker', async ({ page }) => {
  await page.addInitScript(() => {
    const requestFrame = window.requestAnimationFrame.bind(window);
    window.__anthillRafCalls = 0;
    window.requestAnimationFrame = callback => {
      window.__anthillRafCalls += 1;
      return requestFrame(callback);
    };
  });

  await createDemo(page);

  const before = await page.locator('#anthill-canvas').evaluate(canvas => ({
    frame: canvas.toDataURL(), rafCalls: window.__anthillRafCalls,
  }));
  await page.waitForTimeout(350);
  const after = await page.locator('#anthill-canvas').evaluate(canvas => ({
    frame: canvas.toDataURL(), rafCalls: window.__anthillRafCalls,
  }));
  expect(after.frame).toBe(before.frame);
  expect(after.rafCalls).toBe(before.rafCalls);
});

test('timeline cursor event is the default causal root', async ({ page, request }) => {
  const runId = await createDemo(page);
  const response = await request.get(`/api/anthill/runs/${runId}/world`);
  expect(response.status(), await response.text()).toBe(200);
  const cursorEventId = (await response.json()).state.cursor_event_id;

  await page.locator('.inspector-tabs button[data-tab="causal"]').click();
  const root = page.locator('#causal-graph .causal-node.root');
  await expect(root).toBeVisible();
  await expect(root).toHaveAttribute('data-event-id', cursorEventId);
  await expect(page.locator('#causal-heading')).toHaveText(/events · \d+ explicit links/);
});

test('an open causal panel follows the timeline cursor', async ({ page, request }) => {
  const runId = await createDemo(page);
  const headResponse = await request.get(`/api/anthill/runs/${runId}/world`);
  const startResponse = await request.get(`/api/anthill/runs/${runId}/world?at_seq=0`);
  expect(headResponse.status(), await headResponse.text()).toBe(200);
  expect(startResponse.status(), await startResponse.text()).toBe(200);
  const headEventId = (await headResponse.json()).state.cursor_event_id;
  const startEventId = (await startResponse.json()).state.cursor_event_id;
  expect(startEventId).not.toBe(headEventId);

  await page.locator('.inspector-tabs button[data-tab="causal"]').click();
  const root = page.locator('#causal-graph .causal-node.root');
  await expect(root).toHaveAttribute('data-event-id', headEventId);

  await page.locator('#jump-start').click();

  await expect(page.locator('#world-mode')).toHaveText('HISTORY · SEQ 0');
  await expect(root).toHaveAttribute('data-event-id', startEventId);
});

test('a stale causal direction response cannot overwrite the latest request', async ({ page, request }) => {
  const runId = await createDemo(page);
  const response = await request.get(`/api/anthill/runs/${runId}/world`);
  expect(response.status(), await response.text()).toBe(200);
  const eventId = (await response.json()).state.cursor_event_id;
  let markAncestorsStarted;
  const ancestorsStarted = new Promise(resolve => {
    markAncestorsStarted = resolve;
  });

  await page.route('**/api/anthill/runs/**/causal/**', async route => {
    const direction = new URL(route.request().url()).searchParams.get('direction');
    if (direction === 'ancestors') {
      markAncestorsStarted();
      await new Promise(resolve => setTimeout(resolve, 250));
    }
    await route.fulfill({
      json: {
        root_event_id: eventId,
        nodes: [{
          event_id: eventId,
          seq: 0,
          event_type: `test.${direction}`,
          summary: direction,
          depth: 0,
          evidence: { level: 'observed', confidence: 1 },
        }],
        edges: [],
      },
    });
  });

  await page.locator('.inspector-tabs button[data-tab="causal"]').click();
  await ancestorsStarted;
  await page.locator('.causal-controls button[data-direction="descendants"]').click();
  const rootType = page.locator('#causal-graph .causal-node.root strong');
  await expect(rootType).toContainText('test.descendants');
  await page.waitForTimeout(350);
  await expect(rootType).toContainText('test.descendants');
});

test('a stale world response cannot overwrite a newly selected run', async ({ page, request }) => {
  const suffix = Date.now();
  const runA = `phase1-switch-a-${suffix}`;
  const runB = `phase1-switch-b-${suffix}`;
  await ingestRun(request, runA, [
    canonicalEvent(runA, 'run-started', 'run.started'),
    canonicalEvent(runA, 'agent-started', 'agent.started', {
      agent_id: 'agent-a',
      subject: { kind: 'agent', id: 'agent-a', name: 'Run A Worker' },
    }),
  ]);
  await ingestRun(request, runB, [
    canonicalEvent(runB, 'run-started', 'run.started'),
    canonicalEvent(runB, 'run-completed', 'run.completed', {
      payload: { status: 'success' },
    }),
  ]);

  await page.goto('/anthill');
  await page.locator('#run-select').selectOption(runA);
  await expect(page.locator('#run-status')).toHaveText('RUNNING');

  let markStaleStarted;
  let releaseStale;
  const staleStarted = new Promise(resolve => {
    markStaleStarted = resolve;
  });
  const staleRelease = new Promise(resolve => {
    releaseStale = resolve;
  });
  await page.route(
    url => url.pathname === `/api/anthill/runs/${runA}/world`
      && url.searchParams.get('at_seq') === '0',
    async route => {
      const response = await route.fetch();
      markStaleStarted();
      await staleRelease;
      try {
        await route.fulfill({ response });
      } catch {
        // A correct implementation aborts this request when the run changes.
      }
    },
  );

  await page.locator('#jump-start').click();
  await staleStarted;
  await page.locator('#run-select').selectOption(runB);
  await expect(page.locator('#run-status')).toHaveText('COMPLETED');
  await expect(page.locator('#world-mode')).toHaveText('AT HEAD · FOLLOWING');

  releaseStale();
  await page.waitForTimeout(350);

  await expect(page.locator('#run-select')).toHaveValue(runB);
  await expect(page.locator('#run-status')).toHaveText('COMPLETED');
  await expect(page.locator('#world-mode')).toHaveText('AT HEAD · FOLLOWING');
  await expect(page.locator('#connection-state')).toHaveAttribute('data-state', 'connected');
});

test('inspector tabs expose selection and support roving arrow-key navigation', async ({ page }) => {
  await page.goto('/anthill');

  const tablist = page.getByRole('tablist', { name: '证据检查器分区' });
  const stateTab = tablist.getByRole('tab', { name: 'STATE' });
  const coverageTab = tablist.getByRole('tab', { name: 'COVERAGE' });

  await expect(stateTab).toHaveAttribute('aria-selected', 'true');
  await expect(stateTab).toHaveAttribute('aria-controls', 'state-panel');
  await expect(stateTab).toHaveAttribute('tabindex', '0');
  await expect(coverageTab).toHaveAttribute('aria-selected', 'false');
  await expect(coverageTab).toHaveAttribute('tabindex', '-1');
  await expect(page.getByRole('tabpanel', { name: 'STATE' })).toBeVisible();

  await stateTab.focus();
  await stateTab.press('ArrowRight');

  await expect(coverageTab).toBeFocused();
  await expect(coverageTab).toHaveAttribute('aria-selected', 'true');
  await expect(coverageTab).toHaveAttribute('tabindex', '0');
  await expect(stateTab).toHaveAttribute('aria-selected', 'false');
  await expect(stateTab).toHaveAttribute('tabindex', '-1');
  await expect(page.getByRole('tabpanel', { name: 'COVERAGE' })).toBeVisible();
  await expect(page.locator('#state-panel')).toBeHidden();
});

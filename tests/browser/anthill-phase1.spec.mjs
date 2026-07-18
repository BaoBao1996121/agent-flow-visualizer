import { expect, test } from '@playwright/test';

function canonicalEvent(runId, eventId, eventType, extra = {}) {
  return {
    schema_version: '0.2.0',
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

async function fetchRunListing(request) {
  const response = await request.get('/api/anthill/runs?limit=500');
  expect(response.status()).toBe(200);
  return response.json();
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

  await page.route(
    url => url.pathname === `/api/anthill/runs/${runId}/causal`,
    async route => {
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
    },
  );

  await page.locator('.inspector-tabs button[data-tab="causal"]').click();
  await ancestorsStarted;
  await page.locator('.causal-controls button[data-direction="descendants"]').click();
  const rootType = page.locator('#causal-graph .causal-node.root strong');
  await expect(rootType).toContainText('test.descendants');
  await page.waitForTimeout(350);
  await expect(rootType).toContainText('test.descendants');
});

test('event detail and causality preserve an exact dot-segment event ID', async ({ page, request }) => {
  const runId = `dot-event-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  await ingestRun(request, runId, [
    canonicalEvent(runId, 'started', 'run.started', {
      payload: { title: 'Dot segment event query' },
    }),
  ]);
  const worldResponse = await request.get(`/api/anthill/runs/${runId}/world`);
  expect(worldResponse.status(), await worldResponse.text()).toBe(200);
  const rootEventId = (await worldResponse.json()).state.cursor_event_id;
  const dotEvent = canonicalEvent(runId, 'placeholder', 'artifact.created', {
    event_id: '..',
    clock: {
      occurred_at: '2026-07-18T00:00:00Z',
      observed_at: '2026-07-18T00:00:00Z',
      ingest_seq: 99,
    },
    subject: { kind: 'artifact', id: 'dot-artifact', name: 'Dot artifact' },
    payload: { summary: 'Exact dot-segment event' },
  });
  const eventQueryIds = [];
  const causalQueryIds = [];

  await page.route(
    url => url.pathname === `/api/anthill/runs/${runId}/event`,
    async route => {
      const eventId = new URL(route.request().url()).searchParams.get('event_id');
      eventQueryIds.push(eventId);
      await route.fulfill({
        status: eventId === '..' ? 200 : 404,
        json: eventId === '..' ? dotEvent : { detail: 'unexpected event ID' },
      });
    },
  );
  await page.route(
    url => url.pathname === `/api/anthill/runs/${runId}/causal`,
    async route => {
      const eventId = new URL(route.request().url()).searchParams.get('event_id');
      causalQueryIds.push(eventId);
      const exactDotRequest = eventId === '..';
      await route.fulfill({
        json: {
          root_event_id: exactDotRequest ? '..' : rootEventId,
          nodes: exactDotRequest ? [{
            event_id: '..',
            seq: 99,
            event_type: 'artifact.created',
            summary: 'Exact dot-segment event',
            depth: 0,
            evidence: { level: 'observed', confidence: 1 },
          }] : [{
            event_id: rootEventId,
            seq: 0,
            event_type: 'run.started',
            summary: 'Root event',
            depth: 0,
            evidence: { level: 'observed', confidence: 1 },
          }, {
            event_id: '..',
            seq: 99,
            event_type: 'artifact.created',
            summary: 'Exact dot-segment event',
            depth: 1,
            evidence: { level: 'observed', confidence: 1 },
          }],
          edges: [],
        },
      });
    },
  );

  await page.goto('/anthill');
  await page.locator('#run-select').selectOption(runId);
  await page.locator('.view-button[data-view="causal"]').click();
  const dotNode = page.locator('#causal-graph .causal-node[data-event-id=".."]');
  await expect(dotNode).toBeVisible();
  await dotNode.click();

  await expect.poll(() => eventQueryIds.includes('..')).toBe(true);
  await expect.poll(() => causalQueryIds.includes('..')).toBe(true);
  await expect(page.locator('#event-heading')).toHaveText('artifact.created');
  await expect(page.locator('#event-detail')).toContainText('EVENT ID');
  await expect(page.locator('#event-detail')).toContainText('..');
  await expect(page.locator('#causal-graph .causal-node.root'))
    .toHaveAttribute('data-event-id', '..');
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

test('a failed run selection restores the previously committed run atomically', async ({ page, request }) => {
  const suffix = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const runA = `load-atomic-a-${suffix}`;
  const runB = `load-atomic-b-${suffix}`;
  await ingestRun(request, runA, [
    canonicalEvent(runA, 'started', 'run.started', { payload: { title: 'Atomic run A' } }),
    canonicalEvent(runA, 'agent', 'agent.started', {
      agent_id: 'atomic-agent-a',
      subject: { kind: 'agent', id: 'atomic-agent-a', name: 'Atomic A Worker' },
    }),
  ]);
  await ingestRun(request, runB, [
    canonicalEvent(runB, 'started', 'run.started', { payload: { title: 'Atomic run B' } }),
    canonicalEvent(runB, 'completed', 'run.completed', { payload: { status: 'success' } }),
  ]);
  await page.goto('/anthill');
  await page.locator('#run-select').selectOption(runA);
  await expect(page.locator('#run-status')).toHaveText('RUNNING');
  await expect(page.locator('#state-stack')).toContainText('Atomic A Worker');
  await expect(page.locator(`#run-select option[value="${runB}"]`)).toContainText('COMPLETED');
  await expect(page.locator('#connection-state')).toHaveAttribute('data-state', 'connected');

  await page.route(
    url => url.pathname === `/api/anthill/runs/${runB}/world`,
    route => route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'deliberate world failure' }),
    }),
  );
  await page.locator('#run-select').selectOption(runB);

  await expect(page.locator('#canvas-tooltip')).toContainText('deliberate world failure');
  await expect(page.locator('#run-select')).toHaveValue(runA);
  await expect(page.locator('#connection-state')).toHaveAttribute('data-state', 'connected');
  await expect(page.locator('#world-empty')).toBeHidden();
  await expect(page.locator('#run-title')).toHaveText('Atomic run A');
  await expect(page.locator('#run-status')).toHaveText('RUNNING');
  await expect(page.locator('#state-stack')).toContainText('Atomic A Worker');
  await expect(page.locator('#timeline-seq')).toHaveText('SEQ 1');
  await expect(page.locator('#integrity-status')).toHaveText('HASH CHAIN VALID');
  await page.unrouteAll({ behavior: 'wait' });
});

test('a failed selection after an in-flight selection restores the last committed run', async ({ page, request }) => {
  const suffix = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const runA = `load-committed-a-${suffix}`;
  const runB = `load-inflight-b-${suffix}`;
  const runC = `load-failing-c-${suffix}`;
  await ingestRun(request, runC, [
    canonicalEvent(runC, 'started', 'run.started', { payload: { title: 'Failing run C' } }),
  ]);
  await ingestRun(request, runB, [
    canonicalEvent(runB, 'started', 'run.started', { payload: { title: 'Pending run B' } }),
    canonicalEvent(runB, 'agent', 'agent.started', {
      agent_id: 'pending-agent-b',
      subject: { kind: 'agent', id: 'pending-agent-b', name: 'Pending B Worker' },
    }),
  ]);
  await ingestRun(request, runA, [
    canonicalEvent(runA, 'started', 'run.started', { payload: { title: 'Stable run A' } }),
    canonicalEvent(runA, 'agent', 'agent.started', {
      agent_id: 'stable-agent-a',
      subject: { kind: 'agent', id: 'stable-agent-a', name: 'Stable A Worker' },
    }),
  ]);

  let markBWorldHeld;
  let releaseBWorld;
  const bWorldHeld = new Promise(resolve => { markBWorldHeld = resolve; });
  const bWorldRelease = new Promise(resolve => { releaseBWorld = resolve; });
  await page.route(
    url => url.pathname === `/api/anthill/runs/${runB}/world`,
    async route => {
      const response = await route.fetch();
      markBWorldHeld();
      await bWorldRelease;
      try {
        await route.fulfill({ response });
      } catch {
        // The later selection invalidates this in-flight load.
      }
    },
  );
  await page.route(
    url => url.pathname === `/api/anthill/runs/${runC}/world`,
    route => route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'deliberate C failure' }),
    }),
  );

  await page.goto('/anthill');
  await page.locator('#run-select').selectOption(runA);
  await expect(page.locator('#run-title')).toHaveText('Stable run A');
  await expect(page.locator('#state-stack')).toContainText('Stable A Worker');
  await expect(page.locator('#connection-state')).toHaveAttribute('data-state', 'connected');

  try {
    await page.locator('#run-select').selectOption(runB);
    await bWorldHeld;
    await page.locator('#run-select').selectOption(runC);

    await expect(page.locator('#canvas-tooltip')).toContainText('deliberate C failure');
    await expect(page.locator('#run-select')).toHaveValue(runA);
    await expect(page.locator('#run-title')).toHaveText('Stable run A');
    await expect(page.locator('#run-status')).toHaveText('RUNNING');
    await expect(page.locator('#state-stack')).toContainText('Stable A Worker');
    await expect(page.locator('#state-stack')).not.toContainText('Pending B Worker');
    await expect(page.locator('#world-empty')).toBeHidden();
    await expect(page.locator('#connection-state')).toHaveAttribute('data-state', 'connected');
  } finally {
    releaseBWorld();
  }
  await page.unrouteAll({ behavior: 'ignoreErrors' });
});

test('main and compare selectors expose the same unambiguous run identity', async ({ page, request }) => {
  const suffix = Date.now();
  const runA = `alpha000-${suffix}-running`;
  const runB = `beta0000-${suffix}-done001`;
  const anchorRun = `anchor00-${suffix}-current`;
  const source = adapter => ({ adapter, fidelity: 'native' });

  await ingestRun(request, runA, [
    canonicalEvent(runA, 'run-started', 'run.started', {
      source: source('fixture.alpha'),
      payload: { title: 'Shared task' },
    }),
    canonicalEvent(runA, 'agent-spawned', 'agent.spawned', {
      source: source('fixture.alpha'),
    }),
  ]);
  await ingestRun(request, runB, [
    canonicalEvent(runB, 'run-started', 'run.started', {
      source: source('fixture.beta'),
      payload: { title: 'Shared task' },
    }),
    canonicalEvent(runB, 'run-completed', 'run.completed', {
      source: source('fixture.beta'),
      payload: { status: 'success' },
    }),
    canonicalEvent(runB, 'artifact-created', 'artifact.created', {
      source: source('fixture.beta'),
    }),
  ]);
  await ingestRun(request, anchorRun, [
    canonicalEvent(anchorRun, 'run-started', 'run.started', {
      source: source('fixture.anchor'),
      payload: { title: 'Anchor task' },
    }),
  ]);
  await page.route(
    url => url.pathname === '/api/anthill/runs',
    async route => {
      const listing = await fetchRunListing(request);
      listing.items = listing.items.filter(item => [runA, runB, anchorRun].includes(item.run_id));
      listing.total = listing.items.length;
      await route.fulfill({ json: listing });
    },
  );

  await page.goto('/anthill');
  await page.locator('#run-select').selectOption(anchorRun);
  await expect(page.locator('#run-status')).toHaveText('RUNNING');
  await page.locator('.view-button[data-view="compare"]').click();

  const mainA = page.locator(`#run-select option[value="${runA}"]`);
  const mainB = page.locator(`#run-select option[value="${runB}"]`);
  const compareA = page.locator(`#compare-run-select option[value="${runA}"]`);
  const compareB = page.locator(`#compare-run-select option[value="${runB}"]`);
  const time = String.raw`\d{4}-\d{2}-\d{2} \d{2}:\d{2}Z`;

  await expect(mainA).toHaveText(new RegExp(
    `^Shared task · SRC fixture\\.alpha · RUNNING · INGEST ${time} · ID alpha000…running$`,
  ));
  await expect(mainB).toHaveText(new RegExp(
    `^Shared task · SRC fixture\\.beta · COMPLETED · INGEST ${time} · ID beta0000…done001$`,
  ));
  await expect(compareA).toHaveText(await mainA.textContent());
  await expect(compareB).toHaveText(await mainB.textContent());
  await expect(page.locator('#run-select')).toHaveValue(anchorRun);
  await expect(page.locator('#compare-run-select')).not.toHaveValue(anchorRun);
  await page.unrouteAll({ behavior: 'ignoreErrors' });
});

test('colliding short run IDs expand to their full identity in both selectors', async ({ page, request }) => {
  const suffix = Date.now();
  const runA = `collisio-${suffix}-left-sameend`;
  const runB = `collisio-${suffix}-right-sameend`;
  const anchorRun = `identity-anchor-${suffix}`;
  const runEvents = runId => [
    canonicalEvent(runId, 'run-started', 'run.started', {
      source: { adapter: 'fixture.same', fidelity: 'native' },
      payload: { title: 'Collision task' },
    }),
  ];

  await ingestRun(request, runA, runEvents(runA));
  await ingestRun(request, runB, runEvents(runB));
  await ingestRun(request, anchorRun, [
    canonicalEvent(anchorRun, 'run-started', 'run.started', {
      source: { adapter: 'fixture.anchor', fidelity: 'native' },
      payload: { title: 'Anchor task' },
    }),
  ]);

  await page.goto('/anthill');
  await page.locator('#run-select').selectOption(anchorRun);
  const mainA = page.locator(`#run-select option[value="${runA}"]`);
  const mainB = page.locator(`#run-select option[value="${runB}"]`);
  await expect(mainA).toContainText(`ID ${runA}`);
  await expect(mainB).toContainText(`ID ${runB}`);
  expect(await mainA.textContent()).not.toBe(await mainB.textContent());

  await page.locator('.view-button[data-view="compare"]').click();
  const compareA = page.locator(`#compare-run-select option[value="${runA}"]`);
  const compareB = page.locator(`#compare-run-select option[value="${runB}"]`);
  await expect(compareA).toHaveText(await mainA.textContent());
  await expect(compareB).toHaveText(await mainB.textContent());
});

test('invalid or absent manifest facts remain visibly unknown', async ({ page, request }) => {
  const runId = `unknown00-${Date.now()}-source0`;
  await ingestRun(request, runId, [
    canonicalEvent(runId, 'run-started', 'run.started'),
  ]);
  await page.route(
    url => url.pathname === '/api/anthill/runs',
    async route => {
      const listing = await fetchRunListing(request);
      listing.items = listing.items.filter(item => item.run_id === runId);
      listing.total = listing.items.length;
      const run = listing.items.find(item => item.run_id === runId);
      run.title = runId;
      run.source_adapter = null;
      run.run_status = null;
      run.created_at = '2026-02-31T10:00:00Z';
      await route.fulfill({ json: listing });
    },
  );

  await page.goto('/anthill');

  const option = page.locator(`#run-select option[value="${runId}"]`);
  await expect(option).toHaveText(
    'unknown0…source0 · SRC UNKNOWN · UNKNOWN · INGEST UNKNOWN · ID unknown0…source0',
  );
  await expect(page.locator('#run-select')).toHaveValue(runId);
  await expect(page.locator('#run-status')).toHaveText('RUNNING');
  await page.unrouteAll({ behavior: 'ignoreErrors' });
});

test('live lifecycle refreshes loaded-run identity without rewriting historical cursor truth', async ({ page, request }) => {
  const runId = `live-identity-${Date.now()}`;
  await ingestRun(request, runId, [
    canonicalEvent(runId, 'run-started', 'run.started', {
      payload: { title: 'Live identity task' },
    }),
    canonicalEvent(runId, 'agent-spawned', 'agent.spawned'),
  ]);

  await page.goto('/anthill');
  await page.locator('#run-select').selectOption(runId);
  await expect(page.locator('#connection-label')).toHaveText('LEDGER CONNECTED');
  await expect(page.locator('#run-status')).toHaveText('RUNNING');
  const option = page.locator(`#run-select option[value="${runId}"]`);
  await expect(option).toContainText('RUNNING');

  await page.locator('#jump-start').click();
  await expect(page.locator('#world-mode')).toHaveText('HISTORY · SEQ 0');

  await ingestRun(request, runId, [
    canonicalEvent(runId, 'run-completed', 'run.completed', {
      payload: { status: 'success' },
    }),
  ]);

  await expect(option).toContainText('COMPLETED');
  await expect(page.locator('#run-status')).toHaveText('RUNNING');
  await expect(page.locator('#world-mode')).toHaveText('HISTORY · SEQ 0');
});

test('ingest identity normalizes explicit offsets and rejects unzoned timestamps', async ({ page, request }) => {
  const suffix = Date.now();
  const offsetRun = `offset-time-${suffix}`;
  const unzonedRun = `unzoned-time-${suffix}`;
  const earlyYearRun = `early-year-${suffix}`;
  for (const runId of [offsetRun, unzonedRun, earlyYearRun]) {
    await ingestRun(request, runId, [
      canonicalEvent(runId, 'run-started', 'run.started', {
        payload: { title: `Time ${runId}` },
      }),
    ]);
  }
  await page.route(
    url => url.pathname === '/api/anthill/runs',
    async route => {
      const listing = await fetchRunListing(request);
      listing.items = listing.items.filter(item => [offsetRun, unzonedRun, earlyYearRun].includes(item.run_id));
      listing.total = listing.items.length;
      listing.items.find(item => item.run_id === offsetRun).created_at = '2026-07-17T16:30:00+08:00';
      listing.items.find(item => item.run_id === unzonedRun).created_at = '2026-07-17T16:30:00';
      listing.items.find(item => item.run_id === earlyYearRun).created_at = '0001-01-01T00:00:00Z';
      await route.fulfill({ json: listing });
    },
  );

  await page.goto('/anthill');

  await expect(page.locator(`#run-select option[value="${offsetRun}"]`))
    .toContainText('INGEST 2026-07-17 08:30Z');
  await expect(page.locator(`#run-select option[value="${unzonedRun}"]`))
    .toContainText('INGEST UNKNOWN');
  await expect(page.locator(`#run-select option[value="${earlyYearRun}"]`))
    .toContainText('INGEST 0001-01-01 00:00Z');
  await page.unrouteAll({ behavior: 'ignoreErrors' });
});

test('loaded-run labels neutralize control and bidi spoofing without creating DOM', async ({ page, request }) => {
  const runId = `safe-label-${Date.now()}`;
  const anchorRun = `safe-anchor-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  await ingestRun(request, runId, [
    canonicalEvent(runId, 'run-started', 'run.started'),
  ]);
  await ingestRun(request, anchorRun, [
    canonicalEvent(anchorRun, 'run-started', 'run.started'),
  ]);
  await page.route(
    url => url.pathname === '/api/anthill/runs',
    async route => {
      const listing = await fetchRunListing(request);
      listing.items = listing.items.filter(item => [runId, anchorRun].includes(item.run_id));
      listing.total = listing.items.length;
      const run = listing.items.find(item => item.run_id === runId);
      run.title = 'Trusted\n\u00b7 SRC forged \u00b7 FAILED\u202e<img data-probe="x">';
      run.source_adapter = 'source\n\u202evalue';
      await route.fulfill({ json: listing });
    },
  );

  await page.goto('/anthill');
  await page.locator('#run-select').selectOption(runId);

  const option = page.locator(`#run-select option[value="${runId}"]`);
  const label = await option.textContent();
  expect(label).not.toContain('\n');
  expect(label).not.toContain('\u202e');
  expect(label).not.toContain('\u00b7 SRC forged');
  expect(label).toContain('\u00b7 SRC source value \u00b7 RUNNING \u00b7');
  await expect(page.locator('img[data-probe="x"]')).toHaveCount(0);

  const safeTitle = 'Trusted \u2219 SRC forged \u2219 FAILED <img data-probe="x">';
  await expect(page.locator('#run-title')).toHaveText(safeTitle);
  await page.locator('.view-button[data-view="compare"]').click();
  const compareTitle = page.locator('#compare-left .compare-run-head h2');
  await expect(compareTitle).toHaveText(safeTitle);
  for (const unsafe of ['\n', '\u202e', '\u00b7 SRC forged']) {
    expect(await compareTitle.textContent()).not.toContain(unsafe);
  }
  await expect(page.locator('img[data-probe="x"]')).toHaveCount(0);
  await page.unrouteAll({ behavior: 'ignoreErrors' });
});

test('newest lifecycle manifest response wins when refresh requests resolve out of order', async ({ page, request }) => {
  const runId = `manifest-race-${Date.now()}`;
  await ingestRun(request, runId, [
    canonicalEvent(runId, 'run-started', 'run.started'),
  ]);
  await page.goto('/anthill');
  await page.locator('#run-select').selectOption(runId);
  await expect(page.locator('#connection-label')).toHaveText('LEDGER CONNECTED');

  let requestCount = 0;
  let releaseFirst;
  const firstRelease = new Promise(resolve => { releaseFirst = resolve; });
  await page.route(
    url => url.pathname === '/api/anthill/runs',
    async route => {
      requestCount += 1;
      const listing = await fetchRunListing(request);
      listing.items = listing.items.filter(item => item.run_id === runId);
      listing.total = listing.items.length;
      if (requestCount === 1) {
        listing.items.find(item => item.run_id === runId).run_status = 'paused';
        await firstRelease;
      }
      try {
        await route.fulfill({ json: listing });
      } catch (_) {
        // The winning refresh may abort an older browser request.
      }
    },
  );

  await ingestRun(request, runId, [canonicalEvent(runId, 'run-paused', 'run.paused')]);
  await expect.poll(() => requestCount).toBe(1);
  await ingestRun(request, runId, [canonicalEvent(runId, 'run-resumed', 'run.resumed')]);
  await expect.poll(() => requestCount).toBe(2);

  const option = page.locator(`#run-select option[value="${runId}"]`);
  await expect(option).toContainText('RUNNING');
  releaseFirst();
  await page.waitForTimeout(250);
  await expect(option).toContainText('RUNNING');
  await page.unrouteAll({ behavior: 'ignoreErrors' });
});

test('manifest-only refresh preserves selectors when the current run is absent', async ({ page, request }) => {
  const suffix = Date.now();
  const currentRun = `current-run-${suffix}`;
  const otherRun = `other-run-${suffix}`;
  for (const runId of [currentRun, otherRun]) {
    await ingestRun(request, runId, [
      canonicalEvent(runId, 'run-started', 'run.started'),
    ]);
  }
  await page.goto('/anthill');
  await page.locator('#run-select').selectOption(currentRun);
  await expect(page.locator('#connection-label')).toHaveText('LEDGER CONNECTED');
  let refreshCount = 0;
  await page.route(
    url => url.pathname === '/api/anthill/runs',
    async route => {
      refreshCount += 1;
      const listing = await fetchRunListing(request);
      listing.items = listing.items.filter(
        item => item.run_id === otherRun,
      );
      listing.total = listing.items.length;
      await route.fulfill({ json: listing });
    },
  );

  await ingestRun(request, currentRun, [
    canonicalEvent(currentRun, 'run-paused', 'run.paused'),
  ]);
  await expect.poll(() => refreshCount).toBeGreaterThan(0);
  await page.waitForTimeout(200);

  await expect(page.locator('#run-select')).toHaveValue(currentRun);
  const staleOption = page.locator(`#run-select option[value="${currentRun}"]`);
  await expect(staleOption).toHaveCount(1);
  await expect(staleOption).toContainText('[STALE]');
  await expect(page.locator('#run-status')).toHaveText('PAUSED');
  await page.unrouteAll({ behavior: 'ignoreErrors' });
});

test('a hidden Compare candidate cannot block the active run manifest refresh', async ({ page, request }) => {
  const suffix = Date.now();
  const currentRun = `visible-current-${suffix}`;
  const hiddenCandidate = `hidden-compare-${suffix}`;
  for (const runId of [currentRun, hiddenCandidate]) {
    await ingestRun(request, runId, [
      canonicalEvent(runId, 'run-started', 'run.started'),
    ]);
  }

  let listingCount = 0;
  await page.route(
    url => url.pathname === '/api/anthill/runs',
    async route => {
      listingCount += 1;
      const listing = await fetchRunListing(request);
      const allowed = listingCount === 1
        ? new Set([currentRun, hiddenCandidate])
        : new Set([currentRun]);
      listing.items = listing.items.filter(item => allowed.has(item.run_id));
      listing.total = listing.items.length;
      await route.fulfill({ json: listing });
    },
  );

  await page.goto('/anthill');
  await page.locator('#run-select').selectOption(currentRun);
  await expect(page.locator('#connection-label')).toHaveText('LEDGER CONNECTED');
  await expect(page.locator('#compare-run-select')).toHaveValue(hiddenCandidate);

  await ingestRun(request, currentRun, [
    canonicalEvent(currentRun, 'run-paused', 'run.paused'),
  ]);

  await expect.poll(() => listingCount).toBeGreaterThan(1);
  await expect(page.locator(`#run-select option[value="${currentRun}"]`))
    .toContainText('PAUSED');
  await expect(page.locator('#run-select')).toHaveValue(currentRun);
  await page.unrouteAll({ behavior: 'ignoreErrors' });
});

test('entering Compare refreshes a background run identity snapshot', async ({ page, request }) => {
  const suffix = Date.now();
  const anchorRun = `compare-anchor-${suffix}`;
  const backgroundRun = `compare-background-${suffix}`;
  for (const runId of [anchorRun, backgroundRun]) {
    await ingestRun(request, runId, [
      canonicalEvent(runId, 'run-started', 'run.started'),
    ]);
  }
  await page.goto('/anthill');
  await page.locator('#run-select').selectOption(anchorRun);
  await expect(page.locator('#connection-label')).toHaveText('LEDGER CONNECTED');

  await ingestRun(request, backgroundRun, [
    canonicalEvent(backgroundRun, 'run-completed', 'run.completed', {
      payload: { status: 'success' },
    }),
  ]);
  await page.locator('.view-button[data-view="compare"]').click();

  await expect(page.locator(`#compare-run-select option[value="${backgroundRun}"]`))
    .toContainText('COMPLETED');
  await expect(page.locator('#run-select')).toHaveValue(anchorRun);
});

test('active Compare cards recompute at the current progress after events on both sides', async ({ page, request }) => {
  const suffix = Date.now();
  const leftRun = `compare-live-left-${suffix}`;
  const rightRun = `compare-live-right-${suffix}`;
  for (const runId of [leftRun, rightRun]) {
    await ingestRun(request, runId, [
      canonicalEvent(runId, 'run-started', 'run.started'),
    ]);
  }

  await page.goto('/anthill');
  await page.locator('#run-select').selectOption(leftRun);
  await expect(page.locator('#connection-label')).toHaveText('LEDGER CONNECTED');
  await page.locator('.view-button[data-view="compare"]').click();
  await page.locator('#compare-run-select').selectOption(rightRun);

  const leftStatus = page.locator('#compare-left .compare-run-head span');
  const rightStatus = page.locator('#compare-right .compare-run-head span');
  await expect(leftStatus).toContainText('LEFT · RUNNING');
  await expect(rightStatus).toContainText('RIGHT · RUNNING');

  await ingestRun(request, leftRun, [
    canonicalEvent(leftRun, 'run-completed', 'run.completed', {
      payload: { status: 'success' },
    }),
  ]);

  await expect(page.locator(`#run-select option[value="${leftRun}"]`))
    .toContainText('COMPLETED');
  await expect(leftStatus).toContainText('LEFT · COMPLETED');
  await expect(rightStatus).toContainText('RIGHT · RUNNING');

  await ingestRun(request, rightRun, [
    canonicalEvent(rightRun, 'run-completed', 'run.completed', {
      payload: { status: 'success' },
    }),
  ]);

  await expect(page.locator(`#compare-run-select option[value="${rightRun}"]`))
    .toContainText('COMPLETED');
  await expect(leftStatus).toContainText('LEFT · COMPLETED');
  await expect(rightStatus).toContainText('RIGHT · COMPLETED');

  const leftEvents = page.locator('#compare-left .compare-metrics dd').first();
  const rightEvents = page.locator('#compare-right .compare-metrics dd').first();
  await expect(leftEvents).toHaveText('2');
  await expect(rightEvents).toHaveText('2');

  await ingestRun(request, leftRun, [
    canonicalEvent(leftRun, 'left-artifact', 'artifact.created'),
  ]);
  await expect(leftEvents).toHaveText('3');
  await expect(rightEvents).toHaveText('2');

  await ingestRun(request, rightRun, [
    canonicalEvent(rightRun, 'right-artifact', 'artifact.created'),
  ]);
  await expect(leftEvents).toHaveText('3');
  await expect(rightEvents).toHaveText('3');
});

test('switching the primary run invalidates an older Compare response', async ({ page, request }) => {
  const suffix = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const [runA, runB, runC] = ['a', 'b', 'c'].map(side => `compare-switch-${side}-${suffix}`);
  for (const runId of [runA, runB, runC]) {
    await ingestRun(request, runId, [canonicalEvent(runId, 'started', 'run.started')]);
  }
  await page.goto('/anthill');
  await page.locator('#run-select').selectOption(runA);
  await page.locator('.view-button[data-view="compare"]').click();
  await page.locator('#compare-run-select').selectOption(runB);
  await expect(page.locator('#compare-left .compare-run-head span')).toContainText('RUNNING');

  let holdOld;
  let releaseOld;
  let markOldDone;
  const oldHeld = new Promise(resolve => { holdOld = resolve; });
  const oldReleased = new Promise(resolve => { releaseOld = resolve; });
  const oldDone = new Promise(resolve => { markOldDone = resolve; });
  await page.route(
    url => url.pathname === '/api/anthill/compare'
      && url.searchParams.get('left_run_id') === runA
      && url.searchParams.get('right_run_id') === runB,
    async route => {
      const response = await route.fetch();
      const result = await response.json();
      result.left.summary.run_status = 'failed';
      holdOld();
      await oldReleased;
      try {
        await route.fulfill({ response, json: result });
      } catch {
        // Correct cancellation can abort the held browser request.
      }
      markOldDone();
    },
  );

  let holdNewWorld;
  let releaseNewWorld;
  const newWorldHeld = new Promise(resolve => { holdNewWorld = resolve; });
  const newWorldReleased = new Promise(resolve => { releaseNewWorld = resolve; });
  await page.route(
    url => url.pathname === `/api/anthill/runs/${runC}/world`,
    async route => {
      const response = await route.fetch();
      holdNewWorld();
      await newWorldReleased;
      try {
        await route.fulfill({ response });
      } catch {
        // Test cleanup may cancel the request after the assertion.
      }
    },
  );

  await page.locator('#step-back').click();
  await oldHeld;
  await page.locator('#run-select').selectOption(runC);
  await newWorldHeld;
  await expect(page.locator('#comparability-banner')).toHaveText('LOADING SELECTED RUN…');
  await expect(page.locator('#compare-left')).toBeEmpty();
  releaseOld();
  await oldDone;

  await expect(page.locator('#run-select')).toHaveValue(runC);
  await expect(page.locator('#compare-left')).toBeEmpty();

  releaseNewWorld();
  await expect(page.locator('#connection-state')).toHaveAttribute('data-state', 'connected');
  await expect(page.locator('#compare-left .compare-run-head span')).toContainText('RUNNING');
  await page.unrouteAll({ behavior: 'wait' });
});

test('a superseded Compare request cannot surface a stale error', async ({ page, request }) => {
  const suffix = Date.now();
  const leftRun = `compare-error-left-${suffix}`;
  const rightRun = `compare-error-right-${suffix}`;
  for (const runId of [leftRun, rightRun]) {
    await ingestRun(request, runId, [
      canonicalEvent(runId, 'run-started', 'run.started'),
    ]);
  }

  await page.route(
    url => url.pathname === '/api/anthill/runs',
    async route => {
      const listing = await fetchRunListing(request);
      listing.items = listing.items.filter(item => [leftRun, rightRun].includes(item.run_id));
      listing.total = listing.items.length;
      await route.fulfill({ json: listing });
    },
  );

  let requestCount = 0;
  let releaseFirst;
  let markFirstHeld;
  let markFirstResponded;
  const firstReleased = new Promise(resolve => { releaseFirst = resolve; });
  const firstHeld = new Promise(resolve => { markFirstHeld = resolve; });
  const firstResponded = new Promise(resolve => { markFirstResponded = resolve; });
  const cancelledCompareRequests = [];
  page.on('requestfailed', failedRequest => {
    if (new URL(failedRequest.url()).pathname === '/api/anthill/compare') {
      cancelledCompareRequests.push(failedRequest.failure()?.errorText || 'cancelled');
    }
  });
  await page.route(
    url => url.pathname === '/api/anthill/compare',
    async route => {
      requestCount += 1;
      if (requestCount === 1) {
        markFirstHeld();
        await firstReleased;
        try {
          await route.fulfill({
            status: 500,
            contentType: 'application/json',
            body: JSON.stringify({ detail: 'stale compare failure' }),
          });
        } catch {
          // A correct single-flight implementation cancels this route.
        }
        markFirstResponded();
        return;
      }
      await route.continue();
    },
  );

  await page.goto('/anthill');
  await page.locator('#run-select').selectOption(leftRun);
  await expect(page.locator('#connection-label')).toHaveText('LEDGER CONNECTED');
  await page.locator('.view-button[data-view="compare"]').click();
  await firstHeld;
  await expect.poll(() => requestCount).toBeGreaterThan(1);
  await expect.poll(() => cancelledCompareRequests.length).toBeGreaterThan(0);
  await expect(page.locator('#compare-right .compare-run-head span'))
    .toContainText('RIGHT · RUNNING');

  releaseFirst();
  await firstResponded;
  await page.waitForTimeout(100);
  await expect(page.locator('#canvas-tooltip')).not.toContainText('stale compare failure');
  await page.unrouteAll({ behavior: 'ignoreErrors' });
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

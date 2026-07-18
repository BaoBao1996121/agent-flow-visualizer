import { expect, test } from '@playwright/test';
import { randomUUID } from 'node:crypto';


async function openLab(page, request, cursor = 43, staticCapture = true) {
  const created = await request.post('/api/anthill/demo');
  expect(created.status(), await created.text()).toBe(201);
  const { run_id: runId } = await created.json();
  const staticQuery = staticCapture ? '&static=1' : '';
  await page.goto(`/labs/phase0-cutaway?run_id=${encodeURIComponent(runId)}&cursor_seq=${cursor}${staticQuery}`);
  return runId;
}


function contractEvent(runId, eventId, eventType, subject, level = 'observed') {
  return {
    event_id: eventId,
    event_type: eventType,
    run_id: runId,
    source: { adapter: 'visual-lab-contract', fidelity: 'native' },
    subject,
    evidence: { level, confidence: level === 'inferred' ? 0.75 : 1 },
    payload: {},
  };
}


async function createContractRun(request, events) {
  const runId = `visual-lab-${randomUUID()}`;
  const response = await request.post(`/api/anthill/runs/${runId}/events`, {
    data: { events: events(runId) },
  });
  expect(response.status(), await response.text()).toBe(201);
  return runId;
}


test('@visual-lab-s0 orthographic lab renders a truthful final-state slice', async ({ page, request }, testInfo) => {
  await openLab(page, request);

  await expect(page.getByTestId('lab-status')).toHaveText('READY');
  await expect(page.getByTestId('integrity-status')).toHaveText('VERIFIED');
  await expect(page.getByTestId('fixture-badge')).toHaveText('SYNTHETIC RUN');
  await expect(page.getByTestId('study-disclaimer')).toContainText('EXPLORATION');
  await expect(page.getByTestId('event-count')).toHaveText('44');
  await expect(page.getByTestId('cursor-seq')).toHaveText('43 / 43');
  await expect(page.getByTestId('current-event-type')).toHaveText('run.completed');
  await expect(page.locator('[data-zone-id]')).toHaveCount(12);
  await expect(page.locator('.lab-entity')).toHaveCount(12);
  await expect(page.getByRole('button', { name: /Coordinator.*agent.*completed.*declared/i }))
    .toBeVisible();

  await testInfo.attach('visual-lab-overview', {
    body: await page.screenshot({ animations: 'disabled', fullPage: true }),
    contentType: 'image/png',
  });
});

test('named cursors and keyboard evidence stay tied to ledger facts', async ({ page, request }) => {
  const runId = await openLab(page, request);
  await expect(page.getByTestId('lab-status')).toHaveText('READY');

  await page.getByRole('button', { name: 'INCIDENT', exact: true }).click();
  await expect(page.getByTestId('cursor-seq')).toHaveText('24 / 43');
  await expect(page.getByTestId('current-event-type')).toHaveText('error.raised');

  const tool = page.locator('[data-entity-id="tool.logs-1"]');
  await tool.focus();
  await tool.press('Enter');
  await expect(page.getByTestId('evidence-title')).toHaveText('Query logs');
  await expect(page.getByTestId('evidence-event-type')).toHaveText('error.raised');
  await expect(page.getByTestId('evidence-truth')).toHaveText('DECLARED');
  await expect(page.getByTestId('evidence-route')).toHaveAttribute(
    'href',
    new RegExp(`/api/anthill/runs/${runId}/event\\?event_id=`),
  );

  await page.getByRole('button', { name: 'COMPACTION', exact: true }).click();
  await expect(page.getByTestId('cursor-seq')).toHaveText('37 / 43');
  await expect(page.getByTestId('current-event-type')).toHaveText('compaction.completed');
  await expect(page.locator('[data-entity-id="compact.ctx-1"]')).toBeVisible();
});

test('reduced motion stops ambient visual-lab animation', async ({ page, request }) => {
  await page.emulateMedia({ reducedMotion: 'no-preference' });
  await openLab(page, request, 43, false);
  await expect(page.getByTestId('lab-status')).toHaveText('READY');
  await expect(page.locator('body')).toHaveAttribute('data-static', 'false');
  const fullMotionCount = await page.evaluate(() => document.getAnimations({ subtree: true })
    .filter(animation => animation.playState === 'running').length);
  expect(fullMotionCount).toBeGreaterThan(0);

  await page.emulateMedia({ reducedMotion: 'reduce' });
  await expect(page.locator('body')).toHaveAttribute('data-motion', 'reduce');
  expect(await page.evaluate(() => document.getAnimations({ subtree: true })
    .filter(animation => animation.playState === 'running').length)).toBe(0);
});


test('opaque entity and event identities retain their exact canonical value', async ({ page, request }) => {
  const eventId = ' event  id ';
  const entityId = ' agent  id ';
  const runId = await createContractRun(request, id => [
    contractEvent(id, eventId, 'agent.spawned', {
      kind: 'agent', id: entityId, name: 'Opaque Agent',
    }),
  ]);

  await page.goto(`/labs/phase0-cutaway?run_id=${runId}&cursor_seq=0&static=1`);
  await expect(page.getByTestId('lab-status')).toHaveText('READY');
  await expect(page.getByTestId('fixture-badge')).toHaveText('RECORDED RUN');
  const entity = page.getByRole('button', { name: /Opaque Agent/ });
  await expect(entity).toHaveAttribute('data-entity-id', entityId);
  await entity.click();
  const expectedRoute = `/api/anthill/runs/${runId}/event?event_id=${encodeURIComponent(eventId)}`;
  await expect(page.getByTestId('evidence-route')).toHaveAttribute('href', expectedRoute);
  const evidence = await request.get(expectedRoute);
  expect(evidence.status(), await evidence.text()).toBe(200);
  expect((await evidence.json()).event_id).toBe(eventId);
});


test('named presets resolve exact ledger event types instead of fixed sequences', async ({ page, request }) => {
  const runId = await createContractRun(request, id => [
    'run.started',
    'agent.step.started',
    'tool.call.requested',
    'error.raised',
    'tool.retry.scheduled',
    'tool.execution.started',
    'context.budget.updated',
    'compaction.completed',
    'run.completed',
  ].map((eventType, index) => contractEvent(
    id,
    `event-${index}`,
    eventType,
    { kind: 'agent', id: 'agent.dynamic', name: 'Dynamic Agent' },
  )));

  await page.goto(`/labs/phase0-cutaway?run_id=${runId}&static=1`);
  await expect(page.getByTestId('lab-status')).toHaveText('READY');
  const incident = page.getByRole('button', { name: 'INCIDENT', exact: true });
  const compaction = page.getByRole('button', { name: 'COMPACTION', exact: true });
  await expect(incident).toHaveAttribute('data-cursor', '3');
  await expect(compaction).toHaveAttribute('data-cursor', '7');
  await incident.click();
  await expect(page.getByTestId('current-event-type')).toHaveText('error.raised');
  await compaction.click();
  await expect(page.getByTestId('current-event-type')).toHaveText('compaction.completed');
});


test('HEAD refreshes the addressed ledger instead of reusing a stale load snapshot', async ({ page, request }) => {
  const subject = { kind: 'agent', id: 'agent.live', name: 'Live Agent' };
  const runId = await createContractRun(request, id => [
    contractEvent(id, 'live-start', 'run.started', subject),
  ]);
  await page.goto(`/labs/phase0-cutaway?run_id=${runId}&static=1`);
  await expect(page.getByTestId('cursor-seq')).toHaveText('0 / 0');

  const appended = await request.post(`/api/anthill/runs/${runId}/events`, {
    data: { events: [contractEvent(runId, 'live-complete', 'run.completed', subject)] },
  });
  expect(appended.status(), await appended.text()).toBe(201);
  await page.getByRole('button', { name: 'HEAD', exact: true }).click();
  await expect(page.getByTestId('cursor-seq')).toHaveText('1 / 1');
  await expect(page.getByTestId('current-event-type')).toHaveText('run.completed');
});


test('invalid ledger integrity fails closed before semantic entities render', async ({ page, request }) => {
  const runId = await createContractRun(request, id => [
    contractEvent(id, 'untrusted-event', 'agent.spawned', {
      kind: 'agent', id: 'agent.untrusted', name: 'Untrusted Agent',
    }),
  ]);
  await page.route(`**/api/anthill/runs/${runId}/integrity`, route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ run_id: runId, valid: false, event_count: 1, errors: ['hash mismatch'] }),
  }));

  await page.goto(`/labs/phase0-cutaway?run_id=${runId}&static=1`);
  await expect(page.getByTestId('lab-status')).toHaveText('ERROR');
  await expect(page.locator('#run-status')).toHaveText('UNAVAILABLE');
  await expect(page.getByTestId('integrity-status')).toHaveText('FAILED');
  await expect(page.getByTestId('current-event-type')).toHaveText('SCENE INVALIDATED');
  await expect(page.getByRole('alert')).toContainText('integrity verification failed');
  await expect(page.locator('.lab-entity')).toHaveCount(0);
});


test('a duplicate ingest sequence in the event envelope fails closed', async ({ page, request }) => {
  const created = await request.post('/api/anthill/demo');
  const { run_id: runId } = await created.json();
  await page.route(`**/api/anthill/runs/${runId}/events?*`, async route => {
    const response = await route.fetch();
    const envelope = await response.json();
    envelope.items[1].clock.ingest_seq = envelope.items[0].clock.ingest_seq;
    await route.fulfill({ response, json: envelope });
  });

  await page.goto(`/labs/phase0-cutaway?run_id=${runId}&static=1`);
  await expect(page.getByTestId('lab-status')).toHaveText('ERROR');
  await expect(page.getByRole('alert')).toContainText('sequence');
  await expect(page.locator('.lab-entity')).toHaveCount(0);
});


test('world, ledger and integrity event counts must reconcile before rendering', async ({ page, request }) => {
  const created = await request.post('/api/anthill/demo');
  const { run_id: runId } = await created.json();
  await page.route(`**/api/anthill/runs/${runId}/world`, async route => {
    const response = await route.fetch();
    const envelope = await response.json();
    envelope.state.event_count += 1;
    await route.fulfill({ response, json: envelope });
  });

  await page.goto(`/labs/phase0-cutaway?run_id=${runId}&static=1`);
  await expect(page.getByTestId('lab-status')).toHaveText('ERROR');
  await expect(page.getByRole('alert')).toContainText('event count');
  await expect(page.locator('.lab-entity')).toHaveCount(0);
});


test('entity last evidence must reconcile with the cursor ledger', async ({ page, request }) => {
  const created = await request.post('/api/anthill/demo');
  const { run_id: runId } = await created.json();
  await page.route(`**/api/anthill/runs/${runId}/world`, async route => {
    const response = await route.fetch();
    const envelope = await response.json();
    envelope.state.entities['agent.coordinator'].last_seq = 0;
    await route.fulfill({ response, json: envelope });
  });

  await page.goto(`/labs/phase0-cutaway?run_id=${runId}&static=1`);
  await expect(page.getByTestId('lab-status')).toHaveText('ERROR');
  await expect(page.getByRole('alert')).toContainText(/entity evidence/i);
  await expect(page.locator('.lab-entity')).toHaveCount(0);
});


test('repeated lab query keys fail closed before any run is addressed', async ({ page }) => {
  for (const query of [
    'run_id=first&run_id=second',
    'run_id=missing&cursor_seq=0&cursor_seq=1',
    'run_id=missing&static=0&static=1',
    'run_id=missing&timeout_ms=100&timeout_ms=200',
  ]) {
    await page.goto(`/labs/phase0-cutaway?${query}`);
    await expect(page.getByTestId('lab-status')).toHaveText('ERROR');
    await expect(page.getByRole('alert')).toContainText('exactly once');
    await expect(page.getByRole('button', { name: 'HEAD', exact: true })).toBeDisabled();
    await expect(page.getByTestId('evidence-route')).not.toHaveAttribute('href');
    await expect(page.getByTestId('evidence-route')).toHaveAttribute('tabindex', '-1');
  }
});


test('request timeout configuration stays inside the bounded study range', async ({ page }) => {
  for (const timeout of ['99', '30001', 'not-a-number']) {
    await page.goto(`/labs/phase0-cutaway?run_id=missing&timeout_ms=${timeout}`);
    await expect(page.getByTestId('lab-status')).toHaveText('ERROR');
    await expect(page.getByRole('alert')).toContainText('between 100 and 30000');
    await expect(page.locator('.lab-entity')).toHaveCount(0);
  }
});


test('a failed load cancels its sibling request and bypasses browser caches', async ({ page }) => {
  await page.addInitScript(() => {
    const nativeFetch = window.fetch.bind(window);
    window.__labFetchCaches = [];
    window.__labSiblingAborted = false;
    window.fetch = (input, init = {}) => {
      const url = String(input);
      if (!url.includes('/api/anthill/')) return nativeFetch(input, init);
      window.__labFetchCaches.push(init.cache ?? 'default');
      if (url.endsWith('/world')) {
        return Promise.resolve(new Response(JSON.stringify({ invalid: true }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }));
      }
      if (url.endsWith('/integrity')) {
        return new Promise((resolve, reject) => {
          const failAsAborted = () => {
            window.__labSiblingAborted = true;
            reject(new DOMException('Cancelled sibling request.', 'AbortError'));
          };
          if (init.signal?.aborted) failAsAborted();
          else init.signal?.addEventListener('abort', failAsAborted, { once: true });
        });
      }
      return nativeFetch(input, init);
    };
  });

  await page.goto('/labs/phase0-cutaway?run_id=sibling-contract&static=1');
  await expect(page.getByTestId('lab-status')).toHaveText('ERROR');
  await expect.poll(() => page.evaluate(() => window.__labSiblingAborted)).toBe(true);
  const cacheModes = await page.evaluate(() => window.__labFetchCaches);
  expect(cacheModes.length).toBeGreaterThanOrEqual(2);
  expect(cacheModes.every(mode => mode === 'no-store')).toBe(true);
});


test('a mixed ledger is labelled as containing synthetic events', async ({ page, request }) => {
  const runId = await createContractRun(request, id => {
    const synthetic = contractEvent(
      id,
      'mixed-synthetic',
      'agent.spawned',
      { kind: 'agent', id: 'agent.mixed', name: 'Mixed Agent' },
    );
    synthetic.payload.synthetic = true;
    return [
      synthetic,
      contractEvent(
        id,
        'mixed-recorded',
        'agent.completed',
        { kind: 'agent', id: 'agent.mixed', name: 'Mixed Agent' },
      ),
    ];
  });

  await page.goto(`/labs/phase0-cutaway?run_id=${runId}&static=1`);
  await expect(page.getByTestId('lab-status')).toHaveText('READY');
  await expect(page.getByTestId('fixture-badge')).toHaveText('CONTAINS SYNTHETIC EVENTS');
});


test('run provenance stays pending until the addressed ledger is classified', async ({ page, request }) => {
  const created = await request.post('/api/anthill/demo');
  const { run_id: runId } = await created.json();
  let releaseWorld;
  const worldGate = new Promise(resolve => { releaseWorld = resolve; });
  await page.route(`**/api/anthill/runs/${runId}/world`, async route => {
    await worldGate;
    await route.continue();
  });

  await page.goto(`/labs/phase0-cutaway?run_id=${runId}&static=1`);
  await expect(page.getByTestId('lab-status')).toHaveText('LOADING');
  await expect(page.getByTestId('fixture-badge')).toHaveText('PENDING');
  releaseWorld();
  await expect(page.getByTestId('lab-status')).toHaveText('READY');
  await expect(page.getByTestId('fixture-badge')).toHaveText('SYNTHETIC RUN');
});


test('an explicit cursor beyond HEAD fails closed instead of seeking HEAD', async ({ page, request }) => {
  const runId = await createContractRun(request, id => [
    contractEvent(
      id,
      'bounded-head',
      'run.started',
      { kind: 'agent', id: 'agent.bound', name: 'Bound Agent' },
    ),
  ]);

  await page.goto(`/labs/phase0-cutaway?run_id=${runId}&cursor_seq=99&static=1`);
  await expect(page.getByTestId('lab-status')).toHaveText('ERROR');
  await expect(page.getByRole('alert')).toContainText(/cursor.*HEAD/i);
  await expect(page.locator('.lab-entity')).toHaveCount(0);
});


test('a failed HEAD revalidation invalidates the previously rendered scene', async ({ page, request }, testInfo) => {
  const runId = await createContractRun(request, id => [
    contractEvent(
      id,
      'stale-start',
      'run.started',
      { kind: 'agent', id: 'agent.stale', name: 'Stale Agent' },
    ),
  ]);
  let failIntegrity = false;
  await page.route(`**/api/anthill/runs/${runId}/integrity`, async route => {
    if (!failIntegrity) return route.continue();
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ run_id: runId, valid: false, event_count: 1, errors: ['hash mismatch'] }),
    });
  });

  await page.goto(`/labs/phase0-cutaway?run_id=${runId}&static=1`);
  await expect(page.getByTestId('lab-status')).toHaveText('READY');
  await expect(page.locator('.lab-entity')).toHaveCount(1);
  failIntegrity = true;
  await page.getByRole('button', { name: 'HEAD', exact: true }).click();
  await expect(page.getByTestId('lab-status')).toHaveText('ERROR');
  await expect(page.getByTestId('integrity-status')).toHaveText('FAILED');
  await expect(page.locator('.lab-entity')).toHaveCount(0);
  await expect(page.getByTestId('evidence-route')).not.toHaveAttribute('href');
  await testInfo.attach('visual-lab-invalidated', {
    body: await page.screenshot({ animations: 'disabled', fullPage: true }),
    contentType: 'image/png',
  });
});


test('a superseded seek failure cannot erase a newer verified HEAD', async ({ page, request }, testInfo) => {
  await openLab(page, request);
  await expect(page.getByTestId('lab-status')).toHaveText('READY');
  await page.evaluate(() => {
    const nativeFetch = window.fetch.bind(window);
    window.__staleSeekReturned = false;
    window.fetch = async (input, init) => {
      const url = String(input);
      if (url.includes('/world?at_seq=24')) {
        await new Promise(resolve => setTimeout(resolve, 250));
        window.__staleSeekReturned = true;
        return new Response(JSON.stringify({ invalid: true }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      return nativeFetch(input, init);
    };
  });

  await page.getByRole('button', { name: 'INCIDENT', exact: true }).click();
  await expect(page.getByTestId('lab-status')).toHaveText('SEEKING');
  await page.getByRole('button', { name: 'HEAD', exact: true }).click();
  await expect(page.getByTestId('lab-status')).toHaveText('READY');
  await page.waitForFunction(() => window.__staleSeekReturned === true);
  await expect(page.getByTestId('lab-status')).toHaveText('READY');
  await expect(page.getByTestId('integrity-status')).toHaveText('VERIFIED');
  await expect(page.getByTestId('current-event-type')).toHaveText('run.completed');
  await expect(page.locator('.lab-entity')).toHaveCount(12);
  await testInfo.attach('visual-lab-superseded-request', {
    body: await page.screenshot({ animations: 'disabled', fullPage: true }),
    contentType: 'image/png',
  });
});


test('a superseded HEAD cannot poison the cache used by a later seek', async ({ page, request }, testInfo) => {
  const subject = { kind: 'agent', id: 'agent.cache', name: 'Cache Agent' };
  const runId = await createContractRun(request, id => [
    contractEvent(id, 'cache-start', 'run.started', subject),
    contractEvent(id, 'cache-incident', 'error.raised', subject),
  ]);
  await page.goto(`/labs/phase0-cutaway?run_id=${runId}&static=1`);
  await expect(page.getByTestId('cursor-seq')).toHaveText('1 / 1');

  const [worldResponse, integrityResponse, eventsResponse] = await Promise.all([
    request.get(`/api/anthill/runs/${runId}/world`),
    request.get(`/api/anthill/runs/${runId}/integrity`),
    request.get(`/api/anthill/runs/${runId}/events?from_seq=0&to_seq=1&limit=5000`),
  ]);
  expect(worldResponse.status()).toBe(200);
  expect(integrityResponse.status()).toBe(200);
  expect(eventsResponse.status()).toBe(200);
  const stale = {
    world: await worldResponse.json(),
    integrity: await integrityResponse.json(),
    events: await eventsResponse.json(),
  };
  const appended = await request.post(`/api/anthill/runs/${runId}/events`, {
    data: { events: [contractEvent(runId, 'cache-complete', 'run.completed', subject)] },
  });
  expect(appended.status(), await appended.text()).toBe(201);

  await page.evaluate(staleEnvelopes => {
    const nativeFetch = window.fetch.bind(window);
    let staleWorldClaimed = false;
    let staleIntegrityClaimed = false;
    let staleFirstStageReturned = 0;
    let staleEventsClaimed = false;
    window.__staleHeadReturned = false;
    const delayedEnvelope = async body => {
      await new Promise(resolve => setTimeout(resolve, 700));
      staleFirstStageReturned += 1;
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    };
    window.fetch = async (input, init) => {
      const url = new URL(String(input), window.location.origin);
      if (url.pathname.endsWith('/world') && url.search === '' && !staleWorldClaimed) {
        staleWorldClaimed = true;
        return delayedEnvelope(staleEnvelopes.world);
      }
      if (url.pathname.endsWith('/integrity') && !staleIntegrityClaimed) {
        staleIntegrityClaimed = true;
        return delayedEnvelope(staleEnvelopes.integrity);
      }
      if (
        url.pathname.endsWith('/events')
        && staleFirstStageReturned === 2
        && !staleEventsClaimed
      ) {
        staleEventsClaimed = true;
        await new Promise(resolve => setTimeout(resolve, 100));
        window.__staleHeadReturned = true;
        return new Response(JSON.stringify(staleEnvelopes.events), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      return nativeFetch(input, init);
    };
  }, stale);

  const head = page.getByRole('button', { name: 'HEAD', exact: true });
  await head.click();
  await expect(page.getByTestId('lab-status')).toHaveText('SEEKING');
  await head.click();
  await expect(page.getByTestId('lab-status')).toHaveText('READY');
  await expect(page.getByTestId('cursor-seq')).toHaveText('2 / 2');
  await page.waitForFunction(() => window.__staleHeadReturned === true);
  await page.evaluate(() => new Promise(resolve => queueMicrotask(resolve)));

  await page.getByRole('button', { name: 'INCIDENT', exact: true }).click();
  await expect(page.getByTestId('lab-status')).toHaveText('READY');
  await expect(page.getByTestId('cursor-seq')).toHaveText('1 / 2');
  await expect(page.getByTestId('current-event-type')).toHaveText('error.raised');
  await testInfo.attach('visual-lab-superseded-head-cache', {
    body: await page.screenshot({ animations: 'disabled', fullPage: true }),
    contentType: 'image/png',
  });
});


test('the complete truth vocabulary has non-color legend and entity styles', async ({ page, request }) => {
  const levels = [
    ['observed', 'agent.spawned'],
    ['declared', 'agent.spawned'],
    ['inferred', 'agent.spawned'],
    ['counterfactual_verified', 'agent.spawned'],
  ];
  const runId = await createContractRun(request, id => levels.map(([level, eventType], index) => (
    contractEvent(
      id,
      `truth-${index}`,
      eventType,
      { kind: 'agent', id: `agent.truth-${index}`, name: `Truth ${level}` },
      level,
    )
  )));

  await page.goto(`/labs/phase0-cutaway?run_id=${runId}&static=1`);
  await expect(page.getByTestId('lab-status')).toHaveText('READY');
  const legend = page.locator('.truth-key [data-truth]');
  await expect(legend).toHaveCount(5);
  for (const [level] of levels) {
    await expect(page.locator(`.lab-entity[data-truth="${level}"]`)).toHaveCount(1);
    await expect(legend.filter({ hasText: level.toUpperCase() })).toHaveCount(1);
  }
  await expect(legend.filter({ hasText: 'UNKNOWN' })).toHaveCount(1);
  const signatures = await legend.evaluateAll(items => items.map(item => {
    const style = getComputedStyle(item);
    return [style.borderStyle, style.borderWidth, style.backgroundImage, style.boxShadow].join('|');
  }));
  expect(new Set(signatures).size).toBe(5);
});


test('entity names and truth metadata fit at the 1600 by 1000 review viewport', async ({ page, request }) => {
  const runId = await openLab(page, request);
  await expect(page.getByTestId('lab-status')).toHaveText('READY');
  await expect(page.locator('#run-id')).toHaveText(runId);
  const runIdIsClipped = await page.locator('#run-id').evaluate(label => (
    label.scrollWidth > label.clientWidth || label.scrollHeight > label.clientHeight
  ));
  expect(runIdIsClipped).toBe(false);
  const clipped = await page.locator('.lab-entity').evaluateAll(items => items.flatMap(item => (
    Array.from(item.querySelectorAll('.entity-name, .entity-meta'))
      .filter(label => label.scrollWidth > label.clientWidth || label.scrollHeight > label.clientHeight)
      .map(label => `${item.dataset.entityId}:${label.className}`)
  )));
  expect(clipped).toEqual([]);
});


test('the evidence drawer defaults to the cursor event and announces entity overrides', async ({ page, request }) => {
  const runId = await openLab(page, request);
  await expect(page.getByTestId('lab-status')).toHaveText('READY');
  await expect(page.getByTestId('evidence-title')).toHaveText('Cursor event');
  await expect(page.getByTestId('evidence-event-type')).toHaveText('run.completed');
  await expect(page.getByTestId('evidence-route')).toHaveAttribute(
    'href',
    new RegExp(`/api/anthill/runs/${runId}/event\\?event_id=`),
  );
  await expect(page.getByTestId('evidence-live')).toContainText('Cursor event');

  await page.locator('[data-entity-id="tool.logs-1"]').click();
  await expect(page.getByTestId('evidence-title')).toHaveText('Query logs');
  await expect(page.getByTestId('evidence-live')).toContainText('Query logs');
  await expect(page.getByTestId('evidence-route')).not.toHaveAttribute('tabindex');
});


test('more than four visible entities in one chamber fails closed', async ({ page, request }) => {
  const created = await request.post('/api/anthill/demo');
  const { run_id: runId } = await created.json();
  await page.route(`**/api/anthill/runs/${runId}/world`, async route => {
    const response = await route.fetch();
    const envelope = await response.json();
    Object.values(envelope.state.entities).slice(0, 5).forEach(entity => {
      entity.zone = 'control';
    });
    await route.fulfill({ response, json: envelope });
  });

  await page.goto(`/labs/phase0-cutaway?run_id=${runId}&static=1`);
  await expect(page.getByTestId('lab-status')).toHaveText('ERROR');
  await expect(page.getByRole('alert')).toContainText(/four.*chamber/i);
  await expect(page.locator('.lab-entity')).toHaveCount(0);
});


test('small operational labels meet normal-text contrast at the review viewport', async ({ page, request }) => {
  await openLab(page, request);
  await expect(page.getByTestId('lab-status')).toHaveText('READY');
  const ratios = await page.evaluate(() => {
    const luminance = value => {
      const channels = value.match(/[\d.]+/g).slice(0, 3).map(Number).map(channel => {
        const normalized = channel / 255;
        return normalized <= 0.04045
          ? normalized / 12.92
          : ((normalized + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
    };
    const contrast = (foreground, background) => {
      const values = [luminance(foreground), luminance(background)].sort((a, b) => b - a);
      return (values[0] + 0.05) / (values[1] + 0.05);
    };
    const pairs = [
      ['.readout-label', '.instrument-strip', 'color', 'backgroundColor'],
      ['.evidence-grid dt', '.evidence-drawer', 'color', 'backgroundColor'],
      ['.chamber-id', '.chamber-face', 'fill', 'fill'],
    ];
    return pairs.map(([foreground, background, foregroundProperty, backgroundProperty]) => contrast(
      getComputedStyle(document.querySelector(foreground))[foregroundProperty],
      getComputedStyle(document.querySelector(background))[backgroundProperty],
    ));
  });
  expect(ratios.every(ratio => ratio >= 4.5)).toBe(true);
});


test('a hung projection request times out into an explicit retry path', async ({ page, request }, testInfo) => {
  const runId = await createContractRun(request, id => [
    contractEvent(
      id,
      'timeout-start',
      'run.started',
      { kind: 'agent', id: 'agent.timeout', name: 'Timeout Agent' },
    ),
  ]);
  let delayWorld = true;
  await page.route(`**/api/anthill/runs/${runId}/world`, async route => {
    if (!delayWorld) return route.continue();
    await new Promise(resolve => setTimeout(resolve, 300));
    return route.continue().catch(() => undefined);
  });

  await page.goto(`/labs/phase0-cutaway?run_id=${runId}&timeout_ms=100&static=1`);
  await expect(page.getByTestId('lab-status')).toHaveText('ERROR');
  await expect(page.locator('#run-status')).toHaveText('UNAVAILABLE');
  await expect(page.getByTestId('integrity-status')).toHaveText('UNVERIFIED');
  await expect(page.getByTestId('current-event-type')).toHaveText('SCENE INVALIDATED');
  await expect(page.getByRole('alert')).toContainText('timed out after 100 ms');
  await expect(page.getByRole('button', { name: 'RETRY LOAD', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'HEAD', exact: true })).toBeDisabled();
  await expect(page.locator('.lab-entity')).toHaveCount(0);
  await testInfo.attach('visual-lab-timeout', {
    body: await page.screenshot({ animations: 'disabled', fullPage: true }),
    contentType: 'image/png',
  });

  delayWorld = false;
  await page.getByRole('button', { name: 'RETRY LOAD', exact: true }).click();
  await expect(page.getByTestId('lab-status')).toHaveText('READY');
  await expect(page.getByRole('button', { name: 'HEAD', exact: true })).toBeEnabled();
  await expect(page.locator('.lab-entity')).toHaveCount(1);
  await testInfo.attach('visual-lab-recovered', {
    body: await page.screenshot({ animations: 'disabled', fullPage: true }),
    contentType: 'image/png',
  });
});

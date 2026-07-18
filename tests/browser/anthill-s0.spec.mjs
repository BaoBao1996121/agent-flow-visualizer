import { expect, test } from '@playwright/test';

function fixtureEvent(runId, eventId, eventType, extra = {}) {
  return {
    schema_version: '0.2.0',
    event_id: `${runId}:${eventId}`,
    event_type: eventType,
    run_id: runId,
    source: { adapter: 'playwright.s0.fixture', fidelity: 'native' },
    evidence: { level: 'observed', confidence: 1 },
    ...extra,
  };
}

test('@s0 fixed fixture traverses run truth, history, objects, and evidence', async ({
  page,
  request,
}, testInfo) => {
  const browserErrors = [];
  page.on('console', message => {
    if (message.type() === 'error') browserErrors.push(`console: ${message.text()}`);
  });
  page.on('pageerror', error => browserErrors.push(`page: ${error.message}`));
  page.on('response', response => {
    if (response.status() >= 500) {
      browserErrors.push(`response: ${response.status()} ${response.url()}`);
    }
  });

  const runId = `s0-vertical-fixture-r${testInfo.retry}`;
  const agent = {
    kind: 'agent',
    id: 'agent.s0.observer',
    name: 'S0 Observer',
  };
  const events = [
    fixtureEvent(runId, 'run-started', 'run.started', {
      agent_id: agent.id,
      subject: agent,
      payload: { status: 'running', fixture: 's0-vertical-v1' },
    }),
    fixtureEvent(runId, 'run-completed', 'run.completed', {
      agent_id: agent.id,
      subject: agent,
      payload: { status: 'success', fixture: 's0-vertical-v1' },
    }),
  ];
  const ingest = await request.post(`/api/anthill/runs/${runId}/events`, {
    data: { events },
  });
  expect(ingest.status(), await ingest.text()).toBe(201);

  await page.goto('/anthill');
  await page.locator('#run-select').selectOption(runId);

  await expect(page.locator('#run-status')).toHaveText('COMPLETED');
  await expect(page.locator('#world-mode')).toHaveText('AT HEAD · FOLLOWING');
  await expect(page.locator('#cursor-count')).toHaveText('1 / 1');
  await expect(page.locator('.truth-bars [data-truth="observed"] em')).toHaveText('2');

  await page.locator('#jump-start').click();
  await expect(page.locator('#world-mode')).toHaveText('HISTORY · SEQ 0');
  await expect(page.locator('#timeline-seq')).toHaveText('SEQ 0');
  await expect(page.locator('#cursor-count')).toHaveText('0 / 1');
  await expect(page.locator('#run-status')).toHaveText('RUNNING');

  await page.getByRole('tab', { name: 'OBJECTS' }).click();
  const mirror = page.getByRole('region', { name: 'World objects at cursor' });
  await expect(mirror).toHaveAttribute('data-cursor-seq', '0');
  const agentButton = mirror.locator(`[data-entity-id="${agent.id}"]`);
  await expect(agentButton).toHaveAccessibleName(
    /S0 Observer.*agent.*started.*observed.*1 event.*cursor seq 0/i,
  );

  await agentButton.focus();
  await agentButton.press('Enter');
  await expect(page.getByRole('tab', { name: 'EVENT' }))
    .toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('#event-heading')).toHaveText('run.started');
  await expect(page.locator('#event-detail .evidence-ribbon')).toHaveAttribute(
    'data-truth',
    'observed',
  );
  await expect(page.locator('#event-detail')).toContainText(`${runId}:run-started`);
  await expect(page.locator('#world-mode')).toHaveText('HISTORY · SEQ 0');
  expect(browserErrors).toEqual([]);
  await testInfo.attach('s0-history-evidence', {
    body: await page.screenshot(),
    contentType: 'image/png',
  });
});

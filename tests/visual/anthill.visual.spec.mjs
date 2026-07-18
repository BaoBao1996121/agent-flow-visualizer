import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';

import { expect, test } from '@playwright/test';

const fixture = JSON.parse(readFileSync(
  new URL('../fixtures/visual_rich_v1.json', import.meta.url),
  'utf8',
));
const VISUAL_INGEST_AT = fixture.events[0].clock.observed_at;

const isSyntheticVisualRun = run => (
  run?.synthetic === true && String(run?.run_id || '').startsWith('visual-')
);
const isSyntheticVisualEvent = event => (
  event?.payload?.synthetic === true
  && String(event?.run_id || '').startsWith('visual-')
  && event?.integrity
  && Number.isInteger(event?.clock?.ingest_seq)
);
const visualIntegrityHash = (runId, ingestSeq) => createHash('sha256')
  .update(`TEST-HARNESS:visual-integrity:${runId}:${ingestSeq}`)
  .digest('hex');
const normalizeVisualRun = run => {
  if (!isSyntheticVisualRun(run)) return run;
  const lastSeq = Number(run.event_count) - 1;
  return {
    ...run,
    created_at: VISUAL_INGEST_AT,
    updated_at: VISUAL_INGEST_AT,
    last_event_hash: Number.isInteger(lastSeq) && lastSeq >= 0
      ? visualIntegrityHash(run.run_id, lastSeq)
      : null,
  };
};
const normalizeVisualEventIntegrity = event => {
  if (!isSyntheticVisualEvent(event)) return event;
  const ingestSeq = event.clock.ingest_seq;
  return {
    ...event,
    clock: { ...event.clock, observed_at: VISUAL_INGEST_AT },
    integrity: {
      ...event.integrity,
      algorithm: 'sha256-test-harness-display',
      previous_event_hash: ingestSeq === 0
        ? null
        : visualIntegrityHash(event.run_id, ingestSeq - 1),
      event_hash: visualIntegrityHash(event.run_id, ingestSeq),
    },
  };
};

async function installVisualResponseNormalization(page) {
  const activity = { runCollectionRequests: 0 };
  await page.route('**/api/anthill/runs**', async route => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;
    const isRunCollection = pathname === '/api/anthill/runs';
    const isEventCollection = pathname.endsWith('/events');
    const isEventDetail = pathname.endsWith('/event');
    if (request.method() !== 'GET' || !(isRunCollection || isEventCollection || isEventDetail)) {
      await route.continue();
      return;
    }
    const response = await route.fetch();
    const payload = await response.json();
    let normalized = payload;
    if (isRunCollection) {
      activity.runCollectionRequests += 1;
      normalized = {
        ...payload,
        items: payload.items
          .map(normalizeVisualRun)
          .sort((left, right) => String(left.run_id).localeCompare(String(right.run_id), 'en-US')),
      };
    } else if (isEventCollection) {
      normalized = {
        ...payload,
        items: payload.items.map(normalizeVisualEventIntegrity),
      };
    } else {
      normalized = normalizeVisualEventIntegrity(payload);
    }
    await route.fulfill({ response, json: normalized });
  });
  return activity;
}

const eventsFor = (runId, limit = fixture.events.length) => fixture.events
  .slice(0, limit)
  .map(event => ({ ...event, run_id: runId }));

async function ingest(request, runId, limit) {
  const response = await request.post(`/api/anthill/runs/${runId}/events`, {
    data: { events: eventsFor(runId, limit) },
  });
  expect(response.status(), await response.text()).toBe(201);
}

async function openFrozenRun(page, runId, expectedSeq) {
  const responseActivity = await installVisualResponseNormalization(page);
  await page.addInitScript(() => localStorage.setItem('anthill.motion.v1', 'reduce'));
  await page.goto('/anthill?static=1');
  await page.locator('#run-select').selectOption(runId);
  await expect(page.locator('#run-select')).toHaveValue(runId);
  await expect(page.locator('#run-select option:checked')).toContainText(
    'INGEST 2026-07-18 00:00Z',
  );
  await expect(page.locator('#timeline-seq')).toHaveText(`SEQ ${expectedSeq}`);
  await expect(page.locator('#connection-label')).toHaveText('LEDGER CONNECTED');
  await page.evaluate(() => document.fonts.ready);
  expect(await page.evaluate(() => window.devicePixelRatio)).toBe(1);
  await expect(page.locator('body')).toHaveAttribute('data-effective-motion', 'reduce');
  return responseActivity;
}

async function capture(page, name) {
  await expect(page).toHaveScreenshot(name);
}

test('overview visual baseline', async ({ page, request }) => {
  const runId = 'visual-overview-v1';
  await ingest(request, runId);
  await openFrozenRun(page, runId, 43);
  await expect(page.locator('#run-status')).toHaveText('COMPLETED');
  await capture(page, 'overview.png');
});

test('evidence visual baseline', async ({ page, request }) => {
  const runId = 'visual-evidence-v1';
  const errorSeq = fixture.events.findIndex(event => event.event_type === 'error.raised');
  await ingest(request, runId);
  await openFrozenRun(page, runId, 43);
  await page.locator('#event-feed button', { hasText: 'error.raised' }).click();
  await expect(page.locator('#event-heading')).toHaveText('error.raised');
  await expect(page.locator('#event-detail')).toContainText('sha256-test-harness-display');
  await expect(page.locator('#event-detail')).toContainText(
    visualIntegrityHash(runId, errorSeq),
  );
  await capture(page, 'evidence.png');
});

test('coverage visual baseline', async ({ page, request }) => {
  const runId = 'visual-coverage-v1';
  await ingest(request, runId);
  await openFrozenRun(page, runId, 43);
  await page.locator('#inspector-tab-coverage').click();
  await expect(page.locator('#coverage-panel')).toBeVisible();
  await expect(page.locator('#coverage-heading')).toContainText('DOMAINS WITH SIGNALS');
  await capture(page, 'coverage.png');
});

test('compare visual baseline', async ({ page, request }) => {
  const leftRun = 'visual-compare-complete-v1';
  const rightRun = 'visual-compare-pre-compaction-v1';
  await ingest(request, leftRun);
  await ingest(request, rightRun, 31);
  const responseActivity = await openFrozenRun(page, leftRun, 43);
  const manifestRequestsBeforeCompare = responseActivity.runCollectionRequests;
  await page.locator('.view-button[data-view="compare"]').click();
  await page.locator('#compare-run-select').selectOption(rightRun);
  await expect(page.locator('#compare-left .compare-run-head span')).toContainText('COMPLETED');
  await expect(page.locator('#compare-right .compare-run-head span')).toContainText('RUNNING');
  await expect(page.locator('#comparability-banner')).toContainText('CONTROLLED KEYS MATCH');
  await page.waitForTimeout(150);
  expect(responseActivity.runCollectionRequests).toBe(manifestRequestsBeforeCompare);
  await capture(page, 'compare.png');
});

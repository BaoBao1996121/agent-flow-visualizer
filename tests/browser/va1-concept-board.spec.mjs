import path from 'node:path';
import { pathToFileURL } from 'node:url';

import { expect, test } from '@playwright/test';


const boardUrl = (query = '') => {
  const url = pathToFileURL(path.resolve('docs', 'visual-lab', 'va1', 'index.html'));
  url.search = query;
  return url.href;
};


test('@va1-s0 compares three isolated directions with an equal information skeleton', async ({ page }, testInfo) => {
  const requested = [];
  page.on('request', request => requested.push(request.url()));
  await page.goto(boardUrl('?view=compare'));

  await expect(page.getByTestId('va1-disclaimer')).toContainText('CONCEPT REFERENCE');
  await expect(page.getByTestId('concept-panel')).toHaveCount(3);
  await expect(page.locator('[data-runtime-reference="none"]')).toHaveCount(3);

  const inventories = await page.getByTestId('concept-panel').evaluateAll(panels => panels.map(panel => ({
    health: panel.querySelectorAll('[data-health]').length,
    slots: [...panel.querySelectorAll('[data-slot]')].map(node => node.dataset.slot),
    actions: [...panel.querySelectorAll('[data-worker-action]')].map(node => node.dataset.workerAction),
  })));
  expect(inventories.map(item => item.health)).toEqual([4, 4, 4]);
  expect(inventories[0].slots).toEqual(inventories[1].slots);
  expect(inventories[1].slots).toEqual(inventories[2].slots);
  expect(inventories[0].actions).toEqual(inventories[1].actions);
  expect(inventories[1].actions).toEqual(inventories[2].actions);
  expect(requested.every(url => url.startsWith('file:'))).toBe(true);

  await testInfo.attach('va1-direction-comparison', {
    body: await page.screenshot({ animations: 'disabled', fullPage: true }),
    contentType: 'image/png',
  });
});


test('recommended focus keeps health, timeline, trace, and evidence readable at 1600x1000', async ({ page }, testInfo) => {
  await page.goto(boardUrl('?view=focus&candidate=field-manual'));

  await expect(page.locator('body')).toHaveAttribute('data-view', 'focus');
  await expect(page.getByTestId('concept-panel')).toHaveCount(3);
  await expect(page.locator('[data-candidate="field-manual"]')).toBeVisible();
  await expect(page.locator('[data-candidate="blueprint"]')).toBeHidden();
  await expect(page.locator('[data-candidate="miniature"]')).toBeHidden();
  await expect(page.locator('[data-candidate="field-manual"] [data-health]')).toHaveCount(4);
  await expect(page.getByTestId('timeline')).toBeVisible();
  await expect(page.getByTestId('trace-legend')).toContainText('SEQUENCE');
  await expect(page.getByTestId('evidence-panel')).toContainText('CANONICAL EVENT');
  await expect(page.getByTestId('evidence-panel').getByRole('heading')).toHaveText('Researcher');
  await expect(page.getByTestId('evidence-panel')).toContainText('DECLARED');
  await expect(page.locator('[data-candidate="field-manual"] .selected-room'))
    .toHaveAttribute('data-slot', 'incident');

  const geometry = await page.evaluate(() => ({
    viewportWidth: innerWidth,
    documentWidth: document.documentElement.scrollWidth,
    clippedLabels: [...document.querySelectorAll('[data-answer-label]')]
      .filter(node => node.scrollWidth > node.clientWidth || node.scrollHeight > node.clientHeight)
      .map(node => node.textContent.trim()),
    smallestAnswerLabel: Math.min(...[...document.querySelectorAll('[data-answer-label]')]
      .map(node => Number.parseFloat(getComputedStyle(node).fontSize))),
  }));
  expect(geometry.documentWidth).toBeLessThanOrEqual(geometry.viewportWidth);
  expect(geometry.clippedLabels).toEqual([]);
  expect(geometry.smallestAnswerLabel).toBeGreaterThanOrEqual(12);

  await testInfo.attach('va1-field-manual-focus', {
    body: await page.screenshot({ animations: 'disabled', fullPage: true }),
    contentType: 'image/png',
  });
});

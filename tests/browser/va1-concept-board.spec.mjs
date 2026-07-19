import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

import { expect, test } from '@playwright/test';


const boardUrl = (query = '') => {
  const url = pathToFileURL(path.resolve('docs', 'visual-lab', 'va1', 'index.html'));
  url.search = query;
  return url.href;
};


test('@va1-compare-s1 compares three isolated directions with an equal information skeleton', async ({ page }, testInfo) => {
  const requested = [];
  page.on('request', request => requested.push(request.url()));
  await page.goto(boardUrl('?view=compare'));

  await expect(page.getByTestId('va1-disclaimer')).toContainText('CONCEPT REFERENCE');
  await expect(page.getByTestId('concept-panel')).toHaveCount(3);
  await expect(page.locator('[data-runtime-reference="none"]')).toHaveCount(3);

  const manifest = JSON.parse(await readFile(
    path.resolve('docs', 'visual-lab', 'va1', 'manifest.json'),
    'utf8',
  ));
  const fixture = JSON.parse(await readFile(manifest.source_fixture.path, 'utf8'));
  const cursorSeq = manifest.information_skeleton.cursor_seq;
  const throughCursor = fixture.events.filter(event => event.clock.source_seq <= cursorSeq);
  const cursorEvent = throughCursor.find(event => event.clock.source_seq === cursorSeq);
  const selectedAgent = throughCursor.find(
    event => event.subject?.id === cursorEvent.agent_id && event.subject?.kind === 'agent',
  ).subject;
  const contextEvent = throughCursor.filter(event => event.payload?.budget_tokens).at(-1);
  const modelEvent = throughCursor.filter(
    event => event.event_type === 'model.response.completed',
  ).at(-1);
  const toolEvent = throughCursor.filter(
    event => event.event_type === 'tool.execution.succeeded',
  ).at(-1);
  const memoryHits = throughCursor.filter(event => event.event_type === 'memory.hit');
  const agentCount = throughCursor.filter(event => event.event_type === 'agent.spawned').length;
  expect(manifest.source_fixture.integrity_evaluated).toBe(false);

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

  const semanticSnapshots = await page.getByTestId('concept-panel').evaluateAll(panels => {
    const text = node => node?.textContent.trim().replace(/\s+/g, ' ');
    return panels.map(panel => {
      const evidence = panel.querySelector('.evidence-panel');
      return {
        health: [...panel.querySelectorAll('[data-health]')].map(node => ({
          id: node.dataset.health,
          scope: node.dataset.scope,
          value: text(node.querySelector('strong')),
        })),
        rooms: [...panel.querySelectorAll('[data-slot]')].map(node => ({
          slot: node.dataset.slot,
          state: text(node.querySelector('em')),
        })),
        evidence: {
          eventSeq: evidence.dataset.eventSeq,
          eventId: evidence.dataset.eventId,
          eventType: evidence.dataset.eventType,
          agentId: evidence.dataset.agentId,
          subjectId: evidence.dataset.subjectId,
          evidenceLevel: evidence.dataset.evidenceLevel,
          heading: text(evidence.querySelector('h3')),
          meta: text(evidence.querySelector('.object-meta')),
          facts: [...evidence.querySelectorAll('dl div')].map(node => ({
            label: text(node.querySelector('dt')),
            value: text(node.querySelector('dd')),
          })),
          route: text(evidence.querySelector('.evidence-route')),
        },
        timeline: {
          markers: [...panel.querySelectorAll('.timeline-track [data-event-seq]')]
            .map(node => ({
              seq: Number(node.dataset.eventSeq),
              relation: node.dataset.relativeToCursor ?? 'at-or-before',
              label: node.getAttribute('aria-label'),
            })),
          future: text(panel.querySelector('.future-label')),
          futureTarget: Number(panel.querySelector('.future-label').dataset.forEventSeq),
        },
      };
    });
  });
  const expectedSnapshot = {
    health: [
      { id: 'run', scope: 'cursor', value: `RUNNING @${cursorSeq}` },
      { id: 'capture', scope: 'transport', value: 'SYNTHETIC' },
      { id: 'ledger', scope: 'integrity', value: 'NOT CHECKED' },
      { id: 'renderer', scope: 'board', value: 'REFERENCE' },
    ],
    rooms: [
      { slot: 'control', state: `${agentCount} agents in run` },
      { slot: 'model', state: `completed @${modelEvent.clock.source_seq}` },
      { slot: 'tool', state: `succeeded @${toolEvent.clock.source_seq}` },
      { slot: 'incident', state: 'recovered · selected' },
      { slot: 'context', state: `ready · ${contextEvent.payload.used_tokens.toLocaleString('en-US')}/${contextEvent.payload.budget_tokens.toLocaleString('en-US')}` },
      { slot: 'memory', state: `${memoryHits.length} hit · ${memoryHits[0].evidence.level}` },
      { slot: 'compaction', state: 'no compaction observed' },
      { slot: 'unknown', state: '0 unclassified events' },
    ],
    evidence: {
      eventSeq: String(cursorSeq),
      eventId: cursorEvent.event_id,
      eventType: cursorEvent.event_type,
      agentId: cursorEvent.agent_id,
      subjectId: cursorEvent.subject.id,
      evidenceLevel: cursorEvent.evidence.level,
      heading: selectedAgent.name,
      meta: 'AGENT · RECOVERED · DECLARED',
      facts: [
        { label: 'LATEST ASSOCIATED EVENT', value: cursorEvent.event_type },
        { label: 'EVENT SUBJECT', value: cursorEvent.subject.id },
        { label: 'AGENT', value: cursorEvent.agent_id },
        { label: 'TRUTH', value: '◇ DECLARED' },
      ],
      route: `CANONICAL EVENT EVENT ${cursorEvent.event_id.replace('evt_', '').slice(0, 7)} · REFERENCE`,
    },
    timeline: {
      markers: [
        { seq: 24, relation: 'at-or-before', label: 'Incident raised, sequence 24' },
        { seq: 30, relation: 'at-or-before', label: 'Recovery, sequence 30' },
        { seq: 37, relation: 'future', label: 'Future: compaction completed, sequence 37' },
        { seq: 30, relation: 'at-or-before', label: 'Cursor, sequence 30' },
      ],
      future: 'FUTURE',
      futureTarget: 37,
    },
  };
  expect(semanticSnapshots).toEqual([expectedSnapshot, expectedSnapshot, expectedSnapshot]);

  const compactionLabels = page.locator(
    '[data-testid="concept-panel"]:visible [data-slot="compaction"] [data-answer-label]',
  );
  await expect(compactionLabels).toHaveText([
    'COMPACTION PRESS',
    'COMPACTION PRESS',
    'COMPACTION PRESS',
  ]);
  const clippedLabels = await compactionLabels.evaluateAll(nodes => nodes
    .map(node => ({
      candidate: node.closest('[data-candidate]').dataset.candidate,
      clipped: node.scrollWidth > node.clientWidth || node.scrollHeight > node.clientHeight,
      fontSize: Number.parseFloat(getComputedStyle(node).fontSize),
    }))
    .filter(item => item.clipped || item.fontSize < 12));
  expect(clippedLabels).toEqual([]);
  const futureLabels = page.locator(
    '[data-testid="concept-panel"]:visible .future-label[data-answer-label]',
  );
  await expect(futureLabels).toHaveCount(3);
  const unreadableFutureLabels = await futureLabels.evaluateAll(nodes => nodes
    .map(node => ({
      candidate: node.closest('[data-candidate]').dataset.candidate,
      clipped: node.scrollWidth > node.clientWidth || node.scrollHeight > node.clientHeight,
      fontSize: Number.parseFloat(getComputedStyle(node).fontSize),
    }))
    .filter(item => item.clipped || item.fontSize < 12));
  expect(unreadableFutureLabels).toEqual([]);
  const futureAnchorDeltas = await page.getByTestId('concept-panel').evaluateAll(panels => panels
    .map(panel => {
      const label = panel.querySelector('.future-label[data-for-event-seq="37"]');
      const marker = panel.querySelector('.event[data-event-seq="37"]');
      if (!label || !marker) return Number.POSITIVE_INFINITY;
      const labelRect = label.getBoundingClientRect();
      const markerRect = marker.getBoundingClientRect();
      return Math.abs(
        (labelRect.left + labelRect.width / 2) - (markerRect.left + markerRect.width / 2),
      );
    }));
  expect(Math.max(...futureAnchorDeltas)).toBeLessThanOrEqual(8);

  await testInfo.attach('va1-direction-comparison', {
    body: await page.screenshot({ animations: 'disabled', fullPage: true }),
    contentType: 'image/png',
  });
});


test('@va1-focus-s1 recommended focus keeps cursor truth, timeline, trace, and evidence readable at 1600x1000', async ({ page }, testInfo) => {
  const manifest = JSON.parse(await readFile(
    path.resolve('docs', 'visual-lab', 'va1', 'manifest.json'),
    'utf8',
  ));
  expect(manifest.source_fixture).toEqual(expect.objectContaining({
    path: 'tests/fixtures/visual_rich_v1.json',
    sha256: '6ae35e714fb6c99d98b8598e0d7f18ccfac8f305c655b294fb67d10d6a360ac2',
  }));
  const fixtureBytes = await readFile(path.resolve(manifest.source_fixture.path));
  expect(createHash('sha256').update(fixtureBytes).digest('hex'))
    .toBe(manifest.source_fixture.sha256);
  const fixture = JSON.parse(fixtureBytes.toString('utf8'));
  const cursorSeq = manifest.information_skeleton.cursor_seq;
  const eventAt = seq => {
    const matches = fixture.events.filter(event => event.clock.source_seq === seq);
    expect(matches).toHaveLength(1);
    return matches[0];
  };
  const cursorEvent = eventAt(cursorSeq);
  expect(cursorEvent).toMatchObject(manifest.source_fixture.cursor_event);
  expect(cursorEvent).toMatchObject({
    event_type: 'error.recovered',
    agent_id: 'agent.researcher',
    subject: { kind: 'tool.call', id: 'tool.logs-1', name: 'Query logs' },
    evidence: { level: 'declared' },
  });
  const futureContext = eventAt(31);
  const futureCompaction = eventAt(37);
  expect(futureContext.event_type).toBe('context.budget.updated');
  expect(futureCompaction.event_type).toBe('compaction.completed');
  const contextAtCursor = fixture.events
    .filter(event => event.clock.source_seq <= cursorSeq && event.payload?.budget_tokens)
    .at(-1);
  expect(contextAtCursor).toMatchObject({
    event_type: 'context.assembly.completed',
    payload: { used_tokens: 1680, budget_tokens: 8192 },
  });
  const selectedAgent = fixture.events.find(
    event => event.subject?.id === cursorEvent.agent_id && event.subject?.kind === 'agent',
  ).subject;

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
  await expect(page.getByTestId('evidence-panel').getByRole('heading'))
    .toHaveText(selectedAgent.name);
  await expect(page.getByTestId('evidence-panel')).toContainText('DECLARED');
  await expect(page.getByTestId('evidence-panel')).toContainText(cursorEvent.subject.id);
  await expect(page.getByTestId('evidence-panel')).toContainText(cursorEvent.agent_id);
  await expect(page.getByTestId('evidence-panel'))
    .toHaveAttribute('data-event-id', cursorEvent.event_id);
  await expect(page.getByTestId('evidence-panel'))
    .toHaveAttribute('data-event-seq', String(cursorSeq));
  await expect(page.getByTestId('evidence-panel'))
    .toHaveAttribute('data-event-type', cursorEvent.event_type);
  await expect(page.getByTestId('evidence-panel'))
    .toHaveAttribute('data-agent-id', cursorEvent.agent_id);
  await expect(page.getByTestId('evidence-panel'))
    .toHaveAttribute('data-subject-id', cursorEvent.subject.id);
  await expect(page.getByTestId('evidence-panel'))
    .toHaveAttribute('data-evidence-level', cursorEvent.evidence.level);
  await expect(page.locator('[data-candidate="field-manual"] [data-slot="context"] em'))
    .toHaveText('ready · 1,680/8,192');
  await expect(page.locator('[data-candidate="field-manual"] [data-slot="compaction"] em'))
    .toHaveText('no compaction observed');
  const timelineMarkers = await page
    .locator('[data-candidate="field-manual"] .timeline-track [data-event-seq]')
    .evaluateAll(nodes => nodes.map(node => ({
      seq: Number(node.dataset.eventSeq),
      relation: node.dataset.relativeToCursor ?? 'at-or-before',
      label: node.getAttribute('aria-label'),
    })));
  expect(timelineMarkers).toEqual([
    { seq: 24, relation: 'at-or-before', label: 'Incident raised, sequence 24' },
    { seq: 30, relation: 'at-or-before', label: 'Recovery, sequence 30' },
    { seq: 37, relation: 'future', label: 'Future: compaction completed, sequence 37' },
    { seq: 30, relation: 'at-or-before', label: 'Cursor, sequence 30' },
  ]);
  await expect(page.locator('[data-candidate="field-manual"] .future-label'))
    .toHaveText('FUTURE');
  const futureAnchorDelta = await page.locator('[data-candidate="field-manual"]').evaluate(panel => {
    const label = panel.querySelector('.future-label[data-for-event-seq="37"]');
    const marker = panel.querySelector('.event[data-event-seq="37"]');
    if (!label || !marker) return Number.POSITIVE_INFINITY;
    const labelRect = label.getBoundingClientRect();
    const markerRect = marker.getBoundingClientRect();
    return Math.abs(
      (labelRect.left + labelRect.width / 2) - (markerRect.left + markerRect.width / 2),
    );
  });
  expect(futureAnchorDelta).toBeLessThanOrEqual(8);
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

  const rendered = (await page.locator('body').innerText()).toLowerCase();
  for (const forbidden of ['near full', '7,990', '8460', '3920', 'sha256:demo-summary']) {
    expect(rendered).not.toContain(forbidden);
  }

  await testInfo.attach('va1-field-manual-focus', {
    body: await page.screenshot({ animations: 'disabled', fullPage: true }),
    contentType: 'image/png',
  });
});

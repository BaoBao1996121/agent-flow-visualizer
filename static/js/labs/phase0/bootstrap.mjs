import {
  LabDataError,
  StudySceneClient,
  canonicalEventRoute,
  readLabConfig,
  safeText,
} from './study-scene.mjs';
import { renderCutaway, renderEntities } from './cutaway-svg.mjs';

const element = id => document.getElementById(id);
const nodes = Object.freeze({
  status: document.querySelector('[data-testid="lab-status"]'),
  fixtureBadge: document.querySelector('[data-testid="fixture-badge"]'),
  integrityStatus: document.querySelector('[data-testid="integrity-status"]'),
  eventCount: document.querySelector('[data-testid="event-count"]'),
  cursorSequence: document.querySelector('[data-testid="cursor-seq"]'),
  currentEventType: document.querySelector('[data-testid="current-event-type"]'),
  evidenceTitle: document.querySelector('[data-testid="evidence-title"]'),
  evidenceEventType: document.querySelector('[data-testid="evidence-event-type"]'),
  evidenceTruth: document.querySelector('[data-testid="evidence-truth"]'),
  evidenceRoute: document.querySelector('[data-testid="evidence-route"]'),
  evidenceLive: document.querySelector('[data-testid="evidence-live"]'),
  runId: element('run-id'),
  runStatus: element('run-status'),
  sceneNote: element('scene-note'),
  svg: element('cutaway-svg'),
  entityPlane: element('entity-plane'),
  drawerSequence: element('drawer-seq'),
  evidenceSummary: element('evidence-summary'),
  evidenceStatus: element('evidence-status'),
  evidenceSource: element('evidence-source'),
  evidenceExplanation: element('evidence-explanation'),
  alert: element('lab-alert'),
  alertMessage: element('lab-alert-message'),
  retry: element('lab-retry'),
});
const PROVENANCE_LABELS = Object.freeze({
  synthetic: 'SYNTHETIC RUN',
  mixed: 'CONTAINS SYNTHETIC EVENTS',
  recorded: 'RECORDED RUN',
});

let config;
let client;
let scene;
let selectedEntityId = '';
let requestGeneration = 0;
let activeController = null;
let controlsBound = false;

function setStatus(value) {
  const status = safeText(value, 'ERROR', 24).toUpperCase();
  nodes.status.textContent = status;
  nodes.status.dataset.state = status.toLowerCase();
}

function showAlert(message, retryable = true) {
  nodes.alertMessage.textContent = safeText(message, 'Unable to load the addressed run.', 480);
  nodes.retry.hidden = !retryable;
  nodes.alert.hidden = false;
}

function clearAlert() {
  nodes.alertMessage.textContent = '';
  nodes.retry.hidden = true;
  nodes.alert.hidden = true;
}

function syncMotionPreference() {
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  document.body.dataset.motion = reduced ? 'reduce' : 'full';
  document.body.dataset.static = String(config?.staticCapture === true);
}

function truthLabel(event, entity) {
  return safeText(event?.truth?.level || entity?.truth?.level, 'unknown', 40).toUpperCase();
}

function disableEvidenceRoute() {
  nodes.evidenceRoute.removeAttribute('href');
  nodes.evidenceRoute.setAttribute('aria-disabled', 'true');
  nodes.evidenceRoute.tabIndex = -1;
}

function enableEvidenceRoute(route) {
  nodes.evidenceRoute.setAttribute('href', route);
  nodes.evidenceRoute.setAttribute('aria-disabled', 'false');
  nodes.evidenceRoute.removeAttribute('tabindex');
}

function clearEvidence() {
  nodes.evidenceTitle.textContent = 'Select an entity';
  nodes.evidenceSummary.textContent = 'Keyboard-focus any visible Agent or machine and press Enter to inspect its latest ledger fact.';
  nodes.evidenceEventType.textContent = '—';
  nodes.evidenceTruth.textContent = '—';
  nodes.evidenceStatus.textContent = '—';
  nodes.evidenceSource.textContent = '—';
  nodes.evidenceExplanation.textContent = 'No evidence selected.';
  nodes.drawerSequence.textContent = 'SEQ —';
  disableEvidenceRoute();
  nodes.evidenceLive.textContent = 'Evidence unavailable.';
}

function showCursorEvidence() {
  const event = scene.currentEvent;
  nodes.evidenceTitle.textContent = 'Cursor event';
  nodes.evidenceSummary.textContent = event.summary;
  nodes.evidenceEventType.textContent = event.type;
  nodes.evidenceTruth.textContent = truthLabel(event, null);
  nodes.evidenceStatus.textContent = 'AT CURSOR';
  nodes.evidenceSource.textContent = `${event.source.adapter} · ${event.source.fidelity}`;
  nodes.evidenceExplanation.textContent = event.truth.explanation;
  nodes.drawerSequence.textContent = `SEQ ${event.sequence}`;
  enableEvidenceRoute(canonicalEventRoute(scene.runId, event.id));
  nodes.evidenceLive.textContent = `Cursor event ${event.type} loaded at sequence ${event.sequence}.`;
}

function selectEntity(entity) {
  const event = scene.eventsById.get(entity.lastEventId);
  selectedEntityId = entity.id;
  for (const candidate of nodes.entityPlane.querySelectorAll('.lab-entity')) {
    candidate.setAttribute('aria-pressed', String(candidate.dataset.entityId === selectedEntityId));
  }

  nodes.evidenceTitle.textContent = entity.name;
  nodes.evidenceSummary.textContent = event?.summary || `Latest projected fact for ${entity.name}.`;
  nodes.evidenceEventType.textContent = event?.type || 'EVENT NOT AVAILABLE';
  nodes.evidenceTruth.textContent = truthLabel(event, entity);
  nodes.evidenceStatus.textContent = entity.status.toUpperCase();
  nodes.evidenceSource.textContent = event
    ? `${event.source.adapter} · ${event.source.fidelity}`
    : entity.truth.sourceAdapter;
  nodes.evidenceExplanation.textContent = event?.truth?.explanation
    || `${entity.truth.level.toUpperCase()} at confidence ${entity.truth.confidence ?? 'not recorded'}.`;
  nodes.drawerSequence.textContent = `SEQ ${event?.sequence ?? entity.lastSeq}`;
  nodes.evidenceLive.textContent = `Evidence loaded for ${entity.name}.`;

  if (entity.lastEventId) {
    enableEvidenceRoute(canonicalEventRoute(scene.runId, entity.lastEventId));
  } else {
    disableEvidenceRoute();
  }
}

function invalidateRenderedScene(error) {
  selectedEntityId = '';
  scene = null;
  nodes.svg.replaceChildren();
  nodes.entityPlane.replaceChildren();
  clearEvidence();
  nodes.runStatus.textContent = 'UNAVAILABLE';
  nodes.fixtureBadge.textContent = 'PENDING';
  nodes.fixtureBadge.dataset.provenance = 'pending';
  nodes.eventCount.textContent = '—';
  nodes.cursorSequence.textContent = '— / —';
  nodes.currentEventType.textContent = 'SCENE INVALIDATED';
  nodes.sceneNote.textContent = 'Scene output was cleared because this request could not be verified; run lifecycle is not inferred from a display failure.';
  nodes.integrityStatus.textContent = error instanceof LabDataError && error.code === 'integrity_failed'
    ? 'FAILED'
    : 'UNVERIFIED';
  const headRetryIsBound = controlsBound && client instanceof StudySceneClient;
  for (const button of document.querySelectorAll('[data-cursor]')) {
    button.disabled = button.dataset.cursor !== 'head' || !headRetryIsBound;
    button.setAttribute('aria-pressed', 'false');
  }
}

function selectedEntityFor(nextScene) {
  return nextScene.entities.find(entity => entity.id === selectedEntityId) || null;
}

function updateCursorButtons() {
  for (const button of document.querySelectorAll('[data-cursor]')) {
    const preset = button.dataset.preset;
    const presetTarget = preset ? scene.namedCursors[preset] : null;
    if (preset) {
      button.hidden = presetTarget === null;
      button.dataset.cursor = presetTarget === null ? '' : String(presetTarget);
    }
    const target = button.dataset.cursor === 'head'
      ? scene.headSeq
      : Number(button.dataset.cursor);
    button.disabled = button.hidden || !Number.isInteger(target) || target > scene.headSeq;
    button.setAttribute('aria-pressed', String(target === scene.cursorSeq));
  }
}

function updateAddressBar() {
  const next = new URL(window.location.href);
  next.searchParams.set('run_id', scene.runId);
  next.searchParams.set('cursor_seq', String(scene.cursorSeq));
  if (config.staticCapture) next.searchParams.set('static', '1');
  window.history.replaceState(null, '', next);
}

function renderScene() {
  nodes.runId.textContent = scene.runId;
  nodes.runId.title = scene.runId;
  nodes.runStatus.textContent = scene.runStatus.toUpperCase();
  nodes.integrityStatus.textContent = scene.integrityStatus.toUpperCase();
  nodes.fixtureBadge.textContent = PROVENANCE_LABELS[scene.provenance];
  nodes.fixtureBadge.dataset.provenance = scene.provenance;
  nodes.eventCount.textContent = String(scene.eventNumber);
  nodes.cursorSequence.textContent = `${scene.cursorSeq} / ${scene.headSeq}`;
  nodes.currentEventType.textContent = scene.currentEvent?.type || 'EVENT NOT AVAILABLE';
  nodes.sceneNote.textContent = `Reducer ${scene.reducerVersion} · ${scene.entities.length} entities visible at cursor · ${scene.eventTotal} ledger events loaded.`;

  renderCutaway(nodes.svg, scene);
  renderEntities(nodes.entityPlane, scene, selectEntity, selectedEntityId);
  updateCursorButtons();
  updateAddressBar();

  const retainedSelection = selectedEntityFor(scene);
  if (retainedSelection) selectEntity(retainedSelection);
  else {
    selectedEntityId = '';
    showCursorEvidence();
  }
}

function failureMessage(error) {
  if (error instanceof LabDataError) return error.message;
  if (error?.name === 'AbortError') return 'The previous cursor request was replaced.';
  return 'Unexpected visual-lab error. Inspect the browser console and addressed API routes.';
}

async function seekTo(target) {
  const generation = ++requestGeneration;
  activeController?.abort();
  activeController = new AbortController();
  clearAlert();
  setStatus('SEEKING');
  try {
    const candidateClient = target === 'head'
      ? new StudySceneClient(config.runId, config.requestTimeoutMs)
      : client;
    const nextScene = target === 'head'
      ? await candidateClient.load(null, activeController.signal)
      : await candidateClient.seek(Number(target), activeController.signal);
    if (generation !== requestGeneration) return;
    if (target === 'head') client = candidateClient;
    scene = nextScene;
    renderScene();
    setStatus('READY');
  } catch (error) {
    if (generation !== requestGeneration || error?.name === 'AbortError') return;
    invalidateRenderedScene(error);
    setStatus('ERROR');
    showAlert(failureMessage(error));
  }
}

function bindControls() {
  if (controlsBound) return;
  controlsBound = true;
  for (const button of document.querySelectorAll('[data-cursor]')) {
    button.addEventListener('click', () => seekTo(button.dataset.cursor));
  }
  const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
  preference.addEventListener('change', syncMotionPreference);
}

async function start() {
  const generation = ++requestGeneration;
  activeController?.abort();
  activeController = new AbortController();
  clearAlert();
  setStatus('LOADING');
  nodes.fixtureBadge.textContent = 'PENDING';
  nodes.fixtureBadge.dataset.provenance = 'pending';
  try {
    config = readLabConfig();
    syncMotionPreference();
    nodes.runId.textContent = config.runId;
    nodes.runId.title = config.runId;
    client = new StudySceneClient(config.runId, config.requestTimeoutMs);
    const nextScene = await client.load(config.requestedCursor, activeController.signal);
    if (generation !== requestGeneration) return;
    scene = nextScene;
    renderScene();
    bindControls();
    setStatus('READY');
  } catch (error) {
    if (error?.name === 'AbortError' || generation !== requestGeneration) return;
    invalidateRenderedScene(error);
    setStatus('ERROR');
    showAlert(failureMessage(error), true);
  }
}

nodes.retry.addEventListener('click', start);
start();

const API_ROOT = '/api/anthill';
const CONTROL_OR_FORMAT = /[\u0000-\u001f\u007f-\u009f\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]/u;
const RESERVED_RUN_ID = /[/\\?#%]/u;
const DEFAULT_REQUEST_TIMEOUT_MS = 10_000;
const MIN_REQUEST_TIMEOUT_MS = 100;
const MAX_REQUEST_TIMEOUT_MS = 30_000;

export const ZONE_IDS = Object.freeze([
  'control',
  'context_assembly',
  'model_engine',
  'tool_workshop',
  'retrieval_depot',
  'memory_vault',
  'compaction_plant',
  'handoff_bridge',
  'checkpoint_station',
  'artifact_foundry',
  'incident_bay',
  'unknown_fog',
]);

const ZONE_SET = new Set(ZONE_IDS);
const TRUTH_LEVELS = new Set([
  'observed',
  'declared',
  'inferred',
  'counterfactual_verified',
  'unknown',
]);
const ZONE_BY_FAMILY = Object.freeze({
  run: 'control',
  agent: 'control',
  task: 'control',
  decision: 'control',
  policy: 'control',
  manifest: 'control',
  semantic: 'control',
  context: 'context_assembly',
  model: 'model_engine',
  tool: 'tool_workshop',
  retrieval: 'retrieval_depot',
  embedding: 'retrieval_depot',
  memory: 'memory_vault',
  compaction: 'compaction_plant',
  handoff: 'handoff_bridge',
  checkpoint: 'checkpoint_station',
  artifact: 'artifact_foundry',
  error: 'incident_bay',
});

export class LabDataError extends Error {
  constructor(message, status = null, code = 'scene_unavailable') {
    super(message);
    this.name = 'LabDataError';
    this.status = status;
    this.code = code;
  }
}

export function safeText(value, fallback = 'UNKNOWN', maxLength = 180) {
  if (typeof value !== 'string') return fallback;
  const clean = value
    .replace(/[\u0000-\u001f\u007f-\u009f\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]/gu, ' ')
    .replace(/\s+/gu, ' ')
    .trim();
  if (!clean) return fallback;
  return clean.length <= maxLength ? clean : `${clean.slice(0, maxLength - 1)}…`;
}

function opaqueId(value, fallback = '') {
  return typeof value === 'string' && value.length >= 1 && value.length <= 256
    ? value
    : fallback;
}

function validRunId(value) {
  return typeof value === 'string'
    && value.length >= 1
    && value.length <= 256
    && value === value.trim()
    && value !== '.'
    && value !== '..'
    && !CONTROL_OR_FORMAT.test(value)
    && !RESERVED_RUN_ID.test(value);
}

function parseCursor(value) {
  if (value === null || value === '') return null;
  if (!/^(0|[1-9]\d*)$/u.test(value)) {
    throw new LabDataError('cursor_seq must be a non-negative integer.');
  }
  const cursor = Number(value);
  if (!Number.isSafeInteger(cursor)) {
    throw new LabDataError('cursor_seq is outside the safe integer range.');
  }
  return cursor;
}

function parseRequestTimeout(value) {
  if (value === null || value === '') return DEFAULT_REQUEST_TIMEOUT_MS;
  if (!/^[1-9]\d*$/u.test(value)) {
    throw new LabDataError('timeout_ms must be an integer between 100 and 30000.');
  }
  const timeout = Number(value);
  if (!Number.isSafeInteger(timeout) || timeout < MIN_REQUEST_TIMEOUT_MS || timeout > MAX_REQUEST_TIMEOUT_MS) {
    throw new LabDataError('timeout_ms must be an integer between 100 and 30000.');
  }
  return timeout;
}

export function readLabConfig(locationLike = window.location) {
  const parameters = new URLSearchParams(locationLike.search);
  const runIds = parameters.getAll('run_id');
  const cursorValues = parameters.getAll('cursor_seq');
  const staticValues = parameters.getAll('static');
  const timeoutValues = parameters.getAll('timeout_ms');
  if (runIds.length !== 1 || cursorValues.length > 1 || staticValues.length > 1 || timeoutValues.length > 1) {
    throw new LabDataError('run_id must appear exactly once; cursor_seq, static and timeout_ms may appear at most once.');
  }
  const [runId] = runIds;
  if (!validRunId(runId)) {
    throw new LabDataError('Provide one valid run_id in the URL. The lab never creates a run automatically.');
  }
  return Object.freeze({
    runId,
    requestedCursor: parseCursor(cursorValues[0] ?? null),
    staticCapture: staticValues.length === 1 && staticValues[0] !== '0',
    requestTimeoutMs: parseRequestTimeout(timeoutValues[0] ?? null),
  });
}

async function responseMessage(response) {
  try {
    const body = await response.json();
    const detail = typeof body?.detail === 'string'
      ? body.detail
      : typeof body?.detail?.message === 'string'
        ? body.detail.message
        : null;
    return safeText(detail, `request failed with status ${response.status}`);
  } catch {
    return `request failed with status ${response.status}`;
  }
}

async function fetchJson(path, signal, timeoutMs) {
  const timeoutSignal = AbortSignal.timeout(timeoutMs);
  const requestSignal = signal ? AbortSignal.any([signal, timeoutSignal]) : timeoutSignal;
  try {
    const response = await fetch(path, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      credentials: 'same-origin',
      cache: 'no-store',
      signal: requestSignal,
    });
    if (!response.ok) {
      throw new LabDataError(await responseMessage(response), response.status);
    }
    return await response.json();
  } catch (error) {
    if (timeoutSignal.aborted && signal?.aborted !== true) {
      throw new LabDataError(`Request timed out after ${timeoutMs} ms.`);
    }
    throw error;
  }
}

function asInteger(value, fallback = -1) {
  return Number.isInteger(value) && Number.isSafeInteger(value) ? value : fallback;
}

function eventSequence(event) {
  return asInteger(event?.clock?.ingest_seq);
}

function eventZone(event) {
  const eventType = typeof event?.event_type === 'string' ? event.event_type : '';
  const family = eventType.split('.', 1)[0];
  return ZONE_BY_FAMILY[family] || 'unknown_fog';
}

function normalizeTruth(truth) {
  const candidate = safeText(truth?.level, 'unknown', 40).toLowerCase();
  const level = TRUTH_LEVELS.has(candidate) ? candidate : 'unknown';
  return Object.freeze({
    level,
    confidence: Number.isFinite(Number(truth?.confidence)) ? Number(truth.confidence) : null,
    sourceFidelity: safeText(truth?.source_fidelity, 'unknown', 60),
    sourceAdapter: safeText(truth?.source_adapter, 'unknown', 120),
  });
}

function normalizeEntity(entity, id) {
  const zone = ZONE_SET.has(entity?.zone) ? entity.zone : 'unknown_fog';
  return Object.freeze({
    id: opaqueId(id, 'unknown-entity'),
    kind: safeText(entity?.kind, 'unknown', 80),
    name: safeText(entity?.name, safeText(id, 'Unknown entity', 120), 120),
    zone,
    status: safeText(entity?.status, 'unknown', 80),
    active: entity?.active === true,
    eventCount: Math.max(0, asInteger(entity?.event_count, 0)),
    firstSeq: asInteger(entity?.first_seq),
    lastSeq: asInteger(entity?.last_seq),
    firstEventId: opaqueId(entity?.first_event_id),
    lastEventId: opaqueId(entity?.last_event_id),
    truth: normalizeTruth(entity?.truth),
  });
}

function normalizeEvent(event) {
  const sequence = eventSequence(event);
  return Object.freeze({
    raw: event,
    id: opaqueId(event?.event_id),
    type: safeText(event?.event_type, 'unknown.event', 160),
    sequence,
    zone: eventZone(event),
    summary: safeText(event?.summary, 'No event summary recorded.', 240),
    subjectId: opaqueId(event?.subject?.id),
    truth: Object.freeze({
      level: (() => {
        const candidate = safeText(event?.evidence?.level, 'unknown', 40).toLowerCase();
        return TRUTH_LEVELS.has(candidate) ? candidate : 'unknown';
      })(),
      confidence: Number.isFinite(Number(event?.evidence?.confidence))
        ? Number(event.evidence.confidence)
        : null,
      explanation: safeText(event?.evidence?.explanation, 'No evidence explanation recorded.', 360),
    }),
    source: Object.freeze({
      adapter: safeText(event?.source?.adapter, 'unknown', 120),
      fidelity: safeText(event?.source?.fidelity, 'unknown', 60),
    }),
    synthetic: event?.payload?.synthetic === true || event?.extensions?.['anthill.demo'] === true,
  });
}

function requireWorldEnvelope(envelope, expectedRunId) {
  if (!envelope || typeof envelope !== 'object' || !envelope.state || typeof envelope.state !== 'object') {
    throw new LabDataError('World API returned an invalid projection envelope.');
  }
  if (envelope.run_id !== expectedRunId || envelope.state.run_id !== expectedRunId) {
    throw new LabDataError('World API returned a different run identity.');
  }
  return envelope;
}

function requireEventEnvelope(envelope, expectedRunId) {
  if (!envelope || typeof envelope !== 'object' || !Array.isArray(envelope.items)) {
    throw new LabDataError('Events API returned an invalid ledger envelope.');
  }
  if (envelope.run_id !== expectedRunId) {
    throw new LabDataError('Events API returned a different run identity.');
  }
  if (envelope.has_more === true) {
    throw new LabDataError('This Phase 0 lab is bounded to 5,000 events; the addressed run exceeds that limit.');
  }
  const eventIds = new Set();
  for (const [index, event] of envelope.items.entries()) {
    if (!event || typeof event !== 'object' || event.run_id !== expectedRunId) {
      throw new LabDataError('Events API returned an event for a different run identity.');
    }
    const eventId = opaqueId(event.event_id);
    if (!eventId || eventIds.has(eventId)) {
      throw new LabDataError('Events API returned a missing or duplicate event identity.');
    }
    if (eventSequence(event) !== index) {
      throw new LabDataError(`Events API sequence is not contiguous at ingest seq ${index}.`);
    }
    eventIds.add(eventId);
  }
  return envelope;
}

function requireIntegrityEnvelope(envelope, expectedRunId) {
  if (!envelope || typeof envelope !== 'object' || envelope.run_id !== expectedRunId) {
    throw new LabDataError('Integrity API returned an invalid run identity.');
  }
  if (envelope.valid !== true) {
    throw new LabDataError('Ledger integrity verification failed.', null, 'integrity_failed');
  }
  return envelope;
}

function reconcileEntityEvidence(entities, eventsById, cursorSeq) {
  for (const entity of entities) {
    const event = eventsById.get(entity.lastEventId);
    if (
      entity.lastSeq < 0
      || entity.lastSeq > cursorSeq
      || !entity.lastEventId
      || !event
      || event.sequence !== entity.lastSeq
    ) {
      throw new LabDataError(`Entity evidence does not reconcile at cursor for ${entity.id}.`);
    }
  }
}

function classifyProvenance(events) {
  const syntheticCount = events.filter(event => event.synthetic).length;
  if (syntheticCount === events.length) return 'synthetic';
  if (syntheticCount === 0) return 'recorded';
  return 'mixed';
}

function buildScene(runId, headEnvelope, cursorEnvelope, eventEnvelope, integrityEnvelope) {
  const world = cursorEnvelope.state;
  const headSeq = asInteger(headEnvelope.head_seq);
  const cursorSeq = asInteger(cursorEnvelope.projected_seq);
  if (headSeq < 0 || cursorSeq < 0 || cursorSeq > headSeq) {
    throw new LabDataError('World API returned an invalid head or cursor sequence.');
  }

  const events = eventEnvelope.items
    .map(normalizeEvent)
    .filter(event => event.sequence >= 0 && event.sequence <= headSeq)
    .sort((left, right) => left.sequence - right.sequence);
  const sequenceSet = new Set(events.map(event => event.sequence));
  if (!sequenceSet.has(cursorSeq)) {
    throw new LabDataError('The cursor event is absent from the ledger response.');
  }
  const integrityEventCount = asInteger(integrityEnvelope.event_count);
  const headEventCount = asInteger(headEnvelope.state?.event_count);
  const cursorEventCount = asInteger(world.event_count);
  const eventsAtCursor = events.filter(event => event.sequence <= cursorSeq).length;
  if (
    events.length !== headSeq + 1
    || headEventCount !== headSeq + 1
    || integrityEventCount !== events.length
  ) {
    throw new LabDataError('Head event count disagrees across ledger, world and integrity evidence.');
  }
  if (cursorEventCount !== cursorSeq + 1 || eventsAtCursor !== cursorEventCount) {
    throw new LabDataError('Cursor event count disagrees with its ledger projection.');
  }

  const eventsById = new Map(events.filter(event => event.id).map(event => [event.id, event]));
  const eventsBySequence = new Map(events.map(event => [event.sequence, event]));
  const entities = Object.entries(world.entities || {})
    .map(([id, entity]) => normalizeEntity(entity, id))
    .sort((left, right) => left.firstSeq - right.firstSeq || left.id.localeCompare(right.id, 'en-US'));
  reconcileEntityEvidence(entities, eventsById, cursorSeq);
  const zoneCounts = Object.fromEntries(ZONE_IDS.map(zoneId => [
    zoneId,
    entities.filter(entity => entity.zone === zoneId).length,
  ]));
  if (Object.values(zoneCounts).some(count => count > 4)) {
    throw new LabDataError('This Phase 0 lab allows at most four visible entities in one chamber.');
  }
  const zoneEventCounts = Object.fromEntries(ZONE_IDS.map(zoneId => [
    zoneId,
    Math.max(0, asInteger(world?.zone_event_counts?.[zoneId], 0)),
  ]));
  const currentEvent = eventsBySequence.get(cursorSeq);
  const namedCursors = Object.freeze({
    incident: events.find(event => event.type === 'error.raised')?.sequence ?? null,
    compaction: events.find(event => event.type === 'compaction.completed')?.sequence ?? null,
  });

  return Object.freeze({
    runId,
    runStatus: safeText(world.run_status, 'unknown', 80),
    headSeq,
    cursorSeq,
    eventNumber: cursorSeq + 1,
    eventTotal: events.length,
    currentEvent,
    currentZone: currentEvent?.zone || 'unknown_fog',
    namedCursors,
    provenance: classifyProvenance(events),
    entities,
    events,
    eventsById,
    zoneCounts,
    zoneEventCounts,
    unknownEventTypes: Array.isArray(world.unknown_event_types)
      ? world.unknown_event_types.map(value => safeText(value, 'unknown.event', 160))
      : [],
    reducerVersion: safeText(world.reducer_version, 'unknown', 60),
    integrityStatus: 'verified',
    integrityEventCount,
  });
}

export function canonicalEventRoute(runId, eventId) {
  return `${API_ROOT}/runs/${encodeURIComponent(runId)}/event?event_id=${encodeURIComponent(eventId)}`;
}

export class StudySceneClient {
  constructor(runId, requestTimeoutMs = DEFAULT_REQUEST_TIMEOUT_MS) {
    if (!validRunId(runId)) throw new LabDataError('Invalid run identity.');
    if (
      !Number.isSafeInteger(requestTimeoutMs)
      || requestTimeoutMs < MIN_REQUEST_TIMEOUT_MS
      || requestTimeoutMs > MAX_REQUEST_TIMEOUT_MS
    ) {
      throw new LabDataError('Invalid request timeout.');
    }
    this.runId = runId;
    this.requestTimeoutMs = requestTimeoutMs;
    this.headEnvelope = null;
    this.eventEnvelope = null;
    this.integrityEnvelope = null;
  }

  worldRoute(cursor = null) {
    const root = `${API_ROOT}/runs/${encodeURIComponent(this.runId)}/world`;
    return cursor === null ? root : `${root}?at_seq=${cursor}`;
  }

  eventsRoute(headSeq) {
    return `${API_ROOT}/runs/${encodeURIComponent(this.runId)}/events?from_seq=0&to_seq=${headSeq}&limit=5000`;
  }

  integrityRoute() {
    return `${API_ROOT}/runs/${encodeURIComponent(this.runId)}/integrity`;
  }

  async load(requestedCursor = null, signal = undefined) {
    const batchController = new AbortController();
    const batchSignal = signal
      ? AbortSignal.any([signal, batchController.signal])
      : batchController.signal;
    try {
      const [headEnvelope, integrityEnvelope] = await Promise.all([
        fetchJson(this.worldRoute(), batchSignal, this.requestTimeoutMs)
          .then(value => requireWorldEnvelope(value, this.runId)),
        fetchJson(this.integrityRoute(), batchSignal, this.requestTimeoutMs)
          .then(value => requireIntegrityEnvelope(value, this.runId)),
      ]);
      const headSeq = asInteger(headEnvelope.head_seq);
      if (headSeq < 0) throw new LabDataError('The addressed run has no ledger events.');
      if (requestedCursor !== null && requestedCursor > headSeq) {
        throw new LabDataError(`Requested cursor ${requestedCursor} exceeds HEAD ${headSeq}.`);
      }
      const cursor = requestedCursor === null ? headSeq : requestedCursor;
      const [cursorEnvelope, eventEnvelope] = await Promise.all([
        cursor === headSeq
          ? Promise.resolve(headEnvelope)
          : fetchJson(this.worldRoute(cursor), batchSignal, this.requestTimeoutMs)
            .then(value => requireWorldEnvelope(value, this.runId)),
        fetchJson(this.eventsRoute(headSeq), batchSignal, this.requestTimeoutMs)
          .then(value => requireEventEnvelope(value, this.runId)),
      ]);
      this.headEnvelope = headEnvelope;
      this.eventEnvelope = eventEnvelope;
      this.integrityEnvelope = integrityEnvelope;
      return buildScene(this.runId, headEnvelope, cursorEnvelope, eventEnvelope, integrityEnvelope);
    } catch (error) {
      batchController.abort();
      throw error;
    }
  }

  async seek(cursor, signal = undefined) {
    if (!this.headEnvelope || !this.eventEnvelope) {
      throw new LabDataError('Load the scene before seeking.');
    }
    const headSeq = asInteger(this.headEnvelope.head_seq);
    const boundedCursor = Math.max(0, Math.min(asInteger(cursor, headSeq), headSeq));
    const cursorEnvelope = boundedCursor === headSeq
      ? this.headEnvelope
      : requireWorldEnvelope(
        await fetchJson(this.worldRoute(boundedCursor), signal, this.requestTimeoutMs),
        this.runId,
      );
    return buildScene(
      this.runId,
      this.headEnvelope,
      cursorEnvelope,
      this.eventEnvelope,
      this.integrityEnvelope,
    );
  }
}

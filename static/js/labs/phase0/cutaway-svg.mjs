import { safeText } from './study-scene.mjs';

const SVG_NS = document.getElementById('cutaway-svg').namespaceURI;

export const ZONES = Object.freeze([
  { id: 'control', label: 'CONTROL NEST', sub: 'agents / plans', color: '#c9f65a', x: 24, y: 48 },
  { id: 'context_assembly', label: 'CONTEXT ASSEMBLY', sub: 'prompt / budget', color: '#61e6c2', x: 319, y: 48 },
  { id: 'model_engine', label: 'MODEL ENGINE', sub: 'request / response', color: '#71a7ff', x: 614, y: 48 },
  { id: 'tool_workshop', label: 'TOOL WORKSHOP', sub: 'execute / retry', color: '#ff9c60', x: 909, y: 48 },
  { id: 'retrieval_depot', label: 'RETRIEVAL DEPOT', sub: 'search / select', color: '#62c8ff', x: 24, y: 265 },
  { id: 'memory_vault', label: 'MEMORY VAULT', sub: 'layers / writes', color: '#bd91ff', x: 319, y: 265 },
  { id: 'compaction_plant', label: 'COMPACTION PLANT', sub: 'replace / lineage', color: '#ffca68', x: 614, y: 265 },
  { id: 'handoff_bridge', label: 'HANDOFF BRIDGE', sub: 'delegate / own', color: '#65dda6', x: 909, y: 265 },
  { id: 'checkpoint_station', label: 'CHECKPOINT STATION', sub: 'snapshot / restore', color: '#98b6ff', x: 24, y: 482 },
  { id: 'artifact_foundry', label: 'ARTIFACT FOUNDRY', sub: 'files / reports', color: '#e8c379', x: 319, y: 482 },
  { id: 'incident_bay', label: 'INCIDENT BAY', sub: 'error / recovery', color: '#ff725f', x: 614, y: 482 },
  { id: 'unknown_fog', label: 'UNKNOWN FOG', sub: 'unmapped remains visible', color: '#8da195', x: 909, y: 482 },
]);

const ZONE_BY_ID = new Map(ZONES.map(zone => [zone.id, zone]));
const CHAMBER_WIDTH = 267;
const CHAMBER_HEIGHT = 174;

function svgElement(name, attributes = {}) {
  const node = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) {
    node.setAttribute(key, String(value));
  }
  return node;
}

function svgText(value, attributes = {}) {
  const node = svgElement('text', attributes);
  node.textContent = safeText(value, 'UNKNOWN', 120);
  return node;
}

function appendMachineGlyph(group, zone) {
  const glyph = svgElement('g', {
    transform: `translate(${zone.x + 214} ${zone.y + 111})`,
    'aria-hidden': 'true',
  });
  glyph.append(
    svgElement('rect', { class: 'zone-machine-fill', x: 0, y: 0, width: 34, height: 30, rx: 2 }),
    svgElement('path', { class: 'zone-machine-line', d: 'M4 6h25M4 12h17M4 24h7m6 0h12' }),
    svgElement('circle', { class: 'zone-machine-line', cx: 27, cy: 18, r: 4 }),
  );
  group.append(glyph);
}

function appendChamber(group, zone, scene, index) {
  const active = scene.currentZone === zone.id;
  const entityCount = scene.zoneCounts[zone.id] || 0;
  const eventCount = scene.zoneEventCounts[zone.id] || 0;
  group.style.setProperty('--zone-accent', zone.color);

  group.append(
    svgElement('rect', {
      class: 'chamber-shadow',
      x: zone.x + 9,
      y: zone.y + 10,
      width: CHAMBER_WIDTH,
      height: CHAMBER_HEIGHT,
      rx: 2,
    }),
    svgElement('polygon', {
      class: 'chamber-slab',
      points: `${zone.x},${zone.y} ${zone.x + 12},${zone.y - 11} ${zone.x + CHAMBER_WIDTH + 12},${zone.y - 11} ${zone.x + CHAMBER_WIDTH},${zone.y}`,
    }),
    svgElement('polygon', {
      class: 'chamber-wall',
      points: `${zone.x + CHAMBER_WIDTH},${zone.y} ${zone.x + CHAMBER_WIDTH + 12},${zone.y - 11} ${zone.x + CHAMBER_WIDTH + 12},${zone.y + CHAMBER_HEIGHT - 11} ${zone.x + CHAMBER_WIDTH},${zone.y + CHAMBER_HEIGHT}`,
    }),
    svgElement('rect', {
      class: `chamber-face${active ? ' is-active' : ''}`,
      x: zone.x,
      y: zone.y,
      width: CHAMBER_WIDTH,
      height: CHAMBER_HEIGHT,
      rx: 2,
    }),
    svgElement('rect', {
      class: 'chamber-window',
      x: zone.x + 12,
      y: zone.y + 43,
      width: CHAMBER_WIDTH - 24,
      height: CHAMBER_HEIGHT - 57,
      rx: 1,
    }),
    svgText(String(index + 1).padStart(2, '0'), {
      class: 'chamber-id',
      x: zone.x + 12,
      y: zone.y + 19,
    }),
    svgText(zone.label, {
      class: 'chamber-label',
      x: zone.x + 38,
      y: zone.y + 19,
    }),
    svgText(`${entityCount} OBJ · ${eventCount} EVT`, {
      class: 'chamber-count',
      x: zone.x + CHAMBER_WIDTH - 12,
      y: zone.y + 19,
      'text-anchor': 'end',
    }),
    svgText(zone.sub, {
      class: 'chamber-id',
      x: zone.x + 38,
      y: zone.y + 34,
    }),
  );

  const floor = svgElement('path', {
    class: 'zone-glyph',
    d: `M${zone.x + 12} ${zone.y + CHAMBER_HEIGHT - 18}H${zone.x + CHAMBER_WIDTH - 12}`,
  });
  group.append(floor);
  appendMachineGlyph(group, zone);

  if (zone.id === 'unknown_fog') {
    group.append(svgElement('rect', {
      class: 'unknown-hatch',
      x: zone.x + 12,
      y: zone.y + 43,
      width: CHAMBER_WIDTH - 24,
      height: CHAMBER_HEIGHT - 57,
      fill: 'url(#lab-unknown-hatch)',
    }));
  }

  if (active) {
    group.append(svgElement('path', {
      class: 'zone-glyph',
      d: `M${zone.x + 5} ${zone.y + 5}h10M${zone.x + 5} ${zone.y + 5}v10M${zone.x + CHAMBER_WIDTH - 5} ${zone.y + 5}h-10M${zone.x + CHAMBER_WIDTH - 5} ${zone.y + 5}v10`,
    }));
  }
}

function buildDefinitions() {
  const definitions = svgElement('defs');
  const hatch = svgElement('pattern', {
    id: 'lab-unknown-hatch',
    width: 12,
    height: 12,
    patternUnits: 'userSpaceOnUse',
    patternTransform: 'rotate(35)',
  });
  hatch.append(svgElement('rect', { width: 3, height: 12, fill: '#8da195' }));
  const glow = svgElement('filter', { id: 'lab-soft-glow', x: '-30%', y: '-30%', width: '160%', height: '160%' });
  glow.append(svgElement('feGaussianBlur', { stdDeviation: 4, result: 'blur' }));
  const gradient = svgElement('linearGradient', { id: 'lab-earth', x1: 0, y1: 0, x2: 0, y2: 1 });
  gradient.append(
    svgElement('stop', { offset: '0%', 'stop-color': '#1a261e' }),
    svgElement('stop', { offset: '100%', 'stop-color': '#0e1511' }),
  );
  definitions.append(hatch, glow, gradient);
  return definitions;
}

function buildBackdrop() {
  const group = svgElement('g', { 'aria-hidden': 'true' });
  group.append(svgElement('rect', {
    class: 'strata-back',
    x: 8,
    y: 27,
    width: 1184,
    height: 649,
    rx: 2,
    fill: 'url(#lab-earth)',
  }));
  for (const y of [246, 463]) {
    group.append(svgElement('path', {
      class: 'strata-line',
      d: `M13 ${y}C180 ${y - 16} 309 ${y + 13} 482 ${y - 2}S830 ${y + 13} 1187 ${y - 4}`,
    }));
  }
  return group;
}

function buildSequenceRail() {
  const group = svgElement('g', { 'aria-hidden': 'true' });
  const centers = ZONES.map(zone => [zone.x + CHAMBER_WIDTH / 2, zone.y + CHAMBER_HEIGHT / 2]);
  const rowPath = [0, 1, 2].map(row => {
    const points = centers.slice(row * 4, row * 4 + 4);
    return `M${points[0][0]} ${points[0][1]}H${points[3][0]}`;
  });
  group.append(svgElement('path', { class: 'sequence-rail', d: rowPath.join(' ') }));
  for (const [x, y] of centers) {
    group.append(svgElement('circle', { class: 'sequence-node', cx: x, cy: y, r: 3 }));
  }
  return group;
}

export function renderCutaway(svgRoot, scene) {
  const fragment = document.createDocumentFragment();
  fragment.append(buildDefinitions(), buildBackdrop(), buildSequenceRail());
  ZONES.forEach((zone, index) => {
    const group = svgElement('g', {
      'data-zone-id': zone.id,
      'aria-label': `${zone.label}; ${scene.zoneCounts[zone.id] || 0} entities; ${scene.zoneEventCounts[zone.id] || 0} events`,
    });
    appendChamber(group, zone, scene, index);
    fragment.append(group);
  });
  svgRoot.replaceChildren(fragment);
}

function figureFor(entity) {
  const figure = document.createElement('span');
  const isAgent = entity.kind.toLowerCase().includes('agent');
  figure.className = `entity-figure ${isAgent ? 'agent' : 'machine'}`;
  figure.setAttribute('aria-hidden', 'true');
  figure.append(document.createElement('span'));
  return figure;
}

function entityPosition(zone, slot) {
  const column = slot % 2;
  const row = Math.floor(slot / 2);
  return {
    left: ((zone.x + 17 + column * 126) / 1200) * 100,
    top: ((zone.y + 55 + row * 60) / 700) * 100,
  };
}

export function renderEntities(container, scene, onSelect, selectedEntityId = '') {
  const fragment = document.createDocumentFragment();
  const zoneSlots = new Map();

  for (const entity of scene.entities) {
    const zone = ZONE_BY_ID.get(entity.zone) || ZONE_BY_ID.get('unknown_fog');
    const slot = zoneSlots.get(zone.id) || 0;
    zoneSlots.set(zone.id, slot + 1);
    const position = entityPosition(zone, slot);

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'lab-entity';
    button.dataset.entityId = entity.id;
    button.dataset.truth = entity.truth.level;
    button.dataset.active = String(entity.active);
    button.setAttribute('aria-pressed', String(entity.id === selectedEntityId));
    button.setAttribute(
      'aria-label',
      `${entity.name}; ${entity.kind}; ${entity.status}; ${entity.truth.level} evidence; ${entity.eventCount} ledger events; open evidence`,
    );
    button.style.left = `${position.left}%`;
    button.style.top = `${position.top}%`;
    button.style.setProperty('--entity-accent', zone.color);

    const name = document.createElement('span');
    name.className = 'entity-name';
    name.textContent = entity.name;
    const meta = document.createElement('span');
    meta.className = 'entity-meta';
    meta.textContent = `${entity.status} · ${entity.truth.level}`;
    button.append(figureFor(entity), name, meta);
    button.addEventListener('click', () => onSelect(entity));
    fragment.append(button);
  }

  container.replaceChildren(fragment);
}

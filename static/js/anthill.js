(() => {
    'use strict';

    const API = '/api/anthill';
    const STATIC_CAPTURE = new URLSearchParams(window.location.search).has('static');
    const TERMINAL_RUN_STATUSES = new Set(['completed', 'failed', 'interrupted', 'cancelled']);
    const RUN_LIFECYCLE_EVENT_TYPES = new Set([
        'run.started', 'run.resumed', 'run.forked', 'run.paused',
        'run.completed', 'run.cancelled', 'error.fatal',
    ]);
    const W = 1120;
    const H = 660;
    const TRUTH_COLORS = {
        observed: '#5ce0ce',
        declared: '#74a8ff',
        inferred: '#ffb45f',
        counterfactual_verified: '#ff6f91',
    };

    const ZONES = [
        { key: 'control', label: 'CONTROL NEST', sub: 'agents / plans / decisions', x: 26, y: 64, w: 242, h: 140, color: '#c8f560' },
        { key: 'context_assembly', label: 'CONTEXT ASSEMBLY', sub: 'prompt manifest / budget', x: 300, y: 64, w: 242, h: 140, color: '#5ce0ce' },
        { key: 'model_engine', label: 'MODEL ENGINE', sub: 'request / stream / usage', x: 574, y: 64, w: 242, h: 140, color: '#74a8ff' },
        { key: 'meter_room', label: 'METER ROOM', sub: 'tokens / scoped time / cost', x: 848, y: 64, w: 242, h: 140, color: '#f5d060' },
        { key: 'tool_workshop', label: 'TOOL WORKSHOP', sub: 'approval / execute / retry', x: 26, y: 236, w: 242, h: 140, color: '#ff9f57' },
        { key: 'retrieval_depot', label: 'RETRIEVAL DEPOT', sub: 'search / rank / select', x: 300, y: 236, w: 242, h: 140, color: '#66c7ff' },
        { key: 'memory_vault', label: 'MEMORY VAULT', sub: 'working / episodic / semantic', x: 574, y: 236, w: 242, h: 140, color: '#c692ff' },
        { key: 'compaction_plant', label: 'COMPACTION PLANT', sub: 'keep / replace / lineage', x: 848, y: 236, w: 242, h: 140, color: '#ffb45f' },
        { key: 'handoff_bridge', label: 'HANDOFF BRIDGE', sub: 'delegation / ownership', x: 26, y: 408, w: 242, h: 140, color: '#58d8a3' },
        { key: 'checkpoint_station', label: 'CHECKPOINT STATION', sub: 'snapshot / fork / restore', x: 300, y: 408, w: 242, h: 140, color: '#98b6ff' },
        { key: 'artifact_foundry', label: 'ARTIFACT FOUNDRY', sub: 'files / reports / outputs', x: 574, y: 408, w: 242, h: 140, color: '#e8c379' },
        { key: 'incident_bay', label: 'INCIDENT BAY', sub: 'error / timeout / recovery', x: 848, y: 408, w: 242, h: 140, color: '#ff5c57' },
    ];
    const ZONE_MAP = Object.fromEntries(ZONES.map(zone => [zone.key, zone]));
    ZONE_MAP.code_archive = { key: 'code_archive', label: 'SOURCE ARCHIVE', x: 34, y: 584, w: 330, h: 40, color: '#789489' };
    ZONE_MAP.inspection_gate = { key: 'inspection_gate', label: 'QUALITY GATE', x: 395, y: 584, w: 330, h: 40, color: '#ff6f91' };
    ZONE_MAP.unknown_fog = { key: 'unknown_fog', label: 'UNKNOWN FOG', x: 756, y: 584, w: 330, h: 40, color: '#49655b' };

    const $ = id => document.getElementById(id);
    const esc = value => String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
    const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
    const humanNumber = value => {
        if (value == null || Number.isNaN(Number(value))) return '—';
        const number = Number(value);
        if (Math.abs(number) >= 1_000_000) return `${(number / 1_000_000).toFixed(1)}m`;
        if (Math.abs(number) >= 1_000) return `${(number / 1_000).toFixed(1)}k`;
        return Number.isInteger(number) ? String(number) : number.toFixed(2);
    };
    const METER_DEFINITIONS = [
        { id: 'input', label: 'INPUT', key: 'model_call.input_tokens' },
        { id: 'output', label: 'OUTPUT', key: 'model_call.output_tokens' },
        { id: 'total', label: 'CALCULATED TOTAL', key: 'model_call.total_tokens', calculated: true },
        { id: 'model', label: 'MODEL SPAN TIME', key: 'model_call.duration_ms' },
        { id: 'run', label: 'RUN ELAPSED', key: 'run.elapsed_ms' },
        { id: 'cost', label: 'COST', key: 'model_call.cost_usd' },
    ];
    const isSafeMeasurementValue = value => (
        typeof value === 'number' && Number.isFinite(value) && value >= 0
    );
    const formatMeasurementNumber = value => {
        const number = Number(value);
        if (Number.isInteger(number)) return number.toLocaleString('en-US');
        return number.toLocaleString('en-US', { maximumFractionDigits: 4 });
    };
    const formatDuration = value => {
        const milliseconds = Number(value);
        if (milliseconds < 1_000) return `${formatMeasurementNumber(milliseconds)} MS`;
        if (milliseconds < 60_000) return `${formatMeasurementNumber(milliseconds / 1_000)} S`;
        return `${formatMeasurementNumber(milliseconds / 60_000)} MIN`;
    };
    const formatCost = value => {
        const cost = Number(value);
        const maximumFractionDigits = cost > 0 && cost < .01 ? 6 : 4;
        return `$${cost.toLocaleString('en-US', { maximumFractionDigits })}`;
    };
    const formatMeasurementValue = reading => {
        if (reading.status === 'ambiguous') return 'AMBIGUOUS';
        if (reading.status !== 'available') return 'NOT OBSERVED';
        if (reading.unit === 'tokens') return `${formatMeasurementNumber(reading.value)} TOKENS`;
        if (reading.unit === 'ms') return formatDuration(reading.value);
        if (reading.unit === 'usd') return formatCost(reading.value);
        return formatMeasurementNumber(reading.value);
    };
    const aggregateEvidenceSummary = aggregate => {
        const parts = Object.entries(aggregate?.evidence_counts || {})
            .filter(([, count]) => Number(count) > 0)
            .sort(([left], [right]) => left.localeCompare(right, 'en-US'))
            .map(([level, count]) => `${String(level).toUpperCase()} ${count}`);
        return parts.join(' + ') || 'EVIDENCE LEVEL NOT OBSERVED';
    };
    const measurementReading = (world, definition) => {
        const source = definition.calculated
            ? world?.calculated_measurements?.[definition.key]
            : world?.measurement_aggregates?.[definition.key];
        const status = source?.status === 'ambiguous'
            ? 'ambiguous'
            : source?.status === 'available' && isSafeMeasurementValue(source.value)
                ? 'available'
                : 'not_observed';
        const basisValues = Array.isArray(source?.basis_values)
            ? source.basis_values.filter(value => typeof value === 'string' && value)
            : [];
        const estimatedValues = Array.isArray(source?.estimated_values)
            ? source.estimated_values.filter(value => typeof value === 'boolean')
            : [];
        const costKind = definition.id !== 'cost' || status !== 'available'
            ? ''
            : estimatedValues.length === 1 && estimatedValues[0] === true
                ? 'ESTIMATED'
                : estimatedValues.length === 1 && estimatedValues[0] === false
                    ? 'MEASURED'
                    : 'ESTIMATE STATUS MIXED';
        const evidenceIds = Array.isArray(source?.evidence_event_ids)
            ? source.evidence_event_ids.filter(value => typeof value === 'string' && value)
            : [];
        const eventId = evidenceIds.at(-1) || source?.last_event_id || '';
        const reading = {
            ...definition,
            status,
            value: status === 'available' ? source.value : null,
            unit: source?.unit || (definition.id === 'cost' ? 'usd' : definition.id === 'model' || definition.id === 'run' ? 'ms' : 'tokens'),
            source,
            eventId,
            basisValues,
            costKind,
            evidenceSummary: definition.calculated
                ? `${evidenceIds.length} COMPONENT EVENT${evidenceIds.length === 1 ? '' : 'S'}`
                : aggregateEvidenceSummary(source),
        };
        reading.valueText = formatMeasurementValue(reading);
        const details = [];
        if (status === 'available') {
            if (definition.calculated) {
                details.push(String(source?.calculation || 'INPUT + OUTPUT')
                    .replaceAll('_', ' ').replaceAll('.', ' ').toUpperCase());
                details.push(`EXPLICIT ${String(source?.explicit_consistency || 'NOT OBSERVED').replaceAll('_', ' ').toUpperCase()}`);
            } else {
                details.push(`${String(source?.scope || 'UNKNOWN SCOPE').replaceAll('_', ' ').toUpperCase()} · ${String(source?.aggregation || 'UNKNOWN AGGREGATION').toUpperCase()}`);
                details.push(`${Number(source?.sample_count || 0)} SAMPLE${Number(source?.sample_count || 0) === 1 ? '' : 'S'} · ${Number(source?.owner_count || 0)} OWNER${Number(source?.owner_count || 0) === 1 ? '' : 'S'}`);
            }
            if (definition.id === 'cost') {
                details.push(costKind);
                details.push(`BASIS ${basisValues.join(' + ') || 'NOT OBSERVED'}`);
            }
            details.push(reading.evidenceSummary);
        } else if (status === 'ambiguous') {
            const conflicts = Array.isArray(source?.conflict_reasons) ? source.conflict_reasons : [];
            details.push(conflicts.length ? conflicts.join(' · ') : 'SAFE AGGREGATE CONFLICT');
            details.push(reading.evidenceSummary);
        } else {
            details.push('SAFE AGGREGATE NOT OBSERVED AT CURSOR');
        }
        reading.detailText = details.filter(Boolean).join(' · ');
        return reading;
    };
    const buildMeterPresentation = world => {
        const readings = METER_DEFINITIONS.map(definition => measurementReading(world, definition));
        const evidenceLevels = [...new Set(readings.flatMap(reading => (
            Object.keys(reading.source?.evidence_counts || {})
        )))];
        return {
            readings,
            byId: Object.fromEntries(readings.map(reading => [reading.id, reading])),
            availableCount: readings.filter(reading => reading.status === 'available').length,
            ambiguousCount: readings.filter(reading => reading.status === 'ambiguous').length,
            truthLevel: evidenceLevels.length === 1
                ? evidenceLevels[0] : evidenceLevels.length > 1 ? 'mixed' : 'not_observed',
        };
    };
    const truthColor = level => TRUTH_COLORS[level] || '#789489';
    const shortId = value => value ? (value.length > 19 ? `${value.slice(0, 8)}…${value.slice(-7)}` : value) : '—';
    const DISPLAY_CONTROL_PATTERN = /[\u0000-\u001f\u007f-\u009f\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]/gu;
    const textField = (value, maxLength = 160) => {
        if (typeof value !== 'string') return '';
        const cleaned = value
            .replace(DISPLAY_CONTROL_PATTERN, ' ')
            .replace(/\u00b7/gu, '\u2219')
            .replace(/\s+/gu, ' ')
            .trim();
        if (cleaned.length <= maxLength) return cleaned;
        return `${cleaned.slice(0, Math.max(0, maxLength - 1))}\u2026`;
    };
    const runIdField = value => typeof value === 'string' ? value : '';
    const identityField = value => {
        if (typeof value !== 'string') return '';
        return value
            .replaceAll('\\', '\\\\')
            .replace(DISPLAY_CONTROL_PATTERN, character => (
                `\\u${character.codePointAt(0).toString(16).padStart(4, '0')}`
            ))
            .replace(/\u00b7/gu, '\\u00b7');
    };
    const buildRunIdLabels = runs => {
        const shortCounts = new Map();
        (runs || []).forEach(run => {
            const runId = runIdField(run?.run_id);
            if (!runId) return;
            const label = shortId(runId);
            shortCounts.set(label, (shortCounts.get(label) || 0) + 1);
        });
        return new Map((runs || []).flatMap(run => {
            const runId = runIdField(run?.run_id);
            if (!runId) return [];
            const label = shortId(runId);
            return [[runId, shortCounts.get(label) > 1 ? runId : label]];
        }));
    };
    const formatIngestTime = value => {
        const timestamp = textField(value, 64);
        const match = timestamp.match(
            /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,9})?(?:Z|[+-](\d{2}):(\d{2}))$/i,
        );
        if (!match) return 'UNKNOWN';
        const [year, month, day, hour, minute, second] = match
            .slice(1, 7).map(Number);
        const leapYear = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
        const monthDays = [31, leapYear ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
        const invalidCalendar = year < 1
            || month < 1 || month > 12
            || day < 1 || day > monthDays[month - 1]
            || hour > 23 || minute > 59 || second > 59
            || Number(match[7] || 0) > 23
            || Number(match[8] || 0) > 59;
        if (invalidCalendar) return 'UNKNOWN';
        const date = new Date(timestamp);
        if (Number.isNaN(date.getTime())) return 'UNKNOWN';
        const pad = number => String(number).padStart(2, '0');
        return [
            String(date.getUTCFullYear()).padStart(4, '0'),
            '-',
            pad(date.getUTCMonth() + 1),
            '-',
            pad(date.getUTCDate()),
            ' ',
            pad(date.getUTCHours()),
            ':',
            pad(date.getUTCMinutes()),
            'Z',
        ].join('');
    };
    const formatRunTitle = (run, runIdLabel = '') => {
        const runId = runIdField(run?.run_id);
        const id = runId ? identityField(runIdLabel || shortId(runId)) : 'UNKNOWN';
        const titleField = textField(run?.title, 120);
        return titleField && titleField !== textField(runId, 120)
            ? titleField
            : id;
    };
    const formatRunOption = (run, runIdLabel = '', stale = false) => {
        const title = formatRunTitle(run, runIdLabel);
        const source = textField(run?.source_adapter, 100) || 'UNKNOWN';
        const status = textField(run?.run_status, 32).toUpperCase() || 'UNKNOWN';
        const marker = run?.synthetic === true ? '[DEMO] ' : '';
        const staleMarker = stale ? '[STALE] ' : '';
        const id = identityField(runIdLabel || shortId(runIdField(run?.run_id))) || 'UNKNOWN';
        return `${staleMarker}${marker}${title} · SRC ${source} · ${status} · INGEST ${formatIngestTime(run?.created_at)} · ID ${id}`;
    };
    const eventFamily = type => String(type || '').split('.')[0];
    const importRunId = prefix => {
        const uuid = globalThis.crypto?.randomUUID?.();
        const token = uuid
            ? uuid.replaceAll('-', '')
            : `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`;
        return `${prefix}_${token}`;
    };

    function hashString(value) {
        let hash = 2166136261;
        for (let index = 0; index < value.length; index += 1) {
            hash ^= value.charCodeAt(index);
            hash = Math.imul(hash, 16777619);
        }
        return hash >>> 0;
    }

    class AnthillCanvas {
        constructor(canvas, callbacks = {}) {
            this.canvas = canvas;
            this.ctx = canvas.getContext('2d', { alpha: false });
            this.ctx.imageSmoothingEnabled = false;
            this.callbacks = callbacks;
            this.world = null;
            this.meterPresentation = buildMeterPresentation(null);
            this.entities = new Map();
            this.hitRegions = [];
            this.hovered = null;
            this.selectedEventId = null;
            this.lastFrame = performance.now();
            this.frameRequest = null;
            this.systemMotionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');
            this.motionMode = this.loadMotionMode();
            this.reducedMotion = false;
            this.systemMotionPreference.addEventListener('change', () => {
                if (this.motionMode === 'system') this.applyMotionPreference();
            });
            this.canvas.addEventListener('mousemove', event => this.onPointerMove(event));
            this.canvas.addEventListener('mouseleave', () => this.clearHover());
            this.canvas.addEventListener('click', event => this.onClick(event));
            this.applyMotionPreference();
        }

        setWorld(world) {
            this.world = world || null;
            this.meterPresentation = buildMeterPresentation(this.world);
            if (!world) return;
            const nextIds = new Set(Object.keys(world.entities || {}));
            for (const [id] of this.entities) {
                if (!nextIds.has(id)) this.entities.delete(id);
            }
            for (const entity of Object.values(world.entities || {})) {
                const zone = ZONE_MAP[entity.zone] || ZONE_MAP.unknown_fog;
                const seed = hashString(entity.id);
                const paddingX = zone.w > 100 ? 38 : 16;
                const paddingY = zone.h > 80 ? 52 : 12;
                const targetX = zone.x + paddingX + (seed % Math.max(zone.w - paddingX * 2, 1));
                const targetY = zone.y + paddingY + ((seed >>> 8) % Math.max(zone.h - paddingY - 15, 1));
                const sprite = this.entities.get(entity.id) || {
                    x: targetX,
                    y: targetY,
                    bob: (seed % 100) / 100 * Math.PI * 2,
                };
                sprite.entity = entity;
                sprite.targetX = targetX;
                sprite.targetY = targetY;
                this.entities.set(entity.id, sprite);
            }
            this.syncAnimation();
        }

        setSelected(eventId) {
            this.selectedEventId = eventId;
            this.requestDraw();
        }

        loadMotionMode() {
            try {
                const stored = localStorage.getItem('anthill.motion.v1');
                return ['system', 'reduce', 'full'].includes(stored) ? stored : 'system';
            } catch (_) {
                return 'system';
            }
        }

        setMotionMode(mode) {
            this.motionMode = ['system', 'reduce', 'full'].includes(mode) ? mode : 'system';
            try { localStorage.setItem('anthill.motion.v1', this.motionMode); } catch (_) { /* optional */ }
            this.applyMotionPreference();
            return this.reducedMotion ? 'reduce' : 'full';
        }

        applyMotionPreference() {
            this.reducedMotion = this.motionMode === 'reduce'
                || (this.motionMode === 'system' && this.systemMotionPreference.matches);
            document.body.dataset.motionPreference = this.motionMode;
            document.body.dataset.effectiveMotion = this.reducedMotion ? 'reduce' : 'full';
            this.syncAnimation();
        }

        isTerminalWorld() {
            return TERMINAL_RUN_STATUSES.has(this.world?.run_status);
        }

        shouldAnimate() {
            return !STATIC_CAPTURE && !this.reducedMotion && this.world != null && !this.isTerminalWorld();
        }

        redraw() {
            this.draw(0, 1);
        }

        requestDraw() {
            if (this.frameRequest == null) this.redraw();
        }

        syncAnimation() {
            if (!this.shouldAnimate()) {
                if (this.frameRequest != null) cancelAnimationFrame(this.frameRequest);
                this.frameRequest = null;
                this.redraw();
                return;
            }
            if (this.frameRequest == null) {
                this.lastFrame = performance.now();
                this.frameRequest = requestAnimationFrame(time => this.frame(time));
            }
        }

        frame(time) {
            this.frameRequest = null;
            if (!this.shouldAnimate()) {
                this.redraw();
                return;
            }
            const delta = Math.min((time - this.lastFrame) / 16.67, 3);
            this.lastFrame = time;
            this.draw(time, delta);
            this.frameRequest = requestAnimationFrame(next => this.frame(next));
        }

        draw(time, delta) {
            const ctx = this.ctx;
            ctx.imageSmoothingEnabled = false;
            ctx.fillStyle = '#07100f';
            ctx.fillRect(0, 0, W, H);
            this.drawRock(ctx);
            this.drawTunnels(ctx);
            this.hitRegions = [];
            for (const zone of ZONES) this.drawZone(ctx, zone, time);
            this.drawBottomArchive(ctx);
            this.drawCausalPackets(ctx, time);
            this.drawEntities(ctx, time, delta);
            this.drawScanline(ctx, time);
        }

        drawRock(ctx) {
            ctx.fillStyle = '#0a1512';
            for (let y = 0; y < H; y += 12) {
                for (let x = (y / 12 % 2) * 6; x < W; x += 18) {
                    const seed = (x * 31 + y * 17) % 13;
                    if (seed < 5) ctx.fillRect(x, y, seed % 2 ? 8 : 12, seed % 3 ? 3 : 5);
                }
            }
            ctx.fillStyle = '#0d1c17';
            ctx.fillRect(0, 39, W, 4);
            ctx.fillStyle = '#14261f';
            for (let x = 0; x < W; x += 22) ctx.fillRect(x, 35 + ((x / 22) % 2) * 4, 13, 4);
        }

        drawTunnels(ctx) {
            const links = [
                ['control', 'context_assembly'], ['context_assembly', 'model_engine'], ['model_engine', 'meter_room'],
                ['tool_workshop', 'retrieval_depot'], ['retrieval_depot', 'memory_vault'], ['memory_vault', 'compaction_plant'],
                ['handoff_bridge', 'checkpoint_station'], ['checkpoint_station', 'artifact_foundry'], ['artifact_foundry', 'incident_bay'],
                ['control', 'tool_workshop'], ['tool_workshop', 'handoff_bridge'],
                ['context_assembly', 'retrieval_depot'], ['retrieval_depot', 'checkpoint_station'],
                ['model_engine', 'memory_vault'], ['memory_vault', 'artifact_foundry'],
                ['meter_room', 'compaction_plant'], ['compaction_plant', 'incident_bay'],
            ];
            ctx.lineCap = 'butt';
            for (const [fromKey, toKey] of links) {
                const from = this.center(ZONE_MAP[fromKey]);
                const to = this.center(ZONE_MAP[toKey]);
                ctx.beginPath();
                ctx.moveTo(from.x, from.y);
                if (Math.abs(from.x - to.x) > Math.abs(from.y - to.y)) {
                    const mid = (from.x + to.x) / 2;
                    ctx.lineTo(mid, from.y); ctx.lineTo(mid, to.y);
                } else {
                    const mid = (from.y + to.y) / 2;
                    ctx.lineTo(from.x, mid); ctx.lineTo(to.x, mid);
                }
                ctx.lineTo(to.x, to.y);
                ctx.strokeStyle = '#020706';
                ctx.lineWidth = 16;
                ctx.stroke();
                ctx.strokeStyle = '#1b3129';
                ctx.lineWidth = 5;
                ctx.stroke();
                ctx.setLineDash([2, 6]);
                ctx.strokeStyle = '#355247';
                ctx.lineWidth = 1;
                ctx.stroke();
                ctx.setLineDash([]);
            }
        }

        drawZone(ctx, zone, time) {
            const state = this.world;
            const activity = state?.zone_activity?.[zone.key] || 0;
            const lastEvent = state?.zone_latest_events?.[zone.key]
                || [...(state?.recent_events || [])].reverse().find(event => event.zone === zone.key);
            const meterTruth = zone.key === 'meter_room' ? this.meterPresentation.truthLevel : null;
            const level = lastEvent?.truth?.level || meterTruth || 'not_observed';
            const confidence = lastEvent?.truth?.confidence ?? 0;
            const pulse = activity > 0 ? (Math.sin(time / 260) + 1) / 2 : 0;

            ctx.fillStyle = activity > 0 ? this.alpha(zone.color, .075 + pulse * .045) : '#0b1815';
            ctx.fillRect(zone.x, zone.y, zone.w, zone.h);
            this.truthStroke(ctx, level, zone.color, confidence, activity > 0, time);
            ctx.strokeRect(zone.x + .5, zone.y + .5, zone.w - 1, zone.h - 1);
            if (level === 'declared') ctx.strokeRect(zone.x + 4.5, zone.y + 4.5, zone.w - 9, zone.h - 9);
            ctx.setLineDash([]);
            ctx.shadowBlur = 0;

            ctx.fillStyle = '#07100f';
            ctx.fillRect(zone.x + 1, zone.y + 1, zone.w - 2, 30);
            ctx.fillStyle = zone.color;
            ctx.fillRect(zone.x + 8, zone.y + 8, 5, 13);
            ctx.font = 'bold 12px "Cascadia Mono", monospace';
            ctx.textBaseline = 'top';
            ctx.fillText(zone.label, zone.x + 19, zone.y + 4);
            ctx.fillStyle = '#58756a';
            ctx.font = '9px "Cascadia Mono", monospace';
            ctx.fillText(zone.sub.toUpperCase(), zone.x + 19, zone.y + 19);

            if (activity > 0) {
                ctx.fillStyle = zone.color;
                ctx.fillRect(zone.x + zone.w - 27, zone.y + 10, 5, 5);
                ctx.fillStyle = '#bed0c7';
                ctx.font = '10px "Cascadia Mono", monospace';
                ctx.fillText(String(activity), zone.x + zone.w - 17, zone.y + 6);
            }
            this.drawMachine(ctx, zone, time, activity);
            this.hitRegions.push({ type: 'zone', zone, x: zone.x, y: zone.y, w: zone.w, h: zone.h, eventId: lastEvent?.event_id });
        }

        drawMachine(ctx, zone, time, activity) {
            const x = zone.x + 18;
            const y = zone.y + 48;
            const color = zone.color;
            ctx.save();
            ctx.translate(x, y);
            ctx.fillStyle = '#132a23';
            ctx.strokeStyle = '#355247';
            ctx.lineWidth = 2;

            if (zone.key === 'control') {
                ctx.fillRect(28, 25, 145, 38); ctx.strokeRect(28.5, 25.5, 144, 37);
                ctx.fillStyle = '#1d3b31'; ctx.fillRect(40, 14, 35, 19); ctx.fillRect(125, 14, 35, 19);
                ctx.fillStyle = color; ctx.fillRect(47, 19, 20, 3); ctx.fillRect(132, 19, 20, 3);
                this.pixelBlink(ctx, 93, 37, color, time, 360);
            } else if (zone.key === 'context_assembly') {
                const context = this.world?.context || {};
                const ratio = clamp(context.utilization || 0, 0, 1);
                ctx.fillRect(25, 9, 168, 65); ctx.strokeRect(25.5, 9.5, 167, 64);
                ctx.fillStyle = '#07100f'; ctx.fillRect(39, 23, 140, 17);
                ctx.fillStyle = context.overflow ? '#ff5c57' : color; ctx.fillRect(40, 24, 138 * ratio, 15);
                ctx.fillStyle = '#58756a';
                for (let index = 0; index < 6; index += 1) ctx.fillRect(40 + index * 25, 51, 16, 8);
            } else if (zone.key === 'model_engine') {
                ctx.fillRect(55, 2, 104, 76); ctx.strokeRect(55.5, 2.5, 103, 75);
                ctx.fillStyle = '#07100f'; ctx.fillRect(71, 15, 72, 50);
                ctx.strokeStyle = color; ctx.lineWidth = 4;
                ctx.beginPath();
                for (let index = 0; index < 5; index += 1) {
                    const px = 78 + index * 14;
                    const py = 40 + Math.sin(time / 250 + index) * (activity ? 10 : 4);
                    index === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
                }
                ctx.stroke();
            } else if (zone.key === 'meter_room') {
                const meter = this.meterPresentation;
                const cells = [
                    [meter.byId.input, 27, 11], [meter.byId.model, 111, 11],
                    [meter.byId.output, 27, 32], [meter.byId.run, 111, 32],
                    [meter.byId.total, 27, 53], [meter.byId.cost, 111, 53],
                ];
                ctx.fillStyle = '#0b1815'; ctx.fillRect(23, 8, 171, 66);
                ctx.strokeStyle = '#355247';
                ctx.strokeRect(23.5, 8.5, 170, 65);
                ctx.fillStyle = '#1d352d';
                ctx.fillRect(104, 9, 1, 64);
                for (const [reading, cellX, cellY] of cells) {
                    const label = reading.id === 'total'
                        ? 'TOTAL · CALCULATED'
                        : reading.id === 'cost' && reading.costKind === 'ESTIMATED'
                            ? 'COST · ESTIMATED'
                            : reading.label;
                    ctx.fillStyle = reading.status === 'available'
                        ? color
                        : reading.status === 'ambiguous' ? '#ffb45f' : '#789489';
                    ctx.font = '8px "Cascadia Mono", monospace';
                    ctx.fillText(label, cellX, cellY);
                    ctx.fillStyle = reading.status === 'available' ? '#d6e3dc' : '#789489';
                    ctx.font = 'bold 10px "Cascadia Mono", monospace';
                    const canvasValue = reading.status === 'available'
                        ? (reading.unit === 'tokens' ? humanNumber(reading.value).toUpperCase() : reading.valueText)
                        : reading.valueText;
                    ctx.fillText(canvasValue, cellX, cellY + 8);
                }
            } else if (zone.key === 'tool_workshop') {
                ctx.fillRect(21, 48, 182, 23); ctx.strokeRect(21.5, 48.5, 181, 22);
                ctx.fillStyle = color; ctx.fillRect(55, 19, 12, 31); ctx.fillRect(46, 12, 31, 10);
                ctx.fillStyle = '#739084'; ctx.fillRect(137, 14, 9, 36); ctx.fillRect(125, 12, 33, 8);
                if (activity) ctx.fillStyle = Math.floor(time / 120) % 2 ? '#ffb45f' : '#ff5c57', ctx.fillRect(98, 39, 8, 8);
            } else if (zone.key === 'retrieval_depot') {
                for (let row = 0; row < 3; row += 1) {
                    ctx.fillStyle = '#172f28'; ctx.fillRect(24, 10 + row * 22, 166, 16);
                    for (let index = 0; index < 7; index += 1) {
                        ctx.fillStyle = ((row + index) % 3 === 0) ? color : '#38584d';
                        ctx.fillRect(30 + index * 22, 14 + row * 22, 13, 8);
                    }
                }
            } else if (zone.key === 'memory_vault') {
                const memory = this.world?.memory || {};
                const layers = ['working', 'episodic', 'semantic'];
                for (let index = 0; index < 3; index += 1) {
                    const observation = memory.layer_operations?.[layers[index]];
                    ctx.fillStyle = '#152c25'; ctx.fillRect(24 + index * 61, 13, 48, 59);
                    ctx.strokeStyle = color; ctx.strokeRect(24.5 + index * 61, 13.5, 47, 58);
                    ctx.fillStyle = observation ? color : '#789489';
                    ctx.font = 'bold 10px "Cascadia Mono", monospace';
                    ctx.fillText(observation ? `${observation.event_count} OPS` : 'N/O', 31 + index * 61, 38);
                }
            } else if (zone.key === 'compaction_plant') {
                const jobs = Object.values(this.world?.compactions || {});
                const job = jobs[jobs.length - 1];
                const moving = job && !['completed', 'failed'].includes(job.status);
                const press = moving ? Math.round((Math.sin(time / 160) + 1) * 9) : 4;
                ctx.fillRect(32, 3, 142, 73); ctx.strokeRect(32.5, 3.5, 141, 72);
                ctx.fillStyle = color; ctx.fillRect(69, 12 + press, 68, 9);
                ctx.fillStyle = '#355247'; ctx.fillRect(60, 50, 86, 13);
                ctx.fillStyle = '#07100f'; ctx.fillRect(74, 53, 58, 7);
                if (job?.reduction_ratio != null) {
                    ctx.fillStyle = color; ctx.font = '10px "Cascadia Mono", monospace';
                    ctx.fillText(`-${Math.round(job.reduction_ratio * 100)}%`, 177, 57);
                }
            } else if (zone.key === 'handoff_bridge') {
                ctx.fillStyle = '#1b352d'; ctx.fillRect(18, 39, 188, 14);
                ctx.fillStyle = color;
                for (let index = 0; index < 7; index += 1) ctx.fillRect(25 + index * 26, 35, 15, 22);
                const packet = (time / 9) % 170;
                ctx.fillStyle = '#d9e7dc'; ctx.fillRect(25 + packet, 40, 7, 7);
            } else if (zone.key === 'checkpoint_station') {
                ctx.fillRect(55, 2, 104, 76); ctx.strokeStyle = color; ctx.strokeRect(55.5, 2.5, 103, 75);
                ctx.fillStyle = '#07100f'; ctx.fillRect(72, 16, 70, 48);
                ctx.strokeStyle = color; ctx.beginPath(); ctx.arc(107, 40, 18, 0, Math.PI * 2); ctx.stroke();
                ctx.fillStyle = color; ctx.fillRect(104, 22, 6, 36); ctx.fillRect(89, 37, 36, 6);
            } else if (zone.key === 'artifact_foundry') {
                ctx.fillRect(22, 49, 179, 23); ctx.strokeRect(22.5, 49.5, 178, 22);
                ctx.fillStyle = '#5f4b2e'; ctx.fillRect(72, 13, 73, 39);
                ctx.fillStyle = color; ctx.fillRect(79, 20, 59, 5); ctx.fillRect(79, 31, 42, 4); ctx.fillRect(79, 41, 51, 4);
                if (activity) this.pixelBlink(ctx, 167, 24, '#ffcf6b', time, 110);
            } else if (zone.key === 'incident_bay') {
                const errors = (this.world?.errors || []).filter(error => error.status === 'open');
                ctx.fillStyle = errors.length ? '#351c19' : '#142a24'; ctx.fillRect(38, 7, 134, 67);
                ctx.strokeStyle = errors.length ? color : '#355247'; ctx.strokeRect(38.5, 7.5, 133, 66);
                ctx.fillStyle = errors.length ? color : '#527064';
                ctx.fillRect(96, 19, 18, 31); ctx.fillRect(96, 56, 18, 9);
                if (errors.length) this.pixelBlink(ctx, 187, 12, color, time, 240);
            }
            ctx.restore();
        }

        drawBottomArchive(ctx) {
            for (const key of ['code_archive', 'inspection_gate', 'unknown_fog']) {
                const zone = ZONE_MAP[key];
                ctx.fillStyle = key === 'unknown_fog' ? 'rgba(53,73,68,.18)' : '#0b1815';
                ctx.fillRect(zone.x, zone.y, zone.w, zone.h);
                ctx.strokeStyle = zone.color; ctx.setLineDash(key === 'unknown_fog' ? [2, 5] : []);
                ctx.strokeRect(zone.x + .5, zone.y + .5, zone.w - 1, zone.h - 1); ctx.setLineDash([]);
                ctx.fillStyle = zone.color; ctx.font = '11px "Cascadia Mono", monospace';
                ctx.fillText(zone.label, zone.x + 11, zone.y + 13);
                if (key === 'unknown_fog') {
                    const count = this.world?.unknown_event_types?.length || 0;
                    ctx.fillStyle = '#789489'; ctx.fillText(`${count} UNMAPPED TYPES`, zone.x + 176, zone.y + 13);
                }
                this.hitRegions.push({ type: 'zone', zone, x: zone.x, y: zone.y, w: zone.w, h: zone.h });
            }
        }

        drawCausalPackets(ctx, time) {
            if (!this.world) return;
            const recent = this.world.recent_events || [];
            const byId = new Map(recent.map(event => [event.event_id, event]));
            const edges = recent.slice(-22).map(event => {
                const cause = event.causation_id ? byId.get(event.causation_id) : null;
                return cause && cause.zone !== event.zone ? { from: cause, to: event } : null;
            }).filter(Boolean);
            edges.forEach((edge, index) => {
                const fromZone = ZONE_MAP[edge.from.zone] || ZONE_MAP.unknown_fog;
                const toZone = ZONE_MAP[edge.to.zone] || ZONE_MAP.unknown_fog;
                const from = this.center(fromZone);
                const to = this.center(toZone);
                const phase = this.shouldAnimate() ? ((time / 1150) + index * .17) % 1 : .55;
                const point = this.elbowPoint(from, to, phase);
                const level = edge.to.truth?.level || 'inferred';
                const color = truthColor(level);
                ctx.save();
                ctx.fillStyle = color;
                if (level === 'counterfactual_verified') { ctx.shadowColor = color; ctx.shadowBlur = 8; }
                ctx.fillRect(Math.round(point.x) - 3, Math.round(point.y) - 3, 7, 7);
                ctx.fillStyle = '#06100d'; ctx.fillRect(Math.round(point.x) - 1, Math.round(point.y) - 1, 3, 3);
                ctx.restore();
            });
        }

        drawEntities(ctx, time, delta) {
            const sprites = [...this.entities.values()].sort((a, b) => {
                const priority = this.entityPriority(a.entity) - this.entityPriority(b.entity);
                if (priority) return priority;
                const recency = Number(b.entity.last_seq || 0) - Number(a.entity.last_seq || 0);
                return recency || String(a.entity.id).localeCompare(String(b.entity.id), 'en-US');
            }).slice(0, 28);
            for (const sprite of sprites) {
                const smoothing = this.shouldAnimate() ? 1 - Math.pow(.84, delta) : 1;
                sprite.x += (sprite.targetX - sprite.x) * smoothing;
                sprite.y += (sprite.targetY - sprite.y) * smoothing;
                const bob = this.shouldAnimate() ? Math.round(Math.sin(time / 210 + sprite.bob)) : 0;
                const entity = sprite.entity;
                const color = truthColor(entity.truth?.level);
                const selected = entity.last_event_id === this.selectedEventId;
                const x = Math.round(sprite.x);
                const y = Math.round(sprite.y + bob);
                if (selected) {
                    ctx.strokeStyle = '#c8f560'; ctx.setLineDash([2, 2]);
                    ctx.strokeRect(x - 10.5, y - 12.5, 21, 25); ctx.setLineDash([]);
                }
                this.drawSprite(ctx, entity, x, y, color, time);
                const w = entity.kind === 'agent' ? 22 : 16;
                this.hitRegions.push({ type: 'entity', entity, x: x - w / 2, y: y - 12, w, h: 25, eventId: entity.last_event_id });
                if (entity.kind === 'agent') {
                    const label = entity.name.length > 16 ? `${entity.name.slice(0, 14)}…` : entity.name;
                    ctx.fillStyle = 'rgba(4,10,9,.88)'; ctx.fillRect(x - 3 - label.length * 3.1, y + 13, label.length * 6.2 + 6, 14);
                    ctx.fillStyle = entity.active ? '#c8f560' : '#a8beb4'; ctx.font = '9px "Cascadia Mono", monospace';
                    ctx.textAlign = 'center'; ctx.fillText(label, x, y + 15); ctx.textAlign = 'left';
                }
            }
        }

        drawSprite(ctx, entity, x, y, color, time) {
            ctx.save();
            const active = entity.active;
            if (entity.kind === 'agent') {
                ctx.fillStyle = '#07100f'; ctx.fillRect(x - 7, y - 6, 15, 12);
                ctx.fillStyle = color; ctx.fillRect(x - 5, y - 5, 11, 10); ctx.fillRect(x - 3, y - 10, 7, 5);
                ctx.fillStyle = '#d9e7dc'; ctx.fillRect(x - 2, y - 8, 2, 2); ctx.fillRect(x + 2, y - 8, 2, 2);
                ctx.fillStyle = color; ctx.fillRect(x - 9, y - 3, 4, 3); ctx.fillRect(x + 6, y - 3, 4, 3);
                ctx.fillRect(x - 6, y + 6, 3, 5); ctx.fillRect(x + 3, y + 6, 3, 5);
                if (active) this.pixelBlink(ctx, x + 9, y - 10, '#c8f560', time, 170);
            } else if (entity.kind === 'task') {
                ctx.fillStyle = '#5e472b'; ctx.fillRect(x - 7, y - 7, 15, 14);
                ctx.strokeStyle = color; ctx.strokeRect(x - 7.5, y - 7.5, 15, 14);
                ctx.fillStyle = color; ctx.fillRect(x - 5, y - 2, 11, 3);
            } else if (entity.kind.startsWith('memory')) {
                ctx.fillStyle = color; ctx.fillRect(x - 6, y - 6, 13, 13);
                ctx.fillStyle = '#07100f'; ctx.fillRect(x - 3, y - 3, 7, 7);
            } else if (entity.kind.startsWith('context')) {
                ctx.fillStyle = color; ctx.fillRect(x - 7, y - 4, 15, 9);
                ctx.fillStyle = '#07100f'; ctx.fillRect(x - 3, y - 1, 7, 3);
            } else if (entity.kind === 'artifact') {
                ctx.fillStyle = '#6b5433'; ctx.fillRect(x - 7, y - 8, 15, 16);
                ctx.fillStyle = color; ctx.fillRect(x - 5, y - 5, 11, 3); ctx.fillRect(x - 5, y, 8, 2);
            } else {
                ctx.fillStyle = color; ctx.fillRect(x - 6, y - 6, 13, 13);
                ctx.fillStyle = '#07100f'; ctx.fillRect(x - 2, y - 2, 5, 5);
            }
            ctx.restore();
        }

        drawScanline(ctx, time) {
            const y = Math.floor((time / 22) % H);
            ctx.fillStyle = 'rgba(200,245,96,.018)';
            ctx.fillRect(0, y, W, 2);
        }

        truthStroke(ctx, level, fallback, confidence, active, time) {
            const color = truthColor(level) || fallback;
            ctx.strokeStyle = color;
            ctx.lineWidth = level === 'counterfactual_verified' ? 2 : 1;
            ctx.globalAlpha = .35 + confidence * .55;
            ctx.setLineDash(
                level === 'inferred' ? [3, 5]
                    : level === 'mixed' ? [7, 3, 1, 3]
                        : level === 'not_observed' ? [1, 6] : [],
            );
            if (level === 'counterfactual_verified') {
                ctx.shadowColor = color; ctx.shadowBlur = 8 + Math.sin(time / 300) * 3;
            }
            if (active && level !== 'counterfactual_verified') {
                ctx.shadowColor = fallback; ctx.shadowBlur = 4;
            }
            ctx.globalAlpha = 1;
        }

        pixelBlink(ctx, x, y, color, time, speed) {
            if (Math.floor(time / speed) % 2 === 0) {
                ctx.fillStyle = color; ctx.fillRect(Math.round(x), Math.round(y), 5, 5);
            }
        }

        center(zone) { return { x: zone.x + zone.w / 2, y: zone.y + zone.h / 2 }; }

        elbowPoint(from, to, phase) {
            const horizontalFirst = Math.abs(from.x - to.x) > Math.abs(from.y - to.y);
            const middle = horizontalFirst ? { x: (from.x + to.x) / 2, y: from.y } : { x: from.x, y: (from.y + to.y) / 2 };
            const middle2 = horizontalFirst ? { x: middle.x, y: to.y } : { x: to.x, y: middle.y };
            const points = [from, middle, middle2, to];
            const lengths = points.slice(1).map((point, index) => Math.abs(point.x - points[index].x) + Math.abs(point.y - points[index].y));
            const total = lengths.reduce((sum, value) => sum + value, 0) || 1;
            let remaining = phase * total;
            for (let index = 0; index < lengths.length; index += 1) {
                if (remaining <= lengths[index]) {
                    const ratio = lengths[index] ? remaining / lengths[index] : 0;
                    return { x: points[index].x + (points[index + 1].x - points[index].x) * ratio, y: points[index].y + (points[index + 1].y - points[index].y) * ratio };
                }
                remaining -= lengths[index];
            }
            return to;
        }

        entityPriority(entity) {
            if (entity.last_event_id === this.selectedEventId) return -3;
            if (['error', 'failed', 'rejected', 'cancelled', 'timeout'].includes(entity.status)) return -2;
            if (['incident_bay', 'unknown_fog'].includes(entity.zone)) return -1;
            if (entity.active) return 0;
            if (entity.kind === 'agent') return 1;
            if (entity.kind === 'task') return 2;
            return 3;
        }

        alpha(hex, alpha) {
            const clean = hex.replace('#', '');
            const value = parseInt(clean, 16);
            return `rgba(${value >> 16},${(value >> 8) & 255},${value & 255},${alpha})`;
        }

        canvasPoint(event) {
            const rect = this.canvas.getBoundingClientRect();
            return { x: (event.clientX - rect.left) * W / rect.width, y: (event.clientY - rect.top) * H / rect.height };
        }

        regionAt(point) {
            return [...this.hitRegions].reverse().find(region => point.x >= region.x && point.x <= region.x + region.w && point.y >= region.y && point.y <= region.y + region.h);
        }

        onPointerMove(event) {
            const region = this.regionAt(this.canvasPoint(event));
            if (region === this.hovered) return;
            this.hovered = region;
            this.canvas.style.cursor = region ? 'pointer' : 'crosshair';
            if (!region) return this.clearHover();
            const rect = this.canvas.getBoundingClientRect();
            const tooltip = $('canvas-tooltip');
            const title = region.type === 'entity' ? region.entity.name : region.zone.label;
            const detail = region.type === 'entity'
                ? `${region.entity.kind} · ${region.entity.status} · ${region.entity.truth.level} ${(region.entity.truth.confidence * 100).toFixed(0)}%`
                : region.zone.key === 'meter_room'
                    ? `${this.meterPresentation.availableCount} available · ${this.meterPresentation.ambiguousCount} ambiguous · OBJECTS lists scoped evidence`
                : `${this.world?.zone_event_counts?.[region.zone.key] || 0} events · ${this.world?.zone_activity?.[region.zone.key] || 0} open · ${region.eventId ? 'click for evidence' : 'not observed'}`;
            tooltip.innerHTML = `<b>${esc(title)}</b><span>${esc(detail)}</span>`;
            tooltip.hidden = false;
            const left = clamp(event.clientX - rect.left + 14, 8, rect.width - 270);
            const top = clamp(event.clientY - rect.top + 14, 8, rect.height - 70);
            tooltip.style.left = `${left}px`;
            tooltip.style.top = `${top}px`;
            this.requestDraw();
        }

        clearHover() {
            this.hovered = null;
            $('canvas-tooltip').hidden = true;
            this.canvas.style.cursor = 'crosshair';
            this.requestDraw();
        }

        onClick(event) {
            const region = this.regionAt(this.canvasPoint(event));
            if (!region) return;
            if (region.eventId && this.callbacks.onEvent) this.callbacks.onEvent(region.eventId);
            else if (region.zone && this.callbacks.onZone) this.callbacks.onZone(region.zone.key);
        }
    }

    class AnthillApp {
        constructor() {
            this.runs = [];
            this.runIdLabels = new Map();
            this.staleRunIds = new Set();
            this.runId = null;
            this.manifest = null;
            this.committedSelection = null;
            this.worldResponse = null;
            this.world = null;
            this.events = [];
            this.eventsById = new Map();
            this.headSeq = -1;
            this.cursorSeq = -1;
            this.followLive = true;
            this.playTimer = null;
            this.eventSource = null;
            this.compareEventSource = null;
            this.worldRequest = null;
            this.selectedEventId = null;
            this.cursorEventId = null;
            this.causalDirection = 'ancestors';
            this.causalRequestId = 0;
            this.runRequestEpoch = 0;
            this.worldRequestId = 0;
            this.headRefreshTimer = null;
            this.manifestRefreshTimer = null;
            this.manifestRefreshController = null;
            this.manifestRefreshRequestId = 0;
            this.currentView = 'world';
            this.compareRunId = null;
            this.compareProgress = 1;
            this.compareData = null;
            this.compareRequestId = 0;
            this.compareRequestController = null;
            this.refreshTimer = null;
            this.lastAnnouncement = '';
            this.announcedRunStateKey = '';
            this.canvas = new AnthillCanvas($('anthill-canvas'), {
                onEvent: id => this.selectEvent(id),
                onZone: zone => this.selectZone(zone),
            });
            $('motion-preference').value = this.canvas.motionMode;
            this.bind();
            this.renderChamberList();
            this.loadRuns();
        }

        bind() {
            $('run-select').addEventListener('change', event => this.selectRun(event.target.value));
            $('demo-button').addEventListener('click', () => this.createDemo());
            $('empty-demo-button').addEventListener('click', () => this.createDemo());
            $('otlp-button').addEventListener('click', () => {
                $('import-menu').open = false;
                $('otlp-file').click();
            });
            $('empty-otlp-button').addEventListener('click', () => $('otlp-file').click());
            $('otlp-file').addEventListener('change', event => this.importOtlpFile(event.target.files?.[0]));
            $('agui-button').addEventListener('click', () => {
                $('import-menu').open = false;
                $('agui-file').click();
            });
            $('empty-agui-button').addEventListener('click', () => $('agui-file').click());
            $('agui-file').addEventListener('change', event => this.importAguiFile(event.target.files?.[0]));
            $('langgraph-button').addEventListener('click', () => {
                $('import-menu').open = false;
                $('langgraph-file').click();
            });
            $('empty-langgraph-button').addEventListener('click', () => $('langgraph-file').click());
            $('langgraph-file').addEventListener('change', event => this.importLangGraphFile(event.target.files?.[0]));
            $('compare-run-select').addEventListener('change', event => {
                this.compareRunId = event.target.value;
                this.openCompareStream();
                this.loadComparison(this.compareProgress);
            });
            $('truth-help').addEventListener('click', () => $('truth-dialog').showModal());
            $('object-search').addEventListener('input', () => this.renderObjectMirror());
            document.querySelectorAll('[data-memory-layer]').forEach(button => {
                button.addEventListener('click', () => {
                    if (button.dataset.eventId) this.selectEvent(button.dataset.eventId);
                });
            });

            const inspectorTabs = [...document.querySelectorAll('.inspector-tabs button')];
            inspectorTabs.forEach((button, index) => {
                button.addEventListener('click', () => this.switchTab(button.dataset.tab));
                button.addEventListener('keydown', event => {
                    if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
                    event.preventDefault();
                    event.stopPropagation();
                    const offset = event.key === 'ArrowRight' ? 1 : -1;
                    const next = inspectorTabs[(index + offset + inspectorTabs.length) % inspectorTabs.length];
                    this.switchTab(next.dataset.tab);
                    next.focus();
                });
            });
            document.querySelectorAll('.view-button[data-view]').forEach(button => button.addEventListener('click', () => this.switchView(button.dataset.view)));
            document.querySelectorAll('.causal-controls button').forEach(button => button.addEventListener('click', () => {
                this.causalDirection = button.dataset.direction;
                document.querySelectorAll('.causal-controls button').forEach(item => {
                    const selected = item === button;
                    item.classList.toggle('active', selected);
                    item.setAttribute('aria-pressed', String(selected));
                });
                if (this.selectedEventId) this.loadCausality(this.selectedEventId);
            }));

            $('timeline-range').addEventListener('input', event => {
                const requestedCursor = Number(event.target.value);
                this.setFollow(false);
                this.stopPlayback();
                if (this.currentView === 'compare') {
                    this.scheduleComparison(requestedCursor / 1000);
                } else {
                    this.scheduleCursor(requestedCursor);
                }
            });
            $('jump-start').addEventListener('click', () => this.currentView === 'compare' ? this.loadComparison(0) : this.gotoSeq(0));
            $('step-back').addEventListener('click', () => this.currentView === 'compare'
                ? this.loadComparison(Math.max(0, this.compareProgress - .025))
                : this.gotoSeq(Math.max(0, this.cursorSeq - 1)));
            $('step-forward').addEventListener('click', () => this.currentView === 'compare'
                ? this.loadComparison(Math.min(1, this.compareProgress + .025))
                : this.gotoSeq(Math.min(this.headSeq, this.cursorSeq + 1)));
            $('jump-head').addEventListener('click', () => {
                if (this.currentView === 'compare') this.loadComparison(1);
                else { this.setFollow(true); this.gotoSeq(this.headSeq); }
            });
            $('play-toggle').addEventListener('click', () => this.togglePlayback());
            $('play-speed').addEventListener('change', () => { if (this.playTimer) { this.stopPlayback(); this.startPlayback(); } });
            $('motion-preference').addEventListener('change', event => {
                const effective = this.canvas.setMotionMode(event.target.value);
                this.announceStatus(`Motion preference ${event.target.value}; effective motion ${effective}.`);
            });
            $('follow-live').addEventListener('click', () => {
                const following = !this.followLive;
                this.setFollow(following);
                this.announceStatus(following
                    ? 'Presentation is following ledger head; ledger capture was never paused.'
                    : 'Presentation paused at ledger head; ledger capture continues.');
                if (this.followLive) this.gotoSeq(this.headSeq);
            });
            $('fork-run').addEventListener('click', () => this.forkCurrentRun());
            window.addEventListener('keydown', event => this.onKey(event));
        }

        async loadRuns(preferredId = null) {
            try {
                const response = await this.fetchJson(`${API}/runs?limit=500`);
                this.runs = response.items || [];
                this.staleRunIds.clear();
                if (!this.runs.length) {
                    const select = $('run-select');
                    select.innerHTML = '';
                    select.append(new Option('事件账本为空', ''));
                    this.showEmpty(true);
                    this.setConnection('offline', 'NO RUNS');
                    return;
                }
                const requested = preferredId || this.runId;
                const target = requested && this.runs.some(run => run.run_id === requested)
                    ? requested
                    : this.runs[0].run_id;
                this.renderRunOptions(target);
                await this.selectRun(target);
            } catch (error) {
                this.setConnection('error', 'API ERROR');
                this.showEmpty(true, error.message);
            }
        }

        renderRunOptions(selectedRunId = this.runId) {
            if (selectedRunId && !this.runs.some(run => run.run_id === selectedRunId)) {
                return false;
            }
            this.runIdLabels = buildRunIdLabels(this.runs);
            const select = $('run-select');
            select.innerHTML = '';
            this.runs.forEach(run => {
                if (typeof run?.run_id !== 'string') return;
                select.append(new Option(
                    formatRunOption(
                        run, this.runIdLabels.get(run.run_id), this.staleRunIds.has(run.run_id),
                    ), run.run_id,
                ));
            });
            if (selectedRunId && this.runs.some(run => run.run_id === selectedRunId)) {
                select.value = selectedRunId;
                this.manifest = this.runs.find(run => run.run_id === selectedRunId) || null;
            }
            this.populateCompareRuns();
            return true;
        }

        async createDemo() {
            const buttons = [$('demo-button'), $('empty-demo-button')];
            buttons.forEach(button => { button.disabled = true; button.dataset.original = button.textContent; button.textContent = '正在生成…'; });
            try {
                const result = await this.fetchJson(`${API}/demo`, { method: 'POST' });
                await this.loadRuns(result.run_id);
            } catch (error) {
                this.flashError(error.message);
            } finally {
                buttons.forEach(button => { button.disabled = false; button.textContent = button.dataset.original || '一键展品'; });
            }
        }

        async importOtlpFile(file) {
            if (!file) return;
            const button = $('otlp-button');
            const summary = $('import-menu').querySelector('summary');
            const original = summary.textContent;
            button.disabled = true;
            summary.textContent = 'IMPORTING…';
            try {
                const payload = JSON.parse(await file.text());
                const result = await this.fetchJson(`${API}/import/otlp`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ payload }),
                });
                await this.loadRuns(result.run_id);
            } catch (error) {
                this.flashError(`OTLP import failed: ${error.message}`);
            } finally {
                button.disabled = false;
                summary.textContent = original;
                $('otlp-file').value = '';
            }
        }

        async importAguiFile(file) {
            if (!file) return;
            const button = $('agui-button');
            const summary = $('import-menu').querySelector('summary');
            const original = summary.textContent;
            button.disabled = true;
            summary.textContent = 'IMPORTING…';
            try {
                const text = await file.text();
                const ndjson = /\.(ndjson|jsonl)$/i.test(file.name)
                    || file.type === 'application/x-ndjson';
                const payload = ndjson ? text : JSON.parse(text);
                const result = await this.fetchJson(`${API}/import/agui`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ payload, format: ndjson ? 'ndjson' : 'json' }),
                });
                await this.loadRuns(result.run_id);
            } catch (error) {
                this.flashError(`AG-UI import failed: ${error.message}`);
            } finally {
                button.disabled = false;
                summary.textContent = original;
                $('agui-file').value = '';
            }
        }

        async importLangGraphFile(file) {
            if (!file) return;
            const button = $('langgraph-button');
            const summary = $('import-menu').querySelector('summary');
            const original = summary.textContent;
            button.disabled = true;
            summary.textContent = 'IMPORTING…';
            try {
                const text = await file.text();
                const ndjson = /\.(ndjson|jsonl)$/i.test(file.name)
                    || file.type === 'application/x-ndjson';
                const payload = ndjson ? text : JSON.parse(text);
                const request = { payload, format: ndjson ? 'ndjson' : 'json' };
                const hasEnvelopeRunId = !ndjson
                    && payload
                    && !Array.isArray(payload)
                    && Array.isArray(payload.parts)
                    && typeof payload.runId === 'string'
                    && payload.runId.trim();
                if (!hasEnvelopeRunId) {
                    const runId = importRunId('langgraph');
                    Object.assign(request, { run_id: runId });
                }
                if (ndjson) {
                    Object.assign(request, { stream_complete: false });
                }
                const result = await this.fetchJson(`${API}/import/langgraph`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(request),
                });
                await this.loadRuns(result.run_id);
            } catch (error) {
                this.flashError(`LangGraph import failed: ${error.message}`);
            } finally {
                button.disabled = false;
                summary.textContent = original;
                $('langgraph-file').value = '';
            }
        }

        async selectRun(runId) {
            if (!runId) return;
            if (
                this.runId
                && this.world
                && (!this.committedSelection || this.committedSelection.runId === this.runId)
            ) {
                this.committedSelection = {
                    runId: this.runId,
                    manifest: this.runs.find(run => run.run_id === this.runId) || this.manifest,
                    selectedEventId: this.selectedEventId,
                    cursorEventId: this.cursorEventId,
                };
            }
            const previousSelection = this.committedSelection
                ? { ...this.committedSelection }
                : null;
            const runRequestEpoch = ++this.runRequestEpoch;
            this.closeStream();
            this.closeCompareStream();
            this.stopPlayback();
            clearTimeout(this.refreshTimer);
            this.refreshTimer = null;
            clearTimeout(this.headRefreshTimer);
            this.cancelManifestRefresh();
            this.headRefreshTimer = null;
            this.cancelComparisonRequest();
            if (this.currentView === 'compare') {
                this.showComparisonLoading('LOADING SELECTED RUN…');
            }
            if (this.worldRequest) this.worldRequest.abort();
            this.worldRequest = null;
            this.worldRequestId += 1;
            this.runId = runId;
            this.selectedEventId = null;
            this.cursorEventId = null;
            this.causalRequestId += 1;
            this.canvas.setSelected(null);
            this.manifest = this.runs.find(run => run.run_id === runId) || null;
            $('run-select').value = runId;
            const loadingId = identityField(this.runIdLabels.get(runId) || shortId(runId));
            this.showEmpty(
                true, `Loading run ${loadingId}…`, 'LOADING RUN',
            );
            this.setConnection('loading', 'LOADING LEDGER');
            try {
                const [world, eventPage, integrity] = await Promise.all([
                    this.fetchJson(`${API}/runs/${encodeURIComponent(runId)}/world`),
                    this.fetchJson(`${API}/runs/${encodeURIComponent(runId)}/events?limit=5000`),
                    this.fetchJson(`${API}/runs/${encodeURIComponent(runId)}/integrity`),
                ]);
                if (this.runId !== runId || this.runRequestEpoch !== runRequestEpoch) return;
                this.events = eventPage.items || [];
                this.eventsById = new Map(this.events.map(event => [event.event_id, event]));
                this.headSeq = Number(world.head_seq ?? -1);
                this.cursorSeq = this.headSeq;
                this.setFollow(true, false);
                this.showEmpty(false);
                this.applyWorld(world);
                this.renderIntegrity(integrity);
                this.renderTimelineTicks();
                this.renderSyntheticBanner();
                this.openStream();
                if (this.currentView === 'compare') {
                    this.populateCompareRuns();
                    this.openCompareStream();
                    await this.loadComparison(this.compareProgress);
                }
                this.committedSelection = {
                    runId: this.runId,
                    manifest: this.manifest,
                    selectedEventId: this.selectedEventId,
                    cursorEventId: this.cursorEventId,
                };
            } catch (error) {
                if (this.runId !== runId || this.runRequestEpoch !== runRequestEpoch) return;
                if (previousSelection) {
                    this.runId = previousSelection.runId;
                    this.manifest = previousSelection.manifest;
                    this.selectedEventId = previousSelection.selectedEventId;
                    this.cursorEventId = previousSelection.cursorEventId;
                    $('run-select').value = previousSelection.runId;
                    this.canvas.setSelected(previousSelection.selectedEventId);
                    this.showEmpty(false);
                    this.renderRunSummary();
                    this.renderSyntheticBanner();
                    this.renderTimeline();
                    this.setConnection('loading', 'RESTORING LEDGER');
                    this.openStream();
                    if (this.currentView === 'compare') {
                        this.populateCompareRuns();
                        this.openCompareStream();
                        await this.loadComparison(this.compareProgress);
                    }
                    this.flashError(`Run selection failed; restored ${identityField(
                        this.runIdLabels.get(previousSelection.runId)
                            || shortId(previousSelection.runId),
                    )}: ${error.message}`);
                    return;
                }
                this.setConnection('error', 'RUN LOAD FAILED');
                this.showEmpty(true, error.message, 'RUN LOAD FAILED');
                if (this.currentView === 'compare') {
                    const banner = $('comparability-banner');
                    banner.className = 'comparability-banner warning';
                    banner.textContent = `RUN LOAD FAILED · ${textField(error.message, 180) || 'UNKNOWN ERROR'}`;
                }
                this.flashError(error.message);
            }
        }

        async gotoSeq(seq) {
            if (!this.runId || this.headSeq < 0) return;
            const runId = this.runId;
            const target = clamp(Math.round(seq), 0, this.headSeq);
            if (target !== this.headSeq) this.setFollow(false);
            if (this.worldRequest) this.worldRequest.abort();
            const controller = new AbortController();
            const requestId = ++this.worldRequestId;
            this.worldRequest = controller;
            try {
                const suffix = target === this.headSeq && this.followLive ? '' : `?at_seq=${target}`;
                const world = await this.fetchJson(`${API}/runs/${encodeURIComponent(runId)}/world${suffix}`, { signal: controller.signal });
                if (
                    controller.signal.aborted
                    || this.runId !== runId
                    || this.worldRequestId !== requestId
                ) return;
                this.applyWorld(world);
            } catch (error) {
                if (
                    error.name !== 'AbortError'
                    && this.runId === runId
                    && this.worldRequestId === requestId
                ) this.flashError(error.message);
            } finally {
                if (this.worldRequestId === requestId) this.worldRequest = null;
            }
        }

        scheduleCursor(seq) {
            clearTimeout(this.refreshTimer);
            this.refreshTimer = setTimeout(() => this.gotoSeq(seq), 55);
            this.updateTimelineLabel(seq);
        }

        scheduleComparison(progress) {
            clearTimeout(this.refreshTimer);
            this.compareProgress = clamp(progress, 0, 1);
            this.updateTimelineLabel();
            this.refreshTimer = setTimeout(() => this.loadComparison(this.compareProgress), 70);
        }

        applyWorld(response) {
            this.worldResponse = response;
            this.world = response.state;
            document.body.dataset.runTerminal = String(TERMINAL_RUN_STATUSES.has(this.world?.run_status));
            const previousCursorEventId = this.cursorEventId;
            const cursorEventId = this.world.cursor_event_id || null;
            this.cursorSeq = Number(response.projected_seq ?? this.world.cursor_seq ?? -1);
            this.headSeq = Math.max(this.headSeq, Number(response.head_seq ?? -1));
            if (!this.selectedEventId || this.selectedEventId === previousCursorEventId) {
                this.selectedEventId = cursorEventId;
            }
            this.cursorEventId = cursorEventId;
            this.canvas.setWorld(this.world);
            this.canvas.setSelected(this.selectedEventId);
            this.renderRunSummary();
            this.renderTruthMix();
            this.renderCognition();
            this.renderChamberList();
            this.renderObjectMirror();
            this.renderStatePanel();
            this.renderCoveragePanel();
            this.renderEventFeed();
            this.renderTimeline();
            if (!$('causal-panel').hidden && this.selectedEventId) {
                this.loadCausality(this.selectedEventId);
            }
            const isHead = this.cursorSeq === this.headSeq;
            this.setConnection('connected', 'LEDGER CONNECTED');
            $('world-mode').textContent = isHead
                ? (this.followLive ? 'AT HEAD · FOLLOWING' : 'AT HEAD · PAUSED')
                : `HISTORY · SEQ ${this.cursorSeq}`;
            const runStateKey = `${this.runId}\u0000${this.world?.run_status || 'unknown'}`;
            if (runStateKey !== this.announcedRunStateKey) {
                this.announcedRunStateKey = runStateKey;
                this.announceStatus(`Run status ${this.world?.run_status || 'unknown'} at cursor sequence ${this.cursorSeq}.`);
            }
        }

        renderRunSummary() {
            const state = this.world;
            $('run-title').textContent = formatRunTitle(
                this.manifest || { run_id: this.runId }, this.runIdLabels.get(this.runId),
            );
            $('run-status').textContent = String(state.run_status || 'unknown').toUpperCase();
            $('run-status').dataset.status = state.run_status || 'unknown';
            $('event-count').textContent = humanNumber(state.event_count);
            $('cursor-count').textContent = `${this.cursorSeq} / ${this.headSeq}`;
            $('adapter-count').textContent = Object.keys(state.source_adapters || {}).length;
            $('error-count').textContent = (state.errors || []).filter(error => error.status === 'open').length;
            const currentEvent = this.eventsById.get(state.cursor_event_id);
            $('privacy-mode').textContent = (currentEvent?.privacy?.content || 'metadata_only').replace('_only', '').toUpperCase();
        }

        renderIntegrity(result) {
            const element = $('integrity-status');
            element.className = `integrity-chip ${result.valid ? 'valid' : 'invalid'}`;
            element.textContent = result.valid ? 'HASH CHAIN VALID' : `INTEGRITY FAIL · ${result.errors.length}`;
        }

        renderTruthMix() {
            const counts = this.world.evidence_counts || {};
            const total = Object.values(counts).reduce((sum, value) => sum + value, 0) || 1;
            document.querySelectorAll('.truth-bars > div').forEach(row => {
                const value = Number(counts[row.dataset.truth] || 0);
                row.querySelector('b').style.width = `${value / total * 100}%`;
                row.querySelector('em').textContent = value;
            });
        }

        renderCognition() {
            const context = this.world.context || {};
            const used = context.used_tokens;
            const budget = context.budget_tokens;
            const eventTypes = Object.keys(this.world.event_type_counts || {});
            const hasFamily = prefix => eventTypes.some(eventType => eventType.startsWith(prefix));
            const contextObserved = hasFamily('context.');
            const compactionObserved = hasFamily('compaction.');
            const ratio = budget != null && budget > 0 ? used / budget : 0;
            $('context-label').textContent = budget != null
                ? `${humanNumber(used)} / ${humanNumber(budget)}`
                : contextObserved
                    ? 'CONTEXT OBSERVED · BUDGET NOT OBSERVED'
                    : 'NOT OBSERVED';
            const fill = $('context-fill');
            fill.style.width = `${clamp(ratio * 100, 0, 100)}%`;
            fill.className = context.overflow ? 'overflow' : ratio >= .85 ? 'warning' : '';
            const memory = this.world.memory || {};
            const operationLabels = {
                'memory.written': 'WRITE',
                'memory.updated': 'UPDATE',
                'memory.deleted': 'DELETE',
                'memory.evicted': 'EVICTION',
                'memory.hit': 'HIT',
                'memory.miss': 'MISS',
                'memory.read': 'READ',
                'memory.searched': 'SEARCH',
            };
            for (const layer of ['working', 'episodic', 'semantic']) {
                const button = document.querySelector(`[data-memory-layer="${layer}"]`);
                const value = $(`memory-${layer}`);
                const observation = memory.layer_operations?.[layer];
                button.disabled = !observation;
                button.dataset.eventId = observation?.last_event_id || '';
                button.dataset.truth = observation?.truth?.level || 'not_observed';
                if (!observation) {
                    value.textContent = 'NOT OBSERVED';
                    button.querySelector('small').textContent = 'NO LAYER SIGNAL';
                    button.setAttribute('aria-label', `${layer} memory operations not observed at cursor`);
                    continue;
                }
                const parts = Object.entries(observation.event_type_counts || {})
                    .filter(([eventType]) => operationLabels[eventType])
                    .map(([eventType, count]) => `${count} ${operationLabels[eventType]}${count === 1 ? '' : 'S'}`);
                value.textContent = parts.join(' · ') || `${observation.event_count} EVENT${observation.event_count === 1 ? '' : 'S'}`;
                button.querySelector('small').textContent = `OBSERVED · #${observation.last_seq}`;
                button.setAttribute('aria-label', `${layer} memory: ${value.textContent}; ${observation.truth?.level || 'unknown'} evidence; inspect event ${observation.last_event_id}`);
            }
            const jobs = Object.values(this.world.compactions || {});
            const job = jobs[jobs.length - 1];
            $('compact-status').textContent = job
                ? String(job.status).toUpperCase()
                : compactionObserved
                    ? 'OBSERVED · NO JOB STATE'
                    : 'NOT OBSERVED';
            $('compact-delta').textContent = job?.tokens_removed != null
                ? `${humanNumber(job.tokens_before)} → ${humanNumber(job.tokens_after)} · removed ${humanNumber(job.tokens_removed)} tokens`
                : '没有压缩记录';
        }

        renderChamberList() {
            const container = $('chamber-list');
            const state = this.world;
            const meter = buildMeterPresentation(state);
            container.innerHTML = '';
            const terminalRun = TERMINAL_RUN_STATUSES.has(state?.run_status);
            const activityLabel = terminalRun ? 'UNRESOLVED' : 'OPEN';
            for (const zone of ZONES) {
                const activity = state?.zone_activity?.[zone.key] || 0;
                const count = state?.zone_event_counts?.[zone.key]
                    ?? (state?.recent_events || []).filter(event => event.zone === zone.key).length;
                const button = document.createElement('button');
                button.type = 'button';
                const activityClass = activity > 0
                    ? (terminalRun ? 'unresolved' : 'active') : '';
                const meterSignal = zone.key === 'meter_room'
                    ? [
                        meter.availableCount ? `${meter.availableCount} SAFE` : '',
                        meter.ambiguousCount ? `${meter.ambiguousCount} AMBIG` : '',
                    ].filter(Boolean).join(' · ')
                    : '';
                button.className = `chamber-item ${activityClass}`;
                button.style.setProperty('--chamber-color', zone.color);
                button.innerHTML = `<i></i><span>${esc(zone.label)}</span><b>${activity ? `${activity} ${activityLabel}` : meterSignal || (count ? `${count} EVT` : '—')}</b>`;
                button.addEventListener('click', () => this.selectZone(zone.key));
                container.append(button);
            }
        }

        renderObjectMirror() {
            const container = $('object-mirror');
            if (!container) return;
            const state = this.world;
            if (!state) {
                container.innerHTML = '<div class="empty-detail">选择 run 后显示全部语义对象。</div>';
                return;
            }
            const query = textField($('object-search')?.value, 120).toLocaleLowerCase('en-US');
            const zoneOrder = new Map(Object.keys(ZONE_MAP).map((key, index) => [key, index]));
            const sortKey = entity => [
                String(zoneOrder.get(entity.zone) ?? 999).padStart(3, '0'),
                textField(entity.kind, 80), textField(entity.name, 160), identityField(entity.id),
            ].join('\u0000');
            const matches = values => !query || values.some(value => String(value ?? '').toLocaleLowerCase('en-US').includes(query));
            const entities = Object.values(state.entities || {})
                .filter(entity => matches([
                    entity.id, entity.name, entity.kind, entity.zone, entity.status,
                    entity.truth?.level, entity.truth?.source_adapter,
                ]))
                .sort((left, right) => sortKey(left) < sortKey(right) ? -1 : sortKey(left) > sortKey(right) ? 1 : 0);
            const zones = Object.values(ZONE_MAP).filter(zone => matches([zone.key, zone.label]));
            const meter = buildMeterPresentation(state);
            const meterReadings = meter.readings.filter(reading => matches([
                'meter', 'measurement', reading.id, reading.key, reading.label,
                reading.status, reading.valueText, reading.detailText,
            ]));
            const terminalRun = TERMINAL_RUN_STATUSES.has(state.run_status);
            const zoneButtons = zones.map(zone => {
                const activity = Number(state.zone_activity?.[zone.key] || 0);
                const recent = state.zone_latest_events?.[zone.key]
                    || [...(state.recent_events || [])].reverse().find(event => event.zone === zone.key);
                const entityCount = Object.values(state.entities || {}).filter(entity => entity.zone === zone.key).length;
                const eventCount = Number(state.zone_event_counts?.[zone.key] || 0);
                const meterSignal = zone.key === 'meter_room'
                    && (meter.availableCount > 0 || meter.ambiguousCount > 0);
                const signal = activity ? (terminalRun ? 'UNRESOLVED' : 'OPEN')
                    : meterSignal ? 'MEASUREMENT SIGNAL AT CURSOR'
                        : (recent || entityCount ? 'SIGNAL AT CURSOR' : 'NO SIGNAL AT CURSOR');
                const truth = recent?.truth?.level || (meterSignal ? meter.truthLevel : 'not_observed');
                const meterSummary = meterSignal
                    ? ` · ${meter.availableCount} SAFE · ${meter.ambiguousCount} AMBIGUOUS`
                    : '';
                return `<button type="button" class="object-button zone-object" data-zone-id="${esc(zone.key)}" data-truth="${esc(truth)}" aria-label="${esc(`${zone.label}; chamber; ${signal}; ${truth}; cursor seq ${state.cursor_seq}`)}">
                    <span class="object-kind">CHAMBER</span><strong>${esc(zone.label)}</strong>
                    <small>${esc(signal)} · ${esc(truth.toUpperCase())} · ${eventCount} EVENTS · ${entityCount} OBJECT${entityCount === 1 ? '' : 'S'}${esc(meterSummary)}</small>
                </button>`;
            }).join('');
            const entityButtons = entities.map(entity => {
                const truth = entity.truth?.level || 'unknown';
                const confidence = entity.truth?.confidence == null ? 'UNKNOWN' : `${Math.round(entity.truth.confidence * 100)}%`;
                const eventCount = Number(entity.event_count || 0);
                const name = textField(entity.name, 160) || identityField(entity.id) || 'UNKNOWN ENTITY';
                const label = `${name}; ${entity.kind}; ${entity.status}; ${truth} ${confidence}; ${eventCount} event${eventCount === 1 ? '' : 's'}; cursor seq ${state.cursor_seq}; zone ${entity.zone}`;
                return `<button type="button" class="object-button entity-object" data-entity-id="${esc(entity.id)}" data-event-id="${esc(entity.last_event_id)}" data-truth="${esc(truth)}" aria-label="${esc(label)}">
                    <span class="object-kind">${esc(entity.kind)}</span><strong>${esc(name)}</strong>
                    <small>${esc(String(entity.status).toUpperCase())} · ${esc(truth.toUpperCase())} ${esc(confidence)} · ${eventCount} EVT · ${esc(entity.zone)}</small>
                </button>`;
            }).join('');
            const meterButtons = meterReadings.map(reading => {
                const evidenceLevels = Object.keys(reading.source?.evidence_counts || {});
                const truth = evidenceLevels.length === 1 ? evidenceLevels[0] : 'mixed';
                const route = reading.eventId
                    ? `inspect evidence event ${reading.eventId}`
                    : 'no aggregate evidence event observed';
                const label = `${reading.label}; ${reading.status.replaceAll('_', ' ')}; ${reading.valueText}; ${reading.detailText}; ${route}; cursor seq ${state.cursor_seq}`;
                return `<button type="button" class="object-button meter-object" data-meter-id="${esc(reading.id)}" data-event-id="${esc(reading.eventId)}" data-meter-status="${esc(reading.status)}" data-truth="${esc(truth)}" aria-label="${esc(label)}">
                    <span class="object-kind">MEASURE</span><strong>${esc(reading.label)} · ${esc(reading.valueText)}</strong>
                    <small>${esc(reading.status.toUpperCase().replaceAll('_', ' '))} · ${esc(reading.detailText)}</small>
                </button>`;
            }).join('');
            $('objects-heading').textContent = `${entities.length} OBJECTS · ${zones.length} CHAMBERS · ${meter.readings.length} METER READOUTS · SEQ ${state.cursor_seq}`;
            container.dataset.cursorSeq = state.cursor_seq;
            container.innerHTML = `
                <section class="object-group meter-object-group"><header><span>SAFE MEASUREMENTS</span><b>${meter.availableCount} AVAILABLE · ${meter.ambiguousCount} AMBIGUOUS</b></header><div class="object-list">${meterButtons || '<div class="empty-detail">No meter readout matches</div>'}</div></section>
                <section class="object-group"><header><span>CHAMBERS</span><b>${zones.length}</b></header><div class="object-list">${zoneButtons || '<div class="empty-detail">No chamber matches</div>'}</div></section>
                <section class="object-group"><header><span>ENTITIES</span><b>${entities.length}</b></header><div class="object-list">${entityButtons || '<div class="empty-detail">No entity matches</div>'}</div></section>`;
            container.querySelectorAll('[data-zone-id]').forEach(button => button.addEventListener('click', () => this.selectZone(button.dataset.zoneId)));
            container.querySelectorAll('[data-entity-id]').forEach(button => button.addEventListener('click', () => this.selectEvent(button.dataset.eventId)));
            container.querySelectorAll('[data-meter-id]').forEach(button => button.addEventListener('click', () => {
                if (button.dataset.eventId) this.selectEvent(button.dataset.eventId);
                else this.selectZone('meter_room');
            }));
        }

        renderStatePanel() {
            const state = this.world;
            $('state-heading').textContent = `${String(state.run_status).toUpperCase()} · ${state.event_count} events`;
            $('state-subheading').textContent = `Reducer ${state.reducer_version} projected at ingest sequence ${state.cursor_seq}.`;
            const agents = Object.values(state.entities || {}).filter(entity => entity.kind === 'agent');
            const jobs = Object.values(state.compactions || {});
            const latestJob = jobs[jobs.length - 1];
            const context = state.context || {};
            const contextObserved = Boolean(context.last_event_id);
            const contextItemCount = Object.keys(context.items || {}).length;
            const contextStatus = typeof context.status === 'string' ? context.status : '';
            const contextStatusObserved = contextObserved
                && !['', 'idle', 'unknown'].includes(contextStatus.toLowerCase());
            const contextBudget = contextObserved && context.budget_tokens != null
                ? `${context.used_tokens != null ? humanNumber(context.used_tokens) : 'NOT OBSERVED'} / ${humanNumber(context.budget_tokens)} tokens`
                : 'NOT OBSERVED';
            const memory = state.memory || {};
            const memoryEventCount = Object.entries(state.event_type_counts || {})
                .filter(([eventType]) => eventType.startsWith('memory.'))
                .reduce((total, [, count]) => total + Number(count || 0), 0);
            const memoryObserved = memoryEventCount > 0;
            const blocks = [
                {
                    title: 'OBSERVED AGENTS', value: agents.length,
                    rows: agents.length ? agents.slice(0, 8).map(agent => [agent.name, `${agent.zone} · ${agent.status}`, agent.active ? 'good' : '']) : [['none observed', '—', '']],
                },
                {
                    title: 'CONTEXT MANIFEST',
                    value: contextObserved ? `${contextItemCount} OBSERVED ITEMS` : 'NOT OBSERVED',
                    rows: [
                        ['budget', contextBudget, context.overflow ? 'danger' : ''],
                        ['policy', contextObserved && context.policy ? context.policy : 'NOT OBSERVED', ''],
                        ['status', contextStatusObserved ? contextStatus : 'NOT OBSERVED', contextStatusObserved ? (context.overflow ? 'danger' : 'good') : ''],
                    ],
                },
                {
                    title: 'OBSERVED MEMORY OPERATIONS',
                    value: memoryObserved ? memoryEventCount : 'NOT OBSERVED',
                    rows: memoryObserved ? [
                        ['hit / miss', `${memory.hits || 0} / ${memory.misses || 0}`, ''],
                        ['writes / evictions', `${memory.writes || 0} / ${memory.evictions || 0}`, ''],
                        ['conflicts', memory.conflicts || 0, memory.conflicts ? 'warning' : ''],
                    ] : [['signal', 'NOT OBSERVED', '']],
                },
                {
                    title: 'LATEST COMPACTION', value: latestJob ? jobs.length : 'NOT OBSERVED',
                    rows: latestJob ? [
                        ['status', latestJob.status, latestJob.status === 'failed' ? 'danger' : 'good'],
                        ['tokens', `${humanNumber(latestJob.tokens_before)} → ${humanNumber(latestJob.tokens_after)}`, ''],
                        ['lossy / removed refs', `${latestJob.lossy ?? 'unknown'} / ${latestJob.removed_refs.length}`, latestJob.lossy ? 'warning' : ''],
                        ['summary hash', shortId(latestJob.summary_hash), ''],
                    ] : [['not observed', '—', '']],
                },
            ];
            $('state-stack').innerHTML = blocks.map(block => `
                <section class="state-block">
                    <header><span>${esc(block.title)}</span><b>${esc(block.value)}</b></header>
                    <dl>${block.rows.map(([key, value, className]) => `<dt>${esc(key)}</dt><dd class="${esc(className)}">${esc(value)}</dd>`).join('')}</dl>
                </section>`).join('');
        }

        renderCoveragePanel() {
            const visibility = this.worldResponse?.visibility;
            const container = $('coverage-content');
            if (!visibility) {
                $('coverage-heading').textContent = 'VISIBILITY UNKNOWN';
                $('coverage-subheading').textContent = 'This server did not return an instrumentation contract.';
                container.className = 'coverage-content empty-detail';
                container.textContent = '升级服务端后再检查适配器能力与盲区。';
                return;
            }
            const domains = visibility.domains || [];
            const observed = domains.filter(row => row.status === 'observed');
            const notSeen = domains.filter(row => row.status === 'observable_not_seen');
            const outside = domains.filter(row => row.status === 'outside_adapter_contract');
            $('coverage-heading').textContent = `${observed.length} DOMAINS WITH SIGNALS`;
            $('coverage-subheading').textContent = `Contract ${visibility.contract_version} · no synthetic coverage score.`;
            const signalText = row => {
                const parts = [];
                if (row.event_count) parts.push(`${row.event_count} EVT`);
                if (row.measurement_keys?.length) parts.push(`${row.measurement_keys.length} SAFE METRIC`);
                if (row.unaggregated_measurement_keys?.length) {
                    parts.push(`${row.unaggregated_measurement_keys.length} RAW · UNSAFE`);
                }
                return parts.join(' · ') || '0 SEEN';
            };
            const domainRow = row => `
                <div class="coverage-domain ${esc(row.status)}" data-coverage-domain="${esc(row.domain)}">
                    <i></i><span>${esc(row.domain.toUpperCase())}</span>
                    <b>${esc(row.status === 'observable_not_seen' ? 'CAN OBSERVE · 0 SEEN' : signalText(row))}</b>
                </div>`;
            const adapters = (visibility.adapters || []).map(adapter => `
                <article class="coverage-adapter ${adapter.registered ? '' : 'unregistered'}">
                    <header><strong>${esc(adapter.label)}</strong><span>${esc(adapter.kind.toUpperCase())}</span></header>
                    <code>${esc(adapter.adapter)} · ${esc(adapter.event_count)} EVT</code>
                    <p>${esc(adapter.can_observe.length ? `CAN OBSERVE: ${adapter.can_observe.join(', ')}` : 'NO NEW OBSERVATION CONTRACT')}</p>
                </article>`).join('');
            const blindSpots = (visibility.blind_spots || []).map(item => `<li>${esc(item)}</li>`).join('');
            const unregistered = visibility.unregistered_adapters?.length
                ? `<div class="coverage-alert">UNREGISTERED: ${esc(visibility.unregistered_adapters.join(', '))}</div>`
                : '';
            const unsafeMeasurements = (visibility.unsafe_measurements || []).map(item => {
                const count = Number(item.issue_count || 0);
                const measurementKey = textField(identityField(item.measurement_key), 96) || 'UNKNOWN';
                const reasons = (item.recent_reasons || []).join(' · ') || 'reason outside recent diagnostic tail';
                return `<div class="coverage-alert measurement-unsafe"><strong>${esc(measurementKey)} · ${count} ISSUE${count === 1 ? '' : 'S'}</strong><span>RAW SIGNAL · SAFE AGGREGATE UNAVAILABLE · ${esc(reasons)}</span></div>`;
            }).join('');
            container.className = 'coverage-content';
            container.innerHTML = `
                <div class="coverage-warning">${esc(visibility.warnings?.[0] || 'Unobserved does not mean absent.')}</div>
                ${unregistered}
                ${unsafeMeasurements ? `<section class="coverage-section"><header><span>UNAGGREGATED MEASUREMENTS</span><b>${visibility.unsafe_measurements.length}</b></header>${unsafeMeasurements}</section>` : ''}
                <section class="coverage-section">
                    <header><span>VISIBLE EVENT / METRIC SIGNALS</span><b>${observed.length}</b></header>
                    <div class="coverage-domains">${observed.map(domainRow).join('') || '<div class="empty-detail">No semantic domain observed</div>'}</div>
                </section>
                <section class="coverage-section">
                    <header><span>OBSERVABLE / NOT SEEN</span><b>${notSeen.length}</b></header>
                    <div class="coverage-domains">${notSeen.map(domainRow).join('') || '<div class="empty-detail">No declared-but-unseen domain</div>'}</div>
                </section>
                <section class="coverage-section">
                    <header><span>OUTSIDE CONTRACT</span><b>${outside.length}</b></header>
                    <p class="coverage-muted">${esc(outside.map(row => row.domain).join(', ') || 'none')}</p>
                </section>
                <section class="coverage-section">
                    <header><span>UNKNOWN FOG TYPES</span><b>${visibility.unmapped_event_types?.length || 0}</b></header>
                    <p class="coverage-muted">${esc(visibility.unmapped_event_types?.join(', ') || 'none')}</p>
                </section>
                <section class="coverage-section">
                    <header><span>ADAPTER CONTRACTS</span><b>${visibility.adapters?.length || 0}</b></header>
                    ${adapters || '<div class="empty-detail">No adapter identity observed</div>'}
                </section>
                <section class="coverage-section">
                    <header><span>KNOWN BLIND SPOTS</span><b>${visibility.blind_spots?.length || 0}</b></header>
                    <ul class="coverage-blind-spots">${blindSpots || '<li>No registered blind-spot statement</li>'}</ul>
                </section>`;
        }

        renderEventFeed(zoneFilter = null) {
            const recent = [...(this.world?.recent_events || [])].reverse();
            const filtered = zoneFilter ? recent.filter(event => event.zone === zoneFilter) : recent;
            $('recent-count').textContent = zoneFilter ? `${filtered.length} · ${zoneFilter}` : filtered.length;
            const list = $('event-feed');
            list.innerHTML = '';
            filtered.slice(0, 80).forEach(event => {
                const item = document.createElement('li');
                const button = document.createElement('button');
                button.type = 'button';
                button.dataset.eventId = event.event_id;
                button.dataset.truth = event.truth.level;
                button.className = event.event_id === this.selectedEventId ? 'selected' : '';
                button.innerHTML = `
                    <span class="event-seq">#${event.seq}</span>
                    <span class="event-copy"><strong><i></i>${esc(event.event_type)} <b class="event-truth">${esc(event.truth.level.toUpperCase())}</b></strong><small>${esc(event.summary || event.subject_id || event.zone)}</small></span>`;
                button.addEventListener('click', () => this.selectEvent(event.event_id));
                item.append(button); list.append(item);
            });
        }

        renderTimeline() {
            const range = $('timeline-range');
            if (this.currentView === 'compare') {
                const enabled = Boolean(this.runId && this.compareRunId);
                range.disabled = !enabled;
                range.min = 0;
                range.max = 1000;
                range.value = Math.round(this.compareProgress * 1000);
                this.updateTimelineLabel();
                $('follow-live').classList.remove('active');
                $('follow-live').disabled = true;
                $('follow-live').setAttribute('aria-pressed', 'false');
                $('fork-run').disabled = true;
                ['jump-start', 'step-back', 'play-toggle', 'step-forward', 'jump-head'].forEach(id => $(id).disabled = !enabled);
                const ticks = $('timeline-ticks');
                ticks.innerHTML = Array.from({ length: 11 }, (_, index) => `<i class="${index % 5 === 0 ? 'major' : ''}" style="left:${index * 10}%"></i>`).join('');
                return;
            }
            range.min = 0;
            range.disabled = this.headSeq < 0;
            range.max = Math.max(this.headSeq, 0);
            range.value = Math.max(this.cursorSeq, 0);
            this.updateTimelineLabel(this.cursorSeq);
            $('follow-live').classList.toggle('active', this.followLive);
            $('follow-live').disabled = false;
            $('follow-live').setAttribute('aria-pressed', String(this.followLive));
            const disabled = this.headSeq < 0;
            $('fork-run').disabled = disabled;
            ['jump-start', 'step-back', 'play-toggle', 'step-forward', 'jump-head'].forEach(id => $(id).disabled = disabled);
        }

        updateTimelineLabel(seq) {
            if (this.currentView === 'compare') {
                const percent = Math.round(this.compareProgress * 100);
                const cursor = this.compareData?.cursor;
                $('timeline-seq').textContent = `SYNC ${percent}%`;
                $('timeline-event').textContent = cursor
                    ? `left #${cursor.left_seq}/${cursor.left_head} · right #${cursor.right_seq}/${cursor.right_head}`
                    : '等待双 run 对比';
                $('timeline-time').textContent = 'NORMALIZED PROGRESS';
                return;
            }
            const event = this.events.find(item => item.clock?.ingest_seq === seq) || this.eventsById.get(this.world?.cursor_event_id);
            $('timeline-seq').textContent = seq >= 0 ? `SEQ ${seq}` : 'SEQ —';
            $('timeline-event').textContent = event ? `${event.event_type} · ${event.summary || event.subject?.name || ''}` : '等待事件';
            $('timeline-time').textContent = event ? this.relativeTime(event) : '—';
            $('world-clock').textContent = event ? this.relativeTime(event) : 'T+00:00.000';
        }

        renderTimelineTicks() {
            const container = $('timeline-ticks');
            container.innerHTML = '';
            const max = Math.max(this.headSeq, 1);
            const stride = Math.max(1, Math.ceil(this.events.length / 160));
            this.events.forEach((event, index) => {
                const seq = event.clock?.ingest_seq ?? index;
                const family = eventFamily(event.event_type);
                if (index % stride !== 0 && family !== 'error' && family !== 'compaction') return;
                const tick = document.createElement('i');
                tick.style.left = `${seq / max * 100}%`;
                if (seq % Math.max(Math.round(max / 10), 1) === 0) tick.classList.add('major');
                if (family === 'error' || event.event_type.endsWith('.failed')) tick.classList.add('error');
                if (family === 'compaction') tick.classList.add('compaction');
                tick.title = `#${seq} ${event.event_type}`;
                container.append(tick);
            });
        }

        renderSyntheticBanner() {
            const synthetic = Boolean(this.manifest?.synthetic);
            $('synthetic-banner').hidden = !synthetic;
        }

        async selectEvent(eventId) {
            if (!eventId || !this.runId) return;
            this.selectedEventId = eventId;
            this.canvas.setSelected(eventId);
            let event = this.eventsById.get(eventId);
            try {
                if (!event) {
                    const query = new URLSearchParams({ event_id: eventId });
                    event = await this.fetchJson(`${API}/runs/${encodeURIComponent(this.runId)}/event?${query}`);
                }
                this.eventsById.set(eventId, event);
                this.renderEventDetail(event);
                this.renderEventFeed();
                this.switchTab('event');
                if (document.querySelector('.view-button[data-view="causal"]')?.classList.contains('active')) this.loadCausality(eventId);
            } catch (error) {
                this.flashError(error.message);
            }
        }

        renderEventDetail(event) {
            $('event-heading').textContent = event.event_type;
            $('event-summary').textContent = event.summary || `Event ${event.event_id}`;
            const evidence = event.evidence || {};
            const source = event.source || {};
            const confidence = evidence.confidence != null ? `${(evidence.confidence * 100).toFixed(0)}%` : '—';
            const refs = (evidence.refs || []).map(ref => `<span class="source-ref">${esc(ref.kind)} · ${esc(ref.uri)}${ref.line_start ? `:${ref.line_start}` : ''}</span>`).join('') || '<span class="source-ref">No direct source reference captured</span>';
            $('event-detail').className = 'event-detail';
            $('event-detail').innerHTML = `
                <div class="evidence-ribbon" data-truth="${esc(evidence.level || 'unknown')}">
                    <strong>${esc((evidence.level || 'unknown').toUpperCase())}</strong><em>${esc(confidence)}</em>
                    <small>${esc(evidence.explanation || 'No adapter explanation')}</small>
                </div>
                <dl class="detail-grid">
                    <dt>INGEST SEQ</dt><dd>${esc(event.clock?.ingest_seq)}</dd>
                    <dt>EVENT ID</dt><dd>${esc(event.event_id)}</dd>
                    <dt>RUN / TRACE</dt><dd>${esc(shortId(event.run_id))} / ${esc(shortId(event.trace_id))}</dd>
                    <dt>SPAN / PARENT</dt><dd>${esc(shortId(event.span_id))} / ${esc(shortId(event.parent_span_id))}</dd>
                    <dt>CAUSED BY</dt><dd>${esc(shortId(event.causation_id))}</dd>
                    <dt>SUBJECT</dt><dd>${esc(event.subject ? `${event.subject.kind}:${event.subject.name || event.subject.id}` : '—')}</dd>
                    <dt>ADAPTER</dt><dd>${esc(source.adapter)} · ${esc(source.fidelity)}</dd>
                    <dt>OCCURRED</dt><dd>${esc(event.clock?.occurred_at || '—')}</dd>
                    <dt>PRIVACY</dt><dd>${esc(event.privacy?.content || '—')}</dd>
                </dl>
                <section class="detail-section"><h3>SOURCE REFERENCES</h3>${refs}</section>
                <section class="detail-section"><h3>PAYLOAD</h3><pre>${esc(JSON.stringify(event.payload || {}, null, 2))}</pre></section>
                <section class="detail-section"><h3>MEASUREMENTS</h3><pre>${esc(JSON.stringify(event.measurements || {}, null, 2))}</pre></section>
                <section class="detail-section"><h3>INTEGRITY</h3><pre>${esc(JSON.stringify(event.integrity || {}, null, 2))}</pre></section>`;
        }

        async loadCausality(eventId) {
            if (!eventId || !this.runId) return;
            const requestId = ++this.causalRequestId;
            const runId = this.runId;
            const direction = this.causalDirection;
            $('causal-graph').className = 'causal-graph empty-detail';
            $('causal-graph').textContent = '正在构建显式因果切片…';
            try {
                const query = new URLSearchParams({
                    event_id: eventId,
                    direction,
                    max_depth: '20',
                });
                const graph = await this.fetchJson(`${API}/runs/${encodeURIComponent(runId)}/causal?${query}`);
                if (
                    requestId !== this.causalRequestId
                    || this.runId !== runId
                    || this.selectedEventId !== eventId
                    || this.causalDirection !== direction
                ) return;
                this.renderCausalGraph(graph);
            } catch (error) {
                if (requestId !== this.causalRequestId) return;
                this.flashError(error.message);
            }
        }

        renderCausalGraph(graph) {
            const container = $('causal-graph');
            container.className = 'causal-graph';
            const levels = new Map();
            graph.nodes.forEach(node => {
                if (!levels.has(node.depth)) levels.set(node.depth, []);
                levels.get(node.depth).push(node);
            });
            container.innerHTML = [...levels.entries()].sort((a, b) => a[0] - b[0]).map(([depth, nodes]) => `
                <section class="causal-level">
                    <div class="causal-level-label">DEPTH ${depth}</div>
                    ${nodes.map(node => `<button type="button" class="causal-node ${node.event_id === graph.root_event_id ? 'root' : ''}" data-event-id="${esc(node.event_id)}" data-truth="${esc(node.evidence.level)}">
                        <strong>#${esc(node.seq)} · ${esc(node.event_type)}</strong>
                        <span>${esc(node.summary || node.event_id)} · ${esc(node.evidence.level)} ${(node.evidence.confidence * 100).toFixed(0)}%</span>
                    </button>`).join('')}
                </section>`).join('') || '<div class="empty-detail">No causal neighbors</div>';
            container.querySelectorAll('.causal-node').forEach(button => button.addEventListener('click', () => this.selectEvent(button.dataset.eventId)));
            $('causal-heading').textContent = `${graph.nodes.length} events · ${graph.edges.length} explicit links`;
        }

        selectZone(zoneKey) {
            this.switchTab('state');
            this.renderEventFeed(zoneKey);
            $('state-heading').textContent = ZONE_MAP[zoneKey]?.label || zoneKey;
            $('state-subheading').textContent = `Filtered ledger events projected into ${zoneKey}.`;
            this.openInspectorOnMobile();
        }

        switchTab(tab) {
            document.querySelectorAll('.inspector-tabs button').forEach(button => {
                const selected = button.dataset.tab === tab;
                button.classList.toggle('active', selected);
                button.setAttribute('aria-selected', String(selected));
                button.tabIndex = selected ? 0 : -1;
            });
            document.querySelectorAll('.inspector-panel').forEach(panel => {
                const active = panel.id === `${tab}-panel`;
                panel.classList.toggle('active', active);
                panel.hidden = !active;
            });
            if (tab === 'causal' && this.selectedEventId) this.loadCausality(this.selectedEventId);
            this.openInspectorOnMobile();
        }

        switchView(view) {
            this.currentView = view;
            document.querySelectorAll('.view-button[data-view]').forEach(button => {
                const selected = button.dataset.view === view;
                button.classList.toggle('active', selected);
                button.setAttribute('aria-pressed', String(selected));
            });
            const comparing = view === 'compare';
            $('app-shell').classList.toggle('compare-layout', comparing);
            $('world-stage').classList.toggle('compare-mode', comparing);
            $('compare-stage').hidden = !comparing;
            if (view === 'world') this.switchTab('state');
            if (view === 'causal') this.switchTab('causal');
            if (comparing) {
                this.stopPlayback();
                this.populateCompareRuns();
                this.openCompareStream();
                if (!STATIC_CAPTURE) this.scheduleManifestRefresh(0);
                this.loadComparison(this.compareProgress);
            } else {
                this.closeCompareStream();
                this.cancelComparisonRequest();
                this.renderTimeline();
            }
        }

        populateCompareRuns() {
            const select = $('compare-run-select');
            if (!select) return;
            const candidates = this.runs.filter(run => run.run_id !== this.runId);
            select.innerHTML = '';
            candidates.forEach(run => {
                select.append(new Option(
                    formatRunOption(
                        run, this.runIdLabels.get(run.run_id), this.staleRunIds.has(run.run_id),
                    ), run.run_id,
                ));
            });
            if (!candidates.length) {
                select.append(new Option('需要另一条 run', ''));
                this.compareRunId = null;
                return;
            }
            if (!this.compareRunId || !candidates.some(run => run.run_id === this.compareRunId)) {
                this.compareRunId = candidates[0].run_id;
            }
            select.value = this.compareRunId;
        }

        cancelComparisonRequest() {
            this.compareRequestId += 1;
            if (this.compareRequestController) this.compareRequestController.abort();
            this.compareRequestController = null;
        }

        showComparisonLoading(message) {
            this.compareData = null;
            for (const id of ['compare-left', 'compare-right', 'compare-delta']) {
                $(id).replaceChildren();
            }
            const banner = $('comparability-banner');
            banner.className = 'comparability-banner';
            banner.textContent = message;
        }

        async loadComparison(progress = this.compareProgress) {
            this.cancelComparisonRequest();
            if (!this.runId || !this.compareRunId || this.runId === this.compareRunId) {
                $('comparability-banner').className = 'comparability-banner warning';
                $('comparability-banner').textContent = '需要至少两条不同的 run。可再创建一个展品或导入 OTLP trace。';
                this.renderTimeline();
                return;
            }
            const leftRunId = this.runId;
            const rightRunId = this.compareRunId;
            this.compareProgress = clamp(progress, 0, 1);
            const requestedProgress = this.compareProgress;
            const requestId = this.compareRequestId;
            const controller = new AbortController();
            this.compareRequestController = controller;
            const banner = $('comparability-banner');
            banner.className = 'comparability-banner';
            banner.textContent = 'REFRESHING COMPARISON AT CURRENT PROGRESS…';
            try {
                const query = new URLSearchParams({
                    left_run_id: leftRunId,
                    right_run_id: rightRunId,
                    progress: String(requestedProgress),
                });
                const result = await this.fetchJson(
                    `${API}/compare?${query}`, { signal: controller.signal },
                );
                if (
                    controller.signal.aborted
                    || this.currentView !== 'compare'
                    || requestId !== this.compareRequestId
                    || this.runId !== leftRunId
                    || this.compareRunId !== rightRunId
                ) return;
                this.compareData = result;
                this.renderComparison(result);
                this.renderTimeline();
            } catch (error) {
                if (
                    error.name === 'AbortError'
                    || this.currentView !== 'compare'
                    || requestId !== this.compareRequestId
                    || this.runId !== leftRunId
                    || this.compareRunId !== rightRunId
                ) return;
                banner.className = 'comparability-banner warning';
                banner.textContent = 'COMPARISON REFRESH FAILED · RETRY OR CHOOSE ANOTHER RUN';
                this.flashError(error.message);
            } finally {
                if (requestId === this.compareRequestId) this.compareRequestController = null;
            }
        }

        async forkCurrentRun() {
            if (!this.runId || this.cursorSeq < 0 || this.currentView === 'compare') return;
            const button = $('fork-run');
            const original = button.textContent;
            button.disabled = true;
            button.textContent = 'FORKING…';
            try {
                const result = await this.fetchJson(`${API}/runs/${encodeURIComponent(this.runId)}/fork`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ at_seq: this.cursorSeq }),
                });
                this.switchView('world');
                await this.loadRuns(result.run_id);
            } catch (error) {
                this.flashError(`Fork failed: ${error.message}`);
            } finally {
                button.textContent = original;
                button.disabled = false;
            }
        }

        renderComparison(result) {
            const comparability = result.comparability;
            const banner = $('comparability-banner');
            banner.className = `comparability-banner ${comparability.controlled ? '' : 'warning'}`;
            banner.textContent = comparability.controlled
                ? `CONTROLLED KEYS MATCH · project ${comparability.shared_project_ids.join(', ')} · task ${comparability.shared_task_ids.join(', ')}`
                : comparability.warnings.join(' ');
            this.renderCompareSide($('compare-left'), result.left, 'LEFT', '#5ce0ce');
            this.renderCompareSide($('compare-right'), result.right, 'RIGHT', '#c692ff');
            this.renderCompareDelta(result);
        }

        renderCompareSide(container, side, label, color) {
            const manifest = this.runs.find(run => run.run_id === side.run_id);
            const summary = side.summary;
            const runIdLabel = this.runIdLabels.get(side.run_id);
            const title = formatRunTitle(manifest || { run_id: side.run_id }, runIdLabel);
            const displayId = identityField(runIdLabel || shortId(side.run_id)) || 'UNKNOWN';
            const status = textField(summary.run_status, 32).toUpperCase() || 'UNKNOWN';
            const mechanisms = Object.entries(summary.mechanisms || {});
            const metrics = summary.metrics || {};
            const metricKeys = [
                'events', 'model_requests_dispatched', 'model_response_first_chunk_events',
                'model_response_chunk_events', 'model_calls_completed', 'model_calls_failed',
                'tool_calls', 'agents', 'context_used_tokens',
                'memory_hits', 'memory_writes', 'compactions', 'compaction_tokens_removed',
                'handoffs', 'checkpoints', 'open_errors', 'input_tokens', 'output_tokens',
                'cost_usd', 'duration_ms_sum',
            ].filter(key => key in metrics);
            const metricLabels = {
                model_requests_dispatched: 'MODEL REQUESTS DISPATCHED',
                model_response_first_chunk_events: 'FIRST CHUNK MARKERS',
                model_response_chunk_events: 'MODEL RESPONSE CHUNKS',
                model_calls_completed: 'COMPLETED MODEL CALLS',
                model_calls_failed: 'FAILED MODEL CALLS',
            };
            const measurementLabels = {
                'model_call.input_tokens': 'MODEL INPUT TOKENS',
                'model_call.output_tokens': 'MODEL OUTPUT TOKENS',
                'model_call.cached_tokens': 'MODEL CACHED TOKENS',
                'model_call.total_tokens': 'MODEL TOTAL TOKENS',
                'model_call.duration_ms': 'MODEL CALL SPAN TIME',
                'model_call.cost_usd': 'MODEL COST',
                'tool.duration_ms': 'TOOL CALL SPAN TIME',
                'code_call.duration_ms': 'CODE CALL SPAN TIME',
                'compaction.duration_ms': 'COMPACTION SPAN TIME',
                'run.elapsed_ms': 'RUN ELAPSED',
            };
            const measurementRows = [
                ...Object.entries(summary.measurements || {}).map(([key, value]) => ({ key, origin: 'aggregate', value })),
                ...Object.entries(summary.calculated_measurements || {}).map(([key, value]) => ({ key, origin: 'calculated', value })),
            ].sort((left, right) => `${left.key}:${left.origin}`.localeCompare(`${right.key}:${right.origin}`, 'en-US'));
            const measurementValue = row => {
                const measurement = row.value || {};
                const label = row.origin === 'calculated' ? 'CALCULATED' : String(measurement.status || 'not_observed').toUpperCase();
                if (measurement.status !== 'available' || !isSafeMeasurementValue(measurement.value)) {
                    const reason = (measurement.conflict_reasons || [])[0];
                    return `${label}${reason ? ` · ${reason}` : ''}`;
                }
                const value = formatMeasurementValue({
                    status: 'available', value: measurement.value, unit: measurement.unit,
                });
                const contract = `${String(measurement.scope || 'unknown').replaceAll('_', ' ').toUpperCase()} · ${String(measurement.aggregation || 'unknown').toUpperCase()}`;
                if (row.origin === 'calculated') {
                    const calculation = String(measurement.calculation || '')
                        .replaceAll('_', ' ').replaceAll('.', ' ').toUpperCase();
                    return `${value} · CALCULATED · ${calculation} · EXPLICIT ${String(measurement.explicit_consistency || 'not_observed').replaceAll('_', ' ').toUpperCase()}`;
                }
                if (row.key === 'model_call.cost_usd') {
                    const estimate = measurement.estimated_values?.length === 1
                        ? (measurement.estimated_values[0] ? 'ESTIMATED' : 'MEASURED')
                        : 'ESTIMATE STATUS MIXED';
                    return `${value} · ${contract} · ${estimate} · BASIS ${(measurement.basis_values || []).join(' + ') || 'NOT OBSERVED'}`;
                }
                return `${value} · ${contract}`;
            };
            const domains = Object.entries(summary.domain_counts || {}).sort((a, b) => b[1] - a[1]).slice(0, 10);
            const domainMax = Math.max(...domains.map(item => item[1]), 1);
            container.style.setProperty('--side-color', color);
            container.innerHTML = `
                <header class="compare-run-head">
                    <span>${esc(label)} · ${esc(status)}</span>
                    <h2>${esc(title)}</h2>
                    <p>${esc(textField((summary.frameworks || []).join(', '), 160) || 'framework not declared')} · ${esc(displayId)}</p>
                </header>
                <div class="compare-mechanisms">
                    ${mechanisms.map(([name, enabled]) => {
                        const observedState = enabled === true ? 'true' : enabled === false ? 'false' : 'not_observed';
                        const label = enabled === true ? 'ON' : enabled === false ? 'OFF' : 'NOT OBSERVED';
                        return `<div class="mechanism-cell ${enabled === true ? 'on' : ''}" data-mechanism="${esc(name)}" data-enabled="${observedState}"><i></i><span>${esc(name.toUpperCase())}</span><b>${label}</b></div>`;
                    }).join('')}
                </div>
                <dl class="compare-metrics">
                    ${metricKeys.map(key => `<div data-metric="${esc(key)}"><dt>${esc(metricLabels[key] || key.replaceAll('_', ' ').toUpperCase())}</dt><dd>${esc(metrics[key] == null ? 'NOT OBSERVED' : humanNumber(metrics[key]))}</dd></div>`).join('')}
                    ${measurementRows.map(row => `<div data-measurement="${esc(row.key)}" data-origin="${esc(row.origin)}"><dt>${esc(measurementLabels[row.key] || row.key.toUpperCase())}${row.origin === 'calculated' ? ' (CALCULATED)' : ''}</dt><dd>${esc(measurementValue(row))}</dd></div>`).join('')}
                </dl>
                <section class="domain-chart">
                    <h3>EVENT DOMAIN DENSITY</h3>
                    ${domains.map(([name, count]) => `<div class="domain-row"><span>${esc(name)}</span><i><b style="width:${count / domainMax * 100}%"></b></i><em>${count}</em></div>`).join('')}
                </section>`;
        }

        renderCompareDelta(result) {
            const metricRows = (result.metric_differences || [])
                .filter(item => item.comparison === 'availability' || item.delta !== 0)
                .sort((a, b) => (b.comparison === 'availability') - (a.comparison === 'availability')
                    || Math.abs(b.delta || 0) - Math.abs(a.delta || 0))
                .slice(0, 12);
            const measurementRows = (result.measurement_differences || [])
                .filter(item => item.comparison !== 'numeric' || item.delta !== 0)
                .sort((left, right) => {
                    const priority = { not_comparable: 0, availability: 1, numeric: 2 };
                    return (priority[left.comparison] ?? 3) - (priority[right.comparison] ?? 3)
                        || Math.abs(right.delta || 0) - Math.abs(left.delta || 0)
                        || String(left.measurement).localeCompare(String(right.measurement), 'en-US');
                })
                .slice(0, 12);
            const eventRows = (result.event_type_differences || []).slice(0, 12);
            const deltaText = value => `${value > 0 ? '+' : ''}${humanNumber(value)}`;
            const metricLabel = key => ({
                model_response_chunk_events: 'MODEL RESPONSE CHUNKS',
                model_calls_completed: 'COMPLETED MODEL CALLS',
                model_calls_failed: 'FAILED MODEL CALLS',
            }[key] || key.replaceAll('_', ' ').toUpperCase());
            const metricDifference = item => item.comparison === 'availability'
                ? `${metricLabel(item.metric)} · OBSERVED ${item.left == null ? 'RIGHT' : 'LEFT'} ONLY`
                : `${metricLabel(item.metric)} · ${deltaText(item.delta)}`;
            const measurementDifference = item => {
                const origin = item.origin === 'calculated' ? ' · CALCULATED' : '';
                const label = `${String(item.measurement).replaceAll('_', ' ').replaceAll('.', ' ').toUpperCase()}${origin}`;
                if (item.comparison === 'not_comparable') return `${label} · NOT COMPARABLE · ${item.reason}`;
                if (item.comparison === 'availability') return `${label} · ${item.reason.toUpperCase()}`;
                return `${label} · ${deltaText(item.delta)} ${String(item.left_contract?.unit || '').toUpperCase()}`;
            };
            $('compare-delta').innerHTML = `
                <header class="compare-delta-head"><strong>Δ DIFFERENCE</strong><span>right minus left · ${(result.progress * 100).toFixed(1)}% progress</span></header>
                <section class="delta-section">
                    <h3><span>METRICS</span><b>${metricRows.length}</b></h3>
                    <div class="delta-list">${metricRows.length ? metricRows.map(item => `<div class="delta-row ${item.comparison === 'availability' ? 'availability' : ''}"><span>${esc(metricDifference(item))}</span><b>${item.comparison === 'availability' ? '↔' : esc(deltaText(item.delta))}</b></div>`).join('') : '<div class="delta-empty">No observed numeric or availability differences</div>'}</div>
                </section>
                <section class="delta-section">
                    <h3><span>SAFE MEASUREMENTS</span><b>${measurementRows.length}</b></h3>
                    <div class="delta-list">${measurementRows.length ? measurementRows.map(item => `<div class="delta-row ${item.comparison !== 'numeric' ? 'availability' : ''}" data-measurement="${esc(item.measurement)}" data-origin="${esc(item.origin)}" data-comparison="${esc(item.comparison)}"><span>${esc(measurementDifference(item))}</span><b>${item.comparison === 'not_comparable' ? 'NOT COMPARABLE' : item.comparison === 'availability' ? '↔' : esc(deltaText(item.delta))}</b></div>`).join('') : '<div class="delta-empty">Same available measurement values and contracts</div>'}</div>
                </section>
                <section class="delta-section">
                    <h3><span>EVENT TYPES</span><b>${eventRows.length}</b></h3>
                    <div class="delta-list">${eventRows.length ? eventRows.map(item => `<div class="delta-row"><span>${esc(item.event_type)}</span><b>${esc(deltaText(item.delta))}</b></div>`).join('') : '<div class="delta-empty">Same event vocabulary at this progress</div>'}</div>
                </section>`;
        }

        togglePlayback() { this.playTimer ? this.stopPlayback() : this.startPlayback(); }

        startPlayback() {
            if (this.currentView === 'compare') {
                if (!this.compareRunId) return;
                if (this.compareProgress >= 1) this.compareProgress = 0;
                $('play-toggle').textContent = 'Ⅱ';
                $('play-toggle').setAttribute('aria-pressed', 'true');
                const tickCompare = () => {
                    if (this.compareProgress >= 1) return this.stopPlayback();
                    this.loadComparison(Math.min(1, this.compareProgress + .025));
                };
                tickCompare();
                this.playTimer = setInterval(tickCompare, Number($('play-speed').value));
                return;
            }
            if (this.headSeq < 0) return;
            if (this.cursorSeq >= this.headSeq) this.gotoSeq(0);
            this.setFollow(false);
            $('play-toggle').textContent = 'Ⅱ';
            $('play-toggle').setAttribute('aria-pressed', 'true');
            const tick = async () => {
                if (this.cursorSeq >= this.headSeq) return this.stopPlayback();
                await this.gotoSeq(this.cursorSeq + 1);
            };
            tick();
            this.playTimer = setInterval(tick, Number($('play-speed').value));
        }

        stopPlayback() {
            if (this.playTimer) clearInterval(this.playTimer);
            this.playTimer = null;
            $('play-toggle').textContent = '▶';
            $('play-toggle').setAttribute('aria-pressed', 'false');
        }

        setFollow(value, render = true) {
            this.followLive = Boolean(value);
            if (render) this.renderTimeline();
        }

        openStream() {
            if (STATIC_CAPTURE || !this.runId || !window.EventSource) return;
            this.closeStream();
            const url = `${API}/runs/${encodeURIComponent(this.runId)}/stream?after_seq=${this.headSeq}`;
            this.eventSource = new EventSource(url);
            this.eventSource.addEventListener('runtime-event', message => {
                try {
                    const event = JSON.parse(message.data);
                    this.eventsById.set(event.event_id, event);
                    this.events.push(event);
                    this.events.sort((a, b) => (a.clock.ingest_seq ?? 0) - (b.clock.ingest_seq ?? 0));
                    this.headSeq = Math.max(this.headSeq, event.clock.ingest_seq ?? -1);
                    if (
                        this.currentView === 'compare'
                        || RUN_LIFECYCLE_EVENT_TYPES.has(event.event_type)
                    ) {
                        this.scheduleManifestRefresh();
                    }
                    if (this.followLive) this.scheduleHeadRefresh();
                    else this.renderTimelineTicks();
                } catch (error) {
                    console.warn('Invalid SSE event', error);
                }
            });
            this.eventSource.addEventListener('gap', () => this.reloadCurrentRun());
            this.eventSource.onopen = () => this.setConnection('connected', 'LEDGER CONNECTED');
            this.eventSource.onerror = () => this.setConnection('error', 'STREAM RETRYING');
        }

        openCompareStream() {
            this.closeCompareStream();
            if (
                STATIC_CAPTURE
                || this.currentView !== 'compare'
                || !this.compareRunId
                || !window.EventSource
            ) return;
            const runId = this.compareRunId;
            const manifest = this.runs.find(run => run.run_id === runId);
            const afterSeq = Math.max(Number(manifest?.event_count || 0) - 1, -1);
            const source = new EventSource(
                `${API}/runs/${encodeURIComponent(runId)}/stream?after_seq=${afterSeq}`,
            );
            this.compareEventSource = source;
            source.addEventListener('runtime-event', message => {
                if (this.currentView !== 'compare' || this.compareRunId !== runId) return;
                try {
                    const event = JSON.parse(message.data);
                    if (event?.event_type) this.scheduleManifestRefresh();
                } catch (error) {
                    console.warn('Invalid Compare SSE event', error);
                }
            });
            source.addEventListener('gap', () => this.scheduleManifestRefresh(0));
        }

        closeCompareStream() {
            if (this.compareEventSource) this.compareEventSource.close();
            this.compareEventSource = null;
        }

        scheduleHeadRefresh() {
            clearTimeout(this.headRefreshTimer);
            this.headRefreshTimer = setTimeout(async () => {
                if (!this.followLive || !this.runId) return;
                const runId = this.runId;
                if (this.worldRequest) this.worldRequest.abort();
                const controller = new AbortController();
                const requestId = ++this.worldRequestId;
                this.worldRequest = controller;
                try {
                    const world = await this.fetchJson(
                        `${API}/runs/${encodeURIComponent(runId)}/world`,
                        { signal: controller.signal },
                    );
                    if (
                        controller.signal.aborted
                        || this.runId !== runId
                        || this.worldRequestId !== requestId
                    ) return;
                    this.applyWorld(world);
                    this.renderTimelineTicks();
                } catch (error) {
                    if (
                        error.name !== 'AbortError'
                        && this.runId === runId
                        && this.worldRequestId === requestId
                    ) console.warn(error);
                } finally {
                    if (this.worldRequestId === requestId) this.worldRequest = null;
                }
            }, 90);
        }

        cancelManifestRefresh() {
            clearTimeout(this.manifestRefreshTimer);
            this.manifestRefreshTimer = null;
            this.manifestRefreshRequestId += 1;
            if (this.manifestRefreshController) this.manifestRefreshController.abort();
            this.manifestRefreshController = null;
        }

        scheduleManifestRefresh(delay = 90) {
            clearTimeout(this.manifestRefreshTimer);
            if (this.manifestRefreshController) this.manifestRefreshController.abort();
            const runId = this.runId;
            const requestId = ++this.manifestRefreshRequestId;
            this.manifestRefreshTimer = setTimeout(async () => {
                this.manifestRefreshTimer = null;
                if (
                    !runId
                    || this.runId !== runId
                    || this.manifestRefreshRequestId !== requestId
                ) return;
                const controller = new AbortController();
                this.manifestRefreshController = controller;
                try {
                    const response = await this.fetchJson(
                        `${API}/runs?limit=500`,
                        { signal: controller.signal },
                    );
                    if (
                        controller.signal.aborted
                        || this.runId !== runId
                        || this.manifestRefreshRequestId !== requestId
                    ) return;
                    const nextRuns = response.items || [];
                    const requiredRunIds = [
                        runId,
                        this.currentView === 'compare' ? this.compareRunId : null,
                    ].filter(Boolean);
                    const missingRunIds = requiredRunIds.filter(
                        id => !nextRuns.some(run => run.run_id === id),
                    );
                    if (missingRunIds.length) {
                        this.markRunLabelsStale(missingRunIds);
                        console.warn('Run manifest refresh omitted an active selector; keeping prior labels');
                        return;
                    }
                    this.staleRunIds.clear();
                    this.runs = nextRuns;
                    this.renderRunOptions(runId);
                    if (this.currentView === 'compare') {
                        await this.loadComparison(this.compareProgress);
                    }
                } catch (error) {
                    if (
                        error.name !== 'AbortError'
                        && this.runId === runId
                        && this.manifestRefreshRequestId === requestId
                    ) {
                        this.markRunLabelsStale([
                            runId, this.currentView === 'compare' ? this.compareRunId : null,
                        ]);
                        console.warn('Run manifest refresh failed', error);
                    }
                } finally {
                    if (this.manifestRefreshRequestId === requestId) {
                        this.manifestRefreshTimer = null;
                        this.manifestRefreshController = null;
                    }
                }
            }, delay);
        }

        markRunLabelsStale(runIds) {
            (runIds || []).filter(Boolean).forEach(runId => this.staleRunIds.add(runId));
            if (this.runId && this.runs.some(run => run.run_id === this.runId)) {
                this.renderRunOptions(this.runId);
            }
            if (this.currentView === 'compare') {
                const banner = $('comparability-banner');
                banner.className = 'comparability-banner warning';
                banner.textContent = 'RUN IDENTITY SNAPSHOT STALE · RETRYING ON THE NEXT RUNTIME EVENT OR REFRESH';
            }
        }

        closeStream() {
            if (this.eventSource) this.eventSource.close();
            this.eventSource = null;
        }

        async reloadCurrentRun() {
            if (this.runId) await this.selectRun(this.runId);
        }

        setConnection(state, label) {
            const element = $('connection-state');
            const changed = element.dataset.state !== state || $('connection-label').textContent !== label;
            element.dataset.state = state;
            $('connection-label').textContent = label;
            if (changed && ['error', 'offline'].includes(state)) {
                this.announceStatus(`Ledger transport ${label.toLocaleLowerCase('en-US')}.`);
            }
        }

        showEmpty(value, message = null, title = null) {
            const empty = $('world-empty');
            empty.hidden = !value;
            if (!value) return;
            if (title !== null) empty.querySelector('h1').textContent = title;
            if (message !== null) empty.querySelector('p').textContent = message;
            empty.querySelector('.empty-actions').hidden = title !== null;
        }

        relativeTime(event) {
            if (!event?.clock?.occurred_at || !this.events.length) return 'T+00:00.000';
            const first = this.events[0]?.clock?.occurred_at;
            const delta = Math.max(new Date(event.clock.occurred_at) - new Date(first), 0);
            const minutes = Math.floor(delta / 60000);
            const seconds = Math.floor((delta % 60000) / 1000);
            const milliseconds = Math.floor(delta % 1000);
            return `T+${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}.${String(milliseconds).padStart(3, '0')}`;
        }

        onKey(event) {
            if (['INPUT', 'SELECT', 'TEXTAREA'].includes(event.target.tagName)) return;
            if (event.code === 'Space') { event.preventDefault(); this.togglePlayback(); }
            if (event.key === 'ArrowLeft') {
                this.currentView === 'compare'
                    ? this.loadComparison(Math.max(0, this.compareProgress - .025))
                    : this.gotoSeq(Math.max(0, this.cursorSeq - 1));
            }
            if (event.key === 'ArrowRight') {
                this.currentView === 'compare'
                    ? this.loadComparison(Math.min(1, this.compareProgress + .025))
                    : this.gotoSeq(Math.min(this.headSeq, this.cursorSeq + 1));
            }
            if (event.key.toLowerCase() === 'l' && this.currentView !== 'compare') {
                this.setFollow(true); this.gotoSeq(this.headSeq);
            }
        }

        openInspectorOnMobile() {
            if (window.innerWidth <= 930) document.querySelector('.inspector').classList.add('open');
        }

        flashError(message) {
            const tooltip = $('canvas-tooltip');
            tooltip.innerHTML = `<b style="color:#ff5c57">ERROR</b><span>${esc(message)}</span>`;
            tooltip.style.left = '16px'; tooltip.style.top = '70px'; tooltip.hidden = false;
            this.announceStatus(`Error: ${textField(message, 170) || 'unknown error'}`);
            setTimeout(() => { if (!this.canvas.hovered) tooltip.hidden = true; }, 4500);
        }

        announceStatus(message) {
            const safe = textField(message, 220);
            if (!safe || safe === this.lastAnnouncement) return;
            this.lastAnnouncement = safe;
            $('anthill-live-status').textContent = safe;
        }

        async fetchJson(url, options = {}) {
            const response = await fetch(url, options);
            if (!response.ok) {
                let detail = `${response.status} ${response.statusText}`;
                try {
                    const body = await response.json();
                    detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail || body);
                } catch (_) { /* keep status */ }
                throw new Error(detail);
            }
            return response.json();
        }
    }

    window.addEventListener('DOMContentLoaded', () => {
        if (STATIC_CAPTURE) document.body.classList.add('static-capture');
        window.anthillApp = new AnthillApp();
    });
})();

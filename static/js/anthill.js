(() => {
    'use strict';

    const API = '/api/anthill';
    const STATIC_CAPTURE = new URLSearchParams(window.location.search).has('static');
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
        { key: 'meter_room', label: 'METER ROOM', sub: 'tokens / latency / cost', x: 848, y: 64, w: 242, h: 140, color: '#f5d060' },
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
    const truthColor = level => TRUTH_COLORS[level] || '#789489';
    const shortId = value => value ? (value.length > 19 ? `${value.slice(0, 8)}…${value.slice(-7)}` : value) : '—';
    const eventFamily = type => String(type || '').split('.')[0];

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
            this.entities = new Map();
            this.hitRegions = [];
            this.hovered = null;
            this.selectedEventId = null;
            this.lastFrame = performance.now();
            this.reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
            this.canvas.addEventListener('mousemove', event => this.onPointerMove(event));
            this.canvas.addEventListener('mouseleave', () => this.clearHover());
            this.canvas.addEventListener('click', event => this.onClick(event));
            if (STATIC_CAPTURE) this.draw(performance.now(), 1);
            else requestAnimationFrame(time => this.frame(time));
        }

        setWorld(world) {
            this.world = world || null;
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
            if (STATIC_CAPTURE) this.draw(performance.now(), 1);
        }

        setSelected(eventId) {
            this.selectedEventId = eventId;
        }

        frame(time) {
            const delta = Math.min((time - this.lastFrame) / 16.67, 3);
            this.lastFrame = time;
            this.draw(time, delta);
            requestAnimationFrame(next => this.frame(next));
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
            const lastEvent = [...(state?.recent_events || [])].reverse().find(event => event.zone === zone.key);
            const level = lastEvent?.truth?.level || 'declared';
            const confidence = lastEvent?.truth?.confidence ?? 1;
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
            ctx.font = 'bold 10px "Cascadia Mono", monospace';
            ctx.textBaseline = 'top';
            ctx.fillText(zone.label, zone.x + 19, zone.y + 7);
            ctx.fillStyle = '#58756a';
            ctx.font = '7px "Cascadia Mono", monospace';
            ctx.fillText(zone.sub.toUpperCase(), zone.x + 19, zone.y + 19);

            if (activity > 0) {
                ctx.fillStyle = zone.color;
                ctx.fillRect(zone.x + zone.w - 27, zone.y + 10, 5, 5);
                ctx.fillStyle = '#bed0c7';
                ctx.font = '8px "Cascadia Mono", monospace';
                ctx.fillText(String(activity), zone.x + zone.w - 17, zone.y + 8);
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
                for (let index = 0; index < 3; index += 1) {
                    ctx.fillStyle = '#142a24'; ctx.fillRect(23 + index * 61, 10, 49, 62);
                    ctx.strokeStyle = '#355247'; ctx.strokeRect(23.5 + index * 61, 10.5, 48, 61);
                    ctx.fillStyle = color; ctx.fillRect(32 + index * 61, 58 - ((index + 1) * 9), 31, 7 + index * 9);
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
                const values = [memory.working || 0, memory.episodic || 0, memory.semantic || 0];
                for (let index = 0; index < 3; index += 1) {
                    ctx.fillStyle = '#152c25'; ctx.fillRect(24 + index * 61, 13, 48, 59);
                    ctx.strokeStyle = color; ctx.strokeRect(24.5 + index * 61, 13.5, 47, 58);
                    const blocks = Math.min(values[index], 5);
                    for (let block = 0; block < blocks; block += 1) {
                        ctx.fillStyle = this.alpha(color, .42 + block * .1);
                        ctx.fillRect(31 + index * 61, 61 - block * 9, 34, 6);
                    }
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
                    ctx.fillStyle = color; ctx.font = '8px "Cascadia Mono", monospace';
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
                ctx.fillStyle = zone.color; ctx.font = '8px "Cascadia Mono", monospace';
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
                const phase = this.reducedMotion ? .55 : ((time / 1150) + index * .17) % 1;
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
            const sprites = [...this.entities.values()].sort((a, b) => this.entityPriority(a.entity) - this.entityPriority(b.entity)).slice(0, 28);
            for (const sprite of sprites) {
                const smoothing = this.reducedMotion ? 1 : 1 - Math.pow(.84, delta);
                sprite.x += (sprite.targetX - sprite.x) * smoothing;
                sprite.y += (sprite.targetY - sprite.y) * smoothing;
                const bob = this.reducedMotion ? 0 : Math.round(Math.sin(time / 210 + sprite.bob));
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
                    ctx.fillStyle = 'rgba(4,10,9,.88)'; ctx.fillRect(x - 2 - label.length * 2.7, y + 13, label.length * 5.4 + 4, 11);
                    ctx.fillStyle = entity.active ? '#c8f560' : '#a8beb4'; ctx.font = '7px "Cascadia Mono", monospace';
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
            ctx.setLineDash(level === 'inferred' ? [3, 5] : []);
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
            if (entity.kind === 'agent') return 0;
            if (entity.active) return 1;
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
                : `${this.world?.zone_activity?.[region.zone.key] || 0} active · click for evidence`;
            tooltip.innerHTML = `<b>${esc(title)}</b><span>${esc(detail)}</span>`;
            tooltip.hidden = false;
            const left = clamp(event.clientX - rect.left + 14, 8, rect.width - 270);
            const top = clamp(event.clientY - rect.top + 14, 8, rect.height - 70);
            tooltip.style.left = `${left}px`;
            tooltip.style.top = `${top}px`;
        }

        clearHover() {
            this.hovered = null;
            $('canvas-tooltip').hidden = true;
            this.canvas.style.cursor = 'crosshair';
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
            this.runId = null;
            this.manifest = null;
            this.worldResponse = null;
            this.world = null;
            this.events = [];
            this.eventsById = new Map();
            this.headSeq = -1;
            this.cursorSeq = -1;
            this.followLive = true;
            this.playTimer = null;
            this.eventSource = null;
            this.worldRequest = null;
            this.selectedEventId = null;
            this.causalDirection = 'ancestors';
            this.currentView = 'world';
            this.compareRunId = null;
            this.compareProgress = 1;
            this.compareData = null;
            this.compareRequestId = 0;
            this.refreshTimer = null;
            this.canvas = new AnthillCanvas($('anthill-canvas'), {
                onEvent: id => this.selectEvent(id),
                onZone: zone => this.selectZone(zone),
            });
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
            $('compare-run-select').addEventListener('change', event => {
                this.compareRunId = event.target.value;
                this.loadComparison(this.compareProgress);
            });
            $('truth-help').addEventListener('click', () => $('truth-dialog').showModal());

            document.querySelectorAll('.inspector-tabs button').forEach(button => button.addEventListener('click', () => this.switchTab(button.dataset.tab)));
            document.querySelectorAll('.view-button[data-view]').forEach(button => button.addEventListener('click', () => this.switchView(button.dataset.view)));
            document.querySelectorAll('.causal-controls button').forEach(button => button.addEventListener('click', () => {
                this.causalDirection = button.dataset.direction;
                document.querySelectorAll('.causal-controls button').forEach(item => item.classList.toggle('active', item === button));
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
            $('follow-live').addEventListener('click', () => {
                this.setFollow(!this.followLive);
                if (this.followLive) this.gotoSeq(this.headSeq);
            });
            $('fork-run').addEventListener('click', () => this.forkCurrentRun());
            window.addEventListener('keydown', event => this.onKey(event));
        }

        async loadRuns(preferredId = null) {
            try {
                const response = await this.fetchJson(`${API}/runs?limit=500`);
                this.runs = response.items || [];
                const select = $('run-select');
                select.innerHTML = '';
                if (!this.runs.length) {
                    select.append(new Option('事件账本为空', ''));
                    this.showEmpty(true);
                    this.setConnection('offline', 'NO RUNS');
                    return;
                }
                this.runs.forEach(run => {
                    const marker = run.synthetic ? '[DEMO] ' : '';
                    const title = run.title && run.title !== run.run_id ? run.title : shortId(run.run_id);
                    select.append(new Option(`${marker}${title} · ${run.event_count || 0} events`, run.run_id));
                });
                this.populateCompareRuns();
                const target = preferredId || this.runId || this.runs[0].run_id;
                select.value = target;
                await this.selectRun(target);
            } catch (error) {
                this.setConnection('error', 'API ERROR');
                this.showEmpty(true, error.message);
            }
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

        async selectRun(runId) {
            if (!runId) return;
            this.closeStream();
            this.stopPlayback();
            this.runId = runId;
            this.manifest = this.runs.find(run => run.run_id === runId) || null;
            $('run-select').value = runId;
            this.showEmpty(false);
            this.setConnection('history', 'LOADING LEDGER');
            try {
                const [world, eventPage, integrity] = await Promise.all([
                    this.fetchJson(`${API}/runs/${encodeURIComponent(runId)}/world`),
                    this.fetchJson(`${API}/runs/${encodeURIComponent(runId)}/events?limit=5000`),
                    this.fetchJson(`${API}/runs/${encodeURIComponent(runId)}/integrity`),
                ]);
                if (this.runId !== runId) return;
                this.events = eventPage.items || [];
                this.eventsById = new Map(this.events.map(event => [event.event_id, event]));
                this.headSeq = Number(world.head_seq ?? -1);
                this.cursorSeq = this.headSeq;
                this.setFollow(true, false);
                this.applyWorld(world);
                this.renderIntegrity(integrity);
                this.renderTimelineTicks();
                this.renderSyntheticBanner();
                this.openStream();
                if (this.currentView === 'compare') {
                    this.populateCompareRuns();
                    await this.loadComparison(this.compareProgress);
                }
            } catch (error) {
                this.setConnection('error', 'RUN LOAD FAILED');
                this.flashError(error.message);
            }
        }

        async gotoSeq(seq) {
            if (!this.runId || this.headSeq < 0) return;
            const target = clamp(Math.round(seq), 0, this.headSeq);
            if (target !== this.headSeq) this.setFollow(false);
            if (this.worldRequest) this.worldRequest.abort();
            this.worldRequest = new AbortController();
            try {
                const suffix = target === this.headSeq && this.followLive ? '' : `?at_seq=${target}`;
                const world = await this.fetchJson(`${API}/runs/${encodeURIComponent(this.runId)}/world${suffix}`, { signal: this.worldRequest.signal });
                this.applyWorld(world);
            } catch (error) {
                if (error.name !== 'AbortError') this.flashError(error.message);
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
            this.cursorSeq = Number(response.projected_seq ?? this.world.cursor_seq ?? -1);
            this.headSeq = Math.max(this.headSeq, Number(response.head_seq ?? -1));
            this.canvas.setWorld(this.world);
            this.renderRunSummary();
            this.renderTruthMix();
            this.renderCognition();
            this.renderChamberList();
            this.renderStatePanel();
            this.renderEventFeed();
            this.renderTimeline();
            const isHead = this.cursorSeq === this.headSeq;
            this.setConnection(isHead ? 'live' : 'history', isHead ? 'LEDGER CONNECTED' : 'HISTORICAL VIEW');
            $('world-mode').textContent = isHead ? 'HEAD / LIVE' : `TIME TRAVEL / SEQ ${this.cursorSeq}`;
        }

        renderRunSummary() {
            const state = this.world;
            $('run-title').textContent = this.manifest?.title || shortId(this.runId);
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
            const ratio = budget ? used / budget : 0;
            $('context-label').textContent = budget ? `${humanNumber(used)} / ${humanNumber(budget)}` : 'NO TELEMETRY';
            const fill = $('context-fill');
            fill.style.width = `${clamp(ratio * 100, 0, 100)}%`;
            fill.className = context.overflow ? 'overflow' : ratio >= .85 ? 'warning' : '';
            $('memory-working').textContent = this.world.memory?.working || 0;
            $('memory-episodic').textContent = this.world.memory?.episodic || 0;
            $('memory-semantic').textContent = this.world.memory?.semantic || 0;
            const jobs = Object.values(this.world.compactions || {});
            const job = jobs[jobs.length - 1];
            $('compact-status').textContent = job ? String(job.status).toUpperCase() : 'IDLE';
            $('compact-delta').textContent = job?.tokens_removed != null
                ? `${humanNumber(job.tokens_before)} → ${humanNumber(job.tokens_after)} · removed ${humanNumber(job.tokens_removed)} tokens`
                : '没有压缩记录';
        }

        renderChamberList() {
            const container = $('chamber-list');
            const state = this.world;
            container.innerHTML = '';
            for (const zone of ZONES) {
                const activity = state?.zone_activity?.[zone.key] || 0;
                const count = (state?.recent_events || []).filter(event => event.zone === zone.key).length;
                const button = document.createElement('button');
                button.type = 'button';
                button.className = `chamber-item ${activity > 0 ? 'active' : ''}`;
                button.style.setProperty('--chamber-color', zone.color);
                button.innerHTML = `<i></i><span>${esc(zone.label)}</span><b>${activity ? `${activity} LIVE` : count ? `${count} EVT` : '—'}</b>`;
                button.addEventListener('click', () => this.selectZone(zone.key));
                container.append(button);
            }
        }

        renderStatePanel() {
            const state = this.world;
            $('state-heading').textContent = `${String(state.run_status).toUpperCase()} · ${state.event_count} events`;
            $('state-subheading').textContent = `Reducer ${state.reducer_version} projected at ingest sequence ${state.cursor_seq}.`;
            const agents = Object.values(state.entities || {}).filter(entity => entity.kind === 'agent');
            const jobs = Object.values(state.compactions || {});
            const latestJob = jobs[jobs.length - 1];
            const context = state.context || {};
            const memory = state.memory || {};
            const blocks = [
                {
                    title: 'AGENTS', value: agents.length,
                    rows: agents.length ? agents.slice(0, 8).map(agent => [agent.name, `${agent.zone} · ${agent.status}`, agent.active ? 'good' : '']) : [['none observed', '—', '']],
                },
                {
                    title: 'CONTEXT MANIFEST', value: Object.keys(context.items || {}).length,
                    rows: [
                        ['budget', context.budget_tokens ? `${humanNumber(context.used_tokens)} / ${humanNumber(context.budget_tokens)} tokens` : 'not captured', context.overflow ? 'danger' : ''],
                        ['policy', context.policy || 'not captured', ''],
                        ['status', context.status || 'unknown', context.overflow ? 'danger' : 'good'],
                    ],
                },
                {
                    title: 'MEMORY OPERATIONS', value: memory.hits + memory.misses + memory.writes,
                    rows: [
                        ['hit / miss', `${memory.hits || 0} / ${memory.misses || 0}`, ''],
                        ['writes / evictions', `${memory.writes || 0} / ${memory.evictions || 0}`, ''],
                        ['conflicts', memory.conflicts || 0, memory.conflicts ? 'warning' : ''],
                    ],
                },
                {
                    title: 'LATEST COMPACTION', value: jobs.length,
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
                    <span class="event-copy"><strong><i></i>${esc(event.event_type)}</strong><small>${esc(event.summary || event.subject_id || event.zone)}</small></span>`;
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
                if (!event) event = await this.fetchJson(`${API}/runs/${encodeURIComponent(this.runId)}/events/${encodeURIComponent(eventId)}`);
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
            $('causal-graph').className = 'causal-graph empty-detail';
            $('causal-graph').textContent = '正在构建显式因果切片…';
            try {
                const graph = await this.fetchJson(`${API}/runs/${encodeURIComponent(this.runId)}/causal/${encodeURIComponent(eventId)}?direction=${this.causalDirection}&max_depth=20`);
                if (this.selectedEventId !== eventId) return;
                this.renderCausalGraph(graph);
            } catch (error) {
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
            document.querySelectorAll('.inspector-tabs button').forEach(button => button.classList.toggle('active', button.dataset.tab === tab));
            document.querySelectorAll('.inspector-panel').forEach(panel => panel.classList.toggle('active', panel.id === `${tab}-panel`));
            if (tab === 'causal' && this.selectedEventId) this.loadCausality(this.selectedEventId);
            this.openInspectorOnMobile();
        }

        switchView(view) {
            this.currentView = view;
            document.querySelectorAll('.view-button[data-view]').forEach(button => button.classList.toggle('active', button.dataset.view === view));
            const comparing = view === 'compare';
            $('app-shell').classList.toggle('compare-layout', comparing);
            $('world-stage').classList.toggle('compare-mode', comparing);
            $('compare-stage').hidden = !comparing;
            if (view === 'world') this.switchTab('state');
            if (view === 'causal') this.switchTab('causal');
            if (comparing) {
                this.stopPlayback();
                this.populateCompareRuns();
                this.loadComparison(this.compareProgress);
            } else {
                this.renderTimeline();
            }
        }

        populateCompareRuns() {
            const select = $('compare-run-select');
            if (!select) return;
            const candidates = this.runs.filter(run => run.run_id !== this.runId);
            select.innerHTML = '';
            candidates.forEach(run => {
                const marker = run.synthetic ? '[DEMO] ' : '';
                select.append(new Option(`${marker}${run.title || shortId(run.run_id)}`, run.run_id));
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

        async loadComparison(progress = this.compareProgress) {
            if (!this.runId || !this.compareRunId || this.runId === this.compareRunId) {
                $('comparability-banner').className = 'comparability-banner warning';
                $('comparability-banner').textContent = '需要至少两条不同的 run。可再创建一个展品或导入 OTLP trace。';
                this.renderTimeline();
                return;
            }
            this.compareProgress = clamp(progress, 0, 1);
            const requestId = ++this.compareRequestId;
            try {
                const query = new URLSearchParams({
                    left_run_id: this.runId,
                    right_run_id: this.compareRunId,
                    progress: String(this.compareProgress),
                });
                const result = await this.fetchJson(`${API}/compare?${query}`);
                if (this.currentView !== 'compare' || requestId !== this.compareRequestId) return;
                this.compareData = result;
                this.renderComparison(result);
                this.renderTimeline();
            } catch (error) {
                this.flashError(error.message);
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
            const mechanisms = Object.entries(summary.mechanisms || {});
            const metrics = summary.metrics || {};
            const metricKeys = [
                'events', 'model_calls', 'tool_calls', 'agents', 'context_used_tokens',
                'memory_hits', 'memory_writes', 'compactions', 'compaction_tokens_removed',
                'handoffs', 'checkpoints', 'open_errors', 'input_tokens', 'output_tokens',
                'cost_usd', 'duration_ms_sum',
            ].filter(key => key in metrics);
            const domains = Object.entries(summary.domain_counts || {}).sort((a, b) => b[1] - a[1]).slice(0, 10);
            const domainMax = Math.max(...domains.map(item => item[1]), 1);
            container.style.setProperty('--side-color', color);
            container.innerHTML = `
                <header class="compare-run-head">
                    <span>${esc(label)} · ${esc(summary.run_status.toUpperCase())}</span>
                    <h2>${esc(manifest?.title || shortId(side.run_id))}</h2>
                    <p>${esc((summary.frameworks || []).join(', ') || 'framework not declared')} · ${esc(shortId(side.run_id))}</p>
                </header>
                <div class="compare-mechanisms">
                    ${mechanisms.map(([name, enabled]) => `<div class="mechanism-cell ${enabled ? 'on' : ''}"><i></i><span>${esc(name.toUpperCase())}</span></div>`).join('')}
                </div>
                <dl class="compare-metrics">
                    ${metricKeys.map(key => `<dt>${esc(key)}</dt><dd>${esc(humanNumber(metrics[key]))}</dd>`).join('')}
                </dl>
                <section class="domain-chart">
                    <h3>EVENT DOMAIN DENSITY</h3>
                    ${domains.map(([name, count]) => `<div class="domain-row"><span>${esc(name)}</span><i><b style="width:${count / domainMax * 100}%"></b></i><em>${count}</em></div>`).join('')}
                </section>`;
        }

        renderCompareDelta(result) {
            const metricRows = (result.metric_differences || [])
                .filter(item => item.delta !== 0)
                .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))
                .slice(0, 12);
            const eventRows = (result.event_type_differences || []).slice(0, 12);
            const deltaText = value => `${value > 0 ? '+' : ''}${humanNumber(value)}`;
            $('compare-delta').innerHTML = `
                <header class="compare-delta-head"><strong>Δ DIFFERENCE</strong><span>right minus left · ${(result.progress * 100).toFixed(1)}% progress</span></header>
                <section class="delta-section">
                    <h3><span>METRICS</span><b>${metricRows.length}</b></h3>
                    <div class="delta-list">${metricRows.length ? metricRows.map(item => `<div class="delta-row"><span>${esc(item.metric)}</span><b>${esc(deltaText(item.delta))}</b></div>`).join('') : '<div class="delta-empty">No numeric differences</div>'}</div>
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
                    if (this.followLive) this.scheduleHeadRefresh();
                    else this.renderTimelineTicks();
                } catch (error) {
                    console.warn('Invalid SSE event', error);
                }
            });
            this.eventSource.addEventListener('gap', () => this.reloadCurrentRun());
            this.eventSource.onopen = () => this.setConnection(this.cursorSeq === this.headSeq ? 'live' : 'history', 'LEDGER CONNECTED');
            this.eventSource.onerror = () => this.setConnection('error', 'STREAM RETRYING');
        }

        scheduleHeadRefresh() {
            clearTimeout(this.headRefreshTimer);
            this.headRefreshTimer = setTimeout(async () => {
                if (!this.followLive || !this.runId) return;
                try {
                    const world = await this.fetchJson(`${API}/runs/${encodeURIComponent(this.runId)}/world`);
                    this.applyWorld(world);
                    this.renderTimelineTicks();
                } catch (error) { console.warn(error); }
            }, 90);
        }

        closeStream() {
            if (this.eventSource) this.eventSource.close();
            this.eventSource = null;
        }

        async reloadCurrentRun() {
            if (this.runId) await this.selectRun(this.runId);
        }

        setConnection(state, label) {
            $('live-state').dataset.state = state;
            $('live-label').textContent = label;
        }

        showEmpty(value, message = null) {
            $('world-empty').hidden = !value;
            if (message) $('world-empty').querySelector('p').textContent = message;
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
            setTimeout(() => { if (!this.canvas.hovered) tooltip.hidden = true; }, 4500);
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

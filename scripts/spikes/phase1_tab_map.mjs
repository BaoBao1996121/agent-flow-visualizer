import { readFileSync } from 'node:fs';

const html = readFileSync(new URL('../../static/anthill.html', import.meta.url), 'utf8');
const tabs = [...html.matchAll(/<button[^>]*data-tab="([^"]+)"/g)].map(match => match[1]);
const panels = [...html.matchAll(/<[^>]+class="[^"]*\binspector-panel\b[^"]*"[^>]*id="([^"]+)"/g)].map(match => match[1]);
const expected = tabs.map(tab => `${tab}-panel`);
if (tabs.length !== 4 || expected.some(panel => !panels.includes(panel))) throw new Error(JSON.stringify({ tabs, panels }));
console.log(`PASS tab/panel mapping: ${tabs.join(', ')}`);

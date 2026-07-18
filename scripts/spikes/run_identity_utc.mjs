const aware = '2026-07-17T16:30:00+08:00';
const unzoned = '2026-07-17T16:30:00';
const hasZone = value => /(?:Z|[+-]\d{2}:\d{2})$/i.test(value);
const date = new Date(aware);
const formatted = `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, '0')}-${String(date.getUTCDate()).padStart(2, '0')} ${String(date.getUTCHours()).padStart(2, '0')}:${String(date.getUTCMinutes()).padStart(2, '0')}Z`;

if (!hasZone(aware) || hasZone(unzoned)) throw new Error('timezone guard failed');
if (formatted !== '2026-07-17 08:30Z') throw new Error(formatted);
console.log('PASS: timezone-aware ingest labels normalize deterministically to UTC');

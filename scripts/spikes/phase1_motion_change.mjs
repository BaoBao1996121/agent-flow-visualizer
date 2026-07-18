import { chromium } from '@playwright/test';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ reducedMotion: 'reduce' });
await page.setContent('<body></body>');
await page.evaluate(() => {
  window.motionChanges = 0;
  const media = matchMedia('(prefers-reduced-motion: reduce)');
  document.body.dataset.initialMotion = String(media.matches);
  media.addEventListener('change', () => { window.motionChanges += 1; });
});
await page.emulateMedia({ reducedMotion: 'no-preference' });
await page.waitForFunction(() => window.motionChanges === 1);
const result = await page.evaluate(() => [document.body.dataset.initialMotion, matchMedia('(prefers-reduced-motion: reduce)').matches]);
await browser.close();
if (result[0] !== 'true' || result[1] !== false) throw new Error(`unexpected motion boundary: ${result}`);
console.log('PASS: reduced-motion media changes are observable without reload');

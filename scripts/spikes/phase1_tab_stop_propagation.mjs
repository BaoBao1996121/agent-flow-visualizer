import { chromium } from '@playwright/test';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.setContent('<button id="tab">STATE</button>');
await page.evaluate(() => {
  window.globalArrowHits = 0;
  window.addEventListener('keydown', () => { window.globalArrowHits += 1; });
  document.querySelector('#tab').addEventListener('keydown', event => event.stopPropagation());
});
await page.locator('#tab').press('ArrowRight');
const hits = await page.evaluate(() => window.globalArrowHits);
await browser.close();
if (hits !== 0) throw new Error(`global handler received ${hits} arrow events`);

import { chromium } from '@playwright/test';

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ reducedMotion: 'reduce' });
const page = await context.newPage();
await page.emulateMedia({ reducedMotion: 'reduce' });
await page.setContent(`<style>#room{clip-path:polygon(0 15%,100% 0,92% 100%,8% 90%)}#pulse{animation:p 1s infinite}@keyframes p{to{opacity:.2}}@media (prefers-reduced-motion: reduce){#pulse{animation:none}}</style><svg aria-label="trace"><path d="M0 0L20 20"/></svg><div id="room"></div><div id="pulse"></div>`);
const result = await page.evaluate(() => ({
  clip: CSS.supports('clip-path', 'polygon(0 0,100% 0,100% 100%)'),
  svg: document.querySelector('svg').getAttribute('aria-label'),
  animations: document.getAnimations().length,
}));
await browser.close();
if (!result.clip || result.svg !== 'trace' || result.animations !== 0) throw new Error(JSON.stringify(result));
console.log('PASS', result);

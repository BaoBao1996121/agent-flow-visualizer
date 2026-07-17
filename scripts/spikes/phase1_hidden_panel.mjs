import { chromium } from '@playwright/test';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.setContent(`
  <section role="tabpanel" id="visible">STATE</section>
  <section role="tabpanel" id="hidden" hidden>EVENT</section>
`);
const visualHidden = await page.locator('#hidden').isHidden();
const exposedPanels = await page.getByRole('tabpanel').count();
await browser.close();
if (!visualHidden || exposedPanels !== 1) throw new Error(JSON.stringify({ visualHidden, exposedPanels }));
console.log('PASS hidden panel is visual and accessibility-hidden');

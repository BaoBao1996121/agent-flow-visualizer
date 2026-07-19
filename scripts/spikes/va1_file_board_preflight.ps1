$root = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$uri = [System.Uri]::new((Join-Path $root "docs/STAGE_LOG.md")).AbsoluteUri
$script = @"
import { chromium } from 'playwright';
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
await page.goto('$uri');
const result = await page.evaluate(() => ({ protocol: location.protocol, grid: CSS.supports('display', 'grid'), mix: CSS.supports('color', 'color-mix(in srgb, red, blue)'), clip: CSS.supports('clip-path', 'polygon(0 0, 100% 0, 100% 100%)') }));
await browser.close();
if (result.protocol !== 'file:' || !result.grid || !result.mix || !result.clip) throw new Error(JSON.stringify(result));
console.log(JSON.stringify(result));
"@
node --input-type=module -e $script
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

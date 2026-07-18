import path from 'node:path';

import { defineConfig } from '@playwright/test';

const image = 'mcr.microsoft.com/playwright:v1.61.1-noble-amd64@sha256:cf0daee9b994042e011bc29f20cdff1a9f682a039b43fcd738f7d8a9d3bcd9d6';
const cliRequestsUpdate = process.argv.some(argument => (
  argument === '-u'
  || argument === '--update-snapshots'
  || argument.startsWith('--update-snapshots=')
));
const updateSnapshots = process.env.ANTHILL_UPDATE_VISUALS === '1' || cliRequestsUpdate;
if (updateSnapshots && (process.platform !== 'linux' || process.env.ANTHILL_VISUAL_IMAGE !== image)) {
  throw new Error('Visual goldens may only be updated in the pinned Linux container.');
}

const port = Number(process.env.ANTHILL_VISUAL_PORT || 8879);
const baseURL = `http://127.0.0.1:${port}`;
const python = process.env.PYTHON || 'python';
const dataDir = path.resolve('output', 'playwright', `visual-ledger-${process.pid}`);

export default defineConfig({
  testDir: 'tests/visual',
  outputDir: 'output/playwright/visual-results',
  snapshotPathTemplate: '{testDir}/goldens/{projectName}/{arg}{ext}',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: Boolean(process.env.CI),
  reporter: process.env.CI
    ? [['line'], ['html', { outputFolder: 'output/playwright/visual-report', open: 'never' }]]
    : 'line',
  updateSnapshots: updateSnapshots ? 'all' : 'none',
  expect: {
    toHaveScreenshot: {
      animations: 'disabled',
      caret: 'hide',
      maxDiffPixelRatio: 0.001,
      scale: 'css',
      threshold: 0.2,
    },
  },
  use: {
    baseURL,
    viewport: { width: 1600, height: 1000 },
    deviceScaleFactor: 1,
    locale: 'en-US',
    timezoneId: 'UTC',
    colorScheme: 'dark',
    reducedMotion: 'reduce',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
  },
  projects: [{ name: 'chromium-noble', use: { browserName: 'chromium' } }],
  webServer: {
    command: `${python} -m uvicorn server:app --host 127.0.0.1 --port ${port}`,
    url: `${baseURL}/api/anthill/schema`,
    env: { ...process.env, ANTHILL_DATA_DIR: dataDir, PYTHONUNBUFFERED: '1' },
    reuseExistingServer: false,
    timeout: 30_000,
    stdout: 'ignore',
    stderr: 'pipe',
  },
});

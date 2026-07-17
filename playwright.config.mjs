import path from 'node:path';

import { defineConfig, devices } from '@playwright/test';

const port = Number(process.env.ANTHILL_E2E_PORT || 8878);
const baseURL = `http://127.0.0.1:${port}`;
const python = process.env.PYTHON || 'python';
const dataDir = path.resolve('output', 'playwright', `ledger-${process.pid}`);

export default defineConfig({
  testDir: 'tests/browser',
  outputDir: 'output/playwright/test-results',
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  forbidOnly: Boolean(process.env.CI),
  failOnFlakyTests: Boolean(process.env.CI),
  reporter: process.env.CI
    ? [
        ['line'],
        ['html', { outputFolder: 'output/playwright/report', open: 'never' }],
      ]
    : 'line',
  use: {
    baseURL,
    viewport: { width: 1600, height: 1000 },
    colorScheme: 'dark',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1600, height: 1000 },
      },
    },
  ],
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

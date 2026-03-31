import { defineConfig, devices } from '@playwright/test';

const frontendHost = process.env.ADMIN_FRONTEND_HOST || '127.0.0.1';
const frontendPort = process.env.ADMIN_FRONTEND_PORT || '5175';
const baseURL = `http://${frontendHost}:${frontendPort}`;

export default defineConfig({
  testDir: '../tests/e2e',
  timeout: 30 * 1000,
  expect: {
    timeout: 5 * 1000
  },
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['html', { outputFolder: '../playwright-report-workflow' }],
    ['json', { outputFile: '../test-results-workflow.json' }],
    ['list']
  ],
  use: {
    baseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 10 * 1000,
    navigationTimeout: 30 * 1000
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] }
    }
  ],
  webServer: {
    command: `npm --prefix ../apps/admin-frontend run dev -- --host ${frontendHost} --port ${frontendPort}`,
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000
  }
});

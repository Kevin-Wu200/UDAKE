import { defineConfig, devices } from '@playwright/test';

const adminHost = process.env.ADMIN_FRONTEND_HOST || '127.0.0.1';
const adminPort = process.env.ADMIN_FRONTEND_PORT || '5175';
const adminBaseURL = (process.env.ADMIN_FRONTEND_URL || `http://${adminHost}:${adminPort}`).replace(/\/+$/, '');

export default defineConfig({
  testDir: '../tests/e2e',
  globalSetup: './playwright.global-setup.ts',
  testMatch: ['auth-workflow.admin.test.ts'],
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  timeout: 45 * 1000,
  expect: {
    timeout: 8 * 1000,
  },
  retries: process.env.CI ? 2 : 1,
  workers: process.env.CI ? 2 : undefined,
  reporter: [
    ['list'],
    ['html', { outputFolder: '../playwright-report-auth' }],
    ['json', { outputFile: '../test-results-auth.json' }],
    ['junit', { outputFile: '../test-results-auth.junit.xml' }],
  ],
  use: {
    baseURL: adminBaseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 12 * 1000,
    navigationTimeout: 35 * 1000,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: `npm run dev --prefix ../apps/admin-frontend -- --host ${adminHost} --port ${adminPort}`,
    url: adminBaseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000,
  },
});

import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright 测试配置
 */
const frontendHost = process.env.IPCONFIG || process.env.VITE_IPCONFIG || 'localhost';
const frontendPort = process.env.FRONTEND_PORT || process.env.VITE_FRONTEND_PORT || '5173';
const resolvedFrontendUrl = (process.env.FRONTEND_URL || process.env.BASE_URL || `http://${frontendHost}:${frontendPort}`).replace(/\/+$/, '');

export default defineConfig({
    testDir: '../tests/e2e',
    globalSetup: './playwright.global-setup.ts',
    fullyParallel: true,
    forbidOnly: !!process.env.CI,

    // 超时设置
    timeout: 45 * 1000,
    expect: {
        timeout: 8 * 1000
    },

    // 测试失败时重试
    retries: process.env.CI ? 2 : 1,

    // 并行运行测试
    workers: process.env.CI ? 2 : undefined,

    // 报告配置
    reporter: [
        ['html', { outputFolder: '../playwright-report' }],
        ['json', { outputFile: '../test-results.json' }],
        ['junit', { outputFile: '../test-results.junit.xml' }],
        ['list']
    ],

    // 共享配置
    use: {
        // 基础 URL
        baseURL: resolvedFrontendUrl,

        // 追踪
        trace: 'on-first-retry',

        // 截图
        screenshot: 'only-on-failure',

        // 视频
        video: 'retain-on-failure',

        // 超时
        actionTimeout: 12 * 1000,
        navigationTimeout: 35 * 1000
    },

    // 测试项目
    projects: [
        {
            name: 'chromium',
            use: { ...devices['Desktop Chrome'] },
        },
        {
            name: 'firefox',
            use: { ...devices['Desktop Firefox'] },
        },
        {
            name: 'webkit',
            use: { ...devices['Desktop Safari'] },
        },
        {
            name: 'Mobile Chrome',
            use: { ...devices['Pixel 5'] },
        },
        {
            name: 'Mobile Safari',
            use: { ...devices['iPhone 12'] },
        },
    ],

    // 本地开发服务器
    webServer: {
        command: 'npm run dev',
        url: resolvedFrontendUrl,
        reuseExistingServer: !process.env.CI,
        timeout: 120 * 1000,
    },
});

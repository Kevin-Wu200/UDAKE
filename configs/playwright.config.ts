import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright 测试配置
 */
export default defineConfig({
    testDir: '../tests/e2e',

    // 超时设置
    timeout: 30 * 1000,
    expect: {
        timeout: 5 * 1000
    },

    // 测试失败时重试
    retries: process.env.CI ? 2 : 0,

    // 并行运行测试
    workers: process.env.CI ? 1 : undefined,

    // 报告配置
    reporter: [
        ['html', { outputFolder: '../playwright-report' }],
        ['json', { outputFile: '../test-results.json' }],
        ['list']
    ],

    // 共享配置
    use: {
        // 基础 URL
        baseURL: process.env.BASE_URL || 'http://localhost:5173',

        // 追踪
        trace: 'on-first-retry',

        // 截图
        screenshot: 'only-on-failure',

        // 视频
        video: 'retain-on-failure',

        // 超时
        actionTimeout: 10 * 1000,
        navigationTimeout: 30 * 1000
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
        url: 'http://localhost:5173',
        reuseExistingServer: !process.env.CI,
        timeout: 120 * 1000,
    },
});

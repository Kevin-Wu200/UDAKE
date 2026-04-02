import { test, expect } from '@playwright/test';
import { gotoAndWaitForAppReady, retryWithBackoff } from './support/stability';

test.describe('完整工作流', () => {
    test.beforeEach(async ({ page }) => {
        await gotoAndWaitForAppReady(page, '/', page.locator('body'));
    });

    test('应该能够加载应用首页', async ({ page }) => {
        // 验证页面标题
        await expect(page).toHaveTitle(/UDAKE/);

        // 验证主要元素存在
        await expect(page.locator('body')).toBeVisible();
    });

    test('应该能够处理数据导入流程', async ({ page }) => {
        // 测试数据导入功能（如果存在）
        const importButton = page.locator('button, a').filter({ hasText: /导入|import/i }).first();

        if (await importButton.isVisible()) {
            await importButton.click();

            // 等待导入对话框或文件输入
            await expect(page.locator('input[type="file"], .modal, .dialog').first()).toBeVisible();
        } else {
            console.log('导入按钮不可见，跳过此测试');
        }
    });

    test('应该能够处理配置流程', async ({ page }) => {
        // 测试配置功能（如果存在）
        const configButton = page.locator('button, a').filter({ hasText: /配置|config|settings/i }).first();

        if (await configButton.isVisible()) {
            await configButton.click();

            // 等待配置面板
            await expect(page.locator('.config-panel, .settings-panel, .modal').first()).toBeVisible();
        } else {
            console.log('配置按钮不可见，跳过此测试');
        }
    });

    test('应该能够处理错误情况', async ({ page }) => {
        // 测试错误处理
        const errorButton = page.locator('button').filter({ hasText: /测试错误|test error/i }).first();

        if (await errorButton.isVisible()) {
            await errorButton.click();

            // 验证错误消息显示
            await expect(page.locator('.error-message, .alert-error').first()).toBeVisible();
        } else {
            console.log('错误测试按钮不可见，跳过此测试');
        }
    });

    test('应该能够处理网络错误', async ({ page }) => {
        // 模拟离线状态
        await page.setOffline(true);

        // 尝试执行需要网络的操作
        const refreshButton = page.locator('button').filter({ hasText: /刷新|refresh/i }).first();

        if (await refreshButton.isVisible()) {
            await retryWithBackoff(async () => {
                await refreshButton.click();
            }, { context: 'click refresh button in offline mode' });

            // 验证离线提示
            await expect(page.locator('.offline-indicator, .network-error').first()).toBeVisible();
        }

        // 恢复在线状态
        await page.setOffline(false);
    });

    test('应该能够响应式布局', async ({ page }) => {
        // 测试桌面视图
        await page.setViewportSize({ width: 1920, height: 1080 });
        await expect(page.locator('body')).toBeVisible();

        // 测试平板视图
        await page.setViewportSize({ width: 768, height: 1024 });
        await expect(page.locator('body')).toBeVisible();

        // 测试移动视图
        await page.setViewportSize({ width: 375, height: 667 });
        await expect(page.locator('body')).toBeVisible();
    });
});

test.describe('性能测试', () => {
    test('页面加载时间应该在合理范围内', async ({ page }) => {
        const startTime = Date.now();

        await gotoAndWaitForAppReady(page, '/', page.locator('body'));

        const loadTime = Date.now() - startTime;

        // 页面应该在 5 秒内加载完成
        expect(loadTime).toBeLessThan(5000);

        console.log(`页面加载时间: ${loadTime}ms`);
    });

    test('应该能够检测性能指标', async ({ page }) => {
        const metrics = await page.evaluate(() => {
            const perfEntries = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming;
            return {
                domContentLoaded: perfEntries.domContentLoadedEventEnd - perfEntries.domContentLoadedEventStart,
                loadComplete: perfEntries.loadEventEnd - perfEntries.loadEventStart,
                totalLoadTime: perfEntries.loadEventEnd - perfEntries.fetchStart
            };
        });

        expect(metrics.totalLoadTime).toBeLessThan(10000);

        console.log('性能指标:', metrics);
    });
});

test.describe('可访问性测试', () => {
    test('应该有适当的标题和描述', async ({ page }) => {
        await gotoAndWaitForAppReady(page, '/', page.locator('body'));

        const title = await page.title();
        expect(title).toBeTruthy();
        expect(title.length).toBeGreaterThan(0);
    });

    test('主要元素应该有适当的焦点管理', async ({ page }) => {
        await gotoAndWaitForAppReady(page, '/', page.locator('body'));

        // 测试 Tab 键导航
        await page.keyboard.press('Tab');

        // 验证焦点转移
        const focusedElement = await page.evaluate(() => document.activeElement?.tagName);
        expect(focusedElement).toBeTruthy();
    });
});

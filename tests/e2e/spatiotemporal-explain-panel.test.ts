import { expect, test } from '@playwright/test';
import { gotoAndWaitForAppReady } from './support/stability';

test.describe('SpatiotemporalExplainPanel 跨浏览器兼容性', () => {
  test('基础渲染与无障碍属性可用', async ({ page }) => {
    await gotoAndWaitForAppReady(
      page,
      '/test-spatiotemporal-explain-panel.html',
      page.locator('.explain-panel h4')
    );

    await page.waitForFunction(() => (window as Window & { __EXPLAIN_PANEL_READY__?: boolean }).__EXPLAIN_PANEL_READY__ === true);

    await expect(page.locator('.explain-panel h4')).toContainText('模型可解释性增强面板');
    await expect(page.locator('#dl-explain-status')).toHaveAttribute('role', 'status');
    await expect(page.locator('#dl-explain-status')).toHaveAttribute('aria-live', 'polite');
    await expect(page.locator('.explain-method-switch')).toHaveAttribute('role', 'tablist');
    await expect(page.locator('[data-result-tab="lime"]')).toHaveAttribute('role', 'tab');
  });

  test('任务提交、图表容器切换与暗黑模式切换', async ({ page }) => {
    await gotoAndWaitForAppReady(
      page,
      '/test-spatiotemporal-explain-panel.html',
      page.locator('#dl-explain-submit')
    );

    await page.click('#dl-explain-submit');
    await expect(page.locator('#dl-explain-status')).toContainText('任务提交成功');
    await expect(page.locator('.explain-task-item')).toHaveCount(1);
    await expect(page.locator('#chart-lime-feature')).toBeVisible();

    await page.click('[data-result-tab="shap"]');
    await expect(page.locator('#chart-shap-waterfall')).toBeVisible();
    await expect(page.locator('#chart-shap-beeswarm')).toBeVisible();

    await page.click('#dl-explain-theme-toggle');
    await expect(page.locator('.explain-panel')).toHaveClass(/theme-dark/);
    await expect(page.locator('#dl-explain-theme-toggle')).toHaveAttribute('aria-pressed', 'true');
  });

  test('国际化切换与移动端布局稳定', async ({ page }) => {
    await gotoAndWaitForAppReady(
      page,
      '/test-spatiotemporal-explain-panel.html',
      page.locator('#e2e-locale')
    );

    await page.selectOption('#e2e-locale', 'en-US');
    await expect(page.locator('.explain-panel h4')).toContainText('Model Explainability');

    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(120);

    const panelWidth = await page.locator('.explain-panel').evaluate((el) => el.getBoundingClientRect().width);
    expect(panelWidth).toBeLessThanOrEqual(390);
    await expect(page.locator('#dl-explain-submit')).toBeVisible();
    await page.click('#dl-explain-submit');
    await expect(page.locator('.explain-task-item')).toHaveCount(1);
    await expect(page.locator('#dl-explain-task-list .explain-task-item .task-id')).toContainText('task-e2e');
  });
});

import { test, expect } from '@playwright/test';

test.describe('国际化兼容性', () => {
  test('Landing Page 应支持中英文切换', async ({ page }) => {
    await page.goto('/landing-page/index.html');

    await expect(page.locator('h1[data-i18n="hero.title"]')).toContainText('智能空间决策');
    await page.click('#languageToggle');
    await expect(page.locator('h1[data-i18n="hero.title"]')).toContainText('Intelligent Spatial Decisions');
  });

  test('测试页面应支持语言切换按钮', async ({ page }) => {
    await page.goto('/test-modal.html');

    await expect(page.locator('h1[data-i18n="test.modal.heading"]')).toContainText('弹窗功能测试');
    await page.click('#test-i18n-switcher');
    await expect(page.locator('h1[data-i18n="test.modal.heading"]')).toContainText('Modal Feature Test');
  });
});

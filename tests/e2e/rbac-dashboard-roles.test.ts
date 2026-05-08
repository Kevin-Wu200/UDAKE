import { expect, test, type Page } from '@playwright/test';

type Role = 'enterprise' | 'company_admin' | 'admin' | 'super_admin';

function sessionFor(role: Role) {
  return {
    token: 'mock-access-token',
    refresh: 'mock-refresh-token',
    user: {
      userId: 9001,
      email: `${role}@example.com`,
      role,
      permissions: ['read', 'write', 'admin'],
      enterpriseId: 100,
    },
  };
}

async function mockApi(page: Page) {
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (path.endsWith('/devices')) {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, message: 'ok', data: { items: [], pagination: { page: 1, page_size: 1, total: 0 }, current_device_id: null } }) });
      return;
    }
    if (path.endsWith('/admin/stats')) {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, message: 'ok', data: { userGrowth: [], keyUsage: { used: 0, unused: 0 }, activeUsers7d: 0, enterpriseTotal: 0, enterpriseActive: 0, todayRegistrations: 0, todayLogins: 0 } }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, message: 'ok', data: {} }) });
  });
}

async function withRole(page: Page, role: Role) {
  const session = sessionFor(role);
  await page.addInitScript((payload) => {
    localStorage.setItem('udake_access_token', payload.token);
    localStorage.setItem('udake_refresh_token', payload.refresh);
    localStorage.setItem('udake_user_info', JSON.stringify(payload.user));
  }, session);
}

test.describe('路由拦截与 Dashboard 角色展示', () => {
  test('enterprise 访问 dashboard 自动按企业视图展示', async ({ page }) => {
    await mockApi(page);
    await withRole(page, 'enterprise');
    await page.goto('/#/dashboard');
    await expect(page.getByText('企业工作台')).toBeVisible();
  });

  test('company_admin 可切换管理/企业视角', async ({ page }) => {
    await mockApi(page);
    await withRole(page, 'company_admin');
    await page.goto('/#/dashboard');
    await expect(page.getByRole('radio', { name: '管理视角' })).toBeVisible();
    await page.getByRole('radio', { name: '企业视角' }).click();
    await expect(page.getByText('企业工作台')).toBeVisible();
  });

  test('admin 访问企业管理页被拦截到 403', async ({ page }) => {
    await mockApi(page);
    await withRole(page, 'admin');
    await page.goto('/#/enterprise-management');
    await expect(page).toHaveURL(/#\/403/);
  });

  test('super_admin 可以访问产品密钥管理页', async ({ page }) => {
    await mockApi(page);
    await withRole(page, 'super_admin');
    await page.goto('/#/product-keys');
    await expect(page).toHaveURL(/#\/product-keys/);
  });
});

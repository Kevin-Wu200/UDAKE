import { expect, test, type Page } from '@playwright/test';
import { createTestDataFactory, gotoAndWaitForAppReady, waitForApiResponse } from './support/stability';

type AnyJson = Record<string, unknown>;

function ok(data: AnyJson = {}, message = 'ok') {
  return {
    success: true,
    message,
    data,
  };
}

async function mockAuthApi(page: Page) {
  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const method = request.method().toUpperCase();
    const url = new URL(request.url());
    const path = url.pathname;

    if (method === 'POST' && path.endsWith('/auth/register')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(ok({ user_id: 1001, email: 'new-user@example.com' }, '验证码已发送')),
      });
      return;
    }

    if (method === 'POST' && path.endsWith('/auth/verify-email-code')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(ok({}, '验证码验证成功')),
      });
      return;
    }

    if (method === 'POST' && path.endsWith('/auth/login')) {
      const payload = JSON.parse(request.postData() || '{}') as { email?: string };
      const email = payload.email || 'user@example.com';
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(
          ok(
            {
              access_token: 'mock-access-token',
              refresh_token: 'mock-refresh-token',
              user_info: {
                user_id: 1001,
                email,
                role: 'user',
                permissions: ['read'],
              },
            },
            '登录成功',
          ),
        ),
      });
      return;
    }

    if (method === 'POST' && path.endsWith('/auth/reset-password/send-code')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(ok({}, '验证码已发送')),
      });
      return;
    }

    if (method === 'POST' && path.endsWith('/auth/reset-password/verify')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(ok({}, '密码重置成功')),
      });
      return;
    }

    if (method === 'GET' && path.endsWith('/devices')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(
          ok({
            items: [
              {
                device_id: 'mock-device-1',
                device_name: '测试设备A',
                device_type: 'desktop',
                os: 'macOS',
                browser: 'Chrome',
                ip: '203.0.*.*',
                location: '上海, 中国',
                last_login_at: 1_735_689_600,
                status: 'active',
                is_current: true,
              },
            ],
            pagination: {
              page: 1,
              page_size: 10,
              total: 1,
            },
            current_device_id: 'mock-device-1',
          }),
        ),
      });
      return;
    }

    await route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ success: false, message: `unmocked endpoint: ${method} ${path}`, data: {} }),
    });
  });
}

test.describe('认证流程 E2E（管理员前端用户中心）', () => {
  test.beforeEach(async ({ page }) => {
    await mockAuthApi(page);
  });

  test('注册流程：发送验证码并完成注册后自动登录', async ({ page }, testInfo) => {
    const dataFactory = createTestDataFactory(testInfo.title);
    const user = dataFactory.user();
    await gotoAndWaitForAppReady(page, '/#/user/register', page.getByRole('button', { name: '发送验证码' }));

    await page.getByPlaceholder('请输入邮箱').fill(user.email);
    await page.getByPlaceholder('请输入密码').fill(user.password);
    await page.getByPlaceholder('请再次输入密码').fill(user.password);
    await page.getByPlaceholder('例如：ABC-1234-5678-9XYZ').fill('ABC-1234-5678-9XYZ');

    await waitForApiResponse(page, '/auth/register', async () => {
      await page.getByRole('button', { name: '发送验证码' }).click();
    });
    await expect(page.getByText('验证码已发送，请查收邮箱')).toBeVisible();

    await page.getByPlaceholder('请输入6位验证码').fill('123456');
    await waitForApiResponse(page, '/auth/verify-email-code', async () => {
      await page.getByRole('button', { name: '完成注册' }).click();
    });

    await expect(page.getByText('注册成功，已自动登录')).toBeVisible();
    await expect
      .poll(async () => page.evaluate(() => localStorage.getItem('udake_access_token')))
      .toBe('mock-access-token');
  });

  test('登录流程：登录后进入设备管理页面', async ({ page }) => {
    await gotoAndWaitForAppReady(page, '/#/user/login', page.getByRole('button', { name: '登录' }));

    await page.getByPlaceholder('请输入邮箱').fill('user@example.com');
    await page.getByPlaceholder('请输入密码').fill('StrongPass123');
    await waitForApiResponse(page, '/auth/login', async () => {
      await page.getByRole('button', { name: '登录' }).click();
    });

    await expect
      .poll(async () => page.evaluate(() => localStorage.getItem('udake_access_token')))
      .toBe('mock-access-token');
    await expect(page).toHaveURL(/#\/user\/devices/);
    await expect(page.getByRole('heading', { name: '设备管理' })).toBeVisible();
  });

  test('找回密码流程：发送验证码并完成重置回到登录页', async ({ page }) => {
    await gotoAndWaitForAppReady(page, '/#/user/forgot-password', page.getByRole('button', { name: '发送验证码' }));

    await page.getByPlaceholder('请输入注册邮箱').fill('user@example.com');
    await page.getByPlaceholder('请输入产品密钥').fill('ABC-1234-5678-9XYZ');
    await waitForApiResponse(page, '/auth/reset-password/send-code', async () => {
      await page.getByRole('button', { name: '发送验证码' }).click();
    });

    await expect(page.getByText('验证码已发送，请在10分钟内完成验证')).toBeVisible();

    await page.getByPlaceholder('请输入验证码').fill('654321');
    await page.getByRole('button', { name: '下一步' }).click();

    await page.getByPlaceholder('请输入新密码').fill('NewStrongPass123');
    await page.getByPlaceholder('请再次输入新密码').fill('NewStrongPass123');
    await page.getByRole('button', { name: '下一步' }).click();

    await waitForApiResponse(page, '/auth/reset-password/verify', async () => {
      await page.getByRole('button', { name: '确认重置' }).click();
    });
    await expect(page).toHaveURL(/#\/user\/login/);
    await expect(page.getByText('用户登录')).toBeVisible();
  });
});

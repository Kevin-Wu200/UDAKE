import { expect, test, type Page } from '@playwright/test';
import {
  createTestDataFactory,
  gotoAndWaitForAppReady,
  retryWithBackoff,
  waitForApiResponse
} from './support/stability';

type NotificationType = 'mention' | 'comment' | 'share' | 'system';
type NotificationPriority = 'low' | 'normal' | 'high' | 'urgent';

type NotificationItem = {
  notification_id: string;
  workflow_id: string;
  type: NotificationType;
  title: string;
  content: string;
  source: string;
  created_at: string;
  read: boolean;
  priority: NotificationPriority;
  source_id?: string;
};

type NotificationPreference = {
  types: Record<NotificationType, boolean>;
  frequency: 'realtime' | '5m' | '15m' | 'daily';
  channels: Array<'popup' | 'list' | 'email'>;
};

type NotificationTestState = {
  workflowId: string;
  createWorkflowCalls: number;
  createCommentCalls: number;
  markSingleCalls: number;
  markBatchCalls: number;
  markAllCalls: number;
  updatePreferenceCalls: number;
  notifications: NotificationItem[];
  preference: NotificationPreference;
};

function buildWorkflowRecord(workflowId: string) {
  const now = new Date().toISOString();
  return {
    workflow_id: workflowId,
    name: '通知中心E2E流程',
    description: 'notification center e2e',
    current: {
      workflow_id: workflowId,
      name: '通知中心E2E流程',
      description: 'notification center e2e',
      version: 1,
      nodes: [],
      edges: []
    },
    versions: [{ version: 1, note: 'e2e', updated_at: now }],
    collaborators: [],
    created_at: now,
    updated_at: now
  };
}

function buildSeedNotifications(workflowId: string): NotificationItem[] {
  const now = Date.now();
  const seed: Array<Pick<NotificationItem, 'notification_id' | 'type' | 'title' | 'content' | 'source' | 'priority' | 'read'>> = [
    {
      notification_id: 'n_mention_1',
      type: 'mention',
      title: '提及-张三',
      content: '张三在评论中@了你',
      source: '协作评论',
      priority: 'high',
      read: false
    },
    {
      notification_id: 'n_comment_1',
      type: 'comment',
      title: '评论-需求评审',
      content: '李四发表了新评论',
      source: '协作评论',
      priority: 'normal',
      read: false
    },
    {
      notification_id: 'n_share_1',
      type: 'share',
      title: '分享-测试链接',
      content: '工作流已分享给测试组',
      source: '分享中心',
      priority: 'low',
      read: true
    },
    {
      notification_id: 'n_system_1',
      type: 'system',
      title: '系统-发布通知',
      content: '系统维护窗口已更新',
      source: '系统服务',
      priority: 'urgent',
      read: false
    },
    {
      notification_id: 'n_comment_2',
      type: 'comment',
      title: '评论-接口联调',
      content: '请确认联调时间',
      source: '协作评论',
      priority: 'normal',
      read: false
    },
    {
      notification_id: 'n_share_2',
      type: 'share',
      title: '分享-外部成员',
      content: '外部成员查看了分享链接',
      source: '分享中心',
      priority: 'low',
      read: false
    },
    {
      notification_id: 'n_system_2',
      type: 'system',
      title: '系统-策略变更',
      content: '策略已切换为低延迟模式',
      source: '系统服务',
      priority: 'high',
      read: false
    },
    {
      notification_id: 'n_mention_2',
      type: 'mention',
      title: '提及-流程发布',
      content: '王五提醒你检查发布流程',
      source: '协作评论',
      priority: 'high',
      read: false
    },
    {
      notification_id: 'n_comment_3',
      type: 'comment',
      title: '评论-回归结果',
      content: '回归结果已上传',
      source: '协作评论',
      priority: 'normal',
      read: true
    },
    {
      notification_id: 'n_system_3',
      type: 'system',
      title: '系统-资源告警',
      content: '资源使用接近阈值',
      source: '系统服务',
      priority: 'urgent',
      read: false
    }
  ];

  return seed.map((item, index) => ({
    ...item,
    workflow_id: workflowId,
    created_at: new Date(now - index * 90_000).toISOString()
  }));
}

async function setupNotificationMock(page: Page, namespace: string): Promise<NotificationTestState> {
  const factory = createTestDataFactory(namespace);
  const workflowId = factory.nextId('wf_e2e_notify');
  const state: NotificationTestState = {
    workflowId,
    createWorkflowCalls: 0,
    createCommentCalls: 0,
    markSingleCalls: 0,
    markBatchCalls: 0,
    markAllCalls: 0,
    updatePreferenceCalls: 0,
    notifications: buildSeedNotifications(workflowId),
    preference: {
      types: {
        mention: true,
        comment: true,
        share: true,
        system: true
      },
      frequency: 'realtime',
      channels: ['popup', 'list']
    }
  };

  await page.addInitScript(() => {
    localStorage.setItem('admin_access_token', 'mock-admin-token');
  });

  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const method = request.method().toUpperCase();
    const url = new URL(request.url());
    const path = url.pathname;

    if (method === 'GET' && path.endsWith('/workflow/node-types')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ built_in: ['input.constant'], custom: [], param_rules: {} })
      });
      return;
    }

    if (method === 'GET' && path.endsWith('/workflow/templates')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ templates: [], count: 0 })
      });
      return;
    }

    if (method === 'GET' && path.endsWith('/workflow/marketplace')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [], count: 0 })
      });
      return;
    }

    if (method === 'POST' && path.endsWith('/workflow/validate')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ valid: true, node_count: 1, edge_count: 0, warnings: [] })
      });
      return;
    }

    if (method === 'POST' && path.endsWith('/workflow')) {
      state.createWorkflowCalls += 1;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ workflow: buildWorkflowRecord(state.workflowId) })
      });
      return;
    }

    if (method === 'GET' && path.endsWith(`/workflow/${state.workflowId}`)) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildWorkflowRecord(state.workflowId))
      });
      return;
    }

    if (method === 'GET' && path.endsWith(`/workflow/${state.workflowId}/runs`)) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ workflow_id: state.workflowId, runs: [], count: 0 })
      });
      return;
    }

    if (method === 'GET' && path.endsWith(`/workflow/${state.workflowId}/comments`)) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ comments: [], count: 0, has_more: false })
      });
      return;
    }

    if (method === 'POST' && path.endsWith(`/workflow/${state.workflowId}/comments`)) {
      state.createCommentCalls += 1;
      const payload = JSON.parse(request.postData() || '{}') as { content?: string };
      const now = new Date().toISOString();
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          comment: {
            comment_id: `c_${Date.now()}`,
            workflow_id: state.workflowId,
            parent_id: null,
            root_id: null,
            depth: 0,
            content: String(payload.content || ''),
            created_at: now,
            updated_at: now,
            deleted: false,
            author_id: 'user_e2e',
            author_name: 'E2E用户',
            mention_users: [],
            reply_count: 0
          }
        })
      });
      return;
    }

    if (method === 'GET' && path.endsWith(`/workflow/${state.workflowId}/notifications/preferences`)) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ...state.preference })
      });
      return;
    }

    if (method === 'PUT' && path.endsWith(`/workflow/${state.workflowId}/notifications/preferences`)) {
      state.updatePreferenceCalls += 1;
      const payload = JSON.parse(request.postData() || '{}') as NotificationPreference;
      state.preference = {
        ...state.preference,
        ...payload,
        types: { ...state.preference.types, ...(payload.types || {}) },
        channels: Array.isArray(payload.channels) ? [...payload.channels] : [...state.preference.channels]
      };
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ...state.preference })
      });
      return;
    }

    if (method === 'GET' && path.endsWith(`/workflow/${state.workflowId}/notifications`)) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          notifications: state.notifications,
          count: state.notifications.length,
          unread_count: state.notifications.filter((item) => !item.read).length,
          has_more: false
        })
      });
      return;
    }

    if (method === 'POST' && path.endsWith(`/workflow/${state.workflowId}/notifications/batch-read`)) {
      state.markBatchCalls += 1;
      const payload = JSON.parse(request.postData() || '{}') as { notification_ids?: string[] };
      const idSet = new Set(payload.notification_ids || []);
      state.notifications = state.notifications.map((item) => (idSet.has(item.notification_id) ? { ...item, read: true } : item));
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ count: idSet.size, notification_ids: Array.from(idSet) })
      });
      return;
    }

    if (method === 'POST' && path.endsWith(`/workflow/${state.workflowId}/notifications/read-all`)) {
      state.markAllCalls += 1;
      state.notifications = state.notifications.map((item) => ({ ...item, read: true }));
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ count: state.notifications.length })
      });
      return;
    }

    if (method === 'POST' && path.includes(`/workflow/${state.workflowId}/notifications/`) && path.endsWith('/read')) {
      state.markSingleCalls += 1;
      const chunks = path.split('/');
      const targetId = chunks[chunks.length - 2] || '';
      state.notifications = state.notifications.map((item) =>
        item.notification_id === targetId ? { ...item, read: true } : item
      );
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ notification_id: targetId, read: true })
      });
      return;
    }

    await route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ message: `unmocked endpoint: ${method} ${path}` })
    });
  });

  return state;
}

async function pushNotification(page: Page, payload: Record<string, unknown>) {
  await page.evaluate((raw) => {
    window.dispatchEvent(new CustomEvent('workflow-notification-push', { detail: raw }));
  }, payload);
}

test.describe('通知中心专项E2E', () => {
  test('创建工作流后评论并接收@提及通知', async ({ page }, testInfo) => {
    const state = await setupNotificationMock(page, testInfo.title);

    await gotoAndWaitForAppReady(page, '/#/workflows/editor', page.getByRole('button', { name: '保存' }));
    await waitForApiResponse(page, '/workflow', async () => {
      await page.getByRole('button', { name: '保存' }).click();
    });
    await expect.poll(() => state.createWorkflowCalls).toBeGreaterThan(0);

    await expect(page.getByText('通知中心')).toBeVisible();

    await page.getByPlaceholder('输入评论，使用 @ 可提及协作者').fill('@alice 请确认这个节点输出');
    await waitForApiResponse(page, '/comments', async () => {
      await page.getByRole('button', { name: '提交评论' }).click();
    });
    await expect.poll(() => state.createCommentCalls).toBeGreaterThan(0);

    await pushNotification(page, {
      notification_id: 'rt_mention_created',
      workflow_id: state.workflowId,
      notification_type: 'mention',
      title: '@提及通知',
      content: '用户A 在评论中提及了你',
      source: '评论线程',
      source_id: 'c_mention_1',
      priority: 'high',
      created_at: new Date().toISOString()
    });

    await expect(page.locator('.notification-list')).toContainText('@提及通知');
    await expect(page.locator('.toast-list')).toContainText('用户A 在评论中提及了你');
  });

  test('多用户协作通知收发链路', async ({ page }, testInfo) => {
    const state = await setupNotificationMock(page, testInfo.title);

    await gotoAndWaitForAppReady(page, `/#/workflows/editor/${state.workflowId}`, page.getByText('通知中心'));
    await expect(page.getByText('通知中心')).toBeVisible();

    await pushNotification(page, {
      notification_id: 'rt_comment_user_a',
      workflow_id: state.workflowId,
      notification_type: 'comment',
      title: '用户A发布评论',
      content: '用户A：请确认评审意见',
      source: '评论线程',
      source_id: 'comment_user_a',
      priority: 'normal',
      created_at: new Date().toISOString()
    });

    await pushNotification(page, {
      notification_id: 'rt_reply_user_b',
      workflow_id: state.workflowId,
      notification_type: 'mention',
      title: '用户B回复评论',
      content: '用户B 回复了你的评论',
      source: '评论线程',
      source_id: 'comment_user_b',
      priority: 'high',
      created_at: new Date().toISOString()
    });

    await expect(page.locator('.notification-list')).toContainText('用户A发布评论');
    await expect(page.locator('.notification-list')).toContainText('用户B回复评论');
  });

  test('通知设置关闭与恢复生效', async ({ page }, testInfo) => {
    const state = await setupNotificationMock(page, testInfo.title);

    await gotoAndWaitForAppReady(page, `/#/workflows/editor/${state.workflowId}`, page.getByText('通知中心'));
    await expect(page.getByText('通知中心')).toBeVisible();

    await retryWithBackoff(
      async () => {
        await page.getByRole('button', { name: '通知设置' }).click();
      },
      { context: 'open notification settings' }
    );
    const mentionSwitch = page.locator('.notification-center .settings-grid .el-switch').first();
    await mentionSwitch.click();
    await expect.poll(() => state.updatePreferenceCalls).toBeGreaterThan(0);

    await pushNotification(page, {
      notification_id: 'rt_mention_disabled',
      workflow_id: state.workflowId,
      notification_type: 'mention',
      title: '关闭后提及通知',
      content: '关闭提及类型后的通知',
      source: '评论线程',
      priority: 'high',
      created_at: new Date().toISOString()
    });

    await expect(page.locator('.notification-list')).not.toContainText('关闭后提及通知');

    await pushNotification(page, {
      notification_id: 'rt_comment_enabled',
      workflow_id: state.workflowId,
      notification_type: 'comment',
      title: '关闭提及时评论仍可见',
      content: '评论通知仍然可见',
      source: '评论线程',
      priority: 'normal',
      created_at: new Date().toISOString()
    });

    await expect(page.locator('.notification-list')).toContainText('关闭提及时评论仍可见');

    await mentionSwitch.click();

    await pushNotification(page, {
      notification_id: 'rt_mention_enabled',
      workflow_id: state.workflowId,
      notification_type: 'mention',
      title: '恢复后提及通知',
      content: '重新开启后可接收提及',
      source: '评论线程',
      priority: 'high',
      created_at: new Date().toISOString()
    });

    await expect(page.locator('.notification-list')).toContainText('恢复后提及通知');
  });

  test('通知筛选支持单选、多选、关键字与未读', async ({ page }, testInfo) => {
    const state = await setupNotificationMock(page, testInfo.title);

    await gotoAndWaitForAppReady(page, `/#/workflows/editor/${state.workflowId}`, page.getByText('通知中心'));
    await expect(page.getByText('通知中心')).toBeVisible();

    await page.locator('.quick-filter-row').getByText('评论').click();
    await expect(page.locator('.notification-list')).toContainText('评论-需求评审');
    await expect(page.locator('.notification-list')).not.toContainText('提及-张三');

    await page.locator('.quick-filter-row').getByText('全部').click();
    await page.locator('.advanced-filter-row .el-checkbox').filter({ hasText: '评论' }).click();
    await page.locator('.advanced-filter-row .el-checkbox').filter({ hasText: '分享' }).click();

    await expect(page.locator('.notification-list')).toContainText('评论-需求评审');
    await expect(page.locator('.notification-list')).toContainText('分享-测试链接');
    await expect(page.locator('.notification-list')).not.toContainText('系统-发布通知');

    await page.getByPlaceholder('来源筛选').fill('分享中心');
    await expect(page.locator('.notification-list')).toContainText('分享-测试链接');
    await expect(page.locator('.notification-list')).not.toContainText('评论-需求评审');

    await page.getByPlaceholder('来源筛选').fill('');
    await page.getByPlaceholder('关键字').fill('联调');
    await expect(page.locator('.notification-list')).toContainText('评论-接口联调');

    await page.getByPlaceholder('关键字').fill('');
    await page.locator('.advanced-filter-row .el-switch').click();
    await expect(page.locator('.notification-list')).not.toContainText('评论-回归结果');
  });

  test('通知操作支持单条、批量、全部已读与分页', async ({ page }, testInfo) => {
    const state = await setupNotificationMock(page, testInfo.title);

    await gotoAndWaitForAppReady(page, `/#/workflows/editor/${state.workflowId}`, page.getByText('通知中心'));
    await expect(page.getByText('通知中心')).toBeVisible();

    const firstCard = page.locator('.notification-card').first();
    await waitForApiResponse(page, '/read', async () => {
      await firstCard.getByRole('button', { name: '标记已读' }).click();
    });
    await expect.poll(() => state.markSingleCalls).toBeGreaterThan(0);

    const checkboxes = page.locator('.notification-card .card-left input[type="checkbox"]');
    await checkboxes.nth(0).click();
    await checkboxes.nth(1).click();
    await waitForApiResponse(page, '/batch-read', async () => {
      await page.getByRole('button', { name: /批量已读/ }).click();
    });
    await expect.poll(() => state.markBatchCalls).toBeGreaterThan(0);

    await waitForApiResponse(page, '/read-all', async () => {
      await page.getByRole('button', { name: '全部已读' }).click();
    });
    await expect.poll(() => state.markAllCalls).toBeGreaterThan(0);
    await expect(page.locator('.notification-header')).toContainText('未读 0');

    await expect(page.locator('.notification-list')).not.toContainText('评论-回归结果');
    await page.locator('.pagination-row .el-pager li').getByText('2').click();
    await expect(page.locator('.notification-list')).toContainText('评论-回归结果');
  });
});

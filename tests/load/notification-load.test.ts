import { describe, expect, it } from 'vitest';
import {
  filterNotifications,
  markNotificationsRead,
  paginateNotifications,
  sortNotifications,
  upsertNotification,
  type WorkflowNotificationItem,
  type WorkflowNotificationPriority,
  type WorkflowNotificationType
} from '../../apps/admin-frontend/src/views/workflow/notificationCenterUtils.ts';

function createNotification(index: number): WorkflowNotificationItem {
  const types: WorkflowNotificationType[] = ['mention', 'comment', 'share', 'system'];
  const priorities: WorkflowNotificationPriority[] = ['low', 'normal', 'high', 'urgent'];

  return {
    notification_id: `load_${index}`,
    workflow_id: 'wf_load',
    type: types[index % types.length],
    title: `负载通知-${index}`,
    content: `负载测试内容-${index}`,
    source: index % 2 === 0 ? '协作评论' : '系统服务',
    created_at: new Date(Date.now() - index * 200).toISOString(),
    read: index % 5 === 0,
    priority: priorities[index % priorities.length]
  };
}

describe('通知中心负载测试', () => {
  it('模拟100用户同时接收通知应在300ms内完成处理', () => {
    let items: WorkflowNotificationItem[] = [];
    const start = performance.now();

    for (let i = 0; i < 100; i += 1) {
      items = upsertNotification(items, createNotification(i), 500);
    }

    const sorted = sortNotifications(items, {
      sortBy: 'priority',
      groupByType: false,
      unreadFirst: true
    });

    const duration = performance.now() - start;
    expect(sorted.length).toBe(100);
    expect(duration).toBeLessThan(300);
  });

  it('混合筛选条件在1000条数据上应在500ms内完成', () => {
    const items = Array.from({ length: 1000 }).map((_, idx) => createNotification(idx));
    const start = performance.now();

    const filtered = filterNotifications(items, {
      singleType: 'all',
      multiTypes: ['mention', 'share'],
      sourceKeyword: '协作',
      textKeyword: '负载通知',
      unreadOnly: true
    });
    const sorted = sortNotifications(filtered, {
      sortBy: 'type',
      groupByType: true,
      unreadFirst: true
    });

    const duration = performance.now() - start;
    expect(sorted.length).toBeGreaterThan(0);
    expect(duration).toBeLessThan(500);
  });

  it('分页遍历1000条通知应无遗漏', () => {
    const items = Array.from({ length: 1000 }).map((_, idx) => createNotification(idx));
    const pageSize = 80;

    let page = 1;
    let totalLoaded = 0;
    while (true) {
      const current = paginateNotifications(items, page, pageSize);
      totalLoaded += current.list.length;
      if (current.currentPage >= current.totalPages) {
        break;
      }
      page += 1;
    }

    expect(totalLoaded).toBe(items.length);
  });

  it('100条批量已读和全量排序应稳定', () => {
    const items = Array.from({ length: 300 }).map((_, idx) => createNotification(idx));
    const ids = items.slice(0, 100).map((item) => item.notification_id);

    const start = performance.now();
    const marked = markNotificationsRead(items, ids, true);
    const sorted = sortNotifications(marked, {
      sortBy: 'time',
      groupByType: false,
      unreadFirst: true
    });
    const duration = performance.now() - start;

    expect(sorted.length).toBe(300);
    expect(duration).toBeLessThan(300);
  });
});

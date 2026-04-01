import { describe, expect, it } from 'vitest';
import {
  countUnreadNotifications,
  filterNotifications,
  markNotificationsRead,
  paginateNotifications,
  sortNotifications,
  upsertNotification,
  type WorkflowNotificationItem,
  type WorkflowNotificationPriority,
  type WorkflowNotificationType
} from '../../apps/admin-frontend/src/views/workflow/notificationCenterUtils.ts';

function buildItems(count: number): WorkflowNotificationItem[] {
  const now = Date.now();
  const types: WorkflowNotificationType[] = ['mention', 'comment', 'share', 'system'];
  const priorities: WorkflowNotificationPriority[] = ['low', 'normal', 'high', 'urgent'];

  return Array.from({ length: count }).map((_, index) => ({
    notification_id: `perf_${index + 1}`,
    workflow_id: 'wf_perf_notification',
    type: types[index % types.length],
    title: `性能通知-${index + 1}`,
    content: `这是第${index + 1}条通知，用于性能基准验证。`,
    source: index % 2 === 0 ? '协作评论' : '系统服务',
    source_id: `source_${index + 1}`,
    created_at: new Date(now - index * 1000).toISOString(),
    read: index % 3 === 0,
    priority: priorities[index % priorities.length],
    metadata: { index }
  }));
}

describe('通知中心性能测试', () => {
  it('100条通知筛选+排序+分页应在500ms内完成', () => {
    const items = buildItems(100);
    const start = performance.now();

    const filtered = filterNotifications(items, {
      singleType: 'all',
      multiTypes: ['mention', 'comment'],
      sourceKeyword: '协作',
      textKeyword: '性能通知',
      unreadOnly: true
    });
    const sorted = sortNotifications(filtered, {
      sortBy: 'priority',
      groupByType: true,
      unreadFirst: true
    });
    const page = paginateNotifications(sorted, 1, 20);

    const duration = performance.now() - start;
    expect(page.total).toBeGreaterThan(0);
    expect(duration).toBeLessThan(500);
  });

  it('1000条通知排序+统计应在500ms内完成', () => {
    const items = buildItems(1000);
    const start = performance.now();

    const sorted = sortNotifications(items, {
      sortBy: 'time',
      groupByType: false,
      unreadFirst: true
    });
    const unread = countUnreadNotifications(sorted);
    const page10 = paginateNotifications(sorted, 10, 50);

    const duration = performance.now() - start;
    expect(unread).toBeGreaterThan(0);
    expect(page10.list.length).toBeLessThanOrEqual(50);
    expect(duration).toBeLessThan(500);
  });

  it('100条批量已读操作应在300ms内完成', () => {
    const items = buildItems(500);
    const targetIds = items.slice(0, 100).map((item) => item.notification_id);

    const start = performance.now();
    const marked = markNotificationsRead(items, targetIds, true);
    const duration = performance.now() - start;

    const markedCount = marked.slice(0, 100).filter((item) => item.read).length;
    expect(markedCount).toBe(100);
    expect(duration).toBeLessThan(300);
  });

  it('长时间upsert后通知缓存长度应稳定在上限内', () => {
    let items = buildItems(200);
    const start = performance.now();

    for (let i = 0; i < 5000; i += 1) {
      items = upsertNotification(
        items,
        {
          notification_id: `rt_${i}`,
          workflow_id: 'wf_perf_notification',
          type: 'comment',
          title: `实时通知-${i}`,
          content: '实时通知写入性能验证',
          source: '实时协作',
          created_at: new Date().toISOString(),
          read: false,
          priority: 'normal'
        },
        500
      );
    }

    const duration = performance.now() - start;
    expect(items.length).toBeLessThanOrEqual(500);
    expect(duration).toBeLessThan(500);
  });
});

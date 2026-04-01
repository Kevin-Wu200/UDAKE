import { describe, it, expect } from 'vitest';
import {
  appendPreferenceHistory,
  countUnreadNotifications,
  createMockNotifications,
  filterNotifications,
  formatNotificationRelativeTime,
  markNotificationsRead,
  paginateNotifications,
  sortNotifications,
  upsertNotification,
  type NotificationPreferenceSnapshot,
  type WorkflowNotificationItem
} from '../apps/admin-frontend/src/views/workflow/notificationCenterUtils.ts';

function createItem(
  partial: Partial<WorkflowNotificationItem> & Pick<WorkflowNotificationItem, 'notification_id'>
): WorkflowNotificationItem {
  return {
    notification_id: partial.notification_id,
    workflow_id: partial.workflow_id || 'wf_test',
    type: partial.type || 'comment',
    title: partial.title || 'title',
    content: partial.content || 'content',
    source: partial.source || 'source',
    created_at: partial.created_at || new Date('2026-04-01T00:00:00.000Z').toISOString(),
    read: partial.read ?? false,
    priority: partial.priority || 'normal',
    source_id: partial.source_id,
    metadata: partial.metadata
  };
}

describe('notificationCenterUtils', () => {
  it('应按条件筛选通知（单选、多选、关键字、未读）', () => {
    const items = [
      createItem({ notification_id: 'n1', type: 'mention', title: '提及我', source: '评论', read: false }),
      createItem({ notification_id: 'n2', type: 'comment', title: '新评论', source: '评论', read: true }),
      createItem({ notification_id: 'n3', type: 'system', title: '系统维护', source: '系统', read: false })
    ];

    const filtered = filterNotifications(items, {
      singleType: 'all',
      multiTypes: ['mention', 'system'],
      textKeyword: '系统',
      unreadOnly: true
    });

    expect(filtered).toHaveLength(1);
    expect(filtered[0].notification_id).toBe('n3');
  });

  it('应按优先级排序并将未读置顶', () => {
    const items = [
      createItem({
        notification_id: 'n1',
        priority: 'low',
        read: false,
        created_at: '2026-04-01T00:00:01.000Z'
      }),
      createItem({
        notification_id: 'n2',
        priority: 'urgent',
        read: true,
        created_at: '2026-04-01T00:00:02.000Z'
      }),
      createItem({
        notification_id: 'n3',
        priority: 'high',
        read: false,
        created_at: '2026-04-01T00:00:03.000Z'
      })
    ];

    const sorted = sortNotifications(items, { sortBy: 'priority', unreadFirst: true });
    expect(sorted.map((item) => item.notification_id)).toEqual(['n3', 'n1', 'n2']);
  });

  it('分页应返回正确页数据', () => {
    const items = Array.from({ length: 7 }).map((_, index) => createItem({ notification_id: `n${index + 1}` }));
    const page2 = paginateNotifications(items, 2, 3);
    expect(page2.total).toBe(7);
    expect(page2.totalPages).toBe(3);
    expect(page2.list.map((item) => item.notification_id)).toEqual(['n4', 'n5', 'n6']);
  });

  it('应支持单条与全量已读更新', () => {
    const items = [
      createItem({ notification_id: 'n1', read: false }),
      createItem({ notification_id: 'n2', read: false })
    ];
    const partial = markNotificationsRead(items, ['n1']);
    expect(partial[0].read).toBe(true);
    expect(partial[1].read).toBe(false);

    const allRead = markNotificationsRead(partial, 'all');
    expect(allRead.every((item) => item.read)).toBe(true);
  });

  it('应正确统计未读并支持 upsert', () => {
    const items = [
      createItem({ notification_id: 'n1', read: false }),
      createItem({ notification_id: 'n2', read: true })
    ];
    expect(countUnreadNotifications(items)).toBe(1);

    const upserted = upsertNotification(items, createItem({ notification_id: 'n1', title: 'updated', read: false }));
    expect(upserted).toHaveLength(2);
    expect(upserted.find((item) => item.notification_id === 'n1')?.title).toBe('updated');
  });

  it('应维护偏好设置历史上限', () => {
    const base: NotificationPreferenceSnapshot = {
      saved_at: '2026-04-01T00:00:00.000Z',
      frequency: 'realtime',
      channels: ['popup', 'list'],
      types: { mention: true, comment: true, share: true, system: true }
    };
    let history: NotificationPreferenceSnapshot[] = [];
    for (let i = 0; i < 5; i += 1) {
      history = appendPreferenceHistory(history, { ...base, saved_at: `2026-04-01T00:00:0${i}.000Z` }, 3);
    }
    expect(history).toHaveLength(3);
    expect(history[0].saved_at).toBe('2026-04-01T00:00:04.000Z');
  });

  it('相对时间格式应按秒/分/小时转换', () => {
    const now = new Date('2026-04-01T00:10:00.000Z').getTime();
    expect(formatNotificationRelativeTime('2026-04-01T00:09:40.000Z', now)).toBe('20秒前');
    expect(formatNotificationRelativeTime('2026-04-01T00:05:00.000Z', now)).toBe('5分钟前');
    expect(formatNotificationRelativeTime('2026-03-31T22:10:00.000Z', now)).toBe('2小时前');
  });

  it('应可生成默认通知数据', () => {
    const mocks = createMockNotifications('wf_x');
    expect(mocks).toHaveLength(4);
    expect(mocks[0].workflow_id).toBe('wf_x');
  });
});

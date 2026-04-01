export type WorkflowNotificationType = 'mention' | 'comment' | 'share' | 'system';

export type WorkflowNotificationPriority = 'low' | 'normal' | 'high' | 'urgent';

export interface WorkflowNotificationItem {
  notification_id: string;
  workflow_id: string;
  type: WorkflowNotificationType;
  title: string;
  content: string;
  source: string;
  source_id?: string;
  created_at: string;
  read: boolean;
  priority: WorkflowNotificationPriority;
  metadata?: Record<string, unknown>;
}

export interface NotificationFilterOptions {
  singleType?: 'all' | WorkflowNotificationType;
  multiTypes?: WorkflowNotificationType[];
  sourceKeyword?: string;
  textKeyword?: string;
  unreadOnly?: boolean;
}

export interface NotificationSortOptions {
  sortBy: 'time' | 'type' | 'priority';
  groupByType?: boolean;
  unreadFirst?: boolean;
}

export interface NotificationPreferenceSnapshot {
  saved_at: string;
  types: Record<WorkflowNotificationType, boolean>;
  frequency: 'realtime' | '5m' | '15m' | 'daily';
  channels: Array<'popup' | 'list' | 'email'>;
}

const PRIORITY_WEIGHT: Record<WorkflowNotificationPriority, number> = {
  urgent: 4,
  high: 3,
  normal: 2,
  low: 1
};

const TYPE_WEIGHT: Record<WorkflowNotificationType, number> = {
  mention: 1,
  comment: 2,
  share: 3,
  system: 4
};

function normalizeTime(value: string) {
  const ts = new Date(value).getTime();
  return Number.isFinite(ts) ? ts : 0;
}

function normalizeText(value: string) {
  return (value || '').trim().toLowerCase();
}

export function countUnreadNotifications(items: WorkflowNotificationItem[]) {
  return items.reduce((count, item) => (item.read ? count : count + 1), 0);
}

export function formatNotificationRelativeTime(isoTime: string, nowTs = Date.now()) {
  const delta = Math.max(0, nowTs - normalizeTime(isoTime));
  const seconds = Math.floor(delta / 1000);
  if (seconds < 60) {
    return `${seconds}秒前`;
  }
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    return `${minutes}分钟前`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `${hours}小时前`;
  }
  const days = Math.floor(hours / 24);
  if (days < 7) {
    return `${days}天前`;
  }
  return new Date(isoTime).toLocaleString();
}

export function filterNotifications(items: WorkflowNotificationItem[], options: NotificationFilterOptions) {
  const singleType = options.singleType || 'all';
  const multiTypes = options.multiTypes || [];
  const sourceKeyword = normalizeText(options.sourceKeyword || '');
  const textKeyword = normalizeText(options.textKeyword || '');
  const unreadOnly = options.unreadOnly === true;

  return items.filter((item) => {
    if (singleType !== 'all' && item.type !== singleType) {
      return false;
    }
    if (multiTypes.length > 0 && !multiTypes.includes(item.type)) {
      return false;
    }
    if (unreadOnly && item.read) {
      return false;
    }
    if (sourceKeyword && !normalizeText(item.source).includes(sourceKeyword)) {
      return false;
    }
    if (textKeyword) {
      const candidate = `${item.title} ${item.content} ${item.source}`;
      if (!normalizeText(candidate).includes(textKeyword)) {
        return false;
      }
    }
    return true;
  });
}

export function sortNotifications(items: WorkflowNotificationItem[], options: NotificationSortOptions) {
  const sortBy = options.sortBy;
  const unreadFirst = options.unreadFirst !== false;
  const groupByType = options.groupByType === true;

  return [...items].sort((a, b) => {
    if (unreadFirst && a.read !== b.read) {
      return a.read ? 1 : -1;
    }
    if (groupByType && a.type !== b.type) {
      return TYPE_WEIGHT[a.type] - TYPE_WEIGHT[b.type];
    }
    if (sortBy === 'priority') {
      const diff = PRIORITY_WEIGHT[b.priority] - PRIORITY_WEIGHT[a.priority];
      if (diff !== 0) {
        return diff;
      }
    }
    if (sortBy === 'type') {
      const diff = TYPE_WEIGHT[a.type] - TYPE_WEIGHT[b.type];
      if (diff !== 0) {
        return diff;
      }
    }
    return normalizeTime(b.created_at) - normalizeTime(a.created_at);
  });
}

export function paginateNotifications(items: WorkflowNotificationItem[], page: number, pageSize: number) {
  const safePageSize = Math.max(1, pageSize);
  const total = items.length;
  const totalPages = Math.max(1, Math.ceil(total / safePageSize));
  const safePage = Math.min(Math.max(1, page), totalPages);
  const start = (safePage - 1) * safePageSize;
  const end = start + safePageSize;
  return {
    total,
    totalPages,
    currentPage: safePage,
    list: items.slice(start, end)
  };
}

export function markNotificationsRead(
  items: WorkflowNotificationItem[],
  target: 'all' | string[] | Set<string>,
  read = true
) {
  if (target === 'all') {
    return items.map((item) => ({ ...item, read }));
  }
  const idSet = target instanceof Set ? target : new Set(target);
  return items.map((item) => (idSet.has(item.notification_id) ? { ...item, read } : item));
}

export function upsertNotification(items: WorkflowNotificationItem[], incoming: WorkflowNotificationItem, max = 500) {
  const index = items.findIndex((item) => item.notification_id === incoming.notification_id);
  if (index === -1) {
    return [incoming, ...items].slice(0, max);
  }
  const next = [...items];
  next[index] = incoming;
  return next;
}

export function appendPreferenceHistory(
  history: NotificationPreferenceSnapshot[],
  snapshot: NotificationPreferenceSnapshot,
  max = 20
) {
  return [snapshot, ...history].slice(0, max);
}

export function createMockNotifications(workflowId: string) {
  const now = Date.now();
  const templates: Array<Pick<WorkflowNotificationItem, 'type' | 'title' | 'content' | 'source' | 'priority'>> = [
    {
      type: 'mention',
      title: '@提及通知',
      content: 'Alice 在评论中提及了你：请确认节点输出。',
      source: '评论线程',
      priority: 'high'
    },
    {
      type: 'comment',
      title: '新评论',
      content: 'Bob 评论了工作流版本更新说明。',
      source: '协作评论',
      priority: 'normal'
    },
    {
      type: 'share',
      title: '分享访问',
      content: '外部成员查看了你分享的工作流链接。',
      source: '分享中心',
      priority: 'low'
    },
    {
      type: 'system',
      title: '系统通知',
      content: '工作流执行节点 catalog 已更新。',
      source: '系统服务',
      priority: 'urgent'
    }
  ];

  return templates.map((template, index) => ({
    notification_id: `mock_${workflowId}_${index + 1}`,
    workflow_id: workflowId,
    type: template.type,
    title: template.title,
    content: template.content,
    source: template.source,
    created_at: new Date(now - index * 90_000).toISOString(),
    read: false,
    priority: template.priority
  }));
}

import type {
  AuditEventType,
  AuditLog,
  DashboardStats,
  KeyStatus,
  KeyType,
  ProductKey,
  UserItem,
  UserRole
} from '../types/admin';

interface ListResult<T> {
  total: number;
  items: T[];
}

const delay = (ms = 280) => new Promise((resolve) => setTimeout(resolve, ms));

const now = new Date();

function formatDate(date: Date): string {
  const y = date.getFullYear();
  const m = `${date.getMonth() + 1}`.padStart(2, '0');
  const d = `${date.getDate()}`.padStart(2, '0');
  const hh = `${date.getHours()}`.padStart(2, '0');
  const mm = `${date.getMinutes()}`.padStart(2, '0');
  return `${y}-${m}-${d} ${hh}:${mm}`;
}

function daysAgo(day: number): string {
  const date = new Date(now);
  date.setDate(date.getDate() - day);
  date.setHours((date.getHours() + day) % 24, (day * 7) % 60, 0, 0);
  return formatDate(date);
}

function randomToken() {
  return `admin_${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`;
}

function randomKey(prefix: string): string {
  const chunk = () => Math.random().toString(36).slice(2, 6).toUpperCase();
  return `${prefix}-${chunk()}-${chunk()}-${chunk()}`;
}

let productKeyAutoId = 1;
let userAutoId = 1;
let logAutoId = 1;

let productKeys: ProductKey[] = Array.from({ length: 52 }, (_, index) => {
  const typePool: KeyType[] = ['trial', 'standard', 'enterprise'];
  const statusPool: KeyStatus[] = ['unused', 'active', 'disabled'];
  const type = typePool[index % typePool.length];
  const status = statusPool[index % statusPool.length];
  const usageCount = status === 'unused' ? 0 : (index * 2 + 3) % 40;

  return {
    id: productKeyAutoId++,
    key: randomKey('UDAKE'),
    type,
    status,
    usageCount,
    enterpriseName: `企业${(index % 9) + 1}`,
    createdAt: daysAgo(index)
  };
});

let users: UserItem[] = Array.from({ length: 42 }, (_, index) => {
  const rolePool: UserRole[] = ['admin', 'auditor', 'viewer'];
  const role = rolePool[index % rolePool.length];
  const username = `user_${index + 1}`;
  return {
    id: userAutoId++,
    username,
    email: `${username}@example.com`,
    role,
    status: index % 6 !== 0,
    createdAt: daysAgo(index + 14),
    lastLoginAt: daysAgo(index % 7),
    devices: [
      { name: `MacBook ${index + 1}`, os: 'macOS', lastActiveAt: daysAgo(index % 4) },
      { name: `iPhone ${index + 1}`, os: 'iOS', lastActiveAt: daysAgo(index % 6) }
    ],
    loginLogs: [
      { time: daysAgo(index % 3), ip: `10.10.0.${index + 10}`, result: 'success' },
      { time: daysAgo((index % 5) + 2), ip: `10.10.2.${index + 30}`, result: index % 5 === 0 ? 'failed' : 'success' }
    ]
  };
});

let auditLogs: AuditLog[] = Array.from({ length: 128 }, (_, index) => {
  const eventPool: AuditEventType[] = [
    'create_key',
    'import_key',
    'update_user',
    'reset_password',
    'login',
    'delete_key'
  ];
  return {
    id: logAutoId++,
    operator: index % 4 === 0 ? 'super_admin' : `operator_${(index % 6) + 1}`,
    eventType: eventPool[index % eventPool.length],
    target: index % 2 === 0 ? `用户 user_${(index % 30) + 1}` : `密钥 UDAKE-${(index % 20) + 100}`,
    time: daysAgo(index % 30),
    ip: `192.168.2.${(index % 64) + 10}`
  };
});

function paginate<T>(items: T[], page: number, pageSize: number): ListResult<T> {
  const start = (page - 1) * pageSize;
  const end = start + pageSize;
  return {
    total: items.length,
    items: items.slice(start, end)
  };
}

function pushAudit(eventType: AuditEventType, target: string, operator = 'super_admin') {
  auditLogs = [
    {
      id: logAutoId++,
      operator,
      eventType,
      target,
      time: formatDate(new Date()),
      ip: '127.0.0.1'
    },
    ...auditLogs
  ];
}

export async function loginApi(username: string, password: string) {
  await delay();
  if (!username || !password) {
    throw new Error('用户名或密码不能为空');
  }
  return {
    accessToken: randomToken()
  };
}

export async function fetchProductKeys(params: {
  page: number;
  pageSize: number;
  type?: KeyType;
  status?: KeyStatus;
  keyword?: string;
}) {
  await delay();
  const keyword = (params.keyword ?? '').trim().toLowerCase();

  let filtered = [...productKeys].sort((a, b) => b.id - a.id);

  if (params.type) {
    filtered = filtered.filter((item) => item.type === params.type);
  }
  if (params.status) {
    filtered = filtered.filter((item) => item.status === params.status);
  }
  if (keyword) {
    filtered = filtered.filter(
      (item) =>
        item.key.toLowerCase().includes(keyword) || item.enterpriseName.toLowerCase().includes(keyword)
    );
  }

  return paginate(filtered, params.page, params.pageSize);
}

export async function createProductKeys(payload: {
  type: KeyType;
  quantity: number;
  enterpriseName: string;
}) {
  await delay();
  const created: ProductKey[] = [];
  for (let i = 0; i < payload.quantity; i += 1) {
    created.push({
      id: productKeyAutoId++,
      key: randomKey('UDAKE'),
      type: payload.type,
      status: 'unused',
      usageCount: 0,
      enterpriseName: payload.enterpriseName,
      createdAt: formatDate(new Date())
    });
  }
  productKeys = [...created, ...productKeys];
  pushAudit('create_key', `批量生成 ${payload.quantity} 条密钥`);
  return created;
}

export async function importProductKeys(rawText: string) {
  await delay();
  const lines = rawText
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  const result = {
    successCount: 0,
    failedCount: 0,
    failedLines: [] as string[]
  };

  for (const line of lines) {
    const [keyText, typeText, statusText, enterpriseText] = line.split(',').map((cell) => cell.trim());
    const key = keyText || '';
    const type = (typeText || 'standard') as KeyType;
    const status = (statusText || 'unused') as KeyStatus;
    const enterpriseName = enterpriseText || '未命名企业';

    const validType = ['trial', 'standard', 'enterprise'].includes(type);
    const validStatus = ['unused', 'active', 'disabled'].includes(status);
    const duplicated = productKeys.some((item) => item.key === key);

    if (!key || !validType || !validStatus || duplicated) {
      result.failedCount += 1;
      result.failedLines.push(line);
      continue;
    }

    productKeys.unshift({
      id: productKeyAutoId++,
      key,
      type,
      status,
      usageCount: status === 'unused' ? 0 : 1,
      enterpriseName,
      createdAt: formatDate(new Date())
    });
    result.successCount += 1;
  }

  pushAudit('import_key', `导入密钥 ${result.successCount} 条`);
  return result;
}

export async function updateProductKey(
  id: number,
  payload: {
    status: KeyStatus;
    enterpriseName: string;
  }
) {
  await delay();
  productKeys = productKeys.map((item) =>
    item.id === id ? { ...item, status: payload.status, enterpriseName: payload.enterpriseName } : item
  );
  pushAudit('update_user', `更新密钥 #${id}`);
}

export async function deleteProductKey(id: number) {
  await delay();
  productKeys = productKeys.filter((item) => item.id !== id);
  pushAudit('delete_key', `删除密钥 #${id}`);
}

export async function fetchUsers(params: {
  page: number;
  pageSize: number;
  role?: UserRole;
  status?: 'enabled' | 'disabled';
  keyword?: string;
}) {
  await delay();
  const keyword = (params.keyword ?? '').trim().toLowerCase();

  let filtered = [...users].sort((a, b) => b.id - a.id);

  if (params.role) {
    filtered = filtered.filter((item) => item.role === params.role);
  }
  if (params.status) {
    const enabled = params.status === 'enabled';
    filtered = filtered.filter((item) => item.status === enabled);
  }
  if (keyword) {
    filtered = filtered.filter(
      (item) =>
        item.username.toLowerCase().includes(keyword) || item.email.toLowerCase().includes(keyword)
    );
  }

  return paginate(filtered, params.page, params.pageSize);
}

export async function updateUserStatus(id: number, enabled: boolean) {
  await delay();
  users = users.map((user) => (user.id === id ? { ...user, status: enabled } : user));
  pushAudit('update_user', `${enabled ? '启用' : '禁用'}用户 #${id}`);
}

export async function resetUserPassword(id: number) {
  await delay();
  pushAudit('reset_password', `重置用户 #${id} 密码`);
}

export async function fetchAuditLogs(params: {
  page: number;
  pageSize: number;
  eventType?: AuditEventType;
  keyword?: string;
  startTime?: string;
  endTime?: string;
}) {
  await delay();

  const keyword = (params.keyword ?? '').trim().toLowerCase();
  let filtered = [...auditLogs].sort((a, b) => b.id - a.id);

  if (params.eventType) {
    filtered = filtered.filter((item) => item.eventType === params.eventType);
  }

  if (keyword) {
    filtered = filtered.filter(
      (item) =>
        item.operator.toLowerCase().includes(keyword) || item.target.toLowerCase().includes(keyword)
    );
  }

  if (params.startTime) {
    const start = new Date(params.startTime).getTime();
    filtered = filtered.filter((item) => new Date(item.time).getTime() >= start);
  }

  if (params.endTime) {
    const end = new Date(params.endTime).getTime();
    filtered = filtered.filter((item) => new Date(item.time).getTime() <= end);
  }

  return paginate(filtered, params.page, params.pageSize);
}

export async function fetchAuditLogsForExport(params: {
  eventType?: AuditEventType;
  keyword?: string;
  startTime?: string;
  endTime?: string;
}) {
  const result = await fetchAuditLogs({ ...params, page: 1, pageSize: 10000 });
  return result.items;
}

export async function fetchDashboardStats(): Promise<DashboardStats> {
  await delay();

  const userGrowth = Array.from({ length: 30 }, (_, index) => {
    const day = 29 - index;
    const date = new Date(now);
    date.setDate(date.getDate() - day);
    const dateText = `${date.getMonth() + 1}/${date.getDate()}`;
    return {
      date: dateText,
      count: 120 + index * 4 + (index % 5)
    };
  });

  const used = productKeys.filter((item) => item.status !== 'unused').length;
  const unused = productKeys.length - used;

  const activeUsers7d = users.filter((item) => {
    const diff = now.getTime() - new Date(item.lastLoginAt).getTime();
    return diff <= 7 * 24 * 60 * 60 * 1000;
  }).length;

  return {
    userGrowth,
    keyUsage: { used, unused },
    activeUsers7d,
    enterpriseTotal: 128,
    enterpriseActive: 103,
    todayRegistrations: 16,
    todayLogins: 219
  };
}

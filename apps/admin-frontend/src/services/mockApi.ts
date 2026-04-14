import type {
  AuditEventType,
  AuditLog,
  DashboardStats,
  KeyStatus,
  KeyType,
  ProductKey,
  ProductKeyCreateForm,
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

function getQuotaByType(type: KeyType) {
  if (type === 'enterprise_trial') {
    return 500;
  }
  if (type === 'enterprise_standard') {
    return 1000;
  }
  if (type === 'personal_trial') {
    return 100;
  }
  return 300;
}

function isEnterpriseType(type: KeyType) {
  return type === 'enterprise_trial' || type === 'enterprise_standard';
}

let productKeyAutoId = 1;
let userAutoId = 1;
let logAutoId = 1;

let productKeys: ProductKey[] = Array.from({ length: 72 }, (_, index) => {
  const typePool: KeyType[] = ['personal_trial', 'personal_standard', 'enterprise_trial', 'enterprise_standard'];
  const statusPool: KeyStatus[] = ['unused', 'active', 'disabled', 'expired'];
  const keyType = typePool[index % typePool.length];
  const status = statusPool[index % statusPool.length];
  const totalQuota = getQuotaByType(keyType);
  const usedCount = status === 'unused' ? 0 : Math.min(totalQuota, (index * 13) % (totalQuota + 1));
  const companyId = isEnterpriseType(keyType) ? (index % 6) + 1 : undefined;
  const userId = status !== 'unused' ? (index % 18) + 1000 : undefined;

  return {
    id: productKeyAutoId++,
    product_key: randomKey('UDAKE'),
    key_type: keyType,
    key_sub_type: keyType.startsWith('personal') ? 'personal' : 'enterprise',
    status,
    total_quota: totalQuota,
    used_count: usedCount,
    user_id: userId,
    company_id: companyId,
    assigned_at: userId ? daysAgo((index % 12) + 1) : undefined,
    expires_at: status === 'expired' ? daysAgo(index % 8) : undefined,
    metadata: {
      generation_seed: `seed_${10000 + index}`,
      enterprise_name: companyId ? `企业${companyId}` : undefined,
      assigned_user_name: userId ? `user_${userId}` : undefined,
      assigned_by: userId ? 'super_admin' : undefined,
      notes: index % 5 === 0 ? '自动生成样例' : undefined
    },
    created_at: daysAgo(index),
    updated_at: daysAgo(Math.max(0, index - 1))
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
  company_id?: number;
  assigned?: boolean;
}) {
  await delay();
  const keyword = (params.keyword ?? '').trim().toLowerCase();

  let filtered = [...productKeys].sort((a, b) => b.id - a.id);

  if (params.type) {
    filtered = filtered.filter((item) => item.key_type === params.type);
  }
  if (params.status) {
    filtered = filtered.filter((item) => item.status === params.status);
  }
  if (typeof params.company_id === 'number') {
    filtered = filtered.filter((item) => item.company_id === params.company_id);
  }
  if (typeof params.assigned === 'boolean') {
    filtered = filtered.filter((item) => params.assigned ? Boolean(item.user_id) : !item.user_id);
  }
  if (keyword) {
    filtered = filtered.filter(
      (item) =>
        item.product_key.toLowerCase().includes(keyword) ||
        (item.metadata?.enterprise_name ?? '').toLowerCase().includes(keyword) ||
        String(item.user_id ?? '').includes(keyword)
    );
  }

  return paginate(filtered, params.page, params.pageSize);
}

export async function fetchProductKeyStats() {
  await delay(120);
  const total = productKeys.length;
  const active = productKeys.filter((item) => item.status === 'active').length;
  const unused = productKeys.filter((item) => item.status === 'unused').length;
  return { total, active, unused };
}

export async function createProductKeys(payload: ProductKeyCreateForm) {
  await delay();
  const created: ProductKey[] = [];
  for (let i = 0; i < payload.count; i += 1) {
    const keyType = payload.type;
    const key = {
      id: productKeyAutoId++,
      product_key: randomKey('UDAKE'),
      key_type: keyType,
      key_sub_type: keyType.startsWith('personal') ? 'personal' : 'enterprise',
      status: 'unused' as KeyStatus,
      total_quota: getQuotaByType(keyType),
      used_count: 0,
      user_id: payload.user_id,
      company_id: payload.company_id,
      assigned_at: payload.user_id ? formatDate(new Date()) : undefined,
      metadata: {
        ...payload.metadata,
        enterprise_name: payload.metadata?.enterprise_name || (payload.company_id ? `企业${payload.company_id}` : undefined),
        assigned_user_name: payload.user_id ? `user_${payload.user_id}` : undefined
      },
      created_at: formatDate(new Date()),
      updated_at: formatDate(new Date())
    };
    created.push(key);
  }
  productKeys = [...created, ...productKeys];
  pushAudit('create_key', `创建密钥 ${payload.count} 条`);
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
    const [productKeyText, typeText, statusText, companyIdText, enterpriseNameText] = line
      .split(',')
      .map((cell) => cell.trim());

    const productKey = productKeyText || '';
    const keyType = (typeText || 'personal_standard') as KeyType;
    const status = (statusText || 'unused') as KeyStatus;
    const companyId = companyIdText ? Number(companyIdText) : undefined;
    const enterpriseName = enterpriseNameText || (companyId ? `企业${companyId}` : undefined);

    const validType = ['personal_trial', 'personal_standard', 'enterprise_trial', 'enterprise_standard'].includes(keyType);
    const validStatus = ['unused', 'active', 'disabled', 'expired'].includes(status);
    const duplicated = productKeys.some((item) => item.product_key === productKey);

    if (!productKey || !validType || !validStatus || duplicated) {
      result.failedCount += 1;
      result.failedLines.push(line);
      continue;
    }

    productKeys.unshift({
      id: productKeyAutoId++,
      product_key: productKey,
      key_type: keyType,
      key_sub_type: keyType.startsWith('personal') ? 'personal' : 'enterprise',
      status,
      total_quota: getQuotaByType(keyType),
      used_count: status === 'unused' ? 0 : 1,
      company_id: companyId,
      metadata: {
        enterprise_name: enterpriseName,
        notes: '批量导入'
      },
      created_at: formatDate(new Date()),
      updated_at: formatDate(new Date())
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
    notes?: string;
  }
) {
  await delay();
  productKeys = productKeys.map((item) => {
    if (item.id !== id) {
      return item;
    }
    return {
      ...item,
      status: payload.status,
      metadata: {
        ...item.metadata,
        notes: payload.notes ?? item.metadata?.notes
      },
      updated_at: formatDate(new Date())
    };
  });
  pushAudit('update_user', `更新密钥 #${id}`);
}

export async function deleteProductKey(id: number) {
  await delay();
  productKeys = productKeys.filter((item) => item.id !== id);
  pushAudit('delete_key', `删除密钥 #${id}`);
}

export async function previewCompanyKeys(payload: { type: KeyType; count: number }) {
  await delay(100);
  const sampleCount = Math.min(Math.max(payload.count, 1), 5);
  const prefix = payload.type === 'enterprise_trial' ? 'TRIAL' : 'STD';
  return Array.from({ length: sampleCount }, () => randomKey(`UDAKE-${prefix}`));
}

export async function fetchCompanyKeys(params: {
  page: number;
  pageSize: number;
  company_id: number;
  type?: KeyType;
  assigned?: boolean;
}) {
  return fetchProductKeys({
    page: params.page,
    pageSize: params.pageSize,
    company_id: params.company_id,
    type: params.type,
    assigned: params.assigned
  });
}

export async function fetchCompanyKeyStats(companyId: number) {
  await delay(100);
  const current = productKeys.filter((item) => item.company_id === companyId);
  const totalKeys = current.length;
  const activeKeys = current.filter((item) => item.status === 'active').length;
  const assignedKeys = current.filter((item) => Boolean(item.user_id)).length;
  const availableKeys = current.filter((item) => !item.user_id && item.status !== 'disabled' && item.status !== 'expired').length;
  return {
    totalKeys,
    activeKeys,
    assignedKeys,
    availableKeys
  };
}

export async function batchGenerateCompanyKeys(payload: {
  company_id: number;
  type: Extract<KeyType, 'enterprise_trial' | 'enterprise_standard'>;
  count: number;
}) {
  return createProductKeys({
    type: payload.type,
    count: payload.count,
    company_id: payload.company_id,
    metadata: {
      enterprise_name: `企业${payload.company_id}`,
      notes: '企业管理员批量生成'
    }
  });
}

export async function fetchCompanyUsers(companyId: number) {
  await delay(120);
  return Array.from({ length: 8 }, (_, index) => ({
    id: companyId * 1000 + index + 1,
    name: `company_${companyId}_user_${index + 1}`
  }));
}

export async function assignCompanyKey(id: number, user: { user_id: number; user_name: string; operator: string }) {
  await delay();
  productKeys = productKeys.map((item) => {
    if (item.id !== id) {
      return item;
    }
    return {
      ...item,
      user_id: user.user_id,
      assigned_at: formatDate(new Date()),
      metadata: {
        ...item.metadata,
        assigned_user_name: user.user_name,
        assigned_by: user.operator
      },
      updated_at: formatDate(new Date())
    };
  });
  pushAudit('update_user', `分配密钥 #${id} 给 ${user.user_name}`, user.operator);
}

export async function revokeCompanyKey(id: number, operator: string) {
  await delay();
  productKeys = productKeys.map((item) => {
    if (item.id !== id) {
      return item;
    }
    return {
      ...item,
      user_id: undefined,
      assigned_at: undefined,
      metadata: {
        ...item.metadata,
        assigned_user_name: undefined,
        assigned_by: operator
      },
      updated_at: formatDate(new Date())
    };
  });
  pushAudit('update_user', `撤销密钥 #${id} 分配`, operator);
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

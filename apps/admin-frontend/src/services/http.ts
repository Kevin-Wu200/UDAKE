import axios from 'axios';
import type { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { ElMessage } from 'element-plus';
import { useAuthStore } from '../stores/auth';
import { resolveLoginRouteByContext } from '../utils/authRedirect';
import type {
  AuditEventType,
  AuditLog,
  CompanyAdmin,
  DashboardStats,
  EmailLog,
  EmailSendStatus,
  KeyStatus,
  KeyType,
  ProductKey,
  ProductKeyCreateForm,
  UserItem,
  UserRole
} from '../types/admin';

interface RetryConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

function resolveErrorMessage(error: AxiosError<any>) {
  const responseData = error.response?.data;

  if (typeof responseData?.message === 'string' && responseData.message.trim()) {
    return responseData.message;
  }

  if (typeof responseData?.detail === 'string' && responseData.detail.trim()) {
    return responseData.detail;
  }

  if (responseData?.detail && typeof responseData.detail?.message === 'string') {
    return responseData.detail.message;
  }

  if (error.code === 'ECONNABORTED' || error.message.includes('timeout')) {
    return '请求超时，请稍后重试';
  }

  if (!error.response) {
    return '网络连接失败，请检查网络后重试';
  }

  return '请求失败，请稍后重试';
}

export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 10000
});

interface BackendResponse<T> {
  success: boolean;
  message: string;
  data: T;
}

function unwrapData<T>(payload: BackendResponse<T> | undefined): T {
  return (payload?.data ?? {}) as T;
}

function resolveUnauthorizedRedirectPath(currentHashPath: string): string {
  if (currentHashPath.startsWith('/user')) {
    return resolveLoginRouteByContext('user');
  }
  if (currentHashPath.startsWith('/enterprise')) {
    return resolveLoginRouteByContext('enterprise');
  }
  return resolveLoginRouteByContext('admin');
}

http.interceptors.request.use((config) => {
  const authStore = useAuthStore();
  const token = authStore.getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

http.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<any>) => {
    const original = error.config as RetryConfig | undefined;
    const statusCode = error.response?.status;
    const requestUrl = String(original?.url ?? '');

    const isRefreshRequest = requestUrl.includes('/auth/refresh');
    const isLoginRequest = requestUrl.includes('/auth/login');

    if (statusCode === 401 && original && !original._retry && !isRefreshRequest && !isLoginRequest) {
      original._retry = true;
      const authStore = useAuthStore();
      const refreshedToken = await authStore.refreshAccessToken();
      if (refreshedToken) {
        original.headers = original.headers ?? {};
        original.headers.Authorization = `Bearer ${refreshedToken}`;
        return http(original);
      }

      authStore.clearToken();
      const currentHashPath = window.location.hash.replace(/^#/, '') || '/';
      const nextLoginPath = resolveUnauthorizedRedirectPath(currentHashPath);
      if (window.location.hash !== `#${nextLoginPath}`) {
        window.location.hash = `#${nextLoginPath}`;
      }
    }

    ElMessage.error(resolveErrorMessage(error));
    return Promise.reject(error);
  }
);

interface FetchProductKeysParams {
  page: number;
  pageSize: number;
  type?: KeyType;
  status?: KeyStatus;
  keyword?: string;
  company_id?: number;
  assigned?: boolean;
}

interface ProductKeyListData {
  keys?: ProductKey[];
  total?: number;
  pagination?: { total?: number };
}

interface ProductKeyStatsData {
  by_status?: Record<string, number>;
}

interface ProductKeyCreateData {
  keys?: ProductKey[];
}

interface ProductKeyBatchImportData {
  success_count?: number;
  failed_count?: number;
  failed_items?: Array<{ key?: string; reason?: string }>;
}

interface CompanyMeData {
  user?: {
    id: number;
    company_name?: string;
    company_admin_type?: 'trial' | 'standard';
    total_keys_created?: number;
    remaining_keys_allowed?: number;
    allowed_key_types?: Array<Extract<KeyType, 'enterprise_trial' | 'enterprise_standard'>>;
  };
}

export async function fetchProductKeys(params: FetchProductKeysParams): Promise<{ total: number; items: ProductKey[] }> {
  const response = await http.get<BackendResponse<ProductKeyListData>>('/admin/product-keys', {
    params: {
      page: params.page,
      page_size: params.pageSize,
      type: params.type,
      status: params.status,
      search: params.keyword?.trim() || undefined,
      company_id: params.company_id
    }
  });
  const data = unwrapData(response.data);
  const items = Array.isArray(data.keys) ? data.keys : [];
  const total = Number(data.total ?? data.pagination?.total ?? 0);
  return { total, items };
}

export async function fetchProductKeyStats(): Promise<{ total: number; active: number; unused: number }> {
  const response = await http.get<BackendResponse<ProductKeyStatsData>>('/admin/product-keys/stats');
  const data = unwrapData(response.data);
  const byStatus = data.by_status ?? {};
  const total = Object.values(byStatus).reduce((sum, count) => sum + Number(count || 0), 0);
  return {
    total,
    active: Number(byStatus.active || 0),
    unused: Number(byStatus.unused || 0)
  };
}

export async function fetchCompanyKeyStats(companyId: number): Promise<{
  totalKeys: number;
  activeKeys: number;
  assignedKeys: number;
  availableKeys: number;
}> {
  const response = await http.get<BackendResponse<{
    total: number;
    active: number;
    assigned: number;
    available: number;
  }>>(`/admin/companies/${companyId}/key-stats`);
  const data = unwrapData(response.data);
  return {
    totalKeys: data.total || 0,
    activeKeys: data.active || 0,
    assignedKeys: data.assigned || 0,
    availableKeys: data.available || 0
  };
}

export async function fetchCompanyKeys(params: {
  page: number;
  pageSize: number;
  company_id: number;
  type?: KeyType;
  assigned?: boolean;
}): Promise<{ total: number; items: ProductKey[] }> {
  return fetchProductKeys({
    page: params.page,
    pageSize: params.pageSize,
    company_id: params.company_id,
    type: params.type,
    assigned: params.assigned
  });
}

export async function createProductKeys(payload: ProductKeyCreateForm): Promise<ProductKey[]> {
  const response = await http.post<BackendResponse<ProductKeyCreateData>>('/admin/product-keys', payload);
  const data = unwrapData(response.data);
  return Array.isArray(data.keys) ? data.keys : [];
}

export async function importProductKeys(rawText: string): Promise<{ successCount: number; failedCount: number; failedLines: string[] }> {
  const rows = rawText
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => line.split(',').map((cell) => cell.trim()))
    .filter((cells) => cells.length >= 2);

  const typeBuckets = new Map<KeyType, { keys: string[]; companyName?: string }>();
  for (const [productKeyText, typeText, _statusText, _companyIdText, enterpriseNameText] of rows) {
    const normalizedType = String(typeText || '').toLowerCase() as KeyType;
    if (!['personal_trial', 'personal_standard', 'enterprise_trial', 'enterprise_standard'].includes(normalizedType)) {
      continue;
    }
    if (!typeBuckets.has(normalizedType)) {
      typeBuckets.set(normalizedType, { keys: [], companyName: enterpriseNameText || undefined });
    }
    const bucket = typeBuckets.get(normalizedType)!;
    bucket.keys.push(String(productKeyText || '').toUpperCase());
    if (!bucket.companyName && enterpriseNameText) {
      bucket.companyName = enterpriseNameText;
    }
  }

  let successCount = 0;
  let failedCount = 0;
  const failedLines: string[] = [];
  for (const [type, bucket] of typeBuckets) {
    const response = await http.post<BackendResponse<ProductKeyBatchImportData>>('/admin/product-keys/batch', {
      type,
      keys: bucket.keys,
      duplicate_action: 'skip',
      company_name: type.startsWith('enterprise') ? bucket.companyName || '未命名企业' : undefined
    });
    const data = unwrapData(response.data);
    successCount += Number(data.success_count || 0);
    failedCount += Number(data.failed_count || 0);
    for (const item of data.failed_items ?? []) {
      if (item.key) {
        failedLines.push(item.key);
      }
    }
  }

  return { successCount, failedCount, failedLines };
}

export async function updateProductKey(id: number, payload: { status?: KeyStatus; notes?: string; extend_days?: number }) {
  const requestPayload = {
    status: payload.status,
    extend_days: payload.extend_days
  };
  await http.put(`/admin/product-keys/${id}`, requestPayload);
}

export async function deleteProductKey(id: number) {
  await http.delete(`/admin/product-keys/${id}`);
}

export async function previewCompanyKeys(payload: { type: KeyType; count: number }): Promise<string[]> {
  const response = await http.get<BackendResponse<{ keys: string[] }>>('/admin/product-keys/preview', {
    params: payload
  });
  return unwrapData(response.data).keys || [];
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

export async function fetchCompanyUsers(companyId: number): Promise<Array<{ id: number; name: string }>> {
  const response = await http.get<BackendResponse<Array<{ id: number; name: string }>>>(`/admin/companies/${companyId}/users`);
  return unwrapData(response.data);
}

export async function assignCompanyKey(id: number, user: { user_id: number; user_name: string; operator: string }) {
  await http.post(`/admin/product-keys/${id}/assign`, user);
}

export async function revokeCompanyKey(id: number, operator: string) {
  await http.post(`/admin/product-keys/${id}/revoke`, { operator });
}

export async function fetchUsers(params: {
  page: number;
  pageSize: number;
  role?: UserRole;
  status?: 'enabled' | 'disabled';
  keyword?: string;
}): Promise<{ total: number; items: UserItem[] }> {
  const response = await http.get<BackendResponse<{ users: Array<Record<string, unknown>>; total: number; pagination?: { total?: number } }>>(
    '/admin/users',
    {
    params: {
      page: params.page,
      page_size: params.pageSize,
      role: params.role,
      status: params.status === 'enabled' ? 'active' : params.status === 'disabled' ? 'disabled' : undefined,
      search: params.keyword
    }
  }
  );
  const data = unwrapData(response.data);
  const items: UserItem[] = Array.isArray(data.users)
    ? data.users.map((raw) => {
      const role = String(raw.role ?? '');
      const statusText = String(raw.status ?? '');
      const status = ['active', 'enabled', 'true', '1'].includes(statusText.toLowerCase());
      return {
        id: Number(raw.id ?? 0),
        username: String(raw.username ?? ''),
        email: String(raw.email ?? ''),
        role,
        status,
        createdAt: String(raw.createdAt ?? raw.created_at ?? ''),
        lastLoginAt: String(raw.lastLoginAt ?? raw.last_login_at ?? ''),
        devices: [],
        loginLogs: []
      };
    })
    : [];
  return {
    total: Number(data.total ?? data.pagination?.total ?? 0),
    items
  };
}

export async function updateUserStatus(id: number, enabled: boolean) {
  await http.post(`/admin/users/${id}/toggle-status`, { status: enabled ? 'active' : 'disabled' });
}

export async function resetUserPassword(id: number) {
  await http.post(`/admin/users/${id}/reset-password`);
}

export async function fetchAuditLogs(params: {
  page: number;
  pageSize: number;
  eventType?: AuditEventType;
  keyword?: string;
  startTime?: string;
  endTime?: string;
}): Promise<{ total: number; items: AuditLog[] }> {
  const response = await http.get<BackendResponse<{ logs: AuditLog[]; total: number }>>('/admin/audit-logs', {
    params: {
      page: params.page,
      page_size: params.pageSize,
      event_type: params.eventType,
      search: params.keyword,
      start_time: params.startTime,
      end_time: params.endTime
    }
  });
  const data = unwrapData(response.data);
  return {
    total: data.total || 0,
    items: data.logs || []
  };
}

export async function fetchAuditLogsForExport(params: {
  eventType?: AuditEventType;
  keyword?: string;
  startTime?: string;
  endTime?: string;
}): Promise<AuditLog[]> {
  const response = await http.get<BackendResponse<AuditLog[]>>('/admin/audit-logs/export', {
    params: {
      event_type: params.eventType,
      search: params.keyword,
      start_time: params.startTime,
      end_time: params.endTime,
      format: 'json'
    }
  });
  return unwrapData(response.data);
}

export async function fetchEmailLogs(params: {
  page: number;
  pageSize: number;
  status?: EmailSendStatus;
  startTime?: string;
  endTime?: string;
}): Promise<{ total: number; items: EmailLog[] }> {
  const response = await http.get<BackendResponse<{ logs: EmailLog[]; total: number }>>('/workflow/notifications/email-logs', {
    params: {
      page: params.page,
      page_size: params.pageSize,
      status: params.status,
      start_time: params.startTime,
      end_time: params.endTime
    }
  });
  const data = unwrapData(response.data);
  return {
    total: data.total || 0,
    items: data.logs || []
  };
}

export async function resendEmailLog(id: number) {
  await http.post(`/workflow/notifications/email-logs/${id}/resend`);
}

export async function fetchDashboardStats(): Promise<DashboardStats> {
  const response = await http.get<BackendResponse<DashboardStats>>('/admin/stats');
  return unwrapData(response.data);
}

export async function fetchCompanyAdminProfile(_companyId: number): Promise<CompanyAdmin> {
  const response = await http.get<BackendResponse<CompanyMeData>>('/company/me');
  const user = unwrapData(response.data).user;
  if (!user || user.company_admin_type !== 'trial' && user.company_admin_type !== 'standard') {
    throw new Error('当前用户不是企业管理员');
  }
  const maxKeys = user.company_admin_type === 'trial' ? 50 : 300;
  const total = Number(user.total_keys_created || 0);
  return {
    id: user.id,
    company_id: _companyId,
    company_name: user.company_name || `企业${_companyId}`,
    company_admin_type: user.company_admin_type,
    total_keys_created: total,
    max_keys_allowed: maxKeys,
    remaining_keys_quota: Math.max(0, Number(user.remaining_keys_allowed ?? maxKeys - total)),
    allowed_key_types: Array.isArray(user.allowed_key_types) ? user.allowed_key_types : ['enterprise_trial']
  };
}

import axios from 'axios';
import type { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { ElMessage } from 'element-plus';
import { useAuthStore } from '../stores/auth';
import type { CompanyAdmin, KeyStatus, KeyType, ProductKey, ProductKeyCreateForm } from '../types/admin';
import {
  createProductKeys as createProductKeysMock,
  deleteProductKey as deleteProductKeyMock,
  fetchCompanyAdminProfile as fetchCompanyAdminProfileMock,
  fetchProductKeyStats as fetchProductKeyStatsMock,
  fetchProductKeys as fetchProductKeysMock,
  importProductKeys as importProductKeysMock,
  updateProductKey as updateProductKeyMock
} from './mockApi';

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

export function isMockApiEnabled(): boolean {
  const flag = String(import.meta.env.VITE_USE_MOCK_API ?? '').trim().toLowerCase();
  if (import.meta.env.PROD) {
    return false;
  }
  return flag === '1' || flag === 'true' || flag === 'yes' || flag === 'on';
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
      if (window.location.hash !== '#/user/login') {
        window.location.hash = '#/user/login';
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
  if (isMockApiEnabled()) {
    return fetchProductKeysMock(params);
  }

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
  if (isMockApiEnabled()) {
    return fetchProductKeyStatsMock();
  }

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

export async function createProductKeys(payload: ProductKeyCreateForm): Promise<ProductKey[]> {
  if (isMockApiEnabled()) {
    return createProductKeysMock(payload);
  }

  const response = await http.post<BackendResponse<ProductKeyCreateData>>('/admin/product-keys', payload);
  const data = unwrapData(response.data);
  return Array.isArray(data.keys) ? data.keys : [];
}

export async function importProductKeys(rawText: string): Promise<{ successCount: number; failedCount: number; failedLines: string[] }> {
  if (isMockApiEnabled()) {
    return importProductKeysMock(rawText);
  }

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
  if (isMockApiEnabled()) {
    return updateProductKeyMock(id, payload);
  }
  const requestPayload = {
    status: payload.status,
    extend_days: payload.extend_days
  };
  await http.put(`/admin/product-keys/${id}`, requestPayload);
}

export async function deleteProductKey(id: number) {
  if (isMockApiEnabled()) {
    return deleteProductKeyMock(id);
  }
  await http.delete(`/admin/product-keys/${id}`);
}

export async function fetchCompanyAdminProfile(_companyId: number): Promise<CompanyAdmin> {
  if (isMockApiEnabled()) {
    return fetchCompanyAdminProfileMock(_companyId);
  }
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

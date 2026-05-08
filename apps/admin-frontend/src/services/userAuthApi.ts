import { http } from './http';
import type { DeviceListResult, UserSessionPayload } from '../types/auth';
import { buildDeviceInfoPayload } from '../utils/auth';
import type { AxiosError } from 'axios';

interface BackendResponse<T> {
  success: boolean;
  message: string;
  data: T;
}

interface LoginResponse {
  access_token: string;
  refresh_token: string;
  user_info: {
    user_id: number;
    email: string;
    role: string;
    permissions: string[];
    enterprise_id?: number | null;
  };
}

interface RefreshResponse {
  access_token: string;
}

interface DeviceListResponse {
  items: Array<{
    device_id: string;
    device_name: string;
    device_type: string;
    os: string;
    browser: string;
    ip: string;
    location: string;
    last_login_at: number;
    status: string;
    is_current: boolean;
  }>;
  pagination: {
    page: number;
    page_size: number;
    total: number;
  };
  current_device_id: string | null;
}

interface ProductKeyValidateApiResponse {
  valid: boolean;
  key_type: string | null;
  message: string;
  error_code?: string;
  suggestion?: string;
}

export interface KeyValidationResult {
  valid: boolean;
  keyType: string;
  message: string;
  errorCode?: string;
  suggestion?: string;
}

type KeyValidationCacheEntry = {
  result: KeyValidationResult;
  timestamp: number;
};

type KeyValidationCache = Record<string, KeyValidationCacheEntry>;

const KEY_VALIDATION_CACHE_STORAGE_KEY = 'udake:key_validation_cache:v1';
const KEY_VALIDATION_CACHE_TTL = 10 * 60 * 1000;
const KEY_VALIDATION_CACHE_MAX_ENTRIES = 100;
const keyValidationMemoryCache = new Map<string, KeyValidationCacheEntry>();

function unwrap<T>(payload: BackendResponse<T>): T {
  return payload.data;
}

function mapSession(data: LoginResponse): UserSessionPayload {
  return {
    accessToken: data.access_token,
    refreshToken: data.refresh_token,
    user: {
      userId: data.user_info.user_id,
      email: data.user_info.email,
      role: data.user_info.role,
      permissions: data.user_info.permissions ?? [],
      enterpriseId: data.user_info.enterprise_id ?? null
    }
  };
}

function mapDeviceList(data: DeviceListResponse): DeviceListResult {
  return {
    items: data.items.map((item) => ({
      deviceId: item.device_id,
      deviceName: item.device_name,
      deviceType: item.device_type,
      os: item.os,
      browser: item.browser,
      ip: item.ip,
      location: item.location,
      lastLoginAt: item.last_login_at,
      status: item.status,
      isCurrent: item.is_current
    })),
    pagination: {
      page: data.pagination.page,
      pageSize: data.pagination.page_size,
      total: data.pagination.total
    },
    currentDeviceId: data.current_device_id
  };
}

function resolveApiErrorMessage(error: unknown): string {
  const axiosError = error as AxiosError<any>;
  const responseData = axiosError?.response?.data;
  const errorCode = responseData?.detail?.data?.error_code ?? responseData?.data?.error_code;
  if (typeof errorCode === 'string' && errorCode) {
    return mapErrorCodeToMessage(errorCode);
  }
  if (typeof responseData?.message === 'string' && responseData.message.trim()) {
    return responseData.message;
  }
  if (typeof responseData?.detail?.message === 'string' && responseData.detail.message.trim()) {
    return responseData.detail.message;
  }
  return '密钥验证失败，请稍后重试';
}

function mapErrorCodeToMessage(errorCode: string): string {
  switch (errorCode) {
    case 'KEY_FORMAT_INVALID':
      return '密钥格式不正确，请输入 XXX-XXXX-XXXX-XXXX';
    case 'KEY_CHECKSUM_MISMATCH':
      return '密钥校验失败，请检查输入内容';
    case 'KEY_NOT_FOUND':
      return '密钥不存在，请核对密钥来源';
    case 'KEY_ALREADY_USED':
      return '该密钥已被使用，请更换未激活密钥';
    case 'KEY_REVOKED':
      return '该密钥已被撤销，请联系管理员';
    case 'KEY_EXPIRED':
      return '该密钥已过期，请联系管理员续期';
    case 'RATE_LIMITED':
      return '请求过于频繁，请稍后再试';
    default:
      return '密钥验证失败，请稍后重试';
  }
}

function nowTs(): number {
  return Date.now();
}

function normalizeKey(raw: string): string {
  return raw.trim().toUpperCase();
}

function pruneExpiredCache(cache: KeyValidationCache, current: number): KeyValidationCache {
  const next: KeyValidationCache = {};
  const entries = Object.entries(cache);
  for (const [key, value] of entries) {
    if (current - value.timestamp <= KEY_VALIDATION_CACHE_TTL) {
      next[key] = value;
    }
  }
  return next;
}

function loadValidationCacheFromStorage(): KeyValidationCache {
  try {
    const raw = localStorage.getItem(KEY_VALIDATION_CACHE_STORAGE_KEY);
    if (!raw) {
      return {};
    }
    const parsed = JSON.parse(raw) as KeyValidationCache;
    return pruneExpiredCache(parsed, nowTs());
  } catch {
    return {};
  }
}

function saveValidationCacheToStorage(cache: KeyValidationCache): void {
  const entries = Object.entries(cache);
  if (entries.length > KEY_VALIDATION_CACHE_MAX_ENTRIES) {
    entries.sort((a, b) => b[1].timestamp - a[1].timestamp);
  }
  const sliced = entries.slice(0, KEY_VALIDATION_CACHE_MAX_ENTRIES);
  const next: KeyValidationCache = {};
  for (const [key, value] of sliced) {
    next[key] = value;
  }
  localStorage.setItem(KEY_VALIDATION_CACHE_STORAGE_KEY, JSON.stringify(next));
}

function getValidationCacheEntry(key: string): KeyValidationCacheEntry | null {
  const inMemory = keyValidationMemoryCache.get(key);
  const current = nowTs();
  if (inMemory && current - inMemory.timestamp <= KEY_VALIDATION_CACHE_TTL) {
    return inMemory;
  }
  const storage = loadValidationCacheFromStorage();
  const entry = storage[key];
  if (!entry) {
    return null;
  }
  if (current - entry.timestamp > KEY_VALIDATION_CACHE_TTL) {
    return null;
  }
  keyValidationMemoryCache.set(key, entry);
  return entry;
}

function setValidationCacheEntry(key: string, result: KeyValidationResult): void {
  const entry: KeyValidationCacheEntry = {
    result,
    timestamp: nowTs()
  };
  keyValidationMemoryCache.set(key, entry);
  if (keyValidationMemoryCache.size > KEY_VALIDATION_CACHE_MAX_ENTRIES) {
    const oldestKey = keyValidationMemoryCache.keys().next().value;
    if (typeof oldestKey === 'string') {
      keyValidationMemoryCache.delete(oldestKey);
    }
  }
  const storage = loadValidationCacheFromStorage();
  storage[key] = entry;
  saveValidationCacheToStorage(storage);
}

function mapValidateResult(data: ProductKeyValidateApiResponse): KeyValidationResult {
  return {
    valid: Boolean(data.valid),
    keyType: typeof data.key_type === 'string' ? data.key_type : '',
    message: typeof data.message === 'string' && data.message.trim() ? data.message : '密钥验证完成',
    errorCode: typeof data.error_code === 'string' ? data.error_code : undefined,
    suggestion: typeof data.suggestion === 'string' ? data.suggestion : undefined
  };
}

export async function loginUser(email: string, password: string): Promise<UserSessionPayload> {
  const response = await http.post<BackendResponse<LoginResponse>>('/auth/login', {
    email,
    password,
    device_info: buildDeviceInfoPayload()
  });
  return mapSession(unwrap(response.data));
}

export async function registerUser(email: string, password: string, productKey: string) {
  const response = await http.post<BackendResponse<Record<string, unknown>>>('/auth/register', {
    email,
    password,
    product_key: productKey
  });
  return unwrap(response.data);
}

export async function validateProductKey(productKey: string): Promise<KeyValidationResult> {
  const normalized = normalizeKey(productKey);
  if (normalized) {
    const cached = getValidationCacheEntry(normalized);
    if (cached) {
      return cached.result;
    }
  }
  try {
    const response = await http.post<BackendResponse<ProductKeyValidateApiResponse>>('/product-keys/validate', {
      product_key: normalized || productKey
    });
    const result = mapValidateResult(unwrap(response.data));
    if (normalized && result.valid) {
      setValidationCacheEntry(normalized, result);
    }
    return result;
  } catch (error) {
    throw new Error(resolveApiErrorMessage(error));
  }
}

export async function verifyRegisterCode(email: string, code: string) {
  const response = await http.post<BackendResponse<Record<string, unknown>>>('/auth/verify-email-code', {
    email,
    code
  });
  return unwrap(response.data);
}

export async function refreshToken(refreshToken: string): Promise<string> {
  const response = await http.post<BackendResponse<RefreshResponse>>('/auth/refresh', {
    refresh_token: refreshToken
  });
  return unwrap(response.data).access_token;
}

export async function logoutUser(accessToken: string) {
  const response = await http.post<BackendResponse<Record<string, unknown>>>('/auth/logout', {
    access_token: accessToken
  });
  return unwrap(response.data);
}

export async function sendResetPasswordCode(email: string, productKey: string) {
  const response = await http.post<BackendResponse<Record<string, unknown>>>('/auth/reset-password/send-code', {
    email,
    product_key: productKey
  });
  return unwrap(response.data);
}

export async function resetPasswordByCode(
  email: string,
  code: string,
  newPassword: string,
  confirmPassword: string
) {
  const response = await http.post<BackendResponse<Record<string, unknown>>>('/auth/reset-password/verify', {
    email,
    code,
    new_password: newPassword,
    confirm_password: confirmPassword
  });
  return unwrap(response.data);
}

export async function changePassword(oldPassword: string, newPassword: string, confirmPassword: string) {
  const response = await http.post<BackendResponse<Record<string, unknown>>>('/auth/change-password', {
    old_password: oldPassword,
    new_password: newPassword,
    confirm_password: confirmPassword
  });
  return unwrap(response.data);
}

export async function sendChangeEmailCode(newEmail: string, currentPassword: string) {
  const response = await http.post<BackendResponse<Record<string, unknown>>>('/auth/change-email/send-code', {
    new_email: newEmail,
    current_password: currentPassword
  });
  return unwrap(response.data);
}

export async function verifyChangeEmailCode(code: string) {
  const response = await http.post<BackendResponse<Record<string, unknown>>>('/auth/change-email/verify', {
    code
  });
  return unwrap(response.data);
}

export async function fetchUserDevices(page: number, pageSize: number): Promise<DeviceListResult> {
  const response = await http.get<BackendResponse<DeviceListResponse>>('/devices', {
    params: {
      page,
      page_size: pageSize
    }
  });
  return mapDeviceList(unwrap(response.data));
}

export async function kickUserDevice(deviceId: string) {
  const response = await http.delete<BackendResponse<Record<string, unknown>>>(`/devices/${deviceId}`);
  return unwrap(response.data);
}

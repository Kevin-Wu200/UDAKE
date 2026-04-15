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
}

export interface KeyValidationResult {
  valid: boolean;
  keyType: string;
  message: string;
}

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
      permissions: data.user_info.permissions ?? []
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
  if (typeof responseData?.message === 'string' && responseData.message.trim()) {
    return responseData.message;
  }
  if (typeof responseData?.detail?.message === 'string' && responseData.detail.message.trim()) {
    return responseData.detail.message;
  }
  return '密钥验证失败，请稍后重试';
}

function mapValidateResult(data: ProductKeyValidateApiResponse): KeyValidationResult {
  return {
    valid: Boolean(data.valid),
    keyType: typeof data.key_type === 'string' ? data.key_type : '',
    message: typeof data.message === 'string' && data.message.trim() ? data.message : '密钥验证完成'
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
  try {
    const response = await http.post<BackendResponse<ProductKeyValidateApiResponse>>('/product-keys/validate', {
      product_key: productKey
    });
    return mapValidateResult(unwrap(response.data));
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

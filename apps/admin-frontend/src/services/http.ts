import axios from 'axios';
import type { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { ElMessage } from 'element-plus';
import { useAuthStore } from '../stores/auth';

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

import axios from 'axios';
import { ElMessage } from 'element-plus';
import { useAuthStore } from '../stores/auth';

export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 10000
});

http.interceptors.request.use((config) => {
  const authStore = useAuthStore();
  if (authStore.accessToken) {
    config.headers.Authorization = `Bearer ${authStore.accessToken}`;
  }
  return config;
});

http.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = error?.response?.data?.message ?? '请求失败，请稍后重试';
    ElMessage.error(message);
    return Promise.reject(error);
  }
);

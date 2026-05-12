import axios from 'axios';
import { defineStore } from 'pinia';
import type { AuthUser, UserSessionPayload } from '../types/auth';
import { getTokenExpireAtMs } from '../utils/auth';
import { loginUser, type LoginContext } from '../services/userAuthApi';

const ACCESS_TOKEN_KEY = 'udake_access_token';
const REFRESH_TOKEN_KEY = 'udake_refresh_token';
const USER_INFO_KEY = 'udake_user_info';
const LOGIN_USER_KEY = 'admin_login_user';
const REAL_USERNAME_KEY = 'udake_real_username';
const LEGACY_ADMIN_ACCESS_TOKEN_KEY = 'admin_access_token';
const VALIDATE_CACHE_MS = 60_000;
const ADMIN_ALLOWED_ROLES = ['company_admin', 'super_admin', 'admin'] as const;

interface RefreshResponse {
  access_token: string;
}

interface BackendResponse<T> {
  success: boolean;
  message: string;
  data: T;
}

function parseJson<T>(raw: string | null): T | null {
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

function getInitialAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY) ?? localStorage.getItem(LEGACY_ADMIN_ACCESS_TOKEN_KEY) ?? '';
}

function normalizeUser(payload: UserSessionPayload): AuthUser {
  const enterpriseId = payload.user.enterpriseId ?? null;
  return {
    username: payload.user.username,
    userId: payload.user.userId,
    email: payload.user.email,
    role: payload.user.role,
    permissions: payload.user.permissions,
    enterpriseId,
    companyId: enterpriseId
  };
}

export function isAdminRole(role: string | null | undefined): boolean {
  return typeof role === 'string' && ADMIN_ALLOWED_ROLES.includes(role as (typeof ADMIN_ALLOWED_ROLES)[number]);
}

export function resolvePostLoginPathByRole(role: string | null | undefined): string {
  if (role === 'enterprise') {
    return '/enterprise/dashboard';
  }
  if (isAdminRole(role)) {
    return '/dashboard';
  }
  return '/user/devices';
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    accessToken: getInitialAccessToken(),
    refreshToken: localStorage.getItem(REFRESH_TOKEN_KEY) ?? '',
    user: parseJson<AuthUser>(localStorage.getItem(USER_INFO_KEY)),
    username: localStorage.getItem(LOGIN_USER_KEY) ?? '',
    user_Name: localStorage.getItem(REAL_USERNAME_KEY) ?? '',
    refreshTimer: null as number | null,
    bootstrapped: false,
    refreshPromise: null as Promise<string | null> | null,
    lastValidatedAt: 0
  }),
  getters: {
    isLoggedIn: (state) => Boolean(state.accessToken),
    isLegacyAdminSession: (state) => Boolean(state.accessToken && !state.refreshToken && !state.user),
    hasAdminAccess: (state) => Boolean(state.accessToken && (state.user ? isAdminRole(state.user.role) : true)),
    isSuperAdmin: (state) => Boolean(state.accessToken && (state.user ? state.user.role === 'super_admin' : true)),
    isCompanyAdmin: (state) => Boolean(state.user?.role === 'company_admin'),
    displayName: (state) => state.user_Name || state.username || state.user?.email || 'User',
    currentCompany: (state) => {
      const companyId = state.user?.enterpriseId ?? state.user?.companyId ?? state.user?.userId ?? 1;
      const prefix = state.user?.email?.split('@')[0] || '默认';
      return {
        id: companyId,
        name: `${prefix}企业`
      };
    }
  },
  actions: {
    setUser(user: AuthUser | null) {
      this.user = user;
      if (user) {
        localStorage.setItem(USER_INFO_KEY, JSON.stringify(user));
        this.username = user.username;
        localStorage.setItem(LOGIN_USER_KEY, user.username);
        this.user_Name = user.username;
        localStorage.setItem(REAL_USERNAME_KEY, user.username);
      } else {
        localStorage.removeItem(USER_INFO_KEY);
      }
    },
    setToken(accessToken: string, refreshToken?: string) {
      this.accessToken = accessToken;
      localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
      localStorage.setItem(LEGACY_ADMIN_ACCESS_TOKEN_KEY, accessToken);

      if (typeof refreshToken === 'string') {
        this.refreshToken = refreshToken;
        if (refreshToken) {
          localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
        } else {
          localStorage.removeItem(REFRESH_TOKEN_KEY);
        }
      }

      this.startTokenAutoRefresh();
    },
    getToken() {
      return this.accessToken;
    },
    clearToken() {
      this.stopTokenAutoRefresh();
      this.accessToken = '';
      this.refreshToken = '';
      this.user = null;
      this.username = '';
      this.user_Name = '';
      this.lastValidatedAt = 0;
      localStorage.removeItem(ACCESS_TOKEN_KEY);
      localStorage.removeItem(LEGACY_ADMIN_ACCESS_TOKEN_KEY);
      localStorage.removeItem(REFRESH_TOKEN_KEY);
      localStorage.removeItem(USER_INFO_KEY);
      localStorage.removeItem(LOGIN_USER_KEY);
      localStorage.removeItem(REAL_USERNAME_KEY);
    },
    async login(email: string, password: string, context: LoginContext = 'admin') {
      const session = await loginUser(email, password, context);
      this.applyUserSession(session);
      return resolvePostLoginPathByRole(session.user.role);
    },
    applyUserSession(payload: UserSessionPayload) {
      this.setUser(normalizeUser(payload));
      this.setToken(payload.accessToken, payload.refreshToken);
    },
    logout() {
      this.clearToken();
    },
    async logoutWithApi() {
      const token = this.accessToken;
      this.clearToken();
      if (!token) {
        return;
      }
      try {
        await axios.post(`${import.meta.env.VITE_API_BASE_URL}/auth/logout`, {
          access_token: token
        });
      } catch {
        // 忽略登出API失败，前端会话已清理
      }
    },
    async validateCurrentToken(force = false) {
      if (this.isLegacyAdminSession) {
        return true;
      }

      if (!this.accessToken) {
        return false;
      }

      const now = Date.now();
      if (!force && now - this.lastValidatedAt < VALIDATE_CACHE_MS) {
        return true;
      }

      try {
        await axios.get(`${import.meta.env.VITE_API_BASE_URL}/devices`, {
          params: { page: 1, page_size: 1 },
          headers: { Authorization: `Bearer ${this.accessToken}` },
          timeout: 8000
        });
        this.lastValidatedAt = now;
        return true;
      } catch {
        return false;
      }
    },
    async refreshAccessToken() {
      if (!this.refreshToken) {
        return null;
      }
      if (this.refreshPromise) {
        return this.refreshPromise;
      }

      this.refreshPromise = (async () => {
        try {
          const response = await axios.post<BackendResponse<RefreshResponse>>(
            `${import.meta.env.VITE_API_BASE_URL}/auth/refresh`,
            { refresh_token: this.refreshToken },
            { timeout: 8000 }
          );
          const refreshedToken = response.data?.data?.access_token;
          if (!refreshedToken) {
            throw new Error('refresh token response invalid');
          }
          this.setToken(refreshedToken);
          this.lastValidatedAt = Date.now();
          return refreshedToken;
        } catch {
          this.clearToken();
          return null;
        } finally {
          this.refreshPromise = null;
        }
      })();

      return this.refreshPromise;
    },
    startTokenAutoRefresh() {
      this.stopTokenAutoRefresh();
      if (!this.accessToken || !this.refreshToken) {
        return;
      }

      const expireAtMs = getTokenExpireAtMs(this.accessToken);
      if (!expireAtMs) {
        return;
      }

      const refreshAtMs = expireAtMs - 5 * 60 * 1000;
      const delay = Math.max(5000, refreshAtMs - Date.now());
      this.refreshTimer = window.setTimeout(() => {
        void this.refreshAccessToken();
      }, delay);
    },
    stopTokenAutoRefresh() {
      if (this.refreshTimer !== null) {
        window.clearTimeout(this.refreshTimer);
        this.refreshTimer = null;
      }
    },
    async bootstrapAuth() {
      if (this.bootstrapped) {
        return;
      }
      this.bootstrapped = true;

      if (!this.accessToken) {
        return;
      }

      if (this.isLegacyAdminSession) {
        return;
      }

      const valid = await this.validateCurrentToken(true);
      if (valid) {
        this.startTokenAutoRefresh();
        return;
      }

      const refreshedToken = await this.refreshAccessToken();
      if (!refreshedToken) {
        this.clearToken();
        return;
      }

      const validated = await this.validateCurrentToken(true);
      if (!validated) {
        this.clearToken();
        return;
      }

      this.startTokenAutoRefresh();
    }
  }
});

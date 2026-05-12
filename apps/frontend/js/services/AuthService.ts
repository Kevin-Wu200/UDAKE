import { resolveRuntimeApiBaseUrl } from './api/runtime.js';

export interface AuthUserInfo {
    id?: number;
    user_id?: number;
    username?: string;
    email: string;
    role: string;
    permissions?: string[];
    product_key_id?: number | null;
    product_key?: string | null;
    key_status?: string;
}

export interface ProductKeyInfo {
    product_key: string;
    key_type: string;
    status: string;
    total_quota: number;
    used_count: number;
    expires_at?: string | null;
}

interface AuthLoginResult {
    access_token: string;
    refresh_token: string;
    user_info: {
        user_id: number;
        email: string;
        role: string;
        permissions?: string[];
        product_key?: string | null;
        key_status?: string;
    };
}

export type AuthLoginContext = 'admin' | 'enterprise' | 'user';

interface ApiEnvelope<T> {
    success?: boolean;
    message?: string;
    data?: T;
    detail?: string | { message?: string };
}

const STORAGE_KEYS = {
    accessToken: 'access_token',
    refreshToken: 'refresh_token',
    userInfo: 'user_info',
    productKeyInfo: 'product_key_info',
};

function decodeJwtPayload(token: string): Record<string, unknown> | null {
    try {
        const parts = token.split('.');
        if (parts.length < 2) {
            return null;
        }
        const payload = parts[1].replace(/-/g, '+').replace(/_/g, '/');
        const padLength = (4 - (payload.length % 4)) % 4;
        const text = atob(payload + '='.repeat(padLength));
        return JSON.parse(text) as Record<string, unknown>;
    } catch {
        return null;
    }
}

export class AuthService {
    private readonly apiBaseUrl: string;

    constructor(apiBaseUrl?: string) {
        this.apiBaseUrl = (apiBaseUrl || resolveRuntimeApiBaseUrl()).replace(/\/+$/, '');
    }

    public getAccessToken(): string | null {
        return localStorage.getItem(STORAGE_KEYS.accessToken);
    }

    public getRefreshToken(): string | null {
        return localStorage.getItem(STORAGE_KEYS.refreshToken);
    }

    public getStoredUserInfo(): AuthUserInfo | null {
        const raw = localStorage.getItem(STORAGE_KEYS.userInfo);
        if (!raw) {
            return null;
        }
        try {
            return JSON.parse(raw) as AuthUserInfo;
        } catch {
            return null;
        }
    }

    public getStoredProductKeyInfo(): ProductKeyInfo | null {
        const raw = localStorage.getItem(STORAGE_KEYS.productKeyInfo);
        if (!raw) {
            return null;
        }
        try {
            return JSON.parse(raw) as ProductKeyInfo;
        } catch {
            return null;
        }
    }

    public async login(username: string, password: string, loginContext: AuthLoginContext = 'user'): Promise<AuthLoginResult> {
        const payload = {
            email: username.trim(),
            password,
            context: loginContext,
            device_info: {
                platform: navigator.platform || 'unknown',
                language: navigator.language || 'unknown',
                user_agent: navigator.userAgent || 'unknown',
            },
        };

        const data = await this.request<AuthLoginResult>('/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        const userInfo: AuthUserInfo = {
            id: data.user_info.user_id,
            user_id: data.user_info.user_id,
            username: data.user_info.email.split('@', 1)[0] || data.user_info.email,
            email: data.user_info.email,
            role: data.user_info.role,
            permissions: data.user_info.permissions || [],
            product_key_id: null,
            product_key: data.user_info.product_key || null,
            key_status: data.user_info.key_status || 'unused',
        };
        this.persistAuthSession(data.access_token, data.refresh_token, userInfo, this.getStoredProductKeyInfo());
        return data;
    }

    public async logout(): Promise<void> {
        const accessToken = this.getAccessToken();
        if (accessToken) {
            try {
                await this.request('/auth/logout', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ access_token: accessToken }),
                });
            } catch {
                // 忽略登出接口失败，始终清理本地会话
            }
        }
        this.clearSession();
    }

    public async refreshToken(): Promise<string> {
        const refreshToken = this.getRefreshToken();
        if (!refreshToken) {
            throw new Error('刷新令牌不存在，请重新登录');
        }
        const data = await this.request<{ access_token: string }>('/auth/refresh', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken }),
        });
        localStorage.setItem(STORAGE_KEYS.accessToken, data.access_token);
        return data.access_token;
    }

    public async getCurrentUser(): Promise<{
        user: AuthUserInfo;
        productKeyInfo: ProductKeyInfo | null;
    }> {
        const accessToken = this.getAccessToken();
        if (!accessToken) {
            throw new Error('未登录');
        }

        const data = await this.request<{
            id: number;
            username: string;
            email: string;
            role: string;
            product_key_id: number | null;
            product_key?: string | null;
            key_status?: string;
            product_key_info?: ProductKeyInfo | null;
        }>('/auth/me', {
            method: 'GET',
            headers: {
                Authorization: `Bearer ${accessToken}`,
            },
        });

        const user: AuthUserInfo = {
            id: data.id,
            user_id: data.id,
            username: data.username,
            email: data.email,
            role: data.role,
            product_key_id: data.product_key_id,
            product_key: data.product_key || null,
            key_status: data.key_status || 'unused',
        };
        const productKeyInfo = data.product_key_info || null;
        this.persistAuthSession(accessToken, this.getRefreshToken(), user, productKeyInfo);
        return { user, productKeyInfo };
    }

    public checkTokenExpired(token?: string | null): boolean {
        const target = token || this.getAccessToken();
        if (!target) {
            return true;
        }
        const payload = decodeJwtPayload(target);
        const exp = Number(payload?.exp || 0);
        if (!exp) {
            return true;
        }
        const now = Math.floor(Date.now() / 1000);
        return exp <= now + 15;
    }

    public persistProductKeyInfo(productKeyInfo: ProductKeyInfo | null): void {
        if (!productKeyInfo) {
            localStorage.removeItem(STORAGE_KEYS.productKeyInfo);
            return;
        }
        localStorage.setItem(STORAGE_KEYS.productKeyInfo, JSON.stringify(productKeyInfo));
    }

    public persistAuthSession(
        accessToken: string | null,
        refreshToken: string | null,
        userInfo: AuthUserInfo | null,
        productKeyInfo: ProductKeyInfo | null
    ): void {
        if (accessToken) {
            localStorage.setItem(STORAGE_KEYS.accessToken, accessToken);
        } else {
            localStorage.removeItem(STORAGE_KEYS.accessToken);
        }
        if (refreshToken) {
            localStorage.setItem(STORAGE_KEYS.refreshToken, refreshToken);
        } else {
            localStorage.removeItem(STORAGE_KEYS.refreshToken);
        }
        if (userInfo) {
            localStorage.setItem(STORAGE_KEYS.userInfo, JSON.stringify(userInfo));
        } else {
            localStorage.removeItem(STORAGE_KEYS.userInfo);
        }
        this.persistProductKeyInfo(productKeyInfo);
    }

    public clearSession(): void {
        localStorage.removeItem(STORAGE_KEYS.accessToken);
        localStorage.removeItem(STORAGE_KEYS.refreshToken);
        localStorage.removeItem(STORAGE_KEYS.userInfo);
        localStorage.removeItem(STORAGE_KEYS.productKeyInfo);
    }

    private async request<T = unknown>(path: string, init: RequestInit): Promise<T> {
        const response = await fetch(`${this.apiBaseUrl}${path}`, {
            ...init,
            credentials: 'omit',
        });
        const payload = (await response.json().catch(() => ({}))) as ApiEnvelope<T>;
        if (!response.ok) {
            const message =
                (typeof payload.detail === 'string' ? payload.detail : payload.detail?.message) ||
                payload.message ||
                `请求失败(${response.status})`;
            throw new Error(message);
        }
        return (payload.data as T) || ({} as T);
    }
}

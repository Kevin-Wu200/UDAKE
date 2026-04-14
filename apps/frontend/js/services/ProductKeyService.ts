import type { ProductKeyInfo } from './AuthService.js';
import { AuthService } from './AuthService.js';
import { resolveRuntimeApiBaseUrl } from './api/runtime.js';

interface KeyStatusResponse {
    key_info: ProductKeyInfo | null;
    attempts: number;
    remaining_attempts: number;
    locked_until: number | null;
    lock_remaining_seconds: number;
}

interface ApiEnvelope<T> {
    success?: boolean;
    message?: string;
    data?: T;
    detail?: string | { message?: string };
}

const STORAGE_KEYS = {
    activationAttempts: 'activation_attempts',
    lockedUntil: 'locked_until',
};

export class ProductKeyService {
    private readonly authService: AuthService;
    private readonly apiBaseUrl: string;

    constructor(authService: AuthService, apiBaseUrl?: string) {
        this.authService = authService;
        this.apiBaseUrl = (apiBaseUrl || resolveRuntimeApiBaseUrl()).replace(/\/+$/, '');
    }

    public async activateKey(productKey: string): Promise<ProductKeyInfo> {
        const accessToken = this.authService.getAccessToken();
        const user = this.authService.getStoredUserInfo();
        if (!accessToken || !user?.user_id) {
            throw new Error('请先登录');
        }

        const data = await this.request<ProductKeyInfo>('/product-keys/activate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                Authorization: `Bearer ${accessToken}`,
            },
            body: JSON.stringify({
                product_key: productKey.trim().toUpperCase(),
                user_id: user.user_id,
            }),
        });

        this.authService.persistProductKeyInfo(data);
        this.setActivationAttempts(0);
        this.setLockedUntil(null);
        return data;
    }

    public async getKeyStatus(): Promise<KeyStatusResponse> {
        const accessToken = this.authService.getAccessToken();
        if (!accessToken) {
            return {
                key_info: this.authService.getStoredProductKeyInfo(),
                attempts: this.getActivationAttempts(),
                remaining_attempts: Math.max(0, 5 - this.getActivationAttempts()),
                locked_until: this.getLockedUntil(),
                lock_remaining_seconds: this.getLockRemainingSeconds(),
            };
        }

        const data = await this.request<KeyStatusResponse>('/product-keys/status', {
            method: 'GET',
            headers: {
                Authorization: `Bearer ${accessToken}`,
            },
        });

        this.setActivationAttempts(data.attempts || 0);
        this.setLockedUntil(data.locked_until);
        if (data.key_info) {
            this.authService.persistProductKeyInfo(data.key_info);
        }
        return data;
    }

    public checkActivationAttempts(): {
        attempts: number;
        remainingAttempts: number;
        lockedUntil: number | null;
        lockRemainingSeconds: number;
        isLocked: boolean;
    } {
        const attempts = this.getActivationAttempts();
        const lockedUntil = this.getLockedUntil();
        const lockRemainingSeconds = this.getLockRemainingSeconds();
        return {
            attempts,
            remainingAttempts: Math.max(0, 5 - attempts),
            lockedUntil,
            lockRemainingSeconds,
            isLocked: lockRemainingSeconds > 0,
        };
    }

    public increaseLocalFailedAttempts(): void {
        const next = this.getActivationAttempts() + 1;
        this.setActivationAttempts(next);
        if (next >= 5) {
            const lockedUntil = Date.now() + 30 * 60 * 1000;
            this.setLockedUntil(lockedUntil);
        }
    }

    public getActivationAttempts(): number {
        return Number(localStorage.getItem(STORAGE_KEYS.activationAttempts) || '0');
    }

    public setActivationAttempts(count: number): void {
        localStorage.setItem(STORAGE_KEYS.activationAttempts, String(Math.max(0, count)));
    }

    public getLockedUntil(): number | null {
        const raw = localStorage.getItem(STORAGE_KEYS.lockedUntil);
        if (!raw) {
            return null;
        }
        const value = Number(raw);
        return Number.isFinite(value) ? value : null;
    }

    public setLockedUntil(timestamp: number | null): void {
        if (!timestamp) {
            localStorage.removeItem(STORAGE_KEYS.lockedUntil);
            return;
        }
        localStorage.setItem(STORAGE_KEYS.lockedUntil, String(timestamp));
    }

    public getLockRemainingSeconds(): number {
        const lockedUntil = this.getLockedUntil();
        if (!lockedUntil) {
            return 0;
        }
        const deltaMs = lockedUntil > 10_000_000_000 ? lockedUntil - Date.now() : lockedUntil * 1000 - Date.now();
        return Math.max(0, Math.ceil(deltaMs / 1000));
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

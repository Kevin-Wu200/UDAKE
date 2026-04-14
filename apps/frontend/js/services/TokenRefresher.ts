import { AuthService } from './AuthService.js';

export class TokenRefresher {
    private readonly authService: AuthService;
    private refreshPromise: Promise<string> | null;

    constructor(authService: AuthService) {
        this.authService = authService;
        this.refreshPromise = null;
    }

    public startStorageSync(onSessionInvalid?: () => void): void {
        window.addEventListener('storage', (event: StorageEvent) => {
            if (!event.key) {
                return;
            }
            if (event.key === 'access_token' && !event.newValue) {
                onSessionInvalid?.();
            }
        });
    }

    public async ensureValidAccessToken(): Promise<string> {
        const current = this.authService.getAccessToken();
        if (!current) {
            throw new Error('未登录');
        }
        if (!this.authService.checkTokenExpired(current)) {
            return current;
        }

        if (!this.refreshPromise) {
            this.refreshPromise = this.authService
                .refreshToken()
                .finally(() => {
                    this.refreshPromise = null;
                });
        }

        try {
            return await this.refreshPromise;
        } catch {
            this.authService.clearSession();
            throw new Error('登录已过期，请重新登录');
        }
    }

    public async fetchWithAuth(url: string, init: RequestInit = {}): Promise<Response> {
        const token = await this.ensureValidAccessToken();
        const headers = new Headers(init.headers || {});
        headers.set('Authorization', `Bearer ${token}`);
        return fetch(url, {
            ...init,
            headers,
        });
    }
}

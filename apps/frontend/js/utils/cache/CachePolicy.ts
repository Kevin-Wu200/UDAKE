/**
 * 缓存策略与键命名规范
 */

export interface CacheKeyInput {
    namespace: string;
    method: string;
    url: string;
    body?: unknown;
    version?: string;
}

const API_CACHE_TTL: Array<{ matcher: RegExp; ttl: number }> = [
    { matcher: /\/config\//, ttl: 10 * 60 * 1000 },
    { matcher: /\/data\/list/, ttl: 60 * 1000 },
    { matcher: /\/result\//, ttl: 5 * 60 * 1000 },
    { matcher: /\/task-status\//, ttl: 30 * 1000 }
];

function hashString(value: string): string {
    let hash = 2166136261;
    for (let i = 0; i < value.length; i++) {
        hash ^= value.charCodeAt(i);
        hash += (hash << 1) + (hash << 4) + (hash << 7) + (hash << 8) + (hash << 24);
    }
    return Math.abs(hash >>> 0).toString(36);
}

function normalizeUrl(url: string): string {
    try {
        const parsed = new URL(url, 'http://local.base');
        return `${parsed.pathname}${parsed.search}`;
    } catch {
        return url;
    }
}

export function buildCacheKey(input: CacheKeyInput): string {
    const method = (input.method || 'GET').toUpperCase();
    const normalizedUrl = normalizeUrl(input.url);
    const payload = input.body === undefined ? '' : JSON.stringify(input.body);
    const hash = hashString(`${method}|${normalizedUrl}|${payload}`);
    const version = input.version ? `:${input.version}` : '';
    return `${input.namespace}${version}:${method}:${hash}`;
}

export function shouldUseApiCache(method: string, url: string): boolean {
    if (method.toUpperCase() !== 'GET') {
        return false;
    }

    return API_CACHE_TTL.some(item => item.matcher.test(url));
}

export function getApiCacheTTL(url: string, fallback: number = 5 * 60 * 1000): number {
    const matched = API_CACHE_TTL.find(item => item.matcher.test(url));
    return matched?.ttl ?? fallback;
}

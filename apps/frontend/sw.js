/**
 * Service Worker - 增强版缓存策略
 * Cache First for CSS/JS, Network First for API (带缓存回退)
 * 支持离线模式和后台同步
 */

const CACHE_NAME = 'udake-v2';
const API_CACHE = 'udake-api-v1';
const STATIC_ASSETS = [
    '/',
    '/index.html',
    '/css/theme-variables.css',
    '/css/layout-styles.css',
    '/css/component-styles.css',
    '/css/animation-styles.css',
    '/css/dark-mode.css',
    '/css/safari-compat.css',
    '/js/主程序.ts',
];

// 可缓存的 GET API 路径（只读查询）
const CACHEABLE_API = [
    '/api/task-status/',
    '/api/result/',
    '/api/recommendations/',
];

// 安装：预缓存静态资源
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
    );
    self.skipWaiting();
});

// 激活：清理旧缓存
self.addEventListener('activate', (event) => {
    const keep = new Set([CACHE_NAME, API_CACHE]);
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.filter((k) => !keep.has(k)).map((k) => caches.delete(k)))
        )
    );
    self.clients.claim();
});

// 请求拦截
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // API 请求：Network First + 缓存回退
    if (url.pathname.startsWith('/api/')) {
        const isCacheable = event.request.method === 'GET' &&
            CACHEABLE_API.some((p) => url.pathname.startsWith(p));

        event.respondWith(
            fetch(event.request)
                .then((response) => {
                    // 成功响应时缓存可缓存的 GET 请求
                    if (response.ok && isCacheable) {
                        const clone = response.clone();
                        caches.open(API_CACHE).then((cache) => cache.put(event.request, clone));
                    }
                    return response;
                })
                .catch(() => {
                    // 离线时尝试从缓存返回
                    if (isCacheable) {
                        return caches.match(event.request).then((cached) => {
                            if (cached) return cached;
                            return new Response(
                                JSON.stringify({ error: '离线模式：无缓存数据' }),
                                { status: 503, headers: { 'Content-Type': 'application/json' } }
                            );
                        });
                    }
                    // POST 等写操作离线时返回特殊状态码
                    return new Response(
                        JSON.stringify({ error: '离线模式：操作已加入队列', offline: true }),
                        { status: 503, headers: { 'Content-Type': 'application/json' } }
                    );
                })
        );
        return;
    }

    // 静态资源：Cache First
    if (event.request.method === 'GET') {
        event.respondWith(
            caches.match(event.request).then((cached) => {
                if (cached) return cached;
                return fetch(event.request).then((response) => {
                    if (response.ok && url.origin === self.location.origin) {
                        const clone = response.clone();
                        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
                    }
                    return response;
                });
            })
        );
    }
});

// 后台同步支持
self.addEventListener('sync', (event) => {
    if (event.tag === 'udake-sync') {
        event.waitUntil(
            self.clients.matchAll().then((clients) => {
                clients.forEach((client) => client.postMessage({ type: 'SYNC_REQUESTED' }));
            })
        );
    }
});

// 接收来自主线程的消息
self.addEventListener('message', (event) => {
    if (event.data?.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});

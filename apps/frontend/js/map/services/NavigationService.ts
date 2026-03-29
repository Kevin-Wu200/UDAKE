/**
 * 导航服务
 * 统一封装在线（高德）与离线路由能力。
 */

import type { RouteType } from '../../../types/map-engine';

export type NavigationMode = RouteType | 'cycling';

export interface NavigationStep {
    instruction: string;
    distanceMeters: number;
    durationSeconds: number;
    icon: 'straight' | 'left' | 'right' | 'arrive';
}

export interface NavigationRoute {
    mode: NavigationMode;
    start: [number, number];
    end: [number, number];
    polyline: Array<[number, number]>;
    steps: NavigationStep[];
    distanceMeters: number;
    durationSeconds: number;
    offline: boolean;
    generatedAt: number;
    source: 'amap' | 'offline-engine';
}

export interface NavigationPlanOptions {
    city?: string;
    forceOffline?: boolean;
    disableCache?: boolean;
    lowPowerMode?: boolean;
    enableVoice?: boolean;
}

export interface DeviationCheckResult {
    deviated: boolean;
    distanceMeters: number;
    route?: NavigationRoute;
}

interface CachedRoute {
    route: NavigationRoute;
    expiresAt: number;
}

const CACHE_TTL_MS = 30 * 60 * 1000;
const DEFAULT_REPLAN_COOLDOWN_MS = 15_000;
const DEFAULT_DEVIATION_THRESHOLD_METERS = 40;
const EARTH_RADIUS_METERS = 6_371_000;

const MODE_SPEED_MPS: Record<NavigationMode, number> = {
    driving: 13.9,
    walking: 1.4,
    transfer: 6.0,
    cycling: 4.5
};

function nowTs(): number {
    return Date.now();
}

function toRadians(value: number): number {
    return (value * Math.PI) / 180;
}

function haversineDistance(start: [number, number], end: [number, number]): number {
    const lon1 = toRadians(start[0]);
    const lat1 = toRadians(start[1]);
    const lon2 = toRadians(end[0]);
    const lat2 = toRadians(end[1]);
    const dLon = lon2 - lon1;
    const dLat = lat2 - lat1;
    const a = Math.sin(dLat / 2) ** 2
        + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return EARTH_RADIUS_METERS * c;
}

function interpolate(start: [number, number], end: [number, number], ratio: number): [number, number] {
    return [
        start[0] + (end[0] - start[0]) * ratio,
        start[1] + (end[1] - start[1]) * ratio
    ];
}

function isNavigatorOnline(): boolean {
    if (typeof navigator === 'undefined') {
        return true;
    }
    return navigator.onLine;
}

function normalizeMode(mode: NavigationMode): NavigationMode {
    if (mode === 'transfer') {
        return 'walking';
    }
    return mode;
}

function routeCacheKey(mode: NavigationMode, start: [number, number], end: [number, number], lowPowerMode: boolean): string {
    const rounded = [
        ...start.map((value) => value.toFixed(5)),
        ...end.map((value) => value.toFixed(5))
    ].join(':');
    return `${mode}:${rounded}:lp=${lowPowerMode ? 1 : 0}`;
}

/**
 * 导航服务
 * 封装高德地图导航功能，并提供离线回退。
 */
export class NavigationService {
    /** 地图实例 */
    map: any;

    /** 驾车导航实例 */
    driving: any;

    /** 步行导航实例 */
    walking: any;

    /** 公交换乘实例 */
    transfer: any;

    private routeCache: Map<string, CachedRoute>;
    private currentRoute: NavigationRoute | null;
    private voiceGuidanceEnabled: boolean;
    private lowPowerModeEnabled: boolean;
    private deviationThresholdMeters: number;
    private replanCooldownMs: number;
    private lastReplanAt: number;
    private rerouteListeners: Set<(route: NavigationRoute) => void>;
    private hintListeners: Set<(step: NavigationStep) => void>;

    constructor(map: any) {
        this.map = map;
        this.driving = null;
        this.walking = null;
        this.transfer = null;

        this.routeCache = new Map();
        this.currentRoute = null;
        this.voiceGuidanceEnabled = true;
        this.lowPowerModeEnabled = false;
        this.deviationThresholdMeters = DEFAULT_DEVIATION_THRESHOLD_METERS;
        this.replanCooldownMs = DEFAULT_REPLAN_COOLDOWN_MS;
        this.lastReplanAt = 0;
        this.rerouteListeners = new Set();
        this.hintListeners = new Set();
    }

    /**
     * 规划路线（优先在线，高德不可用时自动离线回退）。
     */
    async planRoute(
        type: NavigationMode,
        start: [number, number],
        end: [number, number],
        options: NavigationPlanOptions = {}
    ): Promise<NavigationRoute> {
        const mode = type;
        const lowPowerMode = Boolean(options.lowPowerMode ?? this.lowPowerModeEnabled);
        const cacheKey = routeCacheKey(mode, start, end, lowPowerMode);

        if (!options.disableCache) {
            const cached = this.routeCache.get(cacheKey);
            if (cached && cached.expiresAt > nowTs()) {
                this.currentRoute = cached.route;
                return cached.route;
            }
        }

        const canUseOnline = !options.forceOffline && isNavigatorOnline();
        if (canUseOnline) {
            try {
                const onlineRoute = await this.planRouteOnline(mode, start, end, options.city);
                this.currentRoute = onlineRoute;
                this.cacheRoute(cacheKey, onlineRoute);
                this.emitPreviewHint(onlineRoute, options.enableVoice);
                return onlineRoute;
            } catch {
                // 在线规划失败时降级到离线引擎
            }
        }

        const offlineRoute = this.planRouteOffline(mode, start, end, lowPowerMode);
        this.currentRoute = offlineRoute;
        this.cacheRoute(cacheKey, offlineRoute);
        this.emitPreviewHint(offlineRoute, options.enableVoice);
        return offlineRoute;
    }

    /**
     * 提前预热常用路线缓存。
     */
    predictivePreloadRoute(type: NavigationMode, start: [number, number], end: [number, number], lowPowerMode = false): NavigationRoute {
        const mode = normalizeMode(type);
        const route = this.planRouteOffline(mode, start, end, lowPowerMode);
        const key = routeCacheKey(type, start, end, lowPowerMode);
        this.cacheRoute(key, route);
        return route;
    }

    /**
     * 偏航检测与自动重规划。
     */
    async checkDeviationAndReplan(current: [number, number]): Promise<DeviationCheckResult> {
        const route = this.currentRoute;
        if (!route || route.polyline.length < 2) {
            return { deviated: false, distanceMeters: 0 };
        }

        const minDistance = this.distanceToRoute(current, route.polyline);
        if (minDistance <= this.deviationThresholdMeters) {
            return { deviated: false, distanceMeters: minDistance };
        }

        const now = nowTs();
        if (now - this.lastReplanAt < this.replanCooldownMs) {
            return { deviated: true, distanceMeters: minDistance };
        }

        this.lastReplanAt = now;
        const replanned = await this.planRoute(route.mode, current, route.end, {
            forceOffline: route.offline,
            lowPowerMode: this.lowPowerModeEnabled,
            enableVoice: this.voiceGuidanceEnabled
        });

        this.rerouteListeners.forEach((listener) => {
            listener(replanned);
        });

        return {
            deviated: true,
            distanceMeters: minDistance,
            route: replanned
        };
    }

    onReroute(listener: (route: NavigationRoute) => void): () => void {
        this.rerouteListeners.add(listener);
        return () => {
            this.rerouteListeners.delete(listener);
        };
    }

    onHint(listener: (step: NavigationStep) => void): () => void {
        this.hintListeners.add(listener);
        return () => {
            this.hintListeners.delete(listener);
        };
    }

    setVoiceGuidanceEnabled(enabled: boolean): void {
        this.voiceGuidanceEnabled = Boolean(enabled);
    }

    setLowPowerModeEnabled(enabled: boolean): void {
        this.lowPowerModeEnabled = Boolean(enabled);
    }

    setDeviationThresholdMeters(thresholdMeters: number): void {
        this.deviationThresholdMeters = Math.max(10, Math.floor(thresholdMeters));
    }

    getCurrentRoute(): NavigationRoute | null {
        return this.currentRoute;
    }

    protected async planRouteOnline(
        type: NavigationMode,
        start: [number, number],
        end: [number, number],
        city?: string
    ): Promise<NavigationRoute> {
        const normalizedType: RouteType = type === 'cycling' ? 'walking' : type;
        const result = await new Promise<any>((resolve, reject) => {
            switch (normalizedType) {
                case 'driving':
                    this.planDriving(start, end, resolve, reject);
                    break;
                case 'walking':
                    this.planWalking(start, end, resolve, reject);
                    break;
                case 'transfer':
                    this.planTransfer(start, end, resolve, reject, city);
                    break;
                default:
                    reject(new Error(`不支持的路线类型: ${normalizedType}`));
            }
        });

        return this.normalizeAmapRoute(type, start, end, result);
    }

    /**
     * 驾车导航
     */
    protected planDriving(
        start: [number, number],
        end: [number, number],
        resolve: (value: any) => void,
        reject: (reason?: any) => void
    ): void {
        this.map.plugin(['AMap.Driving'], () => {
            const AMap = (window as any).AMap;
            this.driving = new AMap.Driving({
                map: this.map,
                panel: null
            });

            this.driving.search(start, end, (status: string, result: any) => {
                if (status === 'complete') {
                    resolve(result);
                } else {
                    reject(new Error('驾车路线规划失败'));
                }
            });
        });
    }

    /**
     * 步行导航
     */
    protected planWalking(
        start: [number, number],
        end: [number, number],
        resolve: (value: any) => void,
        reject: (reason?: any) => void
    ): void {
        this.map.plugin(['AMap.Walking'], () => {
            const AMap = (window as any).AMap;
            this.walking = new AMap.Walking({
                map: this.map
            });

            this.walking.search(start, end, (status: string, result: any) => {
                if (status === 'complete') {
                    resolve(result);
                } else {
                    reject(new Error('步行路线规划失败'));
                }
            });
        });
    }

    /**
     * 公交换乘
     */
    protected planTransfer(
        start: [number, number],
        end: [number, number],
        resolve: (value: any) => void,
        reject: (reason?: any) => void,
        city?: string
    ): void {
        this.map.plugin(['AMap.Transfer'], () => {
            const AMap = (window as any).AMap;
            this.transfer = new AMap.Transfer({
                map: this.map,
                city: city || '北京'
            });

            this.transfer.search(start, end, (status: string, result: any) => {
                if (status === 'complete') {
                    resolve(result);
                } else {
                    reject(new Error('公交路线规划失败'));
                }
            });
        });
    }

    private planRouteOffline(
        type: NavigationMode,
        start: [number, number],
        end: [number, number],
        lowPowerMode: boolean
    ): NavigationRoute {
        const mode = normalizeMode(type);
        const waypointCount = lowPowerMode ? 1 : 3;
        const polyline: Array<[number, number]> = [start];

        for (let i = 1; i <= waypointCount; i += 1) {
            const ratio = i / (waypointCount + 1);
            const point = interpolate(start, end, ratio);
            polyline.push(point);
        }
        polyline.push(end);

        let distanceMeters = 0;
        for (let i = 1; i < polyline.length; i += 1) {
            distanceMeters += haversineDistance(polyline[i - 1], polyline[i]);
        }

        const speed = MODE_SPEED_MPS[mode] || MODE_SPEED_MPS.walking;
        const durationSeconds = Math.max(1, Math.round(distanceMeters / speed));
        const steps = this.createTurnByTurnSteps(polyline, durationSeconds);

        return {
            mode: type,
            start,
            end,
            polyline,
            steps,
            distanceMeters,
            durationSeconds,
            offline: true,
            generatedAt: nowTs(),
            source: 'offline-engine'
        };
    }

    private normalizeAmapRoute(
        type: NavigationMode,
        start: [number, number],
        end: [number, number],
        result: any
    ): NavigationRoute {
        const rawPath = result?.routes?.[0]?.steps
            ?.flatMap((step: any) => step?.path || []);

        const polyline: Array<[number, number]> = Array.isArray(rawPath) && rawPath.length > 1
            ? rawPath
                .map((item: any) => {
                    if (Array.isArray(item) && item.length >= 2) {
                        return [Number(item[0]), Number(item[1])] as [number, number];
                    }
                    if (item && typeof item === 'object' && 'lng' in item && 'lat' in item) {
                        return [Number(item.lng), Number(item.lat)] as [number, number];
                    }
                    return null;
                })
                .filter(Boolean) as Array<[number, number]>
            : [start, end];

        if (polyline.length < 2) {
            polyline.splice(0, polyline.length, start, end);
        }

        const distanceMeters = Number(result?.routes?.[0]?.distance)
            || this.computePolylineDistance(polyline);
        const durationSeconds = Number(result?.routes?.[0]?.time)
            || Math.max(1, Math.round(distanceMeters / (MODE_SPEED_MPS[normalizeMode(type)] || MODE_SPEED_MPS.walking)));

        const steps = this.createTurnByTurnSteps(polyline, durationSeconds);

        return {
            mode: type,
            start,
            end,
            polyline,
            steps,
            distanceMeters,
            durationSeconds,
            offline: false,
            generatedAt: nowTs(),
            source: 'amap'
        };
    }

    private createTurnByTurnSteps(polyline: Array<[number, number]>, durationSeconds: number): NavigationStep[] {
        if (polyline.length < 2) {
            return [];
        }
        const steps: NavigationStep[] = [];
        const totalDistance = this.computePolylineDistance(polyline);

        for (let i = 1; i < polyline.length; i += 1) {
            const from = polyline[i - 1];
            const to = polyline[i];
            const segmentDistance = haversineDistance(from, to);
            const ratio = totalDistance > 0 ? segmentDistance / totalDistance : 0;
            const segmentDuration = Math.max(1, Math.round(durationSeconds * ratio));

            let icon: NavigationStep['icon'] = 'straight';
            if (i === polyline.length - 1) {
                icon = 'arrive';
            } else if (i > 1) {
                const prev = polyline[i - 2];
                const turn = this.calculateTurn(prev, from, to);
                if (turn < -8) {
                    icon = 'left';
                } else if (turn > 8) {
                    icon = 'right';
                }
            }

            steps.push({
                instruction: this.buildInstruction(icon, segmentDistance),
                distanceMeters: segmentDistance,
                durationSeconds: segmentDuration,
                icon
            });
        }

        return steps;
    }

    private buildInstruction(icon: NavigationStep['icon'], distanceMeters: number): string {
        const distanceText = distanceMeters >= 1000
            ? `${(distanceMeters / 1000).toFixed(1)} 公里`
            : `${Math.round(distanceMeters)} 米`;

        if (icon === 'left') {
            return `前方左转，继续 ${distanceText}`;
        }
        if (icon === 'right') {
            return `前方右转，继续 ${distanceText}`;
        }
        if (icon === 'arrive') {
            return '即将到达目的地';
        }
        return `直行 ${distanceText}`;
    }

    private calculateTurn(a: [number, number], b: [number, number], c: [number, number]): number {
        const abx = b[0] - a[0];
        const aby = b[1] - a[1];
        const bcx = c[0] - b[0];
        const bcy = c[1] - b[1];
        const cross = abx * bcy - aby * bcx;
        const dot = abx * bcx + aby * bcy;
        return (Math.atan2(cross, dot) * 180) / Math.PI;
    }

    private computePolylineDistance(polyline: Array<[number, number]>): number {
        let distance = 0;
        for (let i = 1; i < polyline.length; i += 1) {
            distance += haversineDistance(polyline[i - 1], polyline[i]);
        }
        return distance;
    }

    private distanceToRoute(point: [number, number], polyline: Array<[number, number]>): number {
        if (polyline.length < 2) {
            return 0;
        }

        let minDistance = Number.POSITIVE_INFINITY;
        for (let i = 1; i < polyline.length; i += 1) {
            const segmentDistance = this.distanceToSegment(point, polyline[i - 1], polyline[i]);
            minDistance = Math.min(minDistance, segmentDistance);
        }
        return Number.isFinite(minDistance) ? minDistance : 0;
    }

    private distanceToSegment(point: [number, number], start: [number, number], end: [number, number]): number {
        const x = point[0];
        const y = point[1];
        const x1 = start[0];
        const y1 = start[1];
        const x2 = end[0];
        const y2 = end[1];

        const dx = x2 - x1;
        const dy = y2 - y1;
        if (dx === 0 && dy === 0) {
            return haversineDistance(point, start);
        }

        const t = Math.max(0, Math.min(1, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)));
        const projection: [number, number] = [x1 + t * dx, y1 + t * dy];
        return haversineDistance(point, projection);
    }

    private cacheRoute(key: string, route: NavigationRoute): void {
        this.routeCache.set(key, {
            route,
            expiresAt: nowTs() + CACHE_TTL_MS
        });

        if (this.routeCache.size > 200) {
            const expired = nowTs();
            this.routeCache.forEach((item, cacheKey) => {
                if (item.expiresAt <= expired) {
                    this.routeCache.delete(cacheKey);
                }
            });
        }
    }

    private emitPreviewHint(route: NavigationRoute, enableVoice?: boolean): void {
        const firstStep = route.steps[0];
        if (!firstStep) {
            return;
        }

        this.hintListeners.forEach((listener) => {
            listener(firstStep);
        });

        const shouldSpeak = enableVoice ?? this.voiceGuidanceEnabled;
        if (shouldSpeak) {
            this.speak(firstStep.instruction);
        }
    }

    private speak(text: string): void {
        if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
            return;
        }
        try {
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.lang = 'zh-CN';
            window.speechSynthesis.cancel();
            window.speechSynthesis.speak(utterance);
        } catch {
            // 忽略语音引擎不可用错误
        }
    }

    /**
     * 清除路线
     */
    clearRoute(): void {
        if (this.driving) {
            this.driving.clear();
        }
        if (this.walking) {
            this.walking.clear();
        }
        if (this.transfer) {
            this.transfer.clear();
        }
        this.currentRoute = null;
    }

    /**
     * 销毁服务
     */
    destroy(): void {
        this.clearRoute();
        this.driving = null;
        this.walking = null;
        this.transfer = null;
        this.routeCache.clear();
        this.rerouteListeners.clear();
        this.hintListeners.clear();
    }
}

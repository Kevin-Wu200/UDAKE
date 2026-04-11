import type { IMapAdapter } from '../../types/map';

export type MapProvider = string;

type AdapterFactory = () => Promise<IMapAdapter>;

type ManifestModule = {
    default?: {
        id?: string;
        name?: string;
        provider?: string;
        description?: string;
    };
};

export interface MapEngineDescriptor {
    provider: MapProvider;
    displayName: string;
    source: 'builtin' | 'plugin';
    pluginId?: string;
    manifestPath?: string;
    createAdapter: AdapterFactory;
}

const DEFAULT_PROVIDER = 'geoscene';

const builtinFactories: Record<string, AdapterFactory> = {
    geoscene: async () => {
        const mod = await import('../adapters/GeoSceneAdapter.js');
        return new mod.GeoSceneAdapter();
    },
    amap: async () => {
        const mod = await import('../adapters/AMapAdapter.js');
        return new mod.AMapAdapter();
    }
};

const registry = new Map<string, MapEngineDescriptor>();
let initialized = false;
let initPromise: Promise<void> | null = null;

const manifestLoaders = import.meta.glob('../../../../plugins/map-engines/*/manifest.json');

function normalizeProvider(provider: string): string {
    return provider.trim().toLowerCase();
}

function inferProviderFromManifestPath(path: string): string {
    const matched = path.match(/map-engines\/([^/]+)\/manifest\.json$/i);
    return normalizeProvider(matched?.[1] || '');
}

function registerBuiltinEngines(): void {
    registerMapEngine({
        provider: 'geoscene',
        displayName: 'GeoScene',
        source: 'builtin',
        createAdapter: builtinFactories.geoscene
    });

    registerMapEngine({
        provider: 'amap',
        displayName: '高德',
        source: 'builtin',
        createAdapter: builtinFactories.amap
    });
}

async function discoverPluginEngines(): Promise<void> {
    const entries = Object.entries(manifestLoaders);

    for (const [manifestPath, loader] of entries) {
        try {
            const loaded = (await loader()) as ManifestModule;
            const manifest = loaded.default || {};
            const provider = normalizeProvider(
                manifest.provider || inferProviderFromManifestPath(manifestPath) || manifest.id || ''
            );

            if (!provider) {
                continue;
            }

            const factory = builtinFactories[provider];
            if (!factory) {
                console.warn(`[MapEngineRegistry] 引擎 ${provider} 尚未提供适配器工厂，跳过注册`);
                continue;
            }

            registerMapEngine({
                provider,
                displayName: manifest.name || provider,
                source: 'plugin',
                pluginId: manifest.id,
                manifestPath,
                createAdapter: factory
            });
        } catch (error) {
            console.warn(`[MapEngineRegistry] 读取插件清单失败: ${manifestPath}`, error);
        }
    }
}

export function registerMapEngine(descriptor: MapEngineDescriptor): void {
    const provider = normalizeProvider(descriptor.provider);
    if (!provider) {
        throw new Error('地图引擎 provider 不能为空');
    }

    registry.set(provider, {
        ...descriptor,
        provider,
        displayName: descriptor.displayName || provider
    });
}

export async function ensureMapEngineRegistryReady(): Promise<void> {
    if (initialized) {
        return;
    }

    if (!initPromise) {
        initPromise = (async () => {
            registerBuiltinEngines();
            await discoverPluginEngines();
            initialized = true;
        })();
    }

    await initPromise;
}

export function getMapEngine(provider: MapProvider): MapEngineDescriptor | undefined {
    return registry.get(normalizeProvider(provider));
}

export function getRegisteredMapEngines(): MapEngineDescriptor[] {
    return Array.from(registry.values());
}

export function getMapEngineDisplayName(provider: MapProvider): string {
    return getMapEngine(provider)?.displayName || provider;
}

export function validateMapProvider(provider: string, fallback: string = DEFAULT_PROVIDER): MapProvider {
    const normalized = normalizeProvider(provider);
    if (normalized && registry.has(normalized)) {
        return normalized;
    }

    return normalizeProvider(fallback);
}

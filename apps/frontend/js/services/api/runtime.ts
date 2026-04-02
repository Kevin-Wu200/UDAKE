import type { RuntimeWindowWithConfig } from './types';

function safeReadEnv(key: string): string | undefined {
  try {
    const env = (import.meta as ImportMeta & { env?: Record<string, string> }).env;
    return env?.[key];
  } catch {
    return undefined;
  }
}

function stripApiSuffix(baseUrl: string): string {
  const trimmed = baseUrl.trim().replace(/\/+$/, '');
  return trimmed.endsWith('/api') ? trimmed.slice(0, -4) : trimmed;
}

function normalizeApiBaseUrl(baseUrl: string): string {
  const normalized = stripApiSuffix(baseUrl);
  if (!normalized) {
    return '/api';
  }
  return `${normalized}/api`;
}

export function resolveRuntimeApiBaseUrl(): string {
  const win = (typeof window !== 'undefined' ? window : undefined) as RuntimeWindowWithConfig | undefined;
  const runtimeGlobal = win?.__UDAKE_API_BASE__;

  let runtimeStorage: string | undefined;
  if (typeof window !== 'undefined') {
    try {
      runtimeStorage = localStorage.getItem('UDAKE_API_BASE_URL') || undefined;
    } catch {
      runtimeStorage = undefined;
    }
  }

  const capacitorApiBase = win?.Capacitor?.config?.plugins?.UDAKEConfig?.apiBaseUrl;
  const capacitorServerUrl = win?.Capacitor?.config?.server?.url;
  const envApiBase = safeReadEnv('VITE_API_BASE_URL') || safeReadEnv('VITE_API_URL');
  const envHost = safeReadEnv('VITE_BACKEND_HOST') || safeReadEnv('VITE_IPCONFIG');
  const envPort = safeReadEnv('VITE_BACKEND_PORT') || '8000';
  const fallbackBase = `http://${envHost || 'localhost'}:${envPort}`;

  const rawBase = runtimeGlobal || runtimeStorage || capacitorApiBase || capacitorServerUrl || envApiBase || fallbackBase;
  return normalizeApiBaseUrl(rawBase);
}

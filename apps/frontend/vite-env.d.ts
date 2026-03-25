/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_APP_ENV: string;
  readonly VITE_APP_NAME: string;
  readonly VITE_APP_VERSION: string;
  readonly VITE_API_BASE_URL: string;
  readonly VITE_API_URL: string;
  readonly VITE_WS_URL: string;
  readonly VITE_IPCONFIG: string;
  readonly VITE_BACKEND_HOST: string;
  readonly VITE_BACKEND_PORT: string;
  readonly VITE_FRONTEND_PORT: string;
  readonly VITE_FRONTEND_URL: string;
  readonly VITE_CORS_ORIGINS: string;
  readonly VITE_MAP_PROVIDER: string;
  readonly VITE_ENABLE_DEBUG: string;
  readonly VITE_ENABLE_PERFORMANCE_MONITOR: string;
  readonly VITE_LOG_LEVEL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

import { defineConfig, loadEnv } from 'vite';
import { resolve } from 'path';

export default defineConfig(({ mode }) => {
  const envDir = resolve(__dirname, 'env');
  // 加载环境变量
  const env = loadEnv(mode, envDir, '');

  const backendHost = env.IPCONFIG || env.VITE_IPCONFIG || env.VITE_BACKEND_HOST || 'localhost';
  const backendPort = env.BACKEND_PORT || env.VITE_BACKEND_PORT || '8000';
  const defaultFrontendPort = mode === 'testing' ? '5174' : '5173';
  const frontendPort = env.FRONTEND_PORT || env.VITE_FRONTEND_PORT || defaultFrontendPort;
  const backendUrl = (env.BACKEND_URL || env.VITE_API_BASE_URL || env.VITE_API_URL || `http://${backendHost}:${backendPort}`)
    .replace(/\/+$/, '')
    .replace(/\/api$/, '');
  const wsUrl = (env.WS_URL || env.VITE_WS_URL || backendUrl.replace(/^http/i, 'ws'))
    .replace(/\/+$/, '');
  const frontendUrl = (env.FRONTEND_URL || env.BASE_URL || `http://${backendHost}:${frontendPort}`)
    .replace(/\/+$/, '');

  // 获取当前环境
  const isDevelopment = mode === 'development';
  const isTesting = mode === 'testing';
  const isProduction = mode === 'production';

  return {
    envDir,

    // 基础路径：使用相对路径，确保 Electron 本地文件加载时资源引用正确
    base: './',

    // 根目录
    root: resolve(__dirname, '../apps/frontend'),

    // 开发服务器配置
    server: {
      port: Number(frontendPort),
      strictPort: false,
      host: true,
      open: true,
      cors: true,
      headers: {
        'Cache-Control': 'no-store',
      },
      proxy: {
        // 代理后端 API 请求
        '/api': {
          target: backendUrl,
          changeOrigin: true,
        },
        // 代理 WebSocket 连接
        '/ws': {
          target: wsUrl,
          ws: true,
          changeOrigin: true,
        },
      },
    },

    // 生产环境构建配置
    build: {
      outDir: 'dist',
      emptyOutDir: true,
      sourcemap: isDevelopment || isTesting,
      minify: isProduction ? 'esbuild' : false,
      target: 'es2018',
      // CSS 代码分割
      cssCodeSplit: true,
      // 启用压缩
      reportCompressedSize: true,
      // 代码分割配置
      rollupOptions: {
        output: {
          manualChunks: (id: string) => {
            // 启动相关的关键代码（优先级最高）
            if (id.includes('SplashScreen') || id.includes('LaunchProgressManager') ||
                id.includes('StartupManager') || id.includes('LoadingManager') ||
                id.includes('ResourceOptimizationConfig')) {
              return 'startup';
            }

            // 管理器模块
            if (id.includes('/managers/') || id.includes('ComponentInitializer') ||
                id.includes('EventBinder') || id.includes('StateManager')) {
              return 'managers';
            }

            // 将地图引擎分离为独立 chunk（按不同引擎）
            if (id.includes('ArcGISEngine') || id.includes('arcgis')) {
              return 'map-arcgis';
            }
            if (id.includes('AMapEngine') || id.includes('amap')) {
              return 'map-amap';
            }
            if (id.includes('TiandituEngine') || id.includes('tianditu')) {
              return 'map-tianditu';
            }
            if (id.includes('/apps/frontend/js/adapters/') || id.includes('/apps/frontend/js/map/core/')) {
              return 'map-core';
            }

            // 将图表组件分离为独立 chunk
            if (id.includes('VariogramChart') || id.includes('UncertaintyHistogram') ||
                id.includes('CrossValidationScatterChart') || id.includes('SamplingEfficiencyChart')) {
              return 'charts';
            }

            // 将工具类分离为独立 chunk
            if (id.includes('/apps/frontend/js/utils/')) {
              return 'utils';
            }

            // 将采样相关组件分离为独立 chunk
            if (id.includes('/apps/frontend/js/sampling/')) {
              return 'sampling';
            }

            // 核心功能组件
            if (id.includes('SettingsPanel') || id.includes('PreferencesPanel') ||
                id.includes('NewProjectModal') || id.includes('DataImportModal') ||
                id.includes('ConfirmDialog')) {
              return 'core-components';
            }

            // 地图交互组件
            if (id.includes('MapTooltip') || id.includes('MapLegend') ||
                id.includes('LayerComparisonPanel') || id.includes('MeasureTool') ||
                id.includes('MapEngineSwitcher') || id.includes('LocationCenterButton')) {
              return 'map-interaction';
            }

            // 参数相关组件
            if (id.includes('ParameterAdjustmentPanel') || id.includes('ParameterTabPanel') ||
                id.includes('ParameterHistoryManager') || id.includes('ParameterComparisonPanel') ||
                id.includes('ParameterInfoPanel')) {
              return 'parameter-components';
            }

            // 采样建议相关组件
            if (id.includes('SamplingRecommendationPanel') || id.includes('EnhancedSamplingRecommendationPanel') ||
                id.includes('InteractiveSamplingMarkers') || id.includes('SamplingStrategySelector')) {
              return 'sampling-recommendation';
            }

            // 离线相关组件
            if (id.includes('OfflineModeBanner') || id.includes('CacheManagementPanel')) {
              return 'offline-components';
            }

            // 其他组件
            if (id.includes('/apps/frontend/js/components/')) {
              return 'components';
            }

            // API服务
            if (id.includes('/apps/frontend/js/services/')) {
              return 'services';
            }

            // 模型层
            if (id.includes('/apps/frontend/js/models/')) {
              return 'models';
            }
          },
          chunkFileNames: 'assets/[name]-[hash].js',
          entryFileNames: 'assets/[name]-[hash].js',
          assetFileNames: 'assets/[name]-[hash].[ext]'
        }
      },
      // 优化 chunk 大小警告阈值
      chunkSizeWarningLimit: 800,
    },

    // 依赖预构建配置
    optimizeDeps: {
      exclude: ['@arcgis/core'],
      // 预构建大型依赖
      include: [
        'echarts',
      ]
    },

    // CSS配置
    css: {
      devSourcemap: isDevelopment,
    },

    // 别名配置
    resolve: {
      extensions: ['.mjs', '.js', '.ts', '.jsx', '.tsx', '.json'],
      alias: {
        '@services': resolve(__dirname, '../apps/frontend/js/services'),
        '@components': resolve(__dirname, '../apps/frontend/js/components'),
        '@utils': resolve(__dirname, '../apps/frontend/js/utils'),
        '@models': resolve(__dirname, '../apps/frontend/js/models'),
        '@map': resolve(__dirname, '../apps/frontend/js/map'),
        '@adapters': resolve(__dirname, '../apps/frontend/js/adapters'),
        '@sampling': resolve(__dirname, '../apps/frontend/js/sampling'),
        '@config': resolve(__dirname, '../apps/frontend/js/config'),
        '@types': resolve(__dirname, '../apps/frontend/types'),
      },
    },

    // 预览服务器配置
    preview: {
      port: 4173,
      host: true,
      open: true,
      proxy: {
        '/api': {
          target: backendUrl,
          changeOrigin: true,
        },
        // 代理 WebSocket 连接
        '/ws': {
          target: wsUrl,
          ws: true,
          changeOrigin: true,
        },
      },
    },

    // 定义全局常量
    define: {
      __APP_ENV__: JSON.stringify(mode),
      __APP_VERSION__: JSON.stringify(env.VITE_APP_VERSION || '1.0.0'),
      __APP_NAME__: JSON.stringify(env.VITE_APP_NAME || 'UDAKE'),
      __API_BASE_URL__: JSON.stringify(backendUrl),
      __WS_URL__: JSON.stringify(wsUrl),
      __FRONTEND_URL__: JSON.stringify(frontendUrl),
      'import.meta.env.VITE_OFFICIAL_WEB': JSON.stringify(process.env.OFFICIAL_WEB),
      'import.meta.env.VITE_ADMIN_WEB': JSON.stringify(process.env.ADMIN_WEB),
    },
  };
});

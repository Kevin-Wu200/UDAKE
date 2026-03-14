import { defineConfig, loadEnv } from 'vite';
import { resolve } from 'path';

export default defineConfig(({ mode }) => {
  // 加载环境变量
  const env = loadEnv(mode, process.cwd(), '');

  // 获取当前环境
  const isDevelopment = mode === 'development';
  const isTesting = mode === 'testing';
  const isProduction = mode === 'production';

  return {
    // 基础路径：使用相对路径，确保 Electron 本地文件加载时资源引用正确
    base: './',

    // 根目录
    root: 'frontend',

    // 开发服务器配置
    server: {
      port: isTesting ? 5174 : 5173,
      strictPort: false,
      host: true,
      open: true,
      cors: true,
      proxy: {
        // 代理后端 API 请求
        '/api': {
          target: env.VITE_API_BASE_URL || 'http://localhost:8000',
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
      target: 'es2020',
    },

    // 依赖预构建配置
    optimizeDeps: {
      exclude: ['@arcgis/core'],
    },

    // CSS配置
    css: {
      devSourcemap: isDevelopment,
    },

    // 别名配置
    resolve: {
      alias: {
        '@services': resolve(__dirname, './frontend/js/services'),
        '@components': resolve(__dirname, './frontend/js/components'),
        '@utils': resolve(__dirname, './frontend/js/utils'),
        '@models': resolve(__dirname, './frontend/js/models'),
        '@map': resolve(__dirname, './frontend/js/map'),
        '@adapters': resolve(__dirname, './frontend/js/adapters'),
        '@sampling': resolve(__dirname, './frontend/js/sampling'),
        '@config': resolve(__dirname, './frontend/js/config'),
        '@types': resolve(__dirname, './frontend/types'),
      },
    },

    // 预览服务器配置
    preview: {
      port: 4173,
      host: true,
      open: true,
      proxy: {
        '/api': {
          target: env.VITE_API_BASE_URL || 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },

    // 定义全局常量
    define: {
      __APP_ENV__: JSON.stringify(mode),
      __APP_VERSION__: JSON.stringify(env.VITE_APP_VERSION || '1.0.0'),
      __APP_NAME__: JSON.stringify(env.VITE_APP_NAME || 'UDAKE'),
      __API_BASE_URL__: JSON.stringify(env.VITE_API_BASE_URL || 'http://localhost:8000'),
    },
  };
});
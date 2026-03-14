import { defineConfig } from 'vite';
import { resolve } from 'path';

export default defineConfig({
  // 基础路径：使用相对路径，确保 Electron 本地文件加载时资源引用正确
  base: './',

  // 根目录
  root: 'frontend',

  // 开发服务器配置
  server: {
    port: 5173,
    strictPort: false,
    host: true,
    open: true,
    cors: true,
  },

  // 生产环境构建配置
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: true,
    minify: 'esbuild',
    target: 'es2020',
  },

  // 依赖预构建配置
  optimizeDeps: {
    exclude: ['@arcgis/core'],
  },

  // CSS配置
  css: {
    devSourcemap: true,
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
  },
});
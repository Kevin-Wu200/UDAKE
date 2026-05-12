import { defineConfig, loadEnv } from 'vite';
import vue from '@vitejs/plugin-vue';
import AutoImport from 'unplugin-auto-import/vite';
import Components from 'unplugin-vue-components/vite';
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers';
import { resolve } from 'path';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');

  const backendHost = env.IPCONFIG || env.VITE_IPCONFIG || env.VITE_BACKEND_HOST || 'localhost';
  const backendPort = env.BACKEND_PORT || env.VITE_BACKEND_PORT || '8000';
  const adminPort = env.ADMIN_FRONTEND_PORT || '5175';
  const backendUrl = `http://${backendHost}:${backendPort}`;

  return {
    plugins: [
      vue(),
      AutoImport({
        imports: ['vue', 'vue-router', 'pinia'],
        resolvers: [ElementPlusResolver({ importStyle: true })],
        dts: 'src/auto-imports.d.ts'
      }),
      Components({
        resolvers: [ElementPlusResolver({ importStyle: true })],
        dts: 'src/components.d.ts'
      })
    ],
    server: {
      port: Number(adminPort),
      strictPort: false,
      host: true,
      open: true,
      cors: true,
      proxy: {
        '/api': {
          target: backendUrl,
          changeOrigin: true,
        },
      },
    },
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src'),
      },
    },
    optimizeDeps: {
      include: [
        'vue',
        'vue-router',
        'pinia',
        'element-plus',
        'element-plus/es/components/dialog/style/css',
        'element-plus/es/components/table/style/css',
        'element-plus/es/components/table-column/style/css',
        'element-plus/es/components/pagination/style/css',
        'element-plus/es/components/tag/style/css',
        'element-plus/es/components/loading/style/css',
        'element-plus/es/components/card/style/css',
        'element-plus/es/components/breadcrumb/style/css',
        'element-plus/es/components/breadcrumb-item/style/css',
        'element-plus/es/components/menu/style/css',
        'element-plus/es/components/menu-item/style/css',
        'element-plus/es/components/sub-menu/style/css',
        'element-plus/es/components/icon/style/css',
        'element-plus/es/components/segmented/style/css',
      ],
    },
    define: {
      'import.meta.env.VITE_USE_MOCK_API': mode === 'production' ? JSON.stringify('false') : JSON.stringify(env.VITE_USE_MOCK_API || 'false'),
    },
  };
});

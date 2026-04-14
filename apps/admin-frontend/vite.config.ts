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
  };
});

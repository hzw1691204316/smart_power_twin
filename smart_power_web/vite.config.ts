import { fileURLToPath, URL } from 'node:url'

import { defineConfig, normalizePath } from 'vite'
import vue from '@vitejs/plugin-vue'
import { viteStaticCopy } from 'vite-plugin-static-copy'

const cesiumRoot = normalizePath(
  fileURLToPath(new URL('./node_modules/cesium/Build/Cesium', import.meta.url)),
)
// 开发/预览统一同源API；不是把后端端口改为5173，后端仍独立启动在8000。
const apiProxy = { '/api': { target: 'http://127.0.0.1:8000' } }

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    viteStaticCopy({
      targets: ['Workers', 'ThirdParty', 'Assets', 'Widgets'].map((directory) => ({
        src: `${cesiumRoot}/${directory}`,
        dest: 'cesiumStatic',
        rename: { stripBase: 4 },
      })),
    }),
  ],
  define: { CESIUM_BASE_URL: JSON.stringify('/cesiumStatic/') },
  server: { host: '127.0.0.1', port: 5173, strictPort: true, proxy: apiProxy },
  preview: { host: '127.0.0.1', proxy: apiProxy },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
})

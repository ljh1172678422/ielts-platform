import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// https://vite.dev/config/
// base 支持环境变量覆盖：生产统一 nginx 部署到 /admin/ 子路径时设 ADMIN_BASE=/admin/
// 默认 '/' 适用于独立容器部署（dev server + 独立 nginx 托管根路径）
export default defineConfig({
  base: process.env.ADMIN_BASE ?? '/',
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    // 区别于 user-web 的 5173
    port: 5174,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})

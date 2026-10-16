import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 端口中转方案（2026-10-15）：
//   前端 Vite 占 18082（= 公网已放行的端口），后端让位到 18083。
//   frpc 现有映射 kefu: 18082 -> localhost:18082 因此自动指向前端，无需改 frpc / 云防火墙。
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '127.0.0.1',
    port: 18082,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:18083', // 客服主后端（原 18082）
        changeOrigin: true,
      },
      '/commerce': {
        target: 'http://127.0.0.1:18081',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/commerce/, ''),
      },
      '/health': {
        target: 'http://127.0.0.1:18083', // 客服主后端（原 18082）
        changeOrigin: true,
      },
      '/docs': {
        target: 'http://127.0.0.1:18083', // 后端 API 文档，照旧可看
        changeOrigin: true,
      },
      '/openapi.json': {
        target: 'http://127.0.0.1:18083',
        changeOrigin: true,
      },
    },
  },
})

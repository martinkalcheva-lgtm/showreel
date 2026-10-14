import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 本地开发代理：浏览器全部走同源，规避 CORS
//   /kbapi -> 8000  Boss智库 导入服务 (upload / status)
//   /kbq   -> 8001  Boss智库 查询服务 (query / stream / history)
//   /dsapi -> 8002  data-agent 问数 (POST /api/query, SSE)
// 注意：data-agent 默认端口与导入服务冲突，启动时用命令行换端口：
//   uvicorn main:app --port 8002  （不改后端代码）
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/kbapi': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/kbapi/, ''),
      },
      '/kbq': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/kbq/, ''),
      },
      '/dsapi': {
        target: 'http://localhost:8002',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/dsapi/, ''),
      },
    },
  },
})

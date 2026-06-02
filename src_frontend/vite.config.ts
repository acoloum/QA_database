import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,            // 開發伺服器改用 5173，與生產(:80 waitress) 並存不搶埠
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:80',  // 開發時 /api 轉發到生產 waitress(:80)，免另開後端
        changeOrigin: true,
        secure: false,
      },
    },
  },
})

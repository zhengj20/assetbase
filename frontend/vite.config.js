import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',  // 允许外部访问
    port: 5201,
    proxy: {
      '/api': { target: 'http://127.0.0.1:5200', changeOrigin: true },
    },
  },
  build: {
    // 大依赖独立分包，避免单个 chunk 超过 500KB（echarts/element-plus 体积大且稳定，适合单独缓存）
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        manualChunks: {
          vue: ['vue', 'vue-router', 'pinia'],
          'element-plus': ['element-plus', '@element-plus/icons-vue'],
          echarts: ['echarts'],
          qrcode: ['html5-qrcode'],
        },
      },
    },
  },
})

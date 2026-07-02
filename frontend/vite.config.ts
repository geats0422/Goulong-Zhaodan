import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

function bypassHtmlNavigation(req: { headers: { accept?: string } }) {
  if (req.headers.accept?.includes('text/html')) return '/index.html'
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5174,
    strictPort: true,
    proxy: {
      '/auth': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/settings': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        bypass: bypassHtmlNavigation,
      },
      '/inspection': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        bypass: bypassHtmlNavigation,
      },
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})

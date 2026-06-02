import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'

// vite-plugin-pwa (workbox-build) butuh Node 20+. Di Node <20 dimatikan otomatis.
const nodeMajor = Number(process.versions.node.split('.')[0])

// Build untuk disajikan bench: set STOCKOPS_OUTDIR ke apps/stock_ops/stock_ops/public/stock_ops.
const frappeOut = process.env.STOCKOPS_OUTDIR || ''
const isFrappeBuild = !!frappeOut
// SW PWA dimatikan di Node<20 dan (sementara) pada build bench (scope SW di sub-path perlu penanganan khusus).
const pwaDisabled = nodeMajor < 20 || isFrappeBuild

export default defineConfig(({ mode }) => {
  // loadEnv tanpa prefix '' => baca SEMUA var (termasuk non-VITE seperti FRAPPE_*).
  // Var non-VITE TIDAK diekspos ke kode klien — hanya tersedia di sini (Node).
  const env = loadEnv(mode, process.cwd(), '')
  // Node tidak me-resolve hostname *.localhost → konek via 127.0.0.1, tapi kirim
  // Host header asli (mis. erp.localhost:8000) supaya Frappe memilih site yang tepat.
  const url = new URL(env.FRAPPE_URL || 'http://erp.localhost:8000')
  const siteHost = url.host
  const target = `${url.protocol}//127.0.0.1:${url.port || (url.protocol === 'https:' ? 443 : 80)}`
  const authToken =
    env.FRAPPE_API_KEY && env.FRAPPE_API_SECRET
      ? `token ${env.FRAPPE_API_KEY}:${env.FRAPPE_API_SECRET}`
      : ''

  // Suntik Host + Authorization di sisi server (token tak pernah ke browser).
  const makeProxy = (server) => {
    server.on('proxyReq', (proxyReq) => {
      proxyReq.setHeader('Host', siteHost)
      if (authToken) proxyReq.setHeader('Authorization', authToken)
    })
  }
  const proxy = {}
  for (const path of ['/api', '/files', '/private', '/assets']) {
    proxy[path] = { target, changeOrigin: false, secure: false, configure: makeProxy }
  }

  return {
    base: isFrappeBuild ? '/assets/stock_ops/stock_ops/' : '/',
    build: isFrappeBuild ? { outDir: frappeOut, emptyOutDir: true, target: 'es2018' } : {},
    plugins: [
      vue(),
      VitePWA({
        disable: pwaDisabled,
        registerType: 'autoUpdate',
        manifest: {
          name: 'Stock Ops',
          short_name: 'StockOps',
          description: 'Material Request & Stock Entry (mobile)',
          theme_color: '#8a6f4e',
          background_color: '#181410',
          display: 'standalone',
          orientation: 'portrait',
          icons: [{ src: 'icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any maskable' }]
        },
        workbox: { navigateFallback: 'index.html' }
      })
    ],
    server: { port: 5173, proxy },
    preview: { port: 5173, proxy }
  }
})

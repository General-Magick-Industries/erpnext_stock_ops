// SW lama (scope /stock_ops/) — DIGANTI /stock_ops_sw.js (scope /stock_ops).
// Versi ini melepas dirinya sendiri & cache lamanya agar instalasi lama tidak tertahan di URL ber-slash.
self.addEventListener('install', () => self.skipWaiting())
self.addEventListener('activate', (e) => {
  e.waitUntil(
    (async () => {
      const keys = await caches.keys()
      await Promise.all(keys.filter((k) => k.startsWith('stockops-v') && k !== 'stockops-v3').map((k) => caches.delete(k)))
      await self.registration.unregister()
    })()
  )
})

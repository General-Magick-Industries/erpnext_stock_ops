// Deteksi platform & konfigurasi koneksi.
// - Web (di-serve bench / dev): same-origin, cookie/CSRF atau proxy token.
// - Native (Capacitor/Android): panggil ERPNext via base URL absolut + token auth.
//   CapacitorHttp (diaktifkan di capacitor.config) mem-patch fetch → request lewat native,
//   sehingga TIDAK terkena CORS browser sama sekali.

const LS_URL = 'stockops.serverUrl'
const LS_KEY = 'stockops.apiKey'
const LS_SEC = 'stockops.apiSecret'

let _native = false
try {
  _native = !!(window.Capacitor && typeof window.Capacitor.isNativePlatform === 'function' && window.Capacitor.isNativePlatform())
} catch {
  _native = false
}

export const isNative = () => _native

export function getServerUrl() {
  return localStorage.getItem(LS_URL) || ''
}
export function setServerUrl(u) {
  localStorage.setItem(LS_URL, (u || '').replace(/\/+$/, ''))
}

// Base untuk semua request: native → server URL tersimpan; web → same-origin ('').
export function apiBase() {
  return isNative() ? getServerUrl() : ''
}

export function getToken() {
  const k = localStorage.getItem(LS_KEY)
  const s = localStorage.getItem(LS_SEC)
  return k && s ? `token ${k}:${s}` : ''
}
export function setToken(key, secret) {
  localStorage.setItem(LS_KEY, key)
  localStorage.setItem(LS_SEC, secret)
}
export function clearToken() {
  localStorage.removeItem(LS_KEY)
  localStorage.removeItem(LS_SEC)
}

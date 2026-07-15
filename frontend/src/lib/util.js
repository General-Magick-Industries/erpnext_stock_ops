export function uuid() {
  if (crypto && crypto.randomUUID) return crypto.randomUUID()
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

export function todayStr() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

export function fmtDateTime(iso) {
  if (!iso) return '-'
  // Tolerate "YYYY-MM-DD HH:mm:ss[.ffffff]" (space-separated) and stray concatenations;
  // never render "NaN/NaN/NaN" — fall back to the raw date on an unparseable input.
  const d = new Date(String(iso).replace(' ', 'T'))
  if (isNaN(d.getTime())) return String(iso).slice(0, 16).replace('T', ' ')
  const p = (n) => String(n).padStart(2, '0')
  return `${p(d.getDate())}/${p(d.getMonth() + 1)}/${d.getFullYear()} ${p(d.getHours())}:${p(d.getMinutes())}`
}

// Resize foto dari kamera/galeri ke JPEG ringan agar muat di localStorage (mock).
export function fileToResizedDataUrl(file, maxSize = 1024, quality = 0.7) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const img = new Image()
      img.onload = () => {
        let { width, height } = img
        if (width > height && width > maxSize) {
          height = Math.round((height * maxSize) / width)
          width = maxSize
        } else if (height > maxSize) {
          width = Math.round((width * maxSize) / height)
          height = maxSize
        }
        const canvas = document.createElement('canvas')
        canvas.width = width
        canvas.height = height
        canvas.getContext('2d').drawImage(img, 0, 0, width, height)
        resolve(canvas.toDataURL('image/jpeg', quality))
      }
      img.onerror = reject
      img.src = reader.result
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

// Resize foto → Blob JPEG ringan (untuk disimpan di IndexedDB).
export function fileToResizedBlob(file, maxSize = 1024, quality = 0.7) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const img = new Image()
      img.onload = () => {
        let { width, height } = img
        if (width > height && width > maxSize) {
          height = Math.round((height * maxSize) / width)
          width = maxSize
        } else if (height > maxSize) {
          width = Math.round((width * maxSize) / height)
          height = maxSize
        }
        const canvas = document.createElement('canvas')
        canvas.width = width
        canvas.height = height
        canvas.getContext('2d').drawImage(img, 0, 0, width, height)
        canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('toBlob gagal'))), 'image/jpeg', quality)
      }
      img.onerror = reject
      img.src = reader.result
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

export function delay(ms) {
  return new Promise((r) => setTimeout(r, ms))
}

// Buang tag HTML dari pesan server Frappe (kadang mengandung <b>, <br>, dll).
export function stripHtml(s) {
  return String(s || '')
    .replace(/<[^>]*>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

// Deteksi error "stok minus" dari ERPNext (Allow Negative Stock non-aktif).
// Cocokkan varian pesan EN maupun ID agar bisa diterjemahkan jadi pesan yang jelas.
export function isNegativeStockError(msg) {
  return /negative stock|is negative|insufficient stock|to complete this transaction|needed in warehouse|stok.*minus|stok tidak (cukup|mencukupi)/i.test(
    String(msg || '')
  )
}

// Ambil koordinat GPS → "lat,lng" (atau null bila gagal/ditolak). Butuh secure context (localhost/HTTPS).
export function getGeolocation(timeout = 8000) {
  return new Promise((resolve) => {
    if (typeof navigator === 'undefined' || !navigator.geolocation) return resolve(null)
    navigator.geolocation.getCurrentPosition(
      (p) => resolve(`${p.coords.latitude.toFixed(6)},${p.coords.longitude.toFixed(6)}`),
      () => resolve(null),
      { enableHighAccuracy: true, timeout, maximumAge: 60000 }
    )
  })
}

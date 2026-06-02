// Lapisan akses Frappe REST. Browser memanggil same-origin (/api/...),
// proxy dev (vite.config.js) menambahkan token auth di sisi Node.
// Saat di-deploy di dalam bench (P4), same-origin pakai cookie sesi.

// CSRF token disuntik oleh www page Frappe (window.csrf_token). Di dev (proxy token) kosong.
function csrfToken() {
  const t = typeof window !== 'undefined' ? window.csrf_token : ''
  if (!t || t.includes('{{')) return ''
  return t
}

class ApiError extends Error {
  constructor(message, status, data) {
    super(message)
    this.status = status
    this.data = data
  }
}

function serverMessages(json) {
  try {
    const msgs = json._server_messages ? JSON.parse(json._server_messages) : []
    return msgs.map((m) => (typeof m === 'string' ? JSON.parse(m).message : m.message)).join(' · ')
  } catch {
    return ''
  }
}

async function handle(res) {
  let json = null
  const text = await res.text()
  try {
    json = text ? JSON.parse(text) : null
  } catch {
    json = null
  }
  if (!res.ok) {
    const msg =
      (json && (serverMessages(json) || json.exception || json.message)) ||
      `HTTP ${res.status}`
    throw new ApiError(typeof msg === 'string' ? msg : 'Request gagal', res.status, json)
  }
  return json
}

// Panggil whitelisted method. GET untuk read, POST untuk aksi.
export async function call(method, params = {}, { post = false } = {}) {
  let url = `/api/method/${method}`
  const opts = { method: post ? 'POST' : 'GET', headers: { Accept: 'application/json' } }
  if (post) {
    opts.headers['Content-Type'] = 'application/json'
    const c = csrfToken()
    if (c) opts.headers['X-Frappe-CSRF-Token'] = c
    opts.body = JSON.stringify(params)
  } else {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(params)) qs.append(k, typeof v === 'object' ? JSON.stringify(v) : v)
    const s = qs.toString()
    if (s) url += `?${s}`
  }
  const json = await handle(await fetch(url, opts))
  return json ? json.message : null
}

// List dokumen via resource API.
export async function list(doctype, { fields, filters, limit = 0, order_by, parent } = {}) {
  const qs = new URLSearchParams()
  if (fields) qs.append('fields', JSON.stringify(fields))
  if (filters) qs.append('filters', JSON.stringify(filters))
  if (order_by) qs.append('order_by', order_by)
  qs.append('limit_page_length', String(limit))
  if (parent) qs.append('parent', parent)
  const json = await handle(await fetch(`/api/resource/${encodeURIComponent(doctype)}?${qs.toString()}`))
  return json ? json.data : []
}

export async function getDoc(doctype, name) {
  const json = await handle(await fetch(`/api/resource/${encodeURIComponent(doctype)}/${encodeURIComponent(name)}`))
  return json ? json.data : null
}

// Upload satu foto (Blob) & lampirkan ke dokumen.
export async function uploadFile(blob, { doctype, docname, isPrivate = true, filename = 'photo.jpg' }) {
  const fd = new FormData()
  fd.append('file', blob, filename)
  fd.append('is_private', isPrivate ? '1' : '0')
  fd.append('folder', 'Home/Attachments')
  fd.append('doctype', doctype)
  fd.append('docname', docname)
  const headers = {}
  const c = csrfToken()
  if (c) headers['X-Frappe-CSRF-Token'] = c
  const json = await handle(await fetch('/api/method/upload_file', { method: 'POST', body: fd, headers }))
  return json ? json.message : null
}

export { ApiError }

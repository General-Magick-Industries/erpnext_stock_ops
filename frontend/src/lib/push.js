import { call } from './api'

const SCOPE = '/stock_ops/'

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = atob(base64)
  const arr = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i)
  return arr
}

// Push hanya didukung saat disajikan bench (SW + secure context).
export function pushSupported() {
  return (
    typeof window !== 'undefined' &&
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window &&
    !!window.csrf_token &&
    !String(window.csrf_token).includes('{{')
  )
}

async function reg() {
  return (await navigator.serviceWorker.getRegistration(SCOPE)) || (await navigator.serviceWorker.ready)
}

export async function isSubscribed() {
  if (!pushSupported()) return false
  try {
    const r = await navigator.serviceWorker.getRegistration(SCOPE)
    if (!r) return false
    return !!(await r.pushManager.getSubscription())
  } catch {
    return false
  }
}

export async function enablePush() {
  if (!pushSupported()) throw new Error('unsupported')
  const perm = await Notification.requestPermission()
  if (perm !== 'granted') throw new Error('denied')
  const r = await reg()
  const key = await call('stock_ops.push.get_public_key')
  let sub = await r.pushManager.getSubscription()
  if (!sub) {
    sub = await r.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(key)
    })
  }
  await call('stock_ops.push.save_subscription', { subscription: sub.toJSON() }, { post: true })
  return true
}

export async function disablePush() {
  const r = await navigator.serviceWorker.getRegistration(SCOPE)
  if (!r) return
  const sub = await r.pushManager.getSubscription()
  if (sub) {
    await call('stock_ops.push.delete_subscription', { endpoint: sub.endpoint }, { post: true }).catch(() => {})
    await sub.unsubscribe()
  }
}

export async function sendTest() {
  return call('stock_ops.push.send_test', {}, { post: true })
}

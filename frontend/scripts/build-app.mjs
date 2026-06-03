// Build web assets untuk dibungkus Capacitor (Android).
// base '/', output ke dist/, service worker dimatikan (tak perlu di WebView native).
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const frontend = resolve(here, '..')
const env = { ...process.env, CAP: '1' }
const npx = process.platform === 'win32' ? 'npx.cmd' : 'npx'

console.log('Building app web assets → dist/ (PWA SW off)')
const r = spawnSync(npx, ['vite', 'build'], { cwd: frontend, env, stdio: 'inherit' })
process.exit(r.status || 0)

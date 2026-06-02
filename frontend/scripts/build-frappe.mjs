// Build PWA untuk disajikan bench, langsung ke modul app (repo gabungan pola HRMS).
// Dipakai di server: `cd apps/stock_ops/frontend && npm install && npm run build:frappe`
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { dirname, resolve, join } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url)) // frontend/scripts
const frontend = resolve(here, '..') // frontend/
// modul python ada di apps/stock_ops/stock_ops → relatif dari frontend: ../stock_ops
const outDir = resolve(frontend, '../stock_ops/public/stock_ops')
const wwwFile = resolve(frontend, '../stock_ops/www/stock_ops/index.html')

const env = { ...process.env, STOCKOPS_OUTDIR: outDir, STOCKOPS_WWW: wwwFile }
const npx = process.platform === 'win32' ? 'npx.cmd' : 'npx'

console.log('Building →', outDir)
let r = spawnSync(npx, ['vite', 'build'], { cwd: frontend, env, stdio: 'inherit' })
if (r.status !== 0) process.exit(r.status || 1)

r = spawnSync(process.execPath, [join(here, 'frappe-postbuild.mjs')], { cwd: frontend, env, stdio: 'inherit' })
process.exit(r.status || 0)

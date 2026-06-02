// Ubah index.html hasil build menjadi www/stock_ops.html (template Jinja Frappe),
// menyuntik csrf_token & user sesi. Asset path sudah absolut ke /assets/stock_ops/...
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'

const outDir = process.env.STOCKOPS_OUTDIR
const wwwFile = process.env.STOCKOPS_WWW
if (!outDir || !wwwFile) {
  console.error('Butuh env STOCKOPS_OUTDIR (folder build) dan STOCKOPS_WWW (path www/stock_ops.html)')
  process.exit(1)
}

let html = readFileSync(join(outDir, 'index.html'), 'utf8')

const inject =
  '\n  <link rel="manifest" href="/stock_ops/manifest.json">\n' +
  '  <link rel="apple-touch-icon" href="/assets/stock_ops/stock_ops/icon.svg">\n' +
  '  <script>\n' +
  '    window.csrf_token = "{{ csrf_token }}";\n' +
  '    window.stockops_user = "{{ stockops_user }}";\n' +
  '  </script>\n'

html = html.replace(/<head>/i, '<head>' + inject)

mkdirSync(dirname(wwwFile), { recursive: true })
writeFileSync(wwwFile, html)
console.log('Wrote', wwwFile)

# Stock Ops PWA — Frontend

PWA mobile-first untuk Material Request & Stock Entry (ERPNext v16). Lihat `../PRD.md`.

Status: **P0 (UI)**, **P1 (core online)**, **P2 (offline + scan)** selesai. Tersaji via bench di `/stock_ops`.

## A. Jalankan dev (Windows, hot reload)

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

- Auth dev: Vite proxy meneruskan `/api`,`/files`,`/private`,`/assets` ke `127.0.0.1:8000`
  (Host header `erp.localhost`) dan menyuntik **token** dari `.env.local` di sisi Node
  (var non-`VITE_` → tidak masuk bundle browser). Browser hanya panggil same-origin.
- Backend harus jalan: di WSL `cd ~/frappe-bench && bench start`.
- `.env.local` (gitignored) berisi `FRAPPE_URL`, `FRAPPE_API_KEY`, `FRAPPE_API_SECRET`.

> Scan kamera (getUserMedia) butuh **localhost/HTTPS** → di dev pakai localhost (webcam).
> Ambil foto (file/kamera bawaan) jalan di http biasa.

## B. Build & sajikan via bench (mode produksi, cookie + CSRF)

Build di Windows (Node 18; SW di-skip pada build bench), lalu salin ke app di WSL.

**Windows (PowerShell):**
```powershell
cd frontend
$env:STOCKOPS_OUTDIR="dist-frappe"; $env:STOCKOPS_WWW="dist-frappe\stock_ops.html"
npm run build
node scripts/frappe-postbuild.mjs
Remove-Item Env:\STOCKOPS_OUTDIR; Remove-Item Env:\STOCKOPS_WWW
```

**WSL (salin hasil ke app + clear cache):**
```bash
APP=~/frappe-bench/apps/stock_ops/stock_ops
SRC=/mnt/d/Workspace/StockInOutRMI/frontend/dist-frappe
cp -r "$SRC"/. "$APP/public/stock_ops/"
cp "$SRC/stock_ops.html" "$APP/www/stock_ops.html"
rm -f "$APP/public/stock_ops/stock_ops.html"
cd ~/frappe-bench && bench --site erp.localhost clear-cache
```

Akses: **http://erp.localhost:8000/stock_ops** (login Frappe dulu; guest diarahkan ke `/login`).
Saat tersaji bench, app auto-login dari sesi (`window.stockops_user`) dan pakai cookie + CSRF
(`X-Frappe-CSRF-Token`) — **tanpa token di klien**.

## Struktur
```
src/
  lib/        api.js (REST+csrf), service.js, payload.js, idb.js (foto Blob), i18n.js, util.js
  stores/     app.js (sesi/online/tema/bahasa), master.js (cache bootstrap), docs.js (outbox+sync)
  components/ AppBar, TabBar, Sheet, ItemPickerSheet, PhotoUploader, BarcodeScanner, StatusBadge
  views/      Login, Home, Create, DocForm, DocList, DocDetail, Sync, Settings
scripts/      frappe-postbuild.mjs (index.html → www/stock_ops.html + inject csrf)
```

## Catatan
- **Offline**: master data di-cache (localStorage), transaksi masuk outbox, **foto sebagai Blob di
  IndexedDB**; auto-sync saat kembali online. Idempotensi via `external_localid` (cegah duplikat).
- **PWA install / service worker**: belum aktif (scope SW di sub-path Frappe perlu penanganan
  khusus). Data-offline sudah jalan; SW app-shell menyusul.

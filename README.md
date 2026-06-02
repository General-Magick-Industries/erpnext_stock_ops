# Stock Ops — Frappe App + PWA (ERPNext v16)

Custom Frappe app **`stock_ops`**: PWA gudang mobile-first untuk **Material Request**, **Stock Entry**,
**Stok/Mutasi**, **Stok Menipis + Bulk Request**, **Stock Opname**, **scan barcode**, **foto**, **geolokasi**,
**offline + auto-sync**, dan **push notification**. App + frontend dalam satu repo (pola Frappe HR / HRMS).

## Struktur

```
stock_ops/                 # repo = apps/stock_ops di bench
├── stock_ops/             # modul Python: hooks, api.py, push.py, setup/, doctype/, www/stock_ops/
├── frontend/              # PWA (Vue 3 + Vite) — sumber
├── pyproject.toml
└── README.md
```

## Instalasi di server (bench)

```bash
cd ~/frappe-bench

# 1. ambil app
bench get-app stock_ops https://github.com/denzizzy966/stock_ops --branch new-develop

# 2. install ke site
bench --site <site> install-app stock_ops

# 3. migrate (buat DocType + custom field + VAPID keys via after_install)
bench --site <site> migrate

# 4. build frontend PWA → otomatis ditaruh ke stock_ops/public/stock_ops + www
cd apps/stock_ops/frontend
npm install
npm run build:frappe

# 5. bersihkan cache
cd ~/frappe-bench
bench --site <site> clear-cache
```

Akses: **`https://<site>/stock_ops`** (login Frappe dulu).

`after_install` membuat custom field (`external_localid`, `stock_ops_geolocation` di Material Request &
Stock Entry; `external_localid` di Stock Reconciliation; `stock_ops_warehouses` di Employee) + VAPID keys.
Jika perlu manual:
```bash
bench --site <site> execute stock_ops.setup.install.setup_custom_fields
bench --site <site> execute stock_ops.push.ensure_vapid_keys
```

## Pengembangan frontend (hot reload)

```bash
cd frontend
npm install
# .env.local (TIDAK di-commit): proxy dev menyuntik token di sisi Node
#   FRAPPE_URL=http://erp.localhost:8000
#   FRAPPE_API_KEY=xxxx
#   FRAPPE_API_SECRET=xxxx
npm run dev        # http://localhost:5173
```

## Penggunaan singkat

Login → `/stock_ops` → Beranda (jam, alert stok menipis), **➕ Buat** dokumen (item via cari/scan, foto,
📍 lokasi), **Stok / Mutasi**, **Stok Menipis** (centang → Request Beli), **Transfer Cepat**, **Stock Opname**.
Setelan: bahasa ID/EN, tema gelap, **Tampilan** (v2/Klasik/A/B), notifikasi push.
Pengaitan gudang per karyawan: Employee → field **"Stock Ops Warehouses"**.

## Catatan

- Produksi pakai sesi Frappe (cookie + CSRF). Token API hanya untuk proxy dev — tidak masuk bundle.
- Service worker / push aktif penuh di **HTTPS**.
- Lisensi: MIT.

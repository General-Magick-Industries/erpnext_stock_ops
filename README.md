# Stock Ops — Frappe App + PWA (ERPNext v16)

Custom Frappe app **`stock_ops`**: a mobile-first warehouse PWA for **Material Request**, **Stock Entry**,
**Stock balance / movement**, **Low stock + bulk request**, **Stock Opname**, **barcode scan**, **photos**,
**geolocation**, **offline + auto-sync**, and **push notifications**. The Frappe app and the frontend live in
one repo (same pattern as Frappe HR / HRMS). A companion **Android app (Flutter)** uses the same API.

- **Repository:** `https://github.com/denzizzy966/stock_ops`
- **Branch:** `new-develop`
- **Requires:** Frappe **v16** + ERPNext **v16** (ERPNext doctypes such as Material Request, Stock Entry,
  Warehouse, Bin are used).
- **Python:** **≥ 3.10** (works on the early-v16 / Python 3.11 benches too).
- **Node:** **≥ 20** to build the PWA (vite + workbox).

> **Built PWA assets are git-ignored** (`stock_ops/public/stock_ops/`, `stock_ops/www/stock_ops/index.html`).
> They must be **built on the server / inside the image** with `npm run build:frappe` — never committed.

---

## Repo layout

```
stock_ops/                 # repo root = apps/stock_ops in a bench
├── stock_ops/             # Python module: hooks, api.py, push.py, setup/, doctype/, workspace/, www/
├── frontend/              # PWA source (Vue 3 + Vite)
├── docker/                # apps.json + Containerfile for Docker/Kubernetes installs
├── pyproject.toml
└── README.md
```

---

## Authentication model (read this first)

There is **no shared API token** and **no dedicated "app user"**:

- Each user logs in to the app (PWA/Android) with **their own ERPNext username + password**. The app calls
  `stock_ops.api.get_or_create_token`, which mints a per-user `api_key:api_secret` for that user.
- Installation **creates roles, not users**. `after_install` / `after_migrate` auto-create
  **`Stock Ops User`** and **`Stock Ops Manager`** and map their permissions onto Material Request / Stock
  Entry / Stock Reconciliation (standard role permissions are preserved).
- **One APK** serves every site; the server is chosen from a dropdown on the login screen.

| Role | Create / Submit | Cancel | Delete | Edit Settings | Desk access |
|---|:---:|:---:|:---:|:---:|:---:|
| **Stock Ops User** | ✅ | ❌ | ❌ | ❌ | ❌ (PWA/Android only) |
| **Stock Ops Manager** | ✅ | ✅ | ✅ | ✅ | ✅ (Workspace) |

> `Administrator` bypasses all permission checks — test role limits with a normal user.

---

## Option A — Install on a bench (VM / bare-metal)

```bash
cd ~/frappe-bench

# 1. Get the app (public repo, no token needed)
bench get-app stock_ops https://github.com/denzizzy966/stock_ops --branch new-develop

# 2. Install on a site (runs after_install: custom fields + VAPID keys + roles)
bench --site <site> install-app stock_ops

# 3. Migrate (sync DocTypes, Workspace; runs after_migrate self-heal for roles)
bench --site <site> migrate

# 4. Build the PWA bundle (Node >= 20) → emitted into stock_ops/public + www
cd apps/stock_ops/frontend
npm install --no-audit --no-fund
npm run build:frappe

# 5. Restart + clear cache
cd ~/frappe-bench
bench build --app stock_ops
bench restart
bench --site <site> clear-cache
```

Open **`https://<site>/stock_ops`** (log in with an ERPNext account). Managers also get a Desk Workspace via
the App Switcher (⊞ → **Stock Ops**).

---

## Option B — Docker (frappe_docker custom image)

Stock Ops is a normal Frappe app, so the standard
[frappe_docker custom-apps](https://github.com/frappe/frappe_docker/blob/main/docs/custom-apps.md) flow applies.
The **only** app-specific step is building the PWA bundle (see note above) — the provided overlay
`docker/Containerfile` does that for you.

### B.1 — Build a base image that contains the apps

Use the `docker/apps.json` in this repo (frappe is supplied via build args; erpnext + stock_ops are listed):

```bash
git clone https://github.com/frappe/frappe_docker
cd frappe_docker

export APPS_JSON_BASE64=$(base64 -w 0 /path/to/stock_ops/docker/apps.json)

docker build \
  --build-arg=FRAPPE_PATH=https://github.com/frappe/frappe \
  --build-arg=FRAPPE_BRANCH=version-16 \
  --build-arg=APPS_JSON_BASE64=$APPS_JSON_BASE64 \
  --tag=ghcr.io/<your-org>/stockops-erpnext:base \
  --file=images/layered/Containerfile .
```

### B.2 — Bake the PWA assets into the image

```bash
cd /path/to/stock_ops
docker build \
  --build-arg=BASE_IMAGE=ghcr.io/<your-org>/stockops-erpnext:base \
  --tag=ghcr.io/<your-org>/stockops-erpnext:latest \
  --file=docker/Containerfile .

docker push ghcr.io/<your-org>/stockops-erpnext:latest
```

### B.3 — Run it and install on the site

Point your compose stack at the new image, then:

```bash
# install on the site (creates roles, custom fields, VAPID keys)
docker compose exec backend bench --site <site> install-app stock_ops
docker compose exec backend bench --site <site> migrate
docker compose exec backend bench --site <site> clear-cache
docker compose restart backend frontend
```

> If `/assets/stock_ops/stock_ops/...` 404s after install, the asset volume was created before the app was
> baked in — re-run `bench build --app stock_ops` in the backend container and restart, or recreate the
> `assets` volume so it is repopulated from the new image.

---

## Option C — Kubernetes (Helm)

Use the **same custom image** built in Option B as `image.repository` / `image.tag` in the ERPNext Helm
values. Then run the one-off app install against your site:

```bash
# exec into the backend pod (or run as a Job)
kubectl exec -it deploy/<release>-erpnext-backend -- \
  bench --site <site> install-app stock_ops
kubectl exec -it deploy/<release>-erpnext-backend -- \
  bench --site <site> migrate
kubectl exec -it deploy/<release>-erpnext-backend -- \
  bench --site <site> clear-cache
# roll the web/socketio pods so the new assets are served
kubectl rollout restart deploy/<release>-erpnext
```

The PWA assets are already inside the image (Option B.2), so no extra build step is needed in-cluster.

---

## What gets created on install (checklist)

`bench install-app stock_ops` runs `after_install`; `bench migrate` syncs DocTypes and runs `after_migrate`
(self-heal). After that the site automatically has:

**DocTypes** (module *Stock Ops*)
- [x] **Stock Ops Settings** (Single) — app configuration
- [x] **Stock Ops Menu Override** (child) — per-role menu visibility rows
- [x] **Stock Ops Employee Warehouse** (child) — per-employee warehouse list

**Custom Fields**
- [x] Material Request → `external_localid`, `stock_ops_geolocation`
- [x] Stock Entry → `external_localid`, `stock_ops_geolocation`
- [x] Stock Reconciliation → `external_localid`
- [x] Employee → **`stock_ops_warehouses`** (Table MultiSelect — limits which warehouses the employee sees)

**Roles + permissions** (existing standard role perms are preserved)
- [x] **Stock Ops User** — create / write / submit on Material Request, Stock Entry, Stock Reconciliation;
      read on Item, Bin, Warehouse, UOM, Company, Supplier, …; **no cancel/delete**; no Desk access
- [x] **Stock Ops Manager** — the above **+ cancel / delete / amend** + edit Stock Ops Settings + Desk access

**Stock Ops Settings fields** (ready to edit)
- [x] Default Language (id/en) · Flutter APK URL · **Default Company** · **Default Source Warehouse**
- [x] 13 menu-visibility toggles (Stock, Movement, Documents, Notifications, Scan, Transfer, Low Stock,
      Opname, MR, PR, Stock In/Out/Transfer)
- [x] Per-role menu override table

**Desk integration**
- [x] App Switcher (⊞) tile **Stock Ops** → `/app/stock-ops` (managers only)
- [x] **Stock Ops** Workspace (shortcuts: Open App, Settings, Stock; cards: Documents, Configuration)

**Backend**
- [x] Whitelisted API `stock_ops.api.*` (bootstrap, settings, user context, notifications, transactions, …)
- [x] VAPID keys for Web Push
- [x] On submit of Material Request / Stock Entry → in-app Notification Log entry for managers

**Not automatic — manual follow-up (see below)**
- [ ] Build the PWA bundle (`npm run build:frappe`, or the Docker overlay) so `/stock_ops` is served
- [ ] Assign **Stock Ops User / Manager** roles to users (or via a Role Profile)
- [ ] Configure **Stock Ops Settings** (language, default company/warehouse, menu visibility, APK URL)
- [ ] Restrict warehouses per employee (Employee → *Stock Ops Warehouses*) where needed
- [ ] Upload the APK and set **Flutter APK URL**

---

## Post-install configuration (all install methods)

1. **Stock Ops Settings** (`/app/stock-ops-settings`, or App Switcher ⊞ → Stock Ops):
   - **Default Language** (`id` / `en`)
   - **Flutter APK URL** — link used by the in-app *Download Android* button (blank = hidden)
   - **Menu visibility** + optional **per-role overrides**
2. **Assign roles** (`/app/user` → Roles → *Stock Ops User* / *Stock Ops Manager*, or a Role Profile).
3. *(Optional)* restrict warehouses per user: fill **Stock Ops Warehouses** on the Employee, or add a
   `User Permission` for `Warehouse`.

---

## Android app (Flutter)

A single universal APK works for every site (server is chosen from the login dropdown). Upload the APK to each
site (Desk → File) and paste its path into **Stock Ops Settings → Flutter APK URL** (e.g. `/files/StockOps.apk`).

---

## Frontend development (hot reload)

```bash
cd frontend
npm install
# .env.local (NOT committed): the dev proxy injects a token on the Node side
#   FRAPPE_URL=http://erp.localhost:8000
#   FRAPPE_API_KEY=xxxx
#   FRAPPE_API_SECRET=xxxx
npm run dev        # http://localhost:5173
```

---

## Troubleshooting

- **Install fails on Python 3.11** (`requires a different Python`): use the latest code — `requires-python`
  is now `>=3.10`. Re-run `bench get-app`.
- **Opening the *Stock Ops* Workspace shows "Not Found"**: the App Switcher tile now points to
  **`/app/stock-ops`** (the standard Frappe workspace URL). Older builds used `/desk/stock-ops`, which only
  worked where `/desk` redirects to `/app`; early v16 has no such redirect. Pull the latest, `bench migrate`
  (or `bench --site <site> clear-cache`) and `bench restart`. The workspace lives at `https://<site>/app/stock-ops`.
- **"Buka Aplikasi" / `/stock_ops` shows "Not Found"**: the **PWA bundle was not built**. Run
  `cd apps/stock_ops/frontend && npm run build:frappe` (or use the Docker overlay in `docker/Containerfile`),
  then `bench restart`. The PWA is served from `stock_ops/www/stock_ops/` + `stock_ops/public/stock_ops/`,
  which are git-ignored and must be built on the server/image.

## Notes

- Service worker / web push require **HTTPS**.
- API key/secret are used only by the dev proxy and the mobile login exchange — they are never bundled into
  the frontend.
- License: MIT.

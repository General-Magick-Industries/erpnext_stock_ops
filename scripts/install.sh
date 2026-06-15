#!/usr/bin/env bash
#
# Stock Ops — one-shot installer / updater for a Frappe v16 bench.
# Works on early v16 + Python 3.11 too. Idempotent: safe to re-run.
#
# Run as the bench user, from inside your frappe-bench directory:
#     bash apps/stock_ops/scripts/install.sh <site> [branch]
#   e.g.
#     bash apps/stock_ops/scripts/install.sh erp.globalmagicko.com
#
set -euo pipefail

SITE="${1:-}"
BRANCH="${2:-new-develop}"
REPO="https://github.com/denzizzy966/stock_ops"
APP="stock_ops"

if [ -z "$SITE" ]; then
  echo "Usage: bash apps/stock_ops/scripts/install.sh <site> [branch]"
  exit 1
fi
if [ ! -f "sites/common_site_config.json" ]; then
  echo "ERROR: run this from your frappe-bench directory (sites/ not found here)."
  exit 1
fi

echo "============================================================"
echo " Stock Ops install/update  ·  site=$SITE  branch=$BRANCH"
echo "============================================================"
echo "Python: $(python3 -V 2>&1)"
NODE_V="$(node -v 2>/dev/null || echo none)"
NODE_MAJOR="$(echo "$NODE_V" | sed 's/v//; s/\..*//')"
echo "Node:   $NODE_V"

# 1) get or update the app code -------------------------------------------------
if [ -d "apps/$APP" ]; then
  echo "==> [1/6] Updating app code ($BRANCH)"
  ( cd "apps/$APP" && git fetch origin "$BRANCH" && git checkout "$BRANCH" && git pull --ff-only origin "$BRANCH" )
else
  echo "==> [1/6] Fetching app ($BRANCH)"
  bench get-app "$APP" "$REPO" --branch "$BRANCH"
fi

# 2) install on the site (no-op if already installed) ---------------------------
if bench --site "$SITE" list-apps 2>/dev/null | grep -qw "$APP"; then
  echo "==> [2/6] $APP already installed on $SITE"
else
  echo "==> [2/6] Installing $APP on $SITE"
  bench --site "$SITE" install-app "$APP"
fi

# 3) migrate: sync DocTypes + workspace, run after_install/after_migrate --------
echo "==> [3/6] Migrating $SITE (creates fields, roles, workspace)"
bench --site "$SITE" migrate

# 4) build the PWA bundle (served at /stock_ops). Needs Node >= 20. -------------
if [ "${NODE_MAJOR:-0}" -ge 20 ]; then
  echo "==> [4/6] Building PWA frontend"
  ( cd "apps/$APP/frontend" && npm install --no-audit --no-fund && npm run build:frappe )
  bench build --app "$APP" || true
else
  echo "==> [4/6] SKIPPED PWA build — Node >= 20 required (found: $NODE_V)."
  echo "          Install Node 20+, then run:"
  echo "          cd apps/$APP/frontend && npm install && npm run build:frappe && cd - && bench build --app $APP"
fi

# 5) restart + clear cache ------------------------------------------------------
echo "==> [5/6] Restart + clear cache"
bench restart || true
bench --site "$SITE" clear-cache

# 6) verify ---------------------------------------------------------------------
echo "==> [6/6] Verify app settings endpoint"
bench --site "$SITE" execute stock_ops.api.get_app_settings || true

echo
echo "============================================================"
echo " DONE."
echo "   PWA app:    https://$SITE/stock_ops"
echo "   Workspace:  https://$SITE/app/stock-ops      (App Switcher ⊞ -> Stock Ops)"
echo "   Settings:   https://$SITE/app/stock-ops-settings"
echo
echo " Next steps:"
echo "   - Assign role 'Stock Ops User' or 'Stock Ops Manager' to users."
echo "   - Configure Stock Ops Settings (language, default company/warehouse, menus, APK URL)."
echo "   - Restrict warehouses per Employee via 'Stock Ops Warehouses' (empty = full access)."
echo "============================================================"

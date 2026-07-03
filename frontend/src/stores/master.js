import { defineStore } from 'pinia'
import { bootstrap } from '../lib/service'
import { ITEMS, WAREHOUSES, COMPANIES, UOMS, SUPPLIERS } from '../data/mock'

const LS = 'stockops.master'

function load() {
  try {
    return JSON.parse(localStorage.getItem(LS)) || {}
  } catch {
    return {}
  }
}

// Cache master data (dipakai online & offline). Fallback ke data mock bila kosong.
export const useMaster = defineStore('master', {
  state: () => {
    const s = load()
    return {
      companies: s.companies || [],
      warehouses: s.warehouses || [],
      items: s.items || [],
      uoms: s.uoms || [],
      suppliers: s.suppliers || [],
      locations: s.locations || [],
      userWarehouses: s.userWarehouses || [],
      defaults: s.defaults || null,
      menu: s.menu || {}, // visibilitas menu dari Stock Ops Settings
      caps: s.caps || {}, // kemampuan user (mis. can_cancel) — dari Role Permission
      isApprover: s.isApprover || false, // user adalah approver (leave approver) MR Purchase
      pendingApprovals: s.pendingApprovals || 0, // jumlah MR menunggu persetujuan user
      defaultLang: s.defaultLang || 'id',
      flutterApkUrl: s.flutterApkUrl || '',
      loadedAt: s.loadedAt || null,
      loading: false
    }
  },
  getters: {
    hasData: (s) => s.items.length > 0,
    // Menu tampil? default true bila belum dimuat / tak diset di server.
    menuOn: (s) => (key) => s.menu[key] !== false,
    // Boleh cancel dokumen di server? default true bila caps belum dimuat
    // (penegakan sebenarnya tetap di server; ini hanya menyembunyikan tombol).
    canCancel: (s) => s.caps.can_cancel !== false,
    isManager: (s) => s.caps.is_manager === true,
    // Item siap pakai untuk picker (normalisasi field + fallback gambar)
    itemList: (s) => (s.items.length ? s.items : ITEMS),
    warehouseNames: (s) => (s.warehouses.length ? s.warehouses.map((w) => w.name) : WAREHOUSES),
    // Gudang milik company tertentu (MR memvalidasi warehouse↔company).
    warehousesForCompany: (s) => (company) => {
      if (!s.warehouses.length) return WAREHOUSES
      const f = s.warehouses.filter((w) => !company || w.company === company)
      return (f.length ? f : s.warehouses).map((w) => w.name)
    },
    companyNames: (s) => (s.companies.length ? s.companies.map((c) => c.name) : COMPANIES),
    uomList: (s) => (s.uoms.length ? s.uoms : UOMS),
    supplierNames: (s) => (s.suppliers.length ? s.suppliers.map((x) => x.supplier) : SUPPLIERS),
    locationNames: (s) => s.locations || []
  },
  actions: {
    persist() {
      localStorage.setItem(
        LS,
        JSON.stringify({
          companies: this.companies,
          warehouses: this.warehouses,
          items: this.items,
          uoms: this.uoms,
          suppliers: this.suppliers,
          locations: this.locations,
          userWarehouses: this.userWarehouses,
          defaults: this.defaults,
          menu: this.menu,
          caps: this.caps,
          isApprover: this.isApprover,
          pendingApprovals: this.pendingApprovals,
          defaultLang: this.defaultLang,
          flutterApkUrl: this.flutterApkUrl,
          loadedAt: this.loadedAt
        })
      )
    },
    async load() {
      this.loading = true
      try {
        const b = await bootstrap()
        this.companies = b.companies || []
        this.warehouses = b.warehouses || []
        this.items = (b.items || []).map((it) => ({
          item_code: it.item_code,
          item_name: it.item_name || it.item_code,
          stock_uom: it.stock_uom || 'Nos',
          image: it.image || '',
          barcode: it.barcode || '',
          is_fixed_asset: it.is_fixed_asset ? 1 : 0
        }))
        this.uoms = b.uoms || []
        this.suppliers = b.suppliers || []
        this.locations = b.locations || []
        this.userWarehouses = b.user_warehouses || []
        this.defaults = b.defaults || null
        this.menu = b.menu || {}
        this.caps = b.caps || {}
        this.isApprover = !!b.is_approver
        this.pendingApprovals = b.pending_approvals || 0
        this.defaultLang = b.default_lang || 'id'
        this.flutterApkUrl = b.flutter_apk_url || ''
        this.loadedAt = new Date().toISOString()
        this.persist()
        // Terapkan bahasa default server (kecuali user sudah memilih manual)
        const { useApp } = await import('./app')
        useApp().applyServerLang(this.defaultLang)
        return b
      } finally {
        this.loading = false
      }
    }
  }
})

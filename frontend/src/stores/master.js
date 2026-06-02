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
      userWarehouses: s.userWarehouses || [],
      defaults: s.defaults || null,
      loadedAt: s.loadedAt || null,
      loading: false
    }
  },
  getters: {
    hasData: (s) => s.items.length > 0,
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
    supplierNames: (s) => (s.suppliers.length ? s.suppliers.map((x) => x.supplier) : SUPPLIERS)
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
          userWarehouses: this.userWarehouses,
          defaults: this.defaults,
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
          barcode: it.barcode || ''
        }))
        this.uoms = b.uoms || []
        this.suppliers = b.suppliers || []
        this.userWarehouses = b.user_warehouses || []
        this.defaults = b.defaults || null
        this.loadedAt = new Date().toISOString()
        this.persist()
        return b
      } finally {
        this.loading = false
      }
    }
  }
})

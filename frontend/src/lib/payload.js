import { DOC_TYPES } from '../data/mock'

// Ubah objek dokumen app → payload Frappe sesuai DocType.
export function buildPayload(doc) {
  const cfg = DOC_TYPES[doc.type]
  return cfg.doctype === 'Material Request' ? buildMR(doc, cfg) : buildSE(doc, cfg)
}

function clean(obj) {
  Object.keys(obj).forEach((k) => obj[k] === undefined && delete obj[k])
  return obj
}

function buildMR(doc, cfg) {
  const mrType = doc.type === 'MR' ? 'Material Transfer' : 'Purchase'
  return {
    doctype: 'Material Request',
    material_request_type: mrType,
    company: doc.company,
    transaction_date: doc.date,
    schedule_date: doc.date,
    external_localid: doc.localId,
    stock_ops_geolocation: doc.geo || undefined,
    items: doc.items.map((i) =>
      clean({
        item_code: i.item_code,
        qty: i.qty,
        uom: i.uom,
        schedule_date: doc.date,
        warehouse: doc.targetWarehouse || undefined,
        from_warehouse: cfg.source ? doc.sourceWarehouse : undefined
      })
    )
  }
}

function buildSE(doc, cfg) {
  const seType = { SE_IN: 'Material Receipt', SE_OUT: 'Material Issue', SE_TRANSFER: 'Material Transfer' }[doc.type]
  return clean({
    doctype: 'Stock Entry',
    stock_entry_type: seType,
    company: doc.company,
    posting_date: doc.date,
    external_localid: doc.localId,
    stock_ops_geolocation: doc.geo || undefined,
    from_warehouse: cfg.source ? doc.sourceWarehouse : undefined,
    to_warehouse: cfg.target ? doc.targetWarehouse : undefined,
    items: doc.items.map((i) =>
      clean({
        item_code: i.item_code,
        qty: i.qty,
        uom: i.uom,
        s_warehouse: cfg.source ? doc.sourceWarehouse : undefined,
        t_warehouse: cfg.target ? doc.targetWarehouse : undefined,
        // hindari error "valuation rate not found" untuk item tanpa nilai (testing)
        allow_zero_valuation_rate: 1
      })
    )
  })
}

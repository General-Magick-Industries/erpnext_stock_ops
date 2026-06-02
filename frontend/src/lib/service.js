import { call, uploadFile } from './api'

// Master data (sekali panggil, untuk cache offline)
export const bootstrap = () => call('stock_ops.api.get_bootstrap')

// Buat dokumen draft (idempoten via external_localid)
export const createTransaction = (payload) =>
  call('stock_ops.api.create_transaction', { data: payload }, { post: true })

// Submit dokumen (online)
export const submitTransaction = (doctype, name) =>
  call('stock_ops.api.submit_transaction', { doctype, name }, { post: true })

// Batalkan dokumen submitted
export const cancelTransaction = (doctype, name) =>
  call('stock_ops.api.cancel_transaction', { doctype, name }, { post: true })

// Dokumen terbaru dari server
export const listRecent = (company, limit = 20) =>
  call('stock_ops.api.list_recent', { company, limit })

// Ringkasan jumlah dokumen bulan ini
export const reportCounts = (company) => call('stock_ops.api.report_counts', { company })

// Saldo stok per gudang user
export const getStockBalance = (opts = {}) => {
  const p = {}
  if (opts.warehouse) p.warehouse = opts.warehouse
  if (opts.company) p.company = opts.company
  return call('stock_ops.api.get_stock_balance', p)
}

// Stock opname: lembar stok sistem + buat Stock Reconciliation
export const getOpnameSheet = (warehouse, company) =>
  call('stock_ops.api.get_opname_sheet', { warehouse, company })
export const createOpname = (warehouse, items, company, externalLocalid) =>
  call('stock_ops.api.create_opname', { warehouse, items, company, external_localid: externalLocalid }, { post: true })

// Item stok menipis (di bawah reorder level / ambang)
export const getLowStock = (company, threshold = 10) =>
  call('stock_ops.api.get_low_stock', { company, threshold })

// Bulk request beli dari item terpilih → satu Material Request (Purchase)
export const bulkPurchaseRequest = (items, company, externalLocalid) =>
  call('stock_ops.api.bulk_purchase_request', { items, company, external_localid: externalLocalid }, { post: true })

// Detail item (info + stok per gudang + mutasi)
export const getItemDetail = (itemCode, company) => call('stock_ops.api.get_item_detail', { item_code: itemCode, company })

// Resolve kode (barcode/item_code/nama) → item_code (untuk hasil scan)
export const resolveItem = (code) => call('stock_ops.api.resolve_item', { code })

// Pergerakan stok (Stock Ledger) per gudang user
export const getStockLedger = (opts = {}) => {
  const p = {}
  for (const k of ['item_code', 'warehouse', 'direction', 'from_date', 'to_date', 'company']) {
    if (opts[k]) p[k] = opts[k]
  }
  p.limit = opts.limit || 100
  return call('stock_ops.api.get_stock_ledger', p)
}

export { uploadFile }

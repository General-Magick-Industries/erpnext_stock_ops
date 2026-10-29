<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useApp } from '../stores/app'
import { useMaster } from '../stores/master'
import { useI18n } from '../lib/i18n'
import Sheet from './Sheet.vue'
import BarcodeScanner from './BarcodeScanner.vue'
import SearchInput from './SearchInput.vue'

// `warehouse` = gudang yang dipilih di form → tampilkan stok tersedia per item di gudang itu.
// Saringan pilihan item (bisa dimatikan user lewat "Tampilkan semua"):
//  - filterMode 'stock'    : hanya item ber-stok di filterWarehouse (dokumen keluar / transfer)
//  - filterMode 'defaults' : hanya item ber-Item Defaults gudang = filterWarehouse (masuk / permintaan)
//  - showAssets false      : sembunyikan fixed asset (Default per User › Tampilkan Aset)
const props = defineProps({
  warehouse: { type: String, default: '' },
  filterMode: { type: String, default: '' },
  filterWarehouse: { type: String, default: '' },
  showAssets: { type: Boolean, default: true }
})
const emit = defineEmits(['pick', 'close'])
const app = useApp()
const master = useMaster()
const { t } = useI18n()
const q = ref('')
const showScanner = ref(false)

// Aturan aset berlaku tetap (diatur admin); saringan gudang bisa dimatikan user.
const items = computed(() => master.itemList.filter((i) => props.showAssets || !i.is_fixed_asset))
const showAll = ref(false)

// Stok per item di gudang terpilih (dari cache master.stockByWh).
const loadingStock = ref(false)
async function loadStock() {
  const whs = [props.warehouse, props.filterMode === 'stock' ? props.filterWarehouse : ''].filter(Boolean)
  if (!whs.length || !app.online) return
  loadingStock.value = true
  try {
    await Promise.all([...new Set(whs)].map((w) => master.loadWarehouseStock(w)))
  } finally {
    loadingStock.value = false
  }
}
onMounted(loadStock)
watch(() => [props.warehouse, props.filterWarehouse], loadStock)
const stockMap = computed(() => (props.warehouse && master.stockByWh[props.warehouse]) || null)

// Item hasil saringan gudang. null = saringan tak berlaku (mode kosong / data stok belum ada).
const scoped = computed(() => {
  const wh = props.filterWarehouse
  if (!wh || !props.filterMode) return null
  if (props.filterMode === 'stock') {
    const m = master.stockByWh[wh]
    return m ? items.value.filter((i) => Number(m[i.item_code] || 0) > 0) : null
  }
  if (props.filterMode === 'defaults') {
    const f = items.value.filter((i) => (i.default_warehouses || []).includes(wh))
    // Belum ada Item Defaults untuk gudang ini sama sekali → jangan kosongkan picker.
    return f.length ? f : null
  }
  return null
})
const filterActive = computed(() => !showAll.value && scoped.value !== null)
const pool = computed(() => (filterActive.value ? scoped.value : items.value))
// Keterangan saringan untuk user (+ tombol Tampilkan semua / Saring lagi).
const filterNote = computed(() => {
  const wh = props.filterWarehouse
  if (!wh || !props.filterMode) return ''
  if (props.filterMode === 'defaults' && scoped.value === null) return t('picker.noDefaults', { wh })
  if (scoped.value === null) return ''
  if (showAll.value) return t('picker.showingAll')
  return t(props.filterMode === 'stock' ? 'picker.filterStock' : 'picker.filterDefaults', { wh, n: scoped.value.length })
})
function stockOf(it) {
  const v = Number((stockMap.value && stockMap.value[it.item_code]) || 0)
  return Number.isInteger(v) ? v : +v.toFixed(2)
}
const results = computed(() => {
  const s = q.value.trim().toLowerCase()
  if (!s) return pool.value.slice(0, 100)
  return pool.value
    .filter(
      (i) =>
        (i.item_name || '').toLowerCase().includes(s) ||
        (i.item_code || '').toLowerCase().includes(s) ||
        (i.barcode || '').includes(s)
    )
    .slice(0, 100)
})

function initials(it) {
  return (it.item_name || it.item_code || '?').trim().charAt(0).toUpperCase()
}

function onDetected(code) {
  showScanner.value = false
  const found = items.value.find((i) => i.barcode && i.barcode === code)
  if (found) {
    app.notify(t('toast.scan', { code, name: found.item_name }), 'success')
    emit('pick', found)
  } else {
    q.value = code // tampilkan hasil scan di pencarian untuk dicocokkan manual
    app.notify(t('scan.notFound', { code }), 'warn')
  }
}
</script>

<template>
  <Sheet :title="t('picker.title')" @close="emit('close')">
    <div class="row" style="gap: 8px; margin-bottom: 8px">
      <SearchInput v-model="q" :placeholder="t('picker.searchPlaceholder')" class="grow" />
      <button class="btn brand" style="padding: 12px 14px" @click="showScanner = true" :title="t('scan.title')"><Icon name="camera" /></button>
    </div>
    <div v-if="warehouse" class="tiny muted" style="margin: 0 4px 10px">
      {{ t('picker.stockAt', { wh: warehouse }) }}<span v-if="loadingStock"> · {{ t('common.loading') }}</span>
    </div>
    <div v-if="filterNote" class="picker-filter tiny">
      <Icon name="filter" />
      <span class="grow">{{ filterNote }}</span>
      <button v-if="scoped !== null" class="link-btn" @click="showAll = !showAll">
        {{ showAll ? t('picker.showFiltered') : t('picker.showAll') }}
      </button>
    </div>

    <div v-for="it in results" :key="it.item_code" class="list-item" @click="emit('pick', it)" style="cursor: pointer">
      <img v-if="it.image" :src="it.image" class="thumb" alt="" />
      <span v-else class="thumb" style="display: grid; place-items: center; font-weight: 700; color: var(--muted)">{{ initials(it) }}</span>
      <div class="grow" style="min-width: 0">
        <div class="truncate" style="font-weight: 600">{{ it.item_name }}</div>
        <div class="tiny muted truncate">{{ it.item_code }} · {{ it.stock_uom }}<span v-if="it.barcode"> · {{ it.barcode }}</span></div>
      </div>
      <span v-if="warehouse" class="stk-badge" :class="{ zero: stockOf(it) <= 0 }">
        {{ stockOf(it) }} <span class="tiny">{{ it.stock_uom }}</span>
      </span>
      <span style="font-size: 22px; color: var(--brand)"><Icon name="plus" /></span>
    </div>

    <div v-if="!results.length" class="empty">
      <div class="big"><Icon name="search" /></div>
      {{ filterActive ? t('picker.noMatchFiltered') : t('picker.noMatch') }}
      <div v-if="filterActive" style="margin-top: 10px">
        <button class="btn sm" @click="showAll = true">{{ t('picker.showAll') }}</button>
      </div>
    </div>

    <BarcodeScanner v-if="showScanner" @detected="onDetected" @close="showScanner = false" />
  </Sheet>
</template>

<style scoped>
.picker-filter {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 10px;
  padding: 8px 10px;
  border-radius: 10px;
  background: var(--brand-soft);
}
.picker-filter .link-btn {
  flex-shrink: 0;
  border: 0;
  background: none;
  padding: 0;
  color: var(--brand);
  font-weight: 700;
  cursor: pointer;
}
.stk-badge {
  flex-shrink: 0;
  padding: 3px 9px;
  border-radius: 999px;
  background: #dcfce7;
  color: #166534;
  font-weight: 700;
  font-size: 13px;
  white-space: nowrap;
}
.stk-badge.zero {
  background: var(--line);
  color: var(--muted);
}
.stk-badge .tiny {
  font-weight: 500;
  opacity: 0.8;
}
</style>

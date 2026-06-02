<script setup>
import { ref, computed } from 'vue'
import { useApp } from '../stores/app'
import { useMaster } from '../stores/master'
import { useI18n } from '../lib/i18n'
import Sheet from './Sheet.vue'
import BarcodeScanner from './BarcodeScanner.vue'
import SearchInput from './SearchInput.vue'

const emit = defineEmits(['pick', 'close'])
const app = useApp()
const master = useMaster()
const { t } = useI18n()
const q = ref('')
const showScanner = ref(false)

const items = computed(() => master.itemList)
const results = computed(() => {
  const s = q.value.trim().toLowerCase()
  if (!s) return items.value.slice(0, 100)
  return items.value
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
    <div class="row" style="gap: 8px; margin-bottom: 12px">
      <SearchInput v-model="q" :placeholder="t('picker.searchPlaceholder')" class="grow" />
      <button class="btn brand" style="padding: 12px 14px" @click="showScanner = true" :title="t('scan.title')">📷</button>
    </div>

    <div v-for="it in results" :key="it.item_code" class="list-item" @click="emit('pick', it)" style="cursor: pointer">
      <img v-if="it.image" :src="it.image" class="thumb" alt="" />
      <span v-else class="thumb" style="display: grid; place-items: center; font-weight: 700; color: var(--muted)">{{ initials(it) }}</span>
      <div class="grow">
        <div class="truncate" style="font-weight: 600">{{ it.item_name }}</div>
        <div class="tiny muted truncate">{{ it.item_code }} · {{ it.stock_uom }}<span v-if="it.barcode"> · {{ it.barcode }}</span></div>
      </div>
      <span style="font-size: 22px; color: var(--brand)">＋</span>
    </div>

    <div v-if="!results.length" class="empty">
      <div class="big">🔍</div>
      {{ t('picker.noMatch') }}
    </div>

    <BarcodeScanner v-if="showScanner" @detected="onDetected" @close="showScanner = false" />
  </Sheet>
</template>

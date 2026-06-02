<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApp } from '../stores/app'
import { useDocs } from '../stores/docs'
import { useMaster } from '../stores/master'
import { useI18n } from '../lib/i18n'
import AppBar from '../components/AppBar.vue'
import ItemPickerSheet from '../components/ItemPickerSheet.vue'

const route = useRoute()
const router = useRouter()
const app = useApp()
const docs = useDocs()
const master = useMaster()
const { t } = useI18n()

const company = ref(app.settings.company)
const warehouseOptions = computed(() => master.warehousesForCompany(company.value))

const form = reactive({
  item: null, // { item_code, item_name, stock_uom, image }
  from: app.settings.defaultSourceWarehouse || '',
  to: app.settings.defaultTargetWarehouse || '',
  qty: 1
})
const showPicker = ref(false)
const saving = ref(false)

onMounted(() => {
  const opts = warehouseOptions.value
  if (!opts.includes(form.from)) form.from = opts[0] || ''
  if (!opts.includes(form.to)) form.to = opts[Math.min(1, opts.length - 1)] || ''
  const code = route.query.item
  if (code) {
    const it = master.itemList.find((x) => x.item_code === code)
    if (it) form.item = { item_code: it.item_code, item_name: it.item_name, stock_uom: it.stock_uom, image: it.image }
  }
})

function pick(it) {
  form.item = { item_code: it.item_code, item_name: it.item_name, stock_uom: it.stock_uom, image: it.image }
  showPicker.value = false
}
function step(d) {
  form.qty = Math.max(0, (Number(form.qty) || 0) + d)
}

async function submit() {
  if (!form.item) return app.notify(t('qt.needItem'), 'warn')
  if (!form.qty || form.qty <= 0) return app.notify(t('qt.needQty'), 'warn')
  if (!form.from || !form.to || form.from === form.to) return app.notify(t('qt.sameWh'), 'warn')
  saving.value = true
  const doc = docs.newDraft('SE_TRANSFER')
  doc.company = company.value
  doc.sourceWarehouse = form.from
  doc.targetWarehouse = form.to
  doc.items = [
    {
      item_code: form.item.item_code,
      item_name: form.item.item_name,
      image: form.item.image,
      uom: form.item.stock_uom,
      qty: Number(form.qty)
    }
  ]
  await docs.save({ ...doc })
  saving.value = false
  router.replace(`/doc/${doc.localId}`)
}
</script>

<template>
  <AppBar :title="t('qt.title')" back />
  <div class="content">
    <div class="card">
      <!-- Item -->
      <div class="field">
        <label>{{ t('qt.item') }}</label>
        <button class="list-item" style="width: 100%; border: 0; cursor: pointer; box-shadow: none; background: var(--input-bg); border: 1px solid var(--line)" @click="showPicker = true">
          <template v-if="form.item">
            <img v-if="form.item.image" :src="form.item.image" class="thumb" alt="" />
            <span v-else class="thumb" style="display: grid; place-items: center; font-weight: 700; color: var(--muted)">{{ (form.item.item_name || '?').charAt(0) }}</span>
            <div class="grow"><div class="truncate" style="font-weight: 600">{{ form.item.item_name }}</div><div class="tiny muted">{{ form.item.item_code }}</div></div>
          </template>
          <div v-else class="grow muted">{{ t('qt.pickItem') }}</div>
          <span style="font-size: 20px; color: var(--muted)">🔎</span>
        </button>
      </div>

      <div class="field-row">
        <div class="field">
          <label>{{ t('qt.from') }}</label>
          <select v-model="form.from"><option v-for="w in warehouseOptions" :key="w">{{ w }}</option></select>
        </div>
        <div class="field">
          <label>{{ t('qt.to') }}</label>
          <select v-model="form.to"><option v-for="w in warehouseOptions" :key="w">{{ w }}</option></select>
        </div>
      </div>

      <div class="field" style="margin: 0">
        <label>{{ t('qt.qty') }}</label>
        <div class="qty-box" style="width: fit-content">
          <button @click="step(-1)">−</button>
          <input type="number" inputmode="decimal" v-model.number="form.qty" style="width: 80px" />
          <button @click="step(1)">＋</button>
        </div>
      </div>
    </div>

    <button class="btn brand block mt16" :disabled="saving" @click="submit">
      🔁 {{ saving ? '…' : t('qt.submit') }}
    </button>

    <ItemPickerSheet v-if="showPicker" @pick="pick" @close="showPicker = false" />
  </div>
</template>

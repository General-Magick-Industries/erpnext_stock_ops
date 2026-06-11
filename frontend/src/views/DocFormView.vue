<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { DOC_TYPES } from '../data/mock'
import { useApp } from '../stores/app'
import { useDocs } from '../stores/docs'
import { useMaster } from '../stores/master'
import { useI18n } from '../lib/i18n'
import { getGeolocation } from '../lib/util'
import AppBar from '../components/AppBar.vue'
import ItemPickerSheet from '../components/ItemPickerSheet.vue'
import PhotoUploader from '../components/PhotoUploader.vue'

const route = useRoute()
const router = useRouter()
const app = useApp()
const docs = useDocs()
const master = useMaster()
const { t } = useI18n()

const COMPANIES = computed(() => master.companyNames)
const SUPPLIERS = computed(() => master.supplierNames)
// Company dikunci bila berasal dari Employee user (server). Lihat get_user_context.
const companyReadOnly = computed(() => !!(master.defaults && master.defaults.company_read_only))

const typeKey = route.params.type
const cfg = DOC_TYPES[typeKey]
if (!cfg) router.replace('/create')

const doc = reactive(docs.newDraft(typeKey))

// Gudang difilter sesuai company (hindari error warehouse↔company di MR).
const warehouseOptions = computed(() => master.warehousesForCompany(doc.company))
watch(
  () => doc.company,
  () => {
    const opts = warehouseOptions.value
    if (doc.sourceWarehouse && !opts.includes(doc.sourceWarehouse)) doc.sourceWarehouse = opts[0] || ''
    if (doc.targetWarehouse && !opts.includes(doc.targetWarehouse))
      doc.targetWarehouse = opts[Math.min(1, opts.length - 1)] || ''
  }
)
const showPicker = ref(false)
const saving = ref(false)
const locating = ref(false)

async function tagLocation() {
  locating.value = true
  const g = await getGeolocation()
  locating.value = false
  if (g) {
    doc.geo = g
    app.notify('📍 ' + g, 'success')
  } else {
    app.notify(t('form.locationOff'), 'warn')
  }
}

const totalQty = computed(() => doc.items.reduce((s, i) => s + (Number(i.qty) || 0), 0))

function addItem(it) {
  const exist = doc.items.find((x) => x.item_code === it.item_code)
  if (exist) exist.qty += 1
  else
    doc.items.push({ item_code: it.item_code, item_name: it.item_name, image: it.image, uom: it.stock_uom, qty: 1 })
  showPicker.value = false
}

// Prefill item bila dibuka dari Detail Item (?item=CODE)
if (route.query.item) {
  const it = master.itemList.find((x) => x.item_code === route.query.item)
  if (it) addItem(it)
}
function step(line, d) {
  line.qty = Math.max(0, (Number(line.qty) || 0) + d)
}
function removeLine(code) {
  doc.items = doc.items.filter((i) => i.item_code !== code)
}

function valid() {
  if (!doc.items.length) return t('form.vItems')
  if (doc.items.some((i) => !i.qty || i.qty <= 0)) return t('form.vQty')
  if (cfg.source && !doc.sourceWarehouse) return t('form.vSrc')
  if (cfg.target && !doc.targetWarehouse) return t('form.vTgt')
  if (cfg.source && cfg.target && doc.sourceWarehouse === doc.targetWarehouse) return t('form.vSame')
  return null
}

async function save() {
  const err = valid()
  if (err) return app.notify(err, 'warn')
  saving.value = true
  await docs.save({ ...doc })
  saving.value = false
  router.replace(`/doc/${doc.localId}`)
}
</script>

<template>
  <AppBar :title="cfg ? t('docType.' + cfg.key) + ' · ' + t('form.newSuffix') : ''" back />
  <div class="content" v-if="cfg">
    <div class="card">
      <div class="row" style="gap: 10px; margin-bottom: 12px">
        <span class="lead-icon" :style="{ background: cfg.color }">{{ cfg.icon }}</span>
        <div class="grow">
          <div style="font-weight: 700">{{ t('docType.' + cfg.key) }}</div>
          <div class="tiny muted">{{ cfg.doctype }}</div>
        </div>
      </div>

      <div class="field">
        <label>{{ t('form.company') }}</label>
        <select v-model="doc.company" :disabled="companyReadOnly">
          <option v-for="c in COMPANIES" :key="c">{{ c }}</option>
        </select>
        <div v-if="companyReadOnly" class="tiny muted" style="margin-top: 4px">{{ t('form.companyFromAccount') }}</div>
      </div>

      <div class="field">
        <label>{{ t('form.date') }}</label>
        <input type="date" v-model="doc.date" />
      </div>

      <div v-if="cfg.supplier" class="field">
        <label>{{ t('form.supplier') }} ({{ t('common.optional') }})</label>
        <select v-model="doc.supplier">
          <option value="">—</option>
          <option v-for="s in SUPPLIERS" :key="s">{{ s }}</option>
        </select>
      </div>

      <div class="field-row">
        <div v-if="cfg.source" class="field">
          <label>{{ t('form.sourceWh') }}</label>
          <select v-model="doc.sourceWarehouse">
            <option v-for="w in warehouseOptions" :key="w">{{ w }}</option>
          </select>
        </div>
        <div v-if="cfg.target" class="field">
          <label>{{ t('form.targetWh') }}</label>
          <select v-model="doc.targetWarehouse">
            <option v-for="w in warehouseOptions" :key="w">{{ w }}</option>
          </select>
        </div>
      </div>
    </div>

    <div class="card mt12">
      <div class="row between">
        <div style="font-weight: 700">{{ t('common.items') }} ({{ doc.items.length }})</div>
        <button class="btn brand sm" @click="showPicker = true">＋ {{ t('common.add') }}</button>
      </div>

      <div v-if="!doc.items.length" class="empty" style="padding: 26px">
        <div class="big">🧺</div>
        {{ t('form.noItems') }}
      </div>

      <div v-for="line in doc.items" :key="line.item_code" class="item-line">
        <img v-if="line.image" :src="line.image" class="thumb" alt="" />
        <span v-else class="thumb" style="display: grid; place-items: center; font-weight: 700; color: var(--muted)">
          {{ (line.item_name || '?').charAt(0).toUpperCase() }}
        </span>
        <div class="grow" style="min-width: 0">
          <div class="truncate" style="font-weight: 600">{{ line.item_name }}</div>
          <div class="tiny muted">{{ line.item_code }} · {{ line.uom }}</div>
        </div>
        <div class="qty-box">
          <button @click="step(line, -1)">−</button>
          <input type="number" inputmode="decimal" v-model.number="line.qty" />
          <button @click="step(line, 1)">＋</button>
        </div>
        <button class="btn sm danger" style="padding: 8px 10px" @click="removeLine(line.item_code)">🗑</button>
      </div>

      <div v-if="doc.items.length" class="row between mt12" style="font-weight: 700">
        <span class="muted small">{{ t('form.totalQty') }}</span>
        <span>{{ totalQty }}</span>
      </div>
    </div>

    <div class="card mt12">
      <div style="font-weight: 700; margin-bottom: 10px">{{ t('form.photos') }}</div>
      <PhotoUploader v-model="doc.photos" :local-id="doc.localId" />
    </div>

    <div class="card mt12">
      <div class="field" style="margin: 0">
        <label>{{ t('common.note') }}</label>
        <textarea v-model="doc.remark" rows="2" :placeholder="t('form.notePlaceholder')"></textarea>
      </div>
    </div>

    <div class="card mt12">
      <div class="row between">
        <div style="min-width: 0">
          <div style="font-weight: 700">📍 {{ t('form.location') }}</div>
          <div v-if="doc.geo" class="tiny muted truncate">
            {{ doc.geo }} ·
            <a :href="`https://maps.google.com/?q=${doc.geo}`" target="_blank" style="color: var(--brand)">{{ t('form.viewMap') }}</a>
          </div>
          <div v-else class="tiny muted">—</div>
        </div>
        <button class="btn sm" :class="doc.geo ? '' : 'brand'" :disabled="locating" @click="tagLocation">
          {{ locating ? t('form.locating') : t('form.tagLocation') }}
        </button>
      </div>
    </div>

    <div v-if="!app.online" class="banner-offline mt12">{{ t('form.offlineHint') }}</div>

    <button class="btn brand block mt16" :disabled="saving" @click="save">
      {{ saving ? t('common.saving') : app.online ? t('form.saveSync') : t('form.saveOutbox') }}
    </button>
    <div style="height: 8px"></div>

    <ItemPickerSheet v-if="showPicker" @pick="addItem" @close="showPicker = false" />
  </div>
</template>

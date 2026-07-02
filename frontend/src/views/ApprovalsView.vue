<script setup>
import { ref, computed, onMounted } from 'vue'
import { useApp } from '../stores/app'
import { useMaster } from '../stores/master'
import { useI18n } from '../lib/i18n'
import { listPendingApprovals, getWorkflowTransitions, applyWorkflowAction, getApprovalDetail } from '../lib/service'
import AppBar from '../components/AppBar.vue'
import Sheet from '../components/Sheet.vue'
import SearchInput from '../components/SearchInput.vue'

const app = useApp()
const master = useMaster()
const { t } = useI18n()
const loading = ref(false)
const rows = ref([])
const q = ref('')
const companyFilter = ref('ALL')
const busy = ref('')

// Detail sheet
const open = ref(false)
const detail = ref(null)
const transitions = ref([])
const loadingDetail = ref(false)

const isReject = (a) => /reject|tolak/i.test(a)
const actionLabel = (a) => (isReject(a) ? t('approval.reject') : /approve|setuju/i.test(a) ? t('approval.approve') : a)

const companies = computed(() => [...new Set(rows.value.map((r) => r.company).filter(Boolean))])
const filtered = computed(() => {
  const term = q.value.trim().toLowerCase()
  return rows.value.filter((r) => {
    if (companyFilter.value !== 'ALL' && r.company !== companyFilter.value) return false
    if (term && !(`${r.name} ${r.owner}`.toLowerCase().includes(term))) return false
    return true
  })
})

async function load() {
  loading.value = true
  try {
    rows.value = (await listPendingApprovals()) || []
    master.pendingApprovals = rows.value.length
  } catch (e) {
    app.notify(e && e.message ? e.message : String(e), 'error')
    rows.value = []
  } finally {
    loading.value = false
  }
}
onMounted(load)

async function openDetail(row) {
  open.value = true
  loadingDetail.value = true
  detail.value = { name: row.name, owner: row.owner, material_request_type: row.material_request_type, company: row.company, items: [] }
  transitions.value = []
  try {
    const [d, tr] = await Promise.all([
      getApprovalDetail(row.name),
      getWorkflowTransitions('Material Request', row.name)
    ])
    detail.value = d
    transitions.value = tr || []
  } catch (e) {
    app.notify(e && e.message ? e.message : String(e), 'error')
  } finally {
    loadingDetail.value = false
  }
}

async function act(action) {
  const name = detail.value.name
  const note = isReject(action) ? window.prompt(t('approval.note')) || '' : ''
  busy.value = name
  try {
    const res = await applyWorkflowAction('Material Request', name, action, note)
    app.notify(t('approval.applied', { name, state: res.workflow_state || '' }), 'success')
    rows.value = rows.value.filter((r) => r.name !== name)
    master.pendingApprovals = Math.max(0, master.pendingApprovals - 1)
    open.value = false
  } catch (e) {
    app.notify(e && e.message ? e.message : String(e), 'error')
  } finally {
    busy.value = ''
  }
}
const totalQty = computed(() => (detail.value?.items || []).reduce((s, i) => s + (Number(i.qty) || 0), 0))
</script>

<template>
  <AppBar :title="t('approval.title')" back />
  <div class="content">
    <div v-if="rows.length" class="row" style="gap: 8px; margin-bottom: 8px">
      <SearchInput v-model="q" :placeholder="t('approval.search')" class="grow" />
      <button class="btn sm" :disabled="loading" @click="load">🔄</button>
    </div>
    <div v-if="companies.length > 1" class="chips" style="margin-bottom: 8px">
      <button class="chip" :class="{ active: companyFilter === 'ALL' }" @click="companyFilter = 'ALL'">{{ t('common.all') }}</button>
      <button v-for="c in companies" :key="c" class="chip" :class="{ active: companyFilter === c }" @click="companyFilter = c">{{ c }}</button>
    </div>

    <div v-if="loading" class="empty"><div class="big">⏳</div>{{ t('common.loading') }}</div>
    <div v-else-if="!rows.length" class="empty"><div class="big">✅</div>{{ t('approval.none') }}</div>
    <div v-else-if="!filtered.length" class="empty"><div class="big">🔎</div>{{ t('list.empty') }}</div>

    <div
      v-for="row in filtered"
      :key="row.name"
      class="list-item mt12"
      style="cursor: pointer"
      @click="openDetail(row)"
    >
      <span class="lead-icon" style="background: #b45309">📝</span>
      <div class="grow" style="min-width: 0">
        <div class="truncate" style="font-weight: 700">{{ row.name }}</div>
        <div class="tiny muted truncate">{{ row.material_request_type }} · {{ row.owner }} · {{ row.item_count }} {{ t('common.items') }} · {{ row.transaction_date }}</div>
      </div>
      <span style="font-size: 22px; color: var(--brand)">›</span>
    </div>

    <Sheet v-if="open" :title="t('approval.reviewTitle')" @close="open = false">
      <div v-if="loadingDetail" class="empty"><div class="big">⏳</div>{{ t('common.loading') }}</div>
      <template v-else-if="detail">
        <div class="card">
          <div style="font-weight: 800">{{ detail.name }}</div>
          <div class="tiny muted" style="margin-top: 2px">
            {{ detail.material_request_type }} · {{ detail.company }}
          </div>
          <div class="mt8" style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px">
            <div><div class="tiny muted">{{ t('approval.requester') }}</div><div class="small truncate">{{ detail.owner }}</div></div>
            <div><div class="tiny muted">{{ t('form.date') }}</div><div class="small">{{ detail.transaction_date }}</div></div>
          </div>
        </div>

        <div class="card mt12">
          <div class="row between" style="margin-bottom: 6px">
            <div style="font-weight: 700">{{ t('common.items') }} ({{ detail.items.length }})</div>
            <div class="small muted">{{ t('common.total') }}: <b>{{ totalQty }}</b></div>
          </div>
          <div v-for="(line, i) in detail.items" :key="i" class="item-line">
            <span class="thumb" style="display: grid; place-items: center; font-weight: 700; color: var(--muted)">
              {{ (line.item_name || '?').charAt(0).toUpperCase() }}
            </span>
            <div class="grow" style="min-width: 0">
              <div class="truncate" style="font-weight: 600">{{ line.item_name || line.item_code }}</div>
              <div class="tiny muted truncate">{{ line.item_code }} · {{ line.warehouse || '—' }}</div>
            </div>
            <div style="font-weight: 700">{{ line.qty }} <span class="tiny muted">{{ line.uom }}</span></div>
          </div>
        </div>

        <div class="row" style="gap: 8px; margin-top: 14px">
          <button
            v-for="tr in transitions"
            :key="tr.action"
            class="btn grow"
            :class="isReject(tr.action) ? 'danger' : 'ok'"
            :disabled="busy === detail.name"
            @click="act(tr.action)"
          >
            {{ actionLabel(tr.action) }}
          </button>
          <div v-if="!transitions.length" class="tiny muted">—</div>
        </div>
      </template>
    </Sheet>
  </div>
</template>

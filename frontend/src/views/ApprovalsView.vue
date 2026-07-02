<script setup>
import { ref, onMounted } from 'vue'
import { useApp } from '../stores/app'
import { useMaster } from '../stores/master'
import { useI18n } from '../lib/i18n'
import { listPendingApprovals, getWorkflowTransitions, applyWorkflowAction } from '../lib/service'
import AppBar from '../components/AppBar.vue'

const app = useApp()
const master = useMaster()
const { t } = useI18n()
const loading = ref(false)
const rows = ref([])
const busy = ref('')

// Aksi apa yang "menolak" → tombol merah + minta catatan.
const isReject = (action) => /reject|tolak/i.test(action)
const actionLabel = (action) => (isReject(action) ? t('approval.reject') : /approve|setuju/i.test(action) ? t('approval.approve') : action)

async function load() {
  loading.value = true
  try {
    const list = (await listPendingApprovals()) || []
    // Ambil transition yang tersedia per dokumen (mengikuti Workflow server — seperti Desk).
    for (const r of list) {
      try {
        r.transitions = (await getWorkflowTransitions('Material Request', r.name)) || []
      } catch {
        r.transitions = []
      }
    }
    rows.value = list
    master.pendingApprovals = list.length
  } catch (e) {
    app.notify(e && e.message ? e.message : String(e), 'error')
    rows.value = []
  } finally {
    loading.value = false
  }
}
onMounted(load)

async function act(row, action) {
  const note = isReject(action) ? window.prompt(t('approval.note')) || '' : ''
  busy.value = row.name
  try {
    const res = await applyWorkflowAction('Material Request', row.name, action, note)
    app.notify(t('approval.applied', { name: row.name, state: res.workflow_state || '' }), 'success')
    rows.value = rows.value.filter((r) => r.name !== row.name)
    master.pendingApprovals = Math.max(0, master.pendingApprovals - 1)
  } catch (e) {
    app.notify(e && e.message ? e.message : String(e), 'error')
  } finally {
    busy.value = ''
  }
}
</script>

<template>
  <AppBar :title="t('approval.title')" back />
  <div class="content">
    <div v-if="loading" class="empty"><div class="big">⏳</div>{{ t('common.loading') }}</div>
    <div v-else-if="!rows.length" class="empty"><div class="big">✅</div>{{ t('approval.none') }}</div>

    <div v-for="row in rows" :key="row.name" class="card mt12">
      <div class="row" style="gap: 10px">
        <span class="lead-icon" style="background: #b45309">📝</span>
        <div class="grow" style="min-width: 0">
          <div class="truncate" style="font-weight: 700">{{ row.name }}</div>
          <div class="tiny muted truncate">
            {{ row.material_request_type }} · {{ row.owner }} · {{ row.item_count }} {{ t('common.items') }} · {{ row.transaction_date }}
          </div>
        </div>
      </div>
      <div v-if="row.transitions && row.transitions.length" class="row" style="gap: 8px; margin-top: 10px">
        <button
          v-for="tr in row.transitions"
          :key="tr.action"
          class="btn grow"
          :class="isReject(tr.action) ? 'danger' : 'ok'"
          :disabled="busy === row.name"
          @click="act(row, tr.action)"
        >
          {{ actionLabel(tr.action) }}
        </button>
      </div>
      <div v-else class="tiny muted" style="margin-top: 8px">—</div>
    </div>
  </div>
</template>

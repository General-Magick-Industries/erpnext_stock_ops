<script setup>
import { ref, computed, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from '../lib/i18n'

// Searchable (select2-style) picker. A plain <select> can't surface all 67
// warehouses comfortably; this shows ALL options in a scrollable, filterable panel.
const props = defineProps({
  modelValue: { type: String, default: '' },
  options: { type: Array, default: () => [] },
  placeholder: { type: String, default: '—' },
  disabled: { type: Boolean, default: false }
})
const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()

const open = ref(false)
const q = ref('')
const root = ref(null)
const searchEl = ref(null)

const filtered = computed(() => {
  const s = q.value.trim().toLowerCase()
  if (!s) return props.options
  return props.options.filter((o) => String(o).toLowerCase().includes(s))
})

function toggle() {
  if (props.disabled) return
  open.value = !open.value
  if (open.value) {
    q.value = ''
    nextTick(() => searchEl.value && searchEl.value.focus())
  }
}
function pick(o) {
  emit('update:modelValue', o)
  open.value = false
}
function onDocClick(e) {
  if (root.value && !root.value.contains(e.target)) open.value = false
}
onMounted(() => document.addEventListener('click', onDocClick, true))
onBeforeUnmount(() => document.removeEventListener('click', onDocClick, true))
</script>

<template>
  <div class="wh-select" ref="root">
    <button type="button" class="wh-control" :class="{ disabled }" :disabled="disabled" @click="toggle">
      <span class="wh-value" :class="{ ph: !modelValue }">{{ modelValue || placeholder }}</span>
      <span class="wh-caret">▾</span>
    </button>
    <div v-if="open" class="wh-panel">
      <input
        ref="searchEl"
        v-model="q"
        class="wh-search"
        type="text"
        :placeholder="t('form.whSearch')"
        @keydown.esc.prevent="open = false"
      />
      <div class="wh-list">
        <button
          v-for="o in filtered"
          :key="o"
          type="button"
          class="wh-opt"
          :class="{ active: o === modelValue }"
          @click="pick(o)"
        >
          {{ o }}
        </button>
        <div v-if="!filtered.length" class="wh-empty">{{ t('form.whEmpty') }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.wh-select { position: relative; }
.wh-control {
  width: 100%; display: flex; align-items: center; gap: 8px;
  border: 1px solid var(--line); background: var(--input-bg); color: var(--ink);
  border-radius: 12px; padding: 12px 14px; font-size: 16px; text-align: left; cursor: pointer;
}
.wh-control.disabled { opacity: 0.6; cursor: not-allowed; }
.wh-value { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.wh-value.ph { color: var(--muted); }
.wh-caret { color: var(--muted); font-size: 12px; flex: none; }
.wh-panel {
  position: absolute; z-index: 50; top: calc(100% + 4px); left: 0; right: 0;
  background: var(--card); border: 1px solid var(--line); border-radius: 12px;
  box-shadow: var(--shadow); padding: 8px; overflow: hidden;
}
.wh-search {
  width: 100%; border: 1px solid var(--line); background: var(--input-bg); color: var(--ink);
  border-radius: 10px; padding: 10px 12px; font-size: 15px; margin-bottom: 6px;
}
.wh-search:focus { outline: 2px solid var(--brand); border-color: transparent; }
.wh-list { max-height: 240px; overflow-y: auto; -webkit-overflow-scrolling: touch; }
.wh-opt {
  display: block; width: 100%; text-align: left; border: 0; background: transparent; color: var(--ink);
  padding: 11px 10px; border-radius: 8px; font-size: 15px; cursor: pointer;
}
.wh-opt:hover { background: var(--input-bg); }
.wh-opt.active { background: var(--brand); color: var(--brand-ink, #fff); font-weight: 600; }
.wh-empty { padding: 14px 10px; color: var(--muted); font-size: 14px; text-align: center; }
</style>

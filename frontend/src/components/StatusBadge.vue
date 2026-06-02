<script setup>
import { useI18n } from '../lib/i18n'
defineProps({ status: String, submitted: Boolean })
const { t } = useI18n()
const cls = {
  pending: 's-pending', syncing: 's-syncing', synced: 's-synced', error: 's-error', draft: 's-synced'
}
</script>

<template>
  <span v-if="submitted" class="badge-status s-submitted">{{ t('status.submitted') }}</span>
  <span v-else class="badge-status" :class="cls[status] || 's-pending'">
    {{ t('status.' + (status || 'pending')) }}
  </span>
</template>

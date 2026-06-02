<script setup>
import { useI18n } from '../lib/i18n'
defineProps({ title: String })
const emit = defineEmits(['close'])
const { t } = useI18n()
</script>

<template>
  <div class="sheet-mask" @click.self="emit('close')">
    <div class="sheet">
      <div class="grab"></div>
      <div class="sheet-head">
        <div class="title">{{ title }}</div>
        <button class="btn sm" @click="emit('close')">{{ t('common.close') }}</button>
      </div>
      <div class="sheet-body">
        <slot />
      </div>
    </div>
  </div>
</template>

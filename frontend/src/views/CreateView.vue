<script setup>
import { useRouter } from 'vue-router'
import { DOC_TYPE_LIST } from '../data/mock'
import { useI18n } from '../lib/i18n'
import AppBar from '../components/AppBar.vue'

const router = useRouter()
const { t } = useI18n()
const mrTypes = DOC_TYPE_LIST.filter((x) => x.doctype === 'Material Request')
const seTypes = DOC_TYPE_LIST.filter((x) => x.doctype === 'Stock Entry')
</script>

<template>
  <AppBar :title="t('create.title')" />
  <div class="content">
    <div class="section-title">{{ t('docType.groupMR') }}</div>
    <button
      v-for="ty in mrTypes"
      :key="ty.key"
      class="list-item"
      style="width: 100%; text-align: left; border: 0; cursor: pointer"
      @click="router.push(`/form/${ty.key}`)"
    >
      <span class="lead-icon" :style="{ background: ty.color }">{{ ty.icon }}</span>
      <div class="grow">
        <div style="font-weight: 700">{{ t('docType.' + ty.key) }}</div>
        <div class="tiny muted">{{ ty.doctype }} · {{ ty.meta }}</div>
      </div>
      <span style="font-size: 22px; color: var(--muted)">›</span>
    </button>

    <div class="section-title">{{ t('docType.groupSE') }}</div>
    <button
      v-for="ty in seTypes"
      :key="ty.key"
      class="list-item"
      style="width: 100%; text-align: left; border: 0; cursor: pointer"
      @click="router.push(`/form/${ty.key}`)"
    >
      <span class="lead-icon" :style="{ background: ty.color }">{{ ty.icon }}</span>
      <div class="grow">
        <div style="font-weight: 700">{{ t('docType.' + ty.key) }}</div>
        <div class="tiny muted">{{ ty.doctype }} · {{ ty.meta }}</div>
      </div>
      <span style="font-size: 22px; color: var(--muted)">›</span>
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useDocs } from '../stores/docs'
import { useApp } from '../stores/app'
import { useMaster } from '../stores/master'
import { useI18n } from '../lib/i18n'

const docs = useDocs()
const app = useApp()
const master = useMaster()
const { t } = useI18n()
const pending = computed(() => docs.pendingCount)
const isV2 = computed(() => app.settings.design === 'v2')
const showBalance = computed(() => master.menuOn('stock_balance'))
const showMovement = computed(() => master.menuOn('movement'))
const showDocs = computed(() => master.menuOn('documents'))
const showCreate = computed(() => ['mr', 'pr', 'se_in', 'se_out', 'se_transfer'].some((k) => master.menuOn(k)))
</script>

<template>
  <!-- ===== Desain v2: 4 tab + FAB tengah ===== -->
  <nav v-if="isV2" class="tabbar tabbar-v2">
    <router-link to="/" :class="{ active: $route.name === 'home' }">
      <span class="ic">🏠</span><span class="lbl">{{ t('nav.home') }}</span>
    </router-link>
    <router-link v-if="showBalance" to="/balance" :class="{ active: $route.name === 'balance' }">
      <span class="ic">🏬</span><span class="lbl">{{ t('nav.balance') }}</span>
    </router-link>
    <router-link v-if="showCreate" to="/create" class="navfab" aria-label="Buat">
      <span class="fabbtn">＋</span>
    </router-link>
    <router-link v-if="showMovement" to="/movement" :class="{ active: $route.name === 'movement' }">
      <span class="ic">📈</span><span class="lbl">{{ t('nav.movement') }}</span>
    </router-link>
    <router-link to="/settings" :class="{ active: $route.name === 'settings' || $route.name === 'sync' || $route.name === 'reports' }">
      <span class="ic">⚙️</span><span class="lbl">{{ t('nav.settings') }}</span>
      <span v-if="pending" class="badge">{{ pending }}</span>
    </router-link>
  </nav>

  <!-- ===== Klasik / A / B: 6 tab ===== -->
  <nav v-else class="tabbar">
    <router-link to="/" :class="{ active: $route.name === 'home' }">
      <span class="ic">🏠</span><span class="lbl">{{ t('nav.home') }}</span>
    </router-link>
    <router-link v-if="showBalance" to="/balance" :class="{ active: $route.name === 'balance' }">
      <span class="ic">🏬</span><span class="lbl">{{ t('nav.balance') }}</span>
    </router-link>
    <router-link v-if="showMovement" to="/movement" :class="{ active: $route.name === 'movement' }">
      <span class="ic">📈</span><span class="lbl">{{ t('nav.movement') }}</span>
    </router-link>
    <router-link v-if="showCreate" to="/create" :class="{ active: $route.name === 'create' }">
      <span class="ic">➕</span><span class="lbl">{{ t('nav.create') }}</span>
    </router-link>
    <router-link v-if="showDocs" to="/docs" :class="{ active: $route.name === 'docs' }">
      <span class="ic">📋</span><span class="lbl">{{ t('nav.list') }}</span>
    </router-link>
    <router-link to="/settings" :class="{ active: $route.name === 'settings' || $route.name === 'sync' || $route.name === 'reports' }">
      <span class="ic">⚙️</span><span class="lbl">{{ t('nav.settings') }}</span>
      <span v-if="pending" class="badge">{{ pending }}</span>
    </router-link>
  </nav>
</template>

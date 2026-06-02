<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useApp } from '../stores/app'
import { useMaster } from '../stores/master'
import { useI18n } from '../lib/i18n'

const app = useApp()
const master = useMaster()
const router = useRouter()
const { t } = useI18n()
const email = ref('demo@globalmagicko.com')
const password = ref('demo')
const loading = ref(false)

async function doLogin() {
  loading.value = true
  try {
    // P1: auth via token proxy → bootstrap memverifikasi koneksi & mengambil master.
    const b = await master.load()
    app.setUser({
      email: email.value || (b.user && b.user.name) || 'user',
      name: (b.user && b.user.full_name) || (email.value || 'user').split('@')[0]
    })
    app.reconcileDefaults()
    app.notify(t('toast.loginOk'), 'success')
    router.push('/')
  } catch (e) {
    app.notify(e && e.message ? e.message : 'Gagal terhubung ke server', 'error')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-wrap">
    <img class="login-logo" src="/rmi-logo.png" alt="Real Magick Indonesia" style="background: rgba(255,255,255,.92); border-radius: 18px; padding: 14px" />
    <h1 style="text-align: center; margin: 0 0 4px">Stock Ops</h1>
    <p style="text-align: center; opacity: 0.85; margin: 0 0 22px; font-size: 14px">{{ t('login.subtitle') }}</p>

    <div class="login-card">
      <div class="field">
        <label>{{ t('login.email') }}</label>
        <input v-model="email" type="email" placeholder="email@perusahaan.com" />
      </div>
      <div class="field">
        <label>{{ t('login.password') }}</label>
        <input v-model="password" type="password" placeholder="••••••" @keyup.enter="doLogin" />
      </div>
      <button class="btn brand block" :disabled="loading" @click="doLogin">
        {{ loading ? '…' : t('login.signIn') }}
      </button>
      <p class="tiny muted mt12" style="text-align: center">{{ t('login.mockNote') }}</p>
    </div>
  </div>
</template>

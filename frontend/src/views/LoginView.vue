<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useApp } from '../stores/app'
import { useMaster } from '../stores/master'
import { useI18n } from '../lib/i18n'
import { isNative, getServerUrl } from '../lib/platform'
import { nativeLogin } from '../lib/service'

const app = useApp()
const master = useMaster()
const router = useRouter()
const { t } = useI18n()

const native = isNative()
const serverUrl = ref(getServerUrl() || 'https://erp.halosocia.my.id')
const email = ref(native ? '' : 'demo@globalmagicko.com')
const password = ref(native ? '' : 'demo')
const loading = ref(false)

async function doLogin() {
  loading.value = true
  try {
    let b
    if (native) {
      // App: login user/password → token → simpan, lalu ambil master pakai token.
      const m = await nativeLogin(serverUrl.value, email.value, password.value)
      b = await master.load()
      app.setUser({ email: m.user, name: m.full_name || m.user })
    } else {
      // Web (di-serve bench / proxy dev): sesi/cookie atau token proxy.
      b = await master.load()
      app.setUser({
        email: email.value || (b.user && b.user.name) || 'user',
        name: (b.user && b.user.full_name) || (email.value || 'user').split('@')[0]
      })
    }
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
      <div v-if="native" class="field">
        <label>{{ t('login.server') }}</label>
        <input v-model="serverUrl" type="url" inputmode="url" autocapitalize="off" placeholder="https://erp.perusahaan.com" />
      </div>
      <div class="field">
        <label>{{ native ? t('login.userId') : t('login.email') }}</label>
        <input v-model="email" type="text" autocapitalize="off" autocomplete="username" placeholder="email / username" />
      </div>
      <div class="field">
        <label>{{ t('login.password') }}</label>
        <input v-model="password" type="password" autocomplete="current-password" placeholder="••••••" @keyup.enter="doLogin" />
      </div>
      <button class="btn brand block" :disabled="loading" @click="doLogin">
        {{ loading ? '…' : t('login.signIn') }}
      </button>
      <p v-if="!native" class="tiny muted mt12" style="text-align: center">{{ t('login.mockNote') }}</p>
      <p v-else class="tiny muted mt12" style="text-align: center">{{ t('login.nativeNote') }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { BrowserMultiFormatReader } from '@zxing/browser'
import { useI18n } from '../lib/i18n'

const emit = defineEmits(['detected', 'close'])
const { t } = useI18n()
const video = ref(null)
const error = ref('')
let controls = null
let done = false

onMounted(async () => {
  try {
    const reader = new BrowserMultiFormatReader()
    controls = await reader.decodeFromConstraints(
      { video: { facingMode: { ideal: 'environment' } } },
      video.value,
      (result) => {
        if (result && !done) {
          done = true
          emit('detected', result.getText())
          stop()
        }
      }
    )
  } catch (e) {
    error.value = (e && e.message) || t('scan.camFail')
  }
})

function stop() {
  try {
    controls && controls.stop()
  } catch {
    /* noop */
  }
}
onBeforeUnmount(stop)
</script>

<template>
  <div class="scanner-mask">
    <div class="scanner-top">
      <span style="font-weight: 700">{{ t('scan.title') }}</span>
      <button class="btn sm" @click="emit('close')">{{ t('common.close') }}</button>
    </div>
    <div class="scanner-stage">
      <video ref="video" class="scanner-video" autoplay muted playsinline></video>
      <div v-if="!error" class="scanner-frame"></div>
    </div>
    <p class="scanner-hint">{{ error || t('scan.hint') }}</p>
  </div>
</template>

<style scoped>
.scanner-mask {
  position: fixed; inset: 0; z-index: 70; background: #000; color: #fff;
  display: flex; flex-direction: column;
}
.scanner-top {
  display: flex; align-items: center; justify-content: space-between;
  padding: calc(env(safe-area-inset-top, 0px) + 12px) 14px 12px; background: rgba(0, 0, 0, 0.6);
}
.scanner-stage { flex: 1; position: relative; overflow: hidden; }
.scanner-video { width: 100%; height: 100%; object-fit: cover; }
.scanner-frame {
  position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
  width: 70%; max-width: 280px; aspect-ratio: 1.4 / 1;
  border: 3px solid rgba(255, 255, 255, 0.9); border-radius: 14px;
  box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.35);
}
.scanner-hint { text-align: center; padding: 14px 16px calc(env(safe-area-inset-bottom, 0px) + 16px); margin: 0; font-size: 14px; opacity: 0.9; }
</style>

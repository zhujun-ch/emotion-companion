<template><IslandSections v-if="ready && !redirecting" ref="sections" :initial-mode="initialMode" /></template>

<script setup>
import { ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import IslandSections from './IslandSections.vue'

const sections = ref(null)
const initialMode = ref('diary')
const ready = ref(false)
const redirecting = ref(false)
let firstShow = true
onLoad(options => {
  const mode = options?.mode
  const targetMode = ['board', 'diary', 'treehole'].includes(mode) ? mode : 'diary'
  initialMode.value = targetMode
  redirecting.value = true
  const targetUrl = `/pages/index/index?mode=${targetMode}`
  uni.redirectTo({
    url: targetUrl,
    fail: () => uni.reLaunch({
      url: targetUrl,
      fail: () => { redirecting.value = false; ready.value = true },
    }),
  })
})
onShow(() => {
  if (firstShow) {
    firstShow = false
    return
  }
  sections.value?.refresh()
})
</script>

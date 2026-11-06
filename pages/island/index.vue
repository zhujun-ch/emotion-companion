<template><IslandSections v-if="!redirecting" ref="sections" :initial-mode="initialMode" /></template>

<script setup>
import { ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import IslandSections from './IslandSections.vue'

const sections = ref(null)
const initialMode = ref('diary')
const redirecting = ref(false)
onLoad(options => {
  const mode = options?.mode
  initialMode.value = mode
  if (mode === 'board' || mode === 'diary') {
    redirecting.value = true
    uni.redirectTo({ url: `/pages/index/index?mode=${mode}`, fail: () => { redirecting.value = false } })
  }
})
onShow(() => sections.value?.refresh())
</script>

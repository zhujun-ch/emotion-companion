<template><ConversationWorkspace ref="workspace" /></template>

<script setup>
import { ref } from 'vue'
import { onReady } from '@dcloudio/uni-app'
import ConversationWorkspace from './ConversationWorkspace.vue'

const workspace = ref(null)
onReady(() => workspace.value?.focusComposer())
</script>

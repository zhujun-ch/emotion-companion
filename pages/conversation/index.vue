<template><ConversationWorkspace ref="workspace" /></template>

<script setup>
import { ref } from 'vue'
import { onReady, onShow } from '@dcloudio/uni-app'
import { useConversations } from '../../composables/useConversations'
import ConversationWorkspace from './ConversationWorkspace.vue'

const workspace = ref(null)
const { initialize } = useConversations()
onShow(initialize)
onReady(() => workspace.value?.focusComposer())
</script>

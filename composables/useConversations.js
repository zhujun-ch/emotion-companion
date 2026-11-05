import { ref, computed, nextTick } from 'vue'

const API = 'http://127.0.0.1:5000'
const USER_KEY = 'xinyu-local-user'
const SESSION_KEY = 'xinyu-active-session'
let userId = uni.getStorageSync(USER_KEY)
if (!userId) {
  userId = `local_${Date.now().toString(36)}_${Math.random().toString(36).slice(2)}`
  uni.setStorageSync(USER_KEY, userId)
}
const activeSessionId = ref(uni.getStorageSync(SESSION_KEY) || '')
const sessions = ref([])
const messages = ref([])
const inputText = ref('')
const isLoading = ref(false)
const isInitializing = ref(false)
const error = ref('')
const scrollTop = ref(0)
const scrollAnchor = ref('')
let initialization
const activeTitle = computed(() => sessions.value.find(s => s.id === activeSessionId.value)?.title || '新的倾诉')
const turnCount = computed(() => messages.value.filter(m => m.role === 'ai' && !m.failed).length)

function api(path, method = 'GET', data = {}) {
  return new Promise((resolve, reject) => {
    uni.request({
      url: API + path, method, data: { ...data, user_id: userId }, timeout: 180000,
      success: res => res.statusCode >= 200 && res.statusCode < 300 && res.data.status === 'success'
        ? resolve(res.data) : reject(new Error(res.data?.msg || '请求失败，请稍后重试。')),
      fail: () => reject(new Error('连接没有成功，请检查本地服务后重试。')),
    })
  })
}
function rememberSession(id) {
  activeSessionId.value = id
  uni.setStorageSync(SESSION_KEY, id)
}
async function refreshSessions() {
  sessions.value = (await api('/api/sessions')).sessions
}
async function scrollToBottom() {
  scrollAnchor.value = ''
  await nextTick()
  scrollTop.value += 100000
  scrollAnchor.value = 'chat-bottom'
}
async function loadSession(id) {
  const result = await api(`/api/sessions/${id}/messages`)
  rememberSession(id)
  messages.value = result.messages.map(m => ({ ...m, role: m.role === 'assistant' ? 'ai' : 'user' }))
  error.value = ''
  inputText.value = ''
  await scrollToBottom()
}
async function selectSession(id) {
  if (isLoading.value || isInitializing.value) return
  isInitializing.value = true
  try { await loadSession(id) } catch (e) { error.value = e.message }
  finally { isInitializing.value = false }
}
async function createSession() {
  const result = await api('/api/sessions', 'POST')
  rememberSession(result.session.id)
  sessions.value.unshift(result.session)
  messages.value = []
  error.value = ''
}
async function clearChat() {
  if (isLoading.value || isInitializing.value) return
  isInitializing.value = true
  try {
    await createSession()
    inputText.value = ''
  } catch (e) { error.value = e.message }
  finally { isInitializing.value = false }
}
async function initialize() {
  if (initialization) return initialization
  initialization = (async () => {
    isInitializing.value = true
    try {
      await refreshSessions()
      const selected = sessions.value.find(s => s.id === activeSessionId.value) || sessions.value[0]
      if (selected) await loadSession(selected.id)
      else rememberSession('')
    } catch (e) {
      error.value = e.message
      initialization = undefined
    } finally { isInitializing.value = false }
  })()
  return initialization
}
async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || isLoading.value || isInitializing.value) return
  isLoading.value = true
  error.value = ''
  let userMessage
  try {
    if (!activeSessionId.value) await createSession()
    userMessage = { id: `pending-${Date.now()}`, role: 'user', content: text, pending: true }
    messages.value.push(userMessage)
    inputText.value = ''
    scrollToBottom()
    const result = await api('/api/chat', 'POST', { session_id: activeSessionId.value, text })
    const bubble = messages.value.find(m => m.id === userMessage.id)
    if (bubble) { bubble.pending = false; bubble.id = result.user_message_id }
    messages.value.push({ id: result.assistant_message_id, role: 'ai', content: result.reply,
      emotion: result.emotion_label, confidence: result.confidence, created_at: new Date().toISOString() })
    scrollToBottom()
    try { await refreshSessions() } catch (_) { /* The reply and record have already succeeded. */ }
  } catch (e) {
    error.value = e.message
    const bubble = userMessage && messages.value.find(m => m.id === userMessage.id)
    if (bubble) { bubble.pending = false; bubble.failed = true }
  } finally { isLoading.value = false; scrollToBottom() }
}
async function retry() {
  if (isLoading.value || isInitializing.value) return
  const failed = messages.value.findLast(m => m.role === 'user' && m.failed)
  if (!failed) { initialization = undefined; return initialize() }
  inputText.value = failed.content
  messages.value = messages.value.filter(m => m.id !== failed.id)
  await sendMessage()
}
function deleteSession(id) {
  if (isLoading.value || isInitializing.value) return
  uni.showModal({
    title: '删除这段对话？', content: '这段对话的记录和上下文会一起删除。', confirmText: '删除',
    success: async result => {
      if (!result.confirm || isLoading.value || isInitializing.value) return
      isInitializing.value = true
      try {
        await api(`/api/sessions/${id}?user_id=${encodeURIComponent(userId)}`, 'DELETE')
        await refreshSessions()
        if (activeSessionId.value === id) {
          if (sessions.value.length) await loadSession(sessions.value[0].id)
          else { rememberSession(''); messages.value = []; inputText.value = '' }
        }
        error.value = ''
      } catch (e) { error.value = e.message }
      finally { isInitializing.value = false }
    },
  })
}
function onComposerKeydown(event) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) {
    event.preventDefault()
    sendMessage()
  }
}
function copyReply(content) { uni.setClipboardData({ data: content }) }
function chooseMood(text) { inputText.value = text }
function openClassic() { uni.navigateTo({ url: '/pages/classic/index' }) }
function openExtended() { uni.reLaunch({ url: '/pages/index/index' }) }

export function useConversations() {
  return { sessions, messages, inputText, isLoading, isInitializing, error, scrollTop, scrollAnchor,
    activeSessionId, activeTitle, turnCount, initialize, selectSession, clearChat, sendMessage, retry,
    deleteSession, onComposerKeydown, copyReply, chooseMood, openClassic, openExtended }
}

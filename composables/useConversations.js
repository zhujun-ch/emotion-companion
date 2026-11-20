import { ref, computed, nextTick, watch } from 'vue'
import { account, accountHeaders, clearAccount, openLogin } from './account'
import { pendingWrite } from './requestIds'

const API = import.meta.env?.VITE_API_BASE || 'http://127.0.0.1:5000'
const sessionKey = () => 'xinyu-active-session:' + account.value?.user.id
const activeSessionId = ref(account.value ? uni.getStorageSync(sessionKey()) || '' : '')
const sessions = ref([])
const messages = ref([])
const inputText = ref('')
const isLoading = ref(false)
const isInitializing = ref(false)
const error = ref('')
const scrollTop = ref(0)
const scrollAnchor = ref('')
let initialization
watch(account, () => {
  initialization = undefined
  activeSessionId.value = account.value ? uni.getStorageSync(sessionKey()) || '' : ''
  sessions.value = []
  messages.value = []
  inputText.value = ''
  error.value = ''
  isInitializing.value = false
}, { flush: 'sync' })
const activeTitle = computed(() => sessions.value.find(s => s.id === activeSessionId.value)?.title || '新的倾诉')
const latestReferenceMessage = computed(() => messages.value.slice().reverse().find(message => message.role === 'ai'))
const isFeedbackSaving = ref(false)
const turnCount = computed(() => messages.value.filter(m => m.role === 'ai' && !m.failed).length)

function api(path, method = 'GET', data = {}) {
  const token = account.value?.token
  const pending = method === 'POST' && ['/api/chat', '/api/sessions'].includes(path)
    ? pendingWrite(account.value?.user.id, path, data) : null
  return new Promise((resolve, reject) => {
    uni.request({
      url: API + path, method, data: pending?.data || data, header: accountHeaders(), timeout: 180000,
      success: res => {
        if (token !== account.value?.token) return reject(new Error('登录状态已变更'))
        if (res.statusCode === 401) clearAccount()
        if (res.statusCode >= 200 && res.statusCode < 300 && res.data.status === 'success') {
          pending?.complete()
          resolve(res.data)
        }
        else reject(new Error(res.data?.msg || '请求失败，请稍后重试。'))
      },
      fail: failure => {
        const detail = failure?.errMsg || '网络请求失败'
        // #ifdef MP-WEIXIN
        console.warn('心屿聊天请求失败', method, path.split('?')[0], API, detail)
        reject(new Error('无法连接聊天服务 ' + API + '（' + detail + '）'))
        return
        // #endif
        // #ifndef MP-WEIXIN
        reject(new Error('连接没有成功，请检查本地服务后重试。'))
        // #endif
      },
    })
  })
}
function rememberSession(id) {
  activeSessionId.value = id
  uni.setStorageSync(sessionKey(), id)
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
async function loadSession(id, resetDraft = true) {
  const result = await api(`/api/sessions/${id}/messages`)
  rememberSession(id)
  messages.value = result.messages.map(m => ({ ...m, role: m.role === 'assistant' ? 'ai' : 'user' }))
  error.value = ''
  if (resetDraft) inputText.value = ''
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
  if (!account.value) return openLogin()
  if (isLoading.value || isInitializing.value) return
  isInitializing.value = true
  try {
    await createSession()
    inputText.value = ''
  } catch (e) { error.value = e.message }
  finally { isInitializing.value = false }
}
async function initialize() {
  if (!account.value || isLoading.value || (isInitializing.value && !initialization)) return
  if (initialization) return initialization
  const token = account.value.token
  initialization = (async () => {
    isInitializing.value = true
    try {
      await refreshSessions()
      const selected = sessions.value.find(s => s.id === activeSessionId.value) || sessions.value[0]
      if (selected) await loadSession(selected.id, false)
      else { rememberSession(''); messages.value = [] }
    } catch (e) {
      if (token === account.value?.token) error.value = e.message
    } finally {
      if (token === account.value?.token) {
        isInitializing.value = false
        initialization = undefined
      }
    }
  })()
  return initialization
}
async function sendMessage() {
  if (!account.value) return openLogin()
  const text = inputText.value.trim()
  if (!text || isLoading.value || isInitializing.value) return
  inputText.value = ''
  await sendText(text)
}
async function sendText(text, requestId) {
  const token = account.value?.token
  isLoading.value = true
  error.value = ''
  const userMessage = { id: `pending-${Date.now()}`, role: 'user', content: text, pending: true }
  try {
    if (!activeSessionId.value) await createSession()
    const payload = { session_id: activeSessionId.value, text }
    userMessage.requestId = requestId || pendingWrite(account.value?.user.id, '/api/chat', payload).data.request_id
    messages.value.push(userMessage)
    scrollToBottom()
    const result = await api('/api/chat', 'POST', { ...payload, request_id: userMessage.requestId })
    const bubble = messages.value.find(m => m.id === userMessage.id)
    if (bubble) { bubble.pending = false; bubble.id = result.user_message_id }
    messages.value.push({ id: result.assistant_message_id, role: 'ai', content: result.reply,
      emotion: result.emotion_label, confidence: result.confidence, emotion_reference: result.emotion_reference, feedback: null, created_at: new Date().toISOString() })
    scrollToBottom()
    try { await refreshSessions() } catch (_) { /* The reply and record have already succeeded. */ }
  } catch (e) {
    if (token !== account.value?.token) return
    error.value = e.message
    const bubble = messages.value.find(m => m.id === userMessage.id)
    if (bubble) { bubble.pending = false; bubble.failed = true }
    else messages.value.push({ ...userMessage, pending: false, failed: true })
  } finally { isLoading.value = false; scrollToBottom() }
}
async function retry() {
  if (isLoading.value || isInitializing.value) return
  const failed = messages.value.slice().reverse().find(m => m.role === 'user' && m.failed)
  if (!failed) return initialize()
  messages.value = messages.value.filter(m => m.id !== failed.id)
  await sendText(failed.content, failed.requestId)
}
function deleteSession(id) {
  if (isLoading.value || isInitializing.value) return
  uni.showModal({
    title: '删除这段对话？', content: '这段对话的记录和上下文会一起删除。', confirmText: '删除',
    success: async result => {
      if (!result.confirm || isLoading.value || isInitializing.value) return
      isInitializing.value = true
      try {
        await api(`/api/sessions/${id}`, 'DELETE')
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
async function sendReferenceFeedback(message, agreed, correction = null) {
  if (isFeedbackSaving.value) return
  isFeedbackSaving.value = true
  try {
    const result = await api(`/api/messages/${message.id}/feedback`, 'POST', { agreed, correction })
    message.feedback = result.feedback
    uni.showToast({ title: '反馈已保存，谢谢你告诉我', icon: 'none' })
  } catch (e) { uni.showToast({ title: e.message, icon: 'none' }) }
  finally { isFeedbackSaving.value = false }
}
function disagreeWithReference(message) {
  if (isFeedbackSaving.value) return
  const choices = ['愤怒', '恐惧', '快乐', '中性', '悲伤', '惊奇', '说不准']
  uni.showActionSheet({ itemList: choices, success: result => sendReferenceFeedback(message, false, choices[result.tapIndex]) })
}
function onComposerKeydown(event) {
  if (!isLoading.value && !isInitializing.value && event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) {
    event.preventDefault()
    sendMessage()
  }
}
function copyReply(content) { uni.setClipboardData({ data: content }) }
function chooseMood(text) { inputText.value = text }
function openHome() { uni.reLaunch({ url: '/pages/index/index' }) }
function openConversation(prefill = '') {
  inputText.value = prefill
  uni.navigateTo({ url: '/pages/conversation/index' })
}

export function useConversations() {
  return { sessions, messages, inputText, isLoading, isInitializing, error, scrollTop, scrollAnchor,
    activeSessionId, activeTitle, turnCount, latestReferenceMessage, isFeedbackSaving, sendReferenceFeedback, disagreeWithReference, initialize, selectSession, clearChat, sendMessage, retry,
    deleteSession, onComposerKeydown, copyReply, chooseMood, openHome, openConversation }
}

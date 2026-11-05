<template>
  <view class="app-shell">
    <!-- 左侧导航栏（窄屏自动隐藏） -->
    <view class="sidebar">
      <view class="brand">
        <view class="brand-mark"><text class="brand-mark-text">心</text></view>
        <view>
          <view class="brand-title">心屿 <text class="brand-en">XINYU</text></view>
          <view class="brand-sub">给情绪，一处安放</view>
        </view>
      </view>

      <view class="nav-label">我的小岛 <text class="nav-en">MY LITTLE ISLAND</text></view>

      <view class="nav-list">
        <view
          v-for="item in navItems"
          :key="item.key"
          class="nav-item"
          :class="{ active: item.key === activeNav }"
          @click="activeNav = item.key"
        >
          <text class="nav-icon">{{ item.icon }}</text>
          <view>
            <view>{{ item.title }}</view>
            <view class="nav-item-en">{{ item.en }}</view>
          </view>
        </view>
      </view>

      <view class="sidebar-note">
        <text class="spark">✳</text>
        <text class="note-text">{{ '慢慢来，\n你已经在向前了。' }}</text>
      </view>
    </view>

    <!-- 右侧主内容区 -->
    <view class="main-shell">
      <view class="topbar">
        <view class="breadcrumb">我的小岛 > <text class="active-breadcrumb">心事倾诉</text></view>
        <text class="mode-pill">● 课程演示版</text>
      </view>

      <view class="page">
        <view class="page-heading">
          <view>
            <view class="eyebrow">• YOUR SAFE LITTLE SPACE</view>
            <view class="greeting">{{ greeting }}，旅人 <text class="greeting-spark">✳</text></view>
            <view class="desc">放下外面的忙碌，这一刻，留给你自己。</view>
          </view>
          <view class="new-chat-btn" hover-class="btn-hover" @click="clearChat">+ 新的倾诉</view>
        </view>

        <view class="chat-layout">
          <view class="chat-panel">
            <view class="chat-panel-header">
              <view class="companion-heading">
                <view class="companion-avatar">心</view>
                <view>
                  <view class="companion-name">心屿陪伴</view>
                  <view class="companion-status">● 安静听你说，慢慢陪你聊</view>
                </view>
              </view>
            </view>

            <!-- 聊天记录区：用锚点滚动，比 scroll-top 魔法数字更稳 -->
            <scroll-view
              class="message-space"
              scroll-y
              :scroll-into-view="scrollAnchor"
              scroll-with-animation
            >
              <!-- 空状态 -->
              <view v-if="messages.length === 0" class="chat-welcome">
                <view class="island-art">
                  <view class="sun"></view>
                  <view class="island"></view>
                  <view class="tree"></view>
                </view>
                <view class="welcome-tag">不必逞强，也不用准备好</view>
                <view class="welcome-h2">今天，心里住着什么天气？</view>
                <view class="welcome-p">{{ '开心的、烦恼的，或是说不上来的。\n在这里，每一种感受都有被接住的地方。' }}</view>

                <view class="mood-selector">
                  <view
                    class="mood-item"
                    v-for="m in MOODS"
                    :key="m.name"
                    @click="chooseMood(m.text)"
                  >
                    <view
                      class="mood-face"
                      :style="{ color: m.color, background: m.bg, borderColor: m.color }"
                    >{{ m.icon }}</view>
                    <text class="mood-name">{{ m.name }}</text>
                  </view>
                </view>
              </view>

              <!-- 消息列表 -->
              <view v-else class="chat-records">
                <view class="conversation-date">给自己一点时间，慢慢说。</view>
                <view v-for="msg in messages" :key="msg.id" class="conversation-turn">
                  <view v-if="msg.role === 'user'" class="user-message">
                    <view class="message-bubble">{{ msg.content }}</view>
                  </view>
                  <view v-else class="assistant-message">
                    <view class="companion-avatar">心</view>
                    <view class="assistant-body">
                      <view class="message-bubble" :class="{ 'is-error': msg.isError }">{{ msg.content }}</view>
                      <view v-if="msg.emotion" class="message-meta">
                        <text class="emotion-badge">当前情绪：{{ msg.emotion }}</text>
                      </view>
                    </view>
                  </view>
                </view>

                <view v-if="isLoading" class="sending-state">
                  <text>正在整理一份温柔的回应</text>
                  <text class="dots"><text>.</text><text>.</text><text>.</text></text>
                </view>
                <view id="chat-bottom" class="chat-bottom"></view>
              </view>
            </scroll-view>

            <!-- 输入区 -->
            <view class="composer-area">
              <view class="composer">
                <textarea
                  class="chat-textarea"
                  v-model="inputText"
                  placeholder="此刻的你，想说些什么？"
                  :disabled="isLoading"
                  :maxlength="MAX_LEN"
                  :auto-height="false"
                  confirm-type="send"
                  @keydown="onKeydown"
                />
                <view class="composer-bottom">
                  <view class="composer-tip">你的心事，值得被温柔对待</view>
                  <view class="composer-actions">
                    <text class="char-count">{{ inputText.length }}/{{ MAX_LEN }}</text>
                    <button class="send-btn" :disabled="!canSend" @click="sendMessage">↑</button>
                  </view>
                </view>
              </view>
            </view>
          </view>

          <!-- 右侧挂件 -->
          <view class="chat-aside">
            <view class="card journal-invite">
              <view class="section-eyebrow">留住此刻的感受</view>
              <view class="little-sun"></view>
              <view class="journal-title">{{ '每一种心情，\n都有它的意义。' }}</view>
              <view class="journal-desc">不急着变好，先试着看见自己。</view>
            </view>

            <view class="card breathing-card" @click="toggleBreathing">
              <view class="section-eyebrow">给自己一分钟</view>
              <view class="journal-title small">让心，慢下来。</view>
              <view class="breath-orbit">
                <view class="breath-circle" :class="{ breathing: isBreathing }">
                  <text>{{ breathText }}</text>
                </view>
              </view>
              <view class="breath-hint">{{ isBreathing ? '再点一下，结束练习' : '点一下，开始呼吸' }}</view>
            </view>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, computed, nextTick, onUnmounted } from 'vue'

/* ============ 配置 ============ */
// 真机调试时，把 .env 中的 VITE_API_BASE 改成电脑局域网 IP，例如 http://192.168.1.10:5000
const API_BASE = import.meta.env?.VITE_API_BASE || 'http://127.0.0.1:5000'
const MAX_LEN = 2000
const REQUEST_TIMEOUT = 180000

const NAV_ITEMS = [
  { key: 'talk', icon: '◐', title: '心事倾诉', en: 'A space to talk' },
  { key: 'board', icon: '◔', title: '情绪看板', en: 'Meet your feelings' },
  { key: 'diary', icon: '✎', title: '心情日记', en: 'Little moments' },
]

const MOODS = [
  { name: '快乐', icon: '☀', color: '#d3a95c', bg: '#fcf4e3', text: '今天发生了一件让我很开心的事情！' },
  { name: '焦虑', icon: '⌇', color: '#8f92c4', bg: '#eceefa', text: '我心里有些烦，总担心事情做不好。' },
  { name: '悲伤', icon: '☂', color: '#699fc4', bg: '#e4f0f7', text: '今天觉得有些难过，想找人倾诉。' },
  { name: '愤怒', icon: '⚡', color: '#cc767a', bg: '#fcebeb', text: '有些事情让我很生气，不知道该怎么办。' },
  { name: '压力大', icon: '☁', color: '#8fb5a4', bg: '#ebf3f0', text: '最近事情太多了，我感觉压力很大。' },
]

/* ============ 状态 ============ */
const navItems = NAV_ITEMS
const activeNav = ref('talk')
const inputText = ref('')
const messages = ref([])
const isLoading = ref(false)
const scrollAnchor = ref('')

let msgSeq = 0
let currentTask = null // 当前请求，用于清空对话时中止

const canSend = computed(() => inputText.value.trim().length > 0 && !isLoading.value)

// 根据时间段显示问候语
const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 5) return '夜深了'
  if (h < 11) return '上午好'
  if (h < 13) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})

// 用户 ID：首次生成并持久化，避免所有人共用同一个 ID
const getUserId = () => {
  let id = uni.getStorageSync('xinyu_user_id')
  if (!id) {
    id = 'u_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8)
    uni.setStorageSync('xinyu_user_id', id)
  }
  return id
}
const userId = getUserId()

/* ============ 聊天逻辑 ============ */
const pushMessage = (msg) => {
  messages.value.push({ id: ++msgSeq, ...msg })
  scrollToBottom()
}

// 每次先清空再赋值，保证相同锚点也能重复触发滚动
const scrollToBottom = () => {
  scrollAnchor.value = ''
  nextTick(() => {
    scrollAnchor.value = 'chat-bottom'
  })
}

const chooseMood = (text) => {
  inputText.value = text
}

const clearChat = () => {
  if (currentTask) {
    currentTask.abort()
    currentTask = null
  }
  messages.value = []
  inputText.value = ''
  isLoading.value = false
}

// H5：Enter 发送，Shift+Enter 换行（textarea 的 @confirm 在 H5 并不会触发）
const onKeydown = (e) => {
  // #ifdef H5
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    sendMessage()
  }
  // #endif
}

const sendMessage = () => {
  if (!canSend.value) return
  const text = inputText.value.trim()

  pushMessage({ role: 'user', content: text })
  inputText.value = ''
  isLoading.value = true

  currentTask = uni.request({
    url: `${API_BASE}/api/chat`,
    method: 'POST',
    timeout: REQUEST_TIMEOUT,
    data: { user_id: userId, text },
    success: (res) => {
      const data = res.data || {}
      if (res.statusCode === 200 && data.status === 'success') {
        pushMessage({ role: 'ai', content: data.reply, emotion: data.emotion_label })
      } else {
        pushMessage({
          role: 'ai',
          content: data.msg || `服务暂时没有响应（${res.statusCode}），请稍后再试。`,
          isError: true,
        })
      }
    },
    fail: (err) => {
      // 主动 abort 时不提示错误
      if (err?.errMsg?.includes('abort')) return
      const timeout = err?.errMsg?.includes('timeout')
      pushMessage({
        role: 'ai',
        content: timeout ? '等得有点久了，请再试一次。' : '连不上后端服务，请确认它已启动，且地址正确。',
        isError: true,
      })
    },
    complete: () => {
      currentTask = null
      isLoading.value = false
    },
  })
}

/* ============ 呼吸练习：4 秒吸 / 4 秒呼 ============ */
const isBreathing = ref(false)
const breathText = ref('呼吸')
let breathTimer = null

const toggleBreathing = () => {
  if (isBreathing.value) {
    stopBreathing()
    return
  }
  isBreathing.value = true
  let inhale = true
  breathText.value = '吸气'
  breathTimer = setInterval(() => {
    inhale = !inhale
    breathText.value = inhale ? '吸气' : '呼气'
  }, 4000)
}

const stopBreathing = () => {
  clearInterval(breathTimer)
  breathTimer = null
  isBreathing.value = false
  breathText.value = '呼吸'
}

onUnmounted(() => {
  clearInterval(breathTimer)
  currentTask?.abort()
})
</script>

<style>
page {
  --bg: #f7f8f4;
  --text: #3c483e;
  --green: #58755e;
  --border: #e8eae2;
  --serif: "Noto Serif SC", "Songti SC", "STSong", serif;

  background-color: var(--bg);
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
  color: var(--text);
  height: 100%;
  overflow: hidden;
}

.app-shell { display: flex; height: 100%; }

/* ============ 左侧导航 ============ */
.sidebar {
  width: 228px;
  flex-shrink: 0;
  background: #f0f3ea;
  border-right: 1px solid #e6eadd;
  display: flex;
  flex-direction: column;
  padding: 35px 21px 0;
}
.brand { display: flex; align-items: center; gap: 10px; padding-left: 9px; }
.brand-mark { width: 37px; height: 37px; background: var(--green); border-radius: 12px; display: flex; align-items: center; justify-content: center; }
.brand-mark-text { color: #fff; font-size: 20px; font-weight: bold; }
.brand-title { font-family: var(--serif); font-size: 25px; font-weight: 600; letter-spacing: 4px; color: var(--text); }
.brand-en { font-size: 9px; color: #7e8f78; }
.brand-sub { font-size: 10px; letter-spacing: 2px; color: #8e9b85; margin-top: 4px; }

.nav-label { font-size: 10px; color: #8e9c84; margin: 51px 10px 16px; }
.nav-en { font-size: 7px; color: #a1ab97; margin-left: 5px; }
.nav-list { display: flex; flex-direction: column; gap: 7px; }
.nav-item { display: flex; align-items: center; gap: 14px; padding: 15px 16px; border-radius: 10px; color: #7d8978; cursor: pointer; transition: background .2s; }
.nav-item.active { background: #e0e8d8; color: #4e6a50; font-weight: 600; }
.nav-icon { font-size: 18px; width: 20px; text-align: center; }
.nav-item-en { display: block; font-size: 9px; color: #99a190; margin-top: 5px; font-weight: 400; }

.sidebar-note { margin: 38px 10px 20px; padding: 20px 12px; border-top: 1px solid #dde5d4; }
.spark { font-size: 30px; color: #96a78a; }
.note-text { display: block; white-space: pre-line; font-family: var(--serif); font-size: 16px; line-height: 1.9; color: #7c8c71; margin-top: 10px; }

/* ============ 右侧主体 ============ */
.main-shell { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.topbar { height: 76px; flex-shrink: 0; border-bottom: 1px solid #e9ece3; display: flex; align-items: center; justify-content: space-between; padding: 0 43px; background: #f9faf6; }
.breadcrumb { font-size: 11px; color: #a0a697; }
.active-breadcrumb { color: #63725d; margin-left: 5px; }
.mode-pill { font-size: 10px; border: 1px solid #dfe5d5; padding: 7px 10px; border-radius: 6px; color: #7b8b70; background: #f1f5eb; }

.page { padding: 35px 42px; flex: 1; display: flex; flex-direction: column; overflow: hidden; min-height: 0; }
.page-heading { display: flex; align-items: center; justify-content: space-between; margin-bottom: 29px; }
.eyebrow { font-size: 8px; letter-spacing: 2px; color: #939e86; margin-bottom: 13px; }
.greeting { font-family: var(--serif); font-size: 27px; color: #394a3c; font-weight: 500; }
.greeting-spark { color: #b4be97; margin-left: 5px; }
.desc { font-size: 12px; color: #939b8c; margin-top: 7px; }
.new-chat-btn { font-size: 11px; padding: 9px 15px; border: 1px solid #e0e6d7; border-radius: 7px; color: #77866b; background: #fbfcf8; cursor: pointer; white-space: nowrap; }
.btn-hover { background: #f1f5eb; }

/* ============ 聊天区 ============ */
.chat-layout { display: flex; gap: 22px; flex: 1; min-height: 0; overflow: hidden; }
.chat-panel { flex: 1; min-width: 0; background: #fffefa; border: 1px solid var(--border); border-radius: 13px; display: flex; flex-direction: column; overflow: hidden; box-shadow: 0 3px 10px rgba(83, 99, 67, 0.02); }
.chat-panel-header { height: 76px; flex-shrink: 0; padding: 0 25px; display: flex; align-items: center; border-bottom: 1px solid #eeefe8; }
.companion-heading { display: flex; align-items: center; gap: 10px; }
.companion-avatar { width: 34px; height: 34px; flex-shrink: 0; border-radius: 11px; background: #eaf0e1; color: #7f9b70; display: flex; align-items: center; justify-content: center; font-weight: bold; }
.companion-name { font-size: 12px; font-weight: 500; color: var(--text); }
.companion-status { font-size: 9px; color: #9aa88d; margin-top: 4px; }

.message-space { flex: 1; min-height: 0; padding: 12px 27px 24px; box-sizing: border-box; background: #fffefa; }
.chat-welcome { text-align: center; padding-top: 30px; }

/* 纯 CSS 小岛插画 */
.island-art { width: 100%; height: 167px; position: relative; margin-bottom: 10px; }
.sun { width: 40px; height: 40px; background: #e1c58d; border-radius: 50%; position: absolute; right: 80px; top: 20px; opacity: 0.8; }
.island { width: 200px; height: 50px; background: #d8e4db; border-radius: 50%; position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%); }
.tree { width: 4px; height: 40px; background: #728e71; position: absolute; bottom: 50px; left: 50%; border-radius: 2px; }
.tree::before { content: ''; position: absolute; width: 30px; height: 20px; background: #91a585; border-radius: 50%; top: -10px; left: -13px; }

.welcome-tag { display: block; color: #a0a98d; font-size: 9px; letter-spacing: 2px; }
.welcome-h2 { font-family: var(--serif); font-size: 22px; color: #536649; margin-top: 15px; font-weight: 500; }
.welcome-p { white-space: pre-line; font-size: 11px; color: #9aa18f; margin-top: 12px; line-height: 2; }

.mood-selector { display: flex; justify-content: center; flex-wrap: wrap; gap: 20px 27px; margin: 32px 0; }
.mood-item { display: flex; flex-direction: column; align-items: center; gap: 8px; cursor: pointer; }
.mood-face { width: 41px; height: 41px; border-radius: 50%; border: 1px solid; display: flex; align-items: center; justify-content: center; font-size: 20px; transition: transform .15s; }
.mood-item:active .mood-face { transform: scale(0.92); }
.mood-name { font-size: 10px; color: #8c947f; }

/* 气泡 */
.chat-records { padding-top: 10px; }
.conversation-date { text-align: center; font-size: 9px; color: #a8b19e; margin-bottom: 20px; }
.conversation-turn { margin-bottom: 26px; }
.user-message { display: flex; flex-direction: column; align-items: flex-end; }
.message-bubble { white-space: pre-wrap; word-break: break-word; user-select: text; }
.user-message .message-bubble { background: #e9efdf; border-radius: 11px 2px 11px 11px; padding: 12px 16px; max-width: 85%; color: #617451; font-size: 12px; line-height: 2; }
.assistant-message { display: flex; align-items: flex-start; gap: 10px; }
.assistant-message .companion-avatar { width: 29px; height: 29px; border-radius: 9px; background: #edf2e5; color: #8ba47b; font-size: 12px; }
.assistant-body { max-width: 91%; }
.assistant-body .message-bubble { color: #748168; border: 1px solid #edf0e4; background: #fdfef9; border-radius: 2px 11px 11px 11px; padding: 13px 16px; font-size: 12px; line-height: 2; }
.assistant-body .message-bubble.is-error { color: #a4685f; background: #fdf6f4; border-color: #f2e0db; }
.message-meta { margin-top: 7px; }
.emotion-badge { font-size: 9px; color: #8fa17a; background: #edf2e6; padding: 4px 8px; border-radius: 4px; }

.sending-state { color: #a1ad90; font-size: 10px; margin-top: -8px; }
.dots text { animation: blink 1.4s infinite both; }
.dots text:nth-child(2) { animation-delay: .2s; }
.dots text:nth-child(3) { animation-delay: .4s; }
@keyframes blink { 0%, 80%, 100% { opacity: .2; } 40% { opacity: 1; } }
.chat-bottom { height: 1px; }

/* 输入框 */
.composer-area { flex-shrink: 0; padding: 0 23px 16px; }
.composer { padding: 14px 15px 10px; background: #fafbf6; border: 1px solid #e3e8d9; border-radius: 9px; transition: border-color .2s; }
.composer:focus-within { border-color: #b9c9a8; }
.chat-textarea { width: 100%; height: 55px; background: transparent; font-size: 12px; color: #596b50; line-height: 1.9; }
.composer-bottom { display: flex; align-items: center; justify-content: space-between; margin-top: 5px; }
.composer-tip { color: #a5b097; font-size: 9px; }
.composer-actions { display: flex; align-items: center; gap: 12px; }
.char-count { font-size: 9px; color: #abb29f; }
.send-btn { background: #6d8963; color: #fff; width: 31px; height: 31px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 18px; padding: 0; margin: 0; line-height: 1; }
.send-btn[disabled] { background: #c9d4c3; color: #fff; }

/* 右侧挂件 */
.chat-aside { width: 258px; flex-shrink: 0; display: flex; flex-direction: column; gap: 17px; }
.card { border: 1px solid var(--border); border-radius: 13px; background: #fffefa; padding: 22px 21px; }
.section-eyebrow { font-size: 10px; color: #839176; }
.journal-invite { background: #f1f4e9; position: relative; overflow: hidden; }
.journal-title { white-space: pre-line; font-family: var(--serif); font-size: 22px; color: #607352; margin: 19px 0 12px; line-height: 1.6; }
.journal-title.small { font-size: 18px; }
.journal-desc { font-size: 10px; color: #95a083; }
.little-sun { position: absolute; right: -4px; top: 50px; width: 60px; height: 60px; background: #e3e7c9; border-radius: 50%; opacity: 0.7; }

/* 呼吸练习 */
.breathing-card { text-align: center; cursor: pointer; }
.breath-orbit { width: 104px; height: 104px; margin: 23px auto 17px; border: 1px solid #e9ecde; border-radius: 50%; display: flex; align-items: center; justify-content: center; }
.breath-circle { width: 67px; height: 67px; border-radius: 50%; background: radial-gradient(circle, #e5ecd8, #eaf0e1); display: flex; align-items: center; justify-content: center; color: #8a9d73; font-size: 12px; }
.breath-circle.breathing { animation: breathe 8s ease-in-out infinite; }
.breath-hint { font-size: 9px; color: #a5b097; }
@keyframes breathe {
  0%, 100% { transform: scale(0.8); }
  50% { transform: scale(1.3); }
}

/* ============ 响应式：窄屏隐藏侧栏与挂件 ============ */
@media (max-width: 960px) {
  .chat-aside { display: none; }
}
@media (max-width: 720px) {
  .sidebar { display: none; }
  .topbar { height: 56px; padding: 0 16px; }
  .page { padding: 18px 14px; }
  .page-heading { margin-bottom: 16px; }
  .greeting { font-size: 22px; }
  .chat-panel-header { height: 60px; padding: 0 16px; }
  .message-space { padding: 8px 14px 16px; }
  .composer-area { padding: 0 12px 12px; }
}

@media (prefers-reduced-motion: reduce) {
  .breath-circle.breathing, .dots text { animation: none; }
}
</style>

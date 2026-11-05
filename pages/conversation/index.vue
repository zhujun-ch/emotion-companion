<template>
  <view class="workspace">
    <view class="history-rail">
      <view class="brand"><view class="brand-icon">屿</view><view><view class="brand-name">心屿</view><view class="brand-sub">给情绪，一处安放</view></view></view>
      <button class="new-session" :disabled="isLoading || isInitializing" @click="clearChat"><text>＋</text> 开启一段新的倾诉</button>
      <view class="history-heading"><text>聊过的心事</text><text>{{ sessions.length }}</text></view>
      <scroll-view class="session-list" scroll-y>
        <view v-if="!sessions.length" class="history-empty">还没有聊过的心事。<br />从今天的一件小事开始吧。</view>
        <view v-for="session in sessions" :key="session.id" class="session-row" :class="{ selected: activeSessionId === session.id }">
          <button class="session-open" :disabled="isLoading || isInitializing" @click="selectSession(session.id)">
            <view class="session-title">{{ session.title }}</view>
            <view class="session-sub">{{ formatDate(session.updated_at) }}<text> · {{ Math.floor(session.message_count / 2) }} 轮对话</text></view>
          </button>
          <button class="session-delete" :disabled="isLoading || isInitializing" @click.stop="deleteSession(session.id)" aria-label="删除对话">×</button>
        </view>
      </scroll-view>
      <view class="rail-note"><view class="note-flower">✳</view><view>不用一次说清楚，<br />我们可以慢慢聊。</view></view>

    </view>

    <view class="conversation-shell">
      <view class="topbar"><view class="breadcrumb">我的小岛 <text>/</text> 心事倾诉</view></view>
      <view class="conversation-header">
        <view class="eyebrow">A LITTLE SPACE FOR YOU</view>
        <view class="title-row">
          <view class="page-title">{{ activeTitle === '新的倾诉' ? '此刻，想聊些什么？' : activeTitle }}</view>
          <button class="home-button" @click="openHome">← 返回主页</button>
        </view>
        <view class="header-bottom">
          <view class="page-subtitle">不急着找到答案，先把心里的话说出来。</view>
          <view class="memory-pill"><view class="status-dot"></view>{{ turnCount ? '接着刚才的话，继续聊' : '这段对话，会替你留好' }}</view>
        </view>
      </view>

      <view class="chat-card">
        <view class="companion-bar"><view class="avatar">屿</view><view><view class="companion-name">心屿陪伴</view><view class="companion-status">在这里，听你慢慢说</view></view><view class="session-count">{{ turnCount ? `已聊 ${turnCount} 轮` : '一段新的开始' }}</view></view>
        <scroll-view class="messages" scroll-y :scroll-top="scrollTop" :scroll-into-view="scrollAnchor" scroll-with-animation>
          <view v-if="isInitializing" class="restoring">正在找回这段对话…</view>
          <view v-else-if="messages.length === 0" class="welcome">
            <view class="island-scene"><view class="sun"></view><view class="water water-one"></view><view class="water water-two"></view><view class="island"></view><view class="tree-trunk"></view><view class="tree-leaf leaf-one"></view><view class="tree-leaf leaf-two"></view></view>
            <view class="welcome-eyebrow">每一种感受，都有它的位置</view>
            <view class="welcome-title">今天，心里是什么天气？</view>
            <view class="welcome-description">一件开心的小事，一点说不出的疲惫，<br />或者只是想有人陪着说说话。</view>
            <view class="prompt-list"><button v-for="prompt in prompts" :key="prompt" @click="chooseMood(prompt)">{{ prompt }} <text>↗</text></button></view>
          </view>
          <view v-else class="message-list">
            <view class="conversation-note">这是一段只属于此刻的对话</view>
            <view v-for="message in messages" :key="message.id" class="message-row" :class="message.role === 'user' ? 'from-user' : 'from-companion'">
              <view v-if="message.role === 'ai'" class="avatar message-avatar">屿</view>
              <view class="message-body"><view class="speaker">{{ message.role === 'user' ? '你' : '心屿' }}</view>
                <view class="bubble" :class="{ 'failed-bubble': message.failed }"><text selectable>{{ message.content }}</text></view>
                <view v-if="message.role === 'ai'" class="message-tools"><button class="copy-button" @click="copyReply(message.content)">复制回复</button></view>
                <view v-if="message.failed" class="failed-label">未发送成功</view>
              </view>
            </view>
            <view v-if="isLoading" class="message-row from-companion"><view class="avatar message-avatar">屿</view><view class="typing"><view class="typing-dots"><text></text><text></text><text></text></view><text>正在认真听，也在想怎么回应你</text></view></view>
          </view>
          <view id="chat-bottom" class="chat-bottom"></view>
        </scroll-view>
        <view class="composer-wrap">
          <view v-if="latestReferenceMessage?.emotion_reference && !isLoading" class="reference-panel" :class="{ 'reference-ready': latestReferenceMessage.emotion_reference.state === 'ready' }">
            <template v-if="latestReferenceMessage.emotion_reference.state === 'ready'">
              <view class="reference-main">
                <text v-if="latestReferenceMessage.feedback && !latestReferenceMessage.feedback.agreed">你的更正 · {{ latestReferenceMessage.feedback.correction || '暂不判断' }}</text>
                <text v-else>近期表达可能偏向 · {{ latestReferenceMessage.emotion_reference.label }}</text>
                <view class="reference-actions">
                  <button :disabled="isFeedbackSaving" :class="{ chosen: latestReferenceMessage.feedback?.agreed }" @click="sendReferenceFeedback(latestReferenceMessage, true)">符合</button>
                  <button :disabled="isFeedbackSaving" :class="{ chosen: latestReferenceMessage.feedback && !latestReferenceMessage.feedback.agreed }" @click="disagreeWithReference(latestReferenceMessage)">不太符合</button>
                </view>
              </view>
              <view class="reference-note">{{ latestReferenceMessage.feedback ? '已保存你的反馈，你的感受由你来定义。' : '只是近期文字的参考，你的感受由你来定义。' }}</view>
            </template>
            <view v-else>
              <view>{{ latestReferenceMessage.emotion_reference.reason }}</view>
              <view v-if="latestReferenceMessage.emotion_reference.candidates?.length" class="reference-main">
                <text v-if="latestReferenceMessage.feedback && !latestReferenceMessage.feedback.agreed">你的更正 · {{ latestReferenceMessage.feedback.correction || '说不准' }}</text>
                <text v-else>初步参考 · {{ latestReferenceMessage.emotion_reference.candidates.join(' / ') }}（不确定）</text>
                <view class="reference-actions"><button :disabled="isFeedbackSaving" @click="disagreeWithReference(latestReferenceMessage)">更正我的感受</button></view>
              </view>
            </view>
          </view>
          <view v-if="error" class="error-notice" role="alert"><text>{{ error }}</text><button :disabled="isLoading || isInitializing" @click="retry">重试</button></view>
          <view class="composer" :class="{ 'composer-busy': isLoading }">
            <textarea class="text-input" v-model="inputText" maxlength="2000" :disabled="isLoading || isInitializing" placeholder="从你想说的那句话开始…" :auto-height="true" :show-confirm-bar="false" @keydown="onComposerKeydown" />
            <view class="composer-footer"><text class="keyboard-hint">Enter 发送 · Shift + Enter 换行</text><view class="send-actions"><text class="char-count">{{ inputText.length }} / 2000</text><button class="send-button" :disabled="!inputText.trim() || isLoading || isInitializing" @click="sendMessage">{{ isLoading ? '回应中' : '发送' }} <text v-if="!isLoading">↑</text></button></view></view>
          </view>
          <view class="composer-caption"><text>对话保存在本机 · 新建对话会开启独立的记忆</text><text>不必着急，慢慢说。</text></view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { onMounted } from 'vue'
import { useConversations } from '../../composables/useConversations'
const { sessions, messages, inputText, isLoading, isInitializing, error, scrollTop, scrollAnchor,
  activeSessionId, activeTitle, turnCount, latestReferenceMessage, isFeedbackSaving, sendReferenceFeedback, disagreeWithReference, initialize, selectSession, clearChat, sendMessage, retry,
  deleteSession, onComposerKeydown, copyReply, chooseMood, openHome } = useConversations()
const prompts = ['今天有件小事想和你分享', '最近有些累，想说说心里话', '先陪我随便聊聊吧']
function formatDate(value) {
  const date = new Date(value)
  return `${date.getMonth() + 1}月${date.getDate()}日`
}
onMounted(initialize)
</script>

<style scoped>
.reference-panel { margin-bottom: 10px; padding: 8px 12px; color: #8a977f; background: #f5f7f0; border-radius: 8px; font-size: 11px; line-height: 1.7; }
.reference-main { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 6px 14px; }
.reference-ready { border: 1px solid #e2e9d9; color: #70855e; }
.reference-actions { display: flex; gap: 8px; }
.workspace .reference-actions button { font-size: 10px; padding: 4px 9px; color: #8a987c; border: 1px solid #dce4d1; border-radius: 5px; }
.workspace .reference-actions .chosen { color: #4e6e42; background: #e5edda; border-color: #acbf9c; }
.reference-note { margin-top: 3px; font-size: 9px; color: #9aa68e; }

.workspace { height: 100%; background: #f7f8f3; color: #34483c; font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif; }
.workspace, .workspace * { box-sizing: border-box; }
.workspace { display: flex; height: 100vh; min-height: 460px; overflow: hidden; }
.workspace button { margin: 0; padding: 0; line-height: normal; border-radius: 0; font-size: inherit; background: transparent; color: inherit; cursor: pointer; }
.workspace button::after { border: 0; }
.workspace button[disabled] { opacity: .45; cursor: default; }
.history-rail { width: 260px; flex-shrink: 0; display: flex; flex-direction: column; padding: 35px 20px 22px; background: #eef1e8; border-right: 1px solid #e1e6db; }
.brand { display: flex; gap: 12px; align-items: center; padding: 0 10px; }
.brand-icon, .avatar { display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.brand-icon { width: 42px; height: 44px; background: #526c55; color: #fff; border-radius: 15px 15px 15px 3px; font-size: 22px; font-family: serif; }
.brand-name { font-family: 'Songti SC', serif; font-size: 26px; letter-spacing: 4px; }
.brand-sub { font-size: 10px; color: #85917e; margin-top: 3px; letter-spacing: 2px; }
.workspace .new-session { display: flex; align-items: center; justify-content: center; gap: 8px; margin-top: 36px; border: 1px solid #cbd6c3; border-radius: 10px; padding: 13px 5px; color: #506b50; font-size: 12px; background: #f8faf4; }
.new-session text { font-size: 20px; line-height: 16px; }
.history-heading { display: flex; justify-content: space-between; color: #919b88; margin: 30px 10px 13px; font-size: 10px; letter-spacing: 1px; }
.session-list { flex: 1; min-height: 0; }
.history-empty { color: #929d89; font-size: 12px; line-height: 2; padding: 16px 10px; }
.session-row { display: flex; border-radius: 9px; margin-bottom: 6px; align-items: center; }
.session-row.selected { background: #dfe7d7; }
.session-row:hover { background: #e4eadc; }
.workspace .session-open { text-align: left; flex: 1; min-width: 0; padding: 13px 10px; }
.session-title { font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #5a6b52; }
.session-sub { font-size: 9px; color: #939e88; margin-top: 7px; }
.workspace .session-delete { padding: 10px 8px; font-size: 20px; color: #8b9884; }
.rail-note { margin: 20px 10px 24px; padding-top: 20px; border-top: 1px solid #dce2d4; color: #85977b; font-family: serif; font-size: 16px; line-height: 1.9; }
.note-flower { font-size: 26px; color: #99aa8c; margin-bottom: 6px; }
.workspace .classic-link { display: flex; justify-content: space-between; margin: 0 10px; font-size: 11px; color: #84917b; }
.conversation-shell { min-width: 0; flex: 1; display: flex; flex-direction: column; }
.topbar { height: 62px; flex-shrink: 0; display: flex; align-items: center; justify-content: space-between; padding: 0 40px; border-bottom: 1px solid #e7eadd; }
.breadcrumb { font-size: 11px; color: #88947f; }
.breadcrumb text { margin: 0 12px; color: #bac1b1; }
.workspace .home-button { display: flex; align-items: center; justify-content: center; min-height: 44px; font-size: 14px; border: 1px solid #cbd6c1; border-radius: 9px; padding: 10px 20px; color: #617952; background: #f1f5eb; flex-shrink: 0; white-space: nowrap; }
.conversation-header { display: flex; flex-direction: column; padding: 30px 42px 24px; flex-shrink: 0; }
.title-row { display: flex; justify-content: space-between; align-items: center; gap: 16px; }
.title-row .page-title { min-width: 0; flex: 1; }
.header-bottom { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-top: 10px; }
.header-bottom .page-subtitle { margin-top: 0; }
.eyebrow { font-size: 8px; letter-spacing: 2.3px; color: #96a18c; margin-bottom: 10px; }
.page-title { font-family: 'Songti SC', serif; font-size: 25px; font-weight: 500; max-width: 600px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.page-subtitle { font-size: 11px; color: #929c87; margin-top: 10px; }
.memory-pill { display: flex; align-items: center; gap: 7px; font-size: 10px; color: #839076; white-space: nowrap; }
.status-dot { width: 5px; height: 5px; border-radius: 50%; background: #8da57c; }
.chat-card { margin: 0 40px 26px; flex: 1; min-height: 0; border: 1px solid #e0e5d8; background: #fffefa; border-radius: 16px; display: flex; flex-direction: column; overflow: hidden; box-shadow: 0 6px 28px #4b634508; }
.companion-bar { padding: 16px 25px; display: flex; gap: 11px; align-items: center; border-bottom: 1px solid #eef0e7; flex-shrink: 0; }
.avatar { width: 35px; height: 35px; border-radius: 12px 12px 12px 3px; background: #e7efde; color: #7c976b; font-family: serif; font-size: 18px; }
.companion-name { font-size: 12px; color: #566b4c; }
.companion-status { color: #99a58d; font-size: 9px; margin-top: 5px; }
.session-count { margin-left: auto; font-size: 10px; color: #a0aa93; }
.messages { flex: 1; min-height: 0; overflow-y: auto; }
.restoring { text-align: center; padding: 80px 15px; color: #8c9b80; font-size: 12px; }
.welcome { text-align: center; padding: 12px 20px 24px; }
.island-scene { width: 230px; height: 135px; margin: 0 auto 20px; position: relative; }
.sun { position: absolute; width: 32px; height: 32px; border-radius: 50%; background: #e7cf9d; top: 14px; right: 34px; }
.island { position: absolute; width: 150px; height: 35px; border-radius: 50%; background: #d4e1d0; bottom: 21px; left: 40px; }
.water { position: absolute; border: 1px solid #dde5dd; border-radius: 50%; bottom: 10px; left: 12px; width: 206px; height: 40px; }
.water-two { width: 180px; left: 26px; bottom: 16px; }
.tree-trunk { width: 4px; height: 47px; position: absolute; left: 111px; top: 44px; background: #8d9d7a; }
.tree-leaf { position: absolute; width: 44px; height: 35px; background: #a1b28d; left: 92px; top: 28px; border-radius: 50% 60% 40% 50%; }
.leaf-two { width: 35px; height: 28px; left: 104px; top: 42px; background: #8fa77b; }
.welcome-eyebrow { font-size: 10px; color: #9aa68c; letter-spacing: 2px; }
.welcome-title { font-family: serif; font-size: 23px; margin: 12px 0; color: #5e7350; }
.welcome-description { font-size: 11px; color: #98a08c; line-height: 2; }
.prompt-list { display: flex; gap: 9px; justify-content: center; margin-top: 23px; flex-wrap: wrap; }
.workspace .prompt-list button { padding: 9px 12px; border: 1px solid #e4e8da; color: #88977b; border-radius: 7px; font-size: 10px; }
.prompt-list text { margin-left: 10px; color: #a2af96; }
.message-list { padding: 20px 28px 10px; }
.conversation-note { text-align: center; font-size: 9px; color: #a8af9c; margin-bottom: 27px; }
.message-row { display: flex; gap: 10px; margin-bottom: 25px; }
.from-user { justify-content: flex-end; }
.message-body { max-width: 80%; min-width: 0; }
.speaker { font-size: 9px; margin-bottom: 7px; color: #98a18d; }
.from-user .speaker { text-align: right; }
.bubble { padding: 13px 17px; border-radius: 2px 12px 12px 12px; color: #596d4d; background: #f5f7ef; font-size: 13px; line-height: 1.95; white-space: pre-wrap; overflow-wrap: anywhere; }
.from-user .bubble { background: #e9efdf; border-radius: 12px 2px 12px 12px; color: #4b6242; }
.message-avatar { width: 30px; height: 30px; margin-top: 19px; font-size: 16px; }
.message-tools { display: flex; gap: 14px; align-items: center; margin-top: 9px; }
.emotion-tag { color: #9aaa89; font-size: 9px; }
.workspace .copy-button { font-size: 9px; color: #a4ad98; }
.failed-bubble { border: 1px solid #ddafa2; }
.failed-label { font-size: 10px; color: #b67c6c; text-align: right; padding-top: 5px; }
.typing { padding-top: 22px; display: flex; flex-wrap: wrap; gap: 10px; align-items: center; font-size: 10px; color: #9ca58f; }
.typing-dots { display: flex; gap: 4px; }
.typing-dots text { width: 5px; height: 5px; border-radius: 50%; background: #a8b799; animation: breathe 1.3s infinite; }
.typing-dots text:nth-child(2) { animation-delay: .18s; }
.typing-dots text:nth-child(3) { animation-delay: .36s; }
@keyframes breathe { 50% { opacity: .3; transform: translateY(-3px); } }
.chat-bottom { height: 1px; }
.composer-wrap { padding: 0 22px 14px; flex-shrink: 0; }
.composer { border: 1px solid #dfe6d4; border-radius: 11px; background: #fbfcf7; padding: 15px 16px 11px; }
.composer:focus-within { border-color: #aabb9b; box-shadow: 0 0 0 3px #94a77e0a; }
.text-input { display: block; width: 100%; min-height: 54px; max-height: 130px; font-size: 13px; line-height: 1.8; color: #52664a; }
.composer-footer { display: flex; align-items: center; justify-content: space-between; margin-top: 7px; }
.keyboard-hint { color: #a6ae9b; font-size: 9px; }
.send-actions { display: flex; align-items: center; gap: 15px; }
.char-count { color: #adb59f; font-size: 9px; }
.workspace .send-button { background: #647e56; color: #fff; border-radius: 7px; padding: 9px 15px; font-size: 11px; display: flex; align-items: center; gap: 16px; }
.send-button text { font-size: 16px; }
.composer-caption { display: flex; justify-content: space-between; gap: 12px; font-size: 8px; color: #a7b09b; margin: 10px 2px 0; }
.error-notice { display: flex; align-items: center; justify-content: space-between; gap: 10px; font-size: 12px; color: #a46250; background: #faf0e9; padding: 9px 12px; border-radius: 7px; margin-bottom: 8px; }
.workspace .error-notice button { color: #8c584b; font-size: 11px; flex-shrink: 0; }
@media (max-width: 1100px) { .history-rail { width: 220px; padding-left: 14px; padding-right: 14px; } .topbar { padding: 0 26px; } .conversation-header { padding: 24px 26px 20px; } .chat-card { margin: 0 24px 20px; } .memory-pill { display: none; } }
@media (max-width: 720px) { .workspace { min-height: 360px; } .history-rail { width: 160px; padding: 22px 10px 16px; } .brand { padding: 0 2px; gap: 8px; } .brand-name { font-size: 22px; } .brand-sub { font-size: 8px; letter-spacing: 0; } .brand-icon { width: 32px; height: 36px; } .workspace .new-session { font-size: 10px; margin-top: 24px; } .session-sub text { display: none; } .rail-note { font-size: 12px; } .conversation-header { padding: 20px 15px 16px; } .topbar { padding: 0 16px; height: 48px; } .page-title { font-size: 20px; max-width: 45vw; } .page-subtitle { line-height: 1.6; font-size: 10px; } .chat-card { margin: 0 10px 12px; border-radius: 12px; } .companion-bar { padding: 12px; } .session-count { display: none; } .message-list { padding: 18px 12px 4px; } .message-body { max-width: 88%; } .message-avatar { display: none; } .bubble { font-size: 12px; padding: 10px 12px; } .composer-wrap { padding: 0 9px 10px; } .composer { padding: 12px 10px 8px; } .keyboard-hint, .composer-caption text:last-child { display: none; } .composer-footer { justify-content: flex-end; } .welcome { padding: 0 12px 20px; } .welcome-title { font-size: 20px; } .prompt-list { flex-direction: column; } .island-scene { transform: scale(.8); width: 210px; margin-bottom: 0; } }
@media (max-width: 450px) { .history-rail { width: 115px; padding-left: 5px; padding-right: 5px; } .brand { justify-content: center; } .brand-icon, .brand-sub, .rail-note { display: none; } .history-heading { font-size: 9px; margin-left: 5px; margin-right: 5px; } .workspace .new-session { font-size: 9px; gap: 2px; } .session-title { font-size: 10px; } .workspace .session-open { padding-left: 7px; } .workspace .session-delete { padding: 8px 5px; } .welcome-description { font-size: 10px; } .composer-caption { font-size: 7px; } .text-input { font-size: 12px; } .send-actions { gap: 9px; } }
</style>

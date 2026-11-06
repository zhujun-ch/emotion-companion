<template>
  <view class="app-shell">
    <!-- 左侧导航栏 -->
    <view class="sidebar">
      <view class="brand">
        <view class="brand-mark">
          <text style="color: white; font-size: 20px; font-weight: bold;">心</text>
        </view>
        <view>
          <view class="brand-title">心屿 <text class="brand-en">XINYU</text></view>
          <view class="brand-sub">给情绪，一处安放</view>
        </view>
      </view>

      <view class="nav-label">我的小岛 <text class="nav-en">MY LITTLE ISLAND</text></view>

      <view class="nav-list">
        <view class="nav-item active nav-link" @click="openConversation()">
          <text class="nav-icon">💬</text>
          <view>
            <view>心事倾诉</view>
            <view class="nav-item-en">A space to talk</view>
          </view>
        </view>
        <navigator class="nav-item nav-link" url="/pages/island/index?mode=board">
          <text class="nav-icon">📊</text>
          <view>
            <view>情绪看板</view>
            <view class="nav-item-en">Meet your feelings</view>
          </view>
        </navigator>
        <navigator class="nav-item nav-link" url="/pages/island/index?mode=diary">
          <text class="nav-icon">📝</text>
          <view>
            <view>心情日记</view>
            <view class="nav-item-en">Little moments</view>
          </view>
        </navigator>
      </view>

      <navigator class="nav-item nav-link" url="/pages/island/index?mode=treehole">
        <text class="nav-icon">🌿</text>
        <view>情绪树洞<view class="nav-item-en">Tree hole</view></view>
      </navigator>
      <view class="sidebar-note">
        <text class="spark">✳</text>
        <text class="note-text">慢慢来，\n你已经在向前了。</text>
      </view>
    </view>

    <!-- 右侧主内容区 -->
    <view class="main-shell">
      <!-- 顶部信息栏 -->
      <view class="topbar">
        <view class="breadcrumb">我的小岛 / <text class="active-breadcrumb">心事倾诉</text></view>
        <view class="topbar-right">
          <text class="mode-pill">● 课程演示版</text>
        </view>
      </view>

      <view class="page">
        <view class="mobile-nav">
          <navigator class="mobile-module" url="/pages/island/index?mode=diary">心情日记</navigator>
          <navigator class="mobile-module" url="/pages/island/index?mode=board">情绪看板</navigator>
          <navigator class="mobile-module" url="/pages/island/index?mode=treehole">情绪树洞</navigator>
        </view>
        <!-- 欢迎语 -->
        <view class="page-heading">
          <view>
            <view class="eyebrow">• YOUR SAFE LITTLE SPACE</view>
            <view class="greeting">上午好，旅人 <text class="greeting-spark">✳</text></view>
            <view class="desc">放下外面的忙碌，这一刻，留给你自己。</view>
          </view>
          <button class="new-chat-btn" :disabled="isLoading || isInitializing" @click="startNewConversation">+ 新的倾诉</button>
        </view>

        <!-- 核心聊天卡片区 -->
        <view class="chat-layout">
          <!-- 聊天主体框 -->
          <view class="chat-panel" @click="openConversation()">
            <view class="chat-panel-header">
              <view class="companion-heading">
                <view class="companion-avatar">心</view>
                <view>
                  <view class="companion-name">心屿陪伴</view>
                  <view class="companion-status">点击聊天框，继续和心屿聊聊</view>
                </view>
              </view>
            </view>

            <!-- 聊天记录区 -->
            <scroll-view class="message-space" scroll-y :scroll-top="scrollTop">
              <!-- 空状态：欢迎页 -->
              <view v-if="messages.length === 0" class="chat-welcome">
                <!-- 纯 CSS 绘制的中岛小插画 -->
                <view class="island-art">
                  <view class="sun"></view>
                  <view class="island"></view>
                  <view class="tree"></view>
                </view>
                <view class="welcome-tag">不必逞强，也不用准备好</view>
                <view class="welcome-h2">今天，心里住着什么天气？</view>
                <view class="welcome-p">开心的、烦恼的，或是说不上来的。\n在这里，每一种感受都有被接住的地方。</view>

                <!-- 情绪圆球 -->
                <view class="mood-selector">
                  <view class="mood-item" v-for="m in moods" :key="m.name" @click.stop="openWithMood(m.text)">
                    <view class="mood-face" :style="{ color: m.color, background: m.bg, borderColor: m.color }">{{ m.icon }}</view>
                    <text class="mood-name">{{ m.name }}</text>
                  </view>
                </view>
              </view>

              <!-- 聊天记录列表 -->
              <view v-else class="chat-records">
                <view class="conversation-date">给自己一点时间，慢慢说。</view>
                <view v-for="(msg, index) in messages" :key="index" class="conversation-turn">
                  <!-- 用户发送 -->
                  <view v-if="msg.role === 'user'" class="user-message">
                    <view class="message-bubble">{{ msg.content }}</view>
                  </view>
                  <!-- AI 回复 -->
                  <view v-else class="assistant-message">
                    <view class="companion-avatar">心</view>
                    <view class="assistant-body">
                      <view class="message-bubble">{{ msg.content }}</view>

                    </view>
                  </view>
                </view>
                <view v-if="isLoading" class="sending-state">正在整理一份温柔的回应...</view>
              </view>
            </scroll-view>

            <!-- 底部输入区 -->
            <view class="composer-area">
              <view v-if="error" class="classic-error" @click.stop="retry">{{ error }} · 点击重试</view>
              <button class="chat-entry" @click.stop="openConversation()">
                <text>此刻的你，想说些什么？</text>
                <text class="entry-arrow">开始倾诉 ›</text>
              </button>
            </view>
          </view>

          <!-- 右侧挂件区 -->
          <view class="chat-aside">
            <view class="card journal-invite">
              <view class="section-eyebrow">🖋 留住此刻的感受</view>
              <view class="little-sun"></view>
              <view class="journal-title">每一种心情，\n都有它的意义。</view>
              <view class="journal-desc">不急着变好，先试着看见自己。</view>
            </view>

            <view class="card breathing-card">
              <view class="section-eyebrow">💨 给自己一分钟</view>
              <view class="journal-title" style="font-size: 18px;">让心，慢下来。</view>
              <view class="breath-orbit">
                <view class="breath-circle">
                  <text>呼</text>
                  <text style="font-size: 10px;">吸</text>
                </view>
              </view>
            </view>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { onMounted } from 'vue'
import { useConversations } from '../../composables/useConversations'
const { messages, isLoading, isInitializing, error, scrollTop,
  clearChat, initialize, openConversation, retry } = useConversations()
onMounted(initialize)
function openWithMood(text) {
  openConversation(text)
}
async function startNewConversation() {
  if (isLoading.value || isInitializing.value) return
  await clearChat()
  if (!error.value) openConversation()
}
const moods = [
  { name: '快乐', icon: '☀', color: '#d3a95c', bg: '#fcf4e3', text: '今天发生了一件让我很开心的事情！' },
  { name: '恐惧', icon: '⌇', color: '#8f92c4', bg: '#eceefa', text: '有件事让我有些害怕，想和你说说。' },
  { name: '悲伤', icon: '☂', color: '#699fc4', bg: '#e4f0f7', text: '今天觉得有些难过，想找人倾诉。' },
  { name: '愤怒', icon: '⚡', color: '#cc767a', bg: '#fcebeb', text: '有些事情让我很生气，不知道该怎么办。' },
  { name: '中性', icon: '☁', color: '#8fb5a4', bg: '#ebf3f0', text: '今天和平常一样，想随便聊聊。' },
  { name: '惊奇', icon: '✳', color: '#b48cbd', bg: '#f5edf8', text: '刚发生了一件让我很意外的事。' },
]
</script>

<style>
.chat-panel { cursor: pointer; }
.chat-entry { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin: 0; width: 100%; min-height: 58px; padding: 10px 14px; text-align: left; font-size: 13px; line-height: 1.5; background: #fafbf6; color: #596b50; border: 1px solid #e3e8d9; border-radius: 9px; }
.chat-entry::after { border: none; }
.chat-entry:focus-visible { outline: 2px solid #829b6f; }
.chat-entry text:first-child { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.entry-arrow { flex-shrink: 0; color: #4b6847; font-weight: 600; }
.new-chat-btn { margin: 0; line-height: normal; }
.new-chat-btn::after { border: none; }

.classic-error { color: #a34e44; font-size: 12px; padding: 8px 0; cursor: pointer; }

/* 这里直接采用原项目的优秀 CSS 变量和排版 */
page {
  background-color: #f7f8f4;
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif;
  color: #3c483e;
  --green: #58755e;
  --border: #e8eae2;
  height: 100vh;
  overflow: hidden;
}

.app-shell {
  display: flex;
  height: 100%;
}

/* ============ 左侧导航 ============ */
.sidebar {
  width: 228px;
  background: #f0f3ea;
  border-right: 1px solid #e6eadd;
  display: flex;
  flex-direction: column;
  padding: 35px 21px 0;
}
.brand { display: flex; align-items: center; gap: 10px; padding-left: 9px; }
.brand-mark { width: 37px; height: 37px; background: #58755e; border-radius: 12px; display: flex; align-items: center; justify-content: center;}
.brand-title { font-family: "Noto Serif SC", serif; font-size: 25px; font-weight: 600; letter-spacing: 4px; color: #3c483e; }
.brand-en { font-size: 9px; color: #7e8f78; }
.brand-sub { font-size: 10px; letter-spacing: 2px; color: #8e9b85; margin-top: 4px; }

.nav-label { font-size: 10px; color: #8e9c84; margin: 51px 10px 16px; }
.nav-en { font-size: 7px; color: #a1ab97; margin-left: 5px; }
.nav-list { display: flex; flex-direction: column; gap: 7px;}
.nav-item { display: flex; align-items: center; gap: 14px; padding: 15px 16px; border-radius: 10px; color: #7d8978; }
.nav-item.active { background: #e0e8d8; color: #4e6a50; font-weight: 600; }
.nav-icon { font-size: 18px; }
.nav-item-en { display: block; font-size: 9px; color: #99a190; margin-top: 5px; font-weight: 400; }

.sidebar-note { position: relative; margin: 38px 10px 20px; padding: 20px 12px; border-top: 1px solid #dde5d4; }
.spark { font-size: 30px; color: #96a78a; }
.note-text { display: block; font-family: "Noto Serif SC", serif; font-size: 16px; line-height: 1.9; color: #7c8c71; margin-top: 10px; }

/* ============ 右侧主体 ============ */
.main-shell {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.topbar { height: 76px; border-bottom: 1px solid #e9ece3; display: flex; align-items: center; justify-content: space-between; padding: 0 43px; background: #f9faf6; }
.breadcrumb { font-size: 11px; color: #a0a697; }
.active-breadcrumb { color: #63725d; margin-left: 5px; }
.mode-pill { font-size: 10px; border: 1px solid #dfe5d5; padding: 7px 10px; border-radius: 6px; color: #7b8b70; background: #f1f5eb; }

.page { padding: 35px 42px; flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.page-heading { display: flex; align-items: center; justify-content: space-between; margin-bottom: 29px; }
.eyebrow { font-size: 8px; letter-spacing: 2px; color: #939e86; margin-bottom: 13px; }
.greeting { font-family: "Noto Serif SC", serif; font-size: 27px; color: #394a3c; font-weight: 500; }
.greeting-spark { color: #b4be97; margin-left: 5px; }
.desc { font-size: 12px; color: #939b8c; margin-top: 7px; }
.new-chat-btn { font-size: 11px; padding: 9px 15px; border: 1px solid #e0e6d7; border-radius: 7px; color: #77866b; background: #fbfcf8; cursor: pointer;}

/* ============ 聊天区布局 ============ */
.chat-layout { display: flex; gap: 22px; flex: 1; min-height: 0; overflow: hidden; }
.chat-panel { flex: 1; min-width: 0; background: #fffefa; border: 1px solid #e8eae2; border-radius: 13px; display: flex; flex-direction: column; overflow: hidden; box-shadow: 0 3px 10px rgba(83,99,67,0.02); }
.chat-panel-header { height: 76px; padding: 0 25px; display: flex; align-items: center; border-bottom: 1px solid #eeefe8; }
.companion-heading { display: flex; align-items: center; gap: 10px; }
.companion-avatar { width: 34px; height: 34px; border-radius: 11px; background: #eaf0e1; color: #7f9b70; display: flex; align-items: center; justify-content: center; font-weight: bold; }
.companion-name { font-size: 12px; font-weight: 500; color: #3c483e; }
.companion-status { font-size: 9px; color: #9aa88d; margin-top: 4px; }

.message-space { flex: 1; min-height: 0; width: 100%; box-sizing: border-box; padding: 12px 27px 24px; overflow-y: auto; background: #fffefa; }
.chat-welcome { text-align: center; padding-top: 30px; }

/* 纯 CSS 绘制中岛插画 */
.island-art { width: 100%; height: 167px; position: relative; margin-bottom: 10px;}
.sun { width: 40px; height: 40px; background: #E1C58D; border-radius: 50%; position: absolute; right: 80px; top: 20px; opacity: 0.8;}
.island { width: 200px; height: 50px; background: #D8E4DB; border-radius: 50%; position: absolute; bottom: 20px; left: 50%; transform: translateX(-50%);}
.tree { width: 4px; height: 40px; background: #728E71; position: absolute; bottom: 50px; left: 50%; border-radius: 2px;}
.tree::before { content: ''; position: absolute; width: 30px; height: 20px; background: #91A585; border-radius: 50%; top: -10px; left: -13px;}

.welcome-tag { display: block; color: #a0a98d; font-size: 9px; letter-spacing: 2px; }
.welcome-h2 { font-family: "Noto Serif SC", serif; font-size: 22px; color: #536649; margin-top: 15px; font-weight: 500; }
.welcome-p { font-size: 11px; color: #9aa18f; margin-top: 12px; line-height: 2; }

.mood-selector { display: flex; justify-content: center; gap: 27px; margin: 32px 0; }
.mood-item { display: flex; flex-direction: column; align-items: center; gap: 8px; }
.mood-face { width: 41px; height: 41px; border-radius: 50%; border: 1px solid; display: flex; align-items: center; justify-content: center; font-size: 20px; }
.mood-name { font-size: 10px; color: #8c947f; }

/* 聊天记录气泡 */
.chat-records { padding-top: 10px; }
.conversation-date { text-align: center; font-size: 9px; color: #a8b19e; margin-bottom: 20px; }
.conversation-turn { margin-bottom: 26px; }
.user-message { display: flex; flex-direction: column; align-items: flex-end; margin-bottom: 20px; }
.user-message .message-bubble { background: #e9efdf; border-radius: 11px 2px 11px 11px; padding: 12px 16px; max-width: 85%; color: #617451; font-size: 12px; line-height: 2; }
.assistant-message { display: flex; align-items: flex-start; gap: 10px; }
.assistant-message .companion-avatar { flex-shrink: 0; width: 29px; height: 29px; border-radius: 9px; background: #edf2e5; color: #8ba47b; font-size: 12px; }
.assistant-body { min-width: 0; max-width: calc(100% - 39px); }
.message-bubble { overflow-wrap: anywhere; }
.assistant-body .message-bubble { color: #748168; border: 1px solid #edf0e4; background: #fdfef9; border-radius: 2px 11px 11px 11px; padding: 13px 16px; font-size: 12px; line-height: 2; }
.message-meta { margin-top: 7px; }
.emotion-badge { font-size: 9px; color: #8fa17a; background: #edf2e6; padding: 4px 8px; border-radius: 4px; }
.sending-state { color: #a1ad90; font-size: 10px; }

/* 底部输入框 */
.composer-area { padding: 0 23px 16px; }

/* 右侧挂件 */
.chat-aside { width: 258px; display: flex; flex-direction: column; gap: 17px; }
.card { border: 1px solid #e8eae2; border-radius: 13px; background: #fffefa; padding: 22px 21px; }
.section-eyebrow { font-size: 10px; color: #839176; }
.journal-invite { background: #f1f4e9; position: relative; overflow: hidden; }
.journal-title { font-family: "Noto Serif SC", serif; font-size: 22px; color: #607352; margin: 19px 0 12px; line-height: 1.6; }
.journal-desc { font-size: 10px; color: #95a083; }
.little-sun { position: absolute; right: -4px; top: 50px; width: 60px; height: 60px; background: #e3e7c9; border-radius: 50%; opacity: 0.7; }

.breathing-card { text-align: center; }
.breath-orbit { width: 104px; height: 104px; margin: 23px auto 17px; border: 1px solid #e9ecde; border-radius: 50%; display: flex; align-items: center; justify-content: center; }
.breath-circle { width: 67px; height: 67px; border-radius: 50%; background: radial-gradient(circle, #e5ecd8, #eaf0e1); display: flex; flex-direction: column; align-items: center; justify-content: center; color: #9aab83; }
.nav-link { cursor: pointer; }
.nav-link:hover { background: #e0e8d8; }
.mobile-nav { display: none; }
@media (max-width: 760px) {
  .sidebar, .chat-aside { display: none; }
  .topbar { height: 52px; padding: 0 16px; }
  .page { padding: 14px; overflow: auto; }
  .page-heading { flex-wrap: wrap; gap: 10px; }
  .message-space { padding: 12px 16px 18px; }
  .mood-selector { flex-wrap: wrap; gap: 12px; }
  .mobile-nav { display: flex; gap: 8px; margin: 0 0 16px; }
  .mobile-module { flex: 1 1 0; min-width: 0; text-align: center; padding: 8px 0; font-size: 13px; line-height: 1.5; background: #e4edda; color: #345642; }
}
/* #ifdef MP-WEIXIN */
.app-shell { box-sizing: border-box; padding-top: calc(var(--status-bar-height, 24px) + 44px); }
/* #endif */
</style>

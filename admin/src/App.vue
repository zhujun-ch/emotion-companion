<template>
  <div class="shell">
    <aside>
      <div class="brand"><span class="mark">心</span><div><strong>心屿</strong><small>内容管理端</small></div></div>
      <p class="aside-label">树洞管理</p>
      <button v-for="tab in tabs" :key="tab.id" :disabled="!token" :class="{ active: selected === tab.id }" @click="select(tab.id)">{{ tab.name }}</button>
      <small class="demo-label">课程演示 · 虚构内容</small>
    </aside>
    <main>
      <header><span>心屿 / 树洞审核台</span><button v-if="token" @click="logout">退出登录</button></header>
      <section class="content">
        <div class="hero">
          <span>MODERATION DESK</span>
          <h1>{{ token ? currentTab.name : '登录审核台' }}</h1>
          <p>{{ token ? '处理需要复核的匿名留言，或下架已发布的内容。' : '使用课程演示审核员账号进入管理端。' }}</p>
        </div>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <form v-if="!token" class="panel login" @submit.prevent="login">
          <label>审核员账号<input v-model.trim="username" autocomplete="username" required></label>
          <label>演示口令<input v-model="password" type="password" autocomplete="current-password" required></label>
          <button class="primary" :disabled="busy">登录</button>
        </form>
        <template v-else>
          <div class="summary">
            <div v-for="tab in tabs" :key="tab.id" class="metric"><small>{{ tab.name }}</small><strong>{{ count(tab.id) }}</strong></div>
          </div>
          <div class="queue-heading"><h2>投稿列表</h2><button :disabled="busy" @click="refresh">刷新队列</button></div>
          <p v-if="!visible.length" class="panel empty">当前没有稿件。</p>
          <article v-for="item in visible" :key="item.id" class="panel post">
            <div class="meta"><span class="tag">{{ item.kind }}</span><span>#{{ item.id }} · {{ item.day }}</span><strong>{{ labels[item.state] }}</strong></div>
            <p class="body">{{ item.body }}</p>
            <p class="reason">{{ item.reason }}</p>
            <div v-if="item.state === 'pending'" class="actions">
              <input v-model="reasons[item.id]" maxlength="120" :aria-label="'稿件 ' + item.id + ' 的驳回原因'" placeholder="驳回原因（通过时可留空）">
              <button class="danger" :disabled="busy" @click="review(item, 'reject')">驳回</button>
              <button class="primary" :disabled="busy" @click="review(item, 'approve')">通过并发布</button>
            </div>
            <div v-if="item.state === 'published'" class="actions">
              <button class="danger" :disabled="busy" @click="review(item, 'remove')">下架</button>
            </div>
          </article>
        </template>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const api = (import.meta.env.VITE_API_BASE || 'http://127.0.0.1:5000') + '/api/demo/review'
const tabs = [{ id: 'pending', name: '待审核' }, { id: 'published', name: '已发布' }, { id: 'closed', name: '处理记录' }]
const labels = { pending: '待审核', published: '已发布', blocked: '自动拦截', rejected: '已驳回', removed: '已下架', withdrawn: '已撤回' }
const selected = ref('pending')
const currentTab = computed(() => tabs.find(tab => tab.id === selected.value))
const username = ref('reviewer')
const password = ref('')
const token = ref('')
const posts = ref([])
const reasons = ref({})
const error = ref('')
const busy = ref(false)
const inTab = (item, tab) => tab === 'closed' ? !['pending', 'published'].includes(item.state) : item.state === tab
const count = tab => posts.value.filter(item => inTab(item, tab)).length
const visible = computed(() => posts.value.filter(item => inTab(item, selected.value)))

async function request(path, body) {
  const response = await fetch(api + path, {
    method: body ? 'POST' : 'GET',
    headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token.value },
    body: body && JSON.stringify(body),
  })
  const data = await response.json()
  if (!response.ok) throw new Error(data.message || '演示审核接口不可用')
  return data
}
async function run(action) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try { await action() }
  catch (failure) { error.value = failure instanceof TypeError ? '无法连接演示后端' : failure.message }
  finally { busy.value = false }
}
function login() {
  return run(async () => {
    const data = await request('/login', { username: username.value, password: password.value })
    token.value = data.token
    password.value = ''
    posts.value = await request('/posts')
  })
}
function logout() {
  if (busy.value) return
  token.value = ''
  error.value = ''
  posts.value = []
  reasons.value = {}
  selected.value = 'pending'
}
function refresh() {
  return run(async () => { posts.value = await request('/posts') })
}
function select(tab) {
  selected.value = tab
  error.value = ''
}
function review(item, action) {
  if (action === 'remove' && !window.confirm('将这条留言从树洞下架？')) return
  return run(async () => {
    await request('/posts/' + item.id, { action, reason: action === 'reject' ? reasons.value[item.id] || '' : '' })
    delete reasons.value[item.id]
    posts.value = await request('/posts')
  })
}
</script>

<style>
:root { font-family: system-ui, "Microsoft YaHei", sans-serif; background: #f3f6f4; color: #23372f; }
* { box-sizing: border-box; }
body { margin: 0; }
.shell { min-height: 100vh; display: grid; grid-template-columns: 222px minmax(0, 1fr); }
aside { background: #233d34; color: #fff; padding: 28px 17px; }
.brand { display: flex; gap: 12px; align-items: center; margin-bottom: 46px; }
.brand strong { font-size: 21px; }
.mark { background: #567d69; border-radius: 13px; display: grid; place-items: center; width: 44px; height: 44px; }
small { display: block; font-size: 13px; color: #527363; }
aside small, .aside-label { color: #b9d1c2; font-size: 12px; }
aside button { display: block; width: 100%; text-align: left; background: transparent; color: #e7f0ea; margin: 7px 0; }
aside .active { background: #436859; }
.demo-label { margin-top: 34px; }
header { display: flex; justify-content: space-between; align-items: center; min-height: 63px; background: #fff; padding: 12px 28px; border-bottom: 1px solid #dde6df; font-size: 14px; }
.content { max-width: 1040px; margin: auto; padding: 26px; }
.hero { background: #e1ece4; border-radius: 20px; padding: 24px 27px; }
.hero span { letter-spacing: 2px; font-size: 11px; color: #416657; }
h1 { margin: 5px 0 8px; font-size: 34px; }
.hero p { margin: 0; color: #466456; }
.panel, .metric { background: #fff; border: 1px solid #dce7df; border-radius: 14px; padding: 17px; margin: 14px 0; }
.summary { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
.metric strong { font-size: 27px; }
.queue-heading, .meta, .actions { display: flex; gap: 9px; align-items: center; flex-wrap: wrap; }
.queue-heading { justify-content: space-between; }
h2 { font-size: 19px; margin: 10px 0; }
.meta { font-size: 13px; color: #4b685b; }
.meta strong { margin-left: auto; }
.tag { padding: 4px 8px; border-radius: 7px; background: #e8f1e9; }
.body { white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.6; }
.reason, .empty { color: #506e60; font-size: 13px; }
.actions { justify-content: flex-end; }
.login { max-width: 420px; }
.login label { display: block; margin-bottom: 13px; }
input, button { font: inherit; border-radius: 8px; padding: 8px 12px; }
input { border: 1px solid #cad9d0; color: #263b32; max-width: 100%; }
.login input { display: block; margin-top: 6px; width: 100%; }
.actions input { flex: 1; min-width: min(220px, 100%); }
button { border: 0; background: #e6eee8; color: #274a39; cursor: pointer; }
button:disabled { opacity: .55; cursor: default; }
.primary { background: #31604b; color: #fff; }
.danger, .error { background: #f9eae5; color: #9b3b31; }
.error { padding: 12px; border-radius: 8px; }
@media (max-width: 720px) {
  .shell { grid-template-columns: 1fr; }
  aside { padding: 14px; }
  .brand { margin: 0 0 6px; }
  aside button { display: inline-block; width: auto; }
  .aside-label, .demo-label { display: none; }
  .content { padding: 14px; }
}
</style>

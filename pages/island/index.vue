<template>
  <scroll-view scroll-y class="island-page">
    <view class="island-layout">
      <view class="island-top">
        <button class="island-back" @click="goHome">‹ 首页</button>
        <text class="island-brand">心屿 · {{ platform }}</text>
      </view>
      <view class="island-hero">
        <text class="island-kicker">我的小岛 / {{ area.english }}</text>
        <view class="island-title">{{ area.title }}</view>
        <view class="island-subtitle">{{ area.description }}</view>
      </view>
      <view class="island-tabs">
        <button v-for="(section, key) in areas" :key="key" :class="{ selected: mode === key }" :data-mode="key" @tap.stop="selectTab">
          {{ section.title }}
        </button>
      </view>
      <view v-if="error" class="island-error">{{ error }} <text @click="refresh">重新加载</text></view>
      <view v-if="loading" class="island-empty">正在加载…</view>

      <template v-if="mode === 'diary'">
        <view class="island-card">
          <view class="island-card-title">{{ editingId ? '编辑日记' : '记下今天的感受' }}</view>
          <picker mode="date" :value="diary.day" @change="diary.day = $event.detail.value">
            <view class="island-date">日期　{{ diary.day }}　⌄</view>
          </picker>
          <view class="island-chips">
            <button v-for="mood in moods" :key="mood" :class="{ selected: diary.mood === mood }" @click="diary.mood = mood">{{ mood }}</button>
          </view>
          <textarea v-model="diary.body" class="island-textarea" maxlength="1000" placeholder="今天有什么想记下来的事？" />
          <view class="island-actions">
            <text>{{ diary.body.length }} / 1000</text>
            <button v-if="editingId" @click="resetDiary">取消编辑</button>
            <button class="island-primary" :disabled="busy || !diary.body.trim()" @click="saveDiary">保存日记</button>
          </view>
        </view>
        <view class="island-list-title">我的日记 · {{ diaries.length }} 篇</view>
        <view v-if="!diaries.length && !loading" class="island-empty">还没有日记。可以从一件小事开始。</view>
        <view v-for="entry in diaries" :key="entry.id" class="island-card island-entry">
          <view class="island-meta"><text class="island-tag">{{ entry.mood }}</text> {{ entry.day }}</view>
          <view class="island-body">{{ entry.body }}</view>
          <view class="island-actions">
            <button @click="editDiary(entry)">编辑</button>
            <button :disabled="busy" @click="deleteDiary(entry.id)">删除</button>
          </view>
        </view>
      </template>

      <template v-else-if="mode === 'board'">
        <view class="island-card">
          <view class="island-card-title">记录范围</view>
          <view class="island-chips">
            <button :class="{ selected: range === 7 }" @click="chooseRange(7)">近 7 天</button>
            <button :class="{ selected: range === 30 }" @click="chooseRange(30)">近 30 天</button>
            <button :class="{ selected: range === 90 }" @click="chooseRange(90)">近 90 天</button>
          </view>
          <view class="island-chips">
            <picker mode="date" :value="start" @change="changeRange('start', $event.detail.value)"><view class="island-date">起始 {{ start }}</view></picker>
            <picker mode="date" :value="end" @change="changeRange('end', $event.detail.value)"><view class="island-date">截止 {{ end }}</view></picker>
          </view>
        </view>
        <view class="island-card">
          <view class="island-card-title">心情分布 · {{ filtered.length }} 篇日记</view>
          <view v-if="start > end" class="island-empty">起始日期应早于或等于截止日期。</view>
          <view v-else-if="!filtered.length" class="island-empty">这段时间还没有日记。<text @click="selectMode('diary')">去写日记 ›</text></view>
          <template v-else>
            <view v-for="row in counts" :key="row.label" class="island-chart-row">
              <text>{{ row.label }}</text><view class="island-track"><view class="island-bar" :style="{ width: row.percent + '%' }" /></view><text>{{ row.count }}</text>
            </view>
            <view class="island-list-title">按日记录数</view>
            <view class="island-trend">
              <qiun-data-charts type="line" :chartData="dailyChart" :opts="dailyChartOptions" />
            </view>
            <view v-for="row in daily" :key="row.day" class="island-day"><text>{{ row.day }}</text><text>{{ row.count }} 篇</text></view>
          </template>
        </view>
      </template>

      <template v-else>
        <view class="island-card">
          <view class="island-card-title">写给树洞</view>
          <view class="island-chips">
            <button v-for="kind in kinds" :key="kind" :class="{ selected: post.kind === kind }" @click="post.kind = kind">{{ kind }}</button>
          </view>
          <textarea :value="post.body" @input="updatePostBody" class="island-textarea" maxlength="500"
            placeholder="留一句鼓励，或者说说你此刻的心情。" />
          <view class="island-actions">
            <text v-if="submittingPost">正在审核，请稍等…</text>
            <text v-else>匿名展示 · {{ post.body.length }} / 500</text>
            <button class="island-primary" :disabled="!canSubmitPost" @click="submitPost">匿名提交</button>
          </view>
        </view>
        <view class="island-chips island-feed-tabs">
          <button :class="{ selected: feedTab === 'public' }" @click="setFeedTab('public')">树洞留言</button>
          <button :class="{ selected: feedTab === 'mine' }" @click="setFeedTab('mine')">我的投稿</button>
          <button v-if="reviewerToken" :class="{ selected: feedTab === 'pending' }" @click="setFeedTab('pending')">待审核</button>
          <button v-if="reviewerToken" :class="{ selected: feedTab === 'audit' }" @click="setFeedTab('audit')">处理记录</button>
          <button :disabled="loading || busy" @click="refresh">刷新</button>
        </view>
        <view class="island-review-entry">
          <text v-if="reviewerToken">管理员模式</text>
          <button v-if="reviewerToken" :disabled="busy" @click="logoutReviewer">退出管理</button>
          <button v-else @click="showReviewerLogin = !showReviewerLogin">{{ showReviewerLogin ? '收起登录' : '管理员登录' }}</button>
        </view>
        <view v-if="showReviewerLogin && !reviewerToken" class="island-card">
          <view class="island-card-title">树洞管理员登录</view>
          <input v-model.trim="reviewerName" class="island-review-input" maxlength="40" placeholder="审核员账号" />
          <input v-model="reviewerPassword" class="island-review-input" password maxlength="120" placeholder="演示口令" />
          <view class="island-actions">
            <button class="island-primary" :disabled="busy || !reviewerName || !reviewerPassword" @click="loginReviewer">登录</button>
          </view>
        </view>
        <template v-if="feedTab === 'audit' && reviewerToken">
          <view v-if="!reviewHistory.length && !loading" class="island-empty">暂无处理记录。</view>
          <view v-for="entry in reviewHistory" :key="entry.id" class="island-card island-entry">
            <view class="island-meta">{{ entry.target_type === 'comment' ? '回复 #' + entry.comment_id + ' · 树洞 #' + entry.post_id : '树洞 #' + entry.post_id }} · {{ auditActions[entry.action] }} · {{ entry.actor }}</view>
            <view class="island-body">{{ states[entry.state] }} · {{ entry.reason }}</view>
            <view class="island-meta">{{ entry.created_at }} UTC</view>
          </view>
        </template>
        <template v-else>
          <view v-if="!visiblePosts.length && !loading" class="island-empty">这里暂时没有留言。</view>
          <view v-for="item in visiblePosts" :key="item.id" class="island-card island-entry">
            <view class="island-meta"><text class="island-tag">{{ item.targetType === 'comment' ? '回复' : item.kind }}</text> {{ feedTab === 'public' ? '匿名留言' : states[item.state] }} · {{ item.day }}</view>
            <view v-if="item.targetType === 'comment'" class="island-parent">回复树洞 #{{ item.post_id }}：{{ item.post_body }}</view>
            <view class="island-body">{{ item.body }}</view>
            <view v-if="feedTab === 'mine'" class="island-actions">
              <text>{{ item.reason }}</text>
              <button v-if="['pending', 'published'].includes(item.state)" :disabled="busy" @click="item.targetType === 'comment' ? withdrawComment(item.id) : withdraw(item.id)">撤回</button>
            </view>
            <template v-if="feedTab === 'public'">
              <view class="island-comments">
                <view class="island-meta">回复 · {{ item.comments?.length || 0 }}</view>
                <view v-for="comment in item.comments || []" :key="comment.id" class="island-comment">
                  <view class="island-meta">匿名回复 · {{ comment.day }}</view>
                  <view class="island-body">{{ comment.body }}</view>
                  <button v-if="reviewerToken" class="island-danger" :disabled="busy" @click="prepareReview(comment.id, 'remove', 'comment')">下架回复</button>
                </view>
                <button v-if="replyTarget !== item.id" :disabled="busy" @click="openReply(item.id)">回复这条树洞</button>
                <view v-else class="island-reply-form">
                  <textarea :value="replyBody" @input="updateReplyBody" class="island-textarea" maxlength="300" placeholder="匿名留下鼓励或想说的话，回复同样会先审核。" />
                  <view class="island-actions">
                    <text>{{ submittingReply ? '正在审核，请稍等…' : replyBody.length + ' / 300' }}</text>
                    <button :disabled="busy" @click="closeReply">取消</button>
                    <button class="island-primary" :disabled="busy || !replyBody.trim()" @click="submitReply(item.id)">提交回复</button>
                  </view>
                </view>
              </view>
            </template>
            <view v-if="reviewerToken && feedTab === 'public'" class="island-actions">
              <button class="island-danger" :disabled="busy" @click="prepareReview(item.id, 'remove', 'post')">下架</button>
            </view>
            <view v-if="reviewerToken && feedTab === 'pending'" class="island-actions">
              <text>{{ item.reason }}</text>
              <button class="island-danger" :disabled="busy" @click="prepareReview(item.id, 'reject', item.targetType)">驳回</button>
              <button class="island-primary" :disabled="busy" @click="applyReview(item.id, 'approve', '', item.targetType)">通过并发布</button>
            </view>
            <view v-if="reviewTarget?.id === item.id" class="island-review-form">
              <view class="island-meta">{{ reviewTarget.action === 'reject' ? '驳回' : '下架' }}{{ reviewTarget.type === 'comment' ? '回复' : '留言' }} #{{ reviewTarget.id }}</view>
              <input v-model="reviewReason" class="island-review-input" maxlength="120" placeholder="填写处理原因" />
              <view class="island-actions">
                <button :disabled="busy" @click="reviewTarget = null">取消</button>
                <button class="island-danger" :disabled="busy || !reviewReason.trim()" @click="confirmReview">确认处理</button>
              </view>
            </view>
          </view>
        </template>
      </template>
    </view>
  </scroll-view>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import { beijingDay, demoRequest } from '../../composables/demoPages'
import { reviewerToken, reviewRequest, treeholeRequest } from '../../composables/treehole'
import QiunDataCharts from '../../uni_modules/qiun-data-charts/components/qiun-data-charts/qiun-data-charts.vue'

const areas = {
  diary: { title: '心情日记', english: 'JOURNAL', description: '留一点时间，把今天的感受写下来。演示请使用虚构内容。' },
  board: { title: '情绪看板', english: 'MOOD OVERVIEW', description: '看看自己记下了哪些感受。统计来自日记里的自填心情。' },
  treehole: { title: '情绪树洞', english: 'TREE HOLE', description: '在这里匿名留下一段话。请勿填写联系方式或可识别身份的信息。' },
}
let platform = '网页客户端'
// #ifdef MP-WEIXIN
platform = '微信小程序'
// #endif
const moods = ['平静', '开心', '低落', '紧张', '生气', '惊喜']
const kinds = ['鼓励', '倾诉']
const states = { pending: '待人工审核', blocked: '未通过自动检查', published: '已发布', rejected: '已驳回', removed: '已下架', withdrawn: '已撤回' }
const mode = ref('diary')
const area = computed(() => areas[mode.value])
const diaries = ref([])
const posts = ref({ public: [], mine: [] })
const feedTab = ref('public')
const showReviewerLogin = ref(false)
const reviewerName = ref('admin')
const reviewerPassword = ref('')
const pendingPosts = ref([])
const reviewHistory = ref([])
const reviewTarget = ref(null)
const reviewReason = ref('')
const auditActions = { auto: '自动审核', approve: '通过', reject: '驳回', remove: '下架', withdraw: '撤回' }
const visiblePosts = computed(() => {
  if (feedTab.value === 'pending') return pendingPosts.value
  if (feedTab.value === 'mine') return [
    ...posts.value.mine.map(item => ({ ...item, targetType: 'post' })),
    ...(posts.value.mine_comments || []).map(item => ({ ...item, targetType: 'comment' })),
  ].sort((a, b) => b.id - a.id)
  return posts.value.public
})
watch(reviewerToken, token => {
  if (token) return
  pendingPosts.value = []
  reviewHistory.value = []
  reviewTarget.value = null
  if (['pending', 'audit'].includes(feedTab.value)) feedTab.value = 'public'
})
const newDiary = () => ({ day: beijingDay(), mood: moods[0], body: '' })
const diary = ref(newDiary())
const editingId = ref(null)
const post = ref({ kind: kinds[0], body: '' })
const replyTarget = ref(null)
const replyBody = ref('')
const submittingReply = ref(false)
const error = ref('')
const loading = ref(false)
const busy = ref(false)
const submittingPost = ref(false)
const canSubmitPost = computed(() => !busy.value && post.value.body.trim().length > 0)
let latestRefresh = 0
const range = ref(7)
const start = ref(beijingDay(-6))
const end = ref(beijingDay())
const filtered = computed(() => diaries.value.filter(entry => entry.day >= start.value && entry.day <= end.value))
const counts = computed(() => moods.map(label => {
  const count = filtered.value.filter(entry => entry.mood === label).length
  return { label, count, percent: filtered.value.length ? 100 * count / filtered.value.length : 0 }
}))
const daily = computed(() => [...new Set(filtered.value.map(entry => entry.day))].map(day => ({
  day, count: filtered.value.filter(entry => entry.day === day).length,
})))
const dailyChart = computed(() => {
  const chronological = [...daily.value].reverse()
  return {
    categories: chronological.map(row => row.day),
    series: [{ name: '日记篇数', data: chronological.map(row => row.count) }],
  }
})
const dailyChartOptions = {
  color: ['#6d8963'],
  legend: { show: false },
  xAxis: { labelCount: 4 },
  yAxis: { data: [{ min: 0, tofix: 0 }] },
}

onLoad(options => {
  const requested = options?.mode
  mode.value = Object.prototype.hasOwnProperty.call(areas, requested) ? requested : 'diary'
})
onShow(refresh)

async function refresh() {
  const refreshId = ++latestRefresh
  const selected = mode.value
  const tab = feedTab.value
  loading.value = true
  error.value = ''
  try {
    if (selected === 'treehole') {
      const updatedPosts = await treeholeRequest('/posts')
      if (refreshId !== latestRefresh) return
      posts.value = updatedPosts
      if (reviewerToken.value && tab === 'pending') {
        const [reviewed, comments] = await Promise.all([reviewRequest('/posts'), reviewRequest('/comments')])
        if (refreshId === latestRefresh) pendingPosts.value = [
          ...reviewed.filter(item => item.state === 'pending').map(item => ({ ...item, targetType: 'post' })),
          ...comments.filter(item => item.state === 'pending').map(item => ({ ...item, targetType: 'comment' })),
        ]
      }
      if (reviewerToken.value && tab === 'audit') {
        const history = await reviewRequest('/history')
        if (refreshId === latestRefresh) reviewHistory.value = history
      }
    } else {
      const updatedDiaries = await demoRequest('/diaries')
      if (refreshId === latestRefresh) diaries.value = updatedDiaries
    }
  } catch (failure) {
    if (refreshId === latestRefresh) error.value = failure.message
  } finally {
    if (refreshId === latestRefresh) loading.value = false
  }
}
function selectTab(event) {
  selectMode(event.currentTarget.dataset.mode)
}
function selectMode(key) {
  if (!Object.prototype.hasOwnProperty.call(areas, key) || mode.value === key || busy.value) return
  mode.value = key
  refresh()
}
function goHome() {
  uni.reLaunch({ url: '/pages/index/index' })
}
function chooseRange(days) {
  range.value = days
  start.value = beijingDay(1 - days)
  end.value = beijingDay()
}
function changeRange(field, value) {
  range.value = 0
  if (field === 'start') start.value = value
  else end.value = value
}
function resetDiary() {
  diary.value = newDiary()
  editingId.value = null
}
function editDiary(entry) {
  editingId.value = entry.id
  diary.value = { day: entry.day, mood: entry.mood, body: entry.body }
  uni.showToast({ title: '已载入上方编辑区', icon: 'none' })
}
async function mutate(action) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    await action()
    await refresh()
  } catch (failure) {
    error.value = failure.message
    uni.showToast({ title: failure.message, icon: 'none' })
  } finally {
    busy.value = false
  }
}
function saveDiary() {
  return mutate(async () => {
    const id = editingId.value
    await demoRequest(id ? '/diaries/' + id : '/diaries', id ? 'PUT' : 'POST', diary.value)
    resetDiary()
    uni.showToast({ title: '日记已保存', icon: 'none' })
  })
}
function deleteDiary(id) {
  uni.showModal({
    title: '删除日记', content: '删除后无法恢复。', success(result) {
      if (!result.confirm) return
      mutate(async () => {
        await demoRequest('/diaries/' + id, 'DELETE')
        if (editingId.value === id) resetDiary()
      })
    },
  })
}
function updatePostBody(event) {
  post.value.body = event.detail.value
}
async function submitPost() {
  if (!canSubmitPost.value) return
  const { kind, body } = post.value
  submittingPost.value = true
  try {
    await mutate(async () => {
      const result = await treeholeRequest('/posts', 'POST', { kind, body: body.trim() })
      if (post.value.body === body) post.value.body = ''
      feedTab.value = 'mine'
      reviewTarget.value = null
      uni.showToast({ title: states[result.state], icon: 'none' })
    })
  } finally {
    submittingPost.value = false
  }
}
function withdraw(id) {
  return mutate(() => treeholeRequest('/posts/' + id + '/withdraw', 'POST'))
}
function withdrawComment(id) {
  return mutate(() => treeholeRequest('/comments/' + id + '/withdraw', 'POST'))
}
function openReply(id) {
  replyTarget.value = id
  replyBody.value = ''
}
function closeReply() {
  replyTarget.value = null
  replyBody.value = ''
}
function updateReplyBody(event) {
  replyBody.value = event.detail.value
}
async function submitReply(id) {
  if (busy.value || replyTarget.value !== id || !replyBody.value.trim()) return
  const body = replyBody.value.trim()
  submittingReply.value = true
  try {
    await mutate(async () => {
      const result = await treeholeRequest('/posts/' + id + '/comments', 'POST', { body })
      closeReply()
      if (result.state !== 'published') feedTab.value = 'mine'
      uni.showToast({ title: states[result.state], icon: 'none' })
    })
  } finally {
    submittingReply.value = false
  }
}
function setFeedTab(tab) {
  if (busy.value || feedTab.value === tab) return
  feedTab.value = tab
  reviewTarget.value = null
  refresh()
}
function loginReviewer() {
  return mutate(async () => {
    const { token, role } = await reviewRequest('/login', 'POST', {
      username: reviewerName.value,
      password: reviewerPassword.value,
    })
    if (role !== 'reviewer' || !token) throw new Error('账号没有树洞审核权限')
    reviewerToken.value = token
    reviewerPassword.value = ''
    showReviewerLogin.value = false
  })
}
function logoutReviewer() {
  return mutate(async () => {
    await reviewRequest('/logout', 'POST')
    reviewerToken.value = ''
  })
}
function prepareReview(id, action, type = 'post') {
  reviewReason.value = ''
  reviewTarget.value = { id, action, type }
}
function confirmReview() {
  if (!reviewTarget.value || !reviewReason.value.trim()) return
  const { id, action, type } = reviewTarget.value
  return applyReview(id, action, reviewReason.value.trim(), type)
}
function applyReview(id, action, reason = '', type = 'post') {
  return mutate(async () => {
    await reviewRequest('/' + (type === 'comment' ? 'comments' : 'posts') + '/' + id, 'POST', { action, reason })
    reviewTarget.value = null
    uni.showToast({ title: '审核操作已保存', icon: 'none' })
  })
}
</script>

<style scoped>
.island-page { height: 100vh; background: #f5f6ef; color: #263c31; font-family: system-ui, sans-serif; }
.island-layout { max-width: 790px; padding: 24px 20px 52px; margin: auto; }
.island-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
.island-brand { color: #536957; font-size: 13px; }
.island-hero { padding: 32px 26px; background: #e4edda; border-radius: 23px; }
.island-kicker { color: #536b50; font-size: 11px; letter-spacing: 2px; }
.island-title { margin: 10px 0 7px; font-size: 36px; font-weight: 700; letter-spacing: 2px; }
.island-subtitle { color: #4d6250; font-size: 14px; line-height: 1.65; }
.island-tabs, .island-chips, .island-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.island-tabs { margin: 18px 0; }
.island-chips { margin: 12px 0; }
.island-card { background: #fff; border: 1px solid #dfe7db; border-radius: 18px; padding: 19px; margin-bottom: 12px; }
.island-card-title { font-size: 18px; font-weight: 700; margin-bottom: 10px; }
.island-layout button { margin: 0; padding: 7px 13px; line-height: 1.5; font-size: 13px; color: #345642; background: #edf1e8; border-radius: 10px; cursor: pointer; }
.island-layout button::after { border: none; }
.island-layout .selected { background: #d5e5ce; color: #244832; font-weight: 700; }
.island-layout .island-primary { background: #355f47; color: #fff; }
.island-layout .island-danger { background: #f7ebe6; color: #8e4438; }
.island-review-entry { display: flex; justify-content: flex-end; align-items: center; gap: 8px; margin-bottom: 12px; color: #546f5c; font-size: 12px; }
.island-review-form { border-top: 1px solid #e5eae0; margin-top: 14px; padding-top: 12px; }
.island-review-input { box-sizing: border-box; width: 100%; height: 40px; margin-top: 8px; padding: 0 10px; border: 1px solid #dce5d7; border-radius: 8px; font-size: 14px; }
.island-layout button[disabled] { opacity: .58; }
.island-date { display: inline-block; padding: 8px 11px; background: #f0f3eb; border-radius: 8px; font-size: 13px; cursor: pointer; }
.island-textarea { box-sizing: border-box; width: 100%; height: 104px; padding: 12px; border: 1px solid #dce5d7; border-radius: 10px; font-size: 15px; line-height: 1.6; }
.island-actions { justify-content: flex-end; margin-top: 12px; color: #617366; font-size: 12px; }
.island-actions text { margin-right: auto; }
.island-list-title { margin: 19px 0 10px; font-weight: 700; }
.island-meta { color: #546f5c; font-size: 12px; }
.island-tag { display: inline-block; background: #eaf2e4; padding: 4px 8px; border-radius: 7px; margin-right: 4px; }
.island-body { white-space: pre-wrap; overflow-wrap: anywhere; margin-top: 10px; font-size: 15px; line-height: 1.6; }
.island-parent { color: #597062; font-size: 12px; margin-top: 10px; padding: 9px; background: #f3f6ef; border-radius: 8px; overflow-wrap: anywhere; }
.island-comments { border-top: 1px solid #edf2e8; margin-top: 18px; padding-top: 13px; }
.island-comment { border-left: 3px solid #dce9d8; margin: 12px 0; padding: 3px 0 8px 12px; }
.island-comment .island-body { margin: 5px 0 8px; font-size: 14px; }
.island-reply-form { margin-top: 12px; }
.island-chart-row { display: grid; grid-template-columns: 36px 1fr 24px; align-items: center; gap: 10px; margin: 12px 0; font-size: 13px; }
.island-trend { height: 240px; margin: 12px 0; }
.island-track { background: #edf2e8; border-radius: 6px; height: 12px; overflow: hidden; }
.island-bar { background: #719874; height: 100%; }
.island-day { display: flex; justify-content: space-between; border-bottom: 1px solid #edf2e8; padding: 8px 0; font-size: 13px; }
.island-error, .island-empty { background: #f4efe3; padding: 12px; border-radius: 10px; font-size: 14px; margin: 12px 0; }
.island-error text, .island-empty text { text-decoration: underline; cursor: pointer; }
@media (max-width: 600px) {
  .island-layout { padding: 16px 14px 40px; }
  .island-hero { padding: 23px 19px; }
  .island-title { font-size: 29px; }
  .island-card { padding: 15px; }
}
/* #ifdef MP-WEIXIN */
.island-layout { padding-top: calc(var(--status-bar-height, 24px) + 50px); }
/* #endif */
</style>

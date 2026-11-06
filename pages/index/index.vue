<template>
  <view class="app-shell">
    <!-- 左侧导航栏 -->
    <view class="sidebar">
      <view class="brand">
        <view class="brand-mark">
          <text style="color: white; font-size: 20px; font-weight: bold;">🍃</text>
        </view>
        <view>
          <view class="brand-title">心屿 <text class="brand-en">XINYU</text></view>
          <view class="brand-sub">给情绪，一处安放</view>
        </view>
      </view>
      <view class="nav-label">我的小岛 <text class="nav-en">MY LITTLE ISLAND</text></view>
      <view class="nav-list">
        <!-- 心事倾诉 -->
        <view class="nav-item" :class="{ active: currentTab === 'chat' }" @click="currentTab = 'chat'">
          <text class="nav-icon">💬</text>
          <view>
            <view>心事倾诉</view>
            <view class="nav-item-en">A space to talk</view>
          </view>
        </view>
        <!-- 情绪看板 -->
        <view class="nav-item" :class="{ active: currentTab === 'chart' }" @click="currentTab = 'chart'">
          <text class="nav-icon">📊</text>
          <view>
            <view>情绪看板</view>
            <view class="nav-item-en">Meet your feelings</view>
          </view>
        </view>
        <!-- 心情日记：改为tab切换，不再跳转 -->
        <view class="nav-item" :class="{ active: currentTab === 'diary' }" @click="currentTab = 'diary'">
          <text class="nav-icon">📝</text>
          <view>
            <view>心情日记</view>
            <view class="nav-item-en">Little moments</view>
          </view>
        </view>
      </view>
      <view class="sidebar-note">
        <text class="spark">✳</text>
        <view class="note-text">慢慢来，<br />你已经在向前了。</view>
      </view>
      <view style="margin-top:auto;padding:16px 10px;">
        <view style="font-size:12px;color:#7c8c71;">旅人</view>
        <view style="font-size:10px;color:#99a190;">今天也要照顾好自己</view>
      </view>
    </view>
    <!-- 右侧主内容区 -->
    <view class="main-shell">
      <!-- 顶部信息栏 -->
      <view class="topbar">
        <view class="breadcrumb">我的小岛 > <text class="active-breadcrumb">{{ currentTitle }}</text></view>
        <view class="topbar-right">
          <text class="mode-pill">● 课程演示版</text>
        </view>
      </view>
      <view class="page">
        <!-- ================= 页面一：心事倾诉 ================= -->
        <view v-if="currentTab === 'chat'" class="page-content">
          <!-- 欢迎语 -->
          <view class="page-heading">
            <view>
              <view class="eyebrow">• YOUR SAFE LITTLE SPACE</view>
              <view class="greeting">上午好，旅人 <text class="greeting-spark">✳</text></view>
              <view class="desc">放下外面的忙碌，这一刻，留给你自己。</view>
            </view>
            <view class="new-chat-btn" @click="clearChat">+ 新的倾诉</view>
          </view>
          <!-- 核心聊天卡片区 -->
          <view class="chat-layout">
            <!-- 聊天主体框 -->
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
              <!-- 聊天记录区 -->
              <scroll-view class="message-space" scroll-y :scroll-top="scrollTop">
                <!-- 空状态：欢迎页 -->
                <view v-if="messages.length === 0" class="chat-welcome">
                  <view class="island-art">
                    <view class="sun"></view>
                    <view class="island"></view>
                    <view class="tree"></view>
                  </view>
                  <view class="welcome-tag">不必逞强，也不用准备好</view>
                  <view class="welcome-h2">今天，心里住着什么天气？</view>
                  <view class="welcome-p">开心的、烦恼的，或是说不上来的。<br />在这里，每一种感受都有被接住的地方。</view>
                  <!-- 情绪圆球 -->
                  <view class="mood-selector">
                    <view class="mood-item" v-for="m in moods" :key="m.name" @click="chooseMood(m.text)">
                      <view class="mood-face" :style="{ color: m.color, background: m.bg, borderColor: m.color }">{{ m.icon }}</view>
                      <text class="mood-name">{{ m.name }}</text>
                    </view>
                  </view>
                </view>
                <!-- 聊天记录列表 -->
                <view v-else class="chat-records">
                  <view class="conversation-date">给自己一点时间，慢慢说。</view>
                  <view v-for="(msg, index) in messages" :key="index" class="conversation-turn">
                    <view v-if="msg.role === 'user'" class="user-message">
                      <view class="message-bubble">{{ msg.content }}</view>
                    </view>
                    <view v-else class="assistant-message">
                      <view class="companion-avatar">心</view>
                      <view class="assistant-body">
                        <view class="message-bubble">{{ msg.content }}</view>
                        <view class="message-meta">
                          <text class="emotion-badge">当前情绪：{{ msg.emotion }}</text>
                        </view>
                      </view>
                    </view>
                  </view>
                  <view v-if="isLoading" class="sending-state">正在整理一份温柔的回应...</view>
                </view>
              </scroll-view>
              <!-- 底部输入区 -->
              <view class="composer-area">
                <view class="composer">
                  <textarea
                    class="chat-textarea"
                    v-model="inputText"
                    placeholder="此刻的你，想说些什么？"
                    :disabled="isLoading"
                    maxlength="2000"
                    confirm-type="send"
                    @confirm="sendMessage"
                  />
                  <view class="composer-bottom">
                    <view class="composer-tip">🛡 你的心事，值得被温柔对待</view>
                    <view class="composer-actions">
                      <text class="char-count">{{ inputText.length }}/2000</text>
                      <button class="send-btn" :disabled="!inputText.trim() || isLoading" @click="sendMessage">↑</button>
                    </view>
                  </view>
                </view>
              </view>
            </view>
            <!-- 右侧挂件区 -->
            <view class="chat-aside">
              <view class="card journal-invite">
                <view class="section-eyebrow">🖋 留住此刻的感受</view>
                <view class="little-sun"></view>
                <view class="journal-title">每一种心情，<br />都有它的意义。</view>
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
        <!-- ================= 页面二：情绪看板 ================= -->
        <view v-else-if="currentTab === 'chart'" class="page-content dashboard-page">
          <view class="page-heading">
            <view>
              <view class="eyebrow">• A GENTLE LOOK WITHIN</view>
              <view class="greeting">看见情绪的起伏</view>
              <view class="desc">情绪没有好坏之分，记录是为了更温柔地理解自己。</view>
            </view>
            <view class="time-switcher">
              <text :class="{ active: timeRange === 7 }" @click="changeTimeRange(7)">近 7 天</text>
              <text :class="{ active: timeRange === 30 }" @click="changeTimeRange(30)">近 30 天</text>
              <text :class="{ active: timeRange === 90 }" @click="changeTimeRange(90)">近 90 天</text>
            </view>
          </view>
          <!-- 统计卡片【全部时间范围都保留】 -->
          <view class="stats-grid">
            <view class="stat-card">
              <view class="stat-top"><text>心情记录</text> <text>💬</text></view>
              <view class="stat-number">{{ dashboardData.total_records }}<text class="stat-unit">条</text></view>
              <view class="stat-bottom">每一次表达，都值得被记录</view>
            </view>
            <view class="stat-card">
              <view class="stat-top"><text>关照自己的日子</text> <text>📅</text></view>
              <view class="stat-number">{{ dashboardData.active_days }}<text class="stat-unit">天</text></view>
              <view class="stat-bottom">最近 {{ timeRange }} 天，你为自己停留的时间</view>
            </view>
            <view class="stat-card">
              <view class="stat-top"><text>连续记录</text> <text>🌱</text></view>
              <view class="stat-number">{{ dashboardData.continuous_days || 0 }}<text class="stat-unit">天</text></view>
              <view class="stat-bottom">从今天或昨天起连续记录的天数</view>
            </view>
            <view class="stat-card">
              <view class="stat-top"><text>最常出现的心情</text> <text>🍃</text></view>
              <view class="stat-number" style="font-size: 24px; font-family: serif; margin-top: 18px;">{{ dashboardData.most_frequent }}</view>
              <view class="stat-bottom">
                {{ dashboardData.most_frequent === '等待发现' ? '从第一条心情记录开始' : `出现 ${dashboardData.most_count} 次 - 试着和它多相处一会儿` }}
              </view>
            </view>
          </view>
          <!-- ========== 近7天：空状态面板 ========== -->
          <view v-if="timeRange === 7" class="empty-dashboard">
            <view class="empty-illustration">
              <view class="plant-island"></view>
            </view>
            <view class="empty-title">每一种心情，都能留下轨迹</view>
            <view class="empty-desc">和心屿聊一聊，或写下今天的日记。<br />你的情绪变化，会在这里一点点生长。</view>
            <view class="empty-btn-group">
              <button class="btn-primary" @click="currentTab='chat'">开始倾诉 →</button>
            </view>
          </view>
          <!-- ========== 30/90天：图表 + 表格区域 ========== -->
          <view v-else>
            <view class="charts-container">
              <view class="card chart-card">
                <view class="chart-header">
                  <text style="font-weight: bold; color: #3c483e;">📈 情绪变化</text>
                  <text class="chart-desc">每天的情绪记录条数，看看最近的心情天气。</text>
                  <text class="chart-tag">最近 {{ timeRange }} 天</text>
                </view>
                <view class="chart-wrapper">
                  <qiun-data-charts
                    chart-type="line"
                    :chartData="lineChartData"
                    :opts="lineChartOpts"
                  />
                  <view class="legend">
                    <text><text style="color:#d3a95c">●</text> 快乐</text>
                    <text><text style="color:#8f92c4">●</text> 焦虑</text>
                    <text><text style="color:#699fc4">●</text> 悲伤</text>
                    <text><text style="color:#cc767a">●</text> 愤怒</text>
                    <text><text style="color:#8fb5a4">●</text> 压力大</text>
                  </view>
                </view>
              </view>
              <view class="card chart-card">
                <view class="chart-header">
                  <text style="font-weight: bold; color: #3c483e;">📊 心情的颜色</text>
                  <text class="chart-desc">每一种感受，都构成完整的你。</text>
                </view>
                <view class="donut-chart-container">
                  <view class="donut-circle" :style="donutGradientStyle">
                    <view class="donut-inner">
                      <text class="donut-number">{{ dashboardData.total_records }}</text>
                      <text class="donut-label">次心情记录</text>
                    </view>
                  </view>
                  <view class="color-list">
                    <view class="color-item" v-for="item in colorDist" :key="item.name">
                      <view class="color-left">
                        <text class="color-dot" :style="{ background: item.color }"></text>
                        <text>{{ item.name }}</text>
                      </view>
                      <view class="color-right">
                        <text>{{ item.count }} 条</text>
                        <text class="percent">{{ item.percent }}%</text>
                      </view>
                    </view>
                  </view>
                </view>
              </view>
            </view>
            <!-- ========== 新增：情绪明细表格 ========== -->
            <view class="card table-card">
              <view class="chart-header">
                <text style="font-weight: bold; color: #3c483e;">📋 情绪明细记录</text>
                <text class="chart-desc">记录清单，回看每一段心情</text>
              </view>
              <view class="table-wrap">
                <view class="table-header">
                  <view class="td">日期</view>
                  <view class="td">情绪标签</view>
                  <view class="td">内容</view>
                </view>
                <view v-if="detailList.length ===0" class="table-empty">暂无情绪记录</view>
                <view v-else>
                  <view class="table-row" v-for="(row,idx) in detailList" :key="idx">
                    <view class="td">{{ row.date }}</view>
                    <view class="td">
                      <text class="tag-emotion" :style="{background:emotionColors[row.emotion_label]+'22',color:emotionColors[row.emotion_label]}">{{ row.emotion_label }}</text>
                    </view>
                    <view class="td">{{ row.content }}</view>
                  </view>
                </view>
              </view>
            </view>
          </view>
        </view>
        <!-- ================= 页面三：心情日记 ================= -->
        <view v-else-if="currentTab === 'diary'" class="page-content diary-page">
          <view class="page-heading">
            <view>
              <view class="eyebrow">• SAVE A LITTLE MOMENT</view>
              <view class="greeting">给今天，留一页</view>
              <view class="desc">不需要文采，只需要诚实地写下此刻的自己。</view>
            </view>
            <view class="diary-date">{{ currentDate }}</view>
          </view>
          <view class="diary-layout">
            <!-- 左侧编辑区域 -->
            <view class="diary-main">
              <view class="card diary-edit-card">
                <view class="diary-edit-title">
                  <text>📝 此刻，我的心情是…</text>
                  <view class="diary-edit-tip">选择最接近你感受的一种，没有标准答案。</view>
                </view>
                <view class="diary-mood-row">
                  <view class="diary-mood-item" v-for="m in moods" :key="m.name" :class="{active:selectedDiaryMood === m.name}" @click="selectedDiaryMood = m.name">
                    <view class="diary-mood-icon">{{ m.icon }}</view>
                    <view class="diary-mood-name">{{ m.name }}</view>
                  </view>
                </view>
                <view class="diary-text-area-wrap">
                  <view class="diary-label">想为这一刻，写下什么？</view>
                  <textarea
                    class="diary-textarea"
                    v-model="diaryContent"
                    maxlength="2000"
                    placeholder="可以是今天发生的一件小事，一闪而过的念头，或者只是：今天的我，有一点累。"
                  ></textarea>
                  <view class="diary-bottom-row">
                    <text class="diary-count">{{ diaryContent.length }}/2000字</text>
                    <button class="diary-save-btn" :disabled="!selectedDiaryMood || !diaryContent.trim()" @click="saveDiary">收藏此刻</button>
                  </view>
                </view>
              </view>
              <view class="diary-list-title">收藏的心情 <text class="diary-total">({{ diaryList.length }}篇)</text></view>
              <view class="diary-list-desc">一页一页，是你和自己走过的日子。</view>
              <view v-if="diaryList.length === 0" class="diary-empty-card">
                <view class="empty-feather">🍃</view>
                <view class="empty-title">第一篇日记，等你落笔</view>
                <view class="empty-tip">从一句话开始也很好。</view>
              </view>
              <scroll-view v-else class="diary-scroll-list" scroll-y>
                <view class="diary-item-card" v-for="(item,idx) in diaryList" :key="idx">
                  <view class="diary-item-head">
                    <text class="diary-item-mood" :style="{color:emotionColors[item.mood]}">{{ item.mood }}</text>
                    <text class="diary-item-time">{{ item.time }}</text>
                  </view>
                  <view class="diary-item-content">{{ item.content }}</view>
                </view>
              </scroll-view>
            </view>
            <!-- 右侧侧边寄语 -->
            <view class="diary-aside">
              <view class="quote-card">
                <view class="quote-mark">“</view>
                <view class="quote-text">允许自己<br>有晴天，<br>也有阴天。</view>
                <view class="quote-desc">写下来，不是为了立刻解决什么，<br />只是让心里的声音，有个落脚的地方。</view>
                <view class="quote-vertical">BE KIND TO YOUR MIND</view>
                <view class="quote-circle"></view>
              </view>
            </view>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>
<script setup>
import { ref, nextTick, computed, watch } from 'vue'
const currentTab = ref('chat')
const inputText = ref('')
const messages = ref([])
const isLoading = ref(false)
const scrollTop = ref(0)
const timeRange = ref(7)
const dashboardData = ref({
  total_records: 0,
  active_days: 0,
  continuous_days:0,
  most_frequent: '等待发现',
  most_count:0
})
const colorDist = ref([])
const detailList = ref([])
const emotionColors = {
  '快乐': '#d3a95c', '焦虑': '#8f92c4', '悲伤': '#699fc4', '愤怒': '#cc767a', '压力大': '#8fb5a4'
}
// ---------【新增日记相关变量】----------
const diaryContent = ref('')
const selectedDiaryMood = ref('')
const diaryList = ref([])
const currentDate = ref('')
// 初始化日期
const getNowDate = ()=>{
  const d = new Date()
  const weekArr = ['星期日','星期一','星期二','星期三','星期四','星期五','星期六']
  return `${d.getFullYear()}年${d.getMonth()+1}月${d.getDate()}日${weekArr[d.getDay()]}`
}
currentDate.value = getNowDate()
// 保存日记
const saveDiary = ()=>{
  const diaryItem = {
    mood: selectedDiaryMood.value,
    content: diaryContent.value,
    time: getNowDate()
  }
  diaryList.value.unshift(diaryItem)
  // 后端同步保存
  uni.request({
    url: `http://127.0.0.1:5000/api/save_diary`,
    method: 'POST',
    data:{
      user_id:'wx_user_001',
      mood: selectedDiaryMood.value,
      content: diaryContent.value
    },
    success:()=>{
      uni.showToast({title:"日记已收藏",icon:"success"})
    },
    fail:()=>{
      uni.showToast({title:"本地保存成功，同步后端失败",icon:"none"})
    }
  })
  // 清空输入
  diaryContent.value = ''
  selectedDiaryMood.value = ''
}
// ---------图表相关变量----------
const lineChartData = ref({ categories: [], series: [] })
const lineChartOpts = ref({
  color: ["#d3a95c","#8f92c4","#699fc4","#cc767a","#8fb5a4"],
  padding:[12,12,12,12],
  extra:{
    line:{
      type:"curve"
    }
  },
  legend: { show: false },
  yAxis: { min: 0 },
  tooltip: { show: true }
})
const emotionNameList = ['快乐','焦虑','悲伤','愤怒','压力大']
const convertTrendToChartData = (rawTrend)=>{
  const dateSet = new Set()
  rawTrend.forEach(item=>dateSet.add(item.date))
  const categories = Array.from(dateSet).sort()
  const series = emotionNameList.map(name=>{
    return {
      name: name,
      data: Array(categories.length).fill(0)
    }
  })
  rawTrend.forEach(row=>{
    const dateIndex = categories.indexOf(row.date)
    if(dateIndex === -1) return
    const ser = series.find(s=>s.name === row.emotion_label)
    if(ser){
      ser.data[dateIndex] = row.count
    }
  })
  lineChartData.value = {
    categories: categories,
    series: series
  }
}
// ---------图表变量结束----------
const currentTitle = computed(() => {
  if (currentTab.value === 'chat') return '心事倾诉'
  if (currentTab.value === 'chart') return '情绪看板'
  if (currentTab.value === 'diary') return '心情日记'
  return ''
})
const donutGradientStyle = computed(()=>{
  const total = dashboardData.value.total_records
  if(total <= 0){
    return { background: '#f0f3ea' }
  }
  let deg = 0
  const parts = []
  for(const item of colorDist.value){
    const percent = item.percent
    const endDeg = deg + percent * 3.6
    parts.push(`${emotionColors[item.name]} ${deg}deg ${endDeg}deg`)
    deg = endDeg
  }
  return {
    background: `conic-gradient(${parts.join(',')}, #f0f3ea ${deg}deg)`
  }
})
const moods = [
  { name: '快乐', icon: '☀', color: '#d3a95c', bg: '#fcf4e3', text: '今天发生了一件让我很开心的事情！' },
  { name: '焦虑', icon: '⌇', color: '#8f92c4', bg: '#eceefa', text: '我心里有些烦，总担心事情做不好。' },
  { name: '悲伤', icon: '☂', color: '#699fc4', bg: '#e4f0f7', text: '今天觉得有些难过，想找人倾诉。' },
  { name: '愤怒', icon: '⚡', color: '#cc767a', bg: '#fcebeb', text: '有些事情让我很生气，不知道该怎么办。' },
  { name: '压力大', icon: '☁', color: '#8fb5a4', bg: '#ebf3f0', text: '最近事情太多了，我感觉压力很大。' },
]
const chooseMood = (text) => {
  inputText.value = text
}
const clearChat = () => {
  messages.value = []
}
const scrollToBottom = async () => {
  await nextTick()
  scrollTop.value = 999999
}
const changeTimeRange = (days) => {
  timeRange.value = days
  dashboardData.value = {
    total_records:0,
    active_days:0,
    continuous_days:0,
    most_frequent:'等待发现',
    most_count:0
  }
  colorDist.value = []
  detailList.value = []
  lineChartData.value = { categories:[], series:[] }
  fetchDashboardData()
}
const fetchDashboardData = () => {
  uni.request({
    url: `http://127.0.0.1:5000/api/dashboard_stats?user_id=wx_user_001&days=${timeRange.value}`,
    method: 'GET',
    success: (res) => {
      if (res.data.status === 'success') {
        dashboardData.value = res.data.summary
        const total = res.data.summary.total_records || 0
        const dist = res.data.distribution || []
        detailList.value = res.data.detail_list || []
        colorDist.value = ['快乐', '焦虑', '悲伤', '愤怒', '压力大'].map(name => {
          const found = dist.find(d => d.emotion_label === name)
          const count = found ? found.count : 0
          let percent = total > 0 ? Math.round((count / total) * 100) : 0
          return {
            name,
            count,
            color: emotionColors[name],
            percent
          }
        })
        convertTrendToChartData(res.data.trend ?? [])
      }
    },
    fail:()=>{
      uni.showToast({title:"获取统计数据失败",icon:"none"})
    }
  })
}
watch(currentTab, (newVal) => {
  if (newVal === 'chart') {
    fetchDashboardData()
  }
  if(newVal === 'diary'){
    currentDate.value = getNowDate()
  }
})
const sendMessage = async () => {
  const text = inputText.value.trim()
  if (!text || isLoading.value) return
  messages.value.push({ role: 'user', content: text })
  inputText.value = ''
  isLoading.value = true
  await scrollToBottom()
  uni.request({
    url: 'http://127.0.0.1:5000/api/chat',
    method: 'POST',
    data: {
      user_id: 'wx_user_001',
      text: text
    },
    success: (res) => {
      if (res.data && res.data.status === 'success') {
        messages.value.push({
          role: 'ai',
          content: res.data.reply ?? '暂时没有收到回复',
          emotion: res.data.emotion_label ?? '未知'
        })
      }else{
        messages.value.push({ role: 'ai', content: '服务返回异常，请稍后重试。', emotion: '未知' })
      }
    },
    fail: (err) => {
      messages.value.push({ role: 'ai', content: '网络连接断开，请检查后端。', emotion: '未知' })
    },
    complete: async () => {
      isLoading.value = false
      await scrollToBottom()
    }
  })
}
</script>
<style>
/* 基础样式 */
page {
  background-color: #f7f8f4;
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif;
  color: #3c483e;
  --green: #58755e;
  --border: #e8eae2;
  height: 100vh;
  overflow: hidden;
}
.app-shell { display: flex; height: 100%; }
/* 左侧导航 */
.sidebar { width: 228px; background: #f0f3ea; border-right: 1px solid #e6eadd; display: flex; flex-direction: column; padding: 35px 21px 0; flex-shrink: 0; }
.brand { display: flex; align-items: center; gap: 10px; padding-left: 9px; }
.brand-mark { width: 37px; height: 37px; background: #58755e; border-radius: 12px; display: flex; align-items: center; justify-content: center;}
.brand-title { font-family: "Noto Serif SC", serif; font-size: 25px; font-weight: 600; letter-spacing: 4px; color: #3c483e; }
.brand-en { font-size: 9px; color: #7e8f78; }
.brand-sub { font-size: 10px; letter-spacing: 2px; color: #8e9b85; margin-top: 4px; }
.nav-label { font-size: 10px; color: #8e9c84; margin: 51px 10px 16px; }
.nav-en { font-size: 7px; color: #a1ab97; margin-left: 5px; }
.nav-list { display: flex; flex-direction: column; gap: 7px;}
.nav-item { display: flex; align-items: center; gap: 14px; padding: 15px 16px; border-radius: 10px; color: #7d8978; cursor: pointer; transition: background 0.2s; }
.nav-item.active { background: #e0e8d8; color: #4e6a50; font-weight: 600; }
.nav-item:hover { background: #e5ebde; }
.nav-icon { font-size: 18px; }
.nav-item-en { display: block; font-size: 9px; color: #99a190; margin-top: 5px; font-weight: 400; }
.sidebar-note { position: relative; margin: 38px 10px 20px; padding: 20px 12px; border-top: 1px solid #dde5d4; }
.spark { font-size: 30px; color: #96a78a; }
.note-text { display: block; font-family: "Noto Serif SC", serif; font-size: 16px; line-height: 1.9; color: #7c8c71; margin-top: 10px; }
/* 右侧主体 */
.main-shell { flex: 1; display: flex; flex-direction: column; min-width: 0; width: calc(100% - 228px); }
.topbar { height: 76px; border-bottom: 1px solid #e9ece3; display: flex; align-items: center; justify-content: space-between; padding: 0 43px; background: #f9faf6; }
.breadcrumb { font-size: 11px; color: #a0a697; }
.active-breadcrumb { color: #63725d; margin-left: 5px; }
.mode-pill { font-size: 10px; border: 1px solid #dfe5d5; padding: 7px 10px; border-radius: 6px; color: #7b8b70; background: #f1f5eb; }
.page { padding: 35px 42px; flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.page-content { display: flex; flex-direction: column; height: 100%; overflow: hidden; }
.page-heading { display: flex; align-items: center; justify-content: space-between; margin-bottom: 29px; }
.eyebrow { font-size: 8px; letter-spacing: 2px; color: #939e86; margin-bottom: 13px; }
.greeting { font-family: "Noto Serif SC", serif; font-size: 27px; color: #394a3c; font-weight: 500; }
.greeting-spark { color: #b4be97; margin-left: 5px; }
.desc { font-size: 12px; color: #939b8c; margin-top: 7px; }
.new-chat-btn { font-size: 11px; padding: 9px 15px; border: 1px solid #e0e6d7; border-radius: 7px; color: #77866b; background: #fbfcf8; cursor: pointer;}
/* 聊天区 */
.chat-layout { display: flex; gap: 22px; flex: 1; overflow: hidden; }
.chat-panel { flex: 1; background: #fffefa; border: 1px solid #e8eae2; border-radius: 13px; display: flex; flex-direction: column; overflow: hidden; box-shadow: 0 3px 10px rgba(83,99,67,0.02); }
.chat-panel-header { height: 76px; padding: 0 25px; display: flex; align-items: center; border-bottom: 1px solid #eeefe8; }
.companion-heading { display: flex; align-items: center; gap: 10px; }
.companion-avatar { width: 34px; height: 34px; border-radius: 11px; background: #eaf0e1; color: #7f9b70; display: flex; align-items: center; justify-content: center; font-weight: bold; }
.companion-name { font-size: 12px; font-weight: 500; color: #3c483e; }
.companion-status { font-size: 9px; color: #9aa88d; margin-top: 4px; }
.message-space { flex: 1; height: 0; padding: 12px 27px 24px; overflow-y: auto; background: #fffefa; }
.chat-welcome { text-align: center; padding-top: 30px; }
.island-art { width: 100%; height: 160px; position: relative; margin-bottom: 20px;}
.sun { width: 40px; height: 40px; background: #E1C58D; border-radius: 50%; position: absolute; right: 30%; top: 20px; opacity: 0.8;}
.island { width: 200px; height: 60px; background: #D8E4DB; border-radius: 50%; position: absolute; bottom: 10px; left: 50%; transform: translateX(-50%);}
.tree { width: 6px; height: 40px; background: #728E71; position: absolute; bottom: 50px; left: 50%; transform: translateX(-50%); border-radius: 4px;}
.tree::before { content: ''; position: absolute; width: 36px; height: 24px; background: #91A585; border-radius: 50%; top: -15px; left: -15px;}
.welcome-tag { display: block; color: #a0a98d; font-size: 9px; letter-spacing: 2px; margin-top: 10px;}
.welcome-h2 { font-family: "Noto Serif SC", serif; font-size: 24px; color: #536649; margin-top: 15px; font-weight: 500; }
.welcome-p { font-size: 11px; color: #9aa18f; margin-top: 12px; line-height: 2; }
.mood-selector { display: flex; justify-content: center; gap: 27px; margin: 32px 0; }
.mood-item { display: flex; flex-direction: column; align-items: center; gap: 8px; cursor: pointer; transition: transform 0.2s; }
.mood-item:hover { transform: translateY(-3px); }
.mood-face { width: 41px; height: 41px; border-radius: 50%; border: 1px solid; display: flex; align-items: center; justify-content: center; font-size: 20px; }
.mood-name { font-size: 10px; color: #8c947f; }
.chat-records { padding-top: 10px; }
.conversation-date { text-align: center; font-size: 9px; color: #a8b19e; margin-bottom: 20px; }
.conversation-turn { margin-bottom: 26px; }
.user-message { display: flex; flex-direction: column; align-items: flex-end; margin-bottom: 20px; }
.user-message .message-bubble { background: #e9efdf; border-radius: 11px 2px 11px 11px; padding: 12px 16px; max-width: 85%; color: #617451; font-size: 12px; line-height: 2; }
.assistant-message { display: flex; align-items: flex-start; gap: 10px; }
.assistant-message .companion-avatar { width: 29px; height: 29px; border-radius: 9px; background: #edf2e5; color: #8ba47b; font-size: 12px; }
.assistant-body { max-width: 91%; }
.assistant-body .message-bubble { color: #748168; border: 1px solid #edf0e4; background: #fdfef9; border-radius: 2px 11px 11px 11px; padding: 13px 16px; font-size: 12px; line-height: 2; }
.message-meta { margin-top: 7px; }
.emotion-badge { font-size: 9px; color: #8fa17a; background: #edf2e6; padding: 4px 8px; border-radius: 4px; }
.sending-state { color: #a1ad90; font-size: 10px; }
.composer-area { padding: 0 23px 16px; }
.composer { padding: 14px 15px 10px; background: #fafbf6; border: 1px solid #e3e8d9; border-radius: 9px; }
.chat-textarea { width: 100%; height: 55px; background: transparent; font-size: 12px; color: #596b50; line-height: 1.9; }
.composer-bottom { display: flex; align-items: center; justify-content: space-between; margin-top: 5px; }
.composer-tip { color: #a5b097; font-size: 9px; }
.composer-actions { display: flex; align-items: center; gap: 12px; }
.char-count { font-size: 9px; color: #abb29f; }
.send-btn { background: #6d8963; color: #fff; width: 31px; height: 31px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 18px; padding: 0; border:none; }
.send-btn:disabled{
  background:#b4c2b0;
  color:#dee4dc;
}
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
.breath-circle {
  width: 67px;
  height: 67px;
  border-radius: 50%;
  background: radial-gradient(circle, #e5ecd8, #eaf0e1);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #9aab83;
  animation: breathAnim 4s ease‑in‑out infinite;
}
@keyframes breathAnim{
  0%{transform:scale(0.92);}
  50%{transform:scale(1.1);}
  100%{transform:scale(0.92);}
}
/* 占位符 */
.placeholder-box { flex: 1; background: #fffefa; border: 1px dashed #d8e1cc; border-radius: 13px; display: flex; align-items: center; justify-content: center; color: #a0ab95; font-size: 14px; letter-spacing: 1px; }
/* ============ 情绪看板样式 ============ */
.dashboard-page { overflow-y: auto; padding-right: 10px; }
.time-switcher { background: #f0f3ea; padding: 4px; border-radius: 8px; display: flex; gap: 4px; }
.time-switcher text { font-size: 11px; padding: 6px 16px; border-radius: 6px; cursor: pointer; color: #7b8b70; transition: all 0.3s; }
.time-switcher text.active { background: #fff; color: #3c483e; font-weight: 600; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 24px; }
.stat-card { background: #fffefa; border: 1px solid #e8eae2; border-radius: 13px; padding: 20px; box-shadow: 0 3px 10px rgba(83,99,67,0.02); }
.stat-top { display: flex; justify-content: space-between; color: #939e86; font-size: 12px; margin-bottom: 15px; }
.stat-number { font-size: 36px; font-family: "Noto Serif SC", serif; color: #3c483e; margin-bottom: 10px; }
.stat-unit { font-size: 12px; color: #939e86; margin-left: 5px; font-family: sans-serif; }
.stat-bottom { font-size: 10px; color: #a0a98d; }
.charts-container { display: flex; gap: 20px; height: 420px; margin-bottom:20px; }
.chart-card { flex: 1; padding: 24px; display: flex; flex-direction: column; }
.chart-header { margin-bottom: 20px; display:flex;align-items:center;gap:10px;flex-wrap:wrap;}
.chart-tag {font-size:10px;color:#839176;background:#f0f3ea;padding:3px 6px;border-radius:4px;}
.chart-desc { font-size: 11px; color: #939e86; display: block; margin-top: 5px; }
.chart-wrapper {
  flex: 1;
  position: relative;
  display: flex;
  flex-direction: column;
  height: 320px;
}
.legend { display: flex; justify-content: center; gap: 15px; font-size: 10px; color: #7d8978; margin-top: 15px; }
.donut-chart-container { display: flex; flex-direction: column; align-items: center; flex: 1; justify-content: center;}
.donut-circle { width: 160px; height: 160px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-bottom: 20px; }
.donut-inner { width: 120px; height: 120px; background: #fffefa; border-radius: 50%; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.donut-number { font-size: 32px; font-family: serif; color: #3c483e; }
.donut-label { font-size: 10px; color: #939e86; }
.color-list { width: 100%; margin-top: 10px; }
.color-item { display: flex; justify-content: space-between; font-size: 12px; color: #7d8978; margin-bottom: 12px; }
.color-left { display: flex; align-items: center; gap: 8px; }
.color-dot { width: 6px; height: 6px; border-radius: 50%; }
.color-right { display: flex; align-items:center; gap:6px; }
.percent { font-size: 10px; color:#99a190; }
/* ========== 新增：近7天空状态样式 ========== */
.empty-dashboard{
  background:#fffefa;
  border:1px solid #e8eae2;
  border-radius:13px;
  padding:60px 20px;
  text-align:center;
  flex:1;
  display:flex;
  flex-direction:column;
  align-items:center;
  justify-content:center;
}
.empty-illustration{
  width:220px;
  height:140px;
  position:relative;
  margin-bottom:24px;
}
.plant-island{
  width:100%;
  height:100%;
  background:#e9efdf;
  border-radius:50%;
  position:relative;
  opacity:0.7;
}
.plant-island::after{
  content:"";
  position:absolute;
  width:50px;height:70px;
  background:#8fb5a4;
  border-radius:50% 50% 0 0;
  left:50%;top:20px;
  transform:translateX(-50%);
}
.empty-title{
  font-size:22px;
  color:#536649;
  font-family:"Noto Serif SC",serif;
  margin-bottom:12px;
}
.empty-desc{
  font-size:12px;color:#939b8c;line-height:1.8;margin-bottom:32px;
}
.empty-btn-group{
  display:flex;gap:14px;
}
.btn-primary{
  background:#58755e;color:#fff;padding:10px 20px;border-radius:8px;border:none;font-size:13px;
}
.btn-outline{
  background:#fffefa;color:#58755e;border:1px solid #d8e1cc;padding:10px 20px;border-radius:8px;font-size:13px;
}
/* ========== 新增：明细表格样式 ========== */
.table-card{margin-top:20px;}
.table-wrap{width:100%;}
.table-header{display:flex;background:#f0f3ea;padding:10px 12px;border-radius:8px 8px 0 0;font-size:12px;color:#58755e;font-weight:500;}
.table-row{display:flex;border-bottom:1px solid #f0f3ea;padding:10px 12px;font-size:12px;}
.table-empty{padding:30px 0;text-align:center;color:#a0ab95;font-size:12px;}
.td{flex:1;}
.tag-emotion{padding:3px 8px;border-radius:4px;font-size:11px;}
/* ========== 【新增心情日记专属样式，和截图对齐】 ========== */
.diary-page{
  overflow-y:auto;
  padding-right:10px;
}
.diary-date{
  font-size:11px;
  color:#939b8c;
}
.diary-layout{
  display:flex;
  gap:24px;
  flex:1;
}
.diary-main{
  flex:1;
  display:flex;
  flex-direction:column;
  gap:24px;
}
.diary-edit-card{
  padding:28px;
}
.diary-edit-title{
  margin-bottom:16px;
}
.diary-edit-title text{
  font-size:15px;
  color:#3c483e;
  font-weight:500;
}
.diary-edit-tip{
  font-size:11px;
  color:#939b8c;
  margin-top:4px;
}
.diary-mood-row{
  display:flex;
  gap:14px;
  margin-bottom:24px;
}
.diary-mood-item{
  flex:1;
  text-align:center;
  border:1px solid #e8eae2;
  border-radius:10px;
  padding:14px 6px;
  background:#fffefa;
  cursor:pointer;
}
.diary-mood-item.active{
  background:#f0f3ea;
  border-color:#b8c7aa;
}
.diary-mood-icon{
  font-size:20px;
  margin-bottom:6px;
}
.diary-mood-name{
  font-size:11px;
  color:#7d8978;
}
.diary-label{
  font-size:13px;
  color:#3c483e;
  margin-bottom:10px;
}
.diary-textarea{
  width:100%;
  height:180px;
  border:1px solid #e8eae2;
  border-radius:10px;
  padding:14px;
  font-size:12px;
  background:#fffefa;
}
.diary-bottom-row{
  display:flex;
  justify-content:space-between;
  align-items:center;
  margin-top:10px;
}
.diary-count{
  font-size:10px;
  color:#a0ab95;
}
.diary-save-btn{
  background:#899c80;
  color:#fff;
  border:none;
  padding:8px 16px;
  border-radius:7px;
  font-size:12px;
}
.diary-save-btn:disabled{
  background:#c9d2c4;
}
.diary-list-title{
  font-size:18px;
  color:#3c483e;
  font-family:"Noto Serif SC",serif;
}
.diary-total{
  font-size:12px;
  color:#939b8c;
  font-weight:400;
}
.diary-list-desc{
  font-size:11px;
  color:#939b8c;
  margin-top:4px;
  margin-bottom:16px;
}
.diary-empty-card{
  border:1px dashed #e2e7d9;
  border-radius:13px;
  padding:40px 20px;
  text-align:center;
}
.empty-feather{
  font-size:24px;
  color:#b4be97;
  margin-bottom:12px;
}
.empty-title{
  font-size:17px;
  color:#536649;
  font-family:"Noto Serif SC",serif;
}
.empty-tip{
  font-size:11px;
  color:#939b8c;
  margin-top:8px;
}
.diary-scroll-list{
  height:300px;
}
.diary-item-card{
  border:1px solid #e8eae2;
  border-radius:10px;
  padding:16px;
  margin-bottom:12px;
  background:#fffefa;
}
.diary-item-head{
  display:flex;
  justify-content:space-between;
  margin-bottom:8px;
}
.diary-item-mood{
  font-size:12px;
  font-weight:500;
}
.diary-item-time{
  font-size:10px;
  color:#a0ab95;
}
.diary-item-content{
  font-size:12px;
  color:#5c6655;
  line-height:1.7;
}
.diary-aside{
  width:270px;
}
.quote-card{
  border:1px solid #e8eae2;
  border-radius:13px;
  background:#fffefa;
  padding:30px 24px;
  position:relative;
  overflow:hidden;
}
.quote-mark{
  font-size:28px;
  color:#c7d1b8;
  font-family:serif;
}
.quote-text{
  font-family:"Noto Serif SC",serif;
  font-size:26px;
  line-height:1.7;
  color:#607352;
  margin:12px 0 20px;
}
.quote-desc{
  font-size:11px;
  color:#939b8c;
  line-height:1.7;
}
.quote-vertical{
  position:absolute;
  right:10px;
  top:100px;
  font-size:9px;
  color:#b4be97;
  letter-spacing:2px;
  writing-mode:vertical-rl;
}
.quote-circle{
  width:120px;
  height:120px;
  border:1px solid #e2e7d9;
  border-radius:50%;
  position:absolute;
  right:-30px;
  bottom:-30px;
  opacity:0.6;
}
</style>

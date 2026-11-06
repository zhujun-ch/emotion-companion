<template>
  <view class="dashboard">
    <view class="dashboard-heading">
      <view>
        <view class="eyebrow">情绪看板 / A GENTLE LOOK WITHIN</view>
        <view class="greeting">看见情绪的起伏</view>
        <view class="description">情绪没有好坏之分，记录是为了更温柔地理解自己。统计来自日记里的自填心情。</view>
      </view>
      <view class="time-switcher">
        <button v-for="days in [7, 30, 90]" :key="days" class="range-option" :class="{ active: timeRange === days }" @click="timeRange = days">近 {{ days }} 天</button>
      </view>
    </view>

    <template v-if="ready">
      <view class="stats-grid">
        <view v-for="card in cards" :key="card.title" class="stat-card">
          <view class="stat-top"><text>{{ card.title }}</text><text>{{ card.icon }}</text></view>
          <view class="stat-number" :class="{ 'stat-mood': !card.unit }">{{ card.value }}<text v-if="card.unit" class="stat-unit">{{ card.unit }}</text></view>
          <view class="stat-bottom">{{ card.description }}</view>
        </view>
      </view>

      <view v-if="timeRange === 7 || !details.length" class="empty-dashboard">
        <view class="plant-island" />
        <view class="empty-title">每一种心情，都能留下轨迹</view>
        <view class="description">{{ timeRange === 7 ? '和心屿聊一聊，或写下今天的日记。' : '这段时间还没有日记。可以从记下一件小事开始。' }}</view>
        <view class="empty-actions">
          <button class="dashboard-primary" @click="$emit('open-diary')">去写日记</button>
          <button @click="$emit('open-chat')">开始倾诉 →</button>
        </view>
      </view>

      <template v-else>
        <view class="charts-grid">
          <view class="chart-card">
            <view class="chart-title">📈 情绪变化 <text class="chart-tag">最近 {{ timeRange }} 天</text></view>
            <view class="description">按天查看各类心情的日记篇数。</view>
            <view class="chart-wrapper">
              <qiun-data-charts type="line" :chartData="trend" :opts="lineOptions" />
            </view>
            <view class="legend">
              <text v-for="item in distribution" :key="item.name"><text class="color-dot" :style="{ background: item.color }" />{{ item.name }}</text>
            </view>
          </view>
          <view class="chart-card">
            <view class="chart-title">📊 心情的颜色</view>
            <view class="description">每一种感受，都构成完整的你。</view>
            <view class="donut-circle" :style="donutStyle">
              <view class="donut-inner">
                <text class="donut-number">{{ details.length }}</text>
                <text class="description">次心情记录</text>
              </view>
            </view>
            <view v-for="item in distribution" :key="item.name" class="color-item">
              <text><text class="color-dot" :style="{ background: item.color }" />{{ item.name }}</text>
              <text>{{ item.count }} 条 · {{ Math.round(item.share * 100) }}%</text>
            </view>
          </view>
        </view>

        <view class="chart-card details-card">
          <view class="chart-title">📋 情绪明细记录</view>
          <view class="description">记录清单，回看每一段心情。</view>
          <view class="table-row table-header"><text>日期</text><text>情绪标签</text><text>内容</text></view>
          <view v-for="entry in details" :key="entry.id" class="table-row">
            <text>{{ entry.day }}</text>
            <view><text class="tag-emotion" :style="{ background: moodColors[entry.mood] + '22' }">{{ entry.mood }}</text></view>
            <text class="entry-body">{{ entry.body }}</text>
          </view>
        </view>
      </template>
    </template>
  </view>
</template>

<script setup>
import { computed, ref } from 'vue'
import { beijingDay } from '../../composables/demoPages'
import QiunDataCharts from '../../uni_modules/qiun-data-charts/components/qiun-data-charts/qiun-data-charts.vue'

defineOptions({ options: { virtualHost: true } })
const props = defineProps({ diaries: Array, moods: Array, ready: Boolean })
defineEmits(['open-chat', 'open-diary'])

const timeRange = ref(7)
const moodColors = { 平静: '#8fb5a4', 开心: '#d3a95c', 低落: '#699fc4', 紧张: '#8f92c4', 生气: '#cc767a', 惊喜: '#bc8fb0' }
const dates = computed(() => Array.from({ length: timeRange.value }, (_, index) => beijingDay(index + 1 - timeRange.value)))
const details = computed(() => {
  const firstDay = dates.value[0]
  const lastDay = dates.value.at(-1)
  return props.diaries.filter(entry => entry.day >= firstDay && entry.day <= lastDay)
})
const recordsByDay = computed(() => {
  const days = new Map()
  for (const { day, mood } of details.value) {
    if (!days.has(day)) days.set(day, new Map())
    const counts = days.get(day)
    counts.set(mood, (counts.get(mood) || 0) + 1)
  }
  return days
})
const distribution = computed(() => props.moods.map(name => {
  const count = details.value.filter(entry => entry.mood === name).length
  return { name, color: moodColors[name], count, share: details.value.length ? count / details.value.length : 0 }
}))
const cards = computed(() => {
  const days = recordsByDay.value
  const mostFrequent = [...distribution.value].sort((a, b) => b.count - a.count)[0]
  let index = dates.value.length - 1
  if (!days.has(dates.value[index])) index -= 1
  let streak = 0
  while (index >= 0 && days.has(dates.value[index])) {
    streak += 1
    index -= 1
  }
  return [
    { title: '心情记录', icon: '💬', value: details.value.length, unit: '条', description: '每一次表达，都值得被记录' },
    { title: '关照自己的日子', icon: '📅', value: days.size, unit: '天', description: `最近 ${timeRange.value} 天有日记的天数` },
    { title: '连续记录', icon: '🌱', value: streak, unit: '天', description: '所选范围内从今天或昨天往前数' },
    { title: '最常出现的心情', icon: '🍃', value: mostFrequent.count ? mostFrequent.name : '等待发现', description: mostFrequent.count ? `出现 ${mostFrequent.count} 次` : '从第一条心情记录开始' },
  ]
})
const trend = computed(() => ({
  categories: dates.value.map(day => day.slice(5)),
  series: props.moods.map(name => ({ name, data: dates.value.map(day => recordsByDay.value.get(day)?.get(name) || 0) })),
}))
const lineOptions = {
  color: props.moods.map(mood => moodColors[mood]),
  legend: { show: false },
  dataPointShape: false,
  hideZeroValues: true,
  xAxis: { labelCount: 5 },
  yAxis: { data: [{ min: 0, tofix: 0 }] },
}
const donutStyle = computed(() => {
  let start = 0
  const stops = distribution.value.filter(item => item.count).map(item => {
    const end = start + item.share * 100
    const stop = `${item.color} ${start}% ${end}%`
    start = end
    return stop
  })
  return { background: `conic-gradient(${stops.join(', ')})` }
})
</script>

<style scoped>
.dashboard { display: flex; flex: 1; flex-direction: column; }
.dashboard-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin: 20px 0 29px; }
.eyebrow { color: #63765a; font-size: 11px; letter-spacing: 2px; }
.greeting { margin: 6px 0; color: #3c483e; font: 30px/1.3 "Noto Serif SC", serif; }
.description { color: #687665; font-size: 13px; line-height: 1.6; }
.time-switcher { display: flex; flex-shrink: 0; gap: 4px; padding: 4px; background: #f0f3ea; border-radius: 8px; }
.time-switcher .range-option {
  margin: 0;
  padding: 6px 16px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #7b8b70;
  font: 400 11px/normal -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif;
  cursor: pointer;
  transition: all 0.3s;
}
.time-switcher .range-option::after { border: 0; }
.time-switcher .range-option.active { background: #fff; color: #3c483e; font-weight: 600; box-shadow: 0 2px 5px rgba(0, 0, 0, 0.05); }
.stats-grid, .charts-grid { display: grid; gap: 16px; margin-bottom: 16px; }
.stats-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.charts-grid { grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); }
.stat-card, .chart-card, .empty-dashboard { background: #fffefa; border: 1px solid #e8eae2; border-radius: 13px; padding: 20px; }
.stat-top, .color-item { display: flex; justify-content: space-between; gap: 8px; color: #5f715c; font-size: 13px; }
.stat-number { margin: 8px 0 4px; color: #3c483e; font: 32px/1.2 "Noto Serif SC", serif; }
.stat-mood { font-size: 24px; line-height: 38px; }
.stat-unit { margin-left: 4px; color: #687665; font: 12px system-ui, sans-serif; }
.stat-bottom { color: #687665; font-size: 11px; }
.chart-title { color: #3c483e; font-size: 16px; font-weight: 700; }
.chart-tag { padding: 3px 6px; background: #f0f3ea; border-radius: 4px; color: #687665; font-size: 11px; font-weight: 400; }
.chart-wrapper { height: 280px; margin: 12px 0; }
.legend { display: flex; flex-wrap: wrap; justify-content: center; gap: 6px 12px; color: #5f715c; font-size: 12px; }
.color-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 5px; }
.donut-circle, .donut-inner { display: flex; align-items: center; justify-content: center; border-radius: 50%; }
.donut-circle { width: 148px; height: 148px; margin: 14px auto; background: #f0f3ea; }
.donut-inner { width: 108px; height: 108px; flex-direction: column; background: #fffefa; }
.donut-number { color: #3c483e; font: 30px "Noto Serif SC", serif; }
.color-item { margin-bottom: 6px; }
.table-row { display: grid; grid-template-columns: 88px 70px minmax(0, 1fr); align-items: start; gap: 8px; padding: 10px 8px; border-bottom: 1px solid #f0f3ea; font-size: 12px; }
.table-header { margin-top: 12px; background: #f0f3ea; border-radius: 8px 8px 0 0; color: #4e6750; font-weight: 700; }
.tag-emotion { display: inline-block; padding: 2px 6px; border-radius: 4px; }
.entry-body { white-space: pre-wrap; overflow-wrap: anywhere; }
.empty-dashboard { display: flex; flex: 1 0 auto; flex-direction: column; justify-content: center; padding: 60px 20px; text-align: center; }
.plant-island { position: relative; width: 220px; height: 140px; margin: 0 auto 24px; border-radius: 50%; background: #e9efdf; }
.plant-island::after { content: ''; position: absolute; width: 50px; height: 70px; left: 50%; top: 20px; transform: translateX(-50%); background: #8fb5a4; border-radius: 50% 50% 0 0; }
.empty-title { color: #536649; font: 22px/1.6 "Noto Serif SC", serif; }
.empty-actions { display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; margin-top: 16px; }
.empty-actions button { flex: 0 0 auto; margin: 0; }
.empty-actions .dashboard-primary { background: #58755e; color: #fff; }
@media (max-width: 760px) {
  .dashboard-heading { align-items: flex-start; flex-direction: column; }
  .stats-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
  .charts-grid { grid-template-columns: minmax(0, 1fr); }
  .stat-card, .chart-card { padding: 12px; }
  .empty-dashboard { padding: 36px 16px; }
}
/* #ifdef MP-WEIXIN */
.dashboard-heading { gap: 10px; margin: 12px 0 14px; }
.greeting { font-size: 24px; }
.time-switcher { align-self: stretch; }
.time-switcher .range-option { flex: 1; min-height: 32px; padding: 6px 4px; }
.stats-grid { margin-bottom: 12px; }
.stat-card { padding: 10px; }
.stat-number { margin: 5px 0 3px; font-size: 27px; }
.stat-mood { font-size: 20px; line-height: 32px; }
.empty-dashboard { padding: 18px 12px; }
.plant-island { width: 132px; height: 80px; margin-bottom: 12px; }
.plant-island::after { width: 32px; height: 42px; top: 13px; }
.empty-title { font-size: 18px; }
.empty-actions button { padding: 7px 12px; font-size: 13px; line-height: 1.5; }
.chart-wrapper { height: 225px; }
.table-row { grid-template-columns: 75px 52px minmax(0, 1fr); gap: 5px; padding: 9px 4px; }
/* #endif */
</style>

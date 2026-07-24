<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { api, ApiError } from '@/api'
import { useECharts } from '@/composables/useECharts'
import type { EChartsOption } from 'echarts'
import type {
  LearningOverview,
  PartsDistributionResponse,
  TopicsDistributionResponse,
  TrendGranularity,
  TrendResponse,
} from '@ielts/types'

// ---------------------------------------------------------------------------
// 数据状态
// ---------------------------------------------------------------------------

const loading = ref(false)
const overview = ref<LearningOverview | null>(null)

const trendGranularity = ref<TrendGranularity>('daily')
const trendLoading = ref(false)
const trend = ref<TrendResponse | null>(null)

const distributionMonths = ref(3)
const topicsLoading = ref(false)
const topics = ref<TopicsDistributionResponse | null>(null)
const partsLoading = ref(false)
const parts = ref<PartsDistributionResponse | null>(null)

// 图表 composable（4 个独立 chart 实例）
const trendChart = useECharts()
const topicsChart = useECharts()
const partsChart = useECharts()

// ---------------------------------------------------------------------------
// 工具函数
// ---------------------------------------------------------------------------

/** 秒 → "X 分 Y 秒" 或 "X 小时 Y 分" 友好展示。 */
function formatDuration(seconds: number): string {
  if (seconds <= 0) return '0 分'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  if (m < 60) return s > 0 ? `${m} 分 ${s} 秒` : `${m} 分`
  const h = Math.floor(m / 60)
  const restM = m % 60
  return restM > 0 ? `${h} 小时 ${restM} 分` : `${h} 小时`
}

/** 秒 → 分钟（保留 1 位小数）。 */
function toMinutes(seconds: number): number {
  return Math.round((seconds / 60) * 10) / 10
}

// ---------------------------------------------------------------------------
// 数据加载
// ---------------------------------------------------------------------------

async function fetchOverview(): Promise<void> {
  try {
    overview.value = await api.get<LearningOverview>('/learning/overview')
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : '加载学习概览失败')
  }
}

async function fetchTrend(): Promise<void> {
  trendLoading.value = true
  try {
    const path =
      trendGranularity.value === 'daily'
        ? `/learning/daily?days=30`
        : trendGranularity.value === 'weekly'
          ? `/learning/weekly?weeks=12`
          : `/learning/monthly?months=12`
    trend.value = await api.get<TrendResponse>(path)
    renderTrend()
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : '加载趋势失败')
  } finally {
    trendLoading.value = false
  }
}

async function fetchTopics(): Promise<void> {
  topicsLoading.value = true
  try {
    topics.value = await api.get<TopicsDistributionResponse>(
      `/learning/topics?months=${distributionMonths.value}`,
    )
    renderTopics()
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : '加载主题分布失败')
  } finally {
    topicsLoading.value = false
  }
}

async function fetchParts(): Promise<void> {
  partsLoading.value = true
  try {
    parts.value = await api.get<PartsDistributionResponse>(
      `/learning/parts?months=${distributionMonths.value}`,
    )
    renderParts()
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : '加载 Part 分布失败')
  } finally {
    partsLoading.value = false
  }
}

async function loadAll(): Promise<void> {
  loading.value = true
  await Promise.all([fetchOverview(), fetchTrend(), fetchTopics(), fetchParts()])
  loading.value = false
}

// ---------------------------------------------------------------------------
// 图表渲染
// ---------------------------------------------------------------------------

function renderTrend(): void {
  if (!trend.value) return
  const points = trend.value.points
  const xLabels = points.map((p) => p.date ?? p.week_start ?? p.month ?? '')
  const durationData = points.map((p) => toMinutes(p.duration_seconds))
  const countData = points.map((p) => p.attempt_count)

  const option: EChartsOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
    },
    legend: { data: ['练习时长(分)', '答题次数'], top: 0 },
    grid: { left: 40, right: 40, top: 40, bottom: 40 },
    xAxis: {
      type: 'category',
      data: xLabels,
      axisLabel: { fontSize: 10, rotate: 30 },
    },
    yAxis: [
      {
        type: 'value',
        name: '分钟',
        position: 'left',
      },
      {
        type: 'value',
        name: '次数',
        position: 'right',
      },
    ],
    series: [
      {
        name: '练习时长(分)',
        type: 'line',
        smooth: true,
        data: durationData,
        itemStyle: { color: '#6366f1' },
        areaStyle: { opacity: 0.1 },
      },
      {
        name: '答题次数',
        type: 'bar',
        yAxisIndex: 1,
        data: countData,
        itemStyle: { color: '#34d399' },
      },
    ],
  }
  trendChart.setOptions(option)
}

function renderTopics(): void {
  if (!topics.value) return
  const data = topics.value.topics.map((t) => ({
    name: t.topic_name,
    value: t.attempt_count,
  }))

  const option: EChartsOption = {
    tooltip: { trigger: 'item', formatter: '{b}: {c} 次 ({d}%)' },
    legend: { orient: 'vertical', left: 'left', type: 'scroll' },
    series: [
      {
        name: '主题答题分布',
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['55%', '50%'],
        avoidLabelOverlap: true,
        itemStyle: {
          borderRadius: 6,
          borderColor: '#fff',
          borderWidth: 2,
        },
        label: { show: false },
        emphasis: {
          label: { show: true, fontSize: 14, fontWeight: 'bold' },
        },
        data,
      },
    ],
  }
  topicsChart.setOptions(option)
}

function renderParts(): void {
  if (!parts.value) return
  const data = parts.value.parts
  const option: EChartsOption = {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 40, right: 40, top: 30, bottom: 30 },
    xAxis: {
      type: 'category',
      data: data.map((p) => `Part ${p.part}`),
    },
    yAxis: [
      { type: 'value', name: '次数', position: 'left' },
      { type: 'value', name: '分钟', position: 'right' },
    ],
    series: [
      {
        name: '答题次数',
        type: 'bar',
        data: data.map((p) => p.attempt_count),
        itemStyle: { color: '#6366f1', borderRadius: [4, 4, 0, 0] },
      },
      {
        name: '练习时长(分)',
        type: 'bar',
        yAxisIndex: 1,
        data: data.map((p) => toMinutes(p.duration_seconds)),
        itemStyle: { color: '#f59e0b', borderRadius: [4, 4, 0, 0] },
      },
    ],
  }
  partsChart.setOptions(option)
}

// ---------------------------------------------------------------------------
// 监听与生命周期
// ---------------------------------------------------------------------------

watch(trendGranularity, () => {
  fetchTrend()
})

watch(distributionMonths, () => {
  fetchTopics()
  fetchParts()
})

onMounted(() => {
  loadAll()
})

// ---------------------------------------------------------------------------
// 计算属性（卡片展示）
// ---------------------------------------------------------------------------

const streakLabel = computed(() => {
  if (!overview.value) return '—'
  const { current_days, longest_days } = overview.value.streak
  return `${current_days} 天 / 最长 ${longest_days} 天`
})

const dailyGoalLabel = computed(() => {
  if (!overview.value) return '—'
  const { daily_goal_minutes, daily_completed_minutes } =
    overview.value.goal_progress
  if (daily_goal_minutes === null) return '未设置目标'
  return `${daily_completed_minutes ?? 0} / ${daily_goal_minutes} 分钟`
})

const weeklyGoalLabel = computed(() => {
  if (!overview.value) return '—'
  const { weekly_goal_minutes, weekly_completed_minutes } =
    overview.value.goal_progress
  if (weekly_goal_minutes === null) return '未设置目标'
  return `${weekly_completed_minutes ?? 0} / ${weekly_goal_minutes} 分钟`
})
</script>

<template>
  <main v-loading="loading" class="min-h-screen bg-gray-50 py-8">
    <div class="mx-auto max-w-6xl px-4">
      <header class="mb-6">
        <h1 class="text-2xl font-bold text-gray-900">学习数据</h1>
        <p class="mt-1 text-sm text-gray-500">追踪练习进度，可视化学习轨迹</p>
      </header>

      <!-- 概览卡片 -->
      <section v-if="overview" class="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        <div class="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
          <div class="text-xs text-gray-500">今日练习</div>
          <div class="mt-1 text-2xl font-bold text-gray-900">
            {{ overview.today.practice_count }}
          </div>
          <div class="mt-1 text-xs text-gray-400">
            {{ formatDuration(overview.today.duration_seconds) }}
          </div>
        </div>
        <div class="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
          <div class="text-xs text-gray-500">连续打卡</div>
          <div class="mt-1 text-2xl font-bold text-indigo-600">
            {{ overview.streak.current_days }}
          </div>
          <div class="mt-1 text-xs text-gray-400">{{ streakLabel }}</div>
        </div>
        <div class="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
          <div class="text-xs text-gray-500">累计答题</div>
          <div class="mt-1 text-2xl font-bold text-gray-900">
            {{ overview.cumulative.total_attempts }}
          </div>
          <div class="mt-1 text-xs text-gray-400">
            {{ overview.cumulative.total_recordings }} 条录音
          </div>
        </div>
        <div class="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
          <div class="text-xs text-gray-500">累计练习时长</div>
          <div class="mt-1 text-2xl font-bold text-gray-900">
            {{ formatDuration(overview.cumulative.total_duration_seconds) }}
          </div>
          <div class="mt-1 text-xs text-gray-400">
            {{ overview.cumulative.total_sessions }} 次会话
          </div>
        </div>
      </section>

      <!-- 目标进度 -->
      <section
        v-if="overview"
        class="mb-6 rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100"
      >
        <div class="mb-3 flex items-center justify-between">
          <h2 class="text-base font-semibold text-gray-800">目标达成度</h2>
          <span class="text-xs text-gray-400">基于 active 目标</span>
        </div>
        <div class="grid grid-cols-2 gap-4 text-sm">
          <div>
            <div class="text-gray-500">今日目标</div>
            <div class="mt-1 font-medium text-gray-900">{{ dailyGoalLabel }}</div>
          </div>
          <div>
            <div class="text-gray-500">本周目标</div>
            <div class="mt-1 font-medium text-gray-900">{{ weeklyGoalLabel }}</div>
          </div>
        </div>
      </section>

      <!-- 趋势图 -->
      <section
        v-loading="trendLoading"
        class="mb-6 rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100"
      >
        <div class="mb-4 flex items-center justify-between">
          <h2 class="text-base font-semibold text-gray-800">学习趋势</h2>
          <el-radio-group v-model="trendGranularity" size="small">
            <el-radio-button value="daily">日</el-radio-button>
            <el-radio-button value="weekly">周</el-radio-button>
            <el-radio-button value="monthly">月</el-radio-button>
          </el-radio-group>
        </div>
        <div
          ref="trendChart.chartRef"
          class="h-72 w-full"
          :class="{ 'opacity-50': trendLoading }"
        ></div>
      </section>

      <!-- 分布图（topics / parts） -->
      <section class="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div
          v-loading="topicsLoading"
          class="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100"
        >
          <div class="mb-4 flex items-center justify-between">
            <h2 class="text-base font-semibold text-gray-800">主题分布</h2>
            <el-select v-model="distributionMonths" size="small" class="w-32">
              <el-option :value="1" label="近 1 月" />
              <el-option :value="3" label="近 3 月" />
              <el-option :value="6" label="近 6 月" />
              <el-option :value="12" label="近 12 月" />
            </el-select>
          </div>
          <div
            v-if="topics && topics.topics.length > 0"
            ref="topicsChart.chartRef"
            class="h-72 w-full"
          ></div>
          <el-empty
            v-else
            description="暂无主题分布数据"
            :image-size="80"
          />
        </div>

        <div
          v-loading="partsLoading"
          class="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100"
        >
          <div class="mb-4 flex items-center justify-between">
            <h2 class="text-base font-semibold text-gray-800">Part 分布</h2>
            <span class="text-xs text-gray-400">近 {{ distributionMonths }} 月</span>
          </div>
          <div
            v-if="parts && parts.parts.length > 0"
            ref="partsChart.chartRef"
            class="h-72 w-full"
          ></div>
          <el-empty
            v-else
            description="暂无 Part 分布数据"
            :image-size="80"
          />
        </div>
      </section>
    </div>
  </main>
</template>

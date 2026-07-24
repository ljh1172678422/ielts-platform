<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api, ApiError } from '@/api'
import { useAuthStore } from '@/stores/auth'
import type {
  HomeOverview,
  RecommendationReason,
} from '@ielts/types'

const router = useRouter()
const authStore = useAuthStore()

// ---------------------------------------------------------------------------
// 首页聚合数据（home.md §2，仅登录后加载）
// ---------------------------------------------------------------------------
const loading = ref(false)
const overview = ref<HomeOverview | null>(null)

async function fetchOverview(): Promise<void> {
  loading.value = true
  try {
    overview.value = await api.get<HomeOverview>('/home/overview')
  } catch (err) {
    overview.value = null
    // 401 已由拦截器统一处理（清 token + 跳登录），此处仅提示其他错误
    if (err instanceof ApiError && err.code !== 2001 && err.code !== 2002 && err.code !== 2005) {
      ElMessage.error(err.message || '加载首页数据失败')
    }
  } finally {
    loading.value = false
  }
}

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

/** 推荐来源标签映射（home.md §2.5，ADR-028 5 级短路）。 */
const REASON_META: Record<
  RecommendationReason,
  { label: string; type: 'primary' | 'success' | 'warning' | 'info' | 'danger' }
> = {
  unfinished_session: { label: '继续未完成', type: 'warning' },
  recent_topic: { label: '近期主题', type: 'primary' },
  favorite: { label: '我的收藏', type: 'danger' },
  less_practiced_part: { label: '补弱练习', type: 'success' },
  popular: { label: '热门推荐', type: 'info' },
}

// ---------------------------------------------------------------------------
// 计算属性（卡片展示）
// ---------------------------------------------------------------------------

const dailyGoalLabel = computed(() => {
  if (!overview.value?.goal_progress) return '未设置目标'
  const { daily_goal_minutes, daily_completed_minutes } = overview.value.goal_progress
  if (daily_goal_minutes === null) return '未设置目标'
  return `${daily_completed_minutes ?? 0} / ${daily_goal_minutes} 分钟`
})

const weeklyGoalLabel = computed(() => {
  if (!overview.value?.goal_progress) return '未设置目标'
  const { weekly_goal_minutes, weekly_completed_minutes } = overview.value.goal_progress
  if (weekly_goal_minutes === null) return '未设置目标'
  return `${weekly_completed_minutes ?? 0} / ${weekly_goal_minutes} 分钟`
})

const targetScoreLabel = computed(() => {
  if (!overview.value?.goal_progress?.target_score) return null
  return overview.value.goal_progress.target_score.toFixed(1)
})

const examDateLabel = computed(() => {
  if (!overview.value?.goal_progress?.exam_date) return null
  return overview.value.goal_progress.exam_date
})

/** 距考试天数（exam_date 在未来时显示）。 */
const daysToExam = computed(() => {
  if (!examDateLabel.value) return null
  const exam = new Date(examDateLabel.value)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const diff = Math.ceil((exam.getTime() - today.getTime()) / (1000 * 60 * 60 * 24))
  return diff >= 0 ? diff : null
})

/** 今日目标进度百分比（0-100）。 */
const dailyGoalPercent = computed(() => {
  if (!overview.value?.goal_progress) return 0
  const { daily_goal_minutes, daily_completed_minutes } = overview.value.goal_progress
  if (!daily_goal_minutes) return 0
  return Math.min(100, Math.round(((daily_completed_minutes ?? 0) / daily_goal_minutes) * 100))
})

// ---------------------------------------------------------------------------
// 跳转
// ---------------------------------------------------------------------------

function goLogin(): void {
  router.push({ name: 'login' })
}

function goRegister(): void {
  router.push({ name: 'register' })
}

function goQuestions(): void {
  router.push({ name: 'questions' })
}

function goLearning(): void {
  router.push({ name: 'learning' })
}

function goProfile(): void {
  router.push({ name: 'profile' })
}

/** 继续未完成 session（home.md §2.3 recent_practice）。 */
function continueSession(): void {
  const session = overview.value?.recent_practice.session
  if (session) {
    router.push({ name: 'practice', params: { id: session.id } })
  }
}

/** 点击推荐题目 → 跳详情（home.md §3.4 列表语义，详情走 questions.md §3）。 */
function goRecommendation(id: string): void {
  router.push({ name: 'question-detail', params: { id } })
}

async function handleLogout(): Promise<void> {
  await authStore.logout()
  overview.value = null
  ElMessage.success('已退出登录')
}

// ---------------------------------------------------------------------------
// 生命周期
// ---------------------------------------------------------------------------

onMounted(() => {
  if (authStore.isAuthenticated) {
    void fetchOverview()
  }
})
</script>

<template>
  <main class="min-h-screen bg-gray-50">
    <!-- 未登录：落地页（保留原入口） -->
    <div
      v-if="!authStore.isAuthenticated"
      class="flex min-h-screen flex-col items-center justify-center px-4"
    >
      <div class="w-full max-w-md text-center">
        <h1 class="text-3xl font-bold text-gray-900">IELTS Speaking</h1>
        <p class="mt-2 text-gray-500">雅思口语练习平台 · user-web</p>
        <div class="mt-8 flex justify-center gap-3">
          <el-button type="primary" @click="goLogin">登录</el-button>
          <el-button @click="goRegister">注册</el-button>
        </div>
      </div>
    </div>

    <!-- 已登录：首页聚合仪表盘（home.md §2） -->
    <div v-else v-loading="loading" class="mx-auto max-w-6xl px-4 py-8">
      <!-- 顶部导航 -->
      <header class="mb-6 flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-bold text-gray-900">
            你好，{{ authStore.user?.email }}
          </h1>
          <p class="mt-1 text-sm text-gray-500">继续你的雅思口语练习之旅</p>
        </div>
        <div class="flex gap-2">
          <el-button @click="goQuestions">题库</el-button>
          <el-button @click="goLearning">学习数据</el-button>
          <el-button @click="goProfile">我的</el-button>
          <el-button type="danger" plain @click="handleLogout">退出</el-button>
        </div>
      </header>

      <template v-if="overview">
        <!-- 今日统计卡片 -->
        <section class="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
          <div class="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
            <div class="text-xs text-gray-500">今日练习</div>
            <div class="mt-1 text-2xl font-bold text-gray-900">
              {{ overview.today.practice_count }}
            </div>
            <div class="mt-1 text-xs text-gray-400">次会话</div>
          </div>
          <div class="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
            <div class="text-xs text-gray-500">今日答题</div>
            <div class="mt-1 text-2xl font-bold text-gray-900">
              {{ overview.today.question_count }}
            </div>
            <div class="mt-1 text-xs text-gray-400">
              {{ overview.today.attempt_count }} 次尝试
            </div>
          </div>
          <div class="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
            <div class="text-xs text-gray-500">今日录音</div>
            <div class="mt-1 text-2xl font-bold text-indigo-600">
              {{ overview.today.recording_count }}
            </div>
            <div class="mt-1 text-xs text-gray-400">条</div>
          </div>
          <div class="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
            <div class="text-xs text-gray-500">今日时长</div>
            <div class="mt-1 text-2xl font-bold text-gray-900">
              {{ formatDuration(overview.today.duration_seconds) }}
            </div>
            <div class="mt-1 text-xs text-gray-400">累计练习</div>
          </div>
        </section>

        <!-- 连续打卡 + 目标进度 -->
        <section class="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2">
          <!-- 连续打卡 -->
          <div class="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
            <div class="mb-3 flex items-center justify-between">
              <h2 class="text-base font-semibold text-gray-800">连续打卡</h2>
              <span class="text-xs text-gray-400">坚持就是胜利</span>
            </div>
            <div class="flex items-end gap-4">
              <div>
                <div class="text-4xl font-bold text-indigo-600">
                  {{ overview.streak.current_days }}
                </div>
                <div class="mt-1 text-xs text-gray-500">当前连续天数</div>
              </div>
              <div class="border-l border-gray-200 pl-4">
                <div class="text-2xl font-semibold text-gray-700">
                  {{ overview.streak.longest_days }}
                </div>
                <div class="mt-1 text-xs text-gray-500">最长记录</div>
              </div>
            </div>
          </div>

          <!-- 目标达成度 -->
          <div class="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
            <div class="mb-3 flex items-center justify-between">
              <h2 class="text-base font-semibold text-gray-800">目标达成度</h2>
              <div v-if="targetScoreLabel" class="flex items-center gap-2 text-xs">
                <el-tag size="small" type="warning">目标 {{ targetScoreLabel }}</el-tag>
                <el-tag v-if="daysToExam !== null" size="small" type="danger">
                  距考 {{ daysToExam }} 天
                </el-tag>
              </div>
            </div>
            <div class="space-y-3">
              <div>
                <div class="mb-1 flex justify-between text-xs">
                  <span class="text-gray-500">今日目标</span>
                  <span class="font-medium text-gray-700">{{ dailyGoalLabel }}</span>
                </div>
                <el-progress
                  :percentage="dailyGoalPercent"
                  :stroke-width="8"
                  :show-text="false"
                  color="#6366f1"
                />
              </div>
              <div class="flex justify-between text-xs">
                <span class="text-gray-500">本周目标</span>
                <span class="font-medium text-gray-700">{{ weeklyGoalLabel }}</span>
              </div>
            </div>
          </div>
        </section>

        <!-- 最近练习（未完成 session） -->
        <section
          v-if="overview.recent_practice.has_unfinished"
          class="mb-6 rounded-2xl bg-gradient-to-r from-indigo-50 to-purple-50 p-4 shadow-sm ring-1 ring-indigo-100"
        >
          <div class="flex items-center justify-between">
            <div>
              <div class="flex items-center gap-2">
                <h2 class="text-base font-semibold text-gray-800">继续未完成的练习</h2>
                <el-tag size="small" type="warning">
                  {{ overview.recent_practice.session?.status }}
                </el-tag>
              </div>
              <p class="mt-1 text-sm text-gray-600">
                已完成
                <span class="font-semibold text-indigo-600">
                  {{ overview.recent_practice.session?.completed_questions }}
                </span>
                /
                {{ overview.recent_practice.session?.question_count }}
                题，继续完成剩余题目
              </p>
            </div>
            <el-button type="primary" @click="continueSession">继续练习</el-button>
          </div>
        </section>

        <!-- 推荐题目（ADR-028 5 级短路） -->
        <section class="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
          <div class="mb-4 flex items-center justify-between">
            <h2 class="text-base font-semibold text-gray-800">为你推荐</h2>
            <span class="text-xs text-gray-400">基于练习记录智能匹配</span>
          </div>

          <el-empty
            v-if="overview.recommendations.length === 0"
            description="暂无推荐，去题库探索更多题目"
            :image-size="80"
          >
            <el-button type="primary" @click="goQuestions">浏览题库</el-button>
          </el-empty>

          <div v-else class="space-y-3">
            <article
              v-for="item in overview.recommendations"
              :key="item.id"
              class="cursor-pointer rounded-xl border border-gray-100 p-3 transition hover:border-indigo-200 hover:bg-indigo-50/30"
              @click="goRecommendation(item.id)"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0 flex-1">
                  <div class="mb-1.5 flex flex-wrap items-center gap-2">
                    <el-tag size="small" type="primary">Part {{ item.part }}</el-tag>
                    <el-tag v-if="item.difficulty" size="small" type="warning">
                      难度 {{ item.difficulty }}
                    </el-tag>
                    <el-tag size="small" type="info">{{ item.topic.name }}</el-tag>
                    <el-tag
                      size="small"
                      :type="REASON_META[item.reason].type"
                      effect="light"
                    >
                      {{ REASON_META[item.reason].label }}
                    </el-tag>
                  </div>
                  <h3 class="truncate text-sm font-medium text-gray-900">
                    {{ item.title }}
                  </h3>
                  <p class="mt-1 text-xs text-gray-400">
                    已练习 {{ item.practice_count }} 次
                  </p>
                </div>
                <svg
                  class="mt-1 h-4 w-4 flex-shrink-0 text-gray-300"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <path d="M9 18l6-6-6-6" />
                </svg>
              </div>
            </article>
          </div>
        </section>
      </template>

      <!-- 加载失败兜底（非 401） -->
      <div
        v-else-if="!loading"
        class="flex flex-col items-center justify-center rounded-2xl bg-white py-16 shadow-sm ring-1 ring-gray-100"
      >
        <el-empty description="加载首页数据失败">
          <el-button type="primary" @click="fetchOverview">重试</el-button>
        </el-empty>
      </div>
    </div>
  </main>
</template>

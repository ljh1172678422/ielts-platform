<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, ApiError } from '@/api'
import { useRecorder } from '@/composables/useRecorder'
import type {
  Attempt,
  AttemptStatus,
  PracticeSession,
  SessionQuestion,
} from '@ielts/types'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const acting = ref(false)
const session = ref<PracticeSession | null>(null)
const activeSqId = ref<string | null>(null)

// 录音状态机（单一录音器，绑定当前操作题目，practice.md §5/§6）
const recorder = useRecorder({ maxSeconds: 300 })
// 当前正在录音的 attempt（用于 stop 时上传）
const recordingAttemptId = ref<string | null>(null)
// 录音下载/播放：每 attempt 一个 ObjectURL，停止播放时释放
const playbackUrls = ref<Record<string, string>>({})
const playbackLoading = ref<Record<string, boolean>>({})

const sessionId = computed(() => String(route.params.id))

/** 会话是否可操作（created/in_progress），completed/abandoned/expired 仅可查看。 */
const isOperable = computed(
  () => session.value?.status === 'created' || session.value?.status === 'in_progress',
)

/** 进度统计：已达成终态（submitted/skipped）的题目数。 */
const progress = computed(() => {
  if (!session.value) return { done: 0, total: 0 }
  const total = session.value.questions.length
  const done = session.value.questions.filter((sq) => isSqCompleted(sq)).length
  return { done, total }
})

/** 会话是否可完成：in_progress 且所有题目已达成终态（ADR-015）。 */
const canComplete = computed(
  () =>
    session.value?.status === 'in_progress' &&
    session.value.questions.length > 0 &&
    session.value.questions.every((sq) => isSqCompleted(sq)),
)

async function fetchSession(): Promise<void> {
  loading.value = true
  try {
    session.value = await api.get<PracticeSession>(`/practice/sessions/${sessionId.value}`)
    // 默认激活第一个未完成的题目
    const firstPending = session.value.questions.find((sq) => !isSqCompleted(sq))
    activeSqId.value = firstPending?.id ?? session.value.questions[0]?.id ?? null
  } catch (err) {
    session.value = null
    ElMessage.error(err instanceof ApiError ? err.message : '加载会话失败')
  } finally {
    loading.value = false
  }
}

// ---------------------------------------------------------------------------
// 题目状态判断（practice.md §3.5 续练场景）
// ---------------------------------------------------------------------------

/** sq 是否已达成终态（submitted/skipped），满足 ADR-015 完成会话条件。 */
function isSqCompleted(sq: SessionQuestion): boolean {
  if (sq.attempts.length === 0) return false
  return sq.attempts.some((a) => a.status === 'submitted' || a.status === 'skipped')
}

/** sq 最后一次 attempt（按 attempt_number，practice.md §3.5）。 */
function lastAttempt(sq: SessionQuestion): Attempt | null {
  if (sq.attempts.length === 0) return null
  return [...sq.attempts].sort((a, b) => a.attempt_number - b.attempt_number).at(-1) ?? null
}

/** 题目状态标签（基于 last attempt）。 */
function sqStatusLabel(sq: SessionQuestion): string {
  if (sq.attempts.length === 0) return '未开始'
  const last = lastAttempt(sq)
  if (!last) return '未开始'
  const map: Record<AttemptStatus, string> = {
    pending: '准备中',
    recording: '录音中',
    submitted: '已完成',
    skipped: '已跳过',
    failed: '录音失败',
  }
  return map[last.status] ?? '未知'
}

function sqStatusType(sq: SessionQuestion): '' | 'success' | 'info' | 'warning' | 'danger' {
  if (sq.attempts.length === 0) return 'info'
  const last = lastAttempt(sq)
  if (!last) return 'info'
  if (last.status === 'submitted') return 'success'
  if (last.status === 'skipped') return 'info'
  if (last.status === 'failed') return 'danger'
  return 'warning'
}

// ---------------------------------------------------------------------------
// attempt 状态机操作（practice.md §4/§5/§6）
// ---------------------------------------------------------------------------

/** 创建答题尝试（POST /practice/attempts，practice.md §4）。 */
async function createAttempt(sq: SessionQuestion): Promise<void> {
  if (acting.value) return
  acting.value = true
  try {
    const attempt = await api.post<Attempt>('/practice/attempts', {
      session_question_id: sq.id,
    })
    sq.attempts.push(attempt)
    activeSqId.value = sq.id
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : '创建答题失败')
  } finally {
    acting.value = false
  }
}

/** 更新答题状态（PATCH /practice/attempts/{id}，practice.md §5）。 */
async function updateStatus(
  sq: SessionQuestion,
  target: 'recording' | 'skipped' | 'failed',
): Promise<void> {
  const last = lastAttempt(sq)
  if (!last || acting.value) return
  acting.value = true
  try {
    const updated = await api.patch<Attempt>(`/practice/attempts/${last.id}`, {
      status: target,
    })
    // 替换末尾 attempt
    const idx = sq.attempts.findIndex((a) => a.id === last.id)
    if (idx >= 0) sq.attempts[idx] = updated
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : '更新状态失败')
  } finally {
    acting.value = false
  }
}

/**
 * 开始录音：PATCH attempt status=recording → 启动 MediaRecorder（practice.md §5/§6.4 step 1）。
 * 乐观更新：先本地切 recording 状态，再异步 PATCH，失败回滚。
 */
async function startRecording(sq: SessionQuestion): Promise<void> {
  const last = lastAttempt(sq)
  if (!last || recorder.isBusy.value) return
  // 仅 pending → recording 允许（practice.md §5.3）
  if (last.status !== 'pending') {
    ElMessage.warning('当前状态不可开始录音')
    return
  }

  // 乐观更新 UI：本地先切 recording（practice.md §5.5）
  const originalStatus = last.status
  last.status = 'recording'
  recordingAttemptId.value = last.id

  // 异步 PATCH + 启动 MediaRecorder
  const started = await recorder.start(last.id)
  if (!started) {
    // MediaRecorder 启动失败 → 回滚 attempt 状态
    last.status = originalStatus
    recordingAttemptId.value = null
    return
  }

  try {
    const updated = await api.patch<Attempt>(`/practice/attempts/${last.id}`, {
      status: 'recording',
    })
    // PATCH 返回的 updated 可能含后端时间戳，合并到本地
    const idx = sq.attempts.findIndex((a) => a.id === last.id)
    if (idx >= 0) sq.attempts[idx] = updated
  } catch (err) {
    // PATCH 失败 → 取消录音并回滚
    recorder.cancel()
    recordingAttemptId.value = null
    last.status = originalStatus
    ElMessage.error(err instanceof ApiError ? err.message : '更新录音状态失败')
  }
}

/**
 * 停止录音并上传（practice.md §6.4，事务：recording.uploaded → attempt.submitted → study_records）。
 * stop() 内部完成 multipart 上传，返回更新后的 Attempt。
 */
async function stopRecording(sq: SessionQuestion): Promise<void> {
  const attemptId = recordingAttemptId.value
  if (!attemptId) return
  const updated = await recorder.stop(attemptId)
  recordingAttemptId.value = null
  if (!updated) {
    // 上传失败，状态机已切 error，UI 显示重试按钮
    return
  }
  // 替换末尾 attempt（含 recording + duration_seconds）
  const idx = sq.attempts.findIndex((a) => a.id === attemptId)
  if (idx >= 0) sq.attempts[idx] = updated
  ElMessage.success('录音上传成功')
}

/** 放弃当前录音（不上传，回到 recording→skipped 走 PATCH，practice.md §5.3）。 */
async function abandonRecording(sq: SessionQuestion): Promise<void> {
  recorder.cancel()
  recordingAttemptId.value = null
  // recording → skipped 走 PATCH 状态机（practice.md §5.3 允许）
  await updateStatus(sq, 'skipped')
}

/** 重新录音（submitted/skipped/failed → 新建 attempt，practice.md §4）。 */
async function retryRecording(sq: SessionQuestion): Promise<void> {
  recorder.reset()
  recordingAttemptId.value = null
  await createAttempt(sq)
}

// ---------------------------------------------------------------------------
// 录音下载/播放（practice.md §7，GET /practice/attempts/{id}/recording）
// ---------------------------------------------------------------------------

/**
 * 用 axios 原始 blob 请求下载录音字节（绕过统一信封解包，practice.md §7.4）。
 * 下载接口直接返回 audio 流，不走 { code, message, data } 信封。
 */
async function fetchRecordingBlob(attemptId: string): Promise<Blob> {
  const { default: request } = await import('@/api')
  const response = await request.get(`/practice/attempts/${attemptId}/recording`, {
    responseType: 'blob',
    // blob 模式下不解析 JSON 信封
    transformResponse: [(data) => data],
  })
  // 响应拦截器返回 body.data，blob 模式下 response.data 即 Blob
  return response.data as unknown as Blob
}

/**
 * 加载录音播放 URL（按需下载，practice.md §7.4）。
 * blob URL 缓存到 playbackUrls，离开页面或重新加载时由浏览器自动释放。
 */
async function loadPlayback(sq: SessionQuestion): Promise<void> {
  const last = lastAttempt(sq)
  if (!last || !last.recording) return
  if (playbackUrls.value[last.id]) return // 已加载
  playbackLoading.value[last.id] = true
  try {
    const blob = await fetchRecordingBlob(last.id)
    playbackUrls.value[last.id] = URL.createObjectURL(blob)
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : '录音加载失败')
  } finally {
    playbackLoading.value[last.id] = false
  }
}

/** 触发浏览器下载录音文件（practice.md §7.4）。 */
async function downloadAudio(sq: SessionQuestion): Promise<void> {
  const last = lastAttempt(sq)
  if (!last || !last.recording) return
  const ext = (last.recording.mime_type.split('/')[1] || 'webm').split(';')[0]
  const filename = `attempt-${last.attempt_number}.${ext}`
  try {
    const blob = await fetchRecordingBlob(last.id)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : '录音下载失败')
  }
}

// ---------------------------------------------------------------------------
// 完成会话（practice.md §8，ADR-015）
// ---------------------------------------------------------------------------

/** 完成会话（POST /practice/sessions/{id}/complete，practice.md §8，ADR-015）。 */
async function completeSession(): Promise<void> {
  if (!canComplete.value || acting.value) return
  try {
    await ElMessageBox.confirm('确认完成本次练习会话？完成后无法继续答题。', '完成会话', {
      type: 'warning',
      confirmButtonText: '确认完成',
      cancelButtonText: '取消',
    })
  } catch {
    return // 用户取消
  }
  acting.value = true
  try {
    session.value = await api.post<PracticeSession>(
      `/practice/sessions/${sessionId.value}/complete`,
    )
    ElMessage.success('会话已完成')
  } catch (err) {
    // 5006: 存在未完成题目（ADR-015）—— 理论上 canComplete 已拦截，此处兜底
    ElMessage.error(err instanceof ApiError ? err.message : '完成会话失败')
  } finally {
    acting.value = false
  }
}

// ---------------------------------------------------------------------------
// 工具
// ---------------------------------------------------------------------------

function goBack(): void {
  router.push({ name: 'questions' })
}

function formatDuration(seconds: number | null): string {
  if (seconds == null) return '-'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}分${s}秒`
}

const statusLabel = computed(() => {
  const map: Record<string, string> = {
    created: '待开始',
    in_progress: '进行中',
    completed: '已完成',
    abandoned: '已放弃',
    expired: '已过期',
  }
  return session.value ? (map[session.value.status] ?? session.value.status) : ''
})

const statusType = computed<'' | 'success' | 'info' | 'warning'>(() => {
  const map: Record<string, '' | 'success' | 'info' | 'warning'> = {
    created: 'info',
    in_progress: 'warning',
    completed: 'success',
    abandoned: 'info',
    expired: 'info',
  }
  return session.value ? (map[session.value.status] ?? '') : ''
})

onMounted(fetchSession)
</script>

<template>
  <main class="min-h-screen bg-gray-50 py-8">
    <div class="mx-auto max-w-3xl px-4">
      <header class="mb-6 flex items-center justify-between">
        <el-button link @click="goBack">← 返回题库</el-button>
        <div v-if="session" class="flex items-center gap-3">
          <el-tag :type="statusType">{{ statusLabel }}</el-tag>
          <span class="text-sm text-gray-500">
            进度 {{ progress.done }}/{{ progress.total }}
          </span>
        </div>
      </header>

      <div v-loading="loading">
        <template v-if="session">
          <!-- 会话信息 -->
          <section class="mb-4 rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-100">
            <div class="flex flex-wrap items-center gap-2 text-sm text-gray-600">
              <el-tag size="small" type="primary">模式 {{ session.mode }}</el-tag>
              <el-tag v-if="session.part_filter" size="small">Part {{ session.part_filter }}</el-tag>
              <span>共 {{ session.question_count }} 题</span>
              <span v-if="session.duration_seconds" class="ml-auto text-gray-400">
                用时 {{ formatDuration(session.duration_seconds) }}
              </span>
            </div>
          </section>

          <!-- 题目列表（状态机 UI，practice.md §3.5） -->
          <section class="space-y-4">
            <article
              v-for="sq in session.questions"
              :key="sq.id"
              class="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-100"
              :class="{ 'ring-2 ring-indigo-200': activeSqId === sq.id }"
            >
              <!-- 题目头部 -->
              <div class="mb-3 flex items-center gap-2">
                <span class="flex h-6 w-6 items-center justify-center rounded-full bg-gray-100 text-xs font-medium text-gray-600">
                  {{ sq.sort_order }}
                </span>
                <el-tag size="small" type="info">Part {{ sq.snapshot.part }}</el-tag>
                <el-tag v-if="sq.snapshot.difficulty" size="small" type="warning">
                  难度 {{ sq.snapshot.difficulty }}
                </el-tag>
                <span v-if="sq.snapshot.topic_name" class="text-xs text-gray-400">
                  {{ sq.snapshot.topic_name }}
                </span>
                <el-tag :type="sqStatusType(sq)" size="small" class="ml-auto">
                  {{ sqStatusLabel(sq) }}
                </el-tag>
              </div>

              <h3 class="text-lg font-semibold text-gray-900">{{ sq.snapshot.title }}</h3>
              <p class="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-gray-700">
                {{ sq.snapshot.content }}
              </p>

              <!-- Cue Card -->
              <div v-if="sq.snapshot.cue_card" class="mt-4 rounded-xl bg-amber-50 p-3">
                <p class="whitespace-pre-wrap text-sm text-amber-900">
                  {{ sq.snapshot.cue_card }}
                </p>
              </div>

              <!-- 答题状态机操作区 -->
              <footer v-if="isOperable" class="mt-4 flex flex-wrap items-center gap-2 border-t border-gray-100 pt-3">
                <template v-if="sq.attempts.length === 0">
                  <!-- 无 attempt：开始答题（practice.md §4） -->
                  <el-button type="primary" size="small" :loading="acting" @click="createAttempt(sq)">
                    开始答题
                  </el-button>
                </template>

                <template v-else>
                  <template v-for="a in sq.attempts" :key="a.id">
                    <span class="text-xs text-gray-400">
                      第{{ a.attempt_number }}次 · {{ a.status }}
                      <span v-if="a.duration_seconds">（{{ formatDuration(a.duration_seconds) }}）</span>
                    </span>
                  </template>

                  <!-- 基于 last attempt 状态显示操作（practice.md §5.3 状态机） -->
                  <template v-if="lastAttempt(sq)?.status === 'pending'">
                    <el-button
                      type="primary"
                      size="small"
                      :loading="recorder.isBusy.value"
                      @click="startRecording(sq)"
                    >
                      开始录音
                    </el-button>
                    <el-button size="small" :loading="acting" @click="updateStatus(sq, 'skipped')">
                      跳过
                    </el-button>
                  </template>

                  <template v-else-if="lastAttempt(sq)?.status === 'recording' && recordingAttemptId === lastAttempt(sq)?.id">
                    <!-- 录音中：显示计时器 + 停止/放弃（practice.md §6） -->
                    <span class="inline-flex items-center gap-1 text-sm font-mono text-rose-600">
                      <span class="inline-block h-2 w-2 animate-pulse rounded-full bg-rose-500" />
                      {{ recorder.elapsedLabel.value }}
                    </span>
                    <el-button
                      type="success"
                      size="small"
                      :loading="recorder.isBusy.value"
                      @click="stopRecording(sq)"
                    >
                      停止并上传
                    </el-button>
                    <el-button size="small" :loading="acting" @click="abandonRecording(sq)">
                      放弃并跳过
                    </el-button>
                  </template>

                  <template v-else-if="lastAttempt(sq)?.status === 'recording'">
                    <!-- 续练恢复：recording 状态但本地未在录音（断线重连场景） -->
                    <el-button size="small" :loading="acting" @click="updateStatus(sq, 'skipped')">
                      放弃并跳过
                    </el-button>
                    <el-button size="small" type="danger" :loading="acting" @click="updateStatus(sq, 'failed')">
                      标记失败
                    </el-button>
                    <span class="text-xs text-gray-400">如需重新录音，请先放弃或标记失败</span>
                  </template>

                  <template v-else-if="lastAttempt(sq)?.status === 'failed'">
                    <el-button size="small" :loading="acting" @click="retryRecording(sq)">
                      重新答题
                    </el-button>
                  </template>

                  <template v-else-if="lastAttempt(sq)?.status === 'skipped'">
                    <el-button size="small" :loading="acting" @click="retryRecording(sq)">
                      重新答题
                    </el-button>
                  </template>

                  <template v-else-if="lastAttempt(sq)?.status === 'submitted'">
                    <el-button size="small" :loading="acting" @click="retryRecording(sq)">
                      重新录音
                    </el-button>
                  </template>
                </template>
              </footer>

              <!-- 录音播放/下载区（practice.md §7，仅 submitted 且有 recording 时显示） -->
              <div
                v-if="lastAttempt(sq)?.status === 'submitted' && lastAttempt(sq)?.recording"
                class="mt-3 rounded-xl bg-gray-50 p-3"
              >
                <div class="flex flex-wrap items-center gap-2">
                  <span class="text-xs text-gray-500">录音回放</span>
                  <span v-if="lastAttempt(sq)?.recording?.duration_seconds" class="text-xs text-gray-400">
                    时长 {{ formatDuration(lastAttempt(sq)?.recording?.duration_seconds ?? null) }}
                  </span>
                  <el-button
                    link
                    type="primary"
                    size="small"
                    :loading="playbackLoading[lastAttempt(sq)!.id]"
                    @click="loadPlayback(sq)"
                  >
                    加载播放
                  </el-button>
                  <el-button link type="primary" size="small" @click="downloadAudio(sq)">
                    下载
                  </el-button>
                </div>
                <audio
                  v-if="playbackUrls[lastAttempt(sq)!.id]"
                  :src="playbackUrls[lastAttempt(sq)!.id]"
                  controls
                  class="mt-2 w-full"
                />
              </div>
            </article>
          </section>

          <!-- 完成会话（practice.md §8，ADR-015） -->
          <footer v-if="isOperable" class="mt-6 flex justify-center">
            <el-button
              type="success"
              size="large"
              :disabled="!canComplete"
              :loading="acting"
              @click="completeSession"
            >
              {{ canComplete ? '完成会话' : `还需完成 ${progress.total - progress.done} 题` }}
            </el-button>
          </footer>
        </template>

        <el-empty v-else-if="!loading" description="会话不存在或无权访问" />
      </div>
    </div>
  </main>
</template>

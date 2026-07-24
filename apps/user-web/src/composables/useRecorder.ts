/**
 * useRecorder — 录音状态机封装（system-architecture §4.1：useRecorder composable）。
 *
 * 对齐 docs/product/user-flow.md §3 录音流程：
 *   IDLE → REQUESTING → RECORDING → STOPPING → UPLOADING → UPLOADED
 *                                    │           │
 *                                    ▼           ▼
 *                                  ERROR       ERROR
 *
 * 状态机：
 * - IDLE       初始态，未启动
 * - REQUESTING 请求麦克风权限（getUserMedia）
 * - RECORDING  MediaRecorder 录制中，计时器运行
 * - STOPPING   调 stop() 后等待 onstop 事件聚合 Blob
 * - UPLOADING  调上传接口中（multipart/form-data）
 * - UPLOADED   上传成功，事务返回 attempt(submitted)
 * - ERROR      任意阶段失败（权限拒绝/录制异常/上传失败），可通过 reset 回到 IDLE
 *
 * 设计要点：
 * - duration_seconds 由后端读元数据计算（ADR-020），前端仅展示计时器，不传给后端。
 * - 录音格式优先 audio/webm（Chromium/Firefox），Safari 回退 audio/mp4。
 * - 录音停止时释放 MediaStream tracks，避免麦克风指示灯常亮。
 * - 状态机用 readonly ref 暴露，外部仅可读，状态转换由本 composable 内部驱动。
 */
import { computed, onBeforeUnmount, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { api, ApiError } from '@/api'
import type { Attempt } from '@ielts/types'

export type RecorderState =
  | 'idle'
  | 'requesting'
  | 'recording'
  | 'stopping'
  | 'uploading'
  | 'uploaded'
  | 'error'

/** 浏览器支持的录音 mime 白名单（与后端 storage.ALLOWED_MIME_TYPES 对齐）。 */
const SUPPORTED_MIME_CANDIDATES = [
  'audio/webm;codecs=opus',
  'audio/webm',
  'audio/mp4;codecs=mp4a.40.2',
  'audio/mp4',
  'audio/mpeg',
  'audio/wav',
] as const

/** MediaRecorder 不可用 / getUserMedia 不可用 / 安全上下文缺失。 */
export function isRecorderSupported(): boolean {
  return (
    typeof navigator !== 'undefined' &&
    typeof navigator.mediaDevices?.getUserMedia === 'function' &&
    typeof window !== 'undefined' &&
    typeof window.MediaRecorder === 'function'
  )
}

/** 选出浏览器首个支持的 mime_type（候选表内顺序优先 webm）。 */
function pickSupportedMime(): string | null {
  if (typeof window === 'undefined' || typeof window.MediaRecorder !== 'function') {
    return null
  }
  for (const candidate of SUPPORTED_MIME_CANDIDATES) {
    if (window.MediaRecorder.isTypeSupported(candidate)) {
      return candidate
    }
  }
  return null
}

/** 录音秒数显示（仅 UI 用，不传后端）。 */
function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60)
    .toString()
    .padStart(2, '0')
  const s = (seconds % 60).toString().padStart(2, '0')
  return `${m}:${s}`
}

export interface UseRecorderOptions {
  /** 录音最大时长（秒），默认 300s（practice Part 2 单题建议 ≤ 2 分钟）。 */
  maxSeconds?: number
  /** 上传失败时是否自动 toast 错误信息（默认 true）。 */
  showErrorToast?: boolean
}

export function useRecorder(options: UseRecorderOptions = {}) {
  const maxSeconds = options.maxSeconds ?? 300
  const showErrorToast = options.showErrorToast ?? true

  const state = ref<RecorderState>('idle')
  const errorMessage = ref<string>('')
  const elapsedSeconds = ref(0)
  const elapsedLabel = computed(() => formatElapsed(elapsedSeconds.value))
  const isRecording = computed(() => state.value === 'recording')
  const isBusy = computed(
    () =>
      state.value === 'requesting' ||
      state.value === 'stopping' ||
      state.value === 'uploading',
  )
  const isUploaded = computed(() => state.value === 'uploaded')
  const hasError = computed(() => state.value === 'error')

  // 内部资源（不暴露）
  let mediaRecorder: MediaRecorder | null = null
  let mediaStream: MediaStream | null = null
  let chunks: Blob[] = []
  let timerId: ReturnType<typeof setInterval> | null = null
  let recordedMime = 'audio/webm'
  // 当前录音绑定的 attempt id（start 时设置，stop 上传时使用，自动停止兜底）
  let currentAttemptId: string | null = null

  function setState(next: RecorderState, msg = ''): void {
    state.value = next
    errorMessage.value = msg
  }

  /** 清理计时器与媒体资源（每次状态终止后调用）。 */
  function releaseResources(): void {
    if (timerId !== null) {
      clearInterval(timerId)
      timerId = null
    }
    if (mediaStream) {
      for (const track of mediaStream.getTracks()) {
        try {
          track.stop()
        } catch {
          /* noop */
        }
      }
      mediaStream = null
    }
    mediaRecorder = null
    chunks = []
  }

  /** 重置到 IDLE（出错后/上传后均可调用）。 */
  function reset(): void {
    releaseResources()
    currentAttemptId = null
    setState('idle')
    elapsedSeconds.value = 0
  }

  /**
   * 启动录音：IDLE → REQUESTING → RECORDING。
   * 失败 → ERROR（权限拒绝 / 设备不可用 / 浏览器不支持）。
   *
   * @param attemptId 录音归属的 attempt id（自动停止时用于上传）
   */
  async function start(attemptId: string): Promise<boolean> {
    if (state.value !== 'idle' && state.value !== 'error') {
      return false
    }
    currentAttemptId = attemptId
    if (!isRecorderSupported()) {
      setState('error', '当前浏览器不支持录音功能，请使用 Chrome / Edge / Firefox 最新版')
      if (showErrorToast) ElMessage.error(errorMessage.value)
      return false
    }
    const mime = pickSupportedMime()
    if (!mime) {
      setState('error', '未找到浏览器支持的音频格式')
      if (showErrorToast) ElMessage.error(errorMessage.value)
      return false
    }

    setState('requesting')
    recordedMime = mime
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
        video: false,
      })
    } catch (err) {
      const msg =
        err instanceof DOMException && err.name === 'NotAllowedError'
          ? '麦克风权限被拒绝，请在浏览器设置中允许后重试'
          : '无法访问麦克风，请检查设备连接'
      setState('error', msg)
      if (showErrorToast) ElMessage.error(msg)
      releaseResources()
      return false
    }

    try {
      mediaRecorder = new MediaRecorder(mediaStream, { mimeType: mime })
    } catch (err) {
      setState('error', '录音器初始化失败')
      if (showErrorToast) ElMessage.error(errorMessage.value)
      releaseResources()
      return false
    }

    chunks = []
    mediaRecorder.ondataavailable = (e: BlobEvent) => {
      if (e.data && e.data.size > 0) chunks.push(e.data)
    }
    mediaRecorder.onerror = () => {
      setState('error', '录音过程中发生错误')
      if (showErrorToast) ElMessage.error(errorMessage.value)
      releaseResources()
    }
    // onstop 在 stop() 中动态设置（聚合 chunks 后上传），此处不预设

    try {
      mediaRecorder.start()
    } catch {
      setState('error', '录音启动失败')
      if (showErrorToast) ElMessage.error(errorMessage.value)
      releaseResources()
      return false
    }

    setState('recording')
    elapsedSeconds.value = 0
    timerId = setInterval(() => {
      elapsedSeconds.value += 1
      if (elapsedSeconds.value >= maxSeconds) {
        // 达到最大时长自动停止（使用 start 时绑定的 attemptId 上传）
        void stop()
      }
    }, 1000)
    return true
  }

  /**
   * 停止录音并上传：RECORDING → STOPPING → UPLOADING → UPLOADED。
   * 任一步失败 → ERROR。
   *
   * 使用 start(attemptId) 时绑定的 attempt id 上传；自动停止时也走同一路径。
   *
   * @param attemptId 可选，覆盖 start 时绑定的 attempt id（手动停止时由调用方传入）
   * @returns 上传成功返回更新后的 Attempt，失败返回 null
   */
  async function stop(attemptId?: string): Promise<Attempt | null> {
    if (state.value !== 'recording' || !mediaRecorder) {
      return null
    }
    const uploadAttemptId = attemptId ?? currentAttemptId
    if (!uploadAttemptId) {
      setState('error', '录音未绑定答题尝试，无法上传')
      if (showErrorToast) ElMessage.error(errorMessage.value)
      releaseResources()
      return null
    }

    setState('stopping')
    const recorder = mediaRecorder
    const stream = mediaStream

    // 等待 MediaRecorder.onstop 触发（聚合 chunks）
    const stopped = new Promise<void>((resolve) => {
      recorder.onstop = () => resolve()
    })
    try {
      if (recorder.state !== 'inactive') {
        recorder.stop()
      }
    } catch {
      setState('error', '停止录音失败')
      if (showErrorToast) ElMessage.error(errorMessage.value)
      releaseResources()
      return null
    }
    await stopped

    // 停止计时器与 tracks（不再录）
    if (timerId !== null) {
      clearInterval(timerId)
      timerId = null
    }
    if (stream) {
      for (const track of stream.getTracks()) {
        try {
          track.stop()
        } catch {
          /* noop */
        }
      }
    }

    if (chunks.length === 0) {
      setState('error', '录音内容为空')
      if (showErrorToast) ElMessage.error(errorMessage.value)
      releaseResources()
      return null
    }

    const blob = new Blob(chunks, { type: recordedMime })
    const file = new File([blob], `recording.${recordedMime.split('/')[1].split(';')[0]}`, {
      type: recordedMime,
    })

    setState('uploading')
    const formData = new FormData()
    formData.append('file', file)

    try {
      // 后端返回更新后的 Attempt（含 recording，status='submitted'，practice.md §6.2）
      const updated = await api.post<Attempt>(
        `/practice/attempts/${uploadAttemptId}/recording`,
        formData,
      )
      setState('uploaded')
      // 上传成功后释放资源，但保留 uploaded 状态供 UI 判断
      mediaRecorder = null
      mediaStream = null
      chunks = []
      currentAttemptId = null
      return updated
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : '录音上传失败，请重试'
      setState('error', msg)
      if (showErrorToast) ElMessage.error(msg)
      releaseResources()
      currentAttemptId = null
      return null
    }
  }

  /** 主动放弃当前录音（不上传，回到 IDLE）。RECORDING → IDLE。 */
  function cancel(): void {
    if (state.value !== 'recording' && state.value !== 'error') {
      return
    }
    try {
      if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.onstop = null
        mediaRecorder.stop()
      }
    } catch {
      /* noop */
    }
    reset()
  }

  // 组件卸载时清理资源，避免麦克风指示灯常亮
  onBeforeUnmount(() => {
    releaseResources()
  })

  return {
    // 状态（只读）
    state,
    errorMessage,
    elapsedSeconds,
    elapsedLabel,
    isRecording,
    isBusy,
    isUploaded,
    hasError,
    // 操作
    start,
    stop,
    cancel,
    reset,
  }
}

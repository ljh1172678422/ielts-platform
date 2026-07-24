import axios, { type AxiosResponse } from 'axios'
import type { ResponseEnvelope, ErrorEnvelope, ApiErrorDetail } from '@ielts/types'

/**
 * 检测 FormData：让 axios 自动设置 multipart/form-data + boundary。
 * 实例默认 Content-Type=application/json 会覆盖 multipart，
 * 必须删除后 axios 才能根据 body 类型推断正确的 Content-Type。
 */
function isFormData(value: unknown): value is FormData {
  return typeof FormData !== 'undefined' && value instanceof FormData
}

/**
 * 统一 API 响应结构（复用 @ielts/types，对齐 docs/api/common.md §2）
 * 成功：{ code: 0, message: 'ok', data: ... }
 * 错误：{ code: <非0>, message, data: null, details? }
 */
type ApiResponse<T = unknown> = ResponseEnvelope<T>

/** localStorage key：access_token 持久化（auth.md §6.2 前端职责）。 */
export const TOKEN_STORAGE_KEY = 'access_token'

/**
 * API 业务错误（携带 common.md 业务码）。
 * 由响应拦截器在 code !== 0 或 HTTP 4xx/5xx 时抛出，调用方可读 .code 做分支。
 */
export class ApiError extends Error {
  readonly code: number
  readonly details?: ApiErrorDetail[]
  readonly httpStatus?: number

  constructor(
    code: number,
    message: string,
    options?: { details?: ApiErrorDetail[]; httpStatus?: number },
  ) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.details = options?.details
    this.httpStatus = options?.httpStatus
  }
}

/** 401 业务码（common.md §3.2 / auth.md §5.4）：收到时清 token 并跳登录。 */
const UNAUTHORIZED_CODES = new Set([2001, 2002, 2005])

/**
 * Axios 实例（统一 API 调用入口）
 * - baseURL: /api/v1（common.md §1.1）
 * - 请求拦截器：注入 Authorization: Bearer <token>（直读 localStorage，与 store 解耦）
 * - 响应拦截器：解包 { code, message, data }，code !== 0 抛 ApiError；401 清 token 跳登录
 */
const request = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json; charset=utf-8' },
})

// 请求拦截器：注入 Bearer token（auth.md §5.1）
// 直读 localStorage 而非 import auth store，避免 api ↔ store 循环依赖；
// store 是 localStorage 的唯一写入方，二者始终同步。
request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(TOKEN_STORAGE_KEY)
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    // FormData：删除默认 Content-Type，让 axios 自动加 multipart/form-data + boundary
    if (isFormData(config.data)) {
      delete config.headers['Content-Type']
      delete config.headers['content-type']
    }
    return config
  },
  (error) => Promise.reject(error),
)

// 响应拦截器：解包统一信封（common.md §2），code !== 0 抛 ApiError
request.interceptors.response.use(
  (response) => {
    const body = response.data as ApiResponse
    if (body.code !== 0) {
      // 业务错误：抛出带业务码的 ApiError
      throw new ApiError(body.code, body.message || '请求失败', {
        httpStatus: response.status,
      })
    }
    // 成功：解包 data 直接返回（调用方拿到业务数据，而非 AxiosResponse）
    return body.data as unknown as AxiosResponse
  },
  (error) => {
    // HTTP 层错误（非 2xx）：尝试从响应体取业务信封
    const status = error.response?.status
    const body = error.response?.data as ErrorEnvelope | undefined

    if (body && typeof body.code === 'number') {
      // 401：token 失效/过期 → 清状态 + 跳登录
      if (UNAUTHORIZED_CODES.has(body.code)) {
        void handleUnauthorized()
      }
      return Promise.reject(
        new ApiError(body.code, body.message || '请求失败', {
          details: body.details,
          httpStatus: status,
        }),
      )
    }

    // 非信封错误（如网络断开 / 网关 502）
    return Promise.reject(
      new ApiError(9003, body?.message || error.message || '服务内部错误', {
        httpStatus: status,
      }),
    )
  },
)

/**
 * 401 处理：清 token + 跳 /login。
 * 用动态 import 懒加载 store/router，避免 api ↔ store/router 循环依赖；
 * 跳转带 redirect 参数，登录后可回跳原页面。
 */
async function handleUnauthorized(): Promise<void> {
  // 先清 localStorage（同步，立即生效，后续请求不再带 token）
  localStorage.removeItem(TOKEN_STORAGE_KEY)
  try {
    const [{ useAuthStore }, { default: router }] = await Promise.all([
      import('@/stores/auth'),
      import('@/router'),
    ])
    useAuthStore().clearAuth()
    const current = router.currentRoute.value
    if (current.name !== 'login') {
      await router.push({
        name: 'login',
        query: current.path !== '/' ? { redirect: current.fullPath } : {},
      })
    }
  } catch {
    // store/router 未就绪时忽略（如应用初始化阶段）
  }
}

/** typed 辅助方法：直接返回业务数据 T（已解包信封）。 */
export const api = {
  get: <T>(url: string) => request.get(url) as unknown as Promise<T>,
  post: <T>(url: string, data?: unknown) => request.post(url, data) as unknown as Promise<T>,
  put: <T>(url: string, data?: unknown) => request.put(url, data) as unknown as Promise<T>,
  patch: <T>(url: string, data?: unknown) => request.patch(url, data) as unknown as Promise<T>,
  delete: <T>(url: string) => request.delete(url) as unknown as Promise<T>,
}

export default request
export type { ApiResponse }

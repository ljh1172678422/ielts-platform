import axios, { type AxiosResponse } from 'axios'
import type { ResponseEnvelope } from '@ielts/types'

/**
 * 统一 API 响应结构（复用 @ielts/types，对齐 docs/api/common.md §2）
 * 成功：{ code: 0, message: 'ok', data: ... }
 * 错误：{ code: <非0>, message, data: null, details? }
 */
type ApiResponse<T = unknown> = ResponseEnvelope<T>

/**
 * Axios 实例（统一 API 调用入口）
 * - baseURL: /api/v1（common.md §1.1）
 * - 请求拦截器：注入 Authorization: Bearer <token>
 * - 响应拦截器：解包 { code, message, data }，code !== 0 抛错
 */
const request = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json; charset=utf-8' },
})

// 请求拦截器：预留 token 注入位置（从 auth store 取）
request.interceptors.request.use(
  (config) => {
    // TODO: 登录实现后取消注释，从 auth store 取 access_token 注入
    // import { useAuthStore } from '@/stores/auth'
    // const authStore = useAuthStore()
    // if (authStore.token) {
    //   config.headers.Authorization = `Bearer ${authStore.token}`
    // }
    return config
  },
  (error) => Promise.reject(error),
)

// 响应拦截器：解包统一响应并在 code !== 0 时抛错（common.md §2）
request.interceptors.response.use(
  (response) => {
    const body = response.data as ApiResponse
    if (body.code !== 0) {
      // 业务错误：抛出，交由调用方 / 全局错误处理
      return Promise.reject(new Error(body.message || '请求失败'))
    }
    // 成功：解包 data 直接返回（调用方拿到业务数据，而非 AxiosResponse）
    return body.data as unknown as AxiosResponse
  },
  (error) => {
    // HTTP 层错误（非 2xx）：统一透传给调用方处理
    return Promise.reject(error)
  },
)

export default request
export type { ApiResponse }

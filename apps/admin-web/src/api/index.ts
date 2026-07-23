import axios from 'axios'

// 后端统一响应结构：{ code, message, data }
// 约定 code === 0 表示成功，其余视为业务错误。
export interface ApiResult<T = unknown> {
  code: number
  message: string
  data: T
}

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
})

// 请求拦截器：预留 token 注入
request.interceptors.request.use(
  (config) => {
    // TODO: 从 auth store 读取 token 并注入
    // const token = useAuthStore().token
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`
    // }
    return config
  },
  (error) => Promise.reject(error),
)

// 响应拦截器：解包 { code, message, data }，code !== 0 抛错
request.interceptors.response.use(
  (response) => {
    const result = response.data as ApiResult
    if (result.code !== 0) {
      // TODO: 统一错误提示（ElMessage）与 401 跳转登录
      return Promise.reject(new Error(result.message || 'Request failed'))
    }
    // 成功：保留完整 response，调用方通过 res.data.data 取业务数据
    // 后续可在此直接返回 result.data 以彻底解包。
    return response
  },
  (error) => {
    // TODO: HTTP 层错误统一处理（超时 / 网络错误 / 4xx / 5xx）
    return Promise.reject(error)
  },
)

export default request

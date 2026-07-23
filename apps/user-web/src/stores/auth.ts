import { defineStore } from 'pinia'
import type {
  AuthData,
  LoginRequest,
  RegisterRequest,
  UserPublic,
  UserRole,
} from '@ielts/types'
import { api, TOKEN_STORAGE_KEY } from '@/api'

/**
 * Auth Store — 认证状态中心（对齐 auth.md / users.md）。
 *
 * 职责：
 * - 持有 access_token + 当前用户信息（role / user），供 UI 响应式消费。
 * - login / register：调 /auth/login | /auth/register，落库 token + user。
 * - fetchProfile：调 /users/me，刷新当前用户信息。
 * - logout：调 /auth/logout（无状态，auth.md §4.4），清本地状态。
 * - token 持久化到 localStorage（auth.md §6.2 前端职责），刷新页面不掉线。
 *
 * 解耦约定：api 请求拦截器直读 localStorage 取 token，本 store 是 localStorage 唯一写入方。
 */
export const useAuthStore = defineStore('auth', {
  state: () => ({
    /** access_token（持久化于 localStorage，刷新后从 localStorage 恢复）。 */
    token: localStorage.getItem(TOKEN_STORAGE_KEY) ?? '',
    /** 当前用户角色（ADR-009 user/admin）。 */
    role: null as UserRole | null,
    /** 当前用户公开信息（auth.md §7.2，登录后写入）。 */
    user: null as UserPublic | null,
  }),
  getters: {
    isAuthenticated: (state): boolean => Boolean(state.token),
    isAdmin: (state): boolean => state.role === 'admin',
  },
  actions: {
    /**
     * 写入认证态（login/register 成功后调用）。
     * 持久化 token 到 localStorage，更新 role/user。
     */
    setAuth(data: AuthData): void {
      this.token = data.access_token
      this.role = data.user.role
      this.user = data.user
      localStorage.setItem(TOKEN_STORAGE_KEY, data.access_token)
    },

    /**
     * 清除认证态（logout / 401 失效时调用）。
     * 同步清 localStorage，使 api 拦截器后续不再带 token。
     */
    clearAuth(): void {
      this.token = ''
      this.role = null
      this.user = null
      localStorage.removeItem(TOKEN_STORAGE_KEY)
    },

    /** 注册（auth.md §2）：成功后写入认证态并返回 user。 */
    async register(req: RegisterRequest): Promise<UserPublic> {
      const data = await api.post<AuthData>('/auth/register', req)
      this.setAuth(data)
      return data.user
    },

    /** 登录（auth.md §3）：成功后写入认证态并返回 user。 */
    async login(req: LoginRequest): Promise<UserPublic> {
      const data = await api.post<AuthData>('/auth/login', req)
      this.setAuth(data)
      return data.user
    },

    /**
     * 退出（auth.md §4，无状态退出 ADR-027）。
     * 调 /auth/logout 写行为日志（失败不阻塞），无论成功与否都清本地状态。
     */
    async logout(): Promise<void> {
      try {
        await api.post<null>('/auth/logout')
      } finally {
        this.clearAuth()
      }
    },

    /**
     * 拉取当前用户信息（users.md §2）。
     * 用于登录后刷新 / 路由守卫首次进入受保护页时补全 user。
     * 若本地已有 token 但 user 为空，调用此方法补全。
     */
    async fetchProfile(): Promise<UserPublic> {
      const user = await api.get<UserPublic>('/users/me')
      this.user = user
      this.role = user.role
      return user
    },
  },
})

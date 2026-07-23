import { defineStore } from 'pinia'
import type { AuthData, LoginRequest, UserPublic, UserRole } from '@ielts/types'
import { api, ApiError, TOKEN_STORAGE_KEY } from '@/api'

/**
 * Admin Auth Store — 管理后台认证状态中心（对齐 admin.md §1.1 / auth.md）。
 *
 * 职责：
 * - 持有 access_token + 当前用户信息（role / user），供 UI 响应式消费。
 * - login：调 /auth/login（复用 auth.md §3），登录后校验 role='admin'，
 *   非管理员 → 抛 2003 并清状态（admin.md §1.1 仅 admin 角色可进后台）。
 * - logout：调 /auth/logout（无状态，auth.md §4.4），清本地状态。
 * - fetchProfile：调 /users/me，刷新当前用户信息（路由守卫首次进入时补全 user）。
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
     * 写入认证态（login 成功后调用）。
     * 持久化 token 到 localStorage，更新 role/user。
     */
    setAuth(data: AuthData): void {
      this.token = data.access_token
      this.role = data.user.role
      this.user = data.user
      localStorage.setItem(TOKEN_STORAGE_KEY, data.access_token)
    },

    /**
     * 清除认证态（logout / 401 失效 / 非管理员登录被拒时调用）。
     * 同步清 localStorage，使 api 拦截器后续不再带 token。
     */
    clearAuth(): void {
      this.token = ''
      this.role = null
      this.user = null
      localStorage.removeItem(TOKEN_STORAGE_KEY)
    },

    /**
     * 管理员登录（admin.md §1.1 复用 auth.md §3 /auth/login）。
     * 登录成功后校验 role='admin'，非管理员 → 抛 2003 并清状态。
     * 返回 user（保证为 admin 角色）。
     */
    async login(req: LoginRequest): Promise<UserPublic> {
      const data = await api.post<AuthData>('/auth/login', req)
      if (data.user.role !== 'admin') {
        // 非管理员账号不允许进入后台（admin.md §1.1）
        this.clearAuth()
        throw new ApiError(2003, '无管理员权限，禁止进入后台', { httpStatus: 403 })
      }
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
     * 用于路由守卫首次进入受保护页时补全 user / 校验 admin 角色。
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

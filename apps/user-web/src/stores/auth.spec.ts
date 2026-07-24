/**
 * Auth Store 单元测试（Phase 11.5，对齐 auth.md §2-§4）。
 *
 * 覆盖：
 * - setAuth/clearAuth：token 持久化 + state 更新
 * - isAuthenticated/isAdmin getters
 * - login/register：API 调用 + setAuth
 * - logout：API 调用 + clearAuth（失败也清）
 * - fetchProfile：API 调用 + user/role 更新
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from './auth'
import { api, TOKEN_STORAGE_KEY, ApiError } from '@/api'
import type { AuthData, UserPublic } from '@ielts/types'

// ---------------------------------------------------------------------------
// 工厂
// ---------------------------------------------------------------------------

function makeUser(overrides: Partial<UserPublic> = {}): UserPublic {
  return {
    id: '1',
    email: 'test@example.com',
    role: 'user',
    status: 'active',
    profile: {
      nickname: 'Tester',
      timezone: 'Asia/Shanghai',
      avatar_url: null,
    },
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

function makeAuthData(overrides: Partial<AuthData> = {}): AuthData {
  return {
    access_token: 'mock-token-abc123',
    token_type: 'bearer',
    expires_in: 86400,
    user: makeUser(),
    ...overrides,
  }
}

// ---------------------------------------------------------------------------
// 测试
// ---------------------------------------------------------------------------

describe('auth store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  describe('initial state', () => {
    it('token 从 localStorage 恢复', () => {
      localStorage.setItem(TOKEN_STORAGE_KEY, 'persisted-token')
      const store = useAuthStore()
      expect(store.token).toBe('persisted-token')
      expect(store.isAuthenticated).toBe(true)
    })

    it('无 token 时 isAuthenticated=false', () => {
      const store = useAuthStore()
      expect(store.token).toBe('')
      expect(store.isAuthenticated).toBe(false)
    })

    it('role/user 初始为 null', () => {
      const store = useAuthStore()
      expect(store.role).toBeNull()
      expect(store.user).toBeNull()
      expect(store.isAdmin).toBe(false)
    })
  })

  describe('setAuth', () => {
    it('写入 token + role + user 并持久化到 localStorage', () => {
      const store = useAuthStore()
      const data = makeAuthData({
        access_token: 'new-token',
        user: makeUser({ role: 'admin', email: 'admin@test.com' }),
      })
      store.setAuth(data)
      expect(store.token).toBe('new-token')
      expect(store.role).toBe('admin')
      expect(store.user?.email).toBe('admin@test.com')
      expect(localStorage.getItem(TOKEN_STORAGE_KEY)).toBe('new-token')
      expect(store.isAuthenticated).toBe(true)
      expect(store.isAdmin).toBe(true)
    })
  })

  describe('clearAuth', () => {
    it('清除 token + role + user 并删除 localStorage', () => {
      const store = useAuthStore()
      store.setAuth(makeAuthData())
      expect(store.isAuthenticated).toBe(true)

      store.clearAuth()
      expect(store.token).toBe('')
      expect(store.role).toBeNull()
      expect(store.user).toBeNull()
      expect(localStorage.getItem(TOKEN_STORAGE_KEY)).toBeNull()
      expect(store.isAuthenticated).toBe(false)
    })
  })

  describe('login', () => {
    it('成功：调 API + setAuth + 返回 user', async () => {
      const store = useAuthStore()
      const mockData = makeAuthData({
        access_token: 'login-token',
        user: makeUser({ id: '42', email: 'login@test.com' }),
      })
      const spy = vi.spyOn(api, 'post').mockResolvedValue(mockData)

      const user = await store.login({
        email: 'login@test.com',
        password: 'Pass1234',
      })

      expect(spy).toHaveBeenCalledWith('/auth/login', {
        email: 'login@test.com',
        password: 'Pass1234',
      })
      expect(store.token).toBe('login-token')
      expect(store.isAuthenticated).toBe(true)
      expect(user.id).toBe('42')
      expect(user.email).toBe('login@test.com')
    })

    it('失败：API 抛错 → 不写入认证态', async () => {
      const store = useAuthStore()
      vi.spyOn(api, 'post').mockRejectedValue(
        new ApiError(3002, '邮箱或密码错误'),
      )

      await expect(
        store.login({ email: 'wrong@test.com', password: 'bad' }),
      ).rejects.toThrow('邮箱或密码错误')

      expect(store.token).toBe('')
      expect(store.isAuthenticated).toBe(false)
      expect(localStorage.getItem(TOKEN_STORAGE_KEY)).toBeNull()
    })
  })

  describe('register', () => {
    it('成功：调 API + setAuth + 返回 user', async () => {
      const store = useAuthStore()
      const mockData = makeAuthData({
        access_token: 'register-token',
        user: makeUser({ id: '99', email: 'new@test.com' }),
      })
      const spy = vi.spyOn(api, 'post').mockResolvedValue(mockData)

      const user = await store.register({
        email: 'new@test.com',
        password: 'Pass1234',
        nickname: 'NewUser',
      })

      expect(spy).toHaveBeenCalledWith('/auth/register', {
        email: 'new@test.com',
        password: 'Pass1234',
        nickname: 'NewUser',
      })
      expect(store.token).toBe('register-token')
      expect(user.id).toBe('99')
    })
  })

  describe('logout', () => {
    it('成功：调 API + 清认证态', async () => {
      const store = useAuthStore()
      store.setAuth(makeAuthData())
      expect(store.isAuthenticated).toBe(true)

      const spy = vi.spyOn(api, 'post').mockResolvedValue(null)
      await store.logout()

      expect(spy).toHaveBeenCalledWith('/auth/logout')
      expect(store.isAuthenticated).toBe(false)
      expect(localStorage.getItem(TOKEN_STORAGE_KEY)).toBeNull()
    })

    it('API 失败：仍清认证态且不抛错（ADR-027 无状态退出）', async () => {
      const store = useAuthStore()
      store.setAuth(makeAuthData())
      expect(store.isAuthenticated).toBe(true)

      vi.spyOn(api, 'post').mockRejectedValue(new ApiError(9003, '服务错误'))

      // logout 应捕获 API 错误，不向调用方抛出（失败不阻塞）
      await store.logout()

      // 即使 API 失败，本地认证态也必须清除
      expect(store.isAuthenticated).toBe(false)
      expect(localStorage.getItem(TOKEN_STORAGE_KEY)).toBeNull()
    })
  })

  describe('fetchProfile', () => {
    it('成功：更新 user + role', async () => {
      const store = useAuthStore()
      const mockUser = makeUser({ id: '7', role: 'admin', email: 'profile@test.com' })
      vi.spyOn(api, 'get').mockResolvedValue(mockUser)

      const user = await store.fetchProfile()

      expect(user.id).toBe('7')
      expect(store.user?.email).toBe('profile@test.com')
      expect(store.role).toBe('admin')
      expect(store.isAdmin).toBe(true)
    })

    it('失败：抛错且不更新 user', async () => {
      const store = useAuthStore()
      vi.spyOn(api, 'get').mockRejectedValue(new ApiError(2001, '未授权'))

      await expect(store.fetchProfile()).rejects.toThrow('未授权')
      expect(store.user).toBeNull()
    })
  })

  describe('isAdmin getter', () => {
    it('role=user → false', () => {
      const store = useAuthStore()
      store.setAuth(makeAuthData({ user: makeUser({ role: 'user' }) }))
      expect(store.isAdmin).toBe(false)
    })

    it('role=admin → true', () => {
      const store = useAuthStore()
      store.setAuth(makeAuthData({ user: makeUser({ role: 'admin' }) }))
      expect(store.isAdmin).toBe(true)
    })
  })
})

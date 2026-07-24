/**
 * LoginView 组件测试（Phase 11.5，对齐 auth.md §3 + user-flow.md）。
 *
 * 覆盖：
 * - 表单渲染（邮箱/密码输入框 + 登录按钮）
 * - 成功登录 → 调 store.login + router.replace 到 redirect 或 /
 * - 失败登录 → 不跳转，展示错误消息
 * - loading 状态：提交期间禁用按钮
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import ElementPlus from 'element-plus'
import LoginView from './LoginView.vue'
import { useAuthStore } from '@/stores/auth'
import { ApiError } from '@/api'
import type { AuthData, UserPublic } from '@ielts/types'

// ---------------------------------------------------------------------------
// 工厂
// ---------------------------------------------------------------------------

function makeAuthData(): AuthData {
  return {
    access_token: 'mock-token',
    token_type: 'bearer',
    expires_in: 86400,
    user: {
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
    },
  }
}

function createTestRouter() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: { template: '<div>home</div>' } },
      { path: '/login', name: 'login', component: LoginView },
      {
        path: '/register',
        name: 'register',
        component: { template: '<div>register</div>' },
      },
      {
        path: '/profile',
        name: 'profile',
        component: { template: '<div>profile</div>' },
      },
    ],
  })
  return router
}

function mountLoginView(router = createTestRouter()) {
  return mount(LoginView, {
    global: {
      plugins: [router, ElementPlus],
    },
  })
}

// ---------------------------------------------------------------------------
// 测试
// ---------------------------------------------------------------------------

describe('LoginView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  describe('渲染', () => {
    it('包含邮箱输入框', () => {
      const wrapper = mountLoginView()
      const emailInput = wrapper.find('input[type="email"]')
      expect(emailInput.exists()).toBe(true)
    })

    it('包含密码输入框', () => {
      const wrapper = mountLoginView()
      const passwordInput = wrapper.find('input[type="password"]')
      expect(passwordInput.exists()).toBe(true)
    })

    it('包含登录按钮', () => {
      const wrapper = mountLoginView()
      const button = wrapper.find('button')
      expect(button.exists()).toBe(true)
      expect(button.text()).toContain('登录')
    })

    it('包含注册链接', () => {
      const wrapper = mountLoginView()
      const link = wrapper.find('a')
      expect(link.exists()).toBe(true)
      expect(link.attributes('href')).toBe('/register')
    })
  })

  describe('登录流程', () => {
    it('成功：调 store.login + 跳转到首页', async () => {
      const router = createTestRouter()
      await router.push('/login')
      await router.isReady()

      const wrapper = mountLoginView(router)
      const store = useAuthStore()

      // mock store.login 成功
      const loginSpy = vi.spyOn(store, 'login').mockResolvedValue(
        makeAuthData().user,
      )

      // 填写表单
      await wrapper.find('input[type="email"]').setValue('test@example.com')
      await wrapper.find('input[type="password"]').setValue('Pass1234')

      // 提交
      await wrapper.find('button').trigger('click')
      await flushPromises()

      expect(loginSpy).toHaveBeenCalledWith({
        email: 'test@example.com',
        password: 'Pass1234',
      })
      // 跳转到首页
      expect(router.currentRoute.value.name).toBe('home')
    })

    it('成功：有 redirect 参数时跳转到原页面', async () => {
      const router = createTestRouter()
      await router.push({ path: '/login', query: { redirect: '/profile' } })
      await router.isReady()

      const wrapper = mountLoginView(router)
      const store = useAuthStore()
      vi.spyOn(store, 'login').mockResolvedValue(makeAuthData().user)

      await wrapper.find('input[type="email"]').setValue('test@example.com')
      await wrapper.find('input[type="password"]').setValue('Pass1234')
      await wrapper.find('button').trigger('click')
      await flushPromises()

      expect(router.currentRoute.value.name).toBe('profile')
    })

    it('失败：3002 邮箱或密码错误 → 不跳转', async () => {
      const router = createTestRouter()
      await router.push('/login')
      await router.isReady()

      const wrapper = mountLoginView(router)
      const store = useAuthStore()
      vi.spyOn(store, 'login').mockRejectedValue(
        new ApiError(3002, '邮箱或密码错误'),
      )

      await wrapper.find('input[type="email"]').setValue('wrong@test.com')
      await wrapper.find('input[type="password"]').setValue('badpass')
      await wrapper.find('button').trigger('click')
      await flushPromises()

      // 仍在登录页
      expect(router.currentRoute.value.name).toBe('login')
      // store 未写入认证态
      expect(store.isAuthenticated).toBe(false)
    })

    it('失败：网络错误 → 不跳转', async () => {
      const router = createTestRouter()
      await router.push('/login')
      await router.isReady()

      const wrapper = mountLoginView(router)
      const store = useAuthStore()
      vi.spyOn(store, 'login').mockRejectedValue(
        new ApiError(9003, '服务内部错误'),
      )

      await wrapper.find('input[type="email"]').setValue('test@example.com')
      await wrapper.find('input[type="password"]').setValue('Pass1234')
      await wrapper.find('button').trigger('click')
      await flushPromises()

      expect(router.currentRoute.value.name).toBe('login')
      expect(store.isAuthenticated).toBe(false)
    })
  })

  describe('loading 状态', () => {
    it('提交期间按钮显示 loading', async () => {
      const router = createTestRouter()
      await router.push('/login')
      await router.isReady()

      const wrapper = mountLoginView(router)
      const store = useAuthStore()

      // mock login 返回一个 pending promise（不立即 resolve）
      let resolveLogin!: (value: UserPublic) => void
      vi.spyOn(store, 'login').mockReturnValue(
        new Promise<UserPublic>((resolve) => {
          resolveLogin = resolve
        }),
      )

      await wrapper.find('input[type="email"]').setValue('test@example.com')
      await wrapper.find('input[type="password"]').setValue('Pass1234')
      wrapper.find('button').trigger('click')
      await flushPromises()

      // loading 期间按钮应有 loading class
      const button = wrapper.find('button')
      expect(button.classes().some((c) => c.includes('loading'))).toBe(true)

      // resolve 后 loading 消失
      resolveLogin(makeAuthData().user)
      await flushPromises()
    })
  })
})

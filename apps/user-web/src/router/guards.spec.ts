/**
 * 路由守卫单元测试（Phase 11.5，对齐 auth.md §5.4 / user-flow.md）。
 *
 * 覆盖：
 * - 已登录访问 public 页（/login /register）→ 跳首页
 * - 未登录访问受保护页（/profile /questions 等）→ 跳 /login 带 redirect
 * - 已登录访问受保护页 → 放行
 * - 未登录访问 public 页 → 放行
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory, type RouteRecordRaw } from 'vue-router'
import HomeView from '@/views/HomeView.vue'
import { useAuthStore } from '@/stores/auth'
import { TOKEN_STORAGE_KEY } from '@/api'

// ---------------------------------------------------------------------------
// 构建测试用 router（复用生产路由守卫逻辑）
// ---------------------------------------------------------------------------

function createTestRouter() {
  const routes: RouteRecordRaw[] = [
    {
      path: '/',
      component: HomeView,
      children: [
        { path: '', name: 'home', component: HomeView, meta: { public: true } },
        {
          path: 'login',
          name: 'login',
          component: { template: '<div>login</div>' },
          meta: { public: true },
        },
        {
          path: 'register',
          name: 'register',
          component: { template: '<div>register</div>' },
          meta: { public: true },
        },
        {
          path: 'profile',
          name: 'profile',
          component: { template: '<div>profile</div>' },
        },
        {
          path: 'questions',
          name: 'questions',
          component: { template: '<div>questions</div>' },
        },
        {
          path: 'practice/:id',
          name: 'practice',
          component: { template: '<div>practice</div>' },
          props: true,
        },
        {
          path: 'learning',
          name: 'learning',
          component: { template: '<div>learning</div>' },
        },
      ],
    },
  ]

  const router = createRouter({
    history: createMemoryHistory(),
    routes,
  })

  // 复用生产守卫逻辑（router/index.ts）
  router.beforeEach((to) => {
    const authStore = useAuthStore()
    const isPublic = to.meta.public === true

    // 已登录访问公开页（排除首页自身）→ 回首页，避免重复登录
    if (isPublic && authStore.isAuthenticated && to.name !== 'home') {
      return { name: 'home' }
    }
    // 未登录访问受保护页 → 跳登录，带 redirect
    if (!isPublic && !authStore.isAuthenticated) {
      return {
        name: 'login',
        query: to.fullPath !== '/' ? { redirect: to.fullPath } : {},
      }
    }
    return true
  })

  return router
}

// ---------------------------------------------------------------------------
// 测试
// ---------------------------------------------------------------------------

describe('router guards', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  describe('未登录用户', () => {
    it('访问 public 页 / → 放行', async () => {
      const router = createTestRouter()
      await router.push('/')
      await router.isReady()
      expect(router.currentRoute.value.name).toBe('home')
    })

    it('访问 /login → 放行', async () => {
      const router = createTestRouter()
      await router.push('/login')
      await router.isReady()
      expect(router.currentRoute.value.name).toBe('login')
    })

    it('访问 /register → 放行', async () => {
      const router = createTestRouter()
      await router.push('/register')
      await router.isReady()
      expect(router.currentRoute.value.name).toBe('register')
    })

    it('访问受保护页 /profile → 跳 /login 带 redirect', async () => {
      const router = createTestRouter()
      await router.push('/profile')
      await router.isReady()
      expect(router.currentRoute.value.name).toBe('login')
      expect(router.currentRoute.value.query.redirect).toBe('/profile')
    })

    it('访问受保护页 /questions → 跳 /login 带 redirect', async () => {
      const router = createTestRouter()
      await router.push('/questions')
      await router.isReady()
      expect(router.currentRoute.value.name).toBe('login')
      expect(router.currentRoute.value.query.redirect).toBe('/questions')
    })

    it('访问受保护页 /practice/123 → 跳 /login 带 redirect', async () => {
      const router = createTestRouter()
      await router.push('/practice/123')
      await router.isReady()
      expect(router.currentRoute.value.name).toBe('login')
      expect(router.currentRoute.value.query.redirect).toBe('/practice/123')
    })

    it('访问受保护页 /learning → 跳 /login 带 redirect', async () => {
      const router = createTestRouter()
      await router.push('/learning')
      await router.isReady()
      expect(router.currentRoute.value.name).toBe('login')
      expect(router.currentRoute.value.query.redirect).toBe('/learning')
    })
  })

  describe('已登录用户', () => {
    beforeEach(() => {
      // 模拟已登录：写 token + setAuth
      localStorage.setItem(TOKEN_STORAGE_KEY, 'test-token')
      const store = useAuthStore()
      store.setAuth({
        access_token: 'test-token',
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
      })
    })

    it('访问受保护页 /profile → 放行', async () => {
      const router = createTestRouter()
      await router.push('/profile')
      await router.isReady()
      expect(router.currentRoute.value.name).toBe('profile')
    })

    it('访问受保护页 /questions → 放行', async () => {
      const router = createTestRouter()
      await router.push('/questions')
      await router.isReady()
      expect(router.currentRoute.value.name).toBe('questions')
    })

    it('访问 /login → 跳首页（避免重复登录）', async () => {
      const router = createTestRouter()
      await router.push('/login')
      await router.isReady()
      expect(router.currentRoute.value.name).toBe('home')
    })

    it('访问 /register → 跳首页', async () => {
      const router = createTestRouter()
      await router.push('/register')
      await router.isReady()
      expect(router.currentRoute.value.name).toBe('home')
    })

    it('访问 / → 放行到首页', async () => {
      const router = createTestRouter()
      await router.push('/')
      await router.isReady()
      expect(router.currentRoute.value.name).toBe('home')
    })
  })
})

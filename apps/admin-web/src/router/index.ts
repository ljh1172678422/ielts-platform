import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import AdminLayout from '@/layouts/AdminLayout.vue'
import DashboardView from '@/views/DashboardView.vue'
import { useAuthStore } from '@/stores/auth'

/**
 * 管理后台路由（admin.md §1.1 / user-flow.md）。
 *
 * 结构：
 * - /login：管理员登录页（public，复用 /auth/login）
 * - /：AdminLayout 布局，子路由为各管理页（受保护 + admin 守卫）
 *
 * 守卫：
 * - 已认证访问 /login → 跳 dashboard
 * - 未认证访问受保护页 → 跳 /login，带 redirect 回跳
 */
const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    component: AdminLayout,
    children: [
      { path: '', name: 'dashboard', component: DashboardView },
      {
        path: 'users',
        name: 'users',
        component: () => import('@/views/UsersView.vue'),
      },
      {
        path: 'topics',
        name: 'topics',
        component: () => import('@/views/TopicsView.vue'),
      },
      {
        path: 'tags',
        name: 'tags',
        component: () => import('@/views/TagsView.vue'),
      },
      {
        path: 'questions',
        name: 'questions',
        component: () => import('@/views/QuestionsView.vue'),
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

/**
 * 全局前置守卫（admin.md §1.1 / user-flow.md）：
 * - 已认证访问 /login → 跳 dashboard，避免重复登录
 * - 未认证访问受保护页（meta.public 非 true）→ 跳 /login，带 redirect 回跳
 */
router.beforeEach((to) => {
  const authStore = useAuthStore()
  const isPublic = to.meta.public === true

  // 已登录访问公开页 → 回 dashboard
  if (isPublic && authStore.isAuthenticated) {
    return { name: 'dashboard' }
  }
  // 未登录访问受保护页 → 跳登录，带 redirect
  if (!isPublic && !authStore.isAuthenticated) {
    return { name: 'login', query: to.fullPath !== '/' ? { redirect: to.fullPath } : {} }
  }
  return true
})

export default router

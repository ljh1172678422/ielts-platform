import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import DefaultLayout from '@/layouts/DefaultLayout.vue'
import HomeView from '@/views/HomeView.vue'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: DefaultLayout,
    children: [
      // 首页 public（落地页：未登录展示登录/注册入口，登录后展示欢迎+退出）
      { path: '', name: 'home', component: HomeView, meta: { public: true } },
      // 登录/注册：路由级懒加载（仅访问时加载），public（meta.public = true）
      {
        path: 'login',
        name: 'login',
        component: () => import('@/views/LoginView.vue'),
        meta: { public: true },
      },
      {
        path: 'register',
        name: 'register',
        component: () => import('@/views/RegisterView.vue'),
        meta: { public: true },
      },
      // /profile 受保护（无 meta.public → 守卫要求 authenticated），Phase 4.8
      {
        path: 'profile',
        name: 'profile',
        component: () => import('@/views/ProfileView.vue'),
      },
      // 题库（Phase 6.4，受保护：浏览/收藏需登录，questions.md §1.2 全接口 Bearer）
      {
        path: 'questions',
        name: 'questions',
        component: () => import('@/views/QuestionsView.vue'),
      },
      {
        path: 'questions/:id',
        name: 'question-detail',
        component: () => import('@/views/QuestionDetailView.vue'),
        props: true,
      },
      // 练习页（Phase 7.6，受保护：practice.md §1.2 全接口 Bearer）
      {
        path: 'practice/:id',
        name: 'practice',
        component: () => import('@/views/PracticeView.vue'),
        props: true,
      },
      // 学习数据页（Phase 9.5，受保护：learning.md §1.2 全接口 Bearer）
      {
        path: 'learning',
        name: 'learning',
        component: () => import('@/views/LearningView.vue'),
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

/**
 * 全局前置守卫（auth.md §5.4 / user-flow.md）：
 * - 已认证访问 public 页（/login /register）→ 跳首页，避免重复登录
 * - 未认证访问受保护页（meta.public 非 true）→ 跳 /login，带 redirect 回跳
 */
router.beforeEach((to) => {
  const authStore = useAuthStore()
  const isPublic = to.meta.public === true

  // 已登录访问公开页 → 回首页
  if (isPublic && authStore.isAuthenticated) {
    return { name: 'home' }
  }
  // 未登录访问受保护页 → 跳登录，带 redirect
  if (!isPublic && !authStore.isAuthenticated) {
    return { name: 'login', query: to.fullPath !== '/' ? { redirect: to.fullPath } : {} }
  }
  return true
})

export default router

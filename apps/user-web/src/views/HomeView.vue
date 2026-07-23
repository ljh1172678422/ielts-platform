<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

async function handleLogout(): Promise<void> {
  await authStore.logout()
  ElMessage.success('已退出登录')
  // 退出后留在首页（public），展示登录/注册入口
}

function goLogin(): void {
  router.push({ name: 'login' })
}

function goRegister(): void {
  router.push({ name: 'register' })
}
</script>

<template>
  <main class="flex min-h-screen flex-col items-center justify-center bg-gray-50 px-4">
    <div class="w-full max-w-md text-center">
      <h1 class="text-3xl font-bold text-gray-900">IELTS Speaking</h1>
      <p class="mt-2 text-gray-500">雅思口语练习平台 · user-web</p>

      <!-- 已登录：展示认证态 + 退出 -->
      <div v-if="authStore.isAuthenticated" class="mt-8">
        <p class="text-gray-700">
          已登录：<span class="font-medium">{{ authStore.user?.email }}</span>
          <span class="ml-2 rounded bg-indigo-50 px-2 py-0.5 text-xs text-indigo-600">
            {{ authStore.role }}
          </span>
        </p>
        <div class="mt-4 flex justify-center gap-3">
          <el-button type="primary" @click="router.push({ name: 'questions' })">题库</el-button>
          <el-button @click="router.push({ name: 'profile' })">我的</el-button>
          <el-button @click="handleLogout">退出登录</el-button>
        </div>
      </div>

      <!-- 未登录：展示登录/注册入口 -->
      <div v-else class="mt-8 flex justify-center gap-3">
        <el-button type="primary" @click="goLogin">登录</el-button>
        <el-button @click="goRegister">注册</el-button>
      </div>
    </div>
  </main>
</template>

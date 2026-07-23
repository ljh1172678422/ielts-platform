<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { ApiError } from '@/api'
import type { LoginRequest } from '@ielts/types'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const formRef = ref<FormInstance>()
const loading = ref(false)
const form = reactive<LoginRequest>({
  email: '',
  password: '',
})

const rules: FormRules<LoginRequest> = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' },
  ],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleSubmit(): Promise<void> {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await authStore.login(form)
    ElMessage.success('登录成功')
    // 优先回跳 redirect 参数指向的原页面，否则回首页
    const redirect = (route.query.redirect as string) || '/'
    router.replace(redirect)
  } catch (err) {
    // 3002 防枚举：邮箱或密码错误；其他业务码直接展示 message
    const message = err instanceof ApiError ? err.message : '登录失败，请稍后重试'
    ElMessage.error(message)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="flex min-h-screen items-center justify-center bg-gray-50 px-4">
    <div class="w-full max-w-md">
      <div class="rounded-2xl bg-white p-8 shadow-sm ring-1 ring-gray-100">
        <header class="mb-6 text-center">
          <h1 class="text-2xl font-bold text-gray-900">登录</h1>
          <p class="mt-1 text-sm text-gray-500">IELTS Speaking 练习平台</p>
        </header>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-position="top"
          @submit.prevent="handleSubmit"
        >
          <el-form-item label="邮箱" prop="email">
            <el-input
              v-model="form.email"
              type="email"
              placeholder="you@example.com"
              autocomplete="email"
              clearable
            />
          </el-form-item>

          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="请输入密码"
              autocomplete="current-password"
              show-password
              @keyup.enter="handleSubmit"
            />
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              class="w-full"
              :loading="loading"
              @click="handleSubmit"
            >
              登录
            </el-button>
          </el-form-item>
        </el-form>

        <p class="text-center text-sm text-gray-500">
          还没有账号？
          <RouterLink to="/register" class="font-medium text-indigo-600 hover:text-indigo-500">
            立即注册
          </RouterLink>
        </p>
      </div>
    </div>
  </main>
</template>

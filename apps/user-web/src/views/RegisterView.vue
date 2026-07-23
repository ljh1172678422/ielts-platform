<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormItemRule, type FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { ApiError } from '@/api'
import type { RegisterRequest } from '@ielts/types'

const router = useRouter()
const authStore = useAuthStore()

const formRef = ref<FormInstance>()
const loading = ref(false)

/** 表单模型：含 confirmPassword（仅前端校验，不提交）。 */
const form = reactive({
  email: '',
  password: '',
  confirmPassword: '',
  nickname: '',
  timezone: 'Asia/Shanghai',
})

const validateConfirm: FormItemRule['validator'] = (_rule, value, callback) => {
  if (value !== form.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const rules: FormRules<typeof form> = {
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' },
  ],
  // auth.md §6.1：MVP 仅长度校验 8..64
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, max: 64, message: '密码长度需在 8..64 之间', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    { validator: validateConfirm, trigger: 'blur' },
  ],
  nickname: [{ max: 100, message: '昵称长度不超过 100', trigger: 'blur' }],
  timezone: [{ required: true, message: '请输入时区', trigger: 'blur' }],
}

async function handleSubmit(): Promise<void> {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    // 仅提交 API 契约字段（auth.md §7.1），nickname 空串转 undefined（缺省取 email 本地部分）
    const req: RegisterRequest = {
      email: form.email,
      password: form.password,
      nickname: form.nickname.trim() || undefined,
      timezone: form.timezone,
    }
    await authStore.register(req)
    ElMessage.success('注册成功')
    router.replace('/')
  } catch (err) {
    // 3001 邮箱已注册 / 1001 字段不合规；其他业务码直接展示 message
    const message = err instanceof ApiError ? err.message : '注册失败，请稍后重试'
    ElMessage.error(message)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="flex min-h-screen items-center justify-center bg-gray-50 px-4 py-8">
    <div class="w-full max-w-md">
      <div class="rounded-2xl bg-white p-8 shadow-sm ring-1 ring-gray-100">
        <header class="mb-6 text-center">
          <h1 class="text-2xl font-bold text-gray-900">注册</h1>
          <p class="mt-1 text-sm text-gray-500">创建你的 IELTS Speaking 账号</p>
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
              placeholder="8-64 位"
              autocomplete="new-password"
              show-password
            />
          </el-form-item>

          <el-form-item label="确认密码" prop="confirmPassword">
            <el-input
              v-model="form.confirmPassword"
              type="password"
              placeholder="再次输入密码"
              autocomplete="new-password"
              show-password
              @keyup.enter="handleSubmit"
            />
          </el-form-item>

          <el-form-item label="昵称（可选）" prop="nickname">
            <el-input
              v-model="form.nickname"
              placeholder="留空则使用邮箱前缀"
              maxlength="100"
            />
          </el-form-item>

          <el-form-item label="时区" prop="timezone">
            <el-input
              v-model="form.timezone"
              placeholder="IANA 时区名，如 Asia/Shanghai"
            />
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              class="w-full"
              :loading="loading"
              @click="handleSubmit"
            >
              注册
            </el-button>
          </el-form-item>
        </el-form>

        <p class="text-center text-sm text-gray-500">
          已有账号？
          <RouterLink to="/login" class="font-medium text-indigo-600 hover:text-indigo-500">
            去登录
          </RouterLink>
        </p>
      </div>
    </div>
  </main>
</template>

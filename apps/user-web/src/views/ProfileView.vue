<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormItemRule, type FormRules } from 'element-plus'
import { api, ApiError } from '@/api'
import { useAuthStore } from '@/stores/auth'
import type {
  ChangePasswordRequest,
  CreateGoalRequest,
  GoalStatus,
  GoalsResponse,
  UpdateProfileRequest,
  UserGoal,
} from '@ielts/types'

const authStore = useAuthStore()

// ==================== 资料编辑（users.md §2/§3） ====================
const profileFormRef = ref<FormInstance>()
const profileLoading = ref(false)
const profileForm = reactive({
  nickname: '',
  avatar_url: '',
  timezone: 'Asia/Shanghai',
})

const profileRules: FormRules<typeof profileForm> = {
  timezone: [{ required: true, message: '请输入时区', trigger: 'blur' }],
  nickname: [{ max: 100, message: '昵称长度不超过 100', trigger: 'blur' }],
  avatar_url: [
    {
      validator: ((_rule, value: string, callback) => {
        if (value && !/^https?:\/\//.test(value)) {
          callback(new Error('头像地址需为 http(s) URL'))
        } else if (value && value.length > 500) {
          callback(new Error('头像地址长度不超过 500'))
        } else {
          callback()
        }
      }) as FormItemRule['validator'],
      trigger: 'blur',
    },
  ],
}

async function handleSaveProfile(): Promise<void> {
  if (!profileFormRef.value) return
  const valid = await profileFormRef.value.validate().catch(() => false)
  if (!valid) return

  profileLoading.value = true
  try {
    // users.md §3.1：全量替换，空串转 null（清空）
    const req: UpdateProfileRequest = {
      nickname: profileForm.nickname.trim() || null,
      avatar_url: profileForm.avatar_url.trim() || null,
      timezone: profileForm.timezone,
    }
    const updated = await api.put<import('@ielts/types').UserPublic>('/users/me', req)
    authStore.user = updated
    authStore.role = updated.role
    ElMessage.success('资料已更新')
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : '更新失败，请稍后重试')
  } finally {
    profileLoading.value = false
  }
}

// ==================== 修改密码（users.md §4） ====================
const pwdFormRef = ref<FormInstance>()
const pwdLoading = ref(false)
const pwdForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

const validateConfirmPwd: FormItemRule['validator'] = (_rule, value, callback) => {
  if (value !== pwdForm.new_password) {
    callback(new Error('两次输入的新密码不一致'))
  } else if (value === pwdForm.old_password) {
    callback(new Error('新密码不能与旧密码相同'))
  } else {
    callback()
  }
}

const pwdRules: FormRules<typeof pwdForm> = {
  old_password: [{ required: true, message: '请输入旧密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, max: 64, message: '密码长度需在 8..64 之间', trigger: 'blur' },
  ],
  confirm_password: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    { validator: validateConfirmPwd, trigger: 'blur' },
  ],
}

async function handleChangePassword(): Promise<void> {
  if (!pwdFormRef.value) return
  const valid = await pwdFormRef.value.validate().catch(() => false)
  if (!valid) return

  pwdLoading.value = true
  try {
    const req: ChangePasswordRequest = {
      old_password: pwdForm.old_password,
      new_password: pwdForm.new_password,
    }
    await api.put<null>('/users/me/password', req)
    ElMessage.success('密码已修改（旧 token 仍有效至过期，ADR-027）')
    pwdFormRef.value.resetFields()
  } catch (err) {
    // 3003 旧密码错误 / 1001 校验失败
    ElMessage.error(err instanceof ApiError ? err.message : '修改失败，请稍后重试')
  } finally {
    pwdLoading.value = false
  }
}

// ==================== 学习目标（users.md §5/§6/§7） ====================
const goalsLoading = ref(false)
const currentGoal = ref<UserGoal | null>(null)
const historyGoals = ref<UserGoal[]>([])

async function fetchGoals(): Promise<void> {
  goalsLoading.value = true
  try {
    const data = await api.get<GoalsResponse>('/users/me/goals')
    currentGoal.value = data.current
    historyGoals.value = data.history
  } catch (err) {
    ElMessage.error(err instanceof ApiError ? err.message : '加载目标失败')
  } finally {
    goalsLoading.value = false
  }
}

// 新建目标对话框
const goalDialogVisible = ref(false)
const goalFormRef = ref<FormInstance>()
const goalSaving = ref(false)
const goalForm = reactive({
  target_score: null as number | null,
  current_level: '',
  exam_date: '',
  daily_goal_minutes: null as number | null,
  weekly_goal_minutes: null as number | null,
})

function openGoalDialog(): void {
  // users.md §6.4：已存在 active 目标时创建会 1004，前端引导先归档
  if (currentGoal.value) {
    ElMessage.warning('已有进行中的目标，请先将其标记为已达成或归档')
    return
  }
  goalForm.target_score = null
  goalForm.current_level = ''
  goalForm.exam_date = ''
  goalForm.daily_goal_minutes = null
  goalForm.weekly_goal_minutes = null
  goalDialogVisible.value = true
}

async function handleCreateGoal(): Promise<void> {
  if (!goalFormRef.value) return
  const valid = await goalFormRef.value.validate().catch(() => false)
  if (!valid) return

  // users.md §6.1：至少一字段非空
  const hasValue =
    goalForm.target_score !== null ||
    goalForm.current_level.trim() !== '' ||
    goalForm.exam_date !== '' ||
    goalForm.daily_goal_minutes !== null ||
    goalForm.weekly_goal_minutes !== null
  if (!hasValue) {
    ElMessage.error('请至少填写一项目标内容')
    return
  }

  goalSaving.value = true
  try {
    const req: CreateGoalRequest = {
      target_score: goalForm.target_score,
      current_level: goalForm.current_level.trim() || null,
      exam_date: goalForm.exam_date || null,
      daily_goal_minutes: goalForm.daily_goal_minutes,
      weekly_goal_minutes: goalForm.weekly_goal_minutes,
    }
    await api.post<UserGoal>('/users/me/goals', req)
    ElMessage.success('目标已创建')
    goalDialogVisible.value = false
    await fetchGoals()
  } catch (err) {
    // 1004 已存在 active / 1001 全空
    ElMessage.error(err instanceof ApiError ? err.message : '创建失败，请稍后重试')
  } finally {
    goalSaving.value = false
  }
}

/** 更新目标状态（users.md §7）：标记当前目标为 achieved/archived。 */
async function handleUpdateGoalStatus(goal: UserGoal, status: GoalStatus): Promise<void> {
  try {
    const req = {
      target_score: goal.target_score,
      current_level: goal.current_level,
      exam_date: goal.exam_date,
      daily_goal_minutes: goal.daily_goal_minutes,
      weekly_goal_minutes: goal.weekly_goal_minutes,
      status,
    }
    await api.put<UserGoal>(`/users/me/goals/${goal.id}`, req)
    ElMessage.success('目标状态已更新')
    await fetchGoals()
  } catch (err) {
    // 1002 不存在 / 1004 改回 active 冲突
    ElMessage.error(err instanceof ApiError ? err.message : '更新失败，请稍后重试')
  }
}

const goalRules: FormRules<typeof goalForm> = {
  target_score: [
    {
      validator: ((_rule, value: number | null, callback) => {
        if (value !== null && (value < 0 || value > 9)) {
          callback(new Error('目标分数需在 0.0–9.0 之间'))
        } else {
          callback()
        }
      }) as FormItemRule['validator'],
      trigger: 'blur',
    },
  ],
  current_level: [{ max: 20, message: '长度不超过 20', trigger: 'blur' }],
}

const statusLabel: Record<GoalStatus, string> = {
  active: '进行中',
  achieved: '已达成',
  archived: '已归档',
}

const statusTagType: Record<GoalStatus, 'success' | 'warning' | 'info'> = {
  active: 'warning',
  achieved: 'success',
  archived: 'info',
}

// ==================== 初始化 ====================
onMounted(async () => {
  // 路由守卫已确保 authenticated；若 user 为空（刷新后），先拉取
  if (!authStore.user) {
    try {
      await authStore.fetchProfile()
    } catch {
      // 拉取失败由 401 拦截器处理跳登录
    }
  }
  // 用最新 profile 填充表单
  syncProfileForm()
  await fetchGoals()
})

function syncProfileForm(): void {
  const p = authStore.user?.profile
  profileForm.nickname = p?.nickname ?? ''
  profileForm.avatar_url = p?.avatar_url ?? ''
  profileForm.timezone = p?.timezone ?? 'Asia/Shanghai'
}
</script>

<template>
  <main class="min-h-screen bg-gray-50 py-8">
    <div class="mx-auto max-w-3xl px-4">
      <header class="mb-6">
        <h1 class="text-2xl font-bold text-gray-900">我的</h1>
        <p class="mt-1 text-sm text-gray-500">
          {{ authStore.user?.email }}
          <span class="ml-2 rounded bg-indigo-50 px-2 py-0.5 text-xs text-indigo-600">
            {{ authStore.role }}
          </span>
        </p>
      </header>

      <el-tabs class="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-gray-100">
        <!-- ========== 资料编辑 ========== -->
        <el-tab-pane label="资料">
          <el-form
            ref="profileFormRef"
            :model="profileForm"
            :rules="profileRules"
            label-position="top"
            class="max-w-md"
          >
            <el-form-item label="昵称" prop="nickname">
              <el-input v-model="profileForm.nickname" placeholder="留空则清空" maxlength="100" />
            </el-form-item>
            <el-form-item label="头像 URL" prop="avatar_url">
              <el-input v-model="profileForm.avatar_url" placeholder="https://..." />
            </el-form-item>
            <el-form-item label="时区" prop="timezone">
              <el-input v-model="profileForm.timezone" placeholder="IANA 时区名，如 Asia/Shanghai" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="profileLoading" @click="handleSaveProfile">
                保存资料
              </el-button>
            </el-form-item>
          </el-form>
          <p class="mt-2 text-xs text-gray-400">邮箱、角色、状态不可修改（users.md §8.2）</p>
        </el-tab-pane>

        <!-- ========== 修改密码 ========== -->
        <el-tab-pane label="密码">
          <el-form
            ref="pwdFormRef"
            :model="pwdForm"
            :rules="pwdRules"
            label-position="top"
            class="max-w-md"
          >
            <el-form-item label="旧密码" prop="old_password">
              <el-input v-model="pwdForm.old_password" type="password" show-password />
            </el-form-item>
            <el-form-item label="新密码" prop="new_password">
              <el-input
                v-model="pwdForm.new_password"
                type="password"
                placeholder="8-64 位"
                show-password
              />
            </el-form-item>
            <el-form-item label="确认新密码" prop="confirm_password">
              <el-input v-model="pwdForm.confirm_password" type="password" show-password />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="pwdLoading" @click="handleChangePassword">
                修改密码
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- ========== 学习目标 ========== -->
        <el-tab-pane label="目标">
          <div v-loading="goalsLoading">
            <div class="mb-4 flex items-center justify-between">
              <h2 class="text-lg font-semibold text-gray-800">学习目标</h2>
              <el-button type="primary" size="small" @click="openGoalDialog">新建目标</el-button>
            </div>

            <!-- 当前进行中目标 -->
            <div v-if="currentGoal" class="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-4">
              <div class="mb-2 flex items-center justify-between">
                <span class="font-medium text-gray-800">当前目标</span>
                <el-tag :type="statusTagType[currentGoal.status]" size="small">
                  {{ statusLabel[currentGoal.status] }}
                </el-tag>
              </div>
              <dl class="grid grid-cols-2 gap-x-4 gap-y-1 text-sm text-gray-700">
                <div>目标分数：{{ currentGoal.target_score ?? '—' }}</div>
                <div>当前水平：{{ currentGoal.current_level ?? '—' }}</div>
                <div>考试日期：{{ currentGoal.exam_date ?? '—' }}</div>
                <div>每日目标：{{ currentGoal.daily_goal_minutes ?? '—' }} 分钟</div>
                <div>每周目标：{{ currentGoal.weekly_goal_minutes ?? '—' }} 分钟</div>
              </dl>
              <div class="mt-3 flex gap-2">
                <el-button size="small" @click="handleUpdateGoalStatus(currentGoal, 'achieved')">
                  标记为已达成
                </el-button>
                <el-button size="small" @click="handleUpdateGoalStatus(currentGoal, 'archived')">
                  归档
                </el-button>
              </div>
            </div>

            <el-empty v-else-if="!goalsLoading" description="暂无进行中的目标" />

            <!-- 历史目标 -->
            <div v-if="historyGoals.length">
              <h3 class="mb-2 text-sm font-medium text-gray-500">历史目标</h3>
              <ul class="space-y-2">
                <li
                  v-for="g in historyGoals"
                  :key="g.id"
                  class="rounded-lg border border-gray-100 bg-white p-3"
                >
                  <div class="flex items-center justify-between">
                    <span class="text-sm text-gray-700">
                      目标 {{ g.target_score ?? '—' }} · 考试 {{ g.exam_date ?? '—' }}
                    </span>
                    <div class="flex items-center gap-2">
                      <el-tag :type="statusTagType[g.status]" size="small">
                        {{ statusLabel[g.status] }}
                      </el-tag>
                      <el-button
                        v-if="g.status !== 'active'"
                        size="small"
                        link
                        @click="handleUpdateGoalStatus(g, 'active')"
                      >
                        重新激活
                      </el-button>
                    </div>
                  </div>
                  <p class="mt-1 text-xs text-gray-400">
                    每日 {{ g.daily_goal_minutes ?? '—' }} 分钟 · 每周
                    {{ g.weekly_goal_minutes ?? '—' }} 分钟
                  </p>
                </li>
              </ul>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>

      <!-- 新建目标对话框 -->
      <el-dialog v-model="goalDialogVisible" title="新建学习目标" width="460px">
        <el-form ref="goalFormRef" :model="goalForm" :rules="goalRules" label-position="top">
          <el-form-item label="目标分数（0.0–9.0）" prop="target_score">
            <el-input-number
              v-model="goalForm.target_score"
              :min="0"
              :max="9"
              :step="0.5"
              :precision="1"
              controls-position="right"
              class="w-full"
            />
          </el-form-item>
          <el-form-item label="当前水平" prop="current_level">
            <el-input v-model="goalForm.current_level" placeholder="如 6.0" maxlength="20" />
          </el-form-item>
          <el-form-item label="考试日期" prop="exam_date">
            <el-date-picker
              v-model="goalForm.exam_date"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="选择日期"
              class="w-full"
            />
          </el-form-item>
          <el-form-item label="每日目标（分钟）" prop="daily_goal_minutes">
            <el-input-number
              v-model="goalForm.daily_goal_minutes"
              :min="0"
              :step="5"
              controls-position="right"
              class="w-full"
            />
          </el-form-item>
          <el-form-item label="每周目标（分钟）" prop="weekly_goal_minutes">
            <el-input-number
              v-model="goalForm.weekly_goal_minutes"
              :min="0"
              :step="15"
              controls-position="right"
              class="w-full"
            />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="goalDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="goalSaving" @click="handleCreateGoal">创建</el-button>
        </template>
      </el-dialog>
    </div>
  </main>
</template>

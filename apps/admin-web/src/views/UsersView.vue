<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, ApiError } from '@/api'
import { useAuthStore } from '@/stores/auth'
import type { AdminUserListItem, AdminUsersData } from '@/types/admin'

/**
 * 用户管理页（admin.md §3）：用户列表 + 启用/禁用。
 * - GET /admin/users（分页 + keyword/status/role 筛选）
 * - PUT /admin/users/{id}/status（8006 防自锁 / 8007 防管理员互操作，后端兜底）
 *
 * 前端额外约束（UX，后端仍是最终防线）：
 * - 当前管理员账号不显示"禁用"按钮（8006）
 * - admin 角色行不显示"禁用"按钮（8007，仅可操作 user 角色）
 */
const authStore = useAuthStore()

const loading = ref(false)
const submitting = ref(false)
const items = ref<AdminUserListItem[]>([])
const total = ref(0)

const filters = reactive({
  keyword: '',
  status: '' as '' | 'active' | 'disabled',
  role: '' as '' | 'user' | 'admin',
})

const pagination = reactive({
  page: 1,
  page_size: 20,
})

async function fetchUsers(): Promise<void> {
  loading.value = true
  try {
    const params: Record<string, string | number> = {
      page: pagination.page,
      page_size: pagination.page_size,
    }
    if (filters.keyword) params.keyword = filters.keyword.trim()
    if (filters.status) params.status = filters.status
    if (filters.role) params.role = filters.role

    const qs = new URLSearchParams(
      Object.entries(params).map(([k, v]) => [k, String(v)]),
    ).toString()
    const data = await api.get<AdminUsersData>(`/admin/users?${qs}`)
    items.value = data.items
    total.value = data.total
  } catch (err) {
    const message = err instanceof ApiError ? err.message : '加载用户列表失败'
    ElMessage.error(message)
  } finally {
    loading.value = false
  }
}

function handleSearch(): void {
  pagination.page = 1
  void fetchUsers()
}

function handleReset(): void {
  filters.keyword = ''
  filters.status = ''
  filters.role = ''
  pagination.page = 1
  void fetchUsers()
}

function handlePageChange(page: number): void {
  pagination.page = page
  void fetchUsers()
}

function handleSizeChange(size: number): void {
  pagination.page_size = size
  pagination.page = 1
  void fetchUsers()
}

/**
 * 切换用户状态（admin.md §3.2）。
 * 后端 8006（禁用自己）/ 8007（禁用其他管理员）兜底，前端用 canToggle 提前隐藏按钮。
 */
async function handleToggleStatus(row: AdminUserListItem): Promise<void> {
  const next = row.status === 'active' ? 'disabled' : 'active'
  const action = next === 'disabled' ? '禁用' : '启用'
  try {
    await ElMessageBox.confirm(`确定${action}用户 ${row.email} 吗？`, '提示', {
      type: 'warning',
      confirmButtonText: action,
      cancelButtonText: '取消',
    })
  } catch {
    return // 用户取消
  }

  submitting.value = true
  try {
    const updated = await api.put<AdminUserListItem>(
      `/admin/users/${row.id}/status`,
      { status: next },
    )
    // 原地替换，避免重新拉取整页
    const idx = items.value.findIndex((u) => u.id === row.id)
    if (idx >= 0) items.value[idx] = updated
    ElMessage.success(`已${action}`)
  } catch (err) {
    const message = err instanceof ApiError ? err.message : `${action}失败`
    ElMessage.error(message)
  } finally {
    submitting.value = false
  }
}

/** 是否可对该用户执行启用/禁用（admin.md §3.2：8006 防自锁 / 8007 防管理员互操作）。 */
function canToggle(row: AdminUserListItem): boolean {
  // 不能操作自己（8006）
  if (authStore.user && row.id === authStore.user.id) return false
  // 仅可操作 user 角色，admin 角色不可操作（8007）
  if (row.role === 'admin') return false
  return true
}

function formatTime(value: string | null): string {
  if (!value) return '—'
  return value.replace('T', ' ').slice(0, 19)
}

onMounted(fetchUsers)
</script>

<template>
  <div v-loading="loading" class="space-y-4 p-6">
    <h1 class="text-xl font-semibold">用户管理</h1>

    <!-- 筛选区 -->
    <el-card shadow="never">
      <div class="flex flex-wrap items-center gap-3">
        <el-input
          v-model="filters.keyword"
          placeholder="搜索邮箱或昵称"
          clearable
          class="w-64"
          @keyup.enter="handleSearch"
        />
        <el-select
          v-model="filters.status"
          placeholder="状态"
          clearable
          class="w-32"
        >
          <el-option label="启用" value="active" />
          <el-option label="禁用" value="disabled" />
        </el-select>
        <el-select
          v-model="filters.role"
          placeholder="角色"
          clearable
          class="w-32"
        >
          <el-option label="普通用户" value="user" />
          <el-option label="管理员" value="admin" />
        </el-select>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="handleReset">重置</el-button>
      </div>
    </el-card>

    <!-- 列表 -->
    <el-card shadow="never">
      <el-table :data="items" stripe>
        <el-table-column label="ID" prop="id" width="80" />
        <el-table-column label="邮箱" prop="email" min-width="200" />
        <el-table-column label="昵称" min-width="120">
          <template #default="{ row }">
            {{ row.nickname || '—' }}
          </template>
        </el-table-column>
        <el-table-column label="角色" width="100">
          <template #default="{ row }">
            <el-tag :type="row.role === 'admin' ? 'danger' : 'info'" size="small">
              {{ row.role === 'admin' ? '管理员' : '用户' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'warning'" size="small">
              {{ row.status === 'active' ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最后登录" width="180">
          <template #default="{ row }">{{ formatTime(row.last_login_at) }}</template>
        </el-table-column>
        <el-table-column label="注册时间" width="180">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="canToggle(row as AdminUserListItem)"
              :type="row.status === 'active' ? 'warning' : 'success'"
              size="small"
              :loading="submitting"
              link
              @click="handleToggleStatus(row as AdminUserListItem)"
            >
              {{ row.status === 'active' ? '禁用' : '启用' }}
            </el-button>
            <span v-else class="text-xs text-gray-400">不可操作</span>
          </template>
        </el-table-column>
      </el-table>

      <div class="mt-4 flex justify-end">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </el-card>
  </div>
</template>

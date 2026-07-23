<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { api, ApiError } from '@/api'
import type { AdminTopicItem, TopicUpsertRequest } from '@/types/admin'

/**
 * 主题管理页（admin.md §4）：CRUD + 软删除。
 * - GET /admin/topics（非分页，主题数量少）
 * - POST /admin/topics（1004 name/slug 冲突）
 * - PUT /admin/topics/{id}（8001 Other 主题 name/slug 不可改，仅 description 可改）
 * - DELETE /admin/topics/{id}（8001 Other 不可删 / 8002 仍有 published 题目）
 *
 * Other 主题（is_system=true）：前端禁用编辑/删除按钮，仅允许在编辑弹窗改 description。
 */
const loading = ref(false)
const submitting = ref(false)
const items = ref<AdminTopicItem[]>([])

const keyword = ref('')

interface DialogState {
  visible: boolean
  isEdit: boolean
  editId: string | null
  isSystem: boolean
  form: TopicUpsertRequest
}

const dialog = reactive<DialogState>({
  visible: false,
  isEdit: false,
  editId: null,
  isSystem: false,
  form: { name: '', slug: '', description: '' },
})

const formRef = ref<FormInstance>()

const rules: FormRules<TopicUpsertRequest> = {
  name: [
    { required: true, message: '请输入主题名称', trigger: 'blur' },
    { max: 50, message: '长度不超过 50', trigger: 'blur' },
  ],
  slug: [{ max: 50, message: '长度不超过 50', trigger: 'blur' }],
  description: [{ max: 200, message: '长度不超过 200', trigger: 'blur' }],
}

async function fetchTopics(): Promise<void> {
  loading.value = true
  try {
    const url = keyword.value.trim()
      ? `/admin/topics?keyword=${encodeURIComponent(keyword.value.trim())}`
      : '/admin/topics'
    const data = await api.get<{ items: AdminTopicItem[] }>(url)
    items.value = data.items
  } catch (err) {
    const message = err instanceof ApiError ? err.message : '加载主题列表失败'
    ElMessage.error(message)
  } finally {
    loading.value = false
  }
}

function handleSearch(): void {
  void fetchTopics()
}

function openCreate(): void {
  dialog.isEdit = false
  dialog.editId = null
  dialog.isSystem = false
  dialog.form = { name: '', slug: '', description: '' }
  dialog.visible = true
}

function openEdit(row: AdminTopicItem): void {
  dialog.isEdit = true
  dialog.editId = row.id
  dialog.isSystem = row.is_system
  dialog.form = {
    name: row.name,
    slug: row.slug,
    description: row.description ?? '',
  }
  dialog.visible = true
}

async function handleSubmit(): Promise<void> {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  // Other 主题（is_system=true）只允许改 description（admin.md §4.3 / §7.2）
  // 前端锁定：name/slug 不可改；提交时强制用原值，避免误传。
  const payload: TopicUpsertRequest = {
    name: dialog.form.name,
    description: dialog.form.description || undefined,
  }
  if (!dialog.isSystem) {
    payload.slug = dialog.form.slug || undefined
  }

  submitting.value = true
  try {
    if (dialog.isEdit && dialog.editId) {
      await api.put<AdminTopicItem>(`/admin/topics/${dialog.editId}`, payload)
      ElMessage.success('主题已更新')
    } else {
      await api.post<AdminTopicItem>('/admin/topics', payload)
      ElMessage.success('主题已创建')
    }
    dialog.visible = false
    await fetchTopics()
  } catch (err) {
    const message = err instanceof ApiError ? err.message : '保存失败'
    ElMessage.error(message)
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row: AdminTopicItem): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确定删除主题「${row.name}」吗？该操作为软删除，可由 DB 恢复。`,
      '删除主题',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }

  submitting.value = true
  try {
    await api.delete<null>(`/admin/topics/${row.id}`)
    ElMessage.success('主题已删除')
    await fetchTopics()
  } catch (err) {
    // 8001 Other 不可删 / 8002 仍有 published 题目
    const message = err instanceof ApiError ? err.message : '删除失败'
    ElMessage.error(message)
  } finally {
    submitting.value = false
  }
}

function formatTime(value: string): string {
  return value.replace('T', ' ').slice(0, 19)
}

onMounted(fetchTopics)
</script>

<template>
  <div v-loading="loading" class="space-y-4 p-6">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-semibold">主题管理</h1>
      <el-button type="primary" @click="openCreate">新建主题</el-button>
    </div>

    <!-- 搜索 -->
    <el-card shadow="never">
      <div class="flex items-center gap-3">
        <el-input
          v-model="keyword"
          placeholder="搜索主题名称"
          clearable
          class="w-64"
          @keyup.enter="handleSearch"
        />
        <el-button type="primary" @click="handleSearch">查询</el-button>
      </div>
    </el-card>

    <!-- 列表 -->
    <el-card shadow="never">
      <el-table :data="items" stripe>
        <el-table-column label="ID" prop="id" width="80" />
        <el-table-column label="名称" min-width="160">
          <template #default="{ row }">
            {{ row.name }}
            <el-tag v-if="row.is_system" type="danger" size="small" class="ml-2">系统</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Slug" prop="slug" min-width="140" />
        <el-table-column label="描述" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">{{ row.description || '—' }}</template>
        </el-table-column>
        <el-table-column label="题目数" prop="question_count" width="100" align="center" />
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="openEdit(row as AdminTopicItem)">编辑</el-button>
            <el-button
              v-if="!row.is_system"
              size="small"
              link
              type="danger"
              :loading="submitting"
              @click="handleDelete(row as AdminTopicItem)"
            >
              删除
            </el-button>
            <span v-else class="ml-2 text-xs text-gray-400">系统保留</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建/编辑弹窗 -->
    <el-dialog
      v-model="dialog.visible"
      :title="dialog.isEdit ? '编辑主题' : '新建主题'"
      width="520px"
    >
      <el-alert
        v-if="dialog.isSystem"
        type="warning"
        :closable="false"
        show-icon
        title="系统保留主题（Other）：name 与 slug 不可修改，仅可修改描述。"
        class="mb-4"
      />
      <el-form
        ref="formRef"
        :model="dialog.form"
        :rules="rules"
        label-position="top"
      >
        <el-form-item label="名称" prop="name">
          <el-input
            v-model="dialog.form.name"
            :disabled="dialog.isSystem"
            placeholder="主题名称"
            maxlength="50"
          />
        </el-form-item>
        <el-form-item label="Slug" prop="slug">
          <el-input
            v-model="dialog.form.slug"
            :disabled="dialog.isSystem"
            placeholder="留空则由名称自动生成"
            maxlength="50"
          />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="dialog.form.description"
            type="textarea"
            :rows="3"
            placeholder="可选"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

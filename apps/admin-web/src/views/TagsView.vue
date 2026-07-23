<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { api, ApiError } from '@/api'
import type { AdminTagItem, TagUpsertRequest } from '@/types/admin'

/**
 * 标签管理页（admin.md §5）：CRUD + 软删除。无系统保留标签。
 * - GET /admin/tags（非分页）
 * - POST /admin/tags（1004 name/slug 冲突）
 * - PUT /admin/tags/{id}（4004 不存在 / 1004 冲突）
 * - DELETE /admin/tags/{id}（4004 不存在 / 8002 仍被题目引用，需先在题目编辑页移除关联）
 */
const loading = ref(false)
const submitting = ref(false)
const items = ref<AdminTagItem[]>([])

const keyword = ref('')

interface DialogState {
  visible: boolean
  isEdit: boolean
  editId: string | null
  form: TagUpsertRequest
}

const dialog = reactive<DialogState>({
  visible: false,
  isEdit: false,
  editId: null,
  form: { name: '', slug: '' },
})

const formRef = ref<FormInstance>()

const rules: FormRules<TagUpsertRequest> = {
  name: [
    { required: true, message: '请输入标签名称', trigger: 'blur' },
    { max: 30, message: '长度不超过 30', trigger: 'blur' },
  ],
  slug: [{ max: 30, message: '长度不超过 30', trigger: 'blur' }],
}

async function fetchTags(): Promise<void> {
  loading.value = true
  try {
    const url = keyword.value.trim()
      ? `/admin/tags?keyword=${encodeURIComponent(keyword.value.trim())}`
      : '/admin/tags'
    const data = await api.get<{ items: AdminTagItem[] }>(url)
    items.value = data.items
  } catch (err) {
    const message = err instanceof ApiError ? err.message : '加载标签列表失败'
    ElMessage.error(message)
  } finally {
    loading.value = false
  }
}

function handleSearch(): void {
  void fetchTags()
}

function openCreate(): void {
  dialog.isEdit = false
  dialog.editId = null
  dialog.form = { name: '', slug: '' }
  dialog.visible = true
}

function openEdit(row: AdminTagItem): void {
  dialog.isEdit = true
  dialog.editId = row.id
  dialog.form = { name: row.name, slug: row.slug }
  dialog.visible = true
}

async function handleSubmit(): Promise<void> {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  const payload: TagUpsertRequest = {
    name: dialog.form.name,
    slug: dialog.form.slug || undefined,
  }

  submitting.value = true
  try {
    if (dialog.isEdit && dialog.editId) {
      await api.put<AdminTagItem>(`/admin/tags/${dialog.editId}`, payload)
      ElMessage.success('标签已更新')
    } else {
      await api.post<AdminTagItem>('/admin/tags', payload)
      ElMessage.success('标签已创建')
    }
    dialog.visible = false
    await fetchTags()
  } catch (err) {
    const message = err instanceof ApiError ? err.message : '保存失败'
    ElMessage.error(message)
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row: AdminTagItem): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确定删除标签「${row.name}」吗？该操作为软删除。`,
      '删除标签',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }

  submitting.value = true
  try {
    await api.delete<null>(`/admin/tags/${row.id}`)
    ElMessage.success('标签已删除')
    await fetchTags()
  } catch (err) {
    // 8002 仍被题目引用（需先在题目编辑页移除关联）
    const message = err instanceof ApiError ? err.message : '删除失败'
    ElMessage.error(message)
  } finally {
    submitting.value = false
  }
}

function formatTime(value: string): string {
  return value.replace('T', ' ').slice(0, 19)
}

onMounted(fetchTags)
</script>

<template>
  <div v-loading="loading" class="space-y-4 p-6">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-semibold">标签管理</h1>
      <el-button type="primary" @click="openCreate">新建标签</el-button>
    </div>

    <!-- 搜索 -->
    <el-card shadow="never">
      <div class="flex items-center gap-3">
        <el-input
          v-model="keyword"
          placeholder="搜索标签名称"
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
        <el-table-column label="名称" prop="name" min-width="160" />
        <el-table-column label="Slug" prop="slug" min-width="140" />
        <el-table-column label="题目数" prop="question_count" width="100" align="center" />
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="openEdit(row as AdminTagItem)">编辑</el-button>
            <el-button
              size="small"
              link
              type="danger"
              :loading="submitting"
              @click="handleDelete(row as AdminTagItem)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建/编辑弹窗 -->
    <el-dialog
      v-model="dialog.visible"
      :title="dialog.isEdit ? '编辑标签' : '新建标签'"
      width="480px"
    >
      <el-form
        ref="formRef"
        :model="dialog.form"
        :rules="rules"
        label-position="top"
      >
        <el-form-item label="名称" prop="name">
          <el-input v-model="dialog.form.name" placeholder="标签名称" maxlength="30" />
        </el-form-item>
        <el-form-item label="Slug" prop="slug">
          <el-input
            v-model="dialog.form.slug"
            placeholder="留空则由名称自动生成"
            maxlength="30"
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

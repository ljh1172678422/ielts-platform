<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import {
  ElMessage,
  ElMessageBox,
  type FormInstance,
  type FormRules,
} from 'element-plus'
import { api, ApiError } from '@/api'
import type { QuestionSourceType, QuestionStatus, SpeakingPart } from '@ielts/types'
import type {
  AdminQuestionDetail,
  AdminQuestionListItem,
  AdminQuestionsData,
  AdminTagItem,
  AdminTopicItem,
  QuestionUpsertRequest,
  TopicRef,
} from '@/types/admin'

/**
 * 题目管理页（admin.md §6）：列表筛选 + 创建/编辑 + 状态切换。
 * - GET /admin/questions（分页 + part/topic_id/status/keyword/tag_id/difficulty 筛选）
 * - GET /admin/questions/{id}（详情，含 content/cue_card，编辑时拉取）
 * - POST /admin/questions（4003 topic 不存在 / 4004 tag 不存在）
 * - PUT /admin/questions/{id}（全量替换，tag_ids 变化时事务内重建关联）
 * - PUT /admin/questions/{id}/status（draft/published/disabled 三态切换，MVP 不限制转换方向）
 *
 * 题目不可物理删除（ADR-010），仅 status=disabled。
 * 管理员可见全部状态（draft/published/disabled）。
 */
const loading = ref(false)
const submitting = ref(false)
const detailLoading = ref(false)
const items = ref<AdminQuestionListItem[]>([])
const total = ref(0)

// 主题/标签选项（筛选 + 表单共用，启动时一次性加载）
const topicOptions = ref<AdminTopicItem[]>([])
const tagOptions = ref<AdminTagItem[]>([])

const filters = reactive({
  keyword: '',
  part: null as SpeakingPart | null,
  topic_id: '',
  status: '' as '' | QuestionStatus,
  tag_id: '',
  difficulty: null as number | null,
})

const pagination = reactive({
  page: 1,
  page_size: 20,
})

interface DialogState {
  visible: boolean
  isEdit: boolean
  editId: string | null
  form: QuestionUpsertRequest
}

const dialog = reactive<DialogState>({
  visible: false,
  isEdit: false,
  editId: null,
  form: emptyForm(),
})

function emptyForm(): QuestionUpsertRequest {
  return {
    part: 1,
    title: '',
    content: '',
    cue_card: '',
    topic_id: '',
    tag_ids: [],
    difficulty: undefined,
    source_type: 'custom',
    source_name: '',
    status: 'draft',
  }
}

const formRef = ref<FormInstance>()

const sourceTypeOptions: { label: string; value: QuestionSourceType }[] = [
  { label: '官方', value: 'official' },
  { label: '历史真题', value: 'historical' },
  { label: '模拟题', value: 'mock' },
  { label: '自编', value: 'custom' },
]

/** Element Plus el-tag 的 type 属性联合类型。 */
type TagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

const statusOptions: { label: string; value: QuestionStatus; tag: TagType }[] = [
  { label: '草稿', value: 'draft', tag: 'warning' },
  { label: '已发布', value: 'published', tag: 'success' },
  { label: '已停用', value: 'disabled', tag: 'info' },
]

const rules: FormRules<QuestionUpsertRequest> = {
  part: [{ required: true, message: '请选择 Part', trigger: 'change' }],
  title: [
    { required: true, message: '请输入标题', trigger: 'blur' },
    { max: 200, message: '长度不超过 200', trigger: 'blur' },
  ],
  content: [
    { required: true, message: '请输入题目正文', trigger: 'blur' },
    { max: 5000, message: '长度不超过 5000', trigger: 'blur' },
  ],
  cue_card: [{ max: 2000, message: '长度不超过 2000', trigger: 'blur' }],
  topic_id: [{ required: true, message: '请选择主题', trigger: 'change' }],
  source_type: [{ required: true, message: '请选择来源类型', trigger: 'change' }],
  source_name: [
    { required: true, message: '请输入来源名称', trigger: 'blur' },
    { max: 255, message: '长度不超过 255', trigger: 'blur' },
  ],
}

async function fetchOptions(): Promise<void> {
  // 主题/标签数量少，非分页，启动时并行加载
  try {
    const [topicsRes, tagsRes] = await Promise.all([
      api.get<{ items: AdminTopicItem[] }>('/admin/topics'),
      api.get<{ items: AdminTagItem[] }>('/admin/tags'),
    ])
    topicOptions.value = topicsRes.items
    tagOptions.value = tagsRes.items
  } catch (err) {
    const message = err instanceof ApiError ? err.message : '加载主题/标签选项失败'
    ElMessage.error(message)
  }
}

async function fetchQuestions(): Promise<void> {
  loading.value = true
  try {
    const params: Record<string, string | number> = {
      page: pagination.page,
      page_size: pagination.page_size,
    }
    if (filters.keyword) params.keyword = filters.keyword.trim()
    if (filters.part) params.part = filters.part
    if (filters.topic_id) params.topic_id = filters.topic_id
    if (filters.status) params.status = filters.status
    if (filters.tag_id) params.tag_id = filters.tag_id
    if (filters.difficulty) params.difficulty = filters.difficulty

    const qs = new URLSearchParams(
      Object.entries(params).map(([k, v]) => [k, String(v)]),
    ).toString()
    const data = await api.get<AdminQuestionsData>(`/admin/questions?${qs}`)
    items.value = data.items
    total.value = data.total
  } catch (err) {
    const message = err instanceof ApiError ? err.message : '加载题目列表失败'
    ElMessage.error(message)
  } finally {
    loading.value = false
  }
}

function handleSearch(): void {
  pagination.page = 1
  void fetchQuestions()
}

function handleReset(): void {
  filters.keyword = ''
  filters.part = null
  filters.topic_id = ''
  filters.status = ''
  filters.tag_id = ''
  filters.difficulty = null
  pagination.page = 1
  void fetchQuestions()
}

function handlePageChange(page: number): void {
  pagination.page = page
  void fetchQuestions()
}

function handleSizeChange(size: number): void {
  pagination.page_size = size
  pagination.page = 1
  void fetchQuestions()
}

function openCreate(): void {
  dialog.isEdit = false
  dialog.editId = null
  dialog.form = emptyForm()
  dialog.visible = true
}

async function openEdit(row: AdminQuestionListItem): Promise<void> {
  dialog.isEdit = false // 先置 false，避免 watch 触发
  dialog.editId = row.id
  dialog.visible = true
  detailLoading.value = true
  try {
    const detail = await api.get<AdminQuestionDetail>(`/admin/questions/${row.id}`)
    dialog.isEdit = true
    dialog.form = {
      part: detail.part,
      title: detail.title,
      content: detail.content,
      cue_card: detail.cue_card ?? '',
      topic_id: detail.topic.id,
      tag_ids: detail.tags.map((t) => t.id),
      difficulty: detail.difficulty ?? undefined,
      source_type: detail.source_type,
      source_name: detail.source_name,
      status: detail.status,
    }
  } catch (err) {
    dialog.visible = false
    const message = err instanceof ApiError ? err.message : '加载题目详情失败'
    ElMessage.error(message)
  } finally {
    detailLoading.value = false
  }
}

async function handleSubmit(): Promise<void> {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  const payload: QuestionUpsertRequest = {
    part: dialog.form.part,
    title: dialog.form.title,
    content: dialog.form.content,
    cue_card: dialog.form.cue_card || undefined,
    topic_id: dialog.form.topic_id,
    tag_ids: dialog.form.tag_ids,
    difficulty: dialog.form.difficulty || undefined,
    source_type: dialog.form.source_type,
    source_name: dialog.form.source_name,
    status: dialog.form.status,
  }

  submitting.value = true
  try {
    if (dialog.isEdit && dialog.editId) {
      await api.put<AdminQuestionDetail>(
        `/admin/questions/${dialog.editId}`,
        payload,
      )
      ElMessage.success('题目已更新')
    } else {
      await api.post<AdminQuestionDetail>('/admin/questions', payload)
      ElMessage.success('题目已创建')
    }
    dialog.visible = false
    await fetchQuestions()
  } catch (err) {
    // 4003 topic 不存在 / 4004 tag 不存在
    const message = err instanceof ApiError ? err.message : '保存失败'
    ElMessage.error(message)
  } finally {
    submitting.value = false
  }
}

/**
 * 切换题目状态（admin.md §6.5，专用接口）。
 * MVP 不限制转换方向（管理员全权），仅记录 activity_log。
 */
async function handleStatusChange(
  row: AdminQuestionListItem,
  next: QuestionStatus,
): Promise<void> {
  if (row.status === next) return
  const label = statusOptions.find((s) => s.value === next)?.label ?? next
  try {
    await ElMessageBox.confirm(
      `确定将题目「${row.title}」状态切换为「${label}」吗？`,
      '切换状态',
      { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' },
    )
  } catch {
    return
  }

  submitting.value = true
  try {
    const updated = await api.put<AdminQuestionListItem>(
      `/admin/questions/${row.id}/status`,
      { status: next },
    )
    const idx = items.value.findIndex((q) => q.id === row.id)
    if (idx >= 0) items.value[idx] = updated
    ElMessage.success(`状态已切换为「${label}」`)
  } catch (err) {
    const message = err instanceof ApiError ? err.message : '状态切换失败'
    ElMessage.error(message)
  } finally {
    submitting.value = false
  }
}

function statusLabel(s: QuestionStatus): string {
  return statusOptions.find((o) => o.value === s)?.label ?? s
}

function statusTagType(s: QuestionStatus): TagType {
  return statusOptions.find((o) => o.value === s)?.tag ?? 'info'
}

function topicName(topic: TopicRef): string {
  return topic.name
}

function formatTime(value: string): string {
  return value.replace('T', ' ').slice(0, 19)
}

onMounted(async () => {
  await fetchOptions()
  await fetchQuestions()
})
</script>

<template>
  <div v-loading="loading" class="space-y-4 p-6">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-semibold">题目管理</h1>
      <el-button type="primary" @click="openCreate">新建题目</el-button>
    </div>

    <!-- 筛选区 -->
    <el-card shadow="never">
      <div class="flex flex-wrap items-center gap-3">
        <el-input
          v-model="filters.keyword"
          placeholder="搜索标题或正文"
          clearable
          class="w-56"
          @keyup.enter="handleSearch"
        />
        <el-select
          v-model="filters.part"
          placeholder="Part"
          clearable
          class="w-28"
        >
          <el-option label="Part 1" :value="1" />
          <el-option label="Part 2" :value="2" />
          <el-option label="Part 3" :value="3" />
        </el-select>
        <el-select
          v-model="filters.topic_id"
          placeholder="主题"
          clearable
          filterable
          class="w-44"
        >
          <el-option
            v-for="t in topicOptions"
            :key="t.id"
            :label="t.name"
            :value="t.id"
          />
        </el-select>
        <el-select
          v-model="filters.status"
          placeholder="状态"
          clearable
          class="w-32"
        >
          <el-option label="草稿" value="draft" />
          <el-option label="已发布" value="published" />
          <el-option label="已停用" value="disabled" />
        </el-select>
        <el-select
          v-model="filters.tag_id"
          placeholder="标签"
          clearable
          filterable
          class="w-40"
        >
          <el-option
            v-for="t in tagOptions"
            :key="t.id"
            :label="t.name"
            :value="t.id"
          />
        </el-select>
        <el-select
          v-model="filters.difficulty"
          placeholder="难度"
          clearable
          class="w-28"
        >
          <el-option v-for="d in 5" :key="d" :label="`难度 ${d}`" :value="d" />
        </el-select>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="handleReset">重置</el-button>
      </div>
    </el-card>

    <!-- 列表 -->
    <el-card shadow="never">
      <el-table :data="items" stripe>
        <el-table-column label="ID" prop="id" width="80" />
        <el-table-column label="Part" prop="part" width="80" align="center" />
        <el-table-column label="标题" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">{{ row.title }}</template>
        </el-table-column>
        <el-table-column label="主题" min-width="120">
          <template #default="{ row }">{{ topicName(row.topic) }}</template>
        </el-table-column>
        <el-table-column label="标签" min-width="160">
          <template #default="{ row }">
            <el-tag
              v-for="tag in row.tags"
              :key="tag.id"
              size="small"
              class="mr-1"
            >
              {{ tag.name }}
            </el-tag>
            <span v-if="!row.tags.length" class="text-gray-400">—</span>
          </template>
        </el-table-column>
        <el-table-column label="难度" width="80" align="center">
          <template #default="{ row }">
            {{ row.difficulty ?? '—' }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="来源" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.source_name }}
            <span class="text-xs text-gray-400">({{ row.source_type }})</span>
          </template>
        </el-table-column>
        <el-table-column label="练习数" prop="practice_count" width="90" align="center" />
        <el-table-column label="更新时间" width="170">
          <template #default="{ row }">{{ formatTime(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link type="primary" @click="openEdit(row as AdminQuestionListItem)">
              编辑
            </el-button>
            <el-dropdown trigger="click" @command="(cmd: unknown) => handleStatusChange(row as AdminQuestionListItem, cmd as QuestionStatus)">
              <el-button size="small" link type="warning">切换状态</el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="draft" :disabled="row.status === 'draft'">
                    草稿
                  </el-dropdown-item>
                  <el-dropdown-item command="published" :disabled="row.status === 'published'">
                    已发布
                  </el-dropdown-item>
                  <el-dropdown-item command="disabled" :disabled="row.status === 'disabled'">
                    已停用
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
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

    <!-- 新建/编辑弹窗 -->
    <el-dialog
      v-model="dialog.visible"
      :title="dialog.isEdit ? '编辑题目' : '新建题目'"
      width="760px"
      top="5vh"
    >
      <div v-loading="detailLoading">
        <el-form
          ref="formRef"
          :model="dialog.form"
          :rules="rules"
          label-position="top"
          :disabled="detailLoading"
        >
          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item label="Part" prop="part">
                <el-select v-model="dialog.form.part" class="w-full">
                  <el-option label="Part 1" :value="1" />
                  <el-option label="Part 2" :value="2" />
                  <el-option label="Part 3" :value="3" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="难度" prop="difficulty">
                <el-select
                  v-model="dialog.form.difficulty"
                  clearable
                  placeholder="可选"
                  class="w-full"
                >
                  <el-option v-for="d in 5" :key="d" :label="`难度 ${d}`" :value="d" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="状态" prop="status">
                <el-select v-model="dialog.form.status" class="w-full">
                  <el-option label="草稿" value="draft" />
                  <el-option label="已发布" value="published" />
                  <el-option v-if="dialog.isEdit" label="已停用" value="disabled" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item label="标题" prop="title">
            <el-input
              v-model="dialog.form.title"
              placeholder="题目标题"
              maxlength="200"
              show-word-limit
            />
          </el-form-item>

          <el-form-item label="题目正文" prop="content">
            <el-input
              v-model="dialog.form.content"
              type="textarea"
              :rows="5"
              placeholder="题目正文"
              maxlength="5000"
              show-word-limit
            />
          </el-form-item>

          <el-form-item label="Cue Card（可选）" prop="cue_card">
            <el-input
              v-model="dialog.form.cue_card"
              type="textarea"
              :rows="3"
              placeholder="Cue Card 内容"
              maxlength="2000"
              show-word-limit
            />
          </el-form-item>

          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item label="主题" prop="topic_id">
                <el-select
                  v-model="dialog.form.topic_id"
                  filterable
                  placeholder="选择主题"
                  class="w-full"
                >
                  <el-option
                    v-for="t in topicOptions"
                    :key="t.id"
                    :label="t.name"
                    :value="t.id"
                  />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="16">
              <el-form-item label="标签" prop="tag_ids">
                <el-select
                  v-model="dialog.form.tag_ids"
                  multiple
                  filterable
                  placeholder="可选，多选"
                  class="w-full"
                >
                  <el-option
                    v-for="t in tagOptions"
                    :key="t.id"
                    :label="t.name"
                    :value="t.id"
                  />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item label="来源类型" prop="source_type">
                <el-select v-model="dialog.form.source_type" class="w-full">
                  <el-option
                    v-for="opt in sourceTypeOptions"
                    :key="opt.value"
                    :label="opt.label"
                    :value="opt.value"
                  />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="16">
              <el-form-item label="来源名称" prop="source_name">
                <el-input
                  v-model="dialog.form.source_name"
                  placeholder="来源名称（ADR-011 必填）"
                  maxlength="255"
                />
              </el-form-item>
            </el-col>
          </el-row>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="submitting || detailLoading"
          :disabled="detailLoading"
          @click="handleSubmit"
        >
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

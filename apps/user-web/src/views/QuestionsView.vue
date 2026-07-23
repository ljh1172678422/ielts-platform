<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api, ApiError } from '@/api'
import type {
  PaginatedQuestions,
  QuestionListItem,
  QuestionSort,
  SpeakingPart,
} from '@ielts/types'

const router = useRouter()

// ==================== 筛选状态（questions.md §2.1） ====================
// 注：topic_id / tag_id 筛选后端已支持，但用户端暂无公开主题/标签列表接口，
// UI 先暴露 Part/难度/keyword/排序/仅收藏（均可硬编码），topic/tag 筛选待后续接入。
const filters = reactive({
  part: null as SpeakingPart | null,
  difficulty: null as number | null,
  keyword: '',
  sort: 'newest' as QuestionSort,
  is_favorited: false,
})

const partOptions: { label: string; value: SpeakingPart | null }[] = [
  { label: '全部 Part', value: null },
  { label: 'Part 1', value: 1 },
  { label: 'Part 2', value: 2 },
  { label: 'Part 3', value: 3 },
]
const difficultyOptions: { label: string; value: number | null }[] = [
  { label: '全部难度', value: null },
  { label: '1', value: 1 },
  { label: '2', value: 2 },
  { label: '3', value: 3 },
  { label: '4', value: 4 },
  { label: '5', value: 5 },
]
const sortOptions: { label: string; value: QuestionSort }[] = [
  { label: '最新', value: 'newest' },
  { label: '最热', value: 'popular' },
]

// ==================== 列表数据 ====================
const loading = ref(false)
const items = ref<QuestionListItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

function buildQueryString(): string {
  const params: Record<string, string | number | boolean> = {
    page: page.value,
    page_size: pageSize.value,
    sort: filters.sort,
  }
  if (filters.part !== null) params.part = filters.part
  if (filters.difficulty !== null) params.difficulty = filters.difficulty
  const kw = filters.keyword.trim()
  if (kw) params.keyword = kw
  if (filters.is_favorited) params.is_favorited = true
  return new URLSearchParams(
    Object.entries(params).map(([k, v]) => [k, String(v)]),
  ).toString()
}

async function fetchList(): Promise<void> {
  loading.value = true
  try {
    const data = await api.get<PaginatedQuestions>(`/questions?${buildQueryString()}`)
    items.value = data.items
    total.value = data.total
  } catch (err) {
    items.value = []
    total.value = 0
    ElMessage.error(err instanceof ApiError ? err.message : '加载题库失败')
  } finally {
    loading.value = false
  }
}

function handleSearch(): void {
  page.value = 1
  void fetchList()
}

function handleReset(): void {
  filters.part = null
  filters.difficulty = null
  filters.keyword = ''
  filters.sort = 'newest'
  filters.is_favorited = false
  page.value = 1
  void fetchList()
}

function handlePageChange(p: number): void {
  page.value = p
  void fetchList()
}

// ==================== 收藏切换（questions.md §4/§5，乐观更新） ====================
const favoritingIds = ref<Set<string>>(new Set())

async function toggleFavorite(item: QuestionListItem): Promise<void> {
  if (favoritingIds.value.has(item.id)) return
  favoritingIds.value.add(item.id)
  const wasFavorited = item.is_favorited
  // 乐观更新
  item.is_favorited = !wasFavorited
  try {
    if (wasFavorited) {
      await api.delete<{ question_id: string; is_favorited: boolean }>(
        `/questions/${item.id}/favorite`,
      )
    } else {
      await api.post<{ question_id: string; is_favorited: boolean }>(
        `/questions/${item.id}/favorite`,
      )
    }
  } catch (err) {
    // 回滚
    item.is_favorited = wasFavorited
    ElMessage.error(err instanceof ApiError ? err.message : '操作失败')
  } finally {
    favoritingIds.value.delete(item.id)
  }
}

// ==================== 跳转 ====================
function goDetail(id: string): void {
  router.push({ name: 'question-detail', params: { id } })
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('zh-CN')
}

onMounted(fetchList)
</script>

<template>
  <main class="min-h-screen bg-gray-50 py-8">
    <div class="mx-auto max-w-5xl px-4">
      <header class="mb-6 flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-bold text-gray-900">题库</h1>
          <p class="mt-1 text-sm text-gray-500">浏览雅思口语题目，收藏喜欢的题目</p>
        </div>
        <el-button @click="router.push({ name: 'home' })">返回首页</el-button>
      </header>

      <!-- 筛选区 -->
      <section class="mb-4 rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100">
        <div class="flex flex-wrap items-end gap-3">
          <div class="flex flex-col">
            <label class="mb-1 text-xs text-gray-500">Part</label>
            <el-select v-model="filters.part" placeholder="全部" class="w-32">
              <el-option
                v-for="o in partOptions"
                :key="String(o.value)"
                :label="o.label"
                :value="o.value"
              />
            </el-select>
          </div>
          <div class="flex flex-col">
            <label class="mb-1 text-xs text-gray-500">难度</label>
            <el-select v-model="filters.difficulty" placeholder="全部" class="w-28">
              <el-option
                v-for="o in difficultyOptions"
                :key="String(o.value)"
                :label="o.label"
                :value="o.value"
              />
            </el-select>
          </div>
          <div class="flex flex-col">
            <label class="mb-1 text-xs text-gray-500">关键词</label>
            <el-input
              v-model="filters.keyword"
              placeholder="搜索标题或正文"
              clearable
              class="w-56"
              @keyup.enter="handleSearch"
            />
          </div>
          <div class="flex flex-col">
            <label class="mb-1 text-xs text-gray-500">排序</label>
            <el-select v-model="filters.sort" class="w-28">
              <el-option
                v-for="o in sortOptions"
                :key="o.value"
                :label="o.label"
                :value="o.value"
              />
            </el-select>
          </div>
          <div class="flex h-10 items-center">
            <el-checkbox v-model="filters.is_favorited">仅看收藏</el-checkbox>
          </div>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </div>
      </section>

      <!-- 列表 -->
      <section v-loading="loading" class="space-y-3">
        <el-empty v-if="!loading && items.length === 0" description="暂无题目" />

        <article
          v-for="item in items"
          :key="item.id"
          class="cursor-pointer rounded-2xl bg-white p-4 shadow-sm ring-1 ring-gray-100 transition hover:ring-indigo-200"
          @click="goDetail(item.id)"
        >
          <div class="flex items-start justify-between gap-4">
            <div class="min-w-0 flex-1">
              <div class="mb-1 flex flex-wrap items-center gap-2">
                <el-tag size="small" type="primary">Part {{ item.part }}</el-tag>
                <el-tag v-if="item.difficulty" size="small" type="warning">
                  难度 {{ item.difficulty }}
                </el-tag>
                <el-tag size="small" type="info">{{ item.topic.name }}</el-tag>
                <span class="text-xs text-gray-400">{{ formatDate(item.created_at) }}</span>
              </div>
              <h3 class="truncate text-base font-medium text-gray-900">{{ item.title }}</h3>
              <p class="mt-1 text-xs text-gray-400">
                已练习 {{ item.practice_count }} 次
              </p>
            </div>
            <!-- 收藏星标（乐观更新） -->
            <button
              type="button"
              class="flex-shrink-0 rounded-full p-1.5 transition hover:bg-gray-100"
              :disabled="favoritingIds.has(item.id)"
              :aria-label="item.is_favorited ? '取消收藏' : '收藏'"
              @click.stop="toggleFavorite(item)"
            >
              <svg
                v-if="item.is_favorited"
                class="h-5 w-5 text-amber-400"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
              </svg>
              <svg
                v-else
                class="h-5 w-5 text-gray-300"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
              </svg>
            </button>
          </div>
        </article>
      </section>

      <!-- 分页 -->
      <footer v-if="total > 0" class="mt-6 flex justify-center">
        <el-pagination
          background
          layout="prev, pager, next, total"
          :current-page="page"
          :page-size="pageSize"
          :total="total"
          @current-change="handlePageChange"
        />
      </footer>
    </div>
  </main>
</template>

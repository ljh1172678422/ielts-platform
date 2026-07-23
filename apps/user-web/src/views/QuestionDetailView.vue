<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api, ApiError } from '@/api'
import type { FavoriteResponse, QuestionDetail } from '@ielts/types'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const detail = ref<QuestionDetail | null>(null)
const favoriting = ref(false)

const questionId = computed(() => String(route.params.id))

async function fetchDetail(): Promise<void> {
  loading.value = true
  try {
    detail.value = await api.get<QuestionDetail>(`/questions/${questionId.value}`)
  } catch (err) {
    detail.value = null
    // 4001 不存在 / 4002 已下架 / 1001 id 非法
    ElMessage.error(err instanceof ApiError ? err.message : '加载题目失败')
  } finally {
    loading.value = false
  }
}

async function toggleFavorite(): Promise<void> {
  if (!detail.value || favoriting.value) return
  favoriting.value = true
  const was = detail.value.is_favorited
  detail.value.is_favorited = !was
  try {
    if (was) {
      await api.delete<FavoriteResponse>(`/questions/${questionId.value}/favorite`)
    } else {
      await api.post<FavoriteResponse>(`/questions/${questionId.value}/favorite`)
    }
  } catch (err) {
    detail.value.is_favorited = was
    ElMessage.error(err instanceof ApiError ? err.message : '操作失败')
  } finally {
    favoriting.value = false
  }
}

/** 开始练习：练习系统属 Phase 7，此处预留入口（questions.md §8 衔接 practice.md）。 */
function startPractice(): void {
  ElMessage.info('练习功能将在下一阶段（Phase 7）上线')
}

function goBack(): void {
  router.push({ name: 'questions' })
}

/** Cue Card 按 \n / - 渲染为列表（questions.md §3.2 前端按 \n / - 渲染）。 */
const cueCardLines = computed<string[]>(() => {
  const raw = detail.value?.cue_card
  if (!raw) return []
  return raw.split('\n').map((l) => l.trim()).filter(Boolean)
})

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('zh-CN')
}

onMounted(fetchDetail)
</script>

<template>
  <main class="min-h-screen bg-gray-50 py-8">
    <div class="mx-auto max-w-3xl px-4">
      <header class="mb-6 flex items-center justify-between">
        <el-button link @click="goBack">← 返回题库</el-button>
      </header>

      <div v-loading="loading">
        <template v-if="detail">
          <article class="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-gray-100">
            <!-- 标题区 -->
            <div class="mb-4 flex flex-wrap items-center gap-2">
              <el-tag type="primary">Part {{ detail.part }}</el-tag>
              <el-tag v-if="detail.difficulty" type="warning">难度 {{ detail.difficulty }}</el-tag>
              <el-tag type="info">{{ detail.topic.name }}</el-tag>
              <el-tag
                v-for="t in detail.tags"
                :key="t.id"
                size="small"
                type="info"
                effect="plain"
              >
                {{ t.name }}
              </el-tag>
              <span class="ml-auto text-xs text-gray-400">
                {{ formatDate(detail.created_at) }} · 已练习 {{ detail.practice_count }} 次
              </span>
            </div>

            <h1 class="text-2xl font-bold text-gray-900">{{ detail.title }}</h1>

            <!-- 题目正文 -->
            <section class="mt-4">
              <h2 class="mb-2 text-sm font-semibold text-gray-700">题目</h2>
              <p class="whitespace-pre-wrap leading-relaxed text-gray-800">{{ detail.content }}</p>
            </section>

            <!-- Cue Card（按 \n / - 渲染，questions.md §3.2） -->
            <section v-if="cueCardLines.length" class="mt-6 rounded-xl bg-amber-50 p-4">
              <h2 class="mb-2 text-sm font-semibold text-amber-800">Cue Card</h2>
              <ul class="space-y-1">
                <li
                  v-for="(line, i) in cueCardLines"
                  :key="i"
                  class="flex gap-2 text-sm text-amber-900"
                >
                  <span class="text-amber-500">{{ line.startsWith('-') ? '' : '•' }}</span>
                  <span>{{ line.replace(/^-\s*/, '') }}</span>
                </li>
              </ul>
            </section>

            <!-- 来源（版权透明，questions.md §6.3） -->
            <section class="mt-6 text-xs text-gray-400">
              来源：{{ detail.source_name }}（{{ detail.source_type }}）
            </section>

            <!-- 操作区 -->
            <footer class="mt-6 flex items-center gap-3 border-t border-gray-100 pt-4">
              <el-button
                :type="detail.is_favorited ? 'warning' : 'default'"
                :loading="favoriting"
                @click="toggleFavorite"
              >
                {{ detail.is_favorited ? '★ 已收藏' : '☆ 收藏' }}
              </el-button>
              <el-button type="primary" @click="startPractice">开始练习</el-button>
            </footer>
          </article>
        </template>

        <el-empty v-else-if="!loading" description="题目不存在或已下架" />
      </div>
    </div>
  </main>
</template>

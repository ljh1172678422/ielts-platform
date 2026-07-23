<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api, ApiError } from '@/api'
import type { DashboardData } from '@/types/admin'

/**
 * Dashboard 页（admin.md §2）：全局统计概览。
 * 调 GET /admin/dashboard，按 用户/题目/练习/主题/标签 分组展示统计卡片。
 */
const loading = ref(false)
const data = ref<DashboardData | null>(null)

async function fetchDashboard(): Promise<void> {
  loading.value = true
  try {
    data.value = await api.get<DashboardData>('/admin/dashboard')
  } catch (err) {
    const message = err instanceof ApiError ? err.message : '加载统计数据失败'
    ElMessage.error(message)
  } finally {
    loading.value = false
  }
}

onMounted(fetchDashboard)

interface StatCard {
  label: string
  value: number
}

const userCards = (): StatCard[] => [
  { label: '用户总数', value: data.value?.users.total ?? 0 },
  { label: '今日活跃', value: data.value?.users.active_today ?? 0 },
  { label: '本周新增', value: data.value?.users.new_this_week ?? 0 },
]

const questionCards = (): StatCard[] => [
  { label: '题目总数', value: data.value?.questions.total ?? 0 },
  { label: '已发布', value: data.value?.questions.published ?? 0 },
  { label: '草稿', value: data.value?.questions.draft ?? 0 },
  { label: '已停用', value: data.value?.questions.disabled ?? 0 },
]

const practiceCards = (): StatCard[] => [
  { label: '练习会话', value: data.value?.practice.total_sessions ?? 0 },
  { label: '答题次数', value: data.value?.practice.total_attempts ?? 0 },
  { label: '录音数', value: data.value?.practice.total_recordings ?? 0 },
  { label: '总时长(秒)', value: data.value?.practice.total_duration_seconds ?? 0 },
]
</script>

<template>
  <div v-loading="loading" class="space-y-6 p-6">
    <h1 class="text-xl font-semibold">Dashboard</h1>

    <template v-if="data">
      <!-- 用户统计 -->
      <section>
        <h2 class="mb-3 text-sm font-medium text-gray-500">用户</h2>
        <el-row :gutter="16">
          <el-col v-for="card in userCards()" :key="card.label" :span="8">
            <el-card shadow="hover">
              <div class="text-sm text-gray-500">{{ card.label }}</div>
              <div class="mt-1 text-2xl font-semibold">{{ card.value }}</div>
            </el-card>
          </el-col>
        </el-row>
      </section>

      <!-- 题目统计 -->
      <section>
        <h2 class="mb-3 text-sm font-medium text-gray-500">题目</h2>
        <el-row :gutter="16">
          <el-col v-for="card in questionCards()" :key="card.label" :span="6">
            <el-card shadow="hover">
              <div class="text-sm text-gray-500">{{ card.label }}</div>
              <div class="mt-1 text-2xl font-semibold">{{ card.value }}</div>
            </el-card>
          </el-col>
        </el-row>
      </section>

      <!-- 练习统计 -->
      <section>
        <h2 class="mb-3 text-sm font-medium text-gray-500">练习</h2>
        <el-row :gutter="16">
          <el-col v-for="card in practiceCards()" :key="card.label" :span="6">
            <el-card shadow="hover">
              <div class="text-sm text-gray-500">{{ card.label }}</div>
              <div class="mt-1 text-2xl font-semibold">{{ card.value }}</div>
            </el-card>
          </el-col>
        </el-row>
      </section>

      <!-- 主题 / 标签 -->
      <section>
        <h2 class="mb-3 text-sm font-medium text-gray-500">分类</h2>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-card shadow="hover">
              <div class="text-sm text-gray-500">主题总数</div>
              <div class="mt-1 text-2xl font-semibold">{{ data.topics.total }}</div>
            </el-card>
          </el-col>
          <el-col :span="8">
            <el-card shadow="hover">
              <div class="text-sm text-gray-500">标签总数</div>
              <div class="mt-1 text-2xl font-semibold">{{ data.tags.total }}</div>
            </el-card>
          </el-col>
        </el-row>
      </section>
    </template>
  </div>
</template>

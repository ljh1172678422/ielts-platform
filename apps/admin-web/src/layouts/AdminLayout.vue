<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

/**
 * 管理后台主布局（admin.md §1.1）。
 * - 侧边栏：Dashboard / 用户 / 主题 / 标签 / 题目 导航（router 模式，高亮当前路由）
 * - 顶栏：当前管理员邮箱 + 退出按钮
 * - 主内容区：router-view 渲染各管理页
 */
const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const activeMenu = computed(() => route.path)

const menuItems = [
  { index: '/', label: 'Dashboard' },
  { index: '/users', label: '用户管理' },
  { index: '/topics', label: '主题管理' },
  { index: '/tags', label: '标签管理' },
  { index: '/questions', label: '题目管理' },
]

async function handleLogout(): Promise<void> {
  try {
    await ElMessageBox.confirm('确定退出登录？', '提示', {
      type: 'warning',
      confirmButtonText: '退出',
      cancelButtonText: '取消',
    })
  } catch {
    return // 用户取消
  }

  await authStore.logout()
  ElMessage.success('已退出登录')
  router.replace({ name: 'login' })
}
</script>

<template>
  <el-container class="layout">
    <el-aside width="220px" class="layout__aside">
      <div class="layout__logo">IELTS Admin</div>
      <el-menu
        :default-active="activeMenu"
        router
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409eff"
      >
        <el-menu-item v-for="item in menuItems" :key="item.index" :index="item.index">
          <span>{{ item.label }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="layout__header">
        <span>管理后台</span>
        <div class="layout__header-right">
          <span v-if="authStore.user" class="layout__user">
            {{ authStore.user.email }}
          </span>
          <el-button text type="primary" @click="handleLogout">退出</el-button>
        </div>
      </el-header>
      <el-main class="layout__main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout {
  height: 100%;
}

.layout__aside {
  background-color: #304156;
}

.layout__logo {
  height: 60px;
  line-height: 60px;
  text-align: center;
  color: #fff;
  font-size: 18px;
  font-weight: 600;
}

.layout__header {
  background-color: #fff;
  border-bottom: 1px solid #e6e6e6;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
}

.layout__header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.layout__user {
  font-weight: 400;
  color: #606266;
  font-size: 13px;
}

.layout__main {
  background-color: #f5f7fa;
}
</style>

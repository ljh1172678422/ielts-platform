import { defineStore } from 'pinia'
import type { UserRole } from '@ielts/types'

/**
 * Auth Store（占位）
 * 仅保留 token 状态与认证判定，登录 / 登出 / 拉取用户信息由后续 auth 模块实现。
 */
export const useAuthStore = defineStore('auth', {
  state: () => ({
    /** access token（占位：登录后由 auth 模块写入） */
    token: '',
    /** 当前用户角色（占位：登录后写入，ADR-009 user/admin） */
    role: null as UserRole | null,
  }),
  getters: {
    isAuthenticated: (state): boolean => Boolean(state.token),
    isAdmin: (state): boolean => state.role === 'admin',
  },
  actions: {
    // TODO: login / logout / fetchProfile 由后续 auth 模块实现
  },
})

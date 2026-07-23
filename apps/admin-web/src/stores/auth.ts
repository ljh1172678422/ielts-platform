import { defineStore } from 'pinia'

// auth store 占位：管理后台登录态与 token
export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: '' as string,
  }),
  getters: {
    isAuthenticated: (state) => !!state.token,
  },
  actions: {
    setToken(token: string) {
      this.token = token
    },
    clearToken() {
      this.token = ''
    },
  },
})

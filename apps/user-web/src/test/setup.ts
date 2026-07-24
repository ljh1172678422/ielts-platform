/**
 * Vitest 全局 setup（每个测试文件执行前运行）。
 *
 * - 清理 localStorage / sessionStorage，避免测试间状态泄漏
 * - 清理所有 mock
 * - 提供统一的 afterEach 钩子
 */
import { afterEach, beforeEach, vi } from 'vitest'

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
})

afterEach(() => {
  vi.restoreAllMocks()
})

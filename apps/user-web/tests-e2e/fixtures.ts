/**
 * E2E 测试共享 fixtures（Phase 11.6 / 11.7）。
 *
 * - 测试账号：E2E_TEST_EMAIL / E2E_TEST_PASSWORD（默认 e2e@test.local / Test1234!）
 *   需在本地 docker compose up 后预先注册或用 seed 脚本创建。
 * - 直接调 API 创建会话/答题，绕开 UI 操作，加速测试前置态。
 * - 通过 UI 操作验证核心闭环（录音/续练），避免 UI 走完整登录链路。
 */
import { test as base, expect, type APIRequestContext, type Page } from '@playwright/test'
import type {
  Attempt,
  AuthData,
  PracticeSession,
  SessionQuestion,
} from '@ielts/types'

/** 测试账号配置（本地 docker 起来后需先注册）。 */
export const TEST_USER = {
  email: process.env.E2E_TEST_EMAIL ?? 'e2e@test.local',
  password: process.env.E2E_TEST_PASSWORD ?? 'Test1234!',
}

/** API 基础路径（对齐 common.md §1.1）。 */
const API_BASE = '/api/v1'

/**
 * 通过 UI 登录（auth.md §3）。
 * 直接走 /auth/login API 更快，但 UI 登录能顺带验证登录跳转链路（user-flow.md §5）。
 */
export async function loginViaUI(page: Page, email = TEST_USER.email): Promise<void> {
  await page.goto('/login')
  await page.getByLabel('邮箱').fill(email)
  await page.getByLabel('密码').fill(TEST_USER.password)
  await page.getByRole('button', { name: '登录' }).click()
  // 登录成功跳首页
  await page.waitForURL('**/')
}

/**
 * 通过 API 登录，返回 access_token（用于直接调 API 加速测试前置态）。
 * 不走 UI，省去渲染开销。
 */
export async function loginViaAPI(
  request: APIRequestContext,
  email = TEST_USER.email,
): Promise<AuthData> {
  const res = await request.post(`${API_BASE}/auth/login`, {
    data: { email, password: TEST_USER.password },
  })
  expect(res.ok(), `登录失败: ${res.status()}`).toBe(true)
  const body = await res.json()
  expect(body.code).toBe(0)
  return body.data as AuthData
}

/** 带鉴权的 API 请求：注入 Bearer token。 */
export async function authedRequest(
  request: APIRequestContext,
  token: string,
  method: 'GET' | 'POST' | 'PATCH' | 'DELETE',
  path: string,
  data?: unknown,
): Promise<{ code: number; data: unknown; message: string }> {
  const res = await request.fetch(`${API_BASE}${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}` },
    data: data ? (data as Record<string, unknown>) : undefined,
    multipart: undefined,
  })
  const body = await res.json()
  return { code: body.code, data: body.data, message: body.message }
}

/** 通过 API 创建练习会话（practice.md §2）。 */
export async function createSessionViaAPI(
  request: APIRequestContext,
  token: string,
  body: { mode: string; question_count: number; topic_id?: string; part?: number },
): Promise<PracticeSession> {
  const res = await authedRequest(request, token, 'POST', '/practice/sessions', body)
  expect(res.code, `创建会话失败: ${res.message}`).toBe(0)
  return res.data as PracticeSession
}

/** 通过 API 获取会话详情（practice.md §3，续练恢复用）。 */
export async function getSessionViaAPI(
  request: APIRequestContext,
  token: string,
  sessionId: string,
): Promise<PracticeSession> {
  const res = await authedRequest(request, token, 'GET', `/practice/sessions/${sessionId}`)
  expect(res.code, `获取会话失败: ${res.message}`).toBe(0)
  return res.data as PracticeSession
}

/** 通过 API 创建答题尝试（practice.md §4）。 */
export async function createAttemptViaAPI(
  request: APIRequestContext,
  token: string,
  sessionQuestionId: string,
): Promise<Attempt> {
  const res = await authedRequest(request, token, 'POST', '/practice/attempts', {
    session_question_id: sessionQuestionId,
  })
  expect(res.code, `创建 attempt 失败: ${res.message}`).toBe(0)
  return res.data as Attempt
}

/** 通过 API 更新答题状态（practice.md §5，跳过场景）。 */
export async function patchAttemptViaAPI(
  request: APIRequestContext,
  token: string,
  attemptId: string,
  status: 'recording' | 'skipped' | 'failed',
): Promise<Attempt> {
  const res = await authedRequest(request, token, 'PATCH', `/practice/attempts/${attemptId}`, {
    status,
  })
  expect(res.code, `更新 attempt 失败: ${res.message}`).toBe(0)
  return res.data as Attempt
}

/**
 * 注入 token 到 localStorage（绕过 UI 登录，直接进入受保护页）。
 * 用于只测练习/续练流程，不重复登录链路。
 */
export async function injectToken(page: Page, token: string, email = TEST_USER.email): Promise<void> {
  await page.goto('/')
  await page.evaluate(
    ({ token, email }) => {
      // 与 api/index.ts TOKEN_STORAGE_KEY 对齐
      localStorage.setItem('access_token', token)
      // 与 auth store state 对齐（role/user 写入 pinia 持久化）
      // pinia 默认非持久化，刷新后由 router guard 触发 fetchProfile 补全
      void email
    },
    { token, email },
  )
}

/** 找到第一个未完成的 session_question（无 submitted/skipped attempt）。 */
export function findFirstUnfinished(questions: SessionQuestion[]): SessionQuestion | undefined {
  return questions.find((sq) => {
    if (sq.attempts.length === 0) return true
    return !sq.attempts.some((a) => a.status === 'submitted' || a.status === 'skipped')
  })
}

/** 统计已达成终态（submitted/skipped）的题目数。 */
export function countCompleted(questions: SessionQuestion[]): number {
  return questions.filter((sq) =>
    sq.attempts.some((a) => a.status === 'submitted' || a.status === 'skipped'),
  ).length
}

/** 扩展 test fixture：注入已登录的 page + token + API helper。 */
export const test = base.extend<{ authedPage: Page; token: string }>({
  token: async ({ request }, use) => {
    const auth = await loginViaAPI(request)
    await use(auth.access_token)
  },
  authedPage: async ({ page, token }, use) => {
    await injectToken(page, token)
    await use(page)
  },
})

export { expect }

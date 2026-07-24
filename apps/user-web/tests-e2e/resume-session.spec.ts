/**
 * Phase 11.7 — 续练场景 Playwright E2E（关闭重开恢复）。
 *
 * 对齐 development-plan.md §13 任务 11.7 + user-flow.md §4 续练流程。
 *
 * 续练闭环：
 *   登录 → 创建会话 → 答第 1 题(录音上传 submitted) + 第 2 题(创建 attempt pending)
 *   → 关闭页面（context.close）
 *   → 新开 context 重新登录 → 首页 recent_practice.has_unfinished=true
 *   → 点"继续练习" → 练习页恢复 → 已答题显示 submitted、未答题显示 pending
 *   → 继续完成剩余 → 完成会话(completed)
 *
 * 续练依赖 session.status='in_progress' 与 attempts 状态持久化（practice.md §3.5）。
 *
 * 前置：本地 docker compose up postgres backend + pnpm dev + 已注册测试账号。
 */
import { test as base, expect, type APIRequestContext, type Page } from '@playwright/test'
import {
  TEST_USER,
  loginViaAPI,
  loginViaUI,
  injectToken,
  createSessionViaAPI,
  createAttemptViaAPI,
  patchAttemptViaAPI,
  getSessionViaAPI,
  authedRequest,
} from './fixtures'
import type { PracticeSession } from '@ielts/types'

/**
 * 续练场景需要跨 context（模拟关闭重开），不能复用 fixtures.ts 的 authedPage。
 * 每个测试自己管理两个 context 的登录态。
 */
base.describe('Phase 11.7 续练场景（关闭重开恢复）', () => {
  base('关闭重开 → 首页续练入口 → 恢复会话 → 完成', async ({ browser, request }) => {
    // === 阶段 1：首次登录，创建会话并答部分题 ===
    const auth1 = await loginViaAPI(request)
    const token1 = auth1.access_token

    // 创建 3 题会话
    const session = await createSessionViaAPI(request, token1, {
      mode: 'random',
      question_count: 3,
    })
    expect(session.status).toBe('created')

    // 第 1 题：创建 attempt + 录音上传（通过 UI 完成录音闭环）
    const sq1 = session.questions[0]
    const attempt1 = await createAttemptViaAPI(request, token1, sq1.id)
    // attempt 创建后 session 自动转 in_progress
    const sessionInProgress = await getSessionViaAPI(request, token1, session.id)
    expect(sessionInProgress.status).toBe('in_progress')

    const context1 = await browser.newContext({
      permissions: ['microphone'],
      baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173',
    })
    const page1 = await context1.newPage()
    await injectToken(page1, token1)
    await page1.goto(`/practice/${session.id}`)
    await expect(page1.getByText('进行中').first()).toBeVisible({ timeout: 10_000 })

    // 录音上传第 1 题
    const article1 = page1.locator('article').first()
    await expect(article1.getByRole('button', { name: '开始录音' })).toBeVisible()
    await article1.getByRole('button', { name: '开始录音' }).click()
    await expect(article1.getByRole('button', { name: '停止并上传' })).toBeVisible()
    await page1.waitForTimeout(2000)
    await article1.getByRole('button', { name: '停止并上传' }).click()
    await expect(article1.getByText('录音上传成功')).toBeVisible({ timeout: 15_000 })
    await expect(article1.getByText('已完成').first()).toBeVisible()

    // 第 2 题：创建 attempt 留 pending（模拟中断时 attempt 已建但未录音）
    const sq2 = session.questions[1]
    await createAttemptViaAPI(request, token1, sq2.id)
    // 第 2 题 attempt 状态 = pending

    // 验证进度：1 题 submitted + 1 题 pending + 1 题 无 attempt
    const midSession = await getSessionViaAPI(request, token1, session.id)
    expect(midSession.questions[0].attempts.at(-1)?.status).toBe('submitted')
    expect(midSession.questions[1].attempts.at(-1)?.status).toBe('pending')
    expect(midSession.questions[2].attempts).toHaveLength(0)

    // === 阶段 2：关闭页面（模拟用户离开） ===
    await context1.close()

    // === 阶段 3：重新打开，首页应显示"继续练习"入口 ===
    const context2 = await browser.newContext()
    const page2 = await context2.newPage()
    // 重新登录（无状态退出 ADR-027，token 仍有效，但模拟新会话重新登录）
    await loginViaUI(page2)

    // 首页 recent_practice.has_unfinished 应为 true（home.md §2.3）
    const homeRes = await authedRequest(request, token1, 'GET', '/home/overview')
    expect(homeRes.code).toBe(0)
    const homeData = homeRes.data as { recent_practice: { has_unfinished: boolean } }
    expect(homeData.recent_practice.has_unfinished).toBe(true)

    // 首页应显示"继续未完成的练习"卡片
    await page2.goto('/')
    await expect(page2.getByText('继续未完成的练习')).toBeVisible({ timeout: 10_000 })
    await expect(page2.getByText(/已完成\s*1\s*\/\s*3/)).toBeVisible()

    // === 阶段 4：点"继续练习"跳到练习页，验证会话恢复 ===
    await page2.getByRole('button', { name: '继续练习' }).click()
    await page2.waitForURL(`**/practice/${session.id}`)
    await expect(page2.getByText('进行中').first()).toBeVisible()

    // 第 1 题：应显示 submitted（录音回放区可见）
    const restoredArt1 = page2.locator('article').first()
    await expect(restoredArt1.getByText('已完成').first()).toBeVisible()
    await expect(restoredArt1.getByText('录音回放')).toBeVisible()

    // 第 2 题：attempt pending，应显示"开始录音"按钮（续练恢复 UI）
    const restoredArt2 = page2.locator('article').nth(1)
    await expect(restoredArt2.getByRole('button', { name: '开始录音' })).toBeVisible({
      timeout: 10_000,
    })

    // 第 3 题：无 attempt，应显示"开始答题"
    const restoredArt3 = page2.locator('article').nth(2)
    await expect(restoredArt3.getByRole('button', { name: '开始答题' })).toBeVisible()

    // 进度 1/3（只有第 1 题 submitted）
    await expect(page2.getByText('进度 1/3')).toBeVisible()

    // === 阶段 5：继续完成剩余题目 ===
    // 第 2 题：录音上传
    await restoredArt2.getByRole('button', { name: '开始录音' }).click()
    await expect(restoredArt2.getByRole('button', { name: '停止并上传' })).toBeVisible()
    await page2.waitForTimeout(2000)
    await restoredArt2.getByRole('button', { name: '停止并上传' }).click()
    await expect(restoredArt2.getByText('录音上传成功')).toBeVisible({ timeout: 15_000 })

    // 第 3 题：通过 API 跳过（加速）
    const sq3 = midSession.questions[2]
    const attempt3 = await createAttemptViaAPI(request, token1, sq3.id)
    await patchAttemptViaAPI(request, token1, attempt3.id, 'skipped')

    // 刷新，进度 3/3，完成会话按钮可点
    await page2.reload()
    await expect(page2.getByText('进度 3/3')).toBeVisible({ timeout: 10_000 })
    await expect(page2.getByRole('button', { name: '完成会话' })).toBeEnabled()

    // 完成会话
    await page2.getByRole('button', { name: '完成会话' }).click()
    await page2.getByRole('button', { name: '确认完成' }).click()
    await expect(page2.getByText('会话已完成')).toBeVisible({ timeout: 10_000 })

    // === 阶段 6：验证最终状态 ===
    const finalSession = await getSessionViaAPI(request, token1, session.id)
    expect(finalSession.status).toBe('completed')
    expect(finalSession.questions[0].attempts.at(-1)?.status).toBe('submitted')
    expect(finalSession.questions[1].attempts.at(-1)?.status).toBe('submitted')
    expect(finalSession.questions[2].attempts.at(-1)?.status).toBe('skipped')

    // 首页 recent_practice.has_unfinished 应变为 false
    const finalHome = await authedRequest(request, token1, 'GET', '/home/overview')
    const finalHomeData = finalHome.data as { recent_practice: { has_unfinished: boolean } }
    expect(finalHomeData.recent_practice.has_unfinished).toBe(false)

    await context2.close()
  })

  base('已完成会话不可继续操作（仅可查看）', async ({ browser, request }) => {
    const auth = await loginViaAPI(request)
    const token = auth.access_token

    // 创建 1 题会话，录音上传后完成
    const session = await createSessionViaAPI(request, token, {
      mode: 'random',
      question_count: 1,
    })
    const sq = session.questions[0]
    const attempt = await createAttemptViaAPI(request, token, sq.id)

    const context = await browser.newContext({
      permissions: ['microphone'],
    })
    const page = await context.newPage()
    await injectToken(page, token)
    await page.goto(`/practice/${session.id}`)

    const article = page.locator('article').first()
    await expect(article.getByRole('button', { name: '开始录音' })).toBeVisible({
      timeout: 10_000,
    })
    await article.getByRole('button', { name: '开始录音' }).click()
    await expect(article.getByRole('button', { name: '停止并上传' })).toBeVisible()
    await page.waitForTimeout(2000)
    await article.getByRole('button', { name: '停止并上传' }).click()
    await expect(article.getByText('录音上传成功')).toBeVisible({ timeout: 15_000 })

    // 完成会话
    await expect(page.getByRole('button', { name: '完成会话' })).toBeEnabled()
    await page.getByRole('button', { name: '完成会话' }).click()
    await page.getByRole('button', { name: '确认完成' }).click()
    await expect(page.getByText('会话已完成')).toBeVisible({ timeout: 10_000 })

    // 完成后：状态 completed，操作区隐藏（isOperable=false），无"开始答题/录音"按钮
    await expect(page.getByText('已完成').first()).toBeVisible()
    await expect(page.getByRole('button', { name: '开始答题' })).toHaveCount(0)
    await expect(page.getByRole('button', { name: '开始录音' })).toHaveCount(0)
    await expect(page.getByRole('button', { name: '完成会话' })).toHaveCount(0)
    // 录音回放区仍可见（仅查看）
    await expect(article.getByText('录音回放')).toBeVisible()

    await context.close()
  })
})

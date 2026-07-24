/**
 * Phase 11.6 — 前端练习录音 Playwright E2E（完整闭环）。
 *
 * 对齐 development-plan.md §13 任务 11.6 + user-flow.md §3 练习录音核心流程。
 *
 * 完整闭环：
 *   登录 → 题库 → 题目详情 → 开始练习(创建会话) → 练习页
 *   → 开始答题(attempt pending) → 开始录音(recording) → 停止并上传(submitted)
 *   → 录音回放区出现 → 剩余题目跳过 → 完成会话(completed)
 *   → 学习数据页统计更新
 *
 * 录音：Chromium --use-fake-device-for-media-stream 注入伪音频流，
 *       MediaRecorder 录到非空 Blob，后端 mutagen 解析 duration（ADR-020）。
 *
 * 前置：本地 docker compose up postgres backend + pnpm dev + 已注册测试账号。
 */
import { test, expect } from './fixtures'
import type { PracticeSession } from '@ielts/types'

test.describe('Phase 11.6 练习录音完整闭环', () => {
  test('登录 → 创建会话 → 录音上传 → 跳过 → 完成会话', async ({ authedPage: page, request, token }) => {
    // 1. 访问题库，确认有可用题目（前置：seed 数据已 published 题目）
    await page.goto('/questions')
    await expect(page.getByRole('heading', { name: /题库/ }).or(page.locator('article').first())).toBeVisible({ timeout: 15_000 })

    // 题库列表至少有一道题
    const questionCards = page.locator('article')
    await expect(questionCards.first()).toBeVisible()
    const questionCount = await questionCards.count()
    expect(questionCount).toBeGreaterThan(0)

    // 2. 直接调 API 创建会话（mode=random，3 题，加速测试；UI 创建走详情页入口）
    const session = await createSessionViaAPI(request, token, {
      mode: 'random',
      question_count: 3,
    })
    expect(session.status).toBe('created')
    expect(session.questions).toHaveLength(3)
    // 新建会话所有题目 attempts 为空
    for (const sq of session.questions) {
      expect(sq.attempts).toHaveLength(0)
    }

    // 3. 跳转练习页，验证会话渲染
    await page.goto(`/practice/${session.id}`)
    await expect(page.getByText(`共 ${session.question_count} 题`)).toBeVisible()
    // 状态标签：待开始
    await expect(page.getByText('待开始').first()).toBeVisible()
    // 进度 0/3
    await expect(page.getByText('进度 0/3')).toBeVisible()

    // 4. 第 1 题：UI 创建 attempt（点"开始答题"）
    const firstArticle = page.locator('article').first()
    await firstArticle.getByRole('button', { name: '开始答题' }).click()
    // attempt 创建后显示"开始录音"按钮（status=pending）
    await expect(firstArticle.getByRole('button', { name: '开始录音' })).toBeVisible()
    // session 状态自动转 in_progress
    await expect(page.getByText('进行中').first()).toBeVisible()

    // 5. 开始录音：点"开始录音"，乐观切 recording 状态
    await firstArticle.getByRole('button', { name: '开始录音' }).click()
    // 录音中：显示计时器 + "停止并上传"按钮
    await expect(firstArticle.getByRole('button', { name: '停止并上传' })).toBeVisible({
      timeout: 10_000,
    })
    // 录音状态标签（计时器显示 mm:ss 格式）
    await expect(firstArticle.locator('text=/\\d{2}:\\d{2}/')).toBeVisible()

    // 6. 录音 2 秒后停止上传（伪音频流，足够生成非空 Blob）
    await page.waitForTimeout(2000)
    await firstArticle.getByRole('button', { name: '停止并上传' }).click()

    // 上传成功后：attempt 转 submitted，显示"重新录音"按钮 + 录音回放区
    await expect(firstArticle.getByText('录音上传成功')).toBeVisible({ timeout: 15_000 })
    await expect(firstArticle.getByText('录音回放')).toBeVisible()
    await expect(firstArticle.getByRole('button', { name: '重新录音' })).toBeVisible()
    // 进度 1/3
    await expect(page.getByText('进度 1/3')).toBeVisible()

    // 7. 加载播放录音（practice.md §7，GET /attempts/{id}/recording）
    await firstArticle.getByRole('button', { name: '加载播放' }).click()
    // audio 标签出现（blob URL 注入 src）
    await expect(firstArticle.locator('audio')).toBeVisible({ timeout: 10_000 })

    // 8. 第 2、3 题：通过 API 跳过（加速；UI 跳过走"跳过"按钮，已由单测覆盖）
    const sq2 = session.questions[1]
    const sq3 = session.questions[2]
    const attempt2 = await createAttemptViaAPI(request, token, sq2.id)
    await patchAttemptViaAPI(request, token, attempt2.id, 'skipped')
    const attempt3 = await createAttemptViaAPI(request, token, sq3.id)
    await patchAttemptViaAPI(request, token, attempt3.id, 'skipped')

    // 9. 刷新练习页，验证进度 3/3，"完成会话"按钮可点（ADR-015 全部终态）
    await page.reload()
    await expect(page.getByText('进度 3/3')).toBeVisible({ timeout: 10_000 })
    const completeBtn = page.getByRole('button', { name: '完成会话' })
    await expect(completeBtn).toBeEnabled()

    // 10. 完成会话（practice.md §8，ElMessageBox 二次确认）
    await completeBtn.click()
    // 确认弹窗
    await page.getByRole('button', { name: '确认完成' }).click()
    await expect(page.getByText('会话已完成')).toBeVisible({ timeout: 10_000 })
    // session 状态转 completed
    await expect(page.getByText('已完成').first()).toBeVisible()

    // 11. 通过 API 验证会话最终状态
    const finalSession = await getSessionViaAPI(request, token, session.id)
    expect(finalSession.status).toBe('completed')
    expect(finalSession.completed_at).not.toBeNull()
  })

  test('学习数据页统计在录音上传后更新', async ({ authedPage: page, request, token }) => {
    // 先记录录音前的今日统计
    const beforeRes = await authedRequest(request, token, 'GET', '/learning/overview')
    expect(beforeRes.code).toBe(0)
    const beforeToday = (beforeRes.data as { today: { recording_count: number } }).today.recording_count

    // 创建会话并录音上传 1 题
    const session = await createSessionViaAPI(request, token, {
      mode: 'random',
      question_count: 1,
    })
    const sq = session.questions[0]
    const attempt = await createAttemptViaAPI(request, token, sq.id)
    // UI 录音上传
    await page.goto(`/practice/${session.id}`)
    const article = page.locator('article').first()
    // attempt 已通过 API 创建，刷新后 UI 显示"开始录音"
    await page.reload()
    await expect(article.getByRole('button', { name: '开始录音' })).toBeVisible({
      timeout: 10_000,
    })
    await article.getByRole('button', { name: '开始录音' }).click()
    await expect(article.getByRole('button', { name: '停止并上传' })).toBeVisible()
    await page.waitForTimeout(2000)
    await article.getByRole('button', { name: '停止并上传' }).click()
    await expect(article.getByText('录音上传成功')).toBeVisible({ timeout: 15_000 })

    // 录音上传成功后 study_records 同步更新（ADR-022）
    const afterRes = await authedRequest(request, token, 'GET', '/learning/overview')
    const afterToday = (afterRes.data as { today: { recording_count: number } }).today.recording_count
    expect(afterToday).toBe(beforeToday + 1)

    // 访问学习数据页验证 UI 渲染统计
    await page.goto('/learning')
    await expect(page.getByText('今日').first()).toBeVisible({ timeout: 10_000 })
  })
})

// 局部 helper 引用（fixtures 已导出，此处仅为类型提示）
import {
  createSessionViaAPI,
  createAttemptViaAPI,
  patchAttemptViaAPI,
  getSessionViaAPI,
  authedRequest,
} from './fixtures'

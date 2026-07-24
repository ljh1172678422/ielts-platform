import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright 配置（Phase 11.6 / 11.7，对齐 development-plan.md §13）。
 *
 * E2E 测试需要本地起 backend + postgres + user-web：
 *   docker compose up -d postgres backend
 *   pnpm --filter @ielts/user-web dev
 *   pnpm --filter @ielts/user-web test:e2e
 *
 * 沙箱无法运行（无 Docker / PG / 显示），仅保证类型正确；本地统一验收。
 *
 * 录音测试：Chromium 通过 --use-fake-device-for-media-stream 注入伪音频流，
 *           无需真实麦克风；permissions.allow=['microphone'] 跳过授权弹窗。
 */
export default defineConfig({
  testDir: './tests-e2e',
  fullyParallel: false, // 练习会话状态机有顺序依赖，串行更稳
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1, // 单 worker：避免测试账号并发创建会话相互干扰
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
  timeout: 60_000,
  expect: { timeout: 10_000 },

  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    // 录音权限：直接授予，避免授权弹窗阻塞
    permissions: ['microphone'],
    launchOptions: {
      args: [
        // 伪媒体流：MediaRecorder 可录音，无需真实麦克风
        '--use-fake-ui-for-media-stream',
        '--use-fake-device-for-media-stream',
        '--autoplay-policy=no-user-gesture-required',
      ],
    },
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  // 自动起 user-web dev server（开发态 vite proxy 转发 /api 到 backend）
  // 若已手动启动，设 E2E_SKIP_WEBSERVER=1 跳过
  webServer: process.env.E2E_SKIP_WEBSERVER
    ? undefined
    : {
        command: 'pnpm dev',
        url: 'http://localhost:5173',
        reuseExistingServer: !process.env.CI,
        timeout: 60_000,
      },
})

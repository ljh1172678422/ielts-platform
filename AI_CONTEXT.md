# AI_CONTEXT.md — AI 协作上下文

> 本文档回答"现在做到哪了"，是 AI 每次协作开始前必须先读的锚点。
> 与 `PROJECT_SPEC.md`（回答"项目是什么"）配合使用。
> 维护原则：**每完成一个阶段或模块，立即更新本文件。**

---

## 1. 项目身份

- **项目名称**：IELTS Speaking Web App
- **代号**：`ielts-platform`
- **一句话定位**：雅思口语练习闭环 Web 应用（题库 → 练习 → 录音 → 统计）
- **当前规格版本**：PROJECT_SPEC v0.5

---

## 2. 当前阶段

**Phase 10 — 首页（已完成）** → 下一步 **Phase 11 — 测试**

```text
[完成] === Phase 0 文档设计阶段全部完成 ===
[完成] === Phase 1 开发环境阶段全部完成 ===
  - 1.1 Monorepo (pnpm workspace + 根 package.json + .editorconfig/.nvmrc/.gitignore)
  - 1.2 user-web (Vue3+TS+Vite+Tailwind+Element Plus+ECharts, build 通过)
  - 1.3 admin-web (Vue3+TS+Vite+Element Plus, build 通过)
  - 1.4 packages (types/api-client/ui/utils 骨架, type-check 通过, user-web 引用验证通过)
  - 1.5 backend (FastAPI 骨架 + /health 200 + pytest 通过; 修复 success() exclude_none 违反 common.md §2.1)
  - 1.6 Docker Compose (4 服务编排 + 3 Dockerfile + 2 nginx.conf, YAML 验证通过)
         ⚠ 实际 `docker compose up` 验收需本地 Docker 环境（沙箱无 Docker）
  - 1.7 Git 分支策略 (README.md 记录 main/develop+feature/* + Conventional Commits)
[完成] === Phase 2 数据库阶段全部完成 ===
  - 2.1 Alembic 初始化 (migrations/env.py 注入 sync_url + alembic.ini file_template 日期前缀)
  - 2.2-2.5 15 表迁移 (拓扑序 001→015, 1:1 对齐 database-design v0.4 DDL)
  - 2.6 种子数据 (迁移 017: roles(user/admin) + Other 主题, ON CONFLICT 幂等)
  - 2.7 updated_at 触发器 (迁移 016: set_updated_at() 函数 + 11 表 BEFORE UPDATE 触发器)
[完成] === Phase 3 后端基础架构全部完成 ===
  - 3.3 安全层 (core/security.py: JWT HS256 24h + bcrypt 原生 API cost=12, 弃 passlib)
  - 3.5 依赖注入 (core/dependencies.py: get_current_user/require_admin; models/user.py 4 表 ORM)
  - 3.6 响应中间件 (core/exceptions.py: 4 异常处理器全链路信封化 AppError/422/HTTPException/500)
  - 3.7 模块骨架 (modules/{auth,users}/{router,service,repository,schemas}.py)
[完成] === Phase 4 用户系统全部完成 ===
  - 4.1-4.6 auth/users 8 接口 + 23 单测全绿
  - 4.7-4.8 user-web 登录/注册/我的页 (type-check + build 通过)
[完成] === Phase 5 管理后台 ===
  - 5.1-5.5 admin 后端 API (dashboard/users/topics/tags/questions CRUD + 启停)
         后端单测 test_admin_* 全绿；admin.md 契约对齐
  - 5.6 admin-web 骨架 (路由 + AdminLayout + LoginView + auth store; build 通过)
  - 5.7 admin-web 各页 (Dashboard/Users/Topics/Tags/Questions 全部完成; type-check + build 通过)
[完成] === Phase 6 题库系统（用户端）===
  - 6.1-6.3 questions 后端模块 (列表筛选/分页/排序 + 详情 4001/4002 分级 + 收藏 POST/DELETE 幂等)
         新增 models/{favorite,practice}.py ORM；questions.md 契约对齐；test_questions 17 单测全绿
  - 6.4 user-web 题库页 (QuestionsView 列表+筛选+收藏星标乐观更新+分页 / QuestionDetailView 详情+Cue Card 渲染+收藏+跳练习入口)
         type-check + build 通过（1659 modules，两 View 独立 chunk）
[完成] === Phase 7 练习系统 ===
  - 7.1-7.5 practice 后端模块 (会话创建/获取/完成 + attempt 创建/更新；状态机 created→in_progress→completed；
         ADR-015 跨表约束校验；5001 会话不存在/5002 状态非法/5003 越权/5004 题数不足/5006 未完成题目)
         扩展 models/practice.py (PracticeSession/PracticeAttempt)；practice.md 契约对齐；test_practice 单测全绿
  - 7.6 user-web 练习页 (PracticeView 状态机 UI + 进度统计 + ADR-015 完成校验 + QuestionDetailView 开始练习入口创建会话跳转)
         路由 /practice/:id；type-check + build 通过（PracticeView 独立 chunk 7.80 kB）
[完成] === Phase 8 录音上传/下载 ===
  - 8.1 录音存储层 (core/storage.py: AudioStorage 抽象 + LocalStorageBackend 实现；
         ALLOWED_MIME_TYPES(webm/mp4/mpeg/wav) + MAX_FILE_SIZE 50MB; cleanup_storage_on_failure)
  - 8.2 音频元数据 (core/audio.py: read_duration_seconds 使用 mutagen 解析 webm/mp4/mpeg/wav；
         ADR-020 后端计算 duration，拒前端传入；AudioMetadataError)
  - 8.3 上传 API (POST /attempts/{id}/recording: 5005/5003/5006/6003/6004/6002 错误码；
         事务写文件→读元数据→recording.uploaded→attempt.submitted→study_records 同步→activity_log；
         失败回滚清理文件 + recording 标 failed)
  - 8.4 下载 API (GET /attempts/{id}/recording: StreamingResponse + 5005/5003/6001 错误码)
  - 8.5 study_records 同步 (ADR-022: 录音上传 + 会话完成事务内 upsert；按 user_profiles.timezone 切日 ADR-018)
         扩展 models/activity.py (StudyRecord) + repository (upsert_study_record_for_recording/
         upsert_study_record_for_session_complete/get_user_timezone/compute_record_date)
  - 8.6 user-web 录音组件 (composables/useRecorder.ts: MediaRecorder 状态机 IDLE→REQUESTING→
         RECORDING→STOPPING→UPLOADING→UPLOADED/ERROR；webm 优先 + mp4 兜底 + 权限/异常处理；
         PracticeView 集成录音 UI + 乐观更新 + 录音回放/下载(audio 标签 + blob URL))
         api/index.ts 增加 FormData 检测自动设置 multipart/form-data + boundary
         test_practice 52 单测全绿；type-check + build 通过
[完成] === Phase 9 学习数据 ===
  - 9.1 概览 API (GET /learning/overview: today/streak/cumulative/goal_progress；
         ADR-018 时区切日；streak 内存计算 current_days/longest_days；active goal 无则全 null)
  - 9.2 趋势 API (GET /learning/{daily,weekly,monthly}: study_records 按 record_date 切分；
         补零缺失日期/周/月；按 ASC 排序；days∈[1,90]/weeks∈[1,52]/months∈[1,24])
  - 9.3 分布 API (GET /learning/{topics,parts}: 实时从事实表聚合 attempts JOIN sq JOIN recordings；
         GROUP BY snapshot.topic_id/topic_name 或 snapshot.part；ADR-016 duration 口径；ORDER BY attempt_count DESC)
  - 9.4 重算 API (POST /learning/recompute: admin 鉴权(2003)+user_id 校验(7001)+user_id 非法(1001)；
         事务内 DELETE+INSERT study_records；按用户各自 timezone 切日(ADR-018)；
         practice_count=COUNT(sessions WHERE completed)/attempt_count=COUNT(submitted attempts)/
         question_count=COUNT(DISTINCT sq)/recording_count/duration_seconds=SUM(recordings)；
         活动日志 study_records_recomputed)
  - 9.5 user-web 学习数据页 (composables/useECharts.ts: ECharts 6 按需引入 + resize/dispose 自动管理；
         views/LearningView.vue: 概览卡片(今日/连续/累计/目标) + 趋势图(线柱混合) +
         主题分布(环图) + Part 分布(双轴柱状)；granularity/months watch 自动刷新)
         packages/types 增加 13 个 learning DTO (LearningOverview/TrendResponse/TopicStat 等)
         路由 /learning 受保护
         test_learning 25 单测全绿；type-check + build 通过(LearningView chunk 564KB 含 echarts)
[完成] === Phase 10 首页 ===
  - 10.1 首页 API (GET /home/overview: 单接口聚合 today/streak/goal_progress/recent_practice/recommendations；
         ADR-028 确定性推荐 5 级短路 unfinished_session→recent_topic→favorite→less_practiced_part→popular；
         复用 learning.repository 子查询 fetch_today_streak_goal；跨级 question_id 去重；凑齐即停；
         goal_progress 扩展 target_score/exam_date；无 active goal 时 whole field null；
         recommendation_limit ∈ [1,10] 越界→1001/422；home.md §2.4 错误码对齐)
  - 10.2 user-web 首页改造 (views/HomeView.vue: 未登录落地页 + 已登录聚合仪表盘；
         今日统计 4 卡片 + 连续打卡/目标进度双栏 + 未完成 session 继续练习入口 +
         推荐列表含 reason 标签(5 种颜色映射) + 点击跳题目详情；
         packages/types 增加 6 个 home DTO (HomeOverview/Recommendation/RecommendationReason 等))
         test_home 11 单测全绿；163 后端单测全绿；ruff 通过；type-check + build 通过
[待办-用户] === 本地 Docker 验证 ===
  ⚠ 沙箱不做预览/运行测试（无 Docker / 无 PG）。用户将在本地 docker compose up 后统一验证：
     - 1.6 四服务全绿 + /health 200
     - 2.x alembic upgrade head 建 15 表 + 触发器 + 种子
     - 4.x auth/users 全链路
     - 5.x admin 后台登录 + dashboard/users/topics/tags/questions CRUD + 启停
     - 6.x 题库浏览/筛选/收藏/详情 4001/4002 分级
     - 7.x 练习会话全生命周期（创建/续练/答题状态机/ADR-015 完成）
     - 8.x 录音上传/下载/回放 + study_records 同步 + duration 后端计算
     - 9.x 学习概览/趋势/分布/重算（含 streak 算法/时区切日/ECharts 渲染）
     - 10.x 首页聚合 + 5 级推荐（确定性可复现）
  沙箱侧只保证：单测全绿、type-check + build 通过、ruff 通过、迁移 offline SQL 语法正确。
[待办]   Phase 11+ 测试/部署
```

---

## 3. 当前任务

- **Phase 10 首页已全部完成**（10.1–10.2）：home 后端模块（GET /home/overview 单接口聚合 + ADR-028 5 级推荐短路）+ user-web HomeView 聚合仪表盘改造（推荐含 reason 标签）。
- **下一步**：阶段 11 测试 —— 补充端到端测试（后端 auth/practice/recording/learning + 前端登录/练习录音流程）。
- **沙箱不做预览/运行验证**（无 Docker / 无 PG）；用户将在本地 docker compose up 后统一验收。
- 沙箱侧仅保证：单测全绿、`type-check + build` 通过、`ruff` 通过。

### 3.1 当前任务边界（阶段 11 生效）

**阶段 11 允许：**
- 按 development-plan.md §13 顺序执行任务 11.1–11.6。
- 补充后端测试（auth/practice/recording/learning 端到端，对齐 ADR-015/状态机/事务回滚）。
- 补充前端测试（Vitest/Playwright 登录跳转 + 练习录音完整闭环）。
- 一次只执行一个任务，完成即 commit + 更新 AI_CONTEXT。

**禁止（阶段 11 仍生效）：**
- ❌ 修改已锁定文档（PROJECT_SPEC / database-design / system-architecture / 全部 API 文档 / user-flow / development-plan）。
- ❌ 改变 DB schema（阶段 2 已锁定 15 表 + 约束 + 索引；如需变更先走修改规则）。
- ❌ 偏离 system-architecture §3 分层（router→service→repository，session 注入 repository）。
- ❌ 改变统一响应结构 `{code,message,data,details?}`。
- ❌ 改变状态机或核心事实链（ADR-015 attempt 跨表约束）。
- ❌ 前端直设 attempt status=submitted（只能由录音上传事务设置）。
- ❌ 一次性生成整个项目（PROJECT_SPEC §开发原则）。

> 阶段 10 → 阶段 11 转换已由用户连续执行模式授权覆盖，无需再次确认。

---

## 4. 已完成模块

**代码模块（Phase 1 开发环境）**：

| 模块 | 路径 | 状态 | 验收 |
| --- | --- | --- | --- |
| Monorepo 根 | `package.json` / `pnpm-workspace.yaml` | ✅ | `pnpm install` 通过 |
| user-web | `apps/user-web/` | ✅ | build 通过（1594 modules） |
| admin-web | `apps/admin-web/` | ✅ | build 通过 |
| packages/types | `packages/types/` | ✅ | type-check 通过（协议层类型） |
| packages/api-client | `packages/api-client/` | ✅ | type-check 通过（axios+信封解包） |
| packages/ui | `packages/ui/` | ✅ | type-check 通过（占位组件） |
| packages/utils | `packages/utils/` | ✅ | type-check 通过（时间/duration 工具） |
| backend 骨架 | `backend/app/` | ✅ | uvicorn 启动 + /health 200 + pytest 通过 |
| Docker Compose | `docker-compose.yml` + Dockerfile×3 + nginx×2 | ✅ | YAML 验证通过（docker up 验收需本地） |
| README | `README.md` | ✅ | Git 分支策略 + 启动说明 |

**代码模块（Phase 2 数据库）**：

| 模块 | 路径 | 状态 | 验收 |
| --- | --- | --- | --- |
| Alembic 环境 | `backend/migrations/env.py` + `alembic.ini` | ✅ | env.py 注入 sync_url + file_template 日期前缀；`alembic heads` = 017 |
| 15 表迁移 | `backend/migrations/versions/20260723_001~015_*.py` | ✅ | 拓扑序链完整 001→015，1:1 对齐 database-design v0.4 DDL（字段/约束/FK/索引/CHECK） |
| 触发器迁移 | `backend/migrations/versions/20260723_016_*.py` | ✅ | set_updated_at() 函数 + 11 表 BEFORE UPDATE 触发器（4 表无 updated_at 跳过） |
| 种子迁移 | `backend/migrations/versions/20260723_017_*.py` | ✅ | roles(user/admin) + Other 主题，ON CONFLICT DO NOTHING 幂等 |
| seed_admin 脚本 | `backend/scripts/seed_admin.py` | ✅ | bcrypt cost≥12 + 生产密码强度校验 + 幂等跳过；`ruff check` + import 验证通过 |
| config 补全 | `backend/app/core/config.py` | ✅ | +seed_admin_nickname 字段（对齐 §9.3）+ `.env.example` 同步 |
| 全链路验证 | — | ✅ | `alembic upgrade head --sql` 生成全部 DDL/索引/触发器/种子 SQL 语法正确；`pytest` 1 passed；`ruff check` 0 错误 |

**代码模块（Phase 3 后端基础架构）**：

| 模块 | 路径 | 状态 | 验收 |
| --- | --- | --- | --- |
| 安全层 | `backend/app/core/security.py` | ✅ | JWT HS256 24h + bcrypt 原生 API cost=12（弃 passlib，1.7.4 与 bcrypt 4.x 兼容 bug） |
| 依赖注入 | `backend/app/core/dependencies.py` | ✅ | get_current_user / require_admin（Bearer→解码→查 user→校验 status/role） |
| 响应中间件 | `backend/app/core/exceptions.py` | ✅ | 4 异常处理器全链路信封化（AppError/422/HTTPException/500），冒烟验证 404→1004 等 |
| 用户域 ORM | `backend/app/models/{user,activity}.py` | ✅ | 4+1 表 SQLAlchemy 2.x Mapped 风格（Role/User/UserProfile/UserGoal + UserActivityLog） |
| 模块骨架 | `backend/app/modules/{auth,users}/` | ✅ | router/service/repository/schemas 分层，main.py 注册路由 |

**代码模块（Phase 4 用户系统）**：

| 模块 | 路径 | 状态 | 验收 |
| --- | --- | --- | --- |
| auth 模块 | `backend/app/modules/auth/{router,service,repository,schemas}.py` | ✅ | register/login/logout 3 接口；3001 邮箱冲突 / 3002 防枚举 / 2004 禁用；4 单测文件 10 tests |
| users 模块 | `backend/app/modules/users/{router,service,repository,schemas}.py` | ✅ | me(GET/PUT) / me/password / me/goals(GET/POST/PUT)；timezone IANA / 3003 旧密码错 / ADR-014 active 唯一；2 单测文件 12 tests |
| user-web 登录页 | `apps/user-web/src/views/{Login,Register}View.vue` | ✅ | auth store(login/register/logout/fetchProfile) + api 拦截器(token/401) + 路由守卫；type-check+build 通过 |
| user-web 我的页 | `apps/user-web/src/views/ProfileView.vue` | ✅ | 资料/密码/目标 三 Tab；全量替换/改密/目标 CRUD 状态机；type-check+build 通过 |
| 共享类型 | `packages/types/src/index.ts` | ✅ | +用户域实体类型（UserPublic/UserProfilePublic/AuthData/UserGoal/GoalsResponse）+ 请求 DTO |

**代码模块（Phase 5 管理后台）**：

| 模块 | 路径 | 状态 | 验收 |
| --- | --- | --- | --- |
| admin 后端模块 | `backend/app/modules/admin/{router,service,repository,schemas}.py` | ✅ | dashboard/users/topics/tags/questions CRUD + 启停；8001 Other 保护 / 8002 引用检查 / 8006 防自锁 / 8007 防管理员互操作；test_admin_* 单测全绿 |
| admin-web 骨架 | `apps/admin-web/src/{router,layouts/AdminLayout,stores/auth,views/LoginView}.vue` | ✅ | 路由守卫 + AdminLayout 侧栏 + auth store(login 校验 admin 角色) + api 拦截器；build 通过 |
| admin-web Dashboard | `apps/admin-web/src/views/DashboardView.vue` | ✅ | GET /admin/dashboard 统计卡片（用户/题目/练习/分类） |
| admin-web 用户管理 | `apps/admin-web/src/views/UsersView.vue` | ✅ | 用户列表(keyword/status/role 筛选+分页) + 启用/禁用；前端拦截自锁/管理员互操作 |
| admin-web 主题管理 | `apps/admin-web/src/views/TopicsView.vue` | ✅ | 主题 CRUD + 软删；Other 主题(is_system)禁用编辑 name/slug + 禁用删除 |
| admin-web 标签管理 | `apps/admin-web/src/views/TagsView.vue` | ✅ | 标签 CRUD + 软删；8002 引用检查提示 |
| admin-web 题目管理 | `apps/admin-web/src/views/QuestionsView.vue` | ✅ | 题目列表(6 维筛选+分页) + 创建/编辑(全字段+tag 多选) + 状态切换(draft/published/disabled 下拉) |
| admin 域类型 | `apps/admin-web/src/types/admin.ts` | ✅ | admin.md §8 DTO 对齐（DashboardData/AdminUserListItem/AdminTopicItem/AdminTagItem/AdminQuestionListItem/Detail + 请求 DTO） |

**代码模块（Phase 6 题库系统-用户端）**：

| 模块 | 路径 | 状态 | 验收 |
| --- | --- | --- | --- |
| favorites ORM | `backend/app/models/favorite.py` | ✅ | favorites 表 ORM（uq_favorites_user_question 唯一约束支撑幂等 ON CONFLICT） |
| practice ORM（部分） | `backend/app/models/practice.py` | ✅ | PracticeSessionQuestion 表 ORM（practice_count 统计用，Phase 7 追加 Session/Attempt） |
| questions 后端模块 | `backend/app/modules/questions/{router,service,repository,schemas}.py` | ✅ | 4 接口：列表(筛选/分页/newest+popular排序) + 详情(4001/4002分级) + 收藏 POST/DELETE 幂等；published 可见性 ADR-010；test_questions 17 单测全绿 |
| user-web 题库页 | `apps/user-web/src/views/QuestionsView.vue` | ✅ | Part/难度/keyword/排序/仅收藏 筛选 + 分页 + 收藏星标乐观更新；type-check+build 通过 |
| user-web 题目详情页 | `apps/user-web/src/views/QuestionDetailView.vue` | ✅ | 完整字段 + Cue Card 按 \n/- 渲染 + 收藏 + 跳练习入口(Phase 7)；type-check+build 通过 |
| 共享类型（题库域） | `packages/types/src/index.ts` | ✅ | +QuestionListItem/QuestionDetail/FavoriteResponse/PaginatedQuestions/QuestionListQuery/TopicRef/TagRef/QuestionSort |

**代码模块（Phase 7 练习系统）**：

| 模块 | 路径 | 状态 | 验收 |
| --- | --- | --- | --- |
| practice ORM（完整） | `backend/app/models/practice.py` | ✅ | PracticeSession + PracticeSessionQuestion(Phase6) + PracticeAttempt + Recording 四表 ORM，对齐 database-design v0.4 §3.3 |
| practice 后端模块 | `backend/app/modules/practice/{router,service,repository,schemas}.py` | ✅ | 5 接口：会话创建/获取/完成 + attempt 创建/更新；状态机 created→in_progress→completed；ADR-015 跨表约束；5001/5002/5003/5004/5006 错误码；test_practice 单测全绿 |
| user-web 练习页 | `apps/user-web/src/views/PracticeView.vue` | ✅ | 状态机 UI（pending→recording→skipped/failed/submitted）+ 进度统计 + ADR-015 完成校验 + 续练；type-check+build 通过 |
| 练习入口 | `apps/user-web/src/views/QuestionDetailView.vue` + `router/index.ts` | ✅ | 题目详情"开始练习"创建会话(mode=topic)+跳 /practice/:id；路由守卫受保护 |
| 共享类型（练习域） | `packages/types/src/index.ts` | ✅ | +PracticeSession/SessionQuestion/Attempt/Recording/SessionStatus/AttemptStatus/PracticeMode/QuestionSnapshot + 请求 DTO |

**代码模块（Phase 8 录音上传/下载）**：

| 模块 | 路径 | 状态 | 验收 |
| --- | --- | --- | --- |
| 录音存储抽象 | `backend/app/core/storage.py` | ✅ | AudioStorage 抽象类 + LocalStorageBackend；ALLOWED_MIME_TYPES(webm/mp4/mpeg/wav) + MAX_FILE_SIZE 50MB；cleanup_storage_on_failure；为 MinIO 预留扩展点 |
| 音频元数据 | `backend/app/core/audio.py` | ✅ | read_duration_seconds 使用 mutagen 解析 webm/mp4/mpeg/wav；ADR-020 后端计算 duration；AudioMetadataError 异常 |
| StudyRecord ORM | `backend/app/models/activity.py` | ✅ | +StudyRecord 表 ORM（uq_study_records_user_date 唯一约束）；models/__init__.py 导出 |
| practice 仓库扩展 | `backend/app/modules/practice/repository.py` | ✅ | +录音 CRUD + submit_attempt_with_recording + upsert_study_record_for_recording + upsert_study_record_for_session_complete + get_user_timezone + compute_record_date（ADR-018 timezone 切日） |
| 录音上传/下载 API | `backend/app/modules/practice/{router,service}.py` | ✅ | POST/GET /attempts/{id}/recording；事务：写文件→读元数据→recording.uploaded→attempt.submitted→study_records 同步→activity_log；失败回滚清理；5005/5003/5006/6001/6002/6003/6004 错误码 |
| user-web 录音组件 | `apps/user-web/src/composables/useRecorder.ts` | ✅ | MediaRecorder 状态机 IDLE→REQUESTING→RECORDING→STOPPING→UPLOADING→UPLOADED/ERROR；webm 优先 + mp4 兜底 + 权限/异常处理；自动停止兜底 |
| user-web 练习页扩展 | `apps/user-web/src/views/PracticeView.vue` | ✅ | 集成录音 UI + 乐观更新 + 录音回放/下载（audio 标签 + blob URL）；续练场景断线重连分支 |
| api 拦截器扩展 | `apps/user-web/src/api/index.ts` | ✅ | +FormData 检测自动设置 multipart/form-data + boundary（删除默认 Content-Type） |
| mutagen 依赖 | `backend/pyproject.toml` | ✅ | +mutagen 用于音频元数据解析 |
| test_practice 扩展 | `backend/tests/test_practice.py` | ✅ | 52 单测全绿（Phase 7 22 + Phase 8 录音上传/下载/study_records 同步 30） |

**代码模块（Phase 9 学习数据）**：

| 模块 | 路径 | 状态 | 验收 |
| --- | --- | --- | --- |
| learning 后端模块 | `backend/app/modules/learning/{__init__,router,service,repository,schemas}.py` | ✅ | 7 接口：overview/daily/weekly/monthly/topics/parts/recompute；ADR-008/016/018/022 落地；1001/2003/7001 错误码；test_learning 25 单测全绿 |
| learning repository | `backend/app/modules/learning/repository.py` | ✅ | study_records 聚合查询 + 事实表分布聚合(attempts JOIN sq JOIN recordings) + recompute_for_user(DELETE+INSERT) + timezone 工具(get_timezone/to_local_date/today_in_timezone/week_monday/month_start/add_months) |
| learning schemas | `backend/app/modules/learning/schemas.py` | ✅ | 13 DTO 对齐 learning.md §10；validate_days/weeks/months 范围校验(1001/422) |
| main 路由注册 | `backend/app/main.py` + `app/modules/__init__.py` | ✅ | +learning_router 挂载到 /api/v1（7 接口在 OpenAPI 出现） |
| ECharts composable | `apps/user-web/src/composables/useECharts.ts` | ✅ | ECharts 6 按需引入(Bar/Line/Pie + Grid/Legend/Title/Tooltip) + shallowRef 实例 + resize 监听 + onBeforeUnmount dispose |
| user-web 学习数据页 | `apps/user-web/src/views/LearningView.vue` | ✅ | 概览卡片(今日/连续/累计/目标) + 趋势图(线柱混合 daily/weekly/monthly 切换) + 主题分布(环图) + Part 分布(双轴柱状)；granularity/months watch 自动刷新；type-check+build 通过 |
| 路由扩展 | `apps/user-web/src/router/index.ts` | ✅ | +/learning 受保护路由 |
| 共享类型（学习数据域） | `packages/types/src/index.ts` | ✅ | +LearningOverview/DayStats/StreakStats/CumulativeStats/GoalProgress/TrendPoint/TrendResponse/TopicStat/TopicsDistributionResponse/PartStat/PartsDistributionResponse/RecomputeRequest/RecomputeResponse/TrendGranularity |

**代码模块（Phase 10 首页）**：

| 模块 | 路径 | 状态 | 验收 |
| --- | --- | --- | --- |
| home 后端模块 | `backend/app/modules/home/{__init__,router,service,repository,schemas}.py` | ✅ | 1 接口：GET /home/overview 单接口聚合；ADR-028 5 级推荐短路(unfinished_session→recent_topic→favorite→less_practiced_part→popular)；复用 learning.repository 子查询 fetch_today_streak_goal；goal_progress 扩展 target_score/exam_date；recommendation_limit ∈ [1,10] 越界→1001/422 |
| home repository | `backend/app/modules/home/repository.py` | ✅ | fetch_today_streak_goal(复用 learning 子查询) + 5 级推荐查询(get_unfinished_session_questions/get_recent_topic_questions/get_favorite_questions/get_less_practiced_part_questions/get_popular_questions) + batch_practice_counts_by_questions + to_recommendation_dict |
| home service | `backend/app/modules/home/service.py` | ✅ | get_overview 编排 + _build_recent_practice + _build_recommendations(5 级短路，跨级 question_id 去重，凑齐即停) |
| home schemas | `backend/app/modules/home/schemas.py` | ✅ | HomeOverview/HomeGoalProgress/RecentPractice/UnfinishedSessionSummary/Recommendation DTO 对齐 home.md §4 |
| main 路由注册 | `backend/app/main.py` + `app/modules/__init__.py` | ✅ | +home_router 挂载到 /api/v1（1 接口在 OpenAPI 出现） |
| user-web 首页改造 | `apps/user-web/src/views/HomeView.vue` | ✅ | 未登录落地页 + 已登录聚合仪表盘（今日统计 4 卡片 + 连续打卡/目标进度双栏 + 未完成 session 继续练习入口 + 推荐列表含 reason 标签 5 种颜色映射 + 点击跳题目详情）；type-check+build 通过 |
| 共享类型（首页域） | `packages/types/src/index.ts` | ✅ | +HomeOverview/HomeGoalProgress/RecentPractice/UnfinishedSessionSummary/Recommendation/RecommendationReason |
| test_home | `backend/tests/test_home.py` | ✅ | 11 单测全绿（recommendation_limit 校验 + recent_practice + 5 级推荐短路 + 跨级去重 + goal_progress 扩展） |

**后端关键文件（Phase 3-4 已实现）**：
- `backend/app/main.py` — create_app() 工厂 + /health + auth/users 路由注册
- `backend/app/core/config.py` — pydantic-settings 配置（jwt_secret/algorithm/expires_seconds 等）
- `backend/app/core/database.py` — async engine + session factory + Base
- `backend/app/core/security.py` — JWT HS256 签发/校验 + bcrypt 哈希/校验（cost=12）
- `backend/app/core/dependencies.py` — get_current_user / require_admin
- `backend/app/core/exceptions.py` — 统一信封 + AppError + 4 异常处理器（对齐 common.md v0.2）
- `backend/tests/` — 6 测试文件 23 tests 全绿（health + auth register/login/logout + users service/goals）

**前端共享包关键约定（对齐 common.md v0.2）**：
- `@ielts/types`：协议层（ResponseEnvelope/ErrorEnvelope/PaginatedData/ID/枚举）+ 用户域实体（UserPublic/AuthData/UserGoal 等）+ 请求 DTO
- `@ielts/api-client`：createApiClient() 工厂 + 请求拦截器(token) + 响应拦截器(信封解包) + ApiClientError
- user-web 复用 `@ielts/types`（消除本地 ApiResponse 重复定义）+ 自建 `api/index.ts`（ApiError + token 注入 + 401 处理）

**文档模块**：

| 文档 | 版本 | 状态 |
| --- | --- | --- |
| `PROJECT_SPEC.md` | v0.5 | ✅ 完成（规格已锁定） |
| `AI_CONTEXT.md` | v0.4 | ✅ 完成（本文件） |
| `docs/database/database-design.md` | v0.4 | ✅ 完成（DDL 已锁定，无开放问题） |
| `docs/architecture/system-architecture.md` | v0.1 | ✅ 完成（架构已锁定） |
| `docs/api/common.md` | v0.2 | ✅ 完成（通用约定已锁定，错误码扩展） |
| `docs/api/auth.md` | v0.1 | ✅ 完成（认证接口已锁定） |
| `docs/api/users.md` | v0.1 | ✅ 完成（用户资料/密码/目标已锁定） |
| `docs/api/questions.md` | v0.1 | ✅ 完成（题库浏览/收藏已锁定） |
| `docs/api/practice.md` | v0.1 | ✅ 完成（会话/答题/录音已锁定） |
| `docs/api/learning.md` | v0.1 | ✅ 完成（统计/趋势/分布/重算已锁定） |
| `docs/api/home.md` | v0.1 | ✅ 完成（首页聚合+推荐已锁定） |
| `docs/api/admin.md` | v0.1 | ✅ 完成（后台CRUD已锁定） |
| `docs/product/user-flow.md` | v0.1 | ✅ 完成（用户流程已锁定） |
| `docs/development-plan.md` | v0.1 | ✅ 完成（开发计划已锁定） |

---

## 4.1 已锁定模块与修改规则

> 以下文档已锁定，AI 不得擅自修改。修改必须按固定顺序进行。

**已锁定：**
- `PROJECT_SPEC.md` v0.5
- `docs/database/database-design.md` v0.4
- `docs/architecture/system-architecture.md` v0.1
- `docs/api/common.md` v0.2
- `docs/api/auth.md` v0.1
- `docs/api/users.md` v0.1
- `docs/api/questions.md` v0.1
- `docs/api/practice.md` v0.1
- `docs/api/learning.md` v0.1
- `docs/api/home.md` v0.1
- `docs/api/admin.md` v0.1
- `docs/product/user-flow.md` v0.1
- `docs/development-plan.md` v0.1

**修改规则（顺序不可逆）：**

```text
1. 发现普通实现问题
     → 不直接修改已锁定文档，在当前任务文档中记录并报告。
2. 发现规格冲突
     → 先报告，等待确认。
3. 确认需要变更
     → 先更新 PROJECT_SPEC.md
     → 再同步 database-design.md
     → 最后更新 AI_CONTEXT.md
     → 三者版本号同步递增
```

> 严禁反向：不得先改 database-design 再回头改 PROJECT_SPEC，也不得只改其一。

**当前禁止修改的数据库要素：**
- 15 张表的清单与归属域
- 核心事实链 `Session → SessionQuestion → Attempt → Recording`
- 所有枚举值集合（§2）
- 所有业务约束（PROJECT_SPEC §4.5 共 12 条）
- 主键策略、软删除策略、外键 ON DELETE 策略

如发现上述要素需要变更，必须先走修改规则流程。

---

## 5. 当前禁止

在进入阶段 1 之前，**严格禁止**以下行为（违反即返工）：

- ❌ 暂不写业务代码（FastAPI 路由、service、repository）。
- ❌ 暂不初始化前端项目（`apps/user-web`、`apps/admin-web`）。
- ❌ 暂不初始化后端项目骨架（`backend/app/...`）。
- ❌ 暂不安装依赖、不生成 `pyproject.toml` / `package.json`。
- ❌ 暂不运行 Alembic（DDL 先以文档形式确定）。
- ❌ 暂不创建 Docker Compose 实际配置（可在文档中规划）。

当前允许的产出仅为 `docs/` 与根目录规格文档。

---

## 6. 技术栈速查

| 层 | 技术 | 版本约束 |
| --- | --- | --- |
| 前端框架 | Vue 3 + TypeScript | Composition API + `<script setup>` |
| 前端构建 | Vite | — |
| 路由/状态 | Vue Router / Pinia | — |
| HTTP | Axios | — |
| UI | Element Plus（后台） + Tailwind CSS（用户端） | — |
| 图表 | ECharts | — |
| 后端 | FastAPI | — |
| ORM | SQLAlchemy 2.x | `Mapped` / `mapped_column` 风格 |
| 校验 | Pydantic 2.x | `model_config` |
| 迁移 | Alembic | — |
| 数据库 | PostgreSQL | — |
| 存储 | 开发本地 FS / 生产 MinIO | — |
| 部署 | Docker + Docker Compose + Nginx | — |

---

## 7. 重要架构决策（速查，详见 ADR）

| # | 决策 | 一句话理由 |
| --- | --- | --- |
| ADR-001 | Monorepo（pnpm workspace + backend） | 共享 types/api-client，统一版本 |
| ADR-002 | 前端仅 user-web + admin-web 两个应用 | MVP 多应用成本无收益 |
| ADR-003 | 后端按领域模块（`modules/<domain>`）组织 | 限定 AI 改动范围，降低耦合 |
| ADR-004 | 数据库 PostgreSQL（MVP 不引入 Redis） | 单一存储降低运维复杂度 |
| ADR-005 | 主键 BIGINT（非 UUID） | 自增、索引友好、足够 MVP 规模 |
| ADR-006 | `practice_answers` → `practice_attempts` | 支持同题重复录音，语义更准 |
| ADR-007 | 录音 API 绑定 attempt（`/attempts/{id}/recording`） | 录音归属明确，无顶层 `/recordings` |
| ADR-008 | `study_records` 为可重算聚合，非事实来源 | 统计异常可从事实表重建 |
| ADR-009 | MVP 角色级权限，不建 `permissions` 表 | 避免提前引入 RBAC |
| ADR-010 | 题目用 `status=disabled` 软停用，不物理删 | 历史会话引用完整性 |
| ADR-011 | 题目录入强制 `source_type` + `source_name` | 版权合规 |
| ADR-012 | MVP 推荐用确定性规则，非 AI | 可复现可测试 |
| ADR-013 | 主键用 `BIGINT GENERATED ALWAYS AS IDENTITY` | SQL 标准，优于 BIGSERIAL，防序列注入 |
| ADR-014 | `user_goals` active 目标用部分唯一索引 | 业务约束"同时仅一个 active 目标" |
| ADR-015 | Attempt/Recording 跨表状态约束走应用层 | DB CHECK 无法跨表，service 校验 |
| ADR-016 | `study_records.duration_seconds` = uploaded 录音时长和 | 易精确计算，避免 session 时长含噪音 |
| ADR-017 | `question_tags` 用复合主键不设独立 id | 纯关联表，复合主键更自然 |
| ADR-018 | 统计按 `user_profiles.timezone` 切日 | 不同时区"今日"不同，UTC 切日会错 |
| ADR-019 | `topic_id` NOT NULL + Other 兜底主题 | 保证按主题练习/统计/推荐可行 |
| ADR-020 | `recordings.duration_seconds` 后端读元数据计算 | 不信前端，统计精确 |
| ADR-021 | `mime_type` MVP 不转码 | 降低复杂度，不擅自引入 FFmpeg |
| ADR-022 | `study_records` MVP 同步更新、架构预留异步 | 业务模型稳定，未来切队列不改接口 |
| ADR-023 | `user_activity_logs` 保留 180 天，审计另建表 | 行为日志与审计日志职责分离 |
| ADR-024 | `Other` 主题系统保留（不可删/不可停用/不可重命名） | 兜底主题被删会破坏 `topic_id NOT NULL` 约束 |
| ADR-025 | JSON 中 id 序列化为字符串 | BIGINT 超 JS 2^53 丢精度（ADR-005 配套） |
| ADR-026 | 全链路 snake_case，不转 camelCase | 减少转换层，与 DB 列名一致 |
| ADR-027 | MVP 无状态退出，无 token 撤销表 | 不引入服务端会话存储，简化认证 |
| ADR-028 | 确定性推荐 5 级短路（无 AI） | 推荐可复现、无随机、可解释；PROJECT_SPEC §7 |

> ADR 正文待建：`docs/architecture/decisions/ADR-00x-*.md`。

---

## 8. 当前数据库实体（MVP，共 15 表）

```text
用户域
  users              (账号/密码哈希/邮箱/状态/角色)   软删:是
  user_profiles      (昵称/头像/资料)                软删:否
  user_goals         (目标分数/考试日期/每日时长)     软删:是
  roles              (user/admin)                    软删:否

题库域
  speaking_topics    (主题)                          软删:是
  tags               (标签)                          软删:是
  speaking_questions (Part/标题/内容/CueCard/难度/状态/来源) 软删:否(status)
  question_tags      (题目-标签 多对多)               软删:否

练习域（核心事实链）
  practice_sessions           (会话)                  软删:否(status)
  practice_session_questions  (会话题目快照+顺序)       软删:否
  practice_attempts           (一次答题尝试)           软删:否(status)
  recordings                  (录音元数据+存储路径)    软删:是

用户行为域
  favorites           (收藏)                         软删:否(存在即收藏)
  study_records       (每日统计聚合,可重算)            软删:否
  user_activity_logs  (原始行为日志)                  软删:否
```

**核心事实链**：`Session → SessionQuestion → Attempt → Recording`

> 不建 `permissions` 表（MVP 角色级）。
> DDL 已锁定于 `docs/database/database-design.md` v0.2，主键统一 `BIGINT GENERATED ALWAYS AS IDENTITY`，`question_tags` 用复合主键。

---

## 9. 当前 API 概览（详见 docs/api/，前缀 /api/v1）

```text
auth:        register / login / logout
users:       me(GET/PUT) / me/password / me/goals
questions:   list / detail / favorite(POST/DELETE)
practice:    sessions(POST/GET) / sessions/{id}/complete
             attempts(POST) / attempts/{id}(PATCH)
             attempts/{id}/recording(POST/GET)
learning:    overview / daily / weekly / monthly / topics / history
home:        overview
admin:       users / topics / tags / questions (CRUD + 启停)
```

---

## 10. AI 修改规则

每次协作开始前，AI 必须遵守：

1. **先读** `PROJECT_SPEC.md`，再读本文件。
2. **不修改未授权模块**；后端改动默认限定在单个 `modules/<domain>`。
3. **不擅自改变数据库模型**——任何表/字段/约束变更需先更新 `docs/database/database-design.md` 并经确认。
4. **不擅自新增依赖**（Python 包 / npm 包）；新增需说明理由并经确认。
5. **不擅自改变 API 契约**——路由/方法/响应结构变更需先更新 `docs/api/`。
6. **不擅自改变统一响应结构** `{ code, message, data }`。
7. **发现规格冲突时，先报告问题**，不要自行调和。
8. **不一次性生成整个项目**；每次只做一个功能/模块/问题。
9. **状态机字段**（session/attempt/recording status）必须按 PROJECT_SPEC §5 转换，禁止自创新状态。
10. **软删除**按 PROJECT_SPEC §8 逐表执行，禁止"视情况"。

---

## 11. 代码风格基线（待代码阶段启用）

- Python：PEP 8 + ruff + mypy（严格）；类型注解必填。
- TypeScript：严格模式；禁用 `any`（除明确标注）。
- Vue：`<script setup lang="ts">`，组合式 API。
- 提交：Conventional Commits（`feat:` / `fix:` / `docs:` / `refactor:` / `test:` / `chore:`）。
- 分支：`main` / `develop` / `feature/<module>-<feature>`。

---

## 12. 协作记录

| 日期 | 协作内容 | 产出 |
| --- | --- | --- |
| 2026-07-23 | 建立 PROJECT_SPEC v0.1 | PROJECT_SPEC.md |
| 2026-07-23 | 架构级评审，升级 v0.2 | PROJECT_SPEC.md v0.2 |
| 2026-07-23 | 建立 AI 协作上下文 | AI_CONTEXT.md v0.1 |
| 2026-07-23 | 编写数据库设计 v0.1 | database-design.md v0.1 |
| 2026-07-23 | 规格一致性审查，修复 10 项冲突 | PROJECT_SPEC v0.3 / database-design v0.2 / AI_CONTEXT v0.2 |
| 2026-07-23 | 5 个行为规则决策，开放问题清零 | PROJECT_SPEC v0.4 / database-design v0.3 / AI_CONTEXT v0.3 |
| 2026-07-23 | 编写系统架构文档 | system-architecture.md v0.1 |
| 2026-07-23 | Other 主题系统保留约束 + 修复 §9 编号 | PROJECT_SPEC v0.5 / database-design v0.4 |
| 2026-07-23 | 编写 API 通用约定 | common.md v0.1 / AI_CONTEXT v0.4 |
| 2026-07-23 | 编写认证模块 API 契约 | auth.md v0.1 / ADR-027 入册 |
| 2026-07-23 | 编写用户模块 API 契约 | users.md v0.1 |
| 2026-07-23 | 编写题库模块 API 契约（用户端） | questions.md v0.1 |
| 2026-07-23 | 编写练习模块 API 契约 | practice.md v0.1 |
| 2026-07-23 | 编写学习数据模块 API 契约 | learning.md v0.1 |
| 2026-07-23 | 编写首页模块 API 契约 | home.md v0.1 / ADR-028 入册 |
| 2026-07-23 | 编写后台管理 API 契约 | admin.md v0.1 |
| 2026-07-23 | 错误码一致性修订 | common.md v0.2（8002 通用化+8006/8007 新增）/ admin.md 错误码对齐 |
| 2026-07-23 | 编写用户流程文档 | user-flow.md v0.1 |
| 2026-07-23 | 编写开发计划文档 | development-plan.md v0.1 |
| 2026-07-23 | **Phase 0 文档设计阶段全部完成** | 13 份文档锁定，待授权进入 Phase 1 |
| 2026-07-23 | **Phase 1 开发环境阶段全部完成** | Monorepo + 2 apps + 4 packages + backend 骨架 + Docker Compose + README；连续执行模式授权 |
| 2026-07-23 | **Phase 2 数据库阶段全部完成** | Alembic + 15 表迁移(001-015) + 触发器(016) + 种子(017) + seed_admin.py；offline SQL 验证通过；进入 Phase 3 |
| 2026-07-23 | **Phase 3 后端基础架构全部完成** | security.py(JWT+bcrypt 原生 API) + dependencies.py(get_current_user/require_admin) + exceptions.py(4 异常处理器) + 模块骨架；GitHub 仓库初始化 + 推送；进入 Phase 4 |
| 2026-07-23 | **Phase 4 用户系统全部完成** | auth(register/login/logout) + users(me/password/goals) 8 接口 + 23 单测全绿；user-web 登录/注册/我的页 + auth store + api 拦截器 + 路由守卫；type-check+build 通过；进入 Phase 5 |
| 2026-07-23 | **Phase 5 管理后台全部完成** | admin 后端(dashboard/users/topics/tags/questions CRUD + 启停) + test_admin_* 单测全绿；admin-web 骨架 + Dashboard/Users/Topics/Tags/Questions 5 页；沙箱放弃预览测试（无 Docker/PG），本地 docker 验证待办入计划；type-check+build 通过；进入 Phase 6 |
| 2026-07-23 | **Phase 6 题库系统（用户端）全部完成** | questions 后端模块(列表/详情/收藏) + favorites/practice ORM + test_questions 17 单测全绿；user-web 题库页/详情页(Cue Card 渲染+收藏+跳练习入口)；type-check+build 通过；进入 Phase 7 |
| 2026-07-23 | **Phase 7 练习系统全部完成** | practice 后端模块(会话创建/获取/完成 + attempt 创建/更新；状态机 + ADR-015 跨表约束) + test_practice 单测全绿；扩展 models/practice.py(PracticeSession/PracticeAttempt/Recording)；user-web PracticeView 状态机 UI + 进度统计 + QuestionDetailView 开始练习入口；路由 /practice/:id；type-check+build 通过(PracticeView 独立 chunk 7.80 kB)；进入 Phase 8 |
| 2026-07-23 | **Phase 8 录音上传/下载全部完成** | core/storage.py(AudioStorage 抽象+LocalStorageBackend) + core/audio.py(mutagen 读 duration ADR-020) + 录音上传/下载 API(POST/GET /attempts/{id}/recording，事务一致性，5005/5003/5006/6001-6004 错误码) + study_records 同步(ADR-022 + ADR-018 timezone 切日) + models/activity.py(StudyRecord)；user-web composables/useRecorder.ts(MediaRecorder 状态机 IDLE→...→UPLOADED/ERROR) + PracticeView 集成录音 UI + 回放/下载 + api FormData 自动处理；test_practice 52 单测全绿；type-check+build 通过；进入 Phase 9 |
| 2026-07-23 | **Phase 9 学习数据全部完成** | learning 后端模块(7 接口：overview/daily/weekly/monthly/topics/parts/recompute；ADR-008/016/018/022；streak 内存计算；事实表实时聚合；DELETE+INSERT 重算事务) + test_learning 25 单测全绿；user-web composables/useECharts.ts(ECharts 6 按需引入+resize/dispose) + LearningView.vue(概览卡片+趋势线柱混合+主题环图+Part 双轴柱状) + 路由 /learning；packages/types +13 learning DTO；全量 152 后端测试通过；type-check+build 通过(LearningView chunk 564KB 含 echarts)；进入 Phase 10 |

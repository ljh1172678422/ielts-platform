# IELTS Speaking Web App — 项目规格说明（PROJECT_SPEC）

> 本文档是 IELTS Speaking Web 应用 MVP 的最高规格说明，是后续所有设计、开发、评审的基准。
> 任何与本文档冲突的实现都需要先更新本文档，再写代码。
> 当前版本：**v0.5**（Other 主题系统保留约束，详见 §16 变更记录）。

---

## 0. 文档定位与使用规则

- 本文档固定核心维度：**产品范围、技术栈、目录结构、数据库模型、页面流程、数据一致性、软删除策略、权限模型、推荐规则、版权约束、MVP 验收标准**。
- 本文档不包含具体 API 字段、UI 设计稿、部署脚本等细节，这些在后续 `docs/` 子文档中展开。
- AI 协作时，每次先让 AI 阅读本文档（以及 `AI_CONTEXT.md`），再开始具体任务。
- 遵循"先文档、后代码"原则：功能未在文档中定义清楚前，不写业务代码。

---

## 1. 产品概述

### 1.1 产品名称

IELTS Speaking Web App（暂定代号：`ielts-platform`）

### 1.2 产品目标

为雅思口语学习者提供一个可独立完成"看题 → 练习 → 录音 → 回顾 → 统计"闭环的 Web 应用，第一版（MVP）完成完整功能闭环，不追求商业化与 AI 评分。

### 1.3 目标用户

- 备考雅思、需要口语练习环境的用户。
- 需要题库管理与内容录入能力的管理员。

### 1.4 核心价值

- 结构化题库（按 Part / 主题 / 标签组织）。
- 模拟练习 + 浏览器原生录音。
- 练习记录持久化与学习数据可视化。
- 管理后台作为内容源头，支持题目录入与启停。

### 1.5 MVP 范围

**包含（MVP）：**

- 用户注册、登录、退出、获取当前用户、修改资料、修改密码
- 题库浏览、搜索、Part/主题/标签筛选、分页、收藏、查看详情
- 创建练习（随机/按条件抽题）、练习页面、答题流程
- 浏览器录音、录音上传、录音保存
- 学习数据统计（总览、日/周/月趋势、Part/主题分布、练习历史）
- 首页（今日统计、最近练习、继续练习、按规则推荐）
- 管理后台：登录、Dashboard、用户管理、主题 CRUD、标签 CRUD、题目 CRUD（含启停）
- 用户学习目标（user_goals）设置

**不包含（非 MVP，后续阶段）：**

- AI 评分、发音评分
- 社交、排行榜
- 支付、微信登录
- 批量导入（JSON/CSV/Excel）——作为后期增强，MVP 仅支持单条录入
- Redis 缓存（MVP 仅用 PostgreSQL）
- RBAC 权限系统与 `permissions` 表（MVP 仅角色级，见 §10）
- AI 智能推荐（MVP 使用规则推荐，见 §11）

---

## 2. 技术栈

### 2.1 前端

| 用途 | 技术 |
| --- | --- |
| 框架 | Vue 3 + TypeScript |
| 构建 | Vite |
| 路由 | Vue Router |
| 状态 | Pinia |
| HTTP | Axios |
| UI 组件库 | Element Plus（后台与复杂表单） |
| 原子化 CSS | Tailwind CSS（用户端页面） |
| 图表 | ECharts（学习统计） |

### 2.2 后端

| 用途 | 技术 |
| --- | --- |
| 语言 | Python |
| Web 框架 | FastAPI |
| ORM | SQLAlchemy 2.x |
| 数据校验 | Pydantic 2.x |
| 迁移 | Alembic |
| 数据库 | PostgreSQL |

### 2.3 文件存储

| 环境 | 方案 |
| --- | --- |
| 开发 | 本地文件系统 |
| 生产 | S3 兼容对象存储（MinIO） |

### 2.4 部署

- Docker + Docker Compose
- Nginx（反向代理 + 静态资源）
- HTTPS
- Linux VPS

### 2.5 关键版本约束

- SQLAlchemy 必须使用 2.x 风格（`Mapped`、`mapped_column`、Session 依赖注入）。
- Pydantic 必须使用 2.x（`BaseModel`、`model_config`）。
- Vue 必须使用 Composition API + `<script setup>`。

---

## 3. 目录结构（Monorepo）

### 3.1 顶层结构

```text
ielts-platform/
├── apps/
│   ├── user-web/          # 用户端：首页/题库/练习/学习数据/我的（单一应用，模块化路由）
│   └── admin-web/         # 管理后台
├── packages/
│   ├── ui/                # 共享 UI 组件
│   ├── types/             # 共享 TypeScript 类型
│   ├── api-client/        # 共享 API 客户端
│   └── utils/             # 共享工具
├── backend/
│   ├── app/
│   │   ├── modules/       # 按领域组织（见 3.3）
│   │   ├── core/          # 配置、数据库、安全、异常、响应
│   │   └── main.py
│   ├── migrations/        # Alembic
│   ├── tests/
│   └── pyproject.toml
├── docker/
├── docs/
│   ├── product/
│   ├── architecture/
│   │   └── decisions/     # ADR 架构决策记录
│   ├── api/
│   └── database/
├── docker-compose.yml
├── PROJECT_SPEC.md        # 本文档
├── AI_CONTEXT.md          # AI 协作上下文
└── README.md
```

### 3.2 前端应用边界

> **逻辑模块 ≠ 独立 Web 应用。**

MVP 仅两个前端应用：

```text
user-web
├── 首页模块
├── 题库模块
├── 练习选择模块
├── 练习过程模块
├── 学习数据模块
└── 我的模块

admin-web
├── Dashboard
├── 用户管理
├── 题库管理
├── 标签管理
└── 主题管理
```

不拆分 `practice-web` / `question-bank-web` / `learning-data-web`。理由：MVP 阶段多应用会引入登录态共享、跨应用路由、公共 UI/API Client 重复等成本，无对应收益。

### 3.3 后端领域模块结构

```text
backend/app/
├── modules/
│   ├── auth/          # 注册、登录、退出、JWT
│   │   ├── router.py
│   │   ├── schemas.py
│   │   ├── service.py
│   │   └── repository.py
│   ├── users/         # 用户资料、目标
│   ├── questions/     # 题库、主题、标签、收藏
│   ├── practice/      # 会话、会话题目、答题（attempt）
│   ├── recordings/    # 录音上传与读取
│   ├── learning/      # 学习统计聚合
│   ├── home/          # 首页聚合 + 推荐
│   └── admin/         # 后台管理接口
│
├── core/
│   ├── config.py
│   ├── database.py
│   ├── security.py
│   ├── exceptions.py
│   └── response.py    # 统一响应结构
│
└── main.py
```

按领域组织的好处：可直接对 AI 下达"只修改 `modules/practice`，不要动其他模块"的指令，降低跨模块耦合风险。

### 3.4 后端分层职责

```text
Router (router.py)        # 入参校验、依赖注入、调用 service、返回响应
   ↓
Service (service.py)      # 业务逻辑、事务边界、跨 repository 编排
   ↓
Repository (repository.py)# 数据访问、查询封装
   ↓
Models (core/models 或各模块) # SQLAlchemy ORM
   ↓
PostgreSQL
```

- Router 不直接操作数据库；Repository 不含业务规则。
- 统一异常格式与统一响应结构在 `core/` 中定义。

---

## 4. 数据库模型

### 4.1 表清单（MVP）

| 模块 | 表 | 说明 | 软删除 |
| --- | --- | --- | --- |
| 用户 | `users` | 账号、密码哈希、邮箱、状态、角色 | 是 |
| 用户 | `user_profiles` | 昵称、头像、个人资料 | 否 |
| 用户 | `user_goals` | 学习目标（目标分数、考试日期、每日时长等） | 是 |
| 用户 | `roles` | 角色（user / admin） | 否 |
| 题库 | `speaking_topics` | 主题（Technology / Travel …） | 是 |
| 题库 | `tags` | 标签 | 是 |
| 题库 | `speaking_questions` | 题目（Part / 标题 / 内容 / Cue Card / 难度 / 状态 / 来源） | 否，用 status |
| 题库 | `question_tags` | 题目-标签 多对多 | 否 |
| 练习 | `practice_sessions` | 一次练习会话 | 否 |
| 练习 | `practice_session_questions` | 会话内题目快照与顺序 | 否 |
| 练习 | `practice_attempts` | 一次具体答题（可重复录音） | 否 |
| 录音 | `recordings` | 录音文件元数据与存储路径 | 是 |
| 用户 | `favorites` | 用户收藏题目 | 否 |
| 学习 | `study_records` | **每日统计聚合**（可重算，非事实来源） | 否 |
| 用户 | `user_activity_logs` | 原始行为日志（事实来源之一） | 否 |

> **MVP 不建 `permissions` 表。** 权限按角色级硬编码（见 §10），避免提前引入 RBAC。

### 4.2 实体关系

**用户侧：**

```text
User
 ├── Profile
 ├── UserGoal (一个用户可有历史/当前多个目标)
 ├── PracticeSession
 │      └── PracticeSessionQuestion
 │                  ├── Question        (题目快照引用)
 │                  └── PracticeAttempt (一题可多次尝试)
 │                              └── Recording
 ├── Favorite ── Question
 ├── StudyRecord          (每日聚合，可由原始记录重算)
 └── ActivityLog          (原始行为日志)
```

**题库侧：**

```text
Topic
 └── Question
        └── QuestionTag ── Tag
```

**练习侧（核心事实链）：**

```text
User
 └── PracticeSession
        └── PracticeSessionQuestion
                  ├── Question
                  └── PracticeAttempt
                             └── Recording
```

> 关键修正（v0.1 → v0.2）：
> 1. `PracticeAnswer` 改名为 `PracticeAttempt`，语义为"一次具体答题尝试"，支持同一题重复录音。
> 2. `Recording` 隶属于 `PracticeAttempt`，而非直接挂 `Question` 或 `Session`。
> 3. 事实链为：`Session → SessionQuestion → Attempt → Recording`。

### 4.3 关键字段约定（命名级，非完整 DDL）

- **主键**：除纯关联表（`question_tags`）外，所有实体表含 `id`（`BIGINT GENERATED ALWAYS AS IDENTITY` 主键）；纯关联表使用复合主键（如 `question_tags` 用 `(question_id, tag_id)`），不设独立 `id`，仅含 `created_at`。
- 所有实体表含：`created_at`、`updated_at`（`TIMESTAMPTZ`，`updated_at` 由触发器自动维护）。
- 软删除字段：`deleted_at`（可空），按 §4.1 表执行。
- 状态字段统一用字符串枚举（如 `status`、`mode`、`part`），用 `VARCHAR + CHECK` 而非 PG ENUM。
- 外键命名：`<目标表单数>_id`（如 `user_id`、`question_id`、`session_id`、`attempt_id`）。
- 时间字段统一 `TIMESTAMP WITH TIME ZONE`，应用层统一 UTC 存储、按用户时区展示。
- 题目来源字段：`source_type`（枚举，必填）+ `source_name`（**必填**文本，见 §12），两者均 `NOT NULL`。
- 用户时区：`user_profiles.timezone`（IANA 名称，默认 `Asia/Shanghai`），统计的"日/周/月/连续天数"均按该时区切分。

### 4.4 枚举值

- `roles.name`: `user` / `admin`
- `speaking_questions.part`: `1` / `2` / `3`
- `speaking_questions.status`: `draft` / `published` / `disabled`
- `speaking_questions.source_type`: `official` / `historical` / `mock` / `custom`
- `practice_sessions.mode`: `random` / `topic` / `part`
- `practice_sessions.status`: `created` / `in_progress` / `completed` / `abandoned` / `expired`
- `practice_attempts.status`: `pending` / `recording` / `submitted` / `skipped` / `failed`
- `recordings.status`: `uploading` / `uploaded` / `failed` / `deleted`
- `user_goals.status`: `active` / `achieved` / `archived`
- `favorites`：无 status，存在即收藏，删除即取消。

### 4.5 业务约束（DB + 应用层）

> 下列约束中，部分由数据库 CHECK/唯一索引保证，部分跨表约束由应用层（service）校验。

1. **`practice_attempts.attempt_number`**：同一 `session_question_id` 下从 1 递增，唯一约束 `(session_question_id, attempt_number)`，语义为"该会话题目的第几次尝试"。
2. **`user_goals` 当前目标唯一**：同一 `user_id` 同时最多一个 `status='active' AND deleted_at IS NULL` 的目标，由**部分唯一索引**保证。
3. **Attempt submitted 前置条件**（应用层校验）：`practice_attempts.status='submitted'` 必须满足该 attempt 存在一条 `recordings.status='uploaded'` 的录音。禁止出现"submitted 但录音 failed/缺失"。
4. **`study_records.duration_seconds` 口径**：= 该用户当日所有 `recordings.status='uploaded'` 的 `duration_seconds` 总和（按 `user_profiles.timezone` 切日）。不使用 session 持续时间，因其含思考/暂停时间且难精确。
5. **`practice_session_questions.question_snapshot`**：`JSONB`，必含字段 `part`、`title`、`content`、`cue_card`、`topic_name`、`difficulty`，保证题目被修改/禁用后历史会话仍可还原作答时内容。
6. **`speaking_questions.source_name`**：`NOT NULL`，与 `source_type` 同为必填（版权合规，见 §12）。
7. **题目不可物理删除**：`speaking_questions` 无 `deleted_at`，仅 `status='disabled'` 软停用，保证 `practice_session_questions.question_id` 引用完整性。
8. **`speaking_questions.topic_id`**：`NOT NULL`，所有题目必须归属主题；无明确主题归入种子主题 `Other`，保证按主题练习/统计/推荐可行。
9. **`recordings.duration_seconds`**：由后端读音频元数据计算，**不信前端传入**；前端 duration 仅作 UI 展示。
10. **`recordings.mime_type`**：MVP 不转码，存浏览器原始格式（webm/mp4 等）；后续 AI 评分需求再引入转码（非 MVP）。
11. **`study_records` 写入**：MVP 同步更新（录音上传事务内 upsert 当日行），架构抽象为统计服务，预留异步切换。
12. **`user_activity_logs` 保留**：在线 180 天，超期归档/删除（定时任务，阶段 11/12）；不承担审计职责，管理员操作另建 `audit_logs`（非 MVP）。
13. **`Other` 主题系统保留**：兜底主题 `Other`（database-design §9.2）为系统保留基础数据，不允许删除（含软删）、停用、重命名；`modules/admin` 主题删除/更新接口对此硬拒绝（错误码 `8001`），前端禁用该行操作按钮。

> 完整 DDL 在 [docs/database/database-design.md](file:///workspace/docs/database/database-design.md) 中展开，由 Alembic 迁移落地。

---

## 5. 页面流程

### 5.1 用户端核心闭环

```text
注册 → 登录 → 首页 → 题库 → 查看题目 → 开始练习
                                              ↓
                                       练习页面（准备 → 练习中 → 录音 → 下一题 → 完成）
                                              ↓
                                       录音上传 → 保存 Attempt
                                              ↓
                                       学习数据 → 继续下一次练习
```

### 5.2 用户端路由（MVP，全部在 user-web 内）

```text
/                # 首页
/login
/register
/questions       # 题库列表（搜索/筛选/分页/收藏）
/questions/:id   # 题目详情
/practice/new    # 选择练习参数
/practice/:id    # 练习会话页
/learning        # 学习数据
/profile         # 我的（含目标设置）
```

### 5.3 管理后台路由（MVP）

```text
/admin/login
/admin/dashboard
/admin/users
/admin/topics
/admin/tags
/admin/questions
/admin/questions/:id  # 编辑页
```

### 5.4 练习会话状态机（Session）

```text
created
   ↓ (开始第一题)
in_progress
   ↓ (全部完成 / 用户主动结束)
completed
   ↓ (用户放弃超时)
abandoned
   ↓ (长期未完成，后台清理)
expired
```

### 5.5 答题状态机（Attempt）

```text
pending
   ↓ (开始录音)
recording
   ↓ (提交录音)
submitted
   ↓ (用户跳过)
skipped
   ↓ (录音上传/处理失败)
failed
```

### 5.6 录音状态机（Recording）

```text
uploading
   ↓
uploaded
   ↓ (用户删除该次录音)
deleted
   ↓ (上传失败)
failed
```

> 不允许用单一 `isRecording` 布尔表达录音状态。前端需以状态机驱动 UI。

### 5.7 关键韧性场景

- 用户练习中关闭浏览器 → 重新打开可继续未完成会话（`practice_sessions.status = in_progress` 持久化，`practice_attempts` 持久化到 `pending`/`recording`）。
- 录音上传失败 → Attempt 可保持 `recording`/`failed`，允许重新录音（产生新 Attempt 或覆盖，由 §7 API 约定）。

---

## 6. API 路由规划（概览）

> 完整契约在 `docs/api/` 下逐模块展开，统一前缀 `/api/v1`。

```text
# 认证与用户
POST   /api/v1/auth/register
POST   /api/v1/auth/login
POST   /api/v1/auth/logout
GET    /api/v1/users/me
PUT    /api/v1/users/me
PUT    /api/v1/users/me/password

# 用户目标
GET    /api/v1/users/me/goals
POST   /api/v1/users/me/goals
PUT    /api/v1/users/me/goals/{id}

# 题库（用户端）
GET    /api/v1/questions
GET    /api/v1/questions/{id}
POST   /api/v1/questions/{id}/favorite
DELETE /api/v1/questions/{id}/favorite

# 练习
POST   /api/v1/practice/sessions                 # 创建练习
GET    /api/v1/practice/sessions/{id}            # 获取会话（含题目列表）
POST   /api/v1/practice/sessions/{id}/complete   # 完成会话

# 答题与录音（录音隶属于 Attempt）
POST   /api/v1/practice/attempts                 # 创建/获取某会话题目的 attempt
POST   /api/v1/practice/attempts/{attempt_id}/recording   # 上传录音
GET    /api/v1/practice/attempts/{attempt_id}/recording   # 获取录音
PATCH  /api/v1/practice/attempts/{attempt_id}    # 更新 attempt 状态（skip/submit）

# 学习数据
GET    /api/v1/learning/overview
GET    /api/v1/learning/daily
GET    /api/v1/learning/weekly
GET    /api/v1/learning/monthly
GET    /api/v1/learning/topics
GET    /api/v1/learning/history                  # 练习历史列表

# 首页
GET    /api/v1/home/overview

# 管理后台（前缀 /api/v1/admin）
# 用户管理 / 主题 CRUD / 标签 CRUD / 题目 CRUD（含启停）
```

### 6.1 统一约定

- 认证：JWT Bearer Token（access_token）。
- 密码：bcrypt。
- 响应：统一 `{ "code": 0, "message": "ok", "data": {...} }`（具体结构在 `docs/api/` 定义）。
- 分页：`page` / `page_size`，返回 `total` / `items`。
- 异常：统一错误码与错误信息结构。
- 时间：UTC 存储，ISO 8601 返回。
- **录音上传绑定 Attempt**：录音天然属于"某次具体答题"，避免顶层 `/recordings` 导致的归属歧义。

---

## 7. 数据一致性原则

1. `practice_sessions` 是练习会话的**事实来源**。
2. `practice_session_questions` 记录会话题目**快照与顺序**（题目被修改/禁用不影响历史会话）。
3. `practice_attempts` 记录用户**具体答题行为**，是录音的归属主体。
4. `recordings` 记录音频文件**元数据与存储路径**，与 attempt 一对一（MVP）或一对多（未来）。
5. `user_activity_logs` 记录**原始行为**（practice_started / attempt_submitted / recording_uploaded / favorite_added …）。
6. `study_records` 是**每日统计聚合**，可由原始练习记录重算，不是系统唯一事实来源。
7. 统计数据异常时，允许从 `practice_sessions` / `practice_attempts` / `recordings` 重新计算并覆盖 `study_records`。
8. 题目使用 `status` 软停用（`disabled`），不物理删除，保证历史会话引用完整性。
9. **跨表状态约束**（应用层）：`attempt.status='submitted'` ⇒ 存在 `recording.status='uploaded'`；`session.status='completed'` ⇒ 其所有 `session_question` 至少有一个 `submitted` 或 `skipped` 的 attempt。
10. **统计口径固定**：`study_records.duration_seconds` = 当日 uploaded 录音时长总和（见 §4.5.4），禁止用 session 时长冒充。

---

## 8. 软删除策略

> 模糊的"视情况"是 AI 协作的大敌。本节给出每张表的明确策略。

| 表 | 软删除 | 机制 | 理由 |
| --- | --- | --- | --- |
| `users` | 是 | `deleted_at` | 账号合规与历史数据保留 |
| `user_profiles` | 否 | — | 随 user 生命周期，不独立软删 |
| `user_goals` | 是 | `deleted_at` + `status` | 历史目标归档 |
| `roles` | 否 | — | 字典表，极少变更 |
| `speaking_topics` | 是 | `deleted_at` | 历史题目引用 |
| `tags` | 是 | `deleted_at` | 历史题目引用 |
| `speaking_questions` | 否 | `status=disabled` | 题目被历史会话引用，禁用而非删除 |
| `question_tags` | 否 | — | 关联表，随主体处理 |
| `practice_sessions` | 否 | `status` | 事实记录，不删 |
| `practice_session_questions` | 否 | — | 快照，不删 |
| `practice_attempts` | 否 | `status` | 事实记录，不删 |
| `recordings` | 是 | `deleted_at` + `status=deleted` | 文件可清理但元数据保留审计 |
| `favorites` | 否 | — | 存在即收藏，删除即取消 |
| `study_records` | 否 | — | 聚合数据，可重算覆盖 |
| `user_activity_logs` | 否 | — | 日志不删（可定期归档） |

---

## 9. 学习统计设计

### 9.1 事实来源 vs 聚合

- **事实来源**：`practice_sessions`、`practice_attempts`、`recordings`、`user_activity_logs`。
- **聚合缓存**：`study_records`（每日一行，按用户聚合）。

### 9.2 聚合字段（每日）

```text
user_id
date                     # 按 user_profiles.timezone 切日
practice_count           # 当日会话数
question_count           # 当日答题数
attempt_count            # 当日尝试数
duration_seconds         # 当日所有 uploaded 录音时长总和（口径见 §4.5.4）
recording_count          # 当日 uploaded 录音数
```

### 9.3 重算机制

- 提供内部脚本/接口从事实表重算某用户某日 `study_records`。
- 连续学习天数（streak）从 `study_records` 或 `practice_sessions` 动态计算。

---

## 10. 权限模型（MVP）

MVP 采用**角色级权限**，不实现 RBAC / `permissions` 表。

```text
user
├── 访问用户端
├── 管理自己的资料与目标
├── 练习、答题、录音
├── 收藏题目
└── 查看自己的学习数据

admin
├── 继承 user 全部权限
├── 访问管理后台
├── 管理用户（查看 / 禁用）
├── 管理题目（CRUD + 启停）
├── 管理标签
└── 管理主题
```

- 角色存储于 `users.role_id` → `roles`。
- `roles` 预置两行：`user`、`admin`。
- 后续若需细粒度权限，再引入 `permissions` 与 `role_permissions` 表（非 MVP）。

---

## 11. 推荐规则（MVP）

MVP **不做 AI 推荐**，使用确定性规则，保证可复现、可测试。优先级从高到低：

```text
1. 用户存在未完成会话（status in [created, in_progress]）
     → 推荐"继续练习"，跳转回该会话
2. 否则，用户最近练习过的主题
     → 推荐该主题下的 published 题目
3. 否则，用户收藏但未练习过的题目
     → 推荐收藏题目
4. 否则，用户较少练习的 Part
     → 推荐该 Part 题目
5. 否则，默认热门题目（按练习次数排序的 published 题目）
```

- 同级内取前 N 条（N 由前端决定，建议 5）。
- 规则在 `modules/home/service.py` 实现，不引入随机数，保证同一状态返回一致结果。

---

## 12. 内容版权与数据来源约束

> 题库内容存在版权风险，MVP 必须明确来源合法性。

### 12.1 允许的题目来源

| `source_type` | 含义 | 版权要求 |
| --- | --- | --- |
| `official` | 官方题目 | 仅录入公共领域或已获授权内容 |
| `historical` | 历史机经 | 仅录入用户回忆、公共整理内容，不复制商业题库 |
| `mock` | 模拟题 | 自编或合法授权 |
| `custom` | 用户自定义 | 用户自创内容 |

### 12.2 红线

- **禁止**抓取、复制未经授权的商业题库（如付费机构的真题库）到本产品。
- 录入题目时必须填写 `source_type` 与 `source_name`（来源说明）。
- 用户自定义内容（`custom`）由用户负责，平台不背书版权。
- 后台题目编辑页需提示版权声明。

### 12.3 字段

- `speaking_questions.source_type`：枚举（见 §4.4），`NOT NULL`。
- `speaking_questions.source_name`：`NOT NULL` 文本，来源说明/出处（如 `custom` 时填"用户自定义"）。

---

## 13. MVP 验收标准

MVP 视为完成，当且仅当以下全部可在部署环境（Docker Compose）中端到端跑通：

### 13.1 用户系统

- [ ] 可注册新账号（邮箱 + 密码）。
- [ ] 可登录并获取 access_token。
- [ ] 可获取与修改当前用户资料。
- [ ] 可修改密码。
- [ ] 密码以 bcrypt 哈希存储，明文不可逆。
- [ ] 可设置/修改学习目标（user_goals）。

### 13.2 题库系统

- [ ] 题库列表支持 Part / 主题 / 标签筛选 + 关键词搜索 + 分页。
- [ ] 题目详情页可查看完整内容。
- [ ] 可收藏 / 取消收藏题目。
- [ ] 仅返回 `published` 状态题目给用户端。
- [ ] 题目录入含 `source_type` / `source_name`。

### 13.3 练习系统

- [ ] 可按 mode/part/topic/question_count 创建练习会话。
- [ ] 练习页面按顺序展示题目。
- [ ] 练习中关闭浏览器后，重新打开可继续未完成会话。
- [ ] 可完成会话，attempt 写入 `practice_attempts`。

### 13.4 录音系统

- [ ] 浏览器可请求麦克风权限并录音。
- [ ] 录音/会话/答题状态机按 §5 转换，UI 反馈正确。
- [ ] 录音 Blob 上传至 `/practice/attempts/{id}/recording` 并持久化（开发环境落本地文件系统）。
- [ ] 录音元数据写入 `recordings` 表，与 attempt 关联。

### 13.5 学习数据

- [ ] 总览页展示：总练习次数、总题数、总时长、连续学习天数、今日/本周/本月练习。
- [ ] 趋势图（日/周/月）可正常渲染。
- [ ] Part 分布、主题分布可正常渲染。
- [ ] 练习历史列表可查看。
- [ ] `study_records` 可从事实表重算。

### 13.6 管理后台

- [ ] 管理员账号可登录后台。
- [ ] 主题 / 标签 / 题目均支持增删改查。
- [ ] 题目支持启用 / 禁用（`published` ⇄ `disabled`）。
- [ ] 用户管理可查看与禁用用户。

### 13.7 首页

- [ ] 展示今日统计、连续学习天数、最近练习、按 §11 规则推荐内容。
- [ ] "继续练习"可跳转回未完成会话。

### 13.8 工程与部署

- [ ] Docker Compose 一键启动：user-web / admin-web / backend / postgres。
- [ ] Alembic 迁移可从零建库。
- [ ] 后端关键路径有单元/集成测试（注册、登录、题目 CRUD、练习创建、录音上传、统计）。
- [ ] 前端关键流程可手动走通（登录、筛选、开始练习、录音、完成）。
- [ ] README 含启动说明。

---

## 14. 开发阶段划分（概览）

| 阶段 | 目标 |
| --- | --- |
| 0 | 项目规划（本文档 + AI_CONTEXT + database-design + system-architecture） |
| 1 | 开发环境（前后端 + DB 可启动，Docker Compose） |
| 2 | 数据库设计落地（Alembic 建表） |
| 3 | 后端基础架构（领域模块骨架 + 统一响应/异常） |
| 4 | 用户系统（含 user_goals） |
| 5 | 管理后台 |
| 6 | 题库系统 |
| 7 | 练习系统（session → attempt） |
| 8 | 录音系统（绑定 attempt） |
| 9 | 学习数据（含 study_records 重算） |
| 10 | 首页（含推荐规则） |
| 11 | 测试 |
| 12 | 部署 |
| 13 | AI 增强（非 MVP） |

> 节奏建议：每周交付一个可运行版本，不把"8 周完成"当硬性目标。

---

## 15. AI 协作约束

- 不一次性生成整个项目；按"需求 → 设计 → 拆分任务 → AI 实现 → 审查 → 测试 → 提交"进行。
- 每次只给 AI 一个功能 / 一个模块 / 一个问题。
- AI 负责代码、测试、文档、Debug、重复劳动；人负责产品目标、架构、数据模型、边界、验收标准。
- 任何模块改动前，先确认是否在"禁止修改模块"清单内（见 `AI_CONTEXT.md`）。
- 后端修改默认限定在单个 `modules/<domain>` 内，跨模块改动需显式授权。

---

## 16. 变更记录

| 版本 | 日期 | 变更 | 负责人 |
| --- | --- | --- | --- |
| v0.1 | 2026-07-23 | 初始创建，固定 MVP 范围与技术栈 | — |
| v0.2 | 2026-07-23 | 架构级修订：①前端合并为 user-web+admin-web；②`practice_answers`→`practice_attempts`；③明确 Session→SessionQuestion→Attempt→Recording 事实链；④新增 `user_goals`；⑤明确推荐规则；⑥录音 API 绑定 attempt；⑦明确 `study_records` 为聚合可重算；⑧软删除逐表明确；⑨MVP 删除 `permissions` 表；⑩后端改领域模块结构；⑪新增数据一致性原则；⑫新增内容版权与来源约束；补充状态机异常状态 | — |
| v0.3 | 2026-07-23 | 规格一致性修订：①`source_name` 改 `NOT NULL`（修复与 §12 冲突）；②明确关联表 `question_tags` 用复合主键、不设独立 id；③主键改 `BIGINT GENERATED ALWAYS AS IDENTITY`；④新增 §4.5 业务约束（attempt_number 语义、active goal 部分唯一索引、Attempt submitted 前置条件、duration 口径、快照必含字段、题目不可物理删除）；⑤补充 `user_profiles.timezone` 与统计切日规则；⑥明确 `question_snapshot` 必含字段；⑦数据一致性原则补充跨表状态约束与统计口径 | — |
| v0.4 | 2026-07-23 | 5 个行为规则决策落地 §4.5：①`topic_id` NOT NULL + Other 兜底主题；②`recordings.duration_seconds` 后端读元数据计算；③`mime_type` MVP 不转码；④`study_records` 同步更新预留异步；⑤`user_activity_logs` 保留 180 天 + 审计另建表(非MVP)。数据库开放问题全部清零 | — |
| v0.5 | 2026-07-23 | §4.5 新增第 13 条：`Other` 主题系统保留（不可删/不可停用/不可重命名，admin 接口硬拒绝错误码 8001，前端禁用按钮）；同步修复 database-design §9 编号顺序 | — |

---

## 17. 下一步（修订后顺序）

```text
1. PROJECT_SPEC.md (v0.2)            ✅ 本次完成
2. AI_CONTEXT.md                      ← 紧接
3. docs/database/database-design.md   ← 重点
4. docs/architecture/system-architecture.md
5. docs/api/                          (各模块契约)
6. docs/product/user-flow.md          (Mermaid)
7. docs/development-plan.md           (任务拆分与排期)
8. 初始化代码（阶段 1）
```

> **数据库与系统架构必须先于 API。** API 依赖数据模型，数据模型依赖系统架构。
> 在 2–4 完成前，不进入阶段 1 的代码初始化。

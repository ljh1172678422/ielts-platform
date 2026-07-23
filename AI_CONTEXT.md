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

**Phase 2 — 数据库阶段（已完成）** → 进入 **Phase 3 — 后端基础架构**

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
  - 2.2-2.5 15 表迁移 (拓扑序 001→015, 1:1 对齐 database-design v0.4 DDL:
         字段类型/NOT NULL/DEFAULT/PK/UNIQUE/CHECK/FK ON DELETE/索引 全部对齐)
  - 2.6 种子数据 (迁移 017: roles(user/admin) + Other 主题, ON CONFLICT 幂等;
         scripts/seed_admin.py: bcrypt cost≥12, 生产密码强度校验, 幂等跳过)
  - 2.7 updated_at 触发器 (迁移 016: set_updated_at() 函数 + 11 表 BEFORE UPDATE 触发器)
  ⚠ 实际 `alembic upgrade head` 需本地 PostgreSQL（沙箱无 PG, 已用 offline --sql 验证全部 DDL/索引/触发器/种子语法正确）
[待办]   阶段 3：后端基础架构（安全层/依赖注入/响应中间件/模块骨架）
```

---

## 3. 当前任务

- **Phase 2 数据库阶段已全部完成**（任务 2.1–2.7）。
- **下一步**：阶段 3 后端基础架构（安全层 / 依赖注入 / 响应中间件 / 模块骨架）。
- **当前状态**：DB schema 已锁定（15 表 + 索引 + 触发器 + 种子迁移就绪），按 development-plan.md §5 执行任务 3.1–3.7。其中 3.1/3.2/3.4 在 Phase 1 已建骨架，Phase 3 重点为 3.3 安全层（security.py JWT/bcrypt）、3.5 依赖注入（get_current_user/require_admin）、3.6 响应中间件、3.7 模块骨架。

### 3.1 当前任务边界（阶段 3 生效）

**阶段 3 允许：**
- 按 development-plan.md §5 顺序执行任务 3.1–3.7。
- 实现 `app/core/security.py`：JWT HS256 签发/校验（auth.md §5，24h，无 refresh）+ bcrypt 哈希/校验（cost≥12，common.md §6）。
- 实现 `app/core/dependencies.py`：`get_current_user` / `require_admin` 依赖注入（解析 Bearer token → 查 users → 校验 role/status）。
- 实现 `app/core/response.py`（或中间件）：统一响应信封包装（common.md §2，success code=0 data 恒在；error data=null details 仅非空时出现）。
- 建立 `app/modules/{auth,users,questions,practice,learning,home,admin}/` 骨架（router 占位，system-architecture §3 分层）。
- 一次只执行一个任务，完成即 commit + 更新 AI_CONTEXT。

**禁止（阶段 3 仍生效）：**
- ❌ 修改已锁定文档（PROJECT_SPEC / database-design / system-architecture / 全部 API 文档 / user-flow / development-plan）。
- ❌ 改变 DB schema（阶段 2 已锁定 15 表 + 约束 + 索引；如需变更先走修改规则）。
- ❌ 偏离 system-architecture §3 分层（router→service→repository，session 注入 repository）。
- ❌ 实现具体业务逻辑（注册/登录/题库 CRUD 等属阶段 4+，本阶段仅骨架 + 基础设施）。
- ❌ 改变统一响应结构 `{code,message,data,details?}`。
- ❌ 改变状态机或核心事实链。
- ❌ 一次性生成整个项目（PROJECT_SPEC §开发原则）。

> 阶段 2 → 阶段 3 转换已由用户连续执行模式授权覆盖，无需再次确认。

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

**后端骨架关键文件**：
- `backend/app/main.py` — create_app() 工厂 + /health
- `backend/app/core/config.py` — pydantic-settings 配置
- `backend/app/core/database.py` — async engine + session factory
- `backend/app/core/exceptions.py` — 统一信封 + AppError + 422 改写（对齐 common.md v0.2）
- `backend/app/core/security.py` — 占位（Phase 4 实现 JWT/bcrypt）
- `backend/tests/test_health.py` — health 端点测试

**前端共享包关键约定（对齐 common.md v0.2）**：
- `@ielts/types`：ResponseEnvelope / ErrorEnvelope / PaginatedData / ID(string) / 各状态枚举
- `@ielts/api-client`：createApiClient() 工厂 + 请求拦截器(token) + 响应拦截器(信封解包) + ApiClientError
- user-web 已迁移复用 `@ielts/types`（消除本地 ApiResponse 重复定义）

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

# IELTS Speaking Web App

雅思口语练习 Web 应用 MVP。管理员录入题目 → 用户注册登录 → 浏览题库 → 口语训练 → 录音 → 保存训练记录 → 查看学习数据。

## 技术栈

- **前端**：Vue 3 + TypeScript + Vite + Element Plus + Tailwind CSS + ECharts
- **后端**：FastAPI + SQLAlchemy 2.x (async) + Pydantic 2.x + Alembic + PostgreSQL
- **Monorepo**：pnpm workspace（apps/* + packages/*）+ uv（后端依赖）
- **部署**：Docker Compose

## 项目结构

```text
.
├── apps/
│   ├── user-web/        # 用户端 SPA（端口 5173）
│   └── admin-web/       # 管理后台 SPA（端口 5174）
├── packages/
│   ├── types/           # 共享 TS 类型（协议层 + 实体视图）
│   ├── api-client/      # axios 封装 + 统一信封解包
│   ├── ui/              # 跨端复用组件
│   └── utils/           # 工具函数（时间/duration 格式化等）
├── backend/             # FastAPI 后端（端口 8000）
├── docs/                # 设计文档（规格/架构/数据库/API/开发计划）
├── docker-compose.yml   # 开发环境编排
└── package.json         # Monorepo 根
```

## 快速开始

### 前置要求

- Node.js ≥ 22 + pnpm ≥ 10
- Python ≥ 3.12 + uv ≥ 0.11
- Docker + Docker Compose（可选，用于容器化启动）

### 方式一：Docker Compose（推荐，一键启动全栈）

```bash
docker compose up -d
```

启动后：

- 用户端：http://localhost:5173
- 管理后台：http://localhost:5174
- 后端 API：http://localhost:8000/health
- PostgreSQL：localhost:5432（ielts / ielts）

### 方式二：本地开发（热重载）

```bash
# 后端
cd backend
cp .env.example .env          # 按需修改 DATABASE_URL
uv sync --extra dev
uv run uvicorn app.main:app --reload --port 8000

# 前端（另开终端）
pnpm install
pnpm dev:user-web             # http://localhost:5173
pnpm dev:admin-web            # http://localhost:5174
```

前端 dev server 已配置 `/api` 代理到 `http://localhost:8000`。

### 常用脚本

```bash
pnpm build              # 构建所有 apps
pnpm type-check         # 全仓类型检查
pnpm test               # 运行测试
cd backend && uv run pytest   # 后端测试
```

## Git 分支策略

采用 `main / develop + feature/*` 双主干模型，对齐 development-plan.md 的任务粒度提交约定。

### 分支模型

| 分支 | 用途 | 保护 | 来源 |
| --- | --- | --- | --- |
| `main` | 生产发布分支，保持随时可部署状态 | 保护分支，仅接受 PR 合并，禁止直推 | 由 `develop` 合入 |
| `develop` | 开发集成分支，反映最新开发进度 | 常规保护，PR 合并 | 由 `feature/*` 合入 |
| `feature/<task-id>-<short-desc>` | 功能分支，一个任务一个分支 | 无 | 从 `develop` 切出 |

### 工作流

```text
1. git checkout develop && git pull
2. git checkout -b feature/2.1-alembic-init    # 按 development-plan 任务编号命名
3. ...开发 + 提交...
4. git push -u origin feature/2.1-alembic-init
5. 发起 PR：feature/* → develop
6. Review 通过后合并，删除功能分支
7. develop 验收稳定后，PR：develop → main（发布）
```

### 分支命名约定

```text
feature/<阶段>.<任务号>-<简短描述>   # 新功能，如 feature/4.1-auth-register
fix/<任务号>-<简短描述>              # bug 修复，如 fix/5.2-dashboard-count
docs/<主题>                         # 文档，如 docs/api-learning
chore/<主题>                        # 构建/依赖/配置，如 chore/docker-setup
```

### 提交信息约定（Conventional Commits）

```text
<type>(<scope>): <subject>

type  ∈ feat | fix | docs | style | refactor | test | chore
scope ∈ 模块名（auth | users | questions | practice | recording | learning | admin | home | infra | db）
```

示例：

```text
feat(auth): 实现 POST /auth/register 注册接口
fix(recording): 修复上传事务回滚时 recording 状态未重置
docs(api): 新增 learning.md 学习数据接口契约
chore(docker): 初始化四服务 Docker Compose 编排
```

### 任务与提交粒度

- **一个任务一个分支**：对齐 development-plan.md 任务编号（如 `feature/4.1-auth-register`）。
- **一个任务一次提交**：任务完成后提交，提交信息含任务编号，便于追溯。
- **提交后更新 AI_CONTEXT.md**：记录当前状态与下一步，再开始下一任务。

## 文档导航

- [PROJECT_SPEC.md](./PROJECT_SPEC.md) — 项目规格宪法
- [AI_CONTEXT.md](./AI_CONTEXT.md) — AI 协作控制面（当前状态/任务边界/ADR 索引）
- [docs/development-plan.md](./docs/development-plan.md) — 13 阶段开发计划
- [docs/architecture/system-architecture.md](./docs/architecture/system-architecture.md) — 系统架构
- [docs/database/database-design.md](./docs/database/database-design.md) — 数据库设计（15 表 DDL）
- [docs/api/](./docs/api/) — API 契约（common/auth/users/questions/practice/learning/home/admin）

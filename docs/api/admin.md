# API 契约 — 管理后台模块（admin.md）

> 本文定义管理后台接口契约：Dashboard、用户管理、主题/标签/题目 CRUD。
> **严格遵守 [common.md](file:///workspace/docs/api/common.md) v0.1**。
> 对应规格：`PROJECT_SPEC.md` v0.5 §6 / §12.3（Other 主题保护）/ `database-design.md` v0.4 §3.1/§3.2。

---

## 0. 文档定位

本文回答："管理员能调哪些接口、CRUD 字段、Other 主题保护、题目状态切换。"
不回答："管理员怎么登录。" → 复用 [auth.md](file:///workspace/docs/api/auth.md) `POST /auth/login`（role=admin 即可，前端按 role 跳后台路由）。
不回答："统一响应/分页。" → [common.md](file:///workspace/docs/api/common.md)。

---

## 1. 模块概述

### 1.1 鉴权约定

- **所有 /admin/* 接口需 Bearer token 且 `role='admin'`**，否则 2003。
- 管理员登录复用 `POST /api/v1/auth/login`（auth.md §3），不单独建 `/admin/login` API。前端 admin-web 路由独立，登录成功后按 `user.role` 跳转。
- 管理员身份确认：`GET /admin/dashboard` 隐式校验 role（任何 admin 接口调用即确认）。

### 1.2 路由表

| Method | Path | 说明 |
| --- | --- | --- |
| GET | `/api/v1/admin/dashboard` | 全局统计概览 |
| GET | `/api/v1/admin/users` | 用户列表（分页+筛选） |
| PUT | `/api/v1/admin/users/{id}/status` | 启用/禁用用户 |
| GET | `/api/v1/admin/topics` | 主题列表 |
| POST | `/api/v1/admin/topics` | 创建主题 |
| PUT | `/api/v1/admin/topics/{id}` | 更新主题 |
| DELETE | `/api/v1/admin/topics/{id}` | 删除主题（软删） |
| GET | `/api/v1/admin/tags` | 标签列表 |
| POST | `/api/v1/admin/tags` | 创建标签 |
| PUT | `/api/v1/admin/tags/{id}` | 更新标签 |
| DELETE | `/api/v1/admin/tags/{id}` | 删除标签（软删） |
| GET | `/api/v1/admin/questions` | 题目列表（含 draft/disabled） |
| POST | `/api/v1/admin/questions` | 创建题目 |
| GET | `/api/v1/admin/questions/{id}` | 题目详情（含 draft/disabled） |
| PUT | `/api/v1/admin/questions/{id}` | 更新题目 |
| PUT | `/api/v1/admin/questions/{id}/status` | 切换题目状态（published/draft/disabled） |

> 题目不提供 DELETE 接口（ADR-010，仅 status=disabled，不可物理删除，因历史练习引用）。

### 1.3 涉及数据表

| 表 | 用途 |
| --- | --- |
| `users` / `user_profiles` | 用户管理 |
| `speaking_topics` | 主题 CRUD |
| `tags` | 标签 CRUD |
| `speaking_questions` / `question_tags` | 题目 CRUD |
| `practice_sessions` / `practice_attempts` / `recordings` | Dashboard 统计 |

### 1.4 核心约束

- **Other 主题保护（PROJECT_SPEC §12.3）**：`Other` 主题不可删/不可停用/不可重命名，违反 → 8001。
- **题目不可物理删除（ADR-010）**：仅 status=disabled，保留历史引用。
- **管理员可见 draft/disabled 题目**：与用户端 questions.md 不同，admin 列表/详情返回全部状态。

---

## 2. GET /api/v1/admin/dashboard

### 2.1 请求

```
GET /api/v1/admin/dashboard
Authorization: Bearer <admin_token>
```

### 2.2 响应（成功）

HTTP 200：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "users": {
      "total": 1256,
      "active_today": 84,
      "new_this_week": 32
    },
    "questions": {
      "total": 480,
      "published": 450,
      "draft": 20,
      "disabled": 10
    },
    "practice": {
      "total_sessions": 8920,
      "total_attempts": 42100,
      "total_recordings": 39800,
      "total_duration_seconds": 3120000
    },
    "topics": { "total": 24 },
    "tags": { "total": 68 }
  }
}
```

### 2.3 错误码

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 2001/2002/2004/2005 | 401/403/401 | 认证失败 |
| 2003 | 403 | 非管理员 |

### 2.4 后端处理

1. 校验 role='admin'。
2. 各表 COUNT 聚合（MVP 接受多次 COUNT 查询，数据量小）。
3. `active_today`：今日有 study_record 的用户数（按 UTC 统计，admin 视角不按用户 timezone）。
4. `new_this_week`：本周（ISO 周，UTC）注册用户数。

---

## 3. 用户管理

### 3.1 GET /api/v1/admin/users

```
GET /api/v1/admin/users?page=1&page_size=20&keyword=alice&status=active&role=user
Authorization: Bearer <admin_token>
```

**Query：**

| 参数 | 类型 | 默认 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `page` / `page_size` | int | 1/20 | 同 common.md | 分页 |
| `keyword` | string | 不传 | 长度 1..100 | 搜索 email 或 nickname（ILIKE） |
| `status` | string | 不传 | `active` / `disabled` | 状态筛选 |
| `role` | string | 不传 | `user` / `admin` | 角色筛选 |

**响应：**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [
      {
        "id": "1001",
        "email": "alice@example.com",
        "role": "user",
        "status": "active",
        "nickname": "Alice",
        "last_login_at": "2026-07-23T11:00:00+00:00",
        "created_at": "2026-07-01T10:00:00+00:00"
      }
    ],
    "total": 1256,
    "page": 1,
    "page_size": 20,
    "total_pages": 63
  }
}
```

> 列表含 `deleted_at IS NULL` 用户（软删用户不在列表，但邮箱占用检查时需考虑，见 auth.md §2.4）。
> **不返回** password_hash / timezone / avatar_url（列表精简）。

### 3.2 PUT /api/v1/admin/users/{id}/status

```
PUT /api/v1/admin/users/{id}/status
Authorization: Bearer <admin_token>
Content-Type: application/json
```

**Body：**

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `status` | string | 是 | `active` / `disabled` |

**响应：** 返回更新后的用户摘要（同 §3.1 列表项结构）。

**错误码：**

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 1001 | 422 | status 非法值 |
| 1002 | 404 | 用户不存在（通用 404，message 指明"用户"） |
| 8006 | 400 | 试图禁用自己（当前管理员账号） |
| 8007 | 400 | 试图禁用其他管理员（MVP 不允许管理员互相操作，仅可操作 user 角色） |

**后端处理：**
1. 校验 target 用户存在 → 否 → 1002。
2. `target.id == current.id` → 8006（防自锁）。
3. `target.role == 'admin'` → 8007（防管理员互操作）。
4. UPDATE users.status，INSERT activity_log(action='user_status_changed', metadata={old, new})。

> **不提供修改用户 role 的接口**：MVP 角色固定，不通过 API 提权（安全考虑，需直接改 DB）。
> **不提供删除用户接口**：用户软删由用户自己操作（未来 users 模块，MVP 暂不提供用户注销 API）。

---

## 4. 主题 CRUD

### 4.1 GET /api/v1/admin/topics

```
GET /api/v1/admin/topics?keyword=tech
Authorization: Bearer <admin_token>
```

**Query：**

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `keyword` | string | 不传 | 搜索 name |

**响应（非分页，主题数量少）：**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [
      {
        "id": "5",
        "name": "Technology",
        "slug": "technology",
        "description": "Tech-related topics",
        "question_count": 42,
        "is_system": false,
        "created_at": "2026-07-01T10:00:00+00:00"
      },
      {
        "id": "1",
        "name": "Other",
        "slug": "other",
        "description": "System reserved topic",
        "question_count": 8,
        "is_system": true,
        "created_at": "2026-07-01T10:00:00+00:00"
      }
    ]
  }
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `is_system` | bool | 系统保留主题（Other），前端据此禁用编辑/删除按钮 |
| `question_count` | int | 该主题下 published 题目数 |

### 4.2 POST /api/v1/admin/topics

**Body：**

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `name` | string | 是 | 长度 1..50，唯一 |
| `slug` | string | 否 | 长度 1..50，唯一；不传则由 name 生成 |
| `description` | string | 否 | 长度 ≤ 200 |

**响应：** 返回新建主题（同 §4.1 列表项，is_system=false）。

**错误码：**

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 1001 | 422 | 字段校验失败 |
| 1004 | 409 | name 或 slug 已存在（资源冲突） |

### 4.3 PUT /api/v1/admin/topics/{id}

**Body：** 同 §4.2（全量替换）。

**错误码：**

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 1001 | 422 | 字段校验失败 |
| 4003 | 404 | 主题不存在 |
| 1004 | 409 | name/slug 与其他主题冲突 |
| 8001 | 400 | Other 主题（is_system=true）不可修改 name/slug（PROJECT_SPEC §12.3） |

> Other 主题仅允许修改 `description`，name/slug 修改返回 8001。

### 4.4 DELETE /api/v1/admin/topics/{id}

软删主题。

**错误码：**

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 4003 | 404 | 主题不存在 |
| 8001 | 400 | Other 主题不可删除（PROJECT_SPEC §12.3） |
| 8002 | 400 | 主题下仍有 published 题目（资源被引用，需先迁移或禁用题目） |

**后端处理：**
1. 校验存在 → 4003。
2. `is_system=true` → 8001。
3. 查 question_count > 0 → 8002（防悬挂引用）。
4. UPDATE topics SET deleted_at=NOW()。

---

## 5. 标签 CRUD

结构与主题类似，无系统保留标签。

### 5.1 GET /api/v1/admin/tags

```
GET /api/v1/admin/tags?keyword=gadget
Authorization: Bearer <admin_token>
```

**响应（非分页）：**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [
      {
        "id": "12",
        "name": "gadget",
        "slug": "gadget",
        "question_count": 15,
        "created_at": "2026-07-01T10:00:00+00:00"
      }
    ]
  }
}
```

### 5.2 POST /api/v1/admin/tags

**Body：**

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `name` | string | 是 | 长度 1..30，唯一 |
| `slug` | string | 否 | 长度 1..30，唯一 |

**错误码：** 1001 / 1004（name/slug 冲突，资源冲突）。

### 5.3 PUT /api/v1/admin/tags/{id}

**Body：** 同 §5.2。

**错误码：** 1001 / 4004（标签不存在）/ 1004（name/slug 冲突）。

### 5.4 DELETE /api/v1/admin/tags/{id}

软删。

**错误码：**

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 4004 | 404 | 标签不存在 |
| 8002 | 400 | 标签仍被题目引用（资源被引用，question_tags 存在记录） |

> 与主题不同，标签删除前需先解除题目关联（管理后台题目编辑页移除标签）。返回 8002 提示前端引导。

---

## 6. 题目 CRUD

### 6.1 GET /api/v1/admin/questions

```
GET /api/v1/admin/questions?page=1&page_size=20&part=2&topic_id=5&status=published&keyword=describe
Authorization: Bearer <admin_token>
```

**Query（比用户端多 status 筛选）：**

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `page` / `page_size` | int | 1/20 | 分页 |
| `part` | int | 不传 | 1/2/3 |
| `topic_id` | string | 不传 | 主题筛选 |
| `status` | string | 不传 | `draft` / `published` / `disabled` |
| `keyword` | string | 不传 | 搜索 title + content |
| `tag_id` | string | 不传 | 标签筛选 |
| `difficulty` | int | 不传 | 1..5 |

**响应：**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [
      {
        "id": "101",
        "part": 2,
        "title": "Describe a useful object",
        "topic": { "id": "5", "name": "Technology" },
        "tags": [{ "id": "12", "name": "gadget" }],
        "difficulty": 3,
        "status": "published",
        "source_type": "custom",
        "source_name": "自编练习题",
        "practice_count": 42,
        "created_by": "1001",
        "created_at": "2026-07-01T10:00:00+00:00",
        "updated_at": "2026-07-15T14:00:00+00:00"
      }
    ],
    "total": 480,
    "page": 1,
    "page_size": 20,
    "total_pages": 24
  }
}
```

> **与用户端列表差异**：含 `status` / `tags` / `source_*` / `created_by` / `updated_at`（管理员需看见全部信息）。

### 6.2 POST /api/v1/admin/questions

**Body：**

| 字段 | 类型 | 必填 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `part` | int | 是 | 1/2/3 | Part |
| `title` | string | 是 | 长度 1..200 | 标题 |
| `content` | string | 是 | 长度 1..5000 | 题目正文 |
| `cue_card` | string | 否 | 长度 ≤ 2000 | Cue Card |
| `topic_id` | string | 是 | 存在 | 主题（ADR-019，必填） |
| `tag_ids` | string[] | 否 | 数组，每项存在 | 标签 ID 列表 |
| `difficulty` | int | 否 | 1..5 | 难度 |
| `source_type` | string | 是 | official/historical/mock/custom | 来源类型 |
| `source_name` | string | 是 | 长度 1..255 | 来源名称（ADR-011，必填） |
| `status` | string | 否 | draft/published | 默认 draft |

**响应：** 返回新建题目详情（同 §6.3）。

**错误码：**

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 1001 | 422 | 字段校验失败 |
| 4003 | 404 | topic_id 不存在 |
| 4004 | 404 | tag_ids 中某 id 不存在 |

> `created_by` 自动填当前管理员 id，不接受前端传入。

### 6.3 GET /api/v1/admin/questions/{id}

**响应：** 完整题目详情（含全部字段，比用户端 questions.md §3.2 多 status/created_by/updated_at/tags）。

**错误码：**

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 4001 | 404 | 题目不存在 |

> 管理员可见 draft/disabled，不返回 4002。

### 6.4 PUT /api/v1/admin/questions/{id}

**Body：** 同 §6.2（全量替换，status 也可在此改，或走 §6.5 专用接口）。

**后端处理：**
1. 更新 speaking_questions 全字段。
2. 若 tag_ids 变化：DELETE 旧 question_tags + INSERT 新（事务内）。
3. UPDATE updated_at。
4. INSERT activity_log(action='question_updated')。

**错误码：** 1001 / 4001 / 4003（topic_id）/ 4004（tag_id）。

> **更新不影响历史 session_questions.snapshot**（ADR-016 快照不可变），仅影响未来新建 session。

### 6.5 PUT /api/v1/admin/questions/{id}/status

**Body：**

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `status` | string | 是 | `draft` / `published` / `disabled` |

**错误码：**

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 1001 | 422 | status 非法值 |
| 4001 | 404 | 题目不存在 |

**状态转换规则：**

```text
draft → published     ✅ 上架
published → draft     ✅ 下架回草稿
published → disabled  ✅ 停用
disabled → published  ✅ 重新启用
disabled → draft      ✅
其他                   ✅ 灵活（MVP 不限制转换，管理员全权）
```

> MVP 不限制状态转换方向（管理员可信操作），仅记录 activity_log。
> 用户端 questions.md 仅见 published（ADR-010），disabled 对用户返回 4002，draft 返回 4001。

---

## 7. 安全与约束汇总

### 7.1 鉴权

- 所有 /admin/* 需 admin 角色（2003）。
- 不提供 role 修改接口（防提权，MVP 角色固定）。

### 7.2 Other 主题保护（PROJECT_SPEC §12.3）

| 操作 | Other 主题 |
| --- | --- |
| DELETE | ❌ 8001 |
| PUT name/slug | ❌ 8001 |
| PUT description | ✅ 允许 |
| 题目引用 | ✅ 允许（兜底主题） |

### 7.3 题目不可物理删除

- 仅 status=disabled（ADR-010），无 DELETE 接口。
- 历史练习引用快照，不受题目状态影响。

### 7.4 软删引用检查

- 主题删除前检查 question_count（8002，资源被引用）。
- 标签删除前检查 question_tags 引用（8002，资源被引用）。

### 7.5 活动日志

- 记录：`user_status_changed` / `topic_created/updated/deleted` / `tag_created/updated/deleted` / `question_created/updated/status_changed`。
- recompute 记录见 learning.md §9.5。

---

## 8. DTO 速查

### 8.1 请求 DTO

```text
UpdateUserStatusRequest:
  status: str  # active/disabled

CreateTopicRequest / UpdateTopicRequest:
  name: str (max_length=50)
  slug: str | None (max_length=50)
  description: str | None (max_length=200)

CreateTagRequest / UpdateTagRequest:
  name: str (max_length=30)
  slug: str | None (max_length=30)

CreateQuestionRequest / UpdateQuestionRequest:
  part: int  # 1/2/3
  title: str (max_length=200)
  content: str (max_length=5000)
  cue_card: str | None (max_length=2000)
  topic_id: str
  tag_ids: str[]
  difficulty: int | None  # 1..5
  source_type: str  # official/historical/mock/custom
  source_name: str (max_length=255)
  status: str  # draft/published (create); draft/published/disabled (update)

UpdateQuestionStatusRequest:
  status: str  # draft/published/disabled
```

### 8.2 响应 DTO

```text
AdminUserListItem:
  id: str
  email: str
  role: str
  status: str
  nickname: str | None
  last_login_at: str | None
  created_at: str

AdminTopicItem:
  id: str
  name: str
  slug: str
  description: str | None
  question_count: int
  is_system: bool
  created_at: str

AdminTagItem:
  id: str
  name: str
  slug: str
  question_count: int
  created_at: str

AdminQuestionListItem:
  id: str
  part: int
  title: str
  topic: TopicRef
  tags: TagRef[]
  difficulty: int | None
  status: str
  source_type: str
  source_name: str
  practice_count: int
  created_by: str
  created_at: str
  updated_at: str

AdminQuestionDetail:               # extends AdminQuestionListItem
  content: str
  cue_card: str | None
```

---

## 9. 与其他模块的衔接

| 衔接点 | 说明 |
| --- | --- |
| `auth.md` §3 | 管理员登录复用 /auth/login |
| `questions.md` | 用户端仅见 published，admin 可见全部 |
| `learning.md` §8 | recompute 接口同属 admin 角色 |
| `common.md` §3.2 | 错误码 8001/8002/8006/8007 |
| `database-design.md` §3.2 | 题库域表 + Other 主题种子 |

---

## 10. ADR 引用

| ADR | 内容 | 本文位置 |
| --- | --- | --- |
| ADR-009 | 角色级权限（admin） | §1.1 / §7.1 |
| ADR-010 | 题目软停用，不可物理删除 | §1.4 / §6 / §7.3 |
| ADR-011 | source_type/source_name 必填 | §6.2 |
| ADR-019 | topic_id NOT NULL | §6.2 |
| ADR-023 | 活动日志精简 | §7.5 |
| ADR-025 | id 序列化为字符串 | 全文 |
| ADR-026 | snake_case | 全文 |
| PROJECT_SPEC §12.3 | Other 主题保护 | §4.3 / §4.4 / §7.2 |

---

## 变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-07-23 | 初始创建：dashboard + 用户管理 + 主题/标签/题目 CRUD 共 16 接口；Other 主题保护（8001）；题目不可物理删除；管理员可见全部状态；管理员防自锁/防互操作（8006/8007）；主题/标签软删引用检查（8002）；错误码与 common.md 对齐 |

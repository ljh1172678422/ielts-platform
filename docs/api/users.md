# API 契约 — 用户模块（users.md）

> 本文定义用户模块的接口契约：当前用户资料、密码修改、学习目标。
> **严格遵守 [common.md](file:///workspace/docs/api/common.md) v0.1 与 [auth.md](file:///workspace/docs/api/auth.md) v0.1**，复用 `UserPublic` / `UserProfilePublic`，不重新定义。
> 对应规格：`PROJECT_SPEC.md` v0.5 §4/§6 / `database-design.md` v0.4 §3.1。

---

## 0. 文档定位

本文回答："users 模块有哪些接口、字段、校验、错误码。"
不回答："UserPublic 长什么样。" → [auth.md §7.2](file:///workspace/docs/api/auth.md)。
不回答："统一响应/错误码段。" → [common.md](file:///workspace/docs/api/common.md)。

---

## 1. 模块概述

### 1.1 职责

- 获取/修改当前用户资料（profile）
- 修改密码（旧密码校验）
- 管理学习目标（user_goals，含 active 唯一约束 ADR-014）

### 1.2 路由表

| Method | Path | 鉴权 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/users/me` | Bearer | 获取当前用户（含 profile） |
| PUT | `/api/v1/users/me` | Bearer | 修改当前用户资料 |
| PUT | `/api/v1/users/me/password` | Bearer | 修改密码（需旧密码） |
| GET | `/api/v1/users/me/goals` | Bearer | 获取目标列表（含当前 active） |
| POST | `/api/v1/users/me/goals` | Bearer | 创建新目标 |
| PUT | `/api/v1/users/me/goals/{goal_id}` | Bearer | 更新指定目标 |

### 1.3 涉及数据表

| 表 | 用途 |
| --- | --- |
| `users` | email / password_hash / status / last_login_at（只读） |
| `user_profiles` | nickname / avatar_url / timezone（可改） |
| `user_goals` | 学习目标 CRUD |
| `user_activity_logs` | 记录 `goal_created` / `goal_updated` |

### 1.4 复用 DTO（来自 auth.md §7.2）

```text
UserPublic:           # GET /users/me 响应用
  id, email, role, status, profile

UserProfilePublic:    # UserPublic.profile
  nickname, timezone, avatar_url
```

> 本文不重复定义上述 DTO，仅在需要扩展字段时声明扩展点（见 §2.2）。

---

## 2. GET /api/v1/users/me

### 2.1 请求

```
GET /api/v1/users/me
Authorization: Bearer <access_token>
```

无 Body / Query。

### 2.2 响应（成功）

HTTP 200，`data` 为 `UserPublic`（auth.md §7.2），**扩展** `created_at`：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": "1001",
    "email": "alice@example.com",
    "role": "user",
    "status": "active",
    "profile": {
      "nickname": "Alice",
      "timezone": "Asia/Shanghai",
      "avatar_url": null
    },
    "created_at": "2026-07-23T12:00:00+00:00"
  }
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `UserPublic.*` | — | 复用 auth.md §7.2 |
| `created_at` | string | 注册时间（ISO 8601），扩展字段 |

### 2.3 错误码

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 2001 | 401 | 无 Authorization 头 |
| 2002 | 401 | token 无效或已过期 |
| 2004 | 403 | 账号已禁用 |
| 2005 | 401 | 账号已注销 |

> 资源所有权天然满足（"me" 即当前用户），无 2003 场景。

### 2.4 后端处理

1. `get_current_user` 依赖注入已校验 token + 账号状态。
2. JOIN `user_profiles` 取 profile。
3. 返回 `UserPublic` + `created_at`。

---

## 3. PUT /api/v1/users/me

### 3.1 请求

```
PUT /api/v1/users/me
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Body（全量替换 profile 字段，未提供则置 null）：**

| 字段 | 类型 | 必填 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `nickname` | string | 否 | 长度 1..100 | 昵称；null 表示清空 |
| `avatar_url` | string | 否 | 长度 ≤ 500，http(s) URL | 头像；null 表示清空 |
| `timezone` | string | 是 | IANA 时区名 | 必填，影响统计切日（ADR-018） |

**示例：**

```json
{
  "nickname": "Alice L.",
  "avatar_url": "https://cdn.example.com/a/1.png",
  "timezone": "Asia/Shanghai"
}
```

> **不可修改字段**：`email`（MVP 不支持改邮箱）、`password`（走 §4 专用接口）、`role`（防越权）、`status`（管理员才可改）。
> 若请求体含这些字段，**忽略**（不报错），避免暴露内部字段。

### 3.2 响应（成功）

HTTP 200，`data` 为更新后的 `UserPublic`（结构同 §2.2）。

### 3.3 错误码

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 1001 | 422 | timezone 非合法 IANA 名 / 字段类型错 |
| 2001/2002/2004/2005 | 401/403/401 | 认证失败（同 §2.3） |

### 3.4 后端处理

1. Pydantic 校验 timezone（用 `zoneinfo.ZoneInfo` 校验合法性，失败 → 1001）。
2. 事务内 UPDATE `user_profiles`(nickname, avatar_url, timezone) WHERE user_id=current。
3. 返回更新后的 `UserPublic`。

> MVP 不记录 `profile_updated` 活动日志（非关键行为，按 ADR-023 精简原则）。

---

## 4. PUT /api/v1/users/me/password

### 4.1 请求

```
PUT /api/v1/users/me/password
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Body：**

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `old_password` | string | 是 | 非空 |
| `new_password` | string | 是 | 长度 8..64，与 old_password 不同 |

**示例：**

```json
{
  "old_password": "Alice@2026",
  "new_password": "Alice@2026New"
}
```

### 4.2 响应（成功）

HTTP 200：

```json
{
  "code": 0,
  "message": "ok",
  "data": null
}
```

> **不返回新 token**：MVP 无状态退出（ADR-027），旧 token 仍有效至自然过期。前端可选是否提示用户重新登录。

### 4.3 错误码

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 1001 | 422 | 字段缺失 / new_password 长度不合规 / new == old |
| 2001/2002/2004/2005 | 401/403/401 | 认证失败 |
| 3003 | 400 | 旧密码错误 |

### 4.4 后端处理

1. Pydantic 校验字段。
2. `bcrypt.verify(old_password, user.password_hash)` → 失败 → **3003**。
3. 校验 `new_password != old_password` → 相同 → 1001。
4. 事务内：
   - `password_hash = bcrypt.hash(new_password)`（cost ≥ 12，与 auth.md §6.1 一致）。
   - UPDATE `users.password_hash`。
5. 返回成功。

### 4.5 安全约束

- **不记录密码到任何日志**（含 old/new）。
- MVP 不强制登出其他设备（无状态，旧 token 仍有效至过期）。
- MVP 不实现密码修改后通知邮件（非 MVP）。

---

## 5. GET /api/v1/users/me/goals

### 5.1 请求

```
GET /api/v1/users/me/goals?status=active
Authorization: Bearer <access_token>
```

**Query（可选）：**

| 参数 | 类型 | 默认 | 约束 |
| --- | --- | --- | --- |
| `status` | string | 不传=全部 | `active` / `achieved` / `archived` |

### 5.2 响应（成功）

HTTP 200，`data` 为对象（含 `current` + `history`），**非分页**（目标数量少）：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "current": {
      "id": "51",
      "target_score": 7.0,
      "current_level": "6.0",
      "exam_date": "2026-11-15",
      "daily_goal_minutes": 60,
      "weekly_goal_minutes": 360,
      "status": "active",
      "created_at": "2026-07-23T12:00:00+00:00",
      "updated_at": "2026-07-23T12:00:00+00:00"
    },
    "history": [
      {
        "id": "50",
        "target_score": 6.5,
        "current_level": null,
        "exam_date": "2026-08-01",
        "daily_goal_minutes": 30,
        "weekly_goal_minutes": 180,
        "status": "achieved",
        "created_at": "2026-06-01T08:00:00+00:00",
        "updated_at": "2026-08-02T10:00:00+00:00"
      }
    ]
  }
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `current` | Goal \| null | 当前 active 目标；无则 null（ADR-014 保证至多 1 个） |
| `history` | Goal[] | 非_active 目标，按 `updated_at DESC` 排序 |

**Goal 结构：**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | goal_id（字符串化） |
| `target_score` | number \| null | 0.0–9.0 |
| `current_level` | string \| null | 当前水平（如 "6.0"） |
| `exam_date` | string \| null | 考试日期 `YYYY-MM-DD` |
| `daily_goal_minutes` | number \| null | 每日目标分钟 |
| `weekly_goal_minutes` | number \| null | 每周目标分钟 |
| `status` | string | active / achieved / archived |
| `created_at` / `updated_at` | string | ISO 8601 |

### 5.3 错误码

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 1001 | 422 | status 参数非合法枚举值 |
| 2001/2002/2004/2005 | 401/403/401 | 认证失败 |

### 5.4 后端处理

1. 查 `user_goals` WHERE user_id=current AND deleted_at IS NULL。
2. 若 `status` 参数存在，叠加过滤。
3. 拆分：`current` = 第一条 active（按 ADR-014 至多 1 条）；`history` = 其余按 updated_at DESC。
4. 返回。

---

## 6. POST /api/v1/users/me/goals

### 6.1 请求

```
POST /api/v1/users/me/goals
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Body：**

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `target_score` | number | 否 | 0.0–9.0 |
| `current_level` | string | 否 | 长度 ≤ 20 |
| `exam_date` | string | 否 | `YYYY-MM-DD`，未来日期 |
| `daily_goal_minutes` | number | 否 | ≥ 0 |
| `weekly_goal_minutes` | number | 否 | ≥ 0 |

> 至少一个字段非空（不允许创建全空目标）。

**示例：**

```json
{
  "target_score": 7.0,
  "current_level": "6.0",
  "exam_date": "2026-11-15",
  "daily_goal_minutes": 60,
  "weekly_goal_minutes": 360
}
```

### 6.2 响应（成功）

HTTP 200，`data` 为新建的 `Goal`（结构同 §5.2），`status='active'`。

### 6.3 错误码

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 1001 | 422 | 字段校验失败 / 全部字段为空 |
| 1004 | 409 | 已存在 active 目标（ADR-014 违反） |
| 2001/2002/2004/2005 | 401/403/401 | 认证失败 |

### 6.4 后端处理（事务）

1. Pydantic 校验 + 至少一字段非空检查。
2. 事务内：
   - 检查是否已存在 active 目标 → 存在 → **1004**（不自动归档旧目标，要求用户显式 PUT 旧目标为 achieved/archived）。
   - INSERT `user_goals`(user_id, ..., status='active')。
   - 部分唯一索引 `uq_user_goals_active` 兜底（若并发插入，DB 层报错 → 转 1004）。
   - INSERT `user_activity_logs`(action='goal_created', entity_type='user_goal', entity_id=new_id)。
3. 返回新建 Goal。

> **不自动归档旧 active 目标**：强制用户显式操作，避免历史目标状态被隐式改动。前端引导：创建前若已有 active，提示先归档。

---

## 7. PUT /api/v1/users/me/goals/{goal_id}

### 7.1 请求

```
PUT /api/v1/users/me/goals/{goal_id}
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Path：** `goal_id`（string，字符串化 ID）

**Body（全量替换）：**

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `target_score` | number | 否 | 0.0–9.0 |
| `current_level` | string | 否 | 长度 ≤ 20 |
| `exam_date` | string | 否 | `YYYY-MM-DD` |
| `daily_goal_minutes` | number | 否 | ≥ 0 |
| `weekly_goal_minutes` | number | 否 | ≥ 0 |
| `status` | string | 是 | `active` / `achieved` / `archived` |

**示例：**

```json
{
  "target_score": 7.0,
  "current_level": "6.5",
  "exam_date": "2026-12-01",
  "daily_goal_minutes": 60,
  "weekly_goal_minutes": 360,
  "status": "achieved"
}
```

### 7.2 响应（成功）

HTTP 200，`data` 为更新后的 `Goal`。

### 7.3 错误码

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 1001 | 422 | 字段校验失败 / status 非合法值 |
| 1002 | 404 | goal_id 不存在或不属于当前用户 |
| 1004 | 409 | 将某 archived/achieved 改回 active，但已存在其他 active 目标（ADR-014） |
| 2001/2002/2004/2005 | 401/403/401 | 认证失败 |
| 2003 | 403 | goal 不属于当前用户（资源所有权） |

### 7.4 后端处理（事务）

1. 按 goal_id + user_id 查（含 deleted_at IS NULL）→ 不存在 → **1002**。
2. Pydantic 校验。
3. 事务内：
   - 若新 status='active' 且原 status≠'active'：
     - 检查是否已存在其他 active 目标 → 存在 → **1004**。
   - UPDATE `user_goals`(全字段, updated_at=NOW())。
   - 部分唯一索引兜底并发。
   - 若 status 发生变化，INSERT `user_activity_logs`(action='goal_updated', entity_type='user_goal', entity_id)。
4. 返回更新后 Goal。

### 7.5 资源所有权

- service 层校验 `goal.user_id == current_user.id`，越权 → 2003。
- 不通过 goal_id 暴露他人目标（即便存在也不返回 1002，防探测）。

---

## 8. 安全与约束汇总

### 8.1 资源所有权

- 所有 `/users/me/*` 接口天然绑定当前用户，无需额外路径参数防越权。
- `/users/me/goals/{goal_id}` 必须校验 `goal.user_id == current_user.id`，越权返回 2003 或 1002（防探测，二选一；MVP 统一用 1002 防探测）。

### 8.2 不可修改字段（PUT /users/me）

- `email` / `role` / `status` / `password_hash` / `id` / `created_at` / `last_login_at` 均不可通过本接口修改。
- 含这些字段的请求体忽略该字段，不报错。

### 8.3 密码安全

- 与 auth.md §6.1 一致：bcrypt cost ≥ 12，不记录明文。
- 修改密码后旧 token 仍有效（ADR-027 无状态），不强制登出。

### 8.4 时区一致性

- `user_profiles.timezone` 修改后立即影响后续统计切日（ADR-018）。
- 历史已生成的 `study_records` 不回溯重算（按当时 timezone 已写入的 record_date 保留）；未来重算任务按新 timezone 重切（详见 learning.md）。

### 8.5 活动日志

- 记录：`goal_created` / `goal_updated`（status 变化时）。
- 不记录：profile 更新（非关键行为）、密码修改（敏感，且 ADR-023 精简原则）。

---

## 9. DTO 速查

### 9.1 请求 DTO

```text
UpdateProfileRequest:
  nickname: str | None (max_length=100)
  avatar_url: str | None (max_length=500)
  timezone: str  # 必填，IANA

ChangePasswordRequest:
  old_password: str (min_length=1)
  new_password: str (min_length=8, max_length=64)

CreateGoalRequest:
  target_score: float | None (ge=0, le=9)
  current_level: str | None (max_length=20)
  exam_date: date | None
  daily_goal_minutes: int | None (ge=0)
  weekly_goal_minutes: int | None (ge=0)
  # 至少一字段非空（service 校验）

UpdateGoalRequest:
  target_score: float | None (ge=0, le=9)
  current_level: str | None (max_length=20)
  exam_date: date | None
  daily_goal_minutes: int | None (ge=0)
  weekly_goal_minutes: int | None (ge=0)
  status: str  # 必填
```

### 9.2 响应 DTO

```text
UserPublic + created_at      # GET/PUT /users/me（auth.md UserPublic 扩展）

Goal:
  id: str
  target_score: float | None
  current_level: str | None
  exam_date: str | None        # YYYY-MM-DD
  daily_goal_minutes: int | None
  weekly_goal_minutes: int | None
  status: str
  created_at: str
  updated_at: str

GoalsResponse:
  current: Goal | None
  history: Goal[]
```

---

## 10. 与其他模块的衔接

| 衔接点 | 说明 |
| --- | --- |
| `auth.md` §7.2 | 复用 `UserPublic` / `UserProfilePublic` |
| `common.md` §3.2 | 错误码 1001/1002/1004/2001-2005/3003 |
| `learning.md` | `user_goals` 的 daily/weekly_goal_minutes 用于学习数据达成度展示 |
| `home.md` | `current` goal 用于首页目标进度展示 |
| `database-design.md` §3.1.4 | `user_goals` DDL + `uq_user_goals_active` 部分唯一索引 |

---

## 11. ADR 引用

| ADR | 内容 | 本文位置 |
| --- | --- | --- |
| ADR-014 | active goal 部分唯一索引 | §6.4 / §7.4 |
| ADR-018 | timezone 切日 | §8.4 |
| ADR-023 | 活动日志精简至关键行为 | §3.4 / §8.5 |
| ADR-025 | id 序列化为字符串 | 全文 goal_id |
| ADR-026 | snake_case | 全文 |
| ADR-027 | MVP 无状态退出，改密后旧 token 仍有效 | §4.2 / §8.3 |

---

## 变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-07-23 | 初始创建：me(GET/PUT) + password + goals(GET/POST/PUT) 共 6 接口；复用 auth.md UserPublic；ADR-014 active 唯一约束落地；资源所有权与防探测策略 |

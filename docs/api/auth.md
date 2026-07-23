# API 契约 — 认证模块（auth.md）

> 本文定义认证模块的接口契约：注册、登录、退出。
> **严格遵守 [common.md](file:///workspace/docs/api/common.md) v0.1**，不重新定义统一响应、错误码、ID 序列化、snake_case 规则。
> 对应规格：`PROJECT_SPEC.md` v0.5 §4/§6 / `database-design.md` v0.4 §3.1 / `system-architecture.md` v0.1 §8。

---

## 0. 文档定位

本文回答："auth 模块有哪些接口、字段、错误码、安全约束。"
不回答："JWT 怎么签发实现。" → 阶段 4 代码实现。
不回答："统一响应长什么样。" → [common.md](file:///workspace/docs/api/common.md)。

---

## 1. 模块概述

### 1.1 职责

- 用户注册（创建 user + profile）
- 用户登录（校验密码 + 签发 JWT）
- 用户退出（MVP 为无状态退出，见 §6.2）

### 1.2 路由表

| Method | Path | 鉴权 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/v1/auth/register` | 无 | 注册新账号 |
| POST | `/api/v1/auth/login` | 无 | 登录并返回 access_token |
| POST | `/api/v1/auth/logout` | Bearer | 退出登录（无状态） |

### 1.3 涉及数据表

| 表 | 用途 |
| --- | --- |
| `users` | 账号、密码哈希、邮箱、状态、角色 |
| `user_profiles` | 注册时同步创建（nickname / timezone） |
| `roles` | 注册时默认绑定 `user` 角色 |
| `user_activity_logs` | 记录 `user_registered` / `user_login` |

---

## 2. POST /api/v1/auth/register

### 2.1 请求

```
POST /api/v1/auth/register
Content-Type: application/json
```

**Body：**

| 字段 | 类型 | 必填 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `email` | string | 是 | 合法邮箱格式，长度 ≤ 255 | 注册邮箱，唯一 |
| `password` | string | 是 | 长度 8..64 | 明文传输（HTTPS），后端 bcrypt 哈希 |
| `nickname` | string | 否 | 长度 1..100 | 昵称；缺省取 email 本地部分 |
| `timezone` | string | 否 | IANA 时区名，如 `Asia/Shanghai` | 缺省 `Asia/Shanghai` |

**示例：**

```json
{
  "email": "alice@example.com",
  "password": "Alice@2026",
  "nickname": "Alice",
  "timezone": "Asia/Shanghai"
}
```

### 2.2 响应（成功）

HTTP 200，`data` 为用户公开信息 + token：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "user": {
      "id": "1001",
      "email": "alice@example.com",
      "role": "user",
      "status": "active",
      "profile": {
        "nickname": "Alice",
        "timezone": "Asia/Shanghai",
        "avatar_url": null
      }
    },
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 86400
  }
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `user.id` | string | 用户 ID（字符串化，§1.5） |
| `user.email` | string | 邮箱 |
| `user.role` | string | 注册恒为 `"user"` |
| `user.status` | string | 注册恒为 `"active"` |
| `user.profile.nickname` | string? | 昵称 |
| `user.profile.timezone` | string | 时区 |
| `user.profile.avatar_url` | string? | 头像 URL，注册时为 null |
| `access_token` | string | JWT |
| `token_type` | string | 恒为 `"bearer"` |
| `expires_in` | int | token 有效期秒数（MVP 86400 = 24h） |

### 2.3 错误码

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 1001 | 422 | 字段缺失/格式错/长度不合规 |
| 1004 | 409 | 邮箱已注册（含软删用户占用该邮箱） |
| 3001 | 409 | 邮箱已注册（同上，业务语义化别名） |

> 注：3001 与 1004 语义重叠，**优先返回 3001**（模块专属码便于前端识别"邮箱已注册"场景）。

### 2.4 后端处理（约束）

1. 校验 email 格式 + password 长度（Pydantic）。
2. 查 `users` 是否存在该 email（含 `deleted_at IS NOT NULL` 的软删账号）→ 存在则 3001。
   - 软删账号占用邮箱时，按 database-design §7.2 邮箱已释放，应允许注册；此处仅检查 `deleted_at IS NULL` 的账号。
3. `password_hash = bcrypt.hash(password)`（cost factor ≥ 12）。
4. 事务内：
   - INSERT `users`(email, password_hash, role_id=user, status=active, email_verified_at=NOW())。
   - INSERT `user_profiles`(user_id, nickname, timezone)。
   - INSERT `user_activity_logs`(action='user_registered', entity_type='user', entity_id=new_user_id)。
5. 签发 JWT，返回。

> MVP 不发送验证邮件，`email_verified_at` 注册即填 NOW()（视同已验证）。未来加邮件验证时改为 NULL 并发邮件（非 MVP）。

---

## 3. POST /api/v1/auth/login

### 3.1 请求

```
POST /api/v1/auth/login
Content-Type: application/json
```

**Body：**

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `email` | string | 是 | 合法邮箱 |
| `password` | string | 是 | 非空 |

**示例：**

```json
{
  "email": "alice@example.com",
  "password": "Alice@2026"
}
```

### 3.2 响应（成功）

HTTP 200，结构与注册响应 `data` 完全一致（§2.2），额外更新 `users.last_login_at`。

### 3.3 错误码

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 1001 | 422 | 字段缺失 |
| 3002 | 401 | 邮箱或密码错误 |
| 2004 | 403 | 账号已禁用（status=disabled） |
| 2005 | 401 | 账号已注销（deleted_at 非空） |

### 3.4 后端处理（约束）

1. 按 email 查 `users`（含 `deleted_at IS NULL` 过滤）。
   - 不存在 → **3002**（不返回 1002，防止账号枚举）。
   - `deleted_at` 非空 → 2005（仅当查询未过滤 deleted_at 时可能命中；MVP 默认过滤，故实际走 3002）。
2. `bcrypt.verify(password, user.password_hash)` → 失败 → **3002**（同上，防枚举）。
3. `status='disabled'` → 2004。
4. 事务内：
   - UPDATE `users.last_login_at = NOW()`。
   - INSERT `user_activity_logs`(action='user_login')。
5. 签发 JWT，返回。

### 3.5 安全约束

- **邮箱/密码错误统一返回 3002**，不区分"邮箱不存在"与"密码错误"，防账号枚举。
- 登录响应时间应恒定（避免通过时序差异判断账号是否存在）——MVP 通过 bcrypt 校验耗时本身较恒定来近似满足。
- 密码错误次数限制（防爆破）：**MVP 不实现**，未来加（非 MVP，需 Redis 计数）。

---

## 4. POST /api/v1/auth/logout

### 4.1 请求

```
POST /api/v1/auth/logout
Authorization: Bearer <access_token>
```

无 Body。

### 4.2 响应（成功）

HTTP 200：

```json
{
  "code": 0,
  "message": "ok",
  "data": null
}
```

### 4.3 错误码

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 2001 | 401 | 无 Authorization 头 |
| 2002 | 401 | token 无效或已过期 |

### 4.4 后端处理（约束）

**MVP 无状态退出**（ADR-027）：

- JWT 为无状态 token，后端不维护会话表，无法真正"撤销"未过期 token。
- logout 接口仅作语义记录与前端指引：
  - INSERT `user_activity_logs`(action='user_logout')（可选，MVP 记录）。
  - 返回成功。
- **前端职责**：收到 200 后清除本地存储的 `access_token` 与用户状态。

> 未来引入 refresh_token / token 撤销表时，logout 才能真正使 token 失效（非 MVP）。
> **安全提示**：MVP 期间若 token 泄露，只能等待自然过期（24h）。生产环境应缩短 `expires_in` 或尽快引入撤销机制。

---

## 5. JWT 约定

### 5.1 载荷（Payload）

```json
{
  "sub": "1001",
  "role": "user",
  "email": "alice@example.com",
  "iat": 1721721600,
  "exp": 1721808000
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `sub` | string | user_id（字符串化） |
| `role` | string | `"user"` / `"admin"` |
| `email` | string | 登录时邮箱，便于日志排查 |
| `iat` | int | 签发时间（Unix 秒） |
| `exp` | int | 过期时间（Unix 秒），iat + expires_in |

### 5.2 算法与密钥

- 算法：`HS256`。
- 密钥：环境变量 `JWT_SECRET`（≥ 32 字节随机串）。
- MVP 不支持密钥轮换。

### 5.3 有效期

| 项 | MVP 值 |
| --- | --- |
| `expires_in` | 86400 秒（24h） |

> 生产建议缩短至 1–2h 并引入 refresh_token（非 MVP）。

### 5.4 校验流程（每个受保护接口）

```text
1. 从 Authorization 头取 Bearer token；缺失 → 2001
2. 解码 JWT，校验签名 + exp；失败 → 2002
3. 按 sub 查 users（含 deleted_at IS NULL）
     - 不存在 / deleted_at 非空 → 2005
     - status=disabled → 2004
4. 注入 current_user 到请求上下文
```

---

## 6. 安全约束汇总

### 6.1 密码

- 存储：bcrypt，cost factor ≥ 12。
- 传输：仅 HTTPS（Nginx 终止 TLS）。
- 长度：8..64。
- 强度校验：MVP 仅长度校验，不强制大小写/数字/符号组合（降低用户体验门槛）。
- 修改密码接口在 `users.md` 定义（`PUT /users/me/password`），本文不涉及。

### 6.2 会话

- MVP 无状态（ADR-027）：无服务端会话表，无 token 撤销。
- 前端负责 token 存储与清除（建议 `localStorage` + XSS 防护，或 HttpOnly cookie）。
- MVP 不实现：refresh_token、token rotation、单设备登录限制、异地登录提示。

### 6.3 速率限制

- MVP 不实现（需 Redis）。
- 未来对 `/auth/login` 与 `/auth/register` 加 IP 级速率限制（非 MVP）。

### 6.4 账号枚举防护

- 注册：邮箱已注册 → 3001（必须告知，因用户需要换邮箱）。
- 登录：邮箱不存在/密码错误 → 统一 3002（不区分，防枚举）。

### 6.5 日志

- 记录：`user_registered`、`user_login`、`user_logout`（写入 `user_activity_logs`）。
- **不记录**：密码、token 明文。
- 登录失败 MVP **不记录**（避免日志膨胀 + 枚举信号），未来加审计时再记（非 MVP）。

---

## 7. DTO 速查

### 7.1 请求 DTO

```text
RegisterRequest:
  email: str (EmailStr)
  password: str (min_length=8, max_length=64)
  nickname: str | None (max_length=100)
  timezone: str = "Asia/Shanghai"

LoginRequest:
  email: str (EmailStr)
  password: str (min_length=1)
```

### 7.2 响应 DTO

```text
AuthResponse:
  user: UserPublic
  access_token: str
  token_type: str = "bearer"
  expires_in: int

UserPublic:
  id: str
  email: str
  role: str
  status: str
  profile: UserProfilePublic

UserProfilePublic:
  nickname: str | None
  timezone: str
  avatar_url: str | None
```

> 完整字段（含 created_at 等）的 `UserPublic` 在 `users.md` 统一定义，本文引用。

---

## 8. 与其他模块的衔接

| 衔接点 | 说明 |
| --- | --- |
| `users.md` | `GET/PUT /users/me`、`PUT /users/me/password`、`user_goals` 接口 |
| `common.md` §5 | 认证失败处理、Bearer 格式 |
| `common.md` §3.2 | 错误码 2001–2005、3001、3002 |
| `system-architecture.md` §8.1 | 认证架构、`get_current_user` 依赖 |

---

## 9. ADR 引用

| ADR | 内容 | 本文位置 |
| --- | --- | --- |
| ADR-009 | 角色级权限（user/admin） | §2.2 role 恒为 user |
| ADR-025 | id 序列化为字符串 | §2.2 user.id、§5.1 sub |
| ADR-026 | snake_case | 全文 |
| ADR-027 | MVP 无状态退出，无 token 撤销 | §4.4 / §6.2 |

---

## 变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-07-23 | 初始创建：register/login/logout 3 接口 + JWT 约定 + 安全约束 + 错误码 + DTO；引用 ADR-027 无状态退出 |

# API 通用约定（common.md）

> 本文定义所有 API 共享的协议：统一响应结构、错误码体系、分页、认证、字段与时间约定。
> **所有模块 API 文档（auth/users/questions/practice/learning/home/admin）必须遵守本文，不得自行定义响应结构或错误码段。**
> 对应规格：`PROJECT_SPEC.md` v0.5 / `system-architecture.md` v0.1。

---

## 0. 文档定位

本文回答："所有 API 长什么样、错误怎么报、怎么分页、怎么认证。"
不回答："某个具体接口的字段是什么。" → 各模块 `*.md`。

---

## 1. 基础约定

### 1.1 基础路径

```text
/api/v1
```

所有路由前缀 `/api/v1`。管理后台叠加 `/api/v1/admin`。

### 1.2 Content-Type

| 场景 | Content-Type |
| --- | --- |
| 普通 JSON 请求/响应 | `application/json; charset=utf-8` |
| 文件上传（录音） | `multipart/form-data` |
| 文件下载（录音读取） | `audio/<格式>`（StreamingResponse） |

### 1.3 HTTP 方法语义

| 方法 | 语义 | 幂等 |
| --- | --- | --- |
| GET | 查询 | 是 |
| POST | 创建 / 触发动作 | 否 |
| PUT | 全量替换 | 是 |
| PATCH | 局部更新（状态机转换用） | 否 |
| DELETE | 删除/取消 | 是 |

### 1.4 字段命名

- **全链路统一 `snake_case`**（后端 → JSON → 前端），不转 `camelCase`。
- 理由：减少心智负担与转换层，与数据库列名一致。
- 前端 TS 接口类型直接用 `snake_case` 字段名。

### 1.5 ID 序列化

> BIGINT 主键在 JavaScript 中超过 `2^53` 会丢精度（ADR-005）。

- **所有 `id` / `*_id` 字段在 JSON 响应中序列化为字符串**（如 `"12345"`）。
- 请求路径参数 `id` 也用字符串形式传递。
- Pydantic schema 中 id 字段声明为 `str`，由序列化配置将 int 转 str。
- 前端对 id 仅作字符串处理，不做数值运算。

### 1.6 时间格式

- 统一 ISO 8601 带时区偏移：`2026-07-23T12:00:00+00:00`。
- 数据库存储 UTC，响应按 UTC 返回（带 `+00:00`）。
- 纯日期字段（如 `record_date`、`exam_date`）用 `YYYY-MM-DD`。
- 前端展示时按 `user_profiles.timezone` 转换。

### 1.7 空值

- 可空字段为 `null`，不省略字段。
- 列表字段空时返回 `[]`，不返回 `null`。

---

## 2. 统一响应结构

### 2.1 成功响应

```json
{
  "code": 0,
  "message": "ok",
  "data": { ... }
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | int | `0` 表示成功 |
| `message` | string | 固定 `"ok"` 或简短说明 |
| `data` | object/array/null | 业务数据；无数据时为 `null` |

### 2.2 错误响应

```json
{
  "code": 2002,
  "message": "token 无效或已过期",
  "data": null,
  "details": [
    { "field": "token", "message": "jwt expired" }
  ]
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | int | 非 0 的业务错误码（见 §3） |
| `message` | string | 面向用户的简短提示 |
| `data` | null | 错误时恒为 `null` |
| `details` | array? | 仅参数校验失败（422）时出现，逐字段说明 |

### 2.3 HTTP 状态码映射

| HTTP | 触发条件 | 响应 body |
| --- | --- | --- |
| 200 | 成功 | `{ code: 0 }` |
| 400 | 业务规则错误（状态机非法、跨表约束违反等） | `{ code: 业务码 }` |
| 401 | 未认证 / token 缺失或失效 | `{ code: 2001/2002 }` |
| 403 | 权限不足 / 资源不属于当前用户 | `{ code: 2003 }` |
| 404 | 资源不存在 | `{ code: 1002 }` |
| 422 | 请求参数校验失败（Pydantic） | `{ code: 1001, details: [...] }` |
| 500 | 服务内部错误 | `{ code: 9003 }` |

> FastAPI 默认 Pydantic 校验失败返回 422 + `{detail:[...]}`，**必须**在全局异常处理器中改写为本结构（`code:1001` + `details`）。

### 2.4 不允许的写法

- ❌ 直接返回裸对象（无 `code/message/data` 包装）。
- ❌ 用 HTTP 状态码表达业务错误（如 200 + `{error:...}`）。
- ❌ 不同模块用不同响应结构。
- ❌ 错误时 `data` 非 null。

---

## 3. 错误码体系

### 3.1 编号规则

```text
0        成功
1xxx     通用错误
2xxx     认证 / 授权 / 账号状态
3xxx     用户模块
4xxx     题库模块
5xxx     练习模块
6xxx     录音模块
7xxx     学习模块
8xxx     管理后台
9xxx     系统 / 存储
```

### 3.2 错误码清单

| code | HTTP | 含义 | 触发示例 |
| --- | --- | --- | --- |
| 0 | 200 | 成功 | — |
| 1001 | 422 | 参数校验失败 | 字段缺失/类型错 |
| 1002 | 404 | 资源不存在 | 任意实体找不到 |
| 1003 | 400 | 操作不支持 | 逻辑上不可执行 |
| 1004 | 409 | 资源冲突 | 唯一约束冲突 |
| 2001 | 401 | 未认证（token 缺失） | 无 Authorization 头 |
| 2002 | 401 | token 无效或已过期 | JWT 解析失败 |
| 2003 | 403 | 权限不足 | 非 admin 访问后台；越权他人资源 |
| 2004 | 403 | 账号已禁用 | user.status=disabled |
| 2005 | 401 | 账号已注销 | user.deleted_at 非空 |
| 3001 | 409 | 邮箱已注册 | register 重复 email |
| 3002 | 401 | 邮箱或密码错误 | login 失败 |
| 3003 | 400 | 旧密码错误 | change password |
| 4001 | 404 | 题目不存在 | — |
| 4002 | 400 | 题目已禁用 | 访问 disabled 题目 |
| 4003 | 404 | 主题不存在 | — |
| 4004 | 404 | 标签不存在 | — |
| 4005 | 409 | 已收藏该题目 | 重复收藏 |
| 4006 | 400 | 未收藏该题目 | 取消不存在的收藏 |
| 5001 | 404 | 练习会话不存在 | — |
| 5002 | 400 | 会话状态非法 | 状态机非法转换 |
| 5003 | 403 | 会话不属于当前用户 | 越权 |
| 5004 | 400 | 题目数量不足 | 抽题数 > 可用题数 |
| 5005 | 404 | attempt 不存在 | — |
| 5006 | 400 | attempt 状态非法 | submitted 前无 uploaded recording（ADR-015） |
| 5007 | 400 | 会话题目不存在 | session_question 找不到 |
| 6001 | 404 | 录音不存在 | — |
| 6002 | 400 | 录音上传失败 | 写文件/元数据失败 |
| 6003 | 400 | 文件格式不支持 | mime 不在白名单 |
| 6004 | 413 | 文件过大 | 超大小限制 |
| 6005 | 400 | 录音状态非法 | 状态机非法转换 |
| 7001 | 404 | 统计数据不存在 | — |
| 8001 | 400 | 管理员操作受限 | 删除/停用/重命名 `Other` 主题（§4.5.13） |
| 8002 | 400 | 资源被引用，不可删除 | 主题/标签删除时仍有题目引用 |
| 8006 | 400 | 管理员不可操作自己 | 试图禁用/变更当前管理员自身账号 |
| 8007 | 400 | 管理员不可操作其他管理员 | MVP 仅允许操作 user 角色 |
| 9001 | 500 | 存储服务异常 | FS/S3 故障 |
| 9002 | 500 | 数据库异常 | — |
| 9003 | 500 | 服务内部错误 | 未捕获异常兜底 |

### 3.3 错误码使用规则

- 新增错误码必须先更新本表，再在模块文档引用。
- 同一业务场景优先复用现有码，不新增近义码。
- `message` 可按场景细化文案，`code` 必须稳定。
- 404 类错误统一用 `1002`（通用"资源不存在"），**不**为每类资源单独建 404 码；模块文档在 `message` 中指明资源类型。

> 例外：关键实体（题目/会话/attempt/录音）保留专属 404 码（4001/5001/5005/6001）以便前端精准识别。

---

## 4. 分页协议

### 4.1 请求参数（Query）

| 参数 | 类型 | 默认 | 约束 |
| --- | --- | --- | --- |
| `page` | int | 1 | ≥ 1 |
| `page_size` | int | 20 | 1..100 |

### 4.2 响应结构

列表接口 `data` 固定为：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "items": [ ... ],
    "total": 156,
    "page": 1,
    "page_size": 20,
    "total_pages": 8
  }
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `items` | array | 当前页数据 |
| `total` | int | 总记录数 |
| `page` | int | 当前页码 |
| `page_size` | int | 每页大小 |
| `total_pages` | int | 总页数（= ceil(total/page_size)） |

### 4.3 规则

- ID 序列化规则（§1.5）仅作用于实体 ID 与外键 ID（`id` / `*_id`）；分页元数据 `total` / `page` / `page_size` / `total_pages` **保持普通 int**，便于前端分页组件直接使用。`total` 是计数元数据而非实体 ID，不会触发 BIGINT 精度问题。
- 越界页：返回空 `items`，不报错。
- 非列表接口（如详情、单个资源）不使用此结构，`data` 直接为对象。

---

## 5. 认证与授权

### 5.1 认证方式

JWT Bearer Token：

```http
Authorization: Bearer <access_token>
```

- 登录成功返回 `access_token`。
- 除 `auth/register` / `auth/login` 外，所有接口需认证。
- token 载荷含 `sub`(user_id)、`role`、`exp`。
- MVP 不实现 refresh_token。

### 5.2 认证失败处理

| 场景 | HTTP | code |
| --- | --- | --- |
| 无 Authorization 头 | 401 | 2001 |
| token 解析失败/过期 | 401 | 2002 |
| 用户已注销（deleted_at） | 401 | 2005 |
| 用户已禁用（status=disabled） | 403 | 2004 |

### 5.3 授权模型

- 角色级（ADR-009）：`user` / `admin`。
- `/api/v1/admin/*` 需 `role='admin'`，否则 403 / code 2003。
- 资源所有权：service 层校验 `resource.user_id == current_user.id`，越权返回 403 / code 2003。
- 用户端接口仅能操作自己的资源（session/attempt/recording/goal/profile）。

---

## 6. 文件上传约定（录音专用）

### 6.1 上传

```http
POST /api/v1/practice/attempts/{attempt_id}/recording
Content-Type: multipart/form-data
Authorization: Bearer <token>

file=<binary>
```

### 6.2 限制

| 项 | 限制 |
| --- | --- |
| 允许 mime | `audio/webm`, `audio/mp4`, `audio/mpeg`, `audio/wav` |
| 最大大小 | 50 MB |
| 超限返回 | 6003（格式）/ 6004（大小） |

### 6.3 后端处理（ADR-020）

```text
接收文件
  ↓ 校验 mime + 大小
  ↓ 写存储
  ↓ 读音频元数据 → duration_seconds（不信前端）
  ↓ INSERT recordings(status=uploading) → uploaded
  ↓ UPDATE attempts.status=submitted（ADR-015）
  ↓ upsert study_records（ADR-022，同步）
  ↓ INSERT activity_log
  ↓ 事务提交
```

### 6.4 下载

```http
GET /api/v1/practice/attempts/{attempt_id}/recording
Authorization: Bearer <token>
→ 200 audio/webm (StreamingResponse)
```

- 鉴权：仅 attempt 所属用户可下载。
- 不存在录音返回 404 / code 6001。

---

## 7. 通用 DTO 片段

> 以下为多模块复用片段，各模块文档引用。

### 7.1 时间戳字段

所有实体响应含：

```json
{
  "created_at": "2026-07-23T12:00:00+00:00",
  "updated_at": "2026-07-23T12:05:00+00:00"
}
```

软删实体额外含 `"deleted_at": null`（已删除则带时间戳，但通常不返回给前端）。

### 7.2 ID 字段

```json
{
  "id": "12345",
  "user_id": "678"
}
```

### 7.3 状态字段

字符串枚举，值集见 database-design §2，如：

```json
{ "status": "published" }
{ "status": "in_progress" }
```

---

## 8. 跨模块引用的状态机约束（API 层）

> 这些约束源于 ADR-015，在 API 层体现为特定错误码。

| 操作 | 前置条件 | 违反时 |
| --- | --- | --- |
| `PATCH attempt → submitted` | 该 attempt 存在 `recording.status=uploaded` | 400 / 5006 |
| `POST session/{id}/complete` | 所有 session_question 有 submitted/skipped attempt | 400 / 5002 |
| `POST attempts/{id}/recording` | attempt.status ∈ {pending, recording} | 400 / 5006 |

---

## 9. 与下游模块文档的契约

各模块 `*.md` 必须包含：

1. 路由表（method + path + 鉴权要求 + 简述）。
2. 每个接口的请求参数（path/query/body）。
3. 响应 `data` 结构（字段名 snake_case、id 为 string、时间为 ISO 8601）。
4. 可能返回的错误码（引用本文 §3.2，不新增近义码）。
5. 状态机相关的接口标注前置条件（引用 §8）。

---

## 变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-07-23 | 初始创建：统一响应结构 + 错误码体系（0–9003）+ 分页协议 + 认证授权 + 文件上传约定 + ID序列化为字符串 + snake_case 全链路 + 跨模块状态机约束 |

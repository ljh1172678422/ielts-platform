# API 契约 — 题库模块（questions.md，用户端）

> 本文定义用户端题库浏览与收藏接口契约。
> **仅用户端读 + 收藏操作，不含管理员 CRUD**（管理员题目/主题/标签管理在 `admin.md`）。
> **严格遵守 [common.md](file:///workspace/docs/api/common.md) v0.1**，不重新定义统一响应/分页/错误码。
> 对应规格：`PROJECT_SPEC.md` v0.5 §6 / `database-design.md` v0.4 §3.2。

---

## 0. 文档定位

本文回答："用户端题库有哪些接口、字段、筛选、错误码。"
不回答："管理员怎么增删改题目。" → `admin.md`。
不回答："统一响应/分页结构。" → [common.md](file:///workspace/docs/api/common.md)。

---

## 1. 模块概述

### 1.1 职责

- 题库列表（搜索 / Part / 主题 / 标签筛选 / 分页 / 排序）
- 题目详情
- 收藏 / 取消收藏

### 1.2 路由表

| Method | Path | 鉴权 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/questions` | Bearer | 题库列表（分页+筛选） |
| GET | `/api/v1/questions/{id}` | Bearer | 题目详情 |
| POST | `/api/v1/questions/{id}/favorite` | Bearer | 收藏题目 |
| DELETE | `/api/v1/questions/{id}/favorite` | Bearer | 取消收藏 |

### 1.3 涉及数据表

| 表 | 用途 |
| --- | --- |
| `speaking_questions` | 题目主表（仅 `status='published'`） |
| `speaking_topics` | 主题关联（名称展示） |
| `tags` / `question_tags` | 标签关联 |
| `favorites` | 收藏关系 |
| `practice_session_questions` | 仅用于 popular 排序统计（引用计数） |

### 1.4 核心约束

- **ADR-010**：用户端仅返回 `speaking_questions.status='published'` 的题目；`draft` / `disabled` 对用户端不可见（访问 disabled 题目详情返回 4002）。
- **ADR-019**：`topic_id` NOT NULL，所有题目必有主题，列表筛选用 `topic_id` 永远有效。
- **收藏语义**：`favorites` 表无 status，存在即收藏，删除即取消（PROJECT_SPEC §4.4）。

---

## 2. GET /api/v1/questions

### 2.1 请求

```
GET /api/v1/questions?page=1&page_size=20&part=2&topic_id=5&tag_id=12&keyword=describe&difficulty=3&sort=newest&is_favorited=true
Authorization: Bearer <access_token>
```

**Query 参数：**

| 参数 | 类型 | 默认 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `page` | int | 1 | ≥ 1 | 页码 |
| `page_size` | int | 20 | 1..100 | 每页大小 |
| `part` | int | 不传=全部 | 1 / 2 / 3 | Part 筛选 |
| `topic_id` | string | 不传=全部 | 字符串化 ID | 主题筛选 |
| `tag_id` | string | 不传=全部 | 字符串化 ID | 单标签筛选（MVP 不支持多标签 AND/OR） |
| `keyword` | string | 不传=不限 | 长度 1..100 | 搜索 `title` + `content`（ILIKE 模糊匹配） |
| `difficulty` | int | 不传=全部 | 1..5 | 难度筛选 |
| `sort` | string | `newest` | `newest` / `popular` | 排序方式 |
| `is_favorited` | bool | 不传=全部 | true/false | 仅看我收藏的题目 |

> `topic_id` / `tag_id` 虽为字符串（§1.5 ID 序列化），但 Query 参数本身是字符串传输，后端转 BIGINT 校验。

### 2.2 响应（成功）

HTTP 200，`data` 为分页结构（common.md §4.2），`items` 为 `QuestionListItem[]`：

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
        "topic": {
          "id": "5",
          "name": "Technology"
        },
        "difficulty": 3,
        "is_favorited": true,
        "practice_count": 42,
        "created_at": "2026-07-01T10:00:00+00:00"
      }
    ],
    "total": 156,
    "page": 1,
    "page_size": 20,
    "total_pages": 8
  }
}
```

**QuestionListItem：**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 题目 ID |
| `part` | int | 1 / 2 / 3 |
| `title` | string | 标题 |
| `topic` | object | `{id, name}` 主题摘要 |
| `difficulty` | int \| null | 1..5 |
| `is_favorited` | bool | 当前用户是否已收藏 |
| `practice_count` | int | 被练习次数（`practice_session_questions` 引用数，用于 popular 排序与热度展示） |
| `created_at` | string | ISO 8601 |

> 列表项**不含** `content` / `cue_card` / `tags` / `source_*`，减少负载；详情接口返回完整字段。

### 2.3 错误码

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 1001 | 422 | 参数类型错 / part 非法值 / sort 非法值 |
| 2001/2002/2004/2005 | 401/403/401 | 认证失败 |

> `topic_id` / `tag_id` 指向不存在的资源时，**不报错**，返回空列表（筛选无匹配），不返回 4003/4004（这两个码保留给创建题目时的引用校验场景）。

### 2.4 后端处理

1. 基础过滤：`speaking_questions.status='published' AND deleted_at IS NULL`（题目无 deleted_at，此处仅 status）。
2. 叠加筛选：part / topic_id / difficulty / keyword（ILIKE `%keyword%` on title + content）。
3. 标签筛选：`tag_id` 存在时，`EXISTS(SELECT 1 FROM question_tags WHERE question_id=q.id AND tag_id=?)`。
4. 收藏筛选：`is_favorited=true` 时，`EXISTS(SELECT 1 FROM favorites WHERE question_id=q.id AND user_id=current)`。
5. 排序：
   - `newest`：`ORDER BY created_at DESC`（默认）。
   - `popular`：`ORDER BY practice_count DESC, created_at DESC`（practice_count 由 LEFT JOIN 子查询统计 `practice_session_questions`）。
6. 分页：`LIMIT page_size OFFSET (page-1)*page_size`。
7. 收藏状态：对当前页 items 批量查 `favorites`（避免 N+1，用 `IN` 批量查询）。
8. practice_count：对当前页 items 批量聚合（避免 N+1）。

### 2.5 性能说明

- 列表查询走索引 `ix_questions_status_part`（status, part）+ `topic_id` 索引。
- `popular` 排序的 practice_count 子查询可能较重，MVP 接受（题库规模有限）；未来可加 `practice_count` 冗余字段到 `speaking_questions`，由统计任务维护（非 MVP）。

---

## 3. GET /api/v1/questions/{id}

### 3.1 请求

```
GET /api/v1/questions/{id}
Authorization: Bearer <access_token>
```

**Path：** `id`（string，题目 ID）

### 3.2 响应（成功）

HTTP 200，`data` 为 `QuestionDetail`：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": "101",
    "part": 2,
    "title": "Describe a useful object",
    "content": "You will have to talk about the topic for one to two minutes...",
    "cue_card": "You should say:\n- what it is\n- how you use it\n- why it is useful",
    "topic": {
      "id": "5",
      "name": "Technology"
    },
    "tags": [
      { "id": "12", "name": "gadget" },
      { "id": "18", "name": "daily-life" }
    ],
    "difficulty": 3,
    "source_type": "custom",
    "source_name": "自编练习题",
    "is_favorited": true,
    "practice_count": 42,
    "created_at": "2026-07-01T10:00:00+00:00"
  }
}
```

**QuestionDetail：**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 题目 ID |
| `part` | int | 1 / 2 / 3 |
| `title` | string | 标题 |
| `content` | string | 题目正文 |
| `cue_card` | string \| null | Cue Card 提示（原始文本，前端按 `\n` / `-` 渲染） |
| `topic` | object | `{id, name}` |
| `tags` | array | `[{id, name}, ...]` 标签列表（可能为空 `[]`） |
| `difficulty` | int \| null | 1..5 |
| `source_type` | string | `official` / `historical` / `mock` / `custom`（版权透明，§12） |
| `source_name` | string | 来源说明 |
| `is_favorited` | bool | 当前用户是否收藏 |
| `practice_count` | int | 被练习次数 |
| `created_at` | string | ISO 8601 |

> **不暴露** `created_by`（用户隐私）、`status`（恒为 published，无需返回）、`updated_at`（对用户无意义）。

### 3.3 错误码

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 1001 | 422 | id 非合法数字 |
| 2001/2002/2004/2005 | 401/403/401 | 认证失败 |
| 4001 | 404 | 题目不存在（id 不存在） |
| 4002 | 400 | 题目已禁用（status=disabled，对用户端不可见） |

### 3.4 后端处理

1. 按 id 查 `speaking_questions`。
   - 不存在 → **4001**。
   - `status='disabled'` → **4002**（区分于 4001，便于前端提示"该题目已下架"）。
   - `status='draft'` → **4001**（草稿对用户端等同不存在，不暴露存在性）。
   - `status='published'` → 继续。
2. JOIN `speaking_topics` 取主题。
3. 查 `question_tags` + `tags` 取标签列表。
4. 查 `favorites` 判断 is_favorited。
5. 聚合 `practice_session_questions` 取 practice_count。
6. 返回 `QuestionDetail`。

---

## 4. POST /api/v1/questions/{id}/favorite

### 4.1 请求

```
POST /api/v1/questions/{id}/favorite
Authorization: Bearer <access_token>
```

无 Body。

**Path：** `id`（string，题目 ID）

### 4.2 响应（成功）

HTTP 200：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "question_id": "101",
    "is_favorited": true
  }
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `question_id` | string | 题目 ID |
| `is_favorited` | bool | 恒为 true（幂等：重复收藏也返回 true） |

### 4.3 错误码

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 1001 | 422 | id 非合法数字 |
| 2001/2002/2004/2005 | 401/403/401 | 认证失败 |
| 4001 | 404 | 题目不存在或非 published（不区分 disabled/draft，防探测） |

> **不返回 4005（已收藏）**：收藏操作幂等，重复收藏返回成功 200，`is_favorited=true`。4005 保留给未来非幂等场景（MVP 不用）。

### 4.4 后端处理

1. 按 id 查 `speaking_questions`，校验 `status='published'`（否则 4001，含 disabled/draft 防探测）。
2. 事务内：
   - `INSERT INTO favorites(user_id, question_id) ON CONFLICT (user_id, question_id) DO NOTHING`（幂等，利用 `uq_favorites_user_question` 唯一约束）。
   - INSERT `user_activity_logs`(action='favorite_added', entity_type='question', entity_id)。
3. 返回 `{question_id, is_favorited: true}`。

---

## 5. DELETE /api/v1/questions/{id}/favorite

### 5.1 请求

```
DELETE /api/v1/questions/{id}/favorite
Authorization: Bearer <access_token>
```

无 Body。

**Path：** `id`（string，题目 ID）

### 5.2 响应（成功）

HTTP 200：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "question_id": "101",
    "is_favorited": false
  }
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `question_id` | string | 题目 ID |
| `is_favorited` | bool | 恒为 false（幂等：重复取消也返回 false） |

### 5.3 错误码

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 1001 | 422 | id 非合法数字 |
| 2001/2002/2004/2005 | 401/403/401 | 认证失败 |

> **不返回 4001 / 4006**：取消收藏操作幂等，无论题目是否存在、是否已收藏，均返回 `is_favorited=false`。理由：取消收藏是"确保不在收藏夹"，无需校验题目状态。

### 5.4 后端处理

1. 事务内：
   - `DELETE FROM favorites WHERE user_id=current AND question_id=?`（无影响行也视为成功）。
   - 若实际删除了行（ROW_COUNT > 0），INSERT `user_activity_logs`(action='favorite_removed', entity_type='question', entity_id)。
2. 返回 `{question_id, is_favorited: false}`。

---

## 6. 安全与约束汇总

### 6.1 可见性

- 用户端仅可见 `status='published'` 题目。
- `disabled` 题目详情访问返回 4002（明确"已下架"）。
- `draft` 题目详情访问返回 4001（草稿等同不存在，不暴露存在性）。
- 收藏/取消收藏接口对 `disabled`/`draft` 题目：POST 收藏返回 4001（防探测），DELETE 取消不校验题目状态（幂等）。

### 6.2 幂等性

- POST 收藏：幂等（`ON CONFLICT DO NOTHING`），重复返回成功。
- DELETE 取消：幂等（无行删除也成功）。

### 6.3 不暴露字段

- 用户端不返回：`created_by`、`updated_at`、`status`（恒 published）。
- 用户端返回：`source_type` / `source_name`（版权透明，PROJECT_SPEC §12）。

### 6.4 资源所有权

- 收藏天然绑定当前用户（`favorites.user_id = current`），无路径参数防越权问题。
- 不存在"查看他人收藏"接口（隐私）。

### 6.5 活动日志

- 记录：`favorite_added`（实际新增时）、`favorite_removed`（实际删除时）。
- 不记录：题目浏览（非关键行为，ADR-023 精简原则）。

---

## 7. DTO 速查

### 7.1 响应 DTO

```text
QuestionListItem:
  id: str
  part: int
  title: str
  topic: TopicRef
  difficulty: int | None
  is_favorited: bool
  practice_count: int
  created_at: str

QuestionDetail:                   # extends QuestionListItem
  content: str
  cue_card: str | None
  tags: TagRef[]
  source_type: str
  source_name: str
  # + QuestionListItem 所有字段

TopicRef:
  id: str
  name: str

TagRef:
  id: str
  name: str

FavoriteResponse:
  question_id: str
  is_favorited: bool

PaginatedData<QuestionListItem>:  # common.md §4.2
  items: QuestionListItem[]
  total: int
  page: int
  page_size: int
  total_pages: int
```

### 7.2 无独立请求 DTO

- GET 列表：Query 参数（§2.1）。
- GET 详情 / POST 收藏 / DELETE 取消：仅 Path 参数，无 Body。

---

## 8. 与其他模块的衔接

| 衔接点 | 说明 |
| --- | --- |
| `admin.md` | 管理员题目/主题/标签 CRUD（用户端只读 published） |
| `practice.md` | "开始练习"从题目详情页跳转，调用 `POST /practice/sessions` |
| `home.md` | 推荐规则引用 `practice_count`（popular 排序）+ 收藏未练习题目 |
| `learning.md` | 主题分布统计依赖 `topic.name` |
| `common.md` §4 | 分页结构 |
| `database-design.md` §3.2 | 题库域表结构 |

---

## 9. ADR 引用

| ADR | 内容 | 本文位置 |
| --- | --- | --- |
| ADR-010 | 题目软停用，仅 published 可见 | §1.4 / §3.4 / §6.1 |
| ADR-019 | topic_id NOT NULL | §1.4 |
| ADR-023 | 活动日志精简 | §6.5 |
| ADR-025 | id 序列化为字符串 | 全文 |
| ADR-026 | snake_case | 全文 |

---

## 变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-07-23 | 初始创建：列表(筛选+分页+排序) + 详情 + 收藏(POST/DELETE) 共 4 接口；published 可见性；收藏幂等；practice_count 统计；不暴露 created_by/status |

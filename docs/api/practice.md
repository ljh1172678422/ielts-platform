# API 契约 — 练习模块（practice.md）

> 本文定义练习模块接口契约：会话、答题、录音上传/下载。
> **严格遵守 [common.md](file:///workspace/docs/api/common.md) v0.1**，录音上传流程严格对齐 [system-architecture.md §5.1](file:///workspace/docs/architecture/system-architecture.md) 序列图与 §5.2/5.3/5.4 状态机。
> 对应规格：`PROJECT_SPEC.md` v0.5 §4/§5 / `database-design.md` v0.4 §3.3。

---

## 0. 文档定位

本文回答："练习会话怎么创建/进行/完成，答题怎么记录，录音怎么上传/下载，状态怎么转。"
不回答："状态机有哪些状态。" → [system-architecture.md §5.2/5.3/5.4](file:///workspace/docs/architecture/system-architecture.md)。
不回答："统一响应/分页/错误码段。" → [common.md](file:///workspace/docs/api/common.md)。

---

## 1. 模块概述

### 1.1 职责

- 创建练习会话（按条件抽题）
- 获取会话详情（含题目快照列表）
- 创建答题尝试（attempt）
- 更新答题状态（录音中/跳过/失败）
- 上传录音（核心，对齐 §5.1 序列图）
- 下载录音
- 完成会话

### 1.2 路由表

| Method | Path | 鉴权 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/v1/practice/sessions` | Bearer | 创建练习会话 |
| GET | `/api/v1/practice/sessions/{id}` | Bearer | 获取会话详情（含题目） |
| POST | `/api/v1/practice/sessions/{id}/complete` | Bearer | 完成会话 |
| POST | `/api/v1/practice/attempts` | Bearer | 创建答题尝试 |
| PATCH | `/api/v1/practice/attempts/{attempt_id}` | Bearer | 更新答题状态 |
| POST | `/api/v1/practice/attempts/{attempt_id}/recording` | Bearer | 上传录音 |
| GET | `/api/v1/practice/attempts/{attempt_id}/recording` | Bearer | 下载录音 |

### 1.3 涉及数据表

| 表 | 用途 |
| --- | --- |
| `practice_sessions` | 会话主表 |
| `practice_session_questions` | 会话题目快照（含 `question_snapshot` JSONB） |
| `practice_attempts` | 答题尝试（含 `attempt_number`） |
| `recordings` | 录音元数据 |
| `speaking_questions` | 抽题来源（仅 published） |
| `study_records` | 同步更新（ADR-022） |
| `user_activity_logs` | 行为记录 |

### 1.4 核心事实链与状态约束

**事实链（ADR-006/007，锁定）：**

```text
Session → SessionQuestion → Attempt → Recording
```

**跨表状态约束（ADR-015，service 层校验）：**

| 约束 | 校验点 | 违反码 |
| --- | --- | --- |
| `attempt.submitted` ⇒ 存在 `recording.uploaded` | 录音上传事务内，先 uploaded 再 submitted | 5006 |
| `session.completed` ⇒ 全部 sq 有 submitted/skipped attempt | 完成会话接口 | 5002 |
| `POST recording` ⇒ `attempt.status ∈ {pending, recording}` | 录音上传前 | 5006 |

---

## 2. POST /api/v1/practice/sessions

### 2.1 请求

```
POST /api/v1/practice/sessions
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Body：**

| 字段 | 类型 | 必填 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `mode` | string | 是 | `random` / `topic` / `part` | 练习模式 |
| `part` | int | 否 | 1 / 2 / 3 | mode=random/part 时指定；不传=全部 Part |
| `topic_id` | string | 否 | 字符串化 ID | mode=random/topic 时指定；不传=全部主题 |
| `question_count` | int | 是 | 1..50 | 抽题数量 |

> `mode` 语义：
> - `random`：全题库随机抽（可叠加 part/topic 过滤）。
> - `topic`：指定 topic_id 抽（part 可选叠加）。
> - `part`：指定 part 抽（topic_id 不传）。

**示例：**

```json
{
  "mode": "topic",
  "part": 2,
  "topic_id": "5",
  "question_count": 5
}
```

### 2.2 响应（成功）

HTTP 200，`data` 为新建 `PracticeSession`（含题目列表）：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": "201",
    "status": "created",
    "mode": "topic",
    "part_filter": 2,
    "topic_filter": "5",
    "question_count": 5,
    "started_at": null,
    "completed_at": null,
    "duration_seconds": null,
    "created_at": "2026-07-23T12:00:00+00:00",
    "updated_at": "2026-07-23T12:00:00+00:00",
    "questions": [
      {
        "id": "301",
        "session_id": "201",
        "question_id": "101",
        "sort_order": 1,
        "snapshot": {
          "part": 2,
          "title": "Describe a useful object",
          "content": "You will have to talk about...",
          "cue_card": "You should say:...",
          "topic_name": "Technology",
          "difficulty": 3
        },
        "attempts": []
      }
    ]
  }
}
```

**PracticeSession：**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 会话 ID |
| `status` | string | `created` / `in_progress` / `completed` / `abandoned` / `expired` |
| `mode` | string | 练习模式 |
| `part_filter` | int \| null | 创建时的 part 过滤（快照） |
| `topic_filter` | string \| null | 创建时的 topic_id 过滤（快照，字符串化） |
| `question_count` | int | 抽题数量 |
| `started_at` | string \| null | 首次进入 in_progress 时间 |
| `completed_at` | string \| null | 完成时间 |
| `duration_seconds` | int \| null | 会话时长（completed 时填，= completed_at - started_at，仅作展示，**统计口径用录音时长**，ADR-016） |
| `created_at` / `updated_at` | string | ISO 8601 |
| `questions` | SessionQuestion[] | 会话题目列表（按 sort_order） |

**SessionQuestion：**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | session_question ID |
| `session_id` | string | 所属会话 |
| `question_id` | string | 原题目 ID（用于跳转详情） |
| `sort_order` | int | 顺序 |
| `snapshot` | object | 题目快照（不可变，ADR-016，含 part/title/content/cue_card/topic_name/difficulty） |
| `attempts` | Attempt[] | 该 sq 的答题尝试列表（新建会话时为空 `[]`） |

### 2.3 错误码

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 1001 | 422 | mode 非法 / question_count 越界 / part 非法 |
| 4003 | 404 | mode=topic 但 topic_id 不存在 |
| 5004 | 400 | 题目数量不足（可用题数 < question_count） |
| 2001/2002/2004/2005 | 401/403/401 | 认证失败 |

### 2.4 后端处理（事务）

1. Pydantic 校验。
2. 若 mode=topic，校验 topic_id 存在且非 Other 系统保留误用（Other 可正常练习，仅 admin 不可删）→ 不存在 → 4003。
3. 构建基础查询：`speaking_questions WHERE status='published'`。
   - 叠加 part 过滤（若有）。
   - 叠加 topic_id 过滤（若有）。
4. 统计可用题数 → `< question_count` → **5004**。
5. 随机抽取 `question_count` 题（`ORDER BY RANDOM() LIMIT n`）。
6. 事务内：
   - INSERT `practice_sessions`(user_id, mode, part_filter, topic_filter, question_count, status='created')。
   - 对每题：
     - 构造 `question_snapshot` JSONB（含 part/title/content/cue_card/topic_name/difficulty，PROJECT_SPEC §4.5.5）。
     - INSERT `practice_session_questions`(session_id, question_id, question_snapshot, sort_order=1..n)。
   - INSERT `user_activity_logs`(action='practice_started', entity_type='practice_session', entity_id=new_session_id)。
7. 返回完整 `PracticeSession`（含 questions，attempts 为空）。

> **不在创建时自动 in_progress**：会话创建后 `status='created'`，用户首次创建 attempt 时（§4）才转 `in_progress` 并填 `started_at`。

---

## 3. GET /api/v1/practice/sessions/{id}

### 3.1 请求

```
GET /api/v1/practice/sessions/{id}
Authorization: Bearer <access_token>
```

### 3.2 响应（成功）

HTTP 200，`data` 为 `PracticeSession`（结构同 §2.2），`questions[].attempts` 含已有尝试列表（按 attempt_number）。

**Attempt：**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | attempt ID |
| `session_question_id` | string | 所属 sq |
| `attempt_number` | int | 第几次尝试（1 起） |
| `status` | string | `pending` / `recording` / `submitted` / `skipped` / `failed` |
| `started_at` | string \| null | 进入 recording 时间 |
| `submitted_at` | string \| null | submitted/skipped 时间 |
| `duration_seconds` | int \| null | attempt 时长（= recording.duration_seconds，若有录音） |
| `recording` | Recording \| null | 关联录音（MVP 1:1，ADR-007） |

**Recording：**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 录音 ID |
| `status` | string | `uploading` / `uploaded` / `failed` / `deleted` |
| `mime_type` | string | 如 `audio/webm` |
| `duration_seconds` | int \| null | 后端读元数据计算（ADR-020） |
| `file_size` | int \| null | 字节 |
| `created_at` | string | ISO 8601 |

### 3.3 错误码

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 1001 | 422 | id 非合法数字 |
| 2001/2002/2004/2005 | 401/403/401 | 认证失败 |
| 5001 | 404 | 会话不存在 |
| 5003 | 403 | 会话不属于当前用户 |

### 3.4 后端处理

1. 按 id 查 `practice_sessions` → 不存在 → 5001。
2. 校验 `session.user_id == current` → 否 → 5003（明确越权，区分 5001 防探测与 5003 防越权）。
3. 查 `practice_session_questions`（按 sort_order）。
4. 对每个 sq 查 `practice_attempts`（按 attempt_number），LEFT JOIN `recordings`。
5. 组装返回。

### 3.5 续练场景

- 用户关闭浏览器后重开，调此接口恢复会话状态。
- `status='in_progress'` 的会话可继续；`completed`/`abandoned`/`expired` 仅可查看不可操作。
- 前端按 `questions[].attempts[-1].status` 判断每题进度。

---

## 4. POST /api/v1/practice/attempts

### 4.1 请求

```
POST /api/v1/practice/attempts
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Body：**

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `session_question_id` | string | 是 | 会话题目 ID |

无其他字段。`attempt_number` 由后端递增分配。

### 4.2 响应（成功）

HTTP 200，`data` 为新建 `Attempt`（status='pending'，recording=null）：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": "401",
    "session_question_id": "301",
    "attempt_number": 1,
    "status": "pending",
    "started_at": null,
    "submitted_at": null,
    "duration_seconds": null,
    "recording": null
  }
}
```

### 4.3 错误码

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 1001 | 422 | session_question_id 缺失/非合法数字 |
| 5001 | 404 | 会话不存在（sq 关联的 session 不存在） |
| 5003 | 403 | 会话不属于当前用户 |
| 5002 | 400 | 会话状态非 in_progress（created 需先激活，completed/abandoned/expired 不可操作） |
| 5007 | 404 | session_question 不存在 |

### 4.4 后端处理（事务）

1. 按 session_question_id 查 `practice_session_questions` → 不存在 → 5007。
2. JOIN `practice_sessions` → 不存在 → 5001；`user_id != current` → 5003。
3. 校验 session.status：
   - `created` → 自动转 `in_progress`，填 `started_at=NOW()`（首次创建 attempt 触发激活）。
   - `in_progress` → 继续。
   - `completed`/`abandoned`/`expired` → **5002**。
4. 事务内：
   - 若 session 从 created→in_progress，UPDATE session。
   - 计算 `attempt_number = MAX(attempt_number) + 1`（无则 1）。
   - INSERT `practice_attempts`(session_question_id, user_id, attempt_number, status='pending')。
   - 部分唯一索引 `uq_attempts_session_question_num` 兜底并发。
   - INSERT `user_activity_logs`(action='attempt_created', entity_type='practice_attempt', entity_id)。
5. 返回 Attempt。

> **支持同题重录**：同一 sq 可多次创建 attempt（attempt_number 递增），用于"重新录音"场景。每次新 attempt 从 pending 开始。

---

## 5. PATCH /api/v1/practice/attempts/{attempt_id}

### 5.1 请求

```
PATCH /api/v1/practice/attempts/{attempt_id}
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Body（局部更新）：**

| 字段 | 类型 | 必填 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `status` | string | 是 | `recording` / `skipped` / `failed` | 目标状态 |

> **不允许通过此接口直接设 `submitted`**：submitted 只能由录音上传成功后由后端设置（ADR-015，§6.4）。
> 若请求 `status='submitted'` → 1001（参数非法）。

**示例（开始录音）：**

```json
{ "status": "recording" }
```

**示例（跳过）：**

```json
{ "status": "skipped" }
```

### 5.2 响应（成功）

HTTP 200，`data` 为更新后的 `Attempt`。

### 5.3 状态转换规则

```text
pending → recording      ✅ 允许（用户开始录音）
pending → skipped        ✅ 允许（直接跳过，不录音）
recording → skipped      ✅ 允许（录音中放弃改跳过）
recording → failed       ✅ 允许（前端检测录音失败，如麦克风断开）
其他转换                  ❌ 5006
→ submitted              ❌ 1001（必须走录音上传接口）
```

### 5.4 错误码

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 1001 | 422 | status 缺失 / 非法值 / 传 submitted |
| 5005 | 404 | attempt 不存在 |
| 5003 | 403 | attempt 不属于当前用户 |
| 5006 | 400 | 状态转换非法（如 submitted→recording） |
| 2001/2002/2004/2005 | 401/403/401 | 认证失败 |

### 5.5 后端处理（事务）

1. 按 attempt_id 查 → 不存在 → 5005。
2. 校验 `attempt.user_id == current` → 否 → 5003。
3. 校验 session.status='in_progress'（间接，通过 sq→session）→ 否 → 5002。
4. 校验状态转换合法性（§5.3）→ 非法 → 5006。
5. 事务内：
   - UPDATE attempt.status，按目标状态填时间戳：
     - → recording：`started_at=NOW()`。
     - → skipped：`submitted_at=NOW()`。
     - → failed：不填 submitted_at。
   - 若 → skipped，INSERT `user_activity_logs`(action='attempt_skipped')。
6. 返回更新后 Attempt。

---

## 6. POST /api/v1/practice/attempts/{attempt_id}/recording

> **核心接口**，严格对齐 [system-architecture.md §5.1](file:///workspace/docs/architecture/system-architecture.md) 录音上传序列图。

### 6.1 请求

```
POST /api/v1/practice/attempts/{attempt_id}/recording
Authorization: Bearer <access_token>
Content-Type: multipart/form-data
```

**Form field：**

| 字段 | 类型 | 必填 | 约束 |
| --- | --- | --- | --- |
| `file` | binary | 是 | audio/webm / audio/mp4 / audio/mpeg / audio/wav，≤ 50MB |

无其他字段。`duration_seconds` 由后端读元数据计算（ADR-020），**不接受前端传入**。

### 6.2 响应（成功）

HTTP 200，`data` 为更新后的 `Attempt`（含 recording，status='submitted'）：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": "401",
    "session_question_id": "301",
    "attempt_number": 1,
    "status": "submitted",
    "started_at": "2026-07-23T12:01:00+00:00",
    "submitted_at": "2026-07-23T12:02:30+00:00",
    "duration_seconds": 86,
    "recording": {
      "id": "501",
      "status": "uploaded",
      "mime_type": "audio/webm",
      "duration_seconds": 86,
      "file_size": 1234567,
      "created_at": "2026-07-23T12:02:30+00:00"
    }
  }
}
```

> `attempt.duration_seconds` = `recording.duration_seconds`（后端读元数据所得）。

### 6.3 错误码

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 1001 | 422 | file 字段缺失 |
| 5005 | 404 | attempt 不存在 |
| 5003 | 403 | attempt 不属于当前用户 |
| 5006 | 400 | attempt.status ∉ {pending, recording}（如已 submitted/skipped） |
| 6003 | 400 | mime_type 不在白名单 |
| 6004 | 413 | 文件 > 50MB |
| 6002 | 400 | 文件写入/元数据读取失败（recording 标 failed） |
| 2001/2002/2004/2005 | 401/403/401 | 认证失败 |

### 6.4 后端处理（事务，严格对齐 §5.1 序列图）

```text
1. 按 attempt_id 查 → 不存在 → 5005
2. 校验 attempt.user_id == current → 否 → 5003
3. 校验 attempt.status ∈ {pending, recording} → 否 → 5006
   (submitted/skipped/failed 不可再上传，需新建 attempt 重录)
4. 校验 file：
   a. mime_type ∈ {audio/webm, audio/mp4, audio/mpeg, audio/wav} → 否 → 6003
   b. file_size ≤ 50MB → 否 → 6004
5. 事务开始：
   a. 写文件到存储（local FS: /storage/recordings/<yyyy>/<mm>/<uuid>.<ext>）
      失败 → 事务回滚，返回 6002
   b. 读音频元数据 → duration_seconds（ADR-020，不信前端）
      失败 → 删除已写文件，事务回滚，返回 6002
   c. INSERT recordings(attempt_id, user_id, storage_type, storage_path,
                        mime_type, duration_seconds, file_size, status='uploading')
   d. UPDATE recordings SET status='uploaded', updated_at=NOW()
   e. UPDATE practice_attempts SET status='submitted', submitted_at=NOW(),
                        duration_seconds=<recording.duration_seconds>
      —— ADR-015: submitted 前置 recording.uploaded 已满足
   f. UPSERT study_records（同步更新，ADR-022）：
      - record_date = 按 user_profiles.timezone 切日（ADR-018）
      - practice_count += 0 (session 不变)
      - attempt_count += 1
      - recording_count += 1
      - duration_seconds += <recording.duration_seconds>
      - question_count += 1 (该 attempt 所属 sq 视为已答题)
   g. INSERT user_activity_logs(action='recording_uploaded',
        entity_type='recording', entity_id=new_recording_id,
        metadata={duration_seconds, file_size})
6. 事务提交（任一步失败全回滚：attempt 退回原 status，recording 不留痕或标 failed）
7. 返回更新后 Attempt（含 recording）
```

> **事务边界**：步骤 5a–5g 在同一事务内。文件写入与 DB 事务的协调：
> - 文件先写临时位置，事务提交后再 rename 到最终路径（避免事务回滚但文件残留）。
> - 若事务回滚，删除临时文件。
> - MVP 接受此简化协调，未来用 outbox 模式优化（非 MVP）。

### 6.5 重新录音

- 已 submitted 的 attempt 不可再上传（5006）。
- 用户想重录：调 `POST /practice/attempts`（§4）新建 attempt（attempt_number+1），再走录音流程。
- 旧 attempt 的 recording 保留（不自动删除），用户可显式删除（未来接口，MVP 不提供录音删除 API，recording.status 仅由系统流转）。

---

## 7. GET /api/v1/practice/attempts/{attempt_id}/recording

### 7.1 请求

```
GET /api/v1/practice/attempts/{attempt_id}/recording
Authorization: Bearer <access_token>
```

### 7.2 响应（成功）

HTTP 200，**直接返回音频流**（非统一响应结构，common.md §2.3 例外）：

```
Content-Type: audio/webm
Content-Length: 1234567
Content-Disposition: inline

<binary audio stream>
```

> 录音下载是文件流接口，不走 `{code, message, data}` 包装，直接 StreamingResponse（common.md §2.4 不适用此例外场景，需在 common.md §2.3 补充说明——但此处不修改 common.md，仅在本接口声明例外）。

### 7.3 错误码

> 错误时仍走统一响应结构：

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 5005 | 404 | attempt 不存在 |
| 5003 | 403 | attempt 不属于当前用户 |
| 6001 | 404 | 录音不存在（attempt 无 recording，或 recording.status='deleted'） |
| 2001/2002/2004/2005 | 401/403/401 | 认证失败 |

### 7.4 后端处理

1. 按 attempt_id 查 → 不存在 → 5005。
2. 校验 `attempt.user_id == current` → 否 → 5003。
3. 查 `recordings` WHERE attempt_id=? AND status='uploaded'（deleted 不返回）→ 不存在 → 6001。
4. 读存储文件 → StreamingResponse，Content-Type = recording.mime_type。

---

## 8. POST /api/v1/practice/sessions/{id}/complete

### 8.1 请求

```
POST /api/v1/practice/sessions/{id}/complete
Authorization: Bearer <access_token>
```

无 Body。

### 8.2 响应（成功）

HTTP 200，`data` 为更新后的 `PracticeSession`（status='completed'，含 duration_seconds）：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": "201",
    "status": "completed",
    "mode": "topic",
    "part_filter": 2,
    "topic_filter": "5",
    "question_count": 5,
    "started_at": "2026-07-23T12:00:00+00:00",
    "completed_at": "2026-07-23T12:30:00+00:00",
    "duration_seconds": 1800,
    "created_at": "2026-07-23T12:00:00+00:00",
    "updated_at": "2026-07-23T12:30:00+00:00",
    "questions": [ ... ]
  }
}
```

> `duration_seconds` = `completed_at - started_at`（会话墙钟时长，**仅展示用**；统计口径用录音时长总和，ADR-016）。

### 8.3 错误码

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 5001 | 404 | 会话不存在 |
| 5003 | 403 | 会话不属于当前用户 |
| 5002 | 400 | 状态非法（非 in_progress 不能 complete） |
| 5006 | 400 | ADR-015 违反：存在 sq 无 submitted/skipped attempt |
| 2001/2002/2004/2005 | 401/403/401 | 认证失败 |

### 8.4 后端处理（事务）

1. 按 id 查 → 不存在 → 5001。
2. 校验 `session.user_id == current` → 否 → 5003。
3. 校验 `session.status='in_progress'` → 否 → 5002（created 需先创建 attempt 激活；completed/abandoned/expired 不可重复完成）。
4. **ADR-015 校验**：遍历所有 session_questions，每个 sq 至少有一个 attempt.status ∈ {submitted, skipped}。
   - 任一 sq 不满足 → **5006**（返回 details 含未完成的 sq_id 列表）。
5. 事务内：
   - UPDATE session SET status='completed', completed_at=NOW(), duration_seconds=EXTRACT(EPOCH FROM (NOW() - started_at))。
   - UPSERT study_records：practice_count += 1（会话完成才计一次完整练习）。
   - INSERT `user_activity_logs`(action='practice_completed', entity_type='practice_session', entity_id)。
6. 返回完整 PracticeSession。

> **study_records 增量说明**：
> - 录音上传时（§6.4）：attempt_count++、recording_count++、duration_seconds += 录音时长、question_count++。
> - 会话完成时（本接口）：practice_count++。
> - 两者独立增量，不重复计算。

---

## 9. 安全与约束汇总

### 9.1 资源所有权

- 所有接口校验 `session.user_id == current` 或 `attempt.user_id == current`，越权 → 5003。
- 不存在"查看他人练习"接口（隐私）。

### 9.2 状态机不可绕过

- `submitted` 只能由录音上传事务设置，前端不可直接 PATCH（§5.1）。
- `session.completed` 必须满足 ADR-015（§8.4）。
- 已终态（submitted/skipped/failed/completed）的状态不可回退，需新建 attempt/session。

### 9.3 录音安全

- mime 白名单 + 大小限制（6003/6004）。
- duration 后端计算（ADR-020），不信前端。
- 文件存储路径用 UUID，不暴露原文件名。
- 下载仅限 attempt 所属用户。

### 9.4 活动日志

- 记录：`practice_started` / `practice_completed` / `attempt_created` / `attempt_skipped` / `recording_uploaded`。
- 不记录：`attempt→recording`（中间态）、`session GET`（浏览，非关键）。

### 9.5 study_records 同步更新（ADR-022）

- 录音上传事务（§6.4）与会话完成事务（§8.4）均同步 upsert study_records。
- 架构上抽象为 `learning.service.record_event(event)`，未来切消息队列不改业务模型（ADR-022）。
- 统计异常时可从事实表重算（learning.md 定义重算接口）。

---

## 10. DTO 速查

### 10.1 请求 DTO

```text
CreateSessionRequest:
  mode: str  # random/topic/part
  part: int | None  # 1/2/3
  topic_id: str | None
  question_count: int  # 1..50

CreateAttemptRequest:
  session_question_id: str

UpdateAttemptRequest:
  status: str  # recording/skipped/failed (NOT submitted)
```

### 10.2 响应 DTO

```text
PracticeSession:
  id: str
  status: str
  mode: str
  part_filter: int | None
  topic_filter: str | None
  question_count: int
  started_at: str | None
  completed_at: str | None
  duration_seconds: int | None
  created_at: str
  updated_at: str
  questions: SessionQuestion[]

SessionQuestion:
  id: str
  session_id: str
  question_id: str
  sort_order: int
  snapshot: QuestionSnapshot  # {part,title,content,cue_card,topic_name,difficulty}
  attempts: Attempt[]

Attempt:
  id: str
  session_question_id: str
  attempt_number: int
  status: str
  started_at: str | None
  submitted_at: str | None
  duration_seconds: int | None
  recording: Recording | None

Recording:
  id: str
  status: str
  mime_type: str
  duration_seconds: int | None
  file_size: int | None
  created_at: str
```

---

## 11. 与其他模块的衔接

| 衔接点 | 说明 |
| --- | --- |
| `questions.md` | session 创建时抽题来自 published questions |
| `learning.md` | study_records 同步更新 + 重算接口 |
| `home.md` | 推荐规则引用未完成 session（status ∈ {created, in_progress}） |
| `common.md` §6 | 录音上传 mime/大小限制 |
| `system-architecture.md` §5.1 | 录音上传序列图（本文 §6.4 严格对齐） |
| `system-architecture.md` §5.2/5.3/5.4 | 状态机（本文 §5.3 引用） |

---

## 12. ADR 引用

| ADR | 内容 | 本文位置 |
| --- | --- | --- |
| ADR-006 | Attempt 模型 | §1.4 / §4 / §6.5 |
| ADR-007 | Recording 绑定 Attempt | §3.2 / §6 |
| ADR-015 | 跨表状态约束 | §1.4 / §5.1 / §6.4 / §8.4 |
| ADR-016 | duration 口径（录音时长，非 session 时长） | §2.2 / §8.2 |
| ADR-018 | timezone 切日 | §6.4 |
| ADR-020 | duration 后端计算 | §6.1 / §6.4 |
| ADR-022 | study_records 同步更新 | §6.4 / §8.4 / §9.5 |
| ADR-025 | id 序列化为字符串 | 全文 |
| ADR-026 | snake_case | 全文 |

---

## 变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-07-23 | 初始创建：7 接口（session 创建/获取/完成 + attempt 创建/更新 + recording 上传/下载）；严格对齐 system-architecture §5.1 录音上传序列图；ADR-015 跨表约束落地；ADR-020 duration 后端计算；ADR-022 study_records 同步更新；submitted 不可前端直设 |

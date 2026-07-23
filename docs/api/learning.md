# API 契约 — 学习数据模块（learning.md）

> 本文定义学习数据模块接口契约：概览、趋势、分布、重算。
> **严格遵守 [common.md](file:///workspace/docs/api/common.md) v0.1**。
> 对应规格：`PROJECT_SPEC.md` v0.5 §6 / `database-design.md` v0.4 §3.4 / `system-architecture.md` v0.1 §5.5。

---

## 0. 文档定位

本文回答："学习数据怎么读、怎么算、怎么重算。"
不回答："study_records 怎么写入。" → [practice.md §6.4/§8.4](file:///workspace/docs/api/practice.md)。
不回答："统一响应/分页结构。" → [common.md](file:///workspace/docs/api/common.md)。

---

## 1. 模块概述

### 1.1 职责

- 学习概览（今日/连续/累计）
- 趋势统计（日/周/月）
- 分布统计（Part 分布 / 主题分布）
- 统计重算（管理员，基于事实表，ADR-008）

### 1.2 路由表

| Method | Path | 鉴权 | 角色 | 说明 |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/learning/overview` | Bearer | user | 学习概览 |
| GET | `/api/v1/learning/daily` | Bearer | user | 日趋势 |
| GET | `/api/v1/learning/weekly` | Bearer | user | 周趋势 |
| GET | `/api/v1/learning/monthly` | Bearer | user | 月趋势 |
| GET | `/api/v1/learning/topics` | Bearer | user | 主题分布 |
| GET | `/api/v1/learning/parts` | Bearer | user | Part 分布 |
| POST | `/api/v1/learning/recompute` | Bearer | admin | 重算 study_records |

### 1.3 涉及数据表

| 表 | 用途 |
| --- | --- |
| `study_records` | 聚合数据读取（ADR-008，可重算，非事实来源） |
| `practice_sessions` | 事实来源（重算 + 实时统计） |
| `practice_attempts` | 事实来源（重算 + 实时统计） |
| `recordings` | 事实来源（duration 聚合） |
| `practice_session_questions` | 分布统计（topic/part 快照） |
| `user_profiles` | timezone 切日（ADR-018） |

### 1.4 核心原则

- **ADR-008**：`study_records` 是聚合缓存，非事实来源；统计异常时可从事实表重算。
- **ADR-016**：`duration_seconds` 口径 = `SUM(recordings.duration_seconds WHERE status='uploaded')`，**非 session 时长**。
- **ADR-018**：所有按日切分（today/本周/本月/连续天数）基于 `user_profiles.timezone`，非 UTC。
- **ADR-022**：`study_records` 由录音上传/会话完成事务同步更新（practice.md §6.4/§8.4），本模块只读 + 重算。

---

## 2. GET /api/v1/learning/overview

### 2.1 请求

```
GET /api/v1/learning/overview
Authorization: Bearer <access_token>
```

无 Query / Body。

### 2.2 响应（成功）

HTTP 200：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "today": {
      "practice_count": 1,
      "question_count": 5,
      "attempt_count": 5,
      "recording_count": 5,
      "duration_seconds": 432
    },
    "streak": {
      "current_days": 7,
      "longest_days": 23
    },
    "cumulative": {
      "total_sessions": 42,
      "total_questions": 198,
      "total_attempts": 210,
      "total_recordings": 195,
      "total_duration_seconds": 16830
    },
    "goal_progress": {
      "daily_goal_minutes": 60,
      "daily_completed_minutes": 7.2,
      "weekly_goal_minutes": 360,
      "weekly_completed_minutes": 52.5
    }
  }
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `today.*` | — | 今日统计（按 user timezone 切日） |
| `streak.current_days` | int | 连续学习天数（今日有数据则计今日） |
| `streak.longest_days` | int | 历史最长连续天数 |
| `cumulative.*` | — | 累计统计（全量，不限时区切日） |
| `goal_progress.*` | — | 目标达成度（来自 active `user_goals`，无 active goal 时各字段 null） |

> `duration` 单位为秒，前端自行转分钟展示（`daily_completed_minutes` 字段名是便于前端直读的语义化字段，值为秒/60 保留 1 位小数）。

### 2.3 错误码

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 2001/2002/2004/2005 | 401/403/401 | 认证失败 |

### 2.4 后端处理

1. 取 `user_profiles.timezone`（缺失默认 `Asia/Shanghai`）。
2. **today**：查 `study_records` WHERE user_id=current AND record_date = today_in_timezone。
3. **streak**：
   - 查最近 N 天的 `study_records`（record_date DESC）。
   - 从今日（或昨日，若今日无数据则从昨日开始计 current_days）向前回溯连续有记录的天数 = `current_days`。
   - `longest_days`：查 `study_records` 全部 record_date，计算最长连续段（MVP 可一次性查全量内存计算，用户量小）。
4. **cumulative**：`SUM` 聚合 `study_records` 全部记录。
5. **goal_progress**：查 active `user_goals`，取 daily/weekly_goal_minutes，对比今日/本周 study_records 聚合。
6. 组装返回。

> **streak 算法说明**（ADR-018 时区敏感）：
> - "今日" = `record_date` 在 user timezone 下的今天。
> - 若今日无 study_record，`current_days` 可能为 0（不算今日，从昨日向前算）；但若昨日有数据，streak 仍可非 0（防止用户晚 23:59 练习跨午夜断算）。
> - MVP 简化：今日有数据 current_days 从今日起算；今日无数据 current_days=0。

---

## 3. GET /api/v1/learning/daily

### 3.1 请求

```
GET /api/v1/learning/daily?days=30
Authorization: Bearer <access_token>
```

**Query：**

| 参数 | 类型 | 默认 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `days` | int | 30 | 1..90 | 返回最近 N 天（含今日） |

### 3.2 响应（成功）

HTTP 200：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "granularity": "daily",
    "timezone": "Asia/Shanghai",
    "points": [
      {
        "date": "2026-07-23",
        "practice_count": 1,
        "question_count": 5,
        "attempt_count": 5,
        "recording_count": 5,
        "duration_seconds": 432
      },
      {
        "date": "2026-07-22",
        "practice_count": 2,
        "question_count": 8,
        "attempt_count": 9,
        "recording_count": 8,
        "duration_seconds": 720
      }
    ]
  }
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `granularity` | string | 恒为 `"daily"` |
| `timezone` | string | 切日所用时区（透明告知前端） |
| `points[].date` | string | `YYYY-MM-DD`（user timezone 下的日期） |
| `points[].*` | — | 当日聚合（来自 study_records） |

> **缺失日期补零**：若某天无 study_record，仍返回该 date 的 point，所有计数为 0、duration_seconds=0。便于前端图表连续渲染。

### 3.3 错误码

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 1001 | 422 | days 越界 |
| 2001/2002/2004/2005 | 401/403/401 | 认证失败 |

### 3.4 后端处理

1. 取 timezone。
2. 计算今日 date（timezone 切日）。
3. 查 `study_records` WHERE user_id=current AND record_date BETWEEN today-(days-1) AND today。
4. 在内存中补齐缺失日期（全 0）。
5. 按 date ASC 返回。

---

## 4. GET /api/v1/learning/weekly

### 4.1 请求

```
GET /api/v1/learning/weekly?weeks=12
Authorization: Bearer <access_token>
```

**Query：**

| 参数 | 类型 | 默认 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `weeks` | int | 12 | 1..52 | 返回最近 N 周（含本周） |

> **周定义**：周一到周日（ISO 8601），按 user timezone 切日。本周 = 含今日的周一~周日。

### 4.2 响应（成功）

HTTP 200：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "granularity": "weekly",
    "timezone": "Asia/Shanghai",
    "points": [
      {
        "week_start": "2026-07-20",
        "week_end": "2026-07-26",
        "practice_count": 5,
        "question_count": 22,
        "attempt_count": 24,
        "recording_count": 22,
        "duration_seconds": 1860
      }
    ]
  }
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `points[].week_start` | string | 周一日期 |
| `points[].week_end` | string | 周日日期 |
| `points[].*` | — | 该周聚合（study_records 按 record_date 分组求和） |

### 4.3 错误码

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 1001 | 422 | weeks 越界 |
| 2001/2002/2004/2005 | 401/403/401 | 认证失败 |

### 4.4 后端处理

1. 取 timezone，算本周一日期。
2. 查 `study_records` WHERE record_date BETWEEN 本周一-(weeks-1)*7 AND 本周日。
3. 在内存中按周分组求和，补齐无数据周（全 0）。
4. 按 week_start ASC 返回。

---

## 5. GET /api/v1/learning/monthly

### 5.1 请求

```
GET /api/v1/learning/monthly?months=12
Authorization: Bearer <access_token>
```

**Query：**

| 参数 | 类型 | 默认 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `months` | int | 12 | 1..24 | 返回最近 N 月（含本月） |

> **月定义**：自然月（1 日到月末），按 user timezone 切日。

### 5.2 响应（成功）

HTTP 200：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "granularity": "monthly",
    "timezone": "Asia/Shanghai",
    "points": [
      {
        "month": "2026-07",
        "practice_count": 18,
        "question_count": 78,
        "attempt_count": 85,
        "recording_count": 80,
        "duration_seconds": 6840
      }
    ]
  }
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `points[].month` | string | `YYYY-MM` |
| `points[].*` | — | 该月聚合 |

### 5.3 错误码

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 1001 | 422 | months 越界 |
| 2001/2002/2004/2005 | 401/403/401 | 认证失败 |

### 5.4 后端处理

同 weekly，按月分组（基于 record_date 的年月）。

---

## 6. GET /api/v1/learning/topics

### 6.1 请求

```
GET /api/v1/learning/topics?months=3
Authorization: Bearer <access_token>
```

**Query：**

| 参数 | 类型 | 默认 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `months` | int | 3 | 1..24 | 统计最近 N 月的主题分布 |

### 6.2 响应（成功）

HTTP 200：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "range_months": 3,
    "timezone": "Asia/Shanghai",
    "topics": [
      { "topic_id": "5", "topic_name": "Technology", "attempt_count": 24, "duration_seconds": 1980 },
      { "topic_id": "8", "topic_name": "Travel", "attempt_count": 15, "duration_seconds": 1200 },
      { "topic_id": "1", "topic_name": "Other", "attempt_count": 3, "duration_seconds": 240 }
    ]
  }
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `topics[].topic_id` | string | 主题 ID |
| `topics[].topic_name` | string | 主题名称（来自 question_snapshot，反映练习时的主题） |
| `topics[].attempt_count` | int | 该主题下的答题次数 |
| `topics[].duration_seconds` | int | 该主题下录音总时长 |

> **数据来源**：`practice_session_questions.question_snapshot.topic_name`（快照），通过 attempt → sq 关联。**不直接读 speaking_topics**（避免主题改名影响历史统计，与快照不可变原则一致）。

### 6.3 错误码

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 1001 | 422 | months 越界 |
| 2001/2002/2004/2005 | 401/403/401 | 认证失败 |

### 6.4 后端处理

1. 取 timezone，算 N 月前的起始 date。
2. 查 `practice_attempts`（WHERE user_id=current AND submitted_at >= 起始时间）JOIN `practice_session_questions` 取 snapshot.topic_name/topic_id。
3. JOIN `recordings`（status='uploaded'）取 duration。
4. GROUP BY topic_id, topic_name，COUNT(attempt)、SUM(duration)。
5. ORDER BY attempt_count DESC。
6. 返回。

> **为何不查 study_records**：study_records 是日聚合，不含主题维度（PROJECT_SPEC §4.4 study_records 字段无 topic）。主题分布必须从事实表实时聚合。

---

## 7. GET /api/v1/learning/parts

### 7.1 请求

```
GET /api/v1/learning/parts?months=3
Authorization: Bearer <access_token>
```

**Query：** 同 §6.1。

### 7.2 响应（成功）

HTTP 200：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "range_months": 3,
    "timezone": "Asia/Shanghai",
    "parts": [
      { "part": 1, "attempt_count": 30, "duration_seconds": 1500 },
      { "part": 2, "attempt_count": 45, "duration_seconds": 3600 },
      { "part": 3, "attempt_count": 12, "duration_seconds": 1440 }
    ]
  }
}
```

### 7.3 后端处理

同 topics，GROUP BY `question_snapshot.part`。Part 为整数（1/2/3），直接从 snapshot 取。

---

## 8. POST /api/v1/learning/recompute

> **管理员接口**，基于事实表重算 `study_records`（ADR-008）。

### 8.1 请求

```
POST /api/v1/learning/recompute
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Body（可选）：**

| 字段 | 类型 | 必填 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `user_id` | string | 否 | 字符串化 ID | 指定用户重算；不传 = 全量用户 |
| `start_date` | string | 否 | `YYYY-MM-DD` | 重算起始日（user timezone）；不传 = 全历史 |
| `end_date` | string | 否 | `YYYY-MM-DD` | 重算结束日；不传 = 至今 |

**示例（指定用户全历史）：**

```json
{ "user_id": "1001" }
```

**示例（全量用户某段时间）：**

```json
{
  "start_date": "2026-07-01",
  "end_date": "2026-07-23"
}
```

### 8.2 响应（成功）

HTTP 200：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "recomputed_users": 42,
    "recomputed_records": 380,
    "deleted_records": 5,
    "duration_seconds_total": 31200
  }
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `recomputed_users` | int | 重算的用户数 |
| `recomputed_records` | int | 重写/新增的 study_records 数 |
| `deleted_records` | int | 删除的多余 study_records（如事实表已无该日数据，但聚合表残留） |
| `duration_seconds_total` | int | 重算涉及的录音总时长（校验用） |

### 8.3 错误码

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 1001 | 422 | user_id 非法 / date 格式错 |
| 2001/2002/2004/2005 | 401/403/401 | 认证失败 |
| 2003 | 403 | 非管理员（role != admin） |
| 7001 | 404 | user_id 指定的用户不存在 |
| 9001 | 503 | 重算任务超时（全量用户且范围大，MVP 同步处理可能超时） |

### 8.4 后端处理（事务，ADR-008）

```text
1. 校验 current_user.role == 'admin' → 否 → 2003
2. 解析参数：
   - user_id 指定：单用户重算
   - 不指定：全量用户（MVP 同步循环，未来改异步任务，ADR-022）
   - start_date/end_date 限定范围（按 user.timezone 切日）
3. 对每个目标用户：
   a. 取 user.timezone
   b. 查该用户所有 submitted attempts（若限定范围，按 attempt.submitted_at 转 user timezone 后落在 [start, end] 内）
   c. JOIN recordings(status='uploaded') 取 duration
   d. JOIN practice_session_questions 取 sq（用于 question_count）
   e. JOIN practice_sessions(status='completed') 取 practice_count
   f. 按 attempt.submitted_at 转时区后的 date 分组：
      - attempt_count = COUNT(attempts WHERE submitted)
      - recording_count = COUNT(recordings WHERE uploaded)
      - duration_seconds = SUM(recordings.duration_seconds)  ← ADR-016
      - question_count = COUNT(DISTINCT sq)                   ← 已答题的 sq 数
      - practice_count = COUNT(sessions WHERE completed_at 在该日)
   g. 在事务内：
      - DELETE 该用户该日期范围的旧 study_records（若 start/end 不限，删全部）
      - INSERT 新计算出的 study_records（record_date = user timezone date）
   h. 累加统计：recomputed_users / recomputed_records / deleted_records / duration_total
4. 全部用户处理完，提交事务
5. 返回汇总
```

> **MVP 同步处理风险**：全量用户重算可能耗时较长，触发 9001。建议生产环境用分批或异步任务（非 MVP）。本接口 MVP 主要用于"指定用户 + 小范围"修复场景。

> **不重算分布统计**：topics/parts 接口实时从事实表聚合，无需重算（无缓存表）。

### 8.5 调用场景

- 统计数据异常（study_records 与事实表不一致）。
- 用户修改 timezone 后，历史 record_date 需按新时区重切（ADR-018，调用本接口重算该用户全历史）。
- 测试/数据修复。

---

## 9. 安全与约束汇总

### 9.1 资源所有权

- 所有读接口（§2–§7）天然绑定 current_user，无路径参数防越权问题。
- recompute 接口需 admin 角色（2003）。

### 9.2 时区一致性（ADR-018）

- 所有按日/周/月切分基于 `user_profiles.timezone`。
- 重算时按各用户自己的 timezone 切（全量重算时不同用户切日结果可能不同）。
- 修改 timezone 后，历史 study_records 不自动重算，需管理员调 recompute 触发（users.md §8.4）。

### 9.3 duration 口径（ADR-016）

- 所有 `duration_seconds` 统计 = `SUM(recordings.duration_seconds WHERE status='uploaded')`。
- **不使用** session.duration_seconds（墙钟时长，仅展示用）。
- 分布统计（topics/parts）的 duration 同口径。

### 9.4 study_records 只读 + 重算

- 本模块**不写** study_records（写入在 practice.md §6.4/§8.4）。
- 重算接口先 DELETE 再 INSERT，保证一致性（不增量更新）。
- 分布统计不走 study_records（无 topic/part 维度），实时从事实表聚合。

### 9.5 活动日志

- recompute 操作记录 `user_activity_logs`(action='study_records_recomputed', entity_type='user', entity_id=target_user_id, metadata={recomputed_records, deleted_records})。
- 读接口不记录（非关键行为，ADR-023）。

---

## 10. DTO 速查

### 10.1 响应 DTO

```text
LearningOverview:
  today: DayStats
  streak: StreakStats
  cumulative: CumulativeStats
  goal_progress: GoalProgress

DayStats:
  practice_count: int
  question_count: int
  attempt_count: int
  recording_count: int
  duration_seconds: int

StreakStats:
  current_days: int
  longest_days: int

CumulativeStats:
  total_sessions: int
  total_questions: int
  total_attempts: int
  total_recordings: int
  total_duration_seconds: int

GoalProgress:
  daily_goal_minutes: int | None
  daily_completed_minutes: float | None
  weekly_goal_minutes: int | None
  weekly_completed_minutes: float | None

TrendResponse:
  granularity: str  # daily/weekly/monthly
  timezone: str
  points: TrendPoint[]

TrendPoint:                 # daily/weekly/monthly 共用，字段按 granularity 含 date/week_start/month
  date | week_start | month: str
  practice_count: int
  question_count: int
  attempt_count: int
  recording_count: int
  duration_seconds: int

TopicsDistributionResponse:
  range_months: int
  timezone: str
  topics: TopicStat[]

TopicStat:
  topic_id: str
  topic_name: str
  attempt_count: int
  duration_seconds: int

PartsDistributionResponse:
  range_months: int
  timezone: str
  parts: PartStat[]

PartStat:
  part: int
  attempt_count: int
  duration_seconds: int

RecomputeResponse:
  recomputed_users: int
  recomputed_records: int
  deleted_records: int
  duration_seconds_total: int
```

### 10.2 请求 DTO

```text
RecomputeRequest:
  user_id: str | None
  start_date: date | None    # YYYY-MM-DD
  end_date: date | None      # YYYY-MM-DD
```

---

## 11. 与其他模块的衔接

| 衔接点 | 说明 |
| --- | --- |
| `practice.md` §6.4/§8.4 | study_records 同步写入规则（本模块只读） |
| `users.md` §8.4 | timezone 修改后调 recompute 重切历史 |
| `home.md` | overview 数据复用（首页简化版） |
| `admin.md` | recompute 接口管理员鉴权（2003） |
| `common.md` §3.2 | 错误码 7001/9001 |
| `database-design.md` §3.4 | study_records / activity_logs 表结构 |

---

## 12. ADR 引用

| ADR | 内容 | 本文位置 |
| --- | --- | --- |
| ADR-008 | study_records 可重算 | §1.4 / §8 / §9.4 |
| ADR-016 | duration 口径（录音时长） | §1.4 / §8.4 / §9.3 |
| ADR-018 | timezone 切日 | §1.4 / §2.4 / §8.4 / §9.2 |
| ADR-022 | study_records 同步更新（写入在 practice） | §1.4 |
| ADR-023 | 活动日志精简 | §9.5 |
| ADR-025 | id 序列化为字符串 | 全文 |
| ADR-026 | snake_case | 全文 |

---

## 变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-07-23 | 初始创建：overview + daily/weekly/monthly 趋势 + topics/parts 分布 + recompute 共 7 接口；ADR-008/016/018/022 落地；分布统计从事实表实时聚合（不走 study_records）；recompute 先 DELETE 再 INSERT |

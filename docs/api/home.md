# API 契约 — 首页模块（home.md）

> 本文定义首页接口契约：聚合概览 + 确定性推荐。
> **严格遵守 [common.md](file:///workspace/docs/api/common.md) v0.1**。
> 对应规格：`PROJECT_SPEC.md` v0.5 §7（推荐规则）/ §6 / `system-architecture.md` v0.1 §5.6。

---

## 0. 文档定位

本文回答："首页一次返回什么，推荐怎么生成。"
不回答："overview 统计怎么算。" → [learning.md §2](file:///workspace/docs/api/learning.md)。
不回答："session 结构。" → [practice.md §2.2](file:///workspace/docs/api/practice.md)。
不回答："题目结构。" → [questions.md §3.2](file:///workspace/docs/api/questions.md)。

---

## 1. 模块概述

### 1.1 职责

- 一次性返回首页所需全部数据（减少首屏请求数）。
- 实现确定性推荐（ADR-028，5 级短路，无 AI）。

### 1.2 路由表

| Method | Path | 鉴权 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/v1/home/overview` | Bearer | 首页聚合数据 |

### 1.3 涉及数据表

| 表 | 用途 |
| --- | --- |
| `study_records` | 今日/streak 统计（learning.md §2 同源） |
| `practice_sessions` | 未完成 session 检索（推荐 1 级）+ 最近主题（推荐 2 级） |
| `practice_session_questions` | 最近主题提取（snapshot.topic_name） |
| `favorites` | 收藏题目（推荐 3 级） |
| `speaking_questions` | 热门题目（推荐 5 级）+ Part 分布（推荐 4 级） |
| `practice_attempts` | 用户较少练习的 Part 计算（推荐 4 级） |
| `user_goals` | active goal 进度 |

### 1.4 核心原则

- **ADR-028 确定性推荐**：5 级优先级短路，逐级尝试，凑齐 `recommendation_limit` 条即停。无随机、无 AI、无协同过滤。
- **单接口聚合**：首页只调一次本接口，前端不再分别调 learning/practice/questions。
- **复用不重算**：today/streak/goal_progress 直接复用 learning.md §2 的统计逻辑（service 层共享）。

---

## 2. GET /api/v1/home/overview

### 2.1 请求

```
GET /api/v1/home/overview
Authorization: Bearer <access_token>
```

**Query（可选）：**

| 参数 | 类型 | 默认 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `recommendation_limit` | int | 5 | 1..10 | 推荐题目返回条数 |

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
    "goal_progress": {
      "daily_goal_minutes": 60,
      "daily_completed_minutes": 7.2,
      "weekly_goal_minutes": 360,
      "weekly_completed_minutes": 52.5,
      "target_score": 7.0,
      "exam_date": "2026-11-15"
    },
    "recent_practice": {
      "has_unfinished": true,
      "session": {
        "id": "201",
        "status": "in_progress",
        "mode": "topic",
        "question_count": 5,
        "completed_questions": 3,
        "updated_at": "2026-07-23T11:30:00+00:00"
      }
    },
    "recommendations": [
      {
        "id": "101",
        "part": 2,
        "title": "Describe a useful object",
        "topic": { "id": "5", "name": "Technology" },
        "difficulty": 3,
        "practice_count": 42,
        "reason": "unfinished_session"
      },
      {
        "id": "155",
        "part": 2,
        "title": "Describe a journey you took",
        "topic": { "id": "8", "name": "Travel" },
        "difficulty": 2,
        "practice_count": 28,
        "reason": "recent_topic"
      },
      {
        "id": "120",
        "part": 1,
        "title": "Do you like reading?",
        "topic": { "id": "3", "name": "Hobby" },
        "difficulty": 1,
        "practice_count": 15,
        "reason": "favorite"
      },
      {
        "id": "88",
        "part": 3,
        "title": "Discuss the impact of technology on education",
        "topic": { "id": "5", "name": "Technology" },
        "difficulty": 4,
        "practice_count": 9,
        "reason": "less_practiced_part"
      },
      {
        "id": "200",
        "part": 2,
        "title": "Describe a person who inspires you",
        "topic": { "id": "6", "name": "People" },
        "difficulty": 3,
        "practice_count": 67,
        "reason": "popular"
      }
    ]
  }
}
```

### 2.3 字段说明

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `today` | DayStats | 今日统计（复用 learning.md §2.4） |
| `streak` | StreakStats | 连续学习（复用 learning.md §2.4） |
| `goal_progress` | object | active goal 进度，扩展 `target_score`/`exam_date`；无 active goal 时为 null |
| `recent_practice` | object | 未完成 session 信息 |
| `recent_practice.has_unfinished` | bool | 是否存在未完成 session（status ∈ {created, in_progress}） |
| `recent_practice.session` | object \| null | 最近一个未完成 session 摘要；无则 null |
| `recent_practice.session.completed_questions` | int | 已有 submitted/skipped attempt 的 sq 数 |
| `recommendations` | Recommendation[] | 推荐题目列表（含 reason 标签） |
| `recommendations[].reason` | string | 推荐来源（见 §2.5） |

> `recommendations[]` 字段为 `QuestionListItem`（questions.md §2.2）扩展 `reason` 字段，**不含 is_favorited**（首页不展示收藏态，减少查询）。

### 2.4 错误码

| code | HTTP | 触发条件 |
| --- | --- | --- |
| 1001 | 422 | recommendation_limit 越界 |
| 2001/2002/2004/2005 | 401/403/401 | 认证失败 |

### 2.5 推荐算法（ADR-028，5 级短路）

严格按 PROJECT_SPEC §7 优先级，逐级尝试，凑齐 `recommendation_limit` 即停：

```text
level 1: unfinished_session
  来源: 未完成 session 中的题目（status ∈ {created, in_progress}）
  取: 该 session 的 session_questions 对应的 speaking_questions（published）
  reason: "unfinished_session"
  上限: min(剩余配额, 该 session 未完成 sq 数)

level 2: recent_topic
  来源: 用户最近 7 天练习过的主题（从 practice_session_questions.snapshot.topic_id 去重）
  取: 这些主题下的 published 题目，排除 level 1 已取
  reason: "recent_topic"
  上限: 剩余配额

level 3: favorite
  来源: favorites 表，排除已练习过的（practice_attempts 中有 submitted）
  取: published 题目
  reason: "favorite"
  上限: 剩余配额

level 4: less_practiced_part
  来源: 统计用户各 Part 的 attempt_count，取最少练习的 Part
  取: 该 Part 下的 published 题目，排除已取
  reason: "less_practiced_part"
  上限: 剩余配额

level 5: popular
  来源: 全题库 published，按 practice_count DESC
  取: 排除已取
  reason: "popular"
  上限: 剩余配额（兜底，确保凑齐）
```

**短路规则**：每一级取完更新"剩余配额"，剩余=0 则停止，不再执行后续级别。

**去重**：跨级别题目 id 去重，同一题不在多个 reason 出现。

**排序**：每级内部按各自语义排序（level 1 按 sq.sort_order；level 2/3/4 按 created_at DESC；level 5 按 practice_count DESC）。

### 2.6 后端处理

1. 取 timezone（复用 learning service）。
2. 并行/顺序查询：
   - today + streak + goal_progress（复用 learning.service.get_overview 的子查询）。
   - 未完成 session（ORDER BY updated_at DESC LIMIT 1）+ completed_questions 统计。
3. 推荐生成（§2.5 逐级短路）：
   - level 1：取未完成 session 的 sq → JOIN speaking_questions(published)。
   - level 2：最近 7 天 attempts → JOIN sq.snapshot.topic_id → 去重 → 查该 topic 下题目。
   - level 3：favorites → LEFT JOIN practice_attempts(submitted) → 取无 submitted 的 → JOIN questions(published)。
   - level 4：GROUP BY snapshot.part → ORDER BY COUNT ASC LIMIT 1 → 查该 part 题目。
   - level 5：ORDER BY practice_count DESC（复用 questions.md 的 popular 排序逻辑）。
4. 组装返回。

> **性能说明**：MVP 接受 5 级串行查询（用户量小）。未来可缓存推荐结果（Redis，非 MVP），或改为定时任务预计算。

---

## 3. 安全与约束汇总

### 3.1 资源所有权

- 天然绑定 current_user，无路径参数防越权。

### 3.2 推荐确定性

- 同一用户同一数据状态下，多次调用返回结果一致（无随机）。
- 数据状态变化（新练习/新收藏/新 session）后推荐相应变化。
- 不引入 AI 推荐、协同过滤、个性化模型（ADR-028）。

### 3.3 活动日志

- 首页访问不记录（非关键行为，ADR-023）。

### 3.4 不暴露字段

- 推荐题目不含 `is_favorited`（减少查询负载）。
- 推荐题目不含 `content`/`cue_card`/`source_*`（列表语义，详情走 questions.md）。

---

## 4. DTO 速查

```text
HomeOverview:
  today: DayStats                  # learning.md
  streak: StreakStats              # learning.md
  goal_progress: HomeGoalProgress | None
  recent_practice: RecentPractice
  recommendations: Recommendation[]

HomeGoalProgress:                  # 扩展 learning.md GoalProgress
  daily_goal_minutes: int | None
  daily_completed_minutes: float | None
  weekly_goal_minutes: int | None
  weekly_completed_minutes: float | None
  target_score: float | None
  exam_date: str | None            # YYYY-MM-DD

RecentPractice:
  has_unfinished: bool
  session: UnfinishedSessionSummary | None

UnfinishedSessionSummary:
  id: str
  status: str
  mode: str
  question_count: int
  completed_questions: int
  updated_at: str

Recommendation:                    # questions.md QuestionListItem - is_favorited + reason
  id: str
  part: int
  title: str
  topic: TopicRef
  difficulty: int | None
  practice_count: int
  reason: str                      # unfinished_session/recent_topic/favorite/less_practiced_part/popular
```

---

## 5. 与其他模块的衔接

| 衔接点 | 说明 |
| --- | --- |
| `learning.md` §2 | today/streak/goal_progress 复用 |
| `practice.md` §2.2 | 未完成 session 检索 |
| `questions.md` §2.2 | Recommendation 结构复用 QuestionListItem |
| `users.md` §5 | active goal 取 target_score/exam_date |
| `common.md` §3.2 | 错误码 |

---

## 6. ADR 引用

| ADR | 内容 | 本文位置 |
| --- | --- | --- |
| ADR-023 | 活动日志精简 | §3.3 |
| ADR-025 | id 序列化为字符串 | 全文 |
| ADR-026 | snake_case | 全文 |
| ADR-028 | 确定性推荐 5 级短路（无 AI） | §1.4 / §2.5 |

---

## 变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-07-23 | 初始创建：home/overview 单接口；ADR-028 确定性推荐 5 级短路入册；复用 learning/practice/questions 数据；推荐含 reason 标签 |

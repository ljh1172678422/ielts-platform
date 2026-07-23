# 用户流程（user-flow.md）

> 本文用 Mermaid 描述核心用户流程，引用已锁定的 API 路径与状态机。
> 不重新定义接口或状态机，仅可视化 [system-architecture.md](file:///workspace/docs/architecture/system-architecture.md) §5 与各 [API 文档](file:///workspace/docs/api/)。

---

## 1. 文档定位

- 回答："用户/管理员从进入应用到完成核心目标，经过哪些页面与接口？"
- 不回答："接口字段长什么样。" → API 文档。
- 不回答："状态机有哪些状态。" → system-architecture.md §5。

---

## 2. 用户端整体流程

```mermaid
flowchart TD
    A[访问应用] --> B{已登录?}
    B -- 否 --> C[登录/注册页]
    C --> D[POST /auth/login]
    D -- 成功 --> E[首页]
    D -- 3001/3002 --> C
    B -- 是 --> E

    E[首页<br/>GET /home/overview] --> F{用户选择}
    F -- 继续练习 --> G[练习页<br/>GET /practice/sessions/{id}]
    F -- 浏览题库 --> H[题库列表<br/>GET /questions]
    F -- 查看数据 --> I[学习数据<br/>GET /learning/overview]
    F -- 个人中心 --> J[我的<br/>GET /users/me]

    H --> K[题目详情<br/>GET /questions/{id}]
    K -- 开始练习 --> L[创建会话<br/>POST /practice/sessions]
    K -- 收藏 --> M[POST/DELETE /questions/{id}/favorite]

    L --> G
    G --> N[练习流程<br/>见 §3]
    N --> I
```

---

## 3. 练习录音核心流程

```mermaid
sequenceDiagram
    participant U as 用户
    participant F as 前端
    participant API as FastAPI

    U->>F: 选择模式/主题/数量
    F->>API: POST /practice/sessions
    API-->>F: session(status=created) + questions[snapshot]

    Note over F,U: 首次进入第 1 题
    F->>API: POST /practice/attempts {session_question_id}
    API-->>F: attempt(status=pending)<br/>session 自动 activated→in_progress

    F->>U: 显示题目快照
    U->>F: 点击开始录音
    F->>API: PATCH /practice/attempts/{id} {status=recording}
    API-->>F: attempt(status=recording)
    F->>F: MediaRecorder 开始录音<br/>显示计时器

    U->>F: 点击停止
    F->>F: 生成 Blob
    F->>API: POST /practice/attempts/{id}/recording (multipart)
    Note right of API: 事务:写文件→读元数据<br/>→recording.uploaded<br/>→attempt.submitted<br/>→study_records 同步
    API-->>F: attempt(status=submitted, recording)

    alt 跳过题目
        U->>F: 点击跳过
        F->>API: PATCH /practice/attempts/{id} {status=skipped}
        API-->>F: attempt(status=skipped)
    end

    Note over F,U: 进入下一题（重复 attempt 流程）
    Note over F: 最后一题完成后
    F->>API: POST /practice/sessions/{id}/complete
    Note right of API: ADR-015 校验<br/>所有 sq 有 submitted/skipped
    API-->>F: session(status=completed)

    F->>API: GET /learning/overview
    API-->>F: 更新后统计
    F->>U: 展示练习结果
```

---

## 4. 续练流程（断线恢复）

```mermaid
flowchart TD
    A[用户重开应用] --> B[GET /home/overview]
    B --> C{recent_practice.has_unfinished?}
    C -- 是 --> D[显示"继续练习"卡片]
    D --> E[用户点击]
    E --> F[GET /practice/sessions/{id}]
    F --> G{遍历 questions.attempts}
    G --> H[定位最后未完成 sq]
    H --> I[恢复 UI 状态:<br/>pending/recording/submitted]
    I --> J[继续练习流程 §3]
    C -- 否 --> K[正常浏览/新练习]
```

> 续练依赖 session.status='in_progress' 与 attempts 状态持久化（practice.md §3.5）。

---

## 5. 注册登录流程

```mermaid
flowchart TD
    A[登录页] --> B{有账号?}
    B -- 否 --> C[注册页]
    C --> D[POST /auth/register]
    D -- 3001 邮箱已注册 --> C
    D -- 成功 --> E[存储 access_token<br/>跳首页]

    B -- 是 --> F[输入邮箱密码]
    F --> G[POST /auth/login]
    G -- 3002 凭证错误 --> F
    G -- 2004 账号禁用 --> H[提示联系管理员]
    G -- 成功 --> E

    E --> I[GET /users/me 确认身份]
    I --> J{role?}
    J -- user --> K[用户端首页]
    J -- admin --> L[后台 Dashboard]
```

---

## 6. 学习数据流程

```mermaid
flowchart TD
    A[学习数据页] --> B[GET /learning/overview]
    B --> C[展示今日/streak/累计/goal]

    A --> D[Tab: 趋势]
    D --> E{粒度}
    E -- 日 --> F[GET /learning/daily?days=30]
    E -- 周 --> G[GET /learning/weekly?weeks=12]
    E -- 月 --> H[GET /learning/monthly?months=12]

    A --> I[Tab: 分布]
    I --> J[GET /learning/topics?months=3]
    I --> K[GET /learning/parts?months=3]
```

---

## 7. 后台管理流程

```mermaid
flowchart TD
    A[管理员登录<br/>POST /auth/login] --> B[role=admin?]
    B -- 否 --> C[2003 拒绝]
    B -- 是 --> D[后台 Dashboard<br/>GET /admin/dashboard]

    D --> E{管理模块}
    E -- 用户 --> F[GET /admin/users]
    F --> G[禁用/启用<br/>PUT /admin/users/{id}/status]

    E -- 题目 --> H[GET /admin/questions]
    H --> I[创建/编辑/状态切换]

    E -- 主题 --> J[GET /admin/topics]
    J --> K[CRUD<br/>Other 主题受 8001 保护]

    E -- 标签 --> L[GET /admin/tags]
    L --> M[CRUD<br/>引用检查 8002]

    E -- 重算 --> N[POST /learning/recompute]
```

---

## 8. 题目状态生命周期（管理员视角）

```mermaid
stateDiagram-v2
    [*] --> draft: POST /admin/questions
    draft --> published: PUT status
    published --> draft: PUT status
    published --> disabled: PUT status
    disabled --> published: PUT status
    disabled --> draft: PUT status

    note right of published
        用户端可见
        questions.md 返回
    end note
    note right of draft
        用户端不可见
        访问返回 4001
    end note
    note right of disabled
        用户端不可见
        访问返回 4002
    end note
```

> 题目不可物理删除（ADR-010），无 DELETE 接口。

---

## 9. 关键流程约束清单

| 流程 | 约束 | 来源 |
| --- | --- | --- |
| 录音上传 | submitted 必须在 recording.uploaded 之后 | ADR-015 / practice.md §6.4 |
| 会话完成 | 所有 sq 有 submitted/skipped attempt | ADR-015 / practice.md §8.4 |
| duration 统计 | 后端读元数据，不信前端 | ADR-020 |
| study_records | 录音上传/会话完成事务同步更新 | ADR-022 |
| 推荐生成 | 5 级短路，确定性无 AI | ADR-028 / home.md §2.5 |
| 题目删除 | 不允许物理删除，仅 disabled | ADR-010 |
| Other 主题 | 不可删/停用/重命名 | PROJECT_SPEC §12.3 |
| 时区切日 | 按 user_profiles.timezone | ADR-018 |
| 历史快照 | session_questions.snapshot 不可变 | ADR-016 |

---

## 变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-07-23 | 初始创建：用户端整体/练习录音/续练/登录/学习数据/后台 6 大流程 + 题目状态机 + 约束清单 |

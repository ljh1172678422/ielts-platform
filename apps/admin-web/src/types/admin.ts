/**
 * Admin 域响应/请求类型（对齐 docs/api/admin.md §8 DTO 速查）。
 *
 * 仅 admin-web 使用，故定义在本地而非 @ielts/types（admin 类型不与 user-web 共享）。
 * ID 序列化为 string（ADR-025），全 snake_case（ADR-026）。
 */
import type {
  ID,
  ISODateTime,
  PaginatedData,
  QuestionSourceType,
  QuestionStatus,
  SpeakingPart,
} from '@ielts/types'

// ---------------------------------------------------------------------------
// Dashboard（admin.md §2.2）
// ---------------------------------------------------------------------------

export interface DashboardData {
  users: {
    total: number
    active_today: number
    new_this_week: number
  }
  questions: {
    total: number
    published: number
    draft: number
    disabled: number
  }
  practice: {
    total_sessions: number
    total_attempts: number
    total_recordings: number
    total_duration_seconds: number
  }
  topics: { total: number }
  tags: { total: number }
}

// ---------------------------------------------------------------------------
// 用户管理（admin.md §3）
// ---------------------------------------------------------------------------

export interface AdminUserListItem {
  id: ID
  email: string
  role: string
  status: string
  nickname: string | null
  last_login_at: ISODateTime | null
  created_at: ISODateTime
}

export interface AdminUsersData extends PaginatedData<AdminUserListItem> {}

export interface UpdateUserStatusRequest {
  status: 'active' | 'disabled'
}

// ---------------------------------------------------------------------------
// 主题 CRUD（admin.md §4）
// ---------------------------------------------------------------------------

export interface AdminTopicItem {
  id: ID
  name: string
  slug: string
  description: string | null
  question_count: number
  is_system: boolean
  created_at: ISODateTime
}

export interface TopicUpsertRequest {
  name: string
  slug?: string
  description?: string
}

// ---------------------------------------------------------------------------
// 标签 CRUD（admin.md §5）
// ---------------------------------------------------------------------------

export interface AdminTagItem {
  id: ID
  name: string
  slug: string
  question_count: number
  created_at: ISODateTime
}

export interface TagUpsertRequest {
  name: string
  slug?: string
}

// ---------------------------------------------------------------------------
// 题目 CRUD（admin.md §6）
// ---------------------------------------------------------------------------

export interface TopicRef {
  id: ID
  name: string
}

export interface TagRef {
  id: ID
  name: string
}

export interface AdminQuestionListItem {
  id: ID
  part: SpeakingPart
  title: string
  topic: TopicRef
  tags: TagRef[]
  difficulty: number | null
  status: QuestionStatus
  source_type: QuestionSourceType
  source_name: string
  practice_count: number
  created_by: ID | null
  created_at: ISODateTime
  updated_at: ISODateTime
}

export interface AdminQuestionDetail extends AdminQuestionListItem {
  content: string
  cue_card: string | null
}

export interface AdminQuestionsData extends PaginatedData<AdminQuestionListItem> {}

export interface QuestionUpsertRequest {
  part: SpeakingPart
  title: string
  content: string
  cue_card?: string
  topic_id: ID
  tag_ids: ID[]
  difficulty?: number
  source_type: QuestionSourceType
  source_name: string
  status?: QuestionStatus
}

export interface UpdateQuestionStatusRequest {
  status: QuestionStatus
}

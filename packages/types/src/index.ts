/**
 * 共享 TS 类型 (@ielts/types)
 *
 * 对齐 common.md v0.2:
 * - 统一响应信封 { code, message, data, details? }
 * - 成功 code=0
 * - 错误时 data=null
 * - ID 序列化为字符串 (ADR-005)
 * - 全链路 snake_case (ADR-026)
 * - 时间 ISO 8601 带时区 (common.md §1.6)
 *
 * 实体视图类型 (Question/Session/Attempt/Recording 等) 在 Phase 3-4
 * 各模块实现时按对应 API 契约文档补充，此处仅锁定协议层类型。
 */

// ---------------------------------------------------------------------------
// 协议层（common.md §1-§4）
// ---------------------------------------------------------------------------

/** 统一响应信封 (common.md §2.1)。成功时 data 为业务数据。 */
export interface ResponseEnvelope<T = unknown> {
  code: number;
  message: string;
  data: T;
}

/** 错误响应 (common.md §2.2)。data 恒为 null，details 仅参数校验失败时出现。 */
export interface ErrorEnvelope {
  code: number;
  message: string;
  data: null;
  details?: ApiErrorDetail[];
}

/** 单条校验错误 (422 details 元素)。 */
export interface ApiErrorDetail {
  field?: string;
  message: string;
}

/** 分页数据结构 (common.md §4.2)。 */
export interface PaginatedData<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

/** 分页查询参数 (common.md §4.1)。 */
export interface PaginationQuery {
  page?: number;
  page_size?: number;
}

// ---------------------------------------------------------------------------
// 基础别名 (common.md §1.5 / §1.6 / ADR-005)
// ---------------------------------------------------------------------------

/**
 * 序列化为字符串的 ID (common.md §1.5, ADR-005)。
 * BIGINT 主键在 JS 超 2^53 会丢精度，故所有 id / *_id 在 JSON 中为 string。
 * 前端仅作字符串处理，不做数值运算。
 */
export type ID = string;

/** ISO 8601 带时区偏移的时间字符串，如 2026-07-23T12:00:00+00:00 (common.md §1.6)。 */
export type ISODateTime = string;

/** 纯日期字符串 YYYY-MM-DD，如 record_date / exam_date (common.md §1.6)。 */
export type ISODate = string;

// ---------------------------------------------------------------------------
// 通用枚举（common.md §3.2 / database-design §2）
// ---------------------------------------------------------------------------

/** 用户角色 (ADR-009)。 */
export type UserRole = 'user' | 'admin';

/** 用户状态。 */
export type UserStatus = 'active' | 'disabled';

/** 题目状态 (ADR-010)。 */
export type QuestionStatus = 'draft' | 'published' | 'disabled';

/** 题目来源类型 (ADR-011)。 */
export type QuestionSourceType = 'official' | 'historical' | 'mock' | 'custom';

/** IELTS Speaking Part。 */
export type SpeakingPart = 1 | 2 | 3;

/** 练习会话状态 (practice.md §2.2)。 */
export type SessionStatus = 'created' | 'in_progress' | 'completed' | 'abandoned' | 'expired';

/** 尝试状态 (ADR-015 / practice.md §3.2)。 */
export type AttemptStatus = 'pending' | 'recording' | 'submitted' | 'skipped' | 'failed';

/** 录音状态 (practice.md §3.2)。 */
export type RecordingStatus = 'uploading' | 'uploaded' | 'failed' | 'deleted';

// ---------------------------------------------------------------------------
// 用户域实体视图（auth.md §7.2 / users.md §2.2，Phase 4 补充）
// ---------------------------------------------------------------------------

/** 用户公开资料（UserPublic.profile，auth.md §7.2）。 */
export interface UserProfilePublic {
  nickname: string | null;
  timezone: string;
  avatar_url: string | null;
}

/**
 * 用户公开信息（auth.md §7.2 / users.md §2.2）。
 * id 序列化为字符串 (ADR-005)，created_at 为 users.md §2.2 扩展字段。
 */
export interface UserPublic {
  id: ID;
  email: string;
  role: UserRole;
  status: UserStatus;
  profile: UserProfilePublic;
  created_at: ISODateTime;
}

/** 认证响应 data（auth.md §2.2，注册/登录共用）。 */
export interface AuthData {
  user: UserPublic;
  access_token: string;
  token_type: 'bearer';
  expires_in: number;
}

// ---------------------------------------------------------------------------
// 用户域请求 DTO（auth.md §7.1 / users.md）
// ---------------------------------------------------------------------------

/** 注册请求（auth.md §7.1）。 */
export interface RegisterRequest {
  email: string;
  password: string;
  nickname?: string;
  timezone?: string;
}

/** 登录请求（auth.md §7.1）。 */
export interface LoginRequest {
  email: string;
  password: string;
}

// ---------------------------------------------------------------------------
// 目标域（users.md §5.2 / §9，Phase 4 补充）
// ---------------------------------------------------------------------------

/** 目标状态（users.md §5）。 */
export type GoalStatus = 'active' | 'achieved' | 'archived';

/** 学习目标（users.md §5.2 / §9.2）。 */
export interface UserGoal {
  id: ID;
  target_score: number | null;
  current_level: string | null;
  exam_date: ISODate | null;
  daily_goal_minutes: number | null;
  weekly_goal_minutes: number | null;
  status: GoalStatus;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

/** 目标列表响应（users.md §5.2，非分页，含 current + history）。 */
export interface GoalsResponse {
  current: UserGoal | null;
  history: UserGoal[];
}

// ---------------------------------------------------------------------------
// users 模块请求 DTO（users.md §9.1）
// ---------------------------------------------------------------------------

/** 修改资料请求（users.md §3.1，全量替换 profile 字段）。 */
export interface UpdateProfileRequest {
  nickname: string | null;
  avatar_url: string | null;
  timezone: string;
}

/** 修改密码请求（users.md §4.1）。 */
export interface ChangePasswordRequest {
  old_password: string;
  new_password: string;
}

/** 创建目标请求（users.md §6.1，至少一字段非空）。 */
export interface CreateGoalRequest {
  target_score?: number | null;
  current_level?: string | null;
  exam_date?: ISODate | null;
  daily_goal_minutes?: number | null;
  weekly_goal_minutes?: number | null;
}

/** 更新目标请求（users.md §7.1，全量替换，status 必填）。 */
export interface UpdateGoalRequest {
  target_score?: number | null;
  current_level?: string | null;
  exam_date?: ISODate | null;
  daily_goal_minutes?: number | null;
  weekly_goal_minutes?: number | null;
  status: GoalStatus;
}

// ---------------------------------------------------------------------------
// 题库域（questions.md §7，Phase 6 补充）
// ---------------------------------------------------------------------------

/** 题库列表排序方式（questions.md §2.1）。 */
export type QuestionSort = 'newest' | 'popular';

/** 主题摘要（questions.md §7.1）。 */
export interface TopicRef {
  id: ID;
  name: string;
}

/** 标签摘要（questions.md §7.1）。 */
export interface TagRef {
  id: ID;
  name: string;
}

/** 题库列表项（questions.md §2.2，不含 content/cue_card/tags/source_*）。 */
export interface QuestionListItem {
  id: ID;
  part: SpeakingPart;
  title: string;
  topic: TopicRef;
  difficulty: number | null;
  is_favorited: boolean;
  practice_count: number;
  created_at: ISODateTime;
}

/** 题目详情（questions.md §3.2，在列表项基础上追加完整字段）。 */
export interface QuestionDetail extends QuestionListItem {
  content: string;
  cue_card: string | null;
  tags: TagRef[];
  source_type: QuestionSourceType;
  source_name: string;
}

/** 收藏/取消收藏响应（questions.md §4.2/§5.2）。 */
export interface FavoriteResponse {
  question_id: ID;
  is_favorited: boolean;
}

/** 题库列表分页响应（common.md §4.2 + questions.md §2.2）。 */
export type PaginatedQuestions = PaginatedData<QuestionListItem>;

/** 题库列表查询参数（questions.md §2.1）。 */
export interface QuestionListQuery {
  page?: number;
  page_size?: number;
  part?: SpeakingPart;
  topic_id?: ID;
  tag_id?: ID;
  keyword?: string;
  difficulty?: number;
  sort?: QuestionSort;
  is_favorited?: boolean;
}

// ---------------------------------------------------------------------------
// 练习域（practice.md §10，Phase 7 补充）
// ---------------------------------------------------------------------------

/** 练习模式 (practice.md §2.1)。 */
export type PracticeMode = 'random' | 'topic' | 'part';

/** 题目快照（不可变，ADR-016，practice.md §2.2）。 */
export interface QuestionSnapshot {
  part: SpeakingPart;
  title: string;
  content: string;
  cue_card: string | null;
  topic_name: string | null;
  difficulty: number | null;
}

/** 录音 (practice.md §3.2，Phase 8 写入，Phase 7 恒为 null)。 */
export interface Recording {
  id: ID;
  status: RecordingStatus;
  mime_type: string;
  duration_seconds: number | null;
  file_size: number | null;
  created_at: ISODateTime;
}

/** 答题尝试 (practice.md §3.2/§4.2)。 */
export interface Attempt {
  id: ID;
  session_question_id: ID;
  attempt_number: number;
  status: AttemptStatus;
  started_at: ISODateTime | null;
  submitted_at: ISODateTime | null;
  duration_seconds: number | null;
  recording: Recording | null;
}

/** 会话题目（含 snapshot 与 attempts，practice.md §2.2）。 */
export interface SessionQuestion {
  id: ID;
  session_id: ID;
  question_id: ID;
  sort_order: number;
  snapshot: QuestionSnapshot;
  attempts: Attempt[];
}

/** 练习会话 (practice.md §2.2)。 */
export interface PracticeSession {
  id: ID;
  status: SessionStatus;
  mode: PracticeMode;
  part_filter: number | null;
  topic_filter: ID | null;
  question_count: number;
  started_at: ISODateTime | null;
  completed_at: ISODateTime | null;
  duration_seconds: number | null;
  created_at: ISODateTime;
  updated_at: ISODateTime;
  questions: SessionQuestion[];
}

/** 创建练习会话请求 (practice.md §2.1)。 */
export interface CreateSessionRequest {
  mode: PracticeMode;
  part?: SpeakingPart;
  topic_id?: ID;
  question_count: number;
}

/** 创建答题尝试请求 (practice.md §4.1)。 */
export interface CreateAttemptRequest {
  session_question_id: ID;
}

/** 更新答题状态请求 (practice.md §5.1，submitted 不可前端直设)。 */
export interface UpdateAttemptRequest {
  status: 'recording' | 'skipped' | 'failed';
}

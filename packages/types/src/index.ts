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

/** 练习会话状态。 */
export type SessionStatus = 'in_progress' | 'completed' | 'abandoned';

/** 尝试状态 (ADR-015)。 */
export type AttemptStatus = 'pending' | 'recording' | 'submitted' | 'skipped';

/** 录音状态。 */
export type RecordingStatus = 'uploading' | 'uploaded' | 'failed';

/**
 * 通用工具函数 (@ielts/utils)
 *
 * 纯函数，无副作用，不依赖 Vue / 浏览器 API（formatDateTime 除外）。
 * 对齐 common.md §1.6 时间约定与 ADR-016 duration 口径。
 */

/**
 * 将秒数格式化为可读时长。
 * - < 60s → "45s"
 * - < 3600s → "3m 12s"
 * - ≥ 3600s → "1h 5m 3s"
 */
export function formatDuration(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  if (s < 60) return `${s}s`;
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}h ${m}m ${sec}s`;
  return `${m}m ${sec}s`;
}

/**
 * 将秒数格式化为 MM:SS 或 H:MM:SS（用于播放器进度显示）。
 */
export function formatDurationClock(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const pad = (n: number) => String(n).padStart(2, '0');
  if (h > 0) return `${h}:${pad(m)}:${pad(sec)}`;
  return `${pad(m)}:${pad(sec)}`;
}

/**
 * 格式化 ISO 时间字符串为本地可读格式。
 *
 * @param iso ISO 8601 带时区字符串 (common.md §1.6)
 * @param locale 展示 locale，默认浏览器
 * @returns 如 "2026-07-23 20:00"
 */
export function formatDateTime(
  iso: string,
  locale: string = typeof navigator !== 'undefined' ? navigator.language : 'zh-CN',
): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  const hh = String(d.getHours()).padStart(2, '0');
  const mi = String(d.getMinutes()).padStart(2, '0');
  // locale 简化：中英文展示风格差异
  if (locale.startsWith('zh')) return `${yyyy}-${mm}-${dd} ${hh}:${mi}`;
  return `${yyyy}-${mm}-${dd} ${hh}:${mi}`;
}

/**
 * 格式化 ISO 时间为纯日期 YYYY-MM-DD。
 */
export function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

/**
 * 相对时间描述（"刚刚"/"3 分钟前"/"2 天前"）。
 */
export function formatRelativeTime(iso: string, now: number = Date.now()): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const diff = now - d.getTime();
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return '刚刚';
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} 分钟前`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} 小时前`;
  const day = Math.floor(hr / 24);
  if (day < 30) return `${day} 天前`;
  const month = Math.floor(day / 30);
  if (month < 12) return `${month} 个月前`;
  return `${Math.floor(month / 12)} 年前`;
}

/**
 * 将分页查询参数对象序列化为 URL query string 片段（已过滤空值）。
 * 仅处理 primitive 与数组（数组重复 key）。
 *
 * @example buildQuery({ page: 1, page_size: 20, keyword: 'tech' })
 *          → "page=1&page_size=20&keyword=tech"
 */
export function buildQuery(params: Record<string, unknown>): string {
  const sp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue;
    if (Array.isArray(value)) {
      for (const v of value) sp.append(key, String(v));
    } else {
      sp.append(key, String(value));
    }
  }
  return sp.toString();
}

/**
 * 计算分页总页数 (common.md §4.2: total_pages = ceil(total / page_size))。
 */
export function calcTotalPages(total: number, pageSize: number): number {
  if (pageSize <= 0) return 0;
  return Math.ceil(total / pageSize);
}

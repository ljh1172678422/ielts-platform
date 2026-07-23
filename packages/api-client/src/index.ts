/**
 * API Client (@ielts/api-client)
 *
 * 对齐 common.md v0.2:
 * - 请求拦截器注入 Bearer token（token 由 apps 注入 getter，本包不依赖 Pinia）
 * - 响应拦截器解包统一信封 { code, message, data }
 *   - HTTP 200 + code=0 → 返回 data（业务数据）
 *   - 任意 code!=0 或 4xx/5xx → 抛 ApiClientError（带 code/message/details）
 * - typed 辅助方法 get/post/put/patch/delete 直接返回业务数据 T
 *
 * 完整模块 API（auth/users/practice 等）封装见 Phase 4。
 */

import axios, {
  type AxiosInstance,
  type AxiosRequestConfig,
  type AxiosError,
  type InternalAxiosRequestConfig,
} from 'axios';
import type {
  ResponseEnvelope,
  ErrorEnvelope,
  ApiErrorDetail,
} from '@ielts/types';

/** API 业务错误（携带 common.md 业务码）。 */
export class ApiClientError extends Error {
  readonly code: number;
  readonly details?: ApiErrorDetail[];
  readonly httpStatus?: number;

  constructor(
    code: number,
    message: string,
    options?: { details?: ApiErrorDetail[]; httpStatus?: number },
  ) {
    super(message);
    this.name = 'ApiClientError';
    this.code = code;
    this.details = options?.details;
    this.httpStatus = options?.httpStatus;
  }
}

/** Token 注入函数：apps 注入从 store 读取 access_token 的 getter。 */
export type TokenGetter = () => string | null;

/** 401 处理回调：apps 注入跳转登录 / 清除 token 逻辑。 */
export type UnauthorizedHandler = () => void;

export interface CreateApiClientOptions {
  baseURL: string;
  /** 请求超时（ms），默认 30000。 */
  timeout?: number;
  /** 注入 Bearer token 的 getter。 */
  getToken?: TokenGetter;
  /** 收到 2001/2002（未认证/token 失效）时回调。 */
  onUnauthorized?: UnauthorizedHandler;
}

/** 已解包信封的 typed HTTP 客户端，所有方法直接返回业务数据 T。 */
export interface ApiClient {
  get<T>(url: string, config?: AxiosRequestConfig): Promise<T>;
  post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>;
  put<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>;
  patch<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T>;
  delete<T>(url: string, config?: AxiosRequestConfig): Promise<T>;
  /** 原始 axios 实例（需直接操作时使用，如文件上传进度）。 */
  raw: AxiosInstance;
}

/**
 * 创建 API Client。
 *
 * @example
 * const api = createApiClient({
 *   baseURL: '/api/v1',
 *   getToken: () => authStore.token,
 *   onUnauthorized: () => router.push('/login'),
 * });
 * const user = await api.get<User>('/users/me');
 */
export function createApiClient(options: CreateApiClientOptions): ApiClient {
  const instance: AxiosInstance = axios.create({
    baseURL: options.baseURL,
    timeout: options.timeout ?? 30000,
    headers: { 'Content-Type': 'application/json' },
  });

  // 请求拦截器：注入 Bearer token (common.md §5.1)
  instance.interceptors.request.use((config: InternalAxiosRequestConfig) => {
    const token = options.getToken?.();
    if (token) {
      config.headers.set('Authorization', `Bearer ${token}`);
    }
    return config;
  });

  // 响应拦截器：解包统一信封 (common.md §2)
  instance.interceptors.response.use(
    (response) => {
      const envelope = response.data as ResponseEnvelope;
      // 成功：code=0，返回 data
      if (envelope && typeof envelope.code === 'number' && envelope.code === 0) {
        return envelope.data;
      }
      // 异常：HTTP 200 但 code!=0（理论上不应发生，按业务错误处理）
      if (envelope && typeof envelope.code === 'number') {
        throw new ApiClientError(envelope.code, envelope.message, {
          details: (envelope as unknown as ErrorEnvelope).details,
          httpStatus: response.status,
        });
      }
      // 非信封结构（如音频流响应），原样返回
      return response.data;
    },
    (error: AxiosError) => {
      // 网络错误 / 超时
      if (!error.response) {
        throw new ApiClientError(9003, error.message || '服务内部错误');
      }

      const status = error.response.status;
      const body = error.response.data as ErrorEnvelope | undefined;

      // 信封错误响应
      if (body && typeof body.code === 'number') {
        // 401：未认证 / token 失效（common.md §5.2）
        if (body.code === 2001 || body.code === 2002 || body.code === 2005) {
          options.onUnauthorized?.();
        }
        throw new ApiClientError(body.code, body.message, {
          details: body.details,
          httpStatus: status,
        });
      }

      // 非信封错误（如网关 502）
      throw new ApiClientError(9003, body?.message || error.message || '服务内部错误', {
        httpStatus: status,
      });
    },
  );

  const wrap = <T>(p: Promise<unknown>): Promise<T> => p as Promise<T>;

  return {
    get: <T>(url: string, config?: AxiosRequestConfig) =>
      wrap<T>(instance.get(url, config)),
    post: <T>(url: string, data?: unknown, config?: AxiosRequestConfig) =>
      wrap<T>(instance.post(url, data, config)),
    put: <T>(url: string, data?: unknown, config?: AxiosRequestConfig) =>
      wrap<T>(instance.put(url, data, config)),
    patch: <T>(url: string, data?: unknown, config?: AxiosRequestConfig) =>
      wrap<T>(instance.patch(url, data, config)),
    delete: <T>(url: string, config?: AxiosRequestConfig) =>
      wrap<T>(instance.delete(url, config)),
    raw: instance,
  };
}

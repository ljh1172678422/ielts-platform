/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 接口基础地址覆盖，默认走 vite 代理 /api */
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
  readonly VITE_USE_REAL_API?: string; // 'true' to enable real backend
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

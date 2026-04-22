/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_ENABLE_EXTERNAL_SIGNALS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module '@fontsource-variable/space-grotesk'

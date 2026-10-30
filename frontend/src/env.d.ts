interface ImportMetaEnv {
  /** Backend address in production, e.g. https://wordpath-api.onrender.com */
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

declare module "*.css";

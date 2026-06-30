import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// 개발 중 /api 호출을 백엔드로 프록시. 대상은 VITE_API_TARGET(.env*) 또는 :8000.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const target = env.VITE_API_TARGET || "http://localhost:8000";
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": { target, changeOrigin: true },
      },
    },
  };
});

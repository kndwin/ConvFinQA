import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { TanStackRouterVite } from "@tanstack/router-plugin/vite";

export default defineConfig({
  plugins: [
    TanStackRouterVite({
      routesDirectory: "./src",
      virtualRouteConfig: "./src/platform/router/routes.ts",
      generatedRouteTree: "./src/platform/router/route-tree.gen.ts",
      target: "react",
      autoCodeSplitting: true,
    }),
    react(),
  ],
  resolve: {
    alias: {
      "@": "/src",
    },
  },
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});

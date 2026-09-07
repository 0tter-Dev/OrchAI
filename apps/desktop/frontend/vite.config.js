import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Served by the backend under /app/ (interfaces/api/main.py mounts
// frontend/dist there, not at "/" -- see ADR-017), so built asset URLs
// must be rooted at /app/ too.
export default defineConfig({
  plugins: [react()],
  base: "/app/",
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});

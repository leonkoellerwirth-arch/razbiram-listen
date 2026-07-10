import { defineConfig } from "vite";

// Relative base so the built viewer works from any subpath (docs/ or GitHub Pages).
export default defineConfig({
  base: "./",
  build: { outDir: "dist" },
});

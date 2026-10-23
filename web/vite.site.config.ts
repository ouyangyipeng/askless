import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  root: new URL("./site", import.meta.url).pathname,
  base: "/askless/",
  plugins: [react()],
  build: {
    outDir: "../../docs",
    emptyOutDir: false,
    // Stable filenames keep the committed Pages directory small across builds.
    rollupOptions: {
      output: {
        entryFileNames: "assets/site.js",
        chunkFileNames: "assets/[name].js",
        assetFileNames: "assets/[name][extname]",
      },
    },
  },
});

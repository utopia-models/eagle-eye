import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import path from "path"
// Two pages from one build: /upwork-jobs.html and /cold-apps.html (shared shadcn + Magic UI components, one shared CSS).
export default defineConfig({ plugins: [react()], resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  build: { outDir: "dist", assetsDir: "", rollupOptions: { input: { "upwork-jobs": path.resolve(__dirname, "upwork-jobs.html"), "cold-apps": path.resolve(__dirname, "cold-apps.html"), "lane-app": path.resolve(__dirname, "lane-app.html") },
    output: { entryFileNames: "[name].js", chunkFileNames: "ee-[name].js", assetFileNames: "ee-[name].[ext]" } } } })

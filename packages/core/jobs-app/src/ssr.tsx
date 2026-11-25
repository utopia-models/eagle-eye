// Gate-only render: the page with sample rows, so a reviewer sees real cells. Never shipped.
import { renderToString } from "react-dom/server"
import { App } from "./App"
const h = (n: number) => new Date(Date.now() - n * 36e5).toISOString()
const UP = { computedAt: h(0.1), matches: [
  { key: "~1", title: "AI Automation Engineer", postedAt: h(2), why: ["fit 9", "n8n, Python"], demo: { slug: "ai-automation", url: "https://ai-automation.utopiamodels.ai/", ready: true }, owner: "horus", vsl: false, vslScript: true, statusWord: "Awaiting VSL", runsheet: "net/work/vsl/ai-automation/runsheet.md" },
  { key: "~2", title: "Principal Eng, Infra & Security", postedAt: h(9), why: ["fit 8"], demo: { slug: "llm-gateway", ready: false }, owner: "builder", vsl: false, statusWord: "Awaiting Demo" },
  { key: "~3", title: "AI Engineer, RAG", postedAt: h(30), demo: null, owner: "UNASSIGNED", vsl: false, statusWord: "Awaiting Demo" }],
  applied: [{ key: "~4", title: "Polymarket bot", sentAt: h(20), job: { posted: null }, demo: { slug: "pm", live: true, url: "https://pm.utopiamodels.ai/" }, vsl: { recorded: false }, pipeline: { noVsl: true }, statusWord: "Awaiting Reply" }] }
console.log(renderToString(<App initial={UP} />))

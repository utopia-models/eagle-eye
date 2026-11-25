import { serve } from "@hono/node-server";
import { buildApp } from "./app.ts";
import { loadColumns } from "./rest.ts";
import { runMigrations } from "./migrate.ts";
import { startListener, stopListener } from "./stream.ts";
import { pool } from "./db.ts";

const HOST = process.env.EAGLE_HOST || "100.127.249.81"; // Ra's Tailscale IP: tailnet only for now
const PORT = Number(process.env.EAGLE_PORT || 8798);

await runMigrations();
await loadColumns();
await startListener();
let stopWorker: (() => Promise<void>) | null = null;
if (process.env.EAGLE_WORKER !== "0") {
  const w = await import("./worker.ts");
  await w.startWorker();
  stopWorker = w.stopWorker;
}
const server = serve({ fetch: buildApp().fetch, hostname: HOST, port: PORT }, i => console.log(`eagle-server on http://${HOST}:${i.port}`));

const shutdown = async () => {
  server.close();
  await stopWorker?.();
  await stopListener();
  await pool.end().catch(() => {});
  process.exit(0);
};
process.on("SIGTERM", shutdown);
process.on("SIGINT", shutdown);

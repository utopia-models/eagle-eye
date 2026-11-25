// eagle-worker: pg-boss on the same Postgres (no Redis). On Ra it runs inside the server process (EAGLE_WORKER=1)
// to keep RAM low; `tsx src/worker.ts` runs it standalone, as the compose `worker` service will.
import { PgBoss } from "pg-boss";
import { fileURLToPath } from "node:url";
import { PG_CONFIG, asOwner } from "./db.ts";

let boss: PgBoss | null = null;

export async function startWorker() {
  boss = new PgBoss({ ...(PG_CONFIG as any), schema: "pgboss", max: 2 });
  boss.on("error", e => console.error("pg-boss", e.message));
  await boss.start();

  // Copy of Twenty engine/trash-cleanup: cron '10 0 * * *', hard-delete rows soft-deleted > 30 days ago, batch 1,000.
  // Rows still referenced (events are append-only and keep their item/roost) stay: history is never orphaned.
  await boss.createQueue("trash-purge");
  await boss.schedule("trash-purge", "10 0 * * *");
  await boss.work("trash-purge", async () => {
    const out: Record<string, number> = {};
    await asOwner(async tx => {
      for (const t of ["recordings", "one_shots", "hunt_items", "roosts", "people", "companies"]) {
        const ref = t === "hunt_items" ? "and not exists (select 1 from events e where e.item_id = x.id) and not exists (select 1 from touches t where t.item_id = x.id)"
          : t === "roosts" ? "and not exists (select 1 from events e where e.roost_id = x.id)" : "";
        const r = await tx.query(`delete from ${t} x where x.id in (select id from ${t} where deleted_at < now() - interval '30 days' limit 1000) ${ref}`).catch(() => ({ rowCount: 0 }));
        out[t] = r.rowCount ?? 0;
      }
    });
    console.log("trash-purge", JSON.stringify(out));
  });

  // Live ingest every 5 min: spike live rows -> API (idempotent source ids). Off with EAGLE_INGEST=0.
  if (process.env.EAGLE_INGEST !== "0") {
    await boss.createQueue("ingest-live");
    await boss.schedule("ingest-live", "*/5 * * * *");
    await boss.work("ingest-live", async () => {
      const { runIngest } = await import("./ingest.ts");
      const r = await runIngest({});
      console.log("ingest-live", JSON.stringify(r.summary));
    });
  }
  // Follow-ups days 3/7/14 (card 11-21 ~8:50 PM): scan every 5 min, one delayed job per follow-up. Off with EAGLE_FOLLOWUPS=0.
  if (process.env.EAGLE_FOLLOWUPS !== "0") {
    const { registerFollowups } = await import("./followups.ts");
    await registerFollowups(boss);
  }
  return boss;
}

export async function stopWorker() { await boss?.stop({ graceful: true, timeout: 5000 }).catch(() => {}); boss = null; }

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  startWorker().then(() => console.log("worker up"));
}

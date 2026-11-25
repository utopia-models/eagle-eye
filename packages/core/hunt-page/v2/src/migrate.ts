import { drizzle } from "drizzle-orm/node-postgres";
import { migrate } from "drizzle-orm/node-postgres/migrator";
import pg from "pg";
import { fileURLToPath } from "node:url";
import { PG_CONFIG } from "./db.ts";

const folder = fileURLToPath(new URL("../migrations", import.meta.url));

/** Drizzle migrations, run as eagleeye_owner so every object is owned by the owner role, not a login. */
export async function runMigrations(cfg: pg.ClientConfig = PG_CONFIG) {
  const client = new pg.Client(cfg);
  await client.connect();
  try {
    await client.query("set role eagleeye_owner");
    await migrate(drizzle(client), { migrationsFolder: folder });
  } finally {
    await client.end();
  }
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  runMigrations().then(() => console.log("migrations applied"), e => { console.error(e); process.exit(1); });
}

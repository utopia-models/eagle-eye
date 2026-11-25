import { resetDb, pool, token, api, item, app } from "./helpers.ts";
import { startListener, stopListener } from "../src/stream.ts";
import { serve } from "@hono/node-server";
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import type { AddressInfo } from "node:net";

let base: string, srv: any, tok: string;
before(async () => {
  await resetDb();
  await startListener();
  tok = await token();
  await new Promise<void>(r => { srv = serve({ fetch: app.fetch, hostname: "127.0.0.1", port: 0 }, () => r()); });
  base = `http://127.0.0.1:${(srv.address() as AddressInfo).port}`;
});
after(async () => { srv.close(); await stopListener(); await pool.end(); });

/** Reads SSE frames off a real HTTP stream until `want` frames of the given type arrive (or times out). */
async function collect(url: string, headers: Record<string, string>, want: { type: string; n: number }, act?: () => Promise<void>, ms = 5000) {
  const ac = new AbortController();
  const res = await fetch(url, { headers, signal: ac.signal });
  assert.equal(res.headers.get("content-type")?.split(";")[0], "text/event-stream");
  const reader = res.body!.getReader(), dec = new TextDecoder();
  const frames: { id?: string; event?: string; data?: any }[] = [];
  let buf = "", acted = false;
  const deadline = Date.now() + ms;
  try {
    while (Date.now() < deadline && frames.filter(f => f.event === want.type).length < want.n) {
      const { value, done } = await Promise.race([reader.read(), new Promise<any>(r => setTimeout(() => r({ value: undefined, done: false }), 200))]);
      if (done) break;
      if (value) buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf("\n\n")) >= 0) {
        const raw = buf.slice(0, i); buf = buf.slice(i + 2);
        const f: any = {};
        for (const line of raw.split("\n")) { const m = line.match(/^(id|event|data): ?(.*)$/); if (m) f[m[1]] = m[1] === "data" ? JSON.parse(m[2]) : m[2]; }
        if (f.event) frames.push(f);
        if (f.event === "ready" && act && !acted) { acted = true; await act(); }
      }
    }
  } finally { ac.abort(); }
  return frames;
}

test("an insert through the API reaches an open SSE client as item.found, with the feed row attached", async () => {
  const frames = await collect(`${base}/api/stream?workspace=tyler`, {}, { type: "item.found", n: 1 },
    async () => { assert.equal((await api(tok, "POST", "/rest/huntItems?upsert=true", item({ externalId: "sse-1" }))).status, 201); });
  const f = frames.find(x => x.event === "item.found");
  assert.ok(f, "no item.found frame: " + JSON.stringify(frames));
  assert.match(f!.id!, /^[0-9a-f-]{36}$/);
  assert.equal(f!.data.item.target, "Shopify replatform");
  assert.ok(f!.data.item.foundAt && f!.data.item.signalAt);
});

test("an unchanged re-find emits nothing; a change emits item.updated", async () => {
  const frames = await collect(`${base}/api/stream?workspace=tyler`, {}, { type: "item.updated", n: 1 }, async () => {
    await api(tok, "POST", "/rest/huntItems?upsert=true", item({ externalId: "sse-1" }));
    await api(tok, "POST", "/rest/huntItems?upsert=true", item({ externalId: "sse-1", signal: "changed" }));
  });
  assert.deepEqual(frames.filter(f => f.event !== "ready").map(f => f.event), ["item.updated"]);
});

test("reconnect with Last-Event-ID replays what was missed, in order", async () => {
  const first = await collect(`${base}/api/stream?workspace=tyler`, {}, { type: "item.found", n: 1 },
    async () => { await api(tok, "POST", "/rest/huntItems?upsert=true", item({ externalId: "sse-2" })); });
  const lastId = first.filter(f => f.event === "item.found").at(-1)!.id!;
  // written while no client was connected
  await api(tok, "POST", "/rest/huntItems?upsert=true", item({ externalId: "sse-3" }));
  await api(tok, "POST", "/rest/huntItems?upsert=true", item({ externalId: "sse-4" }));
  const again = await collect(`${base}/api/stream?workspace=tyler`, { "last-event-id": lastId }, { type: "item.found", n: 2 });
  const found = again.filter(f => f.event === "item.found");
  assert.equal(found.length, 2);
  assert.ok(found[0].id! > lastId && found[1].id! > found[0].id!);
});

test("a workspace's stream never carries another workspace's events", async () => {
  const oTok = await token(["*"], "pat");
  await api(oTok, "POST", "/rest/metadata/huntTypes", { key: "upwork", label: "Upwork", icon: "upwork", version: "0.1.0" });
  const frames = await collect(`${base}/api/stream`, { authorization: `Bearer ${tok}` }, { type: "item.found", n: 1 }, async () => {
    await api(oTok, "POST", "/rest/huntItems?upsert=true", item({ externalId: "osman-only" }));
  }, 1500);
  assert.equal(frames.filter(f => f.event === "item.found").length, 0);
});

test("a burst of writes in one transaction reaches the client complete and in order (no event overtaken)", async () => {
  const batch = Array.from({ length: 30 }, (_, i) => item({ externalId: `burst-${i}`, target: `Burst ${i}` }));
  const frames = await collect(`${base}/api/stream?workspace=tyler`, {}, { type: "item.found", n: 30 },
    async () => { assert.equal((await api(tok, "POST", "/rest/batch/huntItems?upsert=true", batch)).body.counts.created, 30); }, 8000);
  const found = frames.filter(f => f.event === "item.found");
  assert.equal(found.length, 30);
  assert.deepEqual(found.map(f => f.id), found.map(f => f.id).slice().sort());
});

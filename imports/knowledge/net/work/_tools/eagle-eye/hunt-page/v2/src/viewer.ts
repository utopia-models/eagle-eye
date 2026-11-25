// The public one-shot viewer (utopiamodels.ai/v/<slug>): Loom's share page, copied. Two halves:
//   * GET /v/:slug[/file]  serves the page the sender rendered (VIEWER_DIR/<slug>/index.html, video.mp4, poster.jpg,
//     thumb.gif) with HTTP Range for the video. On Ra this is the tailnet copy; in production the Cloudflare Worker
//     (viewer-worker/) serves the same files from R2 and forwards only the beacon here.
//   * POST /v/:slug/e      the watch beacon: {e: "view"|"play"|"progress", pct: 0|25|50|75|100, sid, c}. No token: the
//     slug resolves its workspace (viewers.slug is unique and carries a random suffix). Each new milestone writes the
//     touch (opened_at, watched_s, watch_pct), moves the item forward (vsl_stage/reply_status 'watched') and appends a
//     touch.watch event, once per (slug, sid, milestone).
import { Hono } from "hono";
import { createReadStream, statSync, existsSync } from "node:fs";
import { join, normalize } from "node:path";
import { Readable } from "node:stream";
import { asOwner, withWorkspace, HttpError } from "./db.ts";
import { emit } from "./rest.ts";
import type { Actor } from "./keys.ts";

export const VIEWER_DIR = process.env.VIEWER_DIR || join(process.env.HOME || "/tmp", ".local/share/eagle-viewer");
const TYPES: Record<string, string> = { html: "text/html; charset=utf-8", mp4: "video/mp4", jpg: "image/jpeg", gif: "image/gif", png: "image/png", vtt: "text/vtt", json: "application/json", svg: "image/svg+xml" };
const SLUG = /^[a-z0-9][a-z0-9-]{3,80}$/;
const FILE = /^[a-z0-9][a-z0-9._-]{0,60}$/;
const PCTS = [0, 25, 50, 75, 100];
const ACTOR: Actor = { source: "WEBHOOK", name: "viewer" };

export function serveFile(c: any, path: string) {
  if (!existsSync(path)) throw new HttpError(404, "not found");
  const size = statSync(path).size;
  const type = TYPES[path.split(".").pop() || ""] || "application/octet-stream";
  const base = { "content-type": type, "accept-ranges": "bytes", "cache-control": type.startsWith("text/html") ? "no-cache" : "public, max-age=3600",
    "x-robots-tag": "noindex" };
  const range = c.req.header("range") as string | undefined;
  const m = range?.match(/^bytes=(\d*)-(\d*)$/);
  if (m && (m[1] || m[2])) {
    let start = m[1] ? Number(m[1]) : Math.max(size - Number(m[2]), 0);
    let end = m[1] && m[2] ? Math.min(Number(m[2]), size - 1) : size - 1;
    if (start >= size || start > end) return new Response(null, { status: 416, headers: { "content-range": `bytes */${size}` } });
    const body = Readable.toWeb(createReadStream(path, { start, end })) as ReadableStream;
    return new Response(body, { status: 206, headers: { ...base, "content-length": String(end - start + 1), "content-range": `bytes ${start}-${end}/${size}` } });
  }
  return new Response(Readable.toWeb(createReadStream(path)) as ReadableStream, { status: 200, headers: { ...base, "content-length": String(size) } });
}

/** Record one beacon. Returns what changed (for tests and the response body). */
export async function recordWatch(slug: string, b: { e?: string; pct?: number; sid?: string; c?: string; t?: number }) {
  if (!SLUG.test(slug)) throw new HttpError(404, "no viewer");
  const v = (await asOwner(tx => tx.query("select id, workspace_id, item_id from viewers where slug = $1 and deleted_at is null", [slug]))).rows[0];
  if (!v) throw new HttpError(404, "no viewer");
  const e = b.e === "view" ? "view" : b.e === "play" ? "play" : b.e === "progress" ? "progress" : null;
  if (!e) throw new HttpError(400, "e must be view|play|progress");
  const pct = e === "view" ? null : PCTS.includes(Number(b.pct)) ? Number(b.pct) : e === "play" ? 0 : null;
  if (e === "progress" && pct === null) throw new HttpError(400, "pct must be 0|25|50|75|100");
  const sid = String(b.sid || "").replace(/[^A-Za-z0-9_-]/g, "").slice(0, 40) || "anon";
  const channel = ["email", "linkedin", "upwork", "x", "sms", "call"].includes(String(b.c)) ? String(b.c) : null;
  const watchedS = Number.isFinite(Number(b.t)) ? Math.max(0, Math.min(Number(b.t), 36000)) : null;

  return withWorkspace(v.workspace_id, async tx => {
    const key = `${e}:${pct ?? ""}`;
    const dup = (await tx.query(
      `select 1 from events where item_id = $1 and type in ('touch.watch','viewer.view') and data->>'slug' = $2 and data->>'sid' = $3 and data->>'key' = $4 limit 1`,
      [v.item_id, slug, sid, key])).rowCount;
    if (dup) return { recorded: false, reason: "duplicate" };
    // the touch whose link was opened: ?c=<channel>, else the item's first sent touch
    const touch = (await tx.query(
      `select * from touches where item_id = $1 and status = 'sent' ${channel ? "and channel = $2" : ""} order by sent_at limit 1`,
      channel ? [v.item_id, channel] : [v.item_id])).rows[0]
      ?? (await tx.query(`select * from touches where item_id = $1 and status = 'sent' order by sent_at limit 1`, [v.item_id])).rows[0];
    if (touch) {
      await tx.query(
        `update touches set opened_at = coalesce(opened_at, now()),
           watch_pct = case when $2::smallint is null then watch_pct else greatest(coalesce(watch_pct, -1), $2::smallint) end,
           watched_s = case when $3::numeric is null then watched_s else greatest(coalesce(watched_s, 0), $3::numeric) end
         where id = $1`, [touch.id, pct, watchedS]);
    }
    if (pct !== null) {
      await tx.query(
        `update hunt_items set
           vsl_stage = case when vsl_stage in ('none','scripted','recorded','rendered','sent') then 'watched' else vsl_stage end,
           reply_status = case when reply_status in ('none','opened') then 'watched' else reply_status end
         where id = $1`, [v.item_id]);
    } else {
      await tx.query(`update hunt_items set reply_status = 'opened' where id = $1 and reply_status = 'none'`, [v.item_id]);
    }
    await emit(tx, { workspaceId: v.workspace_id, actor: ACTOR, itemId: v.item_id, type: pct === null ? "viewer.view" : "touch.watch",
      data: { slug, sid, key, e, pct, channel: touch?.channel ?? channel, touch_id: touch?.id ?? null, watched_s: watchedS } });
    return { recorded: true, touch_id: touch?.id ?? null, pct };
  });
}

export function viewerRoutes() {
  const v = new Hono();
  v.post("/v/:slug/e", async c => {
    // sendBeacon posts text/plain (no CORS preflight); accept either
    const raw = await c.req.text();
    let body: any = {};
    try { body = JSON.parse(raw || "{}"); } catch { throw new HttpError(400, "body is JSON"); }
    const out = await recordWatch(c.req.param("slug"), body);
    return c.json(out, 202);
  });
  v.get("/v/:slug", c => {
    const slug = c.req.param("slug");
    if (!SLUG.test(slug)) throw new HttpError(404, "not found");
    if (!c.req.path.endsWith("/")) return c.redirect(`/v/${slug}/`, 301);
    return serveFile(c, join(VIEWER_DIR, slug, "index.html"));
  });
  v.get("/v/:slug/", c => {
    const slug = c.req.param("slug");
    if (!SLUG.test(slug)) throw new HttpError(404, "not found");
    return serveFile(c, join(VIEWER_DIR, slug, "index.html"));
  });
  v.get("/v/:slug/:file", c => {
    const { slug, file } = c.req.param();
    if (!SLUG.test(slug) || !FILE.test(file)) throw new HttpError(404, "not found");
    const p = normalize(join(VIEWER_DIR, slug, file));
    if (!p.startsWith(normalize(join(VIEWER_DIR, slug)) + "/")) throw new HttpError(404, "not found");
    return serveFile(c, p);
  });
  return v;
}

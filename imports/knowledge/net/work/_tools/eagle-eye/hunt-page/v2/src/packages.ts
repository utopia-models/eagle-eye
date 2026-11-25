// The one-shot PACKAGE behind a hunt item, read from the folder the builders write (Tyler 11-22 ~3:55 AM MT: "there needs to be
// a SPECIFIC one-shot system for the specific Upwork job ... in Eagle Eye I want to be very clear which one-shot is associated with
// each hunt"). Derived on read from _shots/stream-vsl/hunts/<lane>/<slug>/, never stored: the folder is the truth.
//
//   niche  = the job's domain in a few words: architecture.yaml title before the colon ("AI chief of staff: system architecture"
//            -> "AI chief of staff"), else the post title's first clause; funding = the company
//   state  = what exists: MVP live (published mvp/) > Working demo (demo/run.txt) > Diagram only (architecture page) > Script only > Not built
//   url    = the one-shot's page as Eagle Eye serves it (:8450/hunts/<slug>/...)
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const SHOTS = process.env.VSL_SHOTS || "/home/architect/dev/utopia-models/_shots/stream-vsl";
const PUBLIC_URL = process.env.EAGLE_UI_URL || "https://ra.tail4016d7.ts.net:8450";
const LANES = ["upwork", "jobs", "funding", "investors"];

export type Pkg = { slug: string; lane: string; niche: string | null; state: string; url: string | null;
  parts: { mvp: boolean; demo: boolean; diagram: boolean; script: boolean; intro: boolean; video: boolean } };

const has = (...p: string[]) => existsSync(join(...p));
const read = (...p: string[]) => { try { return readFileSync(join(...p), "utf8"); } catch { return ""; } };

/** "AI chief of staff: system architecture" -> "AI chief of staff"; generic openers fall back to the post title. */
export function nicheOf(archTitle: string, postTitle: string): string | null {
  const clean = (s: string) => s.replace(/\s+/g, " ").replace(/^["']|["']$/g, "").trim();
  const cut = (s: string) => clean(s.split(/\s(?:with|on|in|for|through|around|to build|to)\s/i)[0].replace(/[,.;]+$/, ""));
  const noArch = (x: string) => clean(x).replace(/\s*\b(system )?architecture\b\s*/i, " ").trim();
  const [head, ...rest] = archTitle.split(":");
  let a = noArch(head);
  // "Tallis: agent tracking architecture": a one-word product name -> the words after the colon
  if (a && !a.includes(" ") && rest.length && noArch(rest.join(":"))) a = noArch(rest.join(":"));
  const tidy = (x: string) => x.replace(/\s+(needed|wanted|required)$/i, "");
  if (a && !/^(one|your|the)\b/i.test(a)) return tidy(cut(a));
  const t = clean(postTitle).split(/\s[|–—-]\s|\s\/\s|\(|:/)[0];
  return t ? tidy(cut(t)) : null;
}

let cache: { at: number; byKey: Map<string, Pkg> } | null = null;

function describe(lane: string, slug: string): Pkg {
  const dir = join(SHOTS, "hunts", lane, slug), pub = join(SHOTS, "eagle-eye-spike/public/hunts", slug);
  const archTitle = (read(dir, "architecture.yaml").match(/^title:\s*(.+)$/m) || [])[1] || "";
  const md = read(dir, `${slug}.md`);
  const postTitle = (md.match(/^#\s+(.+?)\s*(\((Upwork|job post|funding hunt[^)]*)\))?\s*$/m) || [])[1] || "";
  const niche = lane === "funding" ? (postTitle.split(/\s[·|]\s/)[0] || null) : nicheOf(archTitle, postTitle);
  const parts = {
    mvp: has(pub, "mvp/index.html"),
    demo: has(dir, "demo/run.txt") || has(dir, "demo/app"),
    diagram: has(dir, "demo/architecture/architecture.html") || has(pub, "demo/architecture/architecture.html"),
    script: has(dir, "tyler-script.md") || has(dir, "script.md"),
    intro: has(dir, "intro-line.md") || has(dir, "intro.md"),
    video: readdirSync(dir).some(f => /^vsl.*\.mp4$/.test(f) && !/pre-fix|orb/.test(f)),
  };
  const state = parts.mvp ? "MVP live" : parts.demo ? "Working demo" : parts.diagram ? "Diagram only" : parts.script ? "Script only" : "Not built";
  const url = parts.mvp ? `${PUBLIC_URL}/hunts/${slug}/mvp/`
    : has(pub, "demo/index.html") ? `${PUBLIC_URL}/hunts/${slug}/demo/index.html`
    : parts.diagram ? `${PUBLIC_URL}/hunts/${slug}/demo/architecture/architecture.html` : null;
  return { slug, lane, niche, state, url, parts };
}

/** slug -> Pkg and upwork job key (~02...) -> Pkg, rebuilt at most every 30 s (≈60 folders, stat + small reads). */
function index() {
  if (cache && Date.now() - cache.at < 30_000) return cache.byKey;
  const byKey = new Map<string, Pkg>();
  for (const lane of LANES) {
    const root = join(SHOTS, "hunts", lane);
    if (!existsSync(root)) continue;
    for (const slug of readdirSync(root)) {
      if (slug === "agent" || !statSync(join(root, slug)).isDirectory()) continue;
      const p = describe(lane, slug);
      byKey.set(slug, p);
      const job = (read(root, slug, "tabs.txt") + read(root, slug, `${slug}.md`).slice(0, 400)).match(/~(0[12]\d{10,})/);
      if (job && !byKey.has("~" + job[1])) byKey.set("~" + job[1], p);
    }
  }
  cache = { at: Date.now(), byKey };
  return byKey;
}

/** The package a feed row points at: details.oneshot.file / its talk-script label / its page URL / details.tabs path / the job key. */
export function packageFor(r: { external_id?: string; details?: any; target?: string }): Pkg | null {
  const m = index(), d = r.details || {}, o = d.oneshot || {};
  const cands = [o.file, (String(o.label || "").match(/talk-script\s+([\w-]+)/) || [])[1],
    (String(o.url || "").match(/\/hunts\/([^/]+)\//) || [])[1], (String(d.tabs || "").match(/hunts\/\w+\/([^/]+)\/tabs\.txt/) || [])[1],
    d.slug, r.external_id];
  // funding packages are named for the company (hunts/funding/river, .../luwian): "Luwian AI Inc" -> luwian
  const co = String(r.target || "").toLowerCase().replace(/[^a-z0-9 ]/g, "").trim();
  if (co) cands.push(co.replace(/ /g, ""), co.split(" ")[0]);
  for (const c of cands) if (c && m.has(c) && (c !== co.split(" ")[0] && c !== co.replace(/ /g, "") || m.get(c)!.lane === "funding")) return m.get(c)!;
  return null;
}

/** The "How this one-shot works" page for a system (another agent publishes it at :8450/oneshot/<key>/): its path once the file
 *  exists, else null, so Eagle Eye never links to a 404. */
export function oneShotPage(key: string): string | null {
  return has(SHOTS, "eagle-eye-spike/public/oneshot", key, "index.html") ? `/oneshot/${key}/` : null;
}

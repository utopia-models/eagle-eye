import { useEffect, useMemo, useState } from "react"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { ShimmerButton } from "@/components/ui/shimmer-button"

// The cold-apps page (Tyler 2026-11-17; fleetmail 8565, 8740): every application with its CAMPAIGN STEP CHIPS
// (done / pending / replied) on every row; a click opens a right Sheet with all its data. Data: /apps.json (apps_feed.py).
// Components: shadcn Table, Badge, Sheet; Magic UI ShimmerButton. No application counts as a headline (Tyler: no vanity metrics).
const GREEN = "border-green-500/40 text-green-400"
const fmt = (t?: string) => (t ? new Date(t).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "-")
const ago = (t?: string) => { const m = t ? (Date.now() - Date.parse(t)) / 60000 : NaN; return !isFinite(m) ? "-" : m < 90 ? Math.max(1, Math.round(m)) + " min" : m < 2880 ? Math.round(m / 60) + " h" : Math.round(m / 1440) + " d" }
const A = ({ href, children }: any) => <a className="text-primary underline-offset-4 hover:underline" href={href} target="_blank" rel="noopener" onClick={e => e.stopPropagation()}>{children}</a>
const sent = (x: any) => x && /^(sent|accepted|replied)$/.test(x.s || "")
const hot = (s: string) => /interview|screen|offer|assessment/.test(String(s))

// Every campaign at once (Tyler 2026-11-16, knowledge#14280: "see all campaign data ... doesn't need to be perfect"): one row per
// campaign step, counting each person's state across every company. Counts are step states, not application totals.
function rollup(D: any, steps: any[]) {
  const cos = Object.values(D?.companies || {}).map((c: any) => c.campaign).filter(Boolean) as any[]
  const people = cos.flatMap(k => k.people || [])
  const rows = steps.filter(s => (s.per || "person") === "person").map(s => {
    const n: Record<string, number> = {}
    for (const p of people) { const st = (p.steps || {})[s.id]; if (st) { const key = /^(sent|accepted|replied|skipped|none)$/.test(st.s) ? st.s : /^planned/.test(st.s) ? "planned" : "waiting"; n[key] = (n[key] || 0) + 1 } }
    return { id: s.id, label: s.label || s.id, live: s.live !== false, n }
  })
  return { companies: cos.filter(k => (k.people || []).length).length, people: people.length, vsl: cos.reduce((t, k) => t + (k.vsl || []).filter((v: any) => v.url).length, 0), rows }
}
function Rollup({ D, steps }: { D: any; steps: any[] }) {
  const r = useMemo(() => rollup(D, steps), [D, steps])
  const cols: [string, string][] = [["sent", "Sent"], ["accepted", "Accepted"], ["replied", "Replied"], ["waiting", "Waiting"], ["planned", "Planned"]]
  return (
    <section aria-label="All campaigns" className="mb-4 rounded-md border p-3">
      <h2 className="text-xs tracking-widest text-primary">ALL CAMPAIGNS</h2>
      <p className="mt-1 text-sm text-muted-foreground">{r.people} {r.people === 1 ? "person" : "people"} targeted at {r.companies} {r.companies === 1 ? "company" : "companies"} · {r.vsl} VSL{r.vsl === 1 ? "" : "s"} recorded. Steps still marked waiting are channels not live yet.</p>
      <div className="mt-2 overflow-x-auto"><Table>
        <TableHeader><TableRow><TableHead>Step</TableHead>{cols.map(([, l]) => <TableHead key={l} className="text-right">{l}</TableHead>)}</TableRow></TableHeader>
        <TableBody>{r.rows.map(x => <TableRow key={x.id}><TableCell>{x.label}{!x.live && <Badge variant="outline" className="ml-2 border-dashed text-muted-foreground">not live</Badge>}</TableCell>
          {cols.map(([k]) => <TableCell key={k} className={"text-right tabular-nums " + (x.n[k] ? "" : "text-muted-foreground")}>{x.n[k] || 0}</TableCell>)}</TableRow>)}</TableBody>
      </Table></div>
    </section>)
}

// One row's chips, in campaign order: Applied -> People -> SalesBlaster -> VSL -> Reply. done = green, replied = gold, pending = grey.
function chips(a: any, c: any, steps: any[]) {
  const k = c.campaign || {}, sb = steps.find(s => s.id === "sb_email")
  const np = (k.people || []).length, sbSent = (k.people || []).some((p: any) => sent((p.steps || {}).sb_email))
  const vsl = (k.vsl || []).some((v: any) => v.posting === a.id && v.url)
  const reply = (c.replies || []).length > 0 || hot(a.out)
  return [["Applied", true, false], ["People" + (np ? " " + np : ""), np > 0, false], ["SalesBlaster", sbSent, sb && !sb.live], ["VSL", vsl, false], ["Reply", reply, true]] as [string, boolean, boolean][]
}
function Chip({ label, done, isReply }: { label: string; done: boolean; isReply: boolean }) {
  return done ? (isReply ? <Badge>{label}</Badge> : <Badge variant="outline" className={GREEN}>{label}</Badge>) : <Badge variant="outline" className="border-dashed text-muted-foreground">{label}</Badge>
}

export function AppsPage({ initial }: { initial?: any } = {}) {
  const [D, setD] = useState<any>(initial || null), [sel, setSel] = useState<any>(null), [q, setQ] = useState(""), [shown, setShown] = useState(60), [err, setErr] = useState("")
  const load = () => fetch("/apps.json?" + Date.now(), { cache: "no-store" }).then(r => (r.ok ? r.json() : Promise.reject(r.status))).then(d => { setD(d); setErr("") }).catch(e => setErr(String(e)))
  useEffect(() => { if (initial) return; load(); const a = setInterval(load, 30000); return () => clearInterval(a) }, [])
  const steps = D?.campaign_steps || []
  const rows = useMemo(() => (D ? D.apps.filter((a: any) => !q || (a.co + " " + a.role).toLowerCase().includes(q.toLowerCase())) : []), [D, q])
  const alerts = useMemo(() => { if (!D) return []; const seen = new Set<string>(); return D.apps.filter((a: any) => (((D.companies[a.k] || {}).replies || []).length > 0 || hot(a.out)) && !seen.has(a.k) && seen.add(a.k)) }, [D])
  const c = sel ? D.companies[sel.k] || {} : {}, k = c.campaign || {}
  return (
    <main className="mx-auto max-w-6xl border-t-2 border-primary/60 p-4 pt-6">
      <div className="flex flex-wrap items-start justify-between gap-3 pb-4">
        <div>
          <a href="/" className="text-xs tracking-widest text-primary">&larr; EAGLE EYE</a>
          <h1 className="font-serif text-4xl font-bold tracking-wide text-primary">Cold apps</h1>
          <p className="text-sm text-muted-foreground">Newest application first. Green = done, grey = pending, gold = replied. Each row shows its campaign: applied, people, SalesBlaster, VSL, reply. Click one for everything on it.</p>
        </div>
        <ShimmerButton onClick={load} shimmerColor="#d9b35b" background="rgba(7,7,6,1)" borderRadius="6px" className="shrink-0 border-primary/60 px-4 py-2 text-sm text-primary tracking-widest">REFRESH</ShimmerButton>
      </div>
      {D && steps.length > 0 && <Rollup D={D} steps={steps} />}
      {alerts.length > 0 && <div role="status" className="mb-3 rounded-md border border-primary/60 bg-primary/10 p-3 text-sm"><div className="mb-2 font-medium">{alerts.length > 1 ? "Replies and invites" : "Reply or invite"}</div>
        <div className="flex flex-wrap gap-2">{alerts.slice(0, 6).map((a: any) => <Badge key={a.id} className="cursor-pointer" onClick={() => setSel(a)}>{a.co}{hot(a.out) ? " · " + a.out : " · replied"}</Badge>)}</div></div>}
      <input value={q} onChange={e => { setQ(e.target.value); setShown(60) }} placeholder="Filter by company or role" aria-label="Filter"
        className="mb-3 h-9 w-full rounded-md border border-input bg-background px-3 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring sm:max-w-xs" />
      <div className="rounded-md border">
        <Table>
          <TableHeader><TableRow>{[["Application", ""], ["Applied", "hidden sm:table-cell"], ["Campaign", ""]].map(([h, c]) => <TableHead key={h} className={c}>{h}</TableHead>)}</TableRow></TableHeader>
          <TableBody>
            {rows.length === 0 && <TableRow><TableCell colSpan={3} className="text-muted-foreground">{err ? "Offline: " + err : D ? "No applications match." : "Loading."}</TableCell></TableRow>}
            {rows.slice(0, shown).map((a: any) => {
              const co = D.companies[a.k] || {}
              return (
                <TableRow key={a.id} tabIndex={0} className="cursor-pointer" onClick={() => setSel(a)} onKeyDown={e => e.key === "Enter" && setSel(a)}>
                  <TableCell className="max-w-[10rem] sm:max-w-none"><div className="font-serif text-lg font-bold leading-tight">{a.co}</div><div className="text-xs text-muted-foreground">{a.role}</div><div className="mt-1 text-xs text-muted-foreground sm:hidden">{ago(a.at)} ago</div>{a.out !== "submitted" && <div className="mt-1"><Badge variant={hot(a.out) ? "default" : "secondary"}>{a.out}</Badge></div>}</TableCell>
                  <TableCell className="hidden sm:table-cell"><Badge variant="secondary" title={fmt(a.at)}>{ago(a.at)}</Badge></TableCell>
                  <TableCell><div className="flex flex-wrap gap-1 text-[11px]">{chips(a, co, steps).map(([l, d, r]) => <Chip key={l} label={l} done={d} isReply={r} />)}</div></TableCell>
                </TableRow>)
            })}
          </TableBody>
        </Table>
      </div>
      {rows.length > shown && <div className="mt-3"><ShimmerButton onClick={() => setShown(shown + 60)} shimmerColor="#d9b35b" background="rgba(7,7,6,1)" borderRadius="6px" className="border-primary/60 text-primary tracking-widest">SHOW MORE</ShimmerButton></div>}
      <Sheet open={!!sel} onOpenChange={o => !o && setSel(null)}>
        <SheetContent side="right" className="w-full overflow-auto data-[state=open]:animate-none data-[state=open]:duration-0 sm:max-w-md">
          {sel && <>
            <SheetHeader><SheetTitle>{sel.co}</SheetTitle><SheetDescription>{sel.role}</SheetDescription></SheetHeader>
            <h3 className="mt-4 text-xs tracking-widest text-primary">APPLICATION</h3>
            <dl className="mt-2 grid grid-cols-[6rem_1fr] gap-2 text-sm">
              {[["Applied", fmt(sel.at)], ["Posted", sel.posted ? fmt(sel.posted) : "not recorded"], ["Status", sel.out], ["Posting", sel.url ? <A href={sel.url}>{sel.url.replace(/^https?:\/\//, "")}</A> : ""],
                ["Role type", sel.rt], ["ATS", sel.ats + " · " + sel.src], ["Where", [sel.loc, sel.lvl].filter(Boolean).join(" · ")],
                ["Post to apply", sel.tta != null ? Math.round(sel.tta / 60) + " min" : ""], ["Resume", [sel.rv, sel.r].filter(Boolean).join(" · ")],
                ["Emails sent", (c.emails || []).length ? String((c.emails || []).length) : ""], ["Replies", (c.replies || []).length ? String((c.replies || []).length) : "none yet"]].filter(x => x[1]).map(x => <><dt className="text-muted-foreground">{x[0]}</dt><dd className="min-w-0 break-all">{x[1]}</dd></>)}
            </dl>
            <h3 className="mt-5 text-xs tracking-widest text-primary">CAMPAIGN AT {String(sel.co).toUpperCase()}</h3>
            <p className="mt-1 text-xs text-muted-foreground">LinkedIn steps are sent by Desk Sekhmet (the LinkedIn desk).</p>
            <div className="mt-2 flex flex-wrap gap-1">{chips(sel, c, steps).map(([l, d, r]) => <Chip key={l} label={l} done={d} isReply={r} />)}</div>
            {(k.people || []).length === 0 && <p className="mt-2 text-sm text-muted-foreground">No one targeted yet.</p>}
            {(k.people || []).map((p: any) => (
              <div key={p.name} className="mt-3 rounded-md border p-2 text-sm"><div className="font-medium">{p.name}</div><div className="text-xs text-muted-foreground">{p.title}</div>
                <div className="mt-1 flex flex-wrap gap-1">{Object.entries(p.steps || {}).map(([id, v]: any) =>
                  <Badge key={id} variant={sent(v) ? "outline" : "secondary"} className={sent(v) ? GREEN : ""}>{(steps.find((s: any) => s.id === id) || { label: id }).label}: {v.s || "planned"}</Badge>)}</div></div>))}
            {(k.copy || []).length > 0 && <><h3 className="mt-5 text-xs tracking-widest text-primary">REFERRAL COPY</h3>{(k.copy || []).map((x: any, i: number) =>
              <div key={i} className="mt-2 rounded-md border p-2 text-sm"><div className="text-xs text-muted-foreground">{x.name} · {x.channel} · {x.state}</div><p className="mt-1 whitespace-pre-wrap">{x.text}</p></div>)}</>}
          </>}
        </SheetContent>
      </Sheet>
    </main>)
}

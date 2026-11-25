import { useEffect, useMemo, useState } from "react"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { ShimmerButton } from "@/components/ui/shimmer-button"

// The Upwork jobs page (Tyler 2026-11-17; fleetmail 8493 8494 8565 8591 8687): every matched job, freshest first.
// Data: /upwork.json (upwork_feed.py `matches` + `applied`). Components: shadcn Table, Badge, Sheet; Magic UI ShimmerButton.
type Job = any
const GREEN = "border-green-500/40 text-green-400", AMBER = "border-amber-400/40 text-amber-300"
const STAT: Record<string, [any, string]> = { "Proposal Drafting": ["default", ""], "Awaiting Reply": ["outline", "border-primary/50 text-primary"],
  "In Conversation": ["default", ""], Won: ["default", ""], Lost: ["destructive", ""], Passed: ["secondary", ""],
  "Awaiting VSL": ["secondary", ""], "Awaiting Demo": ["secondary", ""] }
const fmt = (t?: string) => (t ? new Date(t).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "-")

// Target: apply within 6 h of posting. green < 6 h, amber 6-24 h, grey older, "-" when the feed has no posted time.
function Age({ t }: { t?: string }) {
  const h = t ? (Date.now() - Date.parse(t)) / 36e5 : NaN
  if (!isFinite(h)) return <Badge variant="outline" title="no posted time yet">-</Badge>
  const x = h < 1 ? Math.max(1, Math.round(h * 60)) + " min" : h < 48 ? Math.round(h * 10) / 10 + " h" : Math.round(h / 24) + " d"
  return h < 6 ? <Badge variant="outline" className={GREEN} title="on target: under 6 h">{x}</Badge>
    : h < 24 ? <Badge variant="outline" className={AMBER} title="6 to 24 h since posting">{x}</Badge> : <Badge variant="secondary" title="older than a day">{x}</Badge>
}
const A = ({ href, children }: any) => <a className="text-primary underline-offset-4 hover:underline" href={href} target="_blank" rel="noopener" onClick={e => e.stopPropagation()}>{children}</a>

function toRows(UP: any): Job[] {
  const M = (UP.matches || []).map((m: any) => ({ id: "m" + m.key, at: m.postedAt, title: m.title || m.key, why: (m.why || []).slice(0, 2).join(" · "), posted: m.postedAt,
    demo: m.demo, owner: m.owner, vsl: m.vsl, script: m.vslScript, status: m.statusWord || m.status, noVsl: false, m }))
  const Ap = (UP.applied || []).map((a: any) => ({ id: "a" + a.key, at: a.job?.posted || a.sentAt, title: a.title || a.key, why: "", posted: a.job?.posted, demo: a.demo, owner: "upwork",
    vsl: !!(a.vsl && (a.vsl.recorded || a.vsl.attached)), script: false, status: a.statusWord || "Awaiting Reply", noVsl: !!a.pipeline?.noVsl, a }))
  return [...M, ...Ap].sort((x, y) => Date.parse(y.at || 0) - Date.parse(x.at || 0))
}

export function App({ initial }: { initial?: any } = {}) {
  const [UP, setUP] = useState<any>(initial || null), [, tick] = useState(0), [sel, setSel] = useState<Job | null>(null)
  const load = () => fetch("/upwork.json?" + Date.now(), { cache: "no-store" }).then(r => (r.ok ? r.json() : null)).then(d => d && setUP(d)).catch(() => {})
  useEffect(() => {
    load(); const a = setInterval(load, 60000), b = setInterval(() => tick(n => n + 1), 60000); return () => { clearInterval(a); clearInterval(b) }
  }, [])
  const rows = useMemo(() => (UP ? toRows(UP) : []), [UP])
  return (
    <main className="mx-auto max-w-6xl border-t-2 border-primary/60 p-4 pt-6">
      <div className="flex flex-wrap items-start justify-between gap-3 pb-4">
        <div>
          <div className="flex gap-4 text-xs tracking-widest"><a href="/" className="text-primary">&larr; EAGLE EYE</a><a href="https://architecture.utopiamodels.ai/vsl-system" target="_blank" rel="noopener" className="text-primary">VSL SYSTEM &#8599;</a></div>
          <h1 className="font-serif text-4xl font-bold tracking-wide text-primary">Upwork jobs</h1>
          <p className="text-sm text-muted-foreground">Every matched job, freshest first. Apply within 6 hours of posting; a proposal goes out only when its VSL is recorded.</p>
        </div>
        <ShimmerButton onClick={load} shimmerColor="#d9b35b" background="rgba(7,7,6,1)" borderRadius="6px" className="shrink-0 border-primary/60 px-4 py-2 text-sm text-primary tracking-widest">REFRESH</ShimmerButton>
      </div>
      <div className="rounded-md border">
        <Table>
          <TableHeader><TableRow>{[["Job", ""], ["Posted", ""], ["Demo", "hidden sm:table-cell"], ["VSL", "hidden sm:table-cell"], ["Status", ""]].map(([c, k]) => <TableHead key={c} className={k}>{c}</TableHead>)}</TableRow></TableHeader>
          <TableBody>
            {rows.length === 0 && <TableRow><TableCell colSpan={5} className="text-muted-foreground">{UP ? "No matched jobs yet." : "Loading."}</TableCell></TableRow>}
            {rows.map(r => {
              const st = STAT[r.status] || ["secondary", ""]
              return (
                <TableRow key={r.id} tabIndex={0} className={"cursor-pointer " + (r.noVsl ? "bg-destructive/15" : "")} onClick={() => setSel(r)} onKeyDown={e => e.key === "Enter" && setSel(r)}>
                  <TableCell><div className="font-serif text-lg font-bold leading-tight">{r.title || "Untitled job " + r.id.slice(1, 8) + "…"}</div>{r.why && <div className="text-xs text-muted-foreground">{r.why}</div>}
                    <div className="mt-1 flex flex-wrap gap-1 sm:hidden"><Badge variant="secondary">Demo: {r.demo?.url && (r.demo.ready || r.demo.live) ? "ready" : r.demo?.slug ? "building" : "none"}</Badge>
                      <Badge variant={r.noVsl ? "destructive" : "secondary"}>VSL: {r.vsl ? "recorded" : r.script ? "script ready" : "none"}</Badge></div>
                    {r.noVsl && <div className="mt-1"><Badge variant="destructive">SENT WITHOUT A VSL</Badge></div>}</TableCell>
                  <TableCell className="whitespace-nowrap"><Age t={r.posted} /></TableCell>
                  <TableCell className="hidden sm:table-cell">{r.demo?.url && (r.demo.ready || r.demo.live) ? <A href={r.demo.url}>ready ↗</A>
                    : r.demo?.slug ? <><Badge variant="secondary">building</Badge><div className="text-xs text-muted-foreground">owner: {r.owner}</div></> : <Badge variant="outline">none</Badge>}</TableCell>
                  <TableCell className="hidden sm:table-cell">{r.vsl ? <Badge>recorded</Badge> : r.script ? <Badge variant="outline" className="border-primary/60 text-primary">script ready</Badge>
                    : <Badge variant={r.noVsl ? "destructive" : "outline"}>none</Badge>}</TableCell>
                  <TableCell><Badge variant={st[0]} className={st[1] + " whitespace-nowrap"}>{r.status}</Badge></TableCell>
                </TableRow>)
            })}
          </TableBody>
        </Table>
      </div>
      <p className="mt-4 text-sm text-muted-foreground">{UP?.computedAt ? "Read from the upwork agent ledger " + fmt(UP.computedAt) + "." : ""}</p>
      <Sheet open={!!sel} onOpenChange={o => !o && setSel(null)}>
        <SheetContent side="right" className="w-full overflow-auto data-[state=open]:animate-none data-[state=open]:duration-0 sm:max-w-md">
          {sel && <>
            <SheetHeader><SheetTitle>{sel.title}</SheetTitle>
              <SheetDescription>{sel.m ? sel.m.statusWord + " · owner: " + sel.m.owner : "Sent " + fmt(sel.a.sentAt)}</SheetDescription></SheetHeader>
            <dl className="mt-4 grid grid-cols-[6rem_1fr] gap-2 text-sm">
              {(sel.m ? [["Job", <A href={sel.m.url}>Upwork post</A>], ["Posted", fmt(sel.m.postedAt)],
                  ["Demo", sel.m.demo?.ready ? <A href={sel.m.demo.url}>{sel.m.demo.url}</A> : sel.m.demo?.slug ? "building: " + sel.m.demo.slug : "none"],
                  ["Run-sheet", sel.m.runsheet], ["VSL", sel.m.vsl ? "recorded" : sel.m.vslScript ? "script ready" : "none"], ["Why it fits", (sel.m.why || []).join(" · ")], ["Note", sel.m.note]]
                : [["Job", <A href={sel.a.url}>Upwork post</A>], ["Status", sel.a.status], ["Bid", sel.a.bid != null ? "$" + sel.a.bid : ""], ["Demo", sel.a.demo?.url ? <A href={sel.a.demo.url}>{sel.a.demo.url}</A> : ""],
                  ["VSL", sel.a.vsl?.file || (sel.a.vsl?.attached ? "attached" : "none")], ["Next", sel.a.next]]
              ).filter((x: any) => x[1]).map((x: any) => <><dt className="text-muted-foreground">{x[0]}</dt><dd className="min-w-0 break-all">{x[1]}</dd></>)}
            </dl></>}
        </SheetContent>
      </Sheet>
    </main>)
}

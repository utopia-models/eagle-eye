import { useEffect, useMemo, useState } from "react"
import NumberFlow from "@number-flow/react"
import { motion, MotionConfig } from "motion/react"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Tracker } from "@/components/ui/tracker"
import { BarList } from "@/components/ui/bar-list"

// The generic lane page, /hunt/<id> and /roost/<id> (knowledge#14769; replaces the hand-built lane.html table + drawer).
// Data: /data.json (the lane's totals) + /lanes.json (rows of the last N days, companies, tiers), both from feed.py.
// Components: shadcn Table, Badge, Sheet, Tabs; Tremor Raw Tracker + BarList; motion; @number-flow/react.
const DAY = 864e5, FOLLOW_D = 5
const nk = (s: any) => String(s || "").toLowerCase().replace(/[^a-z0-9]/g, "")
const KINDS: Record<string, string> = { "event new": "event found", sent: "message sent" }
const kind = (k: any) => { const t = String(k || "").replace(/_/g, " ").trim(); return KINDS[t] || t }
const ago = (ts: string) => { const m = (Date.now() - Date.parse(ts)) / 6e4; if (m < 0) { const f = -m; return f < 90 ? `in ${Math.round(f)} min` : f < 2880 ? `in ${Math.round(f / 60)} h` : `in ${Math.round(f / 1440)} d` }
  return m < 90 ? `${Math.round(m)} min ago` : m < 2880 ? `${Math.round(m / 60)} h ago` : `${Math.round(m / 1440)} d ago` }
const short = (ts?: string) => { if (!ts) return "–"; const m = Math.max(0, (Date.now() - Date.parse(ts)) / 6e4); return m < 90 ? `${Math.round(m)}m` : m < 2880 ? `${Math.round(m / 60)}h` : `${Math.round(m / 1440)}d` }

// A next step the store wrote is shown as it is; otherwise this rule over the row's stage, replies, VSLs and age (knowledge#14131).
export function nextAction(r: any): [string, boolean] {
  if (r.next) return [String(r.next), false]
  const st = String(r.stage || "").toLowerCase(), v = r.vsls || 0
  const age = r.last ? (Date.now() - Date.parse(r.last)) / DAY : null
  const due = r.last ? new Date(Date.parse(r.last) + FOLLOW_D * DAY).toLocaleDateString([], { month: "short", day: "numeric" }) : ""
  if (/reject|cancel|declin|lost|closed/.test(st)) return ["none: closed", true]
  if (/offer/.test(st)) return ["negotiate the offer", false]
  if (/interview|screen|assessment/.test(st)) return [age != null && age < 0 ? `prep for the ${st.split(/[^a-z]/)[0]}` : `send a thank-you${v ? "" : " + VSL"}`, false]
  if (/not sent|draft/.test(st)) return ["send the proposal", false]
  if (/contract|hourly|paid|milestone|direct|hired/.test(st)) return [v ? "deliver, then invoice" : "send an upsell VSL", false]
  if (r.replies > 0) return [v ? "book the call" : "reply with a VSL", false]
  if (r.sent) { if (age != null && age >= FOLLOW_D) return [v ? "follow up" : "follow up with a VSL", false]; return [`wait for a reply${due ? " · follow up " + due : ""}`, true] }
  return [r.side === "roost" ? "reach out with a VSL" : "first touch", false]
}

// Status is a sand ring, not a word (empty = sent, half = replied, full = call or hired, struck = closed); the word is its title.
export function Ring({ stage, replies }: { stage?: string; replies?: number }) {
  const s = String(stage || "").toLowerCase()
  const closed = /reject|cancel|declin|lost|closed/.test(s), full = /interview|screen|offer|contract|hired|paid|call/.test(s), half = !full && (replies || 0) > 0
  const label = stage || (replies ? "replied" : "sent")
  return <svg role="img" aria-label={label} width="18" height="18" viewBox="0 0 18 18" className="shrink-0"><title>{label}</title>
    <circle cx="9" cy="9" r="6.5" fill={full ? "#d9b35b" : "none"} stroke={closed ? "#6b6350" : "#d9b35b"} strokeWidth="1.5" />
    {half && <path d="M9 2.5a6.5 6.5 0 0 1 0 13z" fill="#d9b35b" />}{closed && <path d="M3.5 14.5L14.5 3.5" stroke="#6b6350" strokeWidth="1.5" />}</svg>
}

type Row = { id: string; name: string; sub?: string; ring: [string?, number?]; last?: string; chips: [string, number][]; vsls: number; nx: [string, boolean]; tier?: number; events: any[] }

export function toRows(key: string, side: string, D: any, LF: any): Row[] {
  const lane = (LF.lanes || {})[key] || { events: [], companies: [] }
  const all = LF.companies || {}, blk = (side === "hunt" ? (D?.hunts || {})[key] : (D?.roosts || {})[key]) || null
  const evs: any[] = (lane.events || []).filter((e: any) => !e.up)
  const rowsOf = ((blk && blk.rows) || []) as any[]
  if (key === "in_person") return evs.map((e, i) => { const dt = (String(e.what || "").match(/(\d{4}-\d{2}-\d{2})/) || [])[1], fut = dt && Date.parse(dt + "T23:59:59") >= Date.now()
    return { id: "e" + i, name: e.co || "—", sub: e.what, ring: [fut ? "upcoming" : "found", 0], last: e.ts, chips: [], vsls: 0, nx: [fut ? "RSVP, go, log who you met" : "log who you met (or none)", !fut], events: [e] } })
  if (side === "roost" && rowsOf.length && !(lane.companies || []).length) return rowsOf.map((r, i) => { const c = all[nk(r.name)] || {}
    return { id: "p" + i, name: r.name || "—", sub: [r.stage, r.what].filter(Boolean).join(" · "), ring: [r.stage, 1], last: r.at, chips: [], vsls: c.vsls || 0,
      nx: r.next ? [r.next, false] : nextAction({ stage: /reject|cancel|contract|hourly|paid/i.test(r.stage || "") ? r.stage : "", replies: 1, vsls: c.vsls || 0, last: r.at, side }), events: evs.filter(e => nk(e.co) === nk(r.name)) } })
  const roost: Record<string, any> = {}; rowsOf.forEach(r => { roost[nk(r.name)] = r })
  return (lane.companies || []).map((k: string) => { const c = all[k] || {}, rr = roost[k] || roost[nk(String(c.name || "").split(" ")[0])] || {}, st = c.stage || rr.stage
    return { id: k, name: c.name || k, ring: [st, c.replies], last: c.last, tier: c.tier, vsls: c.vsls || 0, sub: st,
      chips: ([["apps", c.apps], ["mail", c.emails], ["proposals", c.proposals], ["replies", c.replies]] as [string, number][]).filter(x => x[1]),
      nx: nextAction({ stage: st, replies: c.replies, vsls: c.vsls, sent: (c.apps || 0) + (c.emails || 0) + (c.proposals || 0), last: c.last, next: c.next, side }),
      events: evs.filter(e => nk(e.co) === nk(c.name || k)) } }).sort((a: Row, b: Row) => String(b.last || "").localeCompare(String(a.last || "")))
}

// Sand river: one grain per day for the span the feed covers, brightness = how much happened, a pale glint where something came back.
export function river(evs: any[], days: number) {
  const out: { n: number; back: boolean; d: Date }[] = []
  for (let i = days - 1; i >= 0; i--) { const d = new Date(Date.now() - i * DAY); out.push({ n: 0, back: false, d }) }
  evs.filter(e => !e.up).forEach(e => { const i = days - 1 - Math.floor((Date.now() - Date.parse(e.ts)) / DAY); if (i >= 0 && i < days) { out[i].n++; if (/repl|back|receiv|interview|call/.test(String(e.kind))) out[i].back = true } })
  const mx = Math.max(1, ...out.map(o => o.n))
  return out.map(o => ({ color: o.back ? "#f3dc9a" : o.n ? `rgba(217,179,91,${0.25 + 0.65 * o.n / mx})` : "rgba(217,179,91,.08)",
    tooltip: `${o.d.toLocaleDateString([], { month: "short", day: "numeric" })}: ${o.n} ${o.n === 1 ? "event" : "events"}${o.back ? ", something came back" : ""}` }))
}

export function LanePage({ lanes, initial }: { lanes?: any; initial?: { D: any; LF: any; path: string } }) {
  const LANES = lanes || (window as any).__LANES__ || {}
  const path = initial?.path || location.pathname
  const m = path.match(/^\/(hunt|roost)\/([a-z_-]+)/) || [], side = m[1] || "", key = (m[2] || "").replace(/-/g, "_"), L = LANES[key]
  const [D, setD] = useState<any>(initial?.D || null), [LF, setLF] = useState<any>(initial?.LF || null)
  const [sel, setSel] = useState<string | null>(() => (typeof location !== "undefined" ? location.hash.slice(1) : "") || null), [all, setAll] = useState(false)
  useEffect(() => {
    if (initial) return
    const load = async () => { try { const [a, b] = await Promise.all([fetch("/data.json?" + Date.now(), { cache: "no-store" }), fetch("/lanes.json?" + Date.now(), { cache: "no-store" })])
      setD(await a.json()); const lf = await b.json(); setLF(lf && lf.lanes ? lf : { lanes: {}, companies: {}, tiers: [], event_days: 7 }) } catch { setLF((x: any) => x || { lanes: {}, companies: {}, tiers: [] }) } }
    load(); const t = setInterval(load, 30000); return () => clearInterval(t)
  }, [])
  useEffect(() => { const h = () => setSel(location.hash.slice(1) || null); addEventListener("hashchange", h); return () => removeEventListener("hashchange", h) }, [])
  const open = (id: string | null) => { if (id) location.hash = id; else history.replaceState(null, "", location.pathname + location.search); setSel(id) }
  const blk = D && L ? (side === "hunt" ? (D.hunts || {})[key] : (D.roosts || {})[key]) : null
  const rows = useMemo(() => (LF && L ? toRows(key, side, D, LF) : []), [D, LF, key])
  const lane = ((LF || {}).lanes || {})[key] || { events: [] }, days = (LF || {}).event_days || 7
  const evs: any[] = (lane.events || []).filter((e: any) => !e.up), kinds: Record<string, number> = {}
  evs.forEach(e => { const k = kind(e.kind); kinds[k] = (kinds[k] || 0) + 1 })
  const bars = Object.entries(kinds).sort((a, b) => b[1] - a[1]).slice(0, 6).map(([name, value]) => ({ name, value }))
  const totals: [string, number, string][] = []
  if (blk && side === "hunt") { const lb = blk.labels || ["sent", "back"]
    if (blk.sent == null && blk.found != null) totals.push(["found", blk.found, "none sent yet"])
    if (blk.sent != null) { totals.push([lb[0], blk.sent, blk.window || ""], [lb[1], blk.answered || 0, blk.labels ? "" : blk.sent ? Math.round(100 * (blk.answered || 0) / blk.sent) + "% came back" : ""]); if (blk.sent_total != null) totals.push(["all time", blk.sent_total, "submitted"]) } }
  else if (blk && ((blk.rows || []).length || blk.status !== "empty")) totals.push([key === "clients" ? "clients" : "people", (blk.rows || []).length, ""])
  const why = blk && (blk.reason || (blk.status === "empty" ? "no live numbers for this lane" : ""))
  const cur = rows.find(r => r.id === sel)
  const shown = all ? rows : rows.slice(0, 40)
  if (!L || L.side !== side) return <main className="mx-auto max-w-6xl p-6"><h1 className="font-serif text-4xl text-primary">No such lane</h1><p className="text-muted-foreground">"{path}" is not a hunt or roost on Eagle Eye.</p><a href="/" className="text-primary">&larr; EAGLE EYE</a></main>
  return (
    <MotionConfig reducedMotion="user">
      <main className="mx-auto max-w-6xl p-4 pb-16">
        <a href="/" className="text-xs tracking-[.4em] text-primary hover:text-accent-foreground">&larr; EAGLE EYE</a>
        <section className="relative mt-4 overflow-hidden rounded-lg border border-border/60 px-4 py-8 text-center" style={{ background: "radial-gradient(120% 90% at 50% 0%,rgba(217,179,91,.14),transparent 70%)" }}>
          <div className="text-xs tracking-[.5em] text-primary">{side === "hunt" ? "HUNT · WHAT WE SEND OUT" : "ROOST · WHAT COMES BACK"}</div>
          <h1 className="my-2 font-serif text-5xl font-medium tracking-[.14em] text-[#f3dc9a] sm:text-7xl">{L.name}</h1>
          {L.door?.agent && <p className="text-xs uppercase tracking-[.3em] text-muted-foreground">worked by <b className="font-normal text-foreground">{L.door.agent}</b>{L.door.url && <> · <a className="text-primary underline-offset-4 hover:underline" href={L.door.url}>open its {L.door.kind === "desk" ? "desk" : "view"}</a></>}</p>}
          <div className="mt-6 flex flex-wrap justify-center gap-x-12 gap-y-4">{totals.map(([lb, n, sub]) => <div key={lb} className="flex flex-col items-center">
            <div className="flex items-baseline gap-2"><NumberFlow value={n} className="font-serif text-6xl text-[#f3dc9a]" /><span className="text-xs tracking-[.3em] text-primary">{lb.toUpperCase()}</span></div>
            {sub && <small className="font-serif text-base italic text-muted-foreground">{sub}</small>}</div>)}</div>
          {why && <p className="mx-auto mt-4 max-w-[62ch] font-serif text-base italic text-muted-foreground">{String(why).replace(/\s*\([^)]*\)/g, "").replace(/^./, c => c.toUpperCase())}</p>}
          <div className="mx-auto mt-6 max-w-3xl"><Tracker data={river(evs, days)} /><div className="mt-1 flex justify-between text-[10px] tracking-[.3em] text-muted-foreground"><span>{days} DAYS AGO</span><span>TODAY</span></div></div>
        </section>
        {bars.length > 0 && <section className="mt-8"><h2 className="mb-3 text-center text-xs tracking-[.5em] text-primary">WHAT HAPPENED · LAST {days} DAYS</h2><BarList className="mx-auto max-w-2xl" data={bars} /></section>}
        <section className="mt-8">
          <h2 className="mb-3 text-center text-xs tracking-[.5em] text-primary">{key === "in_person" ? "BY EVENT" : side === "roost" && !rows.some(r => r.chips.length) ? "BY PERSON" : "BY COMPANY"}</h2>
          {rows.length === 0 ? <p className="text-center font-serif text-lg italic text-muted-foreground">{LF ? (key === "in_person" ? "Events are listed above by name. A company appears here once someone is met." : "Nothing has come through this lane yet" + (lane.source ? ` (it reads ${String(lane.source).replace(/[\w./~-]*\//g, "")}).` : ".")) : "Loading."}</p> :
            <div className="rounded-md border"><Table><TableHeader><TableRow><TableHead className="w-8" /><TableHead>Name</TableHead><TableHead className="hidden sm:table-cell">Counts</TableHead><TableHead>Last</TableHead><TableHead className="hidden md:table-cell">VSL</TableHead><TableHead className="hidden sm:table-cell">Next</TableHead></TableRow></TableHeader>
              <TableBody>{shown.map((r, i) => <motion.tr key={r.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i, 12) * 0.03 }}
                tabIndex={0} onClick={() => open(r.id)} onKeyDown={e => e.key === "Enter" && open(r.id)} className="h-14 cursor-pointer border-b transition-colors hover:bg-muted/50">
                <TableCell className="py-0"><Ring stage={r.ring[0]} replies={r.ring[1]} /></TableCell>
                <TableCell className="max-w-[18rem] py-0"><div className="truncate font-serif text-lg leading-tight text-[#f3dc9a]">{r.name}{r.tier ? <Badge variant="outline" className="ml-2 border-primary/50 text-primary">T{Math.min(3, r.tier)}</Badge> : null}</div>{r.sub && <div className="truncate text-xs text-muted-foreground">{String(r.sub).slice(0, 90)}</div>}</TableCell>
                <TableCell className="hidden py-0 sm:table-cell"><div className="flex gap-1">{r.chips.map(([k, n]) => <Badge key={k} variant="secondary">{n} {k}</Badge>)}</div></TableCell>
                <TableCell className="whitespace-nowrap py-0 text-muted-foreground" title={r.last}>{short(r.last)}</TableCell>
                <TableCell className="hidden py-0 md:table-cell">{r.vsls ? <Badge>sent{r.vsls > 1 ? " ×" + r.vsls : ""}</Badge> : <Badge variant="outline">not sent</Badge>}</TableCell>
                <TableCell className={"hidden max-w-[16rem] truncate py-0 text-sm sm:table-cell " + (r.nx[1] ? "text-muted-foreground" : "text-primary")}>{r.nx[0]}</TableCell></motion.tr>)}</TableBody></Table></div>}
          {rows.length > 40 && <button className="mx-auto mt-3 block text-xs tracking-[.3em] text-primary" onClick={() => setAll(a => !a)}>{all ? "SHOW THE NEWEST 40" : `SHOW ALL ${rows.length}`}</button>}
        </section>
      </main>
      <Sheet open={!!cur} onOpenChange={o => !o && open(null)}>
        <SheetContent side="right" className="w-full overflow-auto sm:max-w-md">
          {cur && <><SheetHeader><SheetTitle className="font-serif text-2xl text-[#f3dc9a]">{cur.name}</SheetTitle><SheetDescription>{cur.sub || "last " + (cur.last ? ago(cur.last) : "never")}</SheetDescription></SheetHeader>
            <Tabs defaultValue="activity" className="mt-4"><TabsList><TabsTrigger value="activity">Activity</TabsTrigger><TabsTrigger value="next">Next</TabsTrigger></TabsList>
              <TabsContent value="activity">{cur.events.length ? <ol className="space-y-2">{cur.events.map((e, i) => <li key={i} className="border-t border-border/50 pt-2 text-sm"><span className="text-xs tracking-widest text-primary">{kind(e.kind).toUpperCase()}</span> <span className="text-muted-foreground">{ago(e.ts)}</span><div>{e.what}</div></li>)}</ol> : <p className="text-sm text-muted-foreground">No dated activity in the last {days} days.</p>}</TabsContent>
              <TabsContent value="next"><p className="font-serif text-xl text-primary">{cur.nx[0]}</p><p className="mt-1 text-xs text-muted-foreground">{cur.nx[1] ? "Nothing to do yet." : "Derived from the row's stage, replies, VSLs and age."}</p></TabsContent></Tabs></>}
        </SheetContent>
      </Sheet>
    </MotionConfig>)
}

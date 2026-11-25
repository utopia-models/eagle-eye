// Per-stage budget (knowledge#18576): a row that sits in one stage past its budget is flagged `stuck` in /api/feed timelines.
// The stage a row is IN is its last done step; the budget is how long it may wait there for the next step (hours, a measured
// default, overridable per lane). Pure: steps + now in, flag out, so the test needs no database.
export const BUDGET_H: Record<string, number> = { posted: 12, built: 12, recorded: 6 };   // key of the step the row waits AFTER
export type Step = { key: string; label: string; at: string | null; state: string };
export type Stuck = { stage: string; waiting_for: string; since: string; hours: number; budget_h: number };

export function stuckFor(steps: Step[], now = Date.now(), budget = BUDGET_H): Stuck | null {
  const vsl = steps.find(s => s.key === "vsl");
  if (!vsl || vsl.state === "done" || vsl.state === "done_no_time") return null;      // the last step happened: nothing waits
  let cur = -1;
  steps.forEach((s, i) => { if (s.state === "done" && s.at) cur = i; });
  if (cur < 0) return null;
  const s = steps[cur], b = budget[s.key];
  if (b == null) return null;
  const next = steps.slice(cur + 1).find(n => n.state === "pending");
  if (!next) return null;
  const hours = (now - Date.parse(s.at!)) / 3600e3;
  return hours > b ? { stage: s.label, waiting_for: next.label, since: s.at!, hours: Math.round(hours * 10) / 10, budget_h: b } : null;
}

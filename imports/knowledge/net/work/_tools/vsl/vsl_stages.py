#!/usr/bin/env python3
"""vsl_stages.py: `vsl stages`, the per-stage time table of the VSL pipeline, read off the Upwork ledger (knowledge#16071, B1).

One ledger event per stage (ledger.py): vsl_pick -> script_ready -> demo_ready -> vsl_recorded -> vsl_qa -> vsl_sent.
A stage's time is the gap between its event and the previous stage's event for the same job. A job missing either event
prints "no data" for that stage; nothing is guessed or interpolated.

  vsl_stages.py [--ledger FILE] [--job J] [--json]
  vsl_stages.py --self-test
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import statistics
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "upwork"))
import ledger  # noqa: E402

CHAIN = ("vsl_pick", "script_ready", "demo_ready", "vsl_recorded", "vsl_qa", "vsl_sent")
STAGES = tuple((CHAIN[i], CHAIN[i + 1]) for i in range(len(CHAIN) - 1))


def load(path: str) -> dict[str, dict[str, dt.datetime]]:
    """job -> event -> earliest time. Rows without a job or a time are skipped."""
    jobs: dict[str, dict[str, dt.datetime]] = {}
    if not os.path.exists(path):
        return jobs
    with open(path) as f:
        for line in f:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if not isinstance(r, dict) or r.get("event") not in CHAIN or not r.get("job"):
                continue
            t = ledger.row_time(r)
            if t is None:
                continue
            cur = jobs.setdefault(r["job"], {})
            if r["event"] not in cur or t < cur[r["event"]]:
                cur[r["event"]] = t
    return jobs


def table(jobs: dict[str, dict[str, dt.datetime]]) -> list[dict]:
    out = []
    for a, b in STAGES:
        secs = [(ev[b] - ev[a]).total_seconds() for ev in jobs.values() if a in ev and b in ev]
        row = {"stage": f"{a} -> {b}", "jobs": len(secs)}
        if secs:
            row.update(median_s=statistics.median(secs), max_s=max(secs), min_s=min(secs))
        out.append(row)
    return out


def fmt(s: float) -> str:
    s = int(round(s))
    return f"{s // 3600}h{s % 3600 // 60:02d}m" if s >= 3600 else f"{s // 60}m{s % 60:02d}s"


def render(rows: list[dict]) -> str:
    lines = [f"{'stage':<32}{'jobs':>5}{'median':>10}{'min':>10}{'max':>10}"]
    for r in rows:
        if r["jobs"]:
            lines.append(f"{r['stage']:<32}{r['jobs']:>5}{fmt(r['median_s']):>10}{fmt(r['min_s']):>10}{fmt(r['max_s']):>10}")
        else:
            lines.append(f"{r['stage']:<32}{0:>5}{'no data':>10}")
    return "\n".join(lines)


def _self_test() -> int:
    t = os.path.join(tempfile.mkdtemp(), "l.jsonl")
    base = dt.datetime(2026, 11, 18, 13, 0, tzinfo=dt.timezone.utc)

    def add(ev, job, mins, **kw):
        kw.setdefault("who", "horus")
        if ev == "vsl_pick":
            kw.update(fit=80, slug="s")
        if ev == "demo_ready":
            kw["url"] = "https://d"
        if ev == "vsl_recorded":
            kw["file"] = "f.mp4"
        row = ledger.build_row(ev, **{"job": job, **kw})
        row["ts"] = (base + dt.timedelta(minutes=mins)).strftime("%Y-%m-%dT%H:%M:%SZ")
        ledger.append(row, t)
    for ev, m in (("vsl_pick", 0), ("script_ready", 10), ("demo_ready", 70), ("vsl_recorded", 100)):
        add(ev, "~A", m)
    add("vsl_pick", "~B", 0)
    add("script_ready", "~B", 30)
    add("demo_ready", "~B", 150)   # B never recorded
    with open(t, "a") as f:
        f.write("not json\n")
    rows = {r["stage"]: r for r in table(load(t))}
    s1 = rows["vsl_pick -> script_ready"]
    assert s1["jobs"] == 2 and s1["median_s"] == 20 * 60 and s1["max_s"] == 30 * 60, s1
    assert rows["script_ready -> demo_ready"]["median_s"] == 90 * 60, rows
    assert rows["demo_ready -> vsl_recorded"]["jobs"] == 1 and rows["demo_ready -> vsl_recorded"]["median_s"] == 30 * 60
    for a, b in STAGES[3:]:   # nothing recorded past the take: "no data", not zero
        assert rows[f"{a} -> {b}"]["jobs"] == 0, rows
    out = render(table(load(t)))
    assert out.count("no data") == 3 and "1h30m" in out, out
    assert render(table(load("/nonexistent"))).count("no data") == len(STAGES)
    print("vsl_stages self-test: ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ledger")
    ap.add_argument("--job")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return _self_test()
    jobs = load(a.ledger or ledger.path())
    if a.job:
        jobs = {k: v for k, v in jobs.items() if k == a.job}
    rows = table(jobs)
    print(json.dumps(rows, indent=1) if a.json else render(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""feed_lag.py: posted-to-in-Eagle-Eye-feed gap for Upwork rows, per intake source (knowledge#17781).
Reads the same feed oneshot_auto.py ticks on (net/work/vsl/oneshot-auto.yaml feed_url); never touches upwork.com.
  feed_lag.py [--hours 24] [--limit 10] [--sla 10]     exit 1 when any row from a NEW-job intake (alert mail, most-recent desk read) breaks --sla
A row's lag is Eagle Eye's own `findLagMinutes` (signalAt = Upwork post time, foundAt = row in the feed). 180.0 is the
"post time unknown" filler and is dropped. The best-matches desk list is reported but not graded: Upwork ranks a job
into it whenever it likes, so that lag is Upwork's, not a step of ours."""
import argparse, collections, datetime as dt, json, statistics, sys, urllib.request
from pathlib import Path
import yaml

CFG = Path(__file__).resolve().parents[2] / "vsl" / "oneshot-auto.yaml"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=24)
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--sla", type=float, default=10)
    a = ap.parse_args()
    feed = json.loads(urllib.request.urlopen(yaml.safe_load(CFG.read_text())["feed_url"], timeout=60).read())
    cut = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=a.hours)).strftime("%Y-%m-%dT%H:%M")
    rows = [i for i in feed["items"] if i.get("huntType") == "upwork" and i.get("signalAt", "") >= cut
            and i.get("findLagMinutes") not in (None, "180.0")]
    rows.sort(key=lambda i: i["foundAt"], reverse=True)
    print(f"last {a.limit} rows (posted -> in feed, minutes):")
    for i in rows[:a.limit]:
        print(f"  {i['signalAt']} -> {i['foundAt']}  {float(i['findLagMinutes']):6.1f}  {(i['details'].get('src') or '?'):28} {i['signal'][:40]}")
    by = collections.defaultdict(list)
    for i in rows:
        by[i["details"].get("src")].append(float(i["findLagMinutes"]))
    bad = 0
    for src, v in sorted(by.items(), key=lambda kv: str(kv[0])):
        over = sum(x > a.sla for x in v)
        graded = src in ("Upwork desk (most-recent)", "dev@ inbox (Upwork alert)")
        bad += over if graded else 0
        print(f"{src}: n={len(v)} median={statistics.median(v):.1f} max={max(v):.1f} over{a.sla:g}={over}{'' if graded else ' (not graded: best-matches is Upwork ranking delay; no-src rows are manual/backfill)'}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()

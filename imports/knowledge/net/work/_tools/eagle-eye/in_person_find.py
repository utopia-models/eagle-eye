#!/usr/bin/env python3
"""in_person_find.py: the In Person feed for Osman and Claire (knowledge#14303).

Finds upcoming local meetups and career fairs near each person from Luma's place-discovery pages (the same source and
the same real-browser read as ../net-events-watch.py, which feeds Tyler's AI-events list), keeps the ones that fit the
person's search, and writes `<apply root>/candidates/<id>/in_person.jsonl`, one event per line, read by person_feed.py
and shown on their Eagle Eye page. Nothing is invented: a place page that fails to load is named and writes nothing.

    python3 in_person_find.py osman [--dry-run]        # needs a python with playwright (the apply venv on horus's box)
    python3 in_person_find.py --self-test              # offline: the keep/drop rule and the file merge

Env: CHROMIUM_PATH picks the browser binary when playwright's bundled version is not installed.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import datetime as dt

APPLY_ROOT = os.environ.get("EAGLE_CANDIDATES_ROOT") or "/home/eagle/.claude/state/sf/apply/candidates"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
# Where each person is and what their search is (the issue: Osman DC/NoVA tech, data, systems, Salesforce, AI;
# Claire Santa Barbara + Fairfax, pre-law/legal/policy + hospitality). Luma's place slugs are probed live, not guessed:
# `places` that return no page are reported by name. Fairfax is inside Luma's DC place; Luma has no Santa Barbara place.
PROFILES = {
    "osman": {"places": [("Washington, DC / NoVA", "https://luma.com/dc")],
              "keywords": ["data", "systems", "salesforce", "ai ", " ai", "cloud", "devops", "developer", "engineer",
                           "software", "tech", "cyber", "security", "startup", "builders", "career", "job fair", "hiring"]},
    "claire": {"places": [("Washington, DC / Fairfax", "https://luma.com/dc"), ("Santa Barbara", "https://luma.com/santa-barbara")],
               "keywords": ["law", "legal", "pre-law", "policy", "government", "hospitality", "hotel",
                            "restaurant", "career", "job fair", "hiring", "networking"]},
}
ANY = ["career fair", "job fair", "hiring fair", "meetup"]   # a career fair is a fit for anyone


def fits(name: str, keywords: list) -> list:
    n = " " + name.lower() + " "
    return [k.strip() for k in ANY + keywords if k in n]


def fetch(url: str) -> list:
    from playwright.sync_api import sync_playwright  # noqa: PLC0415 — only present in the apply venv
    with sync_playwright() as p:
        kw = {"executable_path": os.environ["CHROMIUM_PATH"]} if os.environ.get("CHROMIUM_PATH") else {}
        b = p.chromium.launch(headless=True, **kw)  # real-browser-check: ok (public event-page scrape, logs in nowhere)
        pg = b.new_page(user_agent=UA)
        pg.goto(url, timeout=30000, wait_until="networkidle")
        pg.wait_for_timeout(3000)
        html = pg.content()
        b.close()
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return []
    try:
        init = json.loads(m.group(1))["props"]["pageProps"]["initialData"]
    except (KeyError, TypeError, ValueError):
        return []
    d = init.get("data", {})
    entries = d.get("events", []) if init.get("kind") == "discover-place" else d.get("upcoming", {}).get("entries", [])
    out = []
    for e in entries:
        ev = e.get("event", {})
        if ev.get("name") and ev.get("url"):
            out.append({"id": ev.get("api_id", ""), "name": ev["name"], "start": ev.get("start_at", ""),
                        "url": "https://lu.ma/" + ev["url"], "city": (ev.get("geo_address_info") or {}).get("city_state", "")})
    return out


def merge(old: list, new: list, today: str) -> list:
    """New finds join the file by event id; an event whose date has passed stays (it is history), nothing is dropped."""
    seen = {r.get("id") for r in old}
    return old + [r for r in new if r["id"] not in seen]


def find(person: str, dry: bool = False) -> int:
    prof = PROFILES[person]
    path = os.path.join(APPLY_ROOT, person, "in_person.jsonl")
    old = []
    if os.path.exists(path):
        old = [json.loads(x) for x in open(path) if x.strip()]
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    new, failed = [], []
    for label, url in prof["places"]:
        evs = fetch(url)
        print(f"{label} ({url}): {len(evs)} listed" if evs else f"{label} ({url}): NO PAGE or empty (not assumed quiet)")
        if not evs:
            failed.append(label)
        for ev in evs:
            why = fits(ev["name"], prof["keywords"])
            if why:
                new.append({**ev, "place": label, "fits": why, "source": "luma place discovery", "found_at": now})
    rows = merge(old, new, now[:10])
    added = len(rows) - len(old)
    print(f"{person}: {len(new)} fit, {added} new, {len(rows)} in file; unreachable places: {failed or 'none'}")
    if not dry and added:
        body = "".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows)
        try:
            tmp = f"{path}.tmp.{os.getpid()}"
            with open(tmp, "w") as f:
                f.write(body)
            os.replace(tmp, path)
        except OSError:   # the store is horus's: a master user writes it as horus (the same sudo rule person_feed.py reads by)
            subprocess.run(["sudo", "-n", "-u", "eagle", "tee", path], input=body, text=True, capture_output=True, check=True, cwd="/")
    return 1 if failed and len(failed) == len(prof["places"]) else 0


def self_test() -> int:
    want = [(fits("Python Data Night", PROFILES["osman"]["keywords"]), ["data"]),
            (fits("Poker tournament", PROFILES["osman"]["keywords"]), []),
            (fits("Fairfax Career Fair", PROFILES["claire"]["keywords"]), ["career fair", "career"]),
            (fits("Legal Tech Mixer", PROFILES["claire"]["keywords"]), ["legal"]),
            ([r["id"] for r in merge([{"id": "a"}], [{"id": "a"}, {"id": "b"}], "")], ["a", "b"])]
    bad = [(g, w) for g, w in want if g != w]
    print("self-test", "PASS" if not bad else f"FAIL {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
    elif a[0] == "--self-test":
        sys.exit(self_test())
    else:
        sys.exit(find(a[0], "--dry-run" in a))

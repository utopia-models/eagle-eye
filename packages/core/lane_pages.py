#!/usr/bin/env python3
"""lane_pages.py: one Eagle Eye page per lane at eagle.utopiamodels.ai/lane/<id> (knowledge#13230).

"open <lane> Eagle Eye" (horus's vocabulary, net/work/_tools/horus_open.py) opens that lane's page in horus's desk. Each
page is GENERATED from net/work/pipeline/lanes.yaml (the declared part: name, side, who works it, on which box, where its
numbers come from, its door, the next upgrade) and reads its numbers LIVE in the browser from the Worker's own /data.json
(the lane's `data_key` under `hunts` or `roosts`, pushed every 30 s by eagle-eye-feed). A lane with no live numbers shows
the feed's own `reason`, never a zero it did not count.

    python3 lane_pages.py --build DIR      # write DIR/<id>.html for every lane (inspect or serve locally)
    python3 lane_pages.py --deploy         # put /lane/<id> for every lane into the live `eagle-eye` Worker (deploy-worker.py)
    python3 lane_pages.py --live           # grade: every lane's /lane/<id> is deployed and equals what lanes.yaml generates
    python3 lane_pages.py --self-test      # offline: every lane renders, names its data_key, escapes its text
"""
from __future__ import annotations

import html
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KB = os.environ.get("EAGLE_KB") or os.path.expanduser("~/dev/utopia-models/knowledge")  # the knowledge checkout (data + lanes.yaml); core lives in utopia-models/eagle-eye
LANES_YAML = os.environ.get("EAGLE_LANES_YAML") or os.path.join(KB, "net/work/pipeline/lanes.yaml")


def load():
    import yaml  # noqa: PLC0415
    with open(LANES_YAML) as f:
        return yaml.safe_load(f)


def door(cfg, ln):
    if ln.get("moonlight"):
        m = ln["moonlight"]
        return f"{m['agent']}'s desk on {m['host']} (say “open the {ln.get('short', ln['name'])} desk” to horus)"
    if ln.get("tab"):
        t = ln["tab"]
        return f"{t['name']} tab" + ("" if t.get("url") else f": {t.get('pending', 'not built yet')}")
    return "none"


def page(cfg, ln) -> str:
    e = html.escape
    side = "roosts" if ln["side"] == "roost" else "hunts"
    runs = "".join(f"<li><b>{e(r['agent'])}</b> on {e(r['box'])}: {e(r['what'])}</li>" for r in ln.get("runs_on") or [])
    meta = json.dumps({"side": side, "key": ln["data_key"], "name": ln["name"]}).replace("<", "\\u003c")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(ln['name'])} · Eagle Eye</title>
<style>
:root{{--bg:#0a0a09;--gold:#d9b35b;--pale:#f3dc9a;--ink:#e8e2d4;--dim:#8f8878;--line:#2a271f}}
*{{box-sizing:border-box}}html,body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 Georgia,serif}}
main{{max-width:980px;margin:0 auto;padding:40px 28px 64px}}
a{{color:var(--pale)}}nav{{font-size:14px;color:var(--dim);margin-bottom:28px}}
.kind{{letter-spacing:.18em;text-transform:uppercase;font-size:12px;color:var(--gold)}}
h1{{font-weight:400;font-size:44px;margin:6px 0 4px;color:var(--pale)}}
.who{{color:var(--dim);margin:0 0 32px}}
.nums{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1px;background:var(--line);border:1px solid var(--line);margin-bottom:12px}}
.num{{background:var(--bg);padding:18px 20px}}.num b{{display:block;font-size:40px;font-weight:400;color:var(--pale);font-variant-numeric:tabular-nums}}
.num span{{font-size:13px;color:var(--dim)}}
.note{{font-size:14px;color:var(--dim);margin:0 0 32px}}
table{{width:100%;min-width:340px;border-collapse:collapse;margin-bottom:32px;font-size:15px}}th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line)}}
th{{font-weight:400;color:var(--gold);font-size:12px;letter-spacing:.12em;text-transform:uppercase}}
h2{{font-weight:400;font-size:13px;letter-spacing:.18em;text-transform:uppercase;color:var(--gold);margin:28px 0 8px}}
ul{{margin:0;padding-left:20px}}p{{margin:0}}
.upgrade{{border-left:2px solid var(--gold);padding:10px 16px;color:var(--pale)}}
@media (max-width:600px){{td:nth-child(2),th:nth-child(2){{display:none}}main{{padding:24px 16px 48px}}h1{{font-size:34px}}.num b{{font-size:32px}}}}
</style></head>
<body><main>
<nav><a href="/">Eagle Eye</a> / {e(ln['name'])}</nav>
<div class="kind">{'Roost' if side == 'roosts' else 'Hunt'}</div>
<h1>{e(ln['name'])}</h1>
<p class="who">Worked by <b>{e(str(ln.get('agent', ln.get('owner', ''))))}</b> · owned by {e(str(ln.get('owner', '')))}</p>
<div id="live"><p class="note">Reading live numbers…</p></div>
<h2>Next upgrade</h2><p class="upgrade">{e(ln.get('upgrade', ''))}</p>
<h2>Who runs it</h2><ul>{runs}</ul>
<h2>Desk</h2><p>{e(door(cfg, ln))}</p>
<h2>Where the numbers come from</h2><p>{e(ln.get('source', ''))}</p>
</main>
<script type="application/json" id="lane">{meta}</script>
<script>
(async () => {{
  const L = JSON.parse(document.getElementById('lane').textContent), box = document.getElementById('live');
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}})[c]);
  const fmt = v => v === null || v === undefined ? '—' : (typeof v === 'number' ? v.toLocaleString() : esc(v));
  try {{
    const d = await (await fetch('/data.json', {{cache: 'no-store'}})).json();
    const x = (d[L.side] || {{}})[L.key];
    if (!x) {{ box.innerHTML = '<p class="note">The feed carries no ' + esc(L.key) + ' entry yet.</p>'; return; }}
    let h = '';
    if (L.side === 'hunts') {{
      if (x.status === 'empty' || x.sent === null) h += '<p class="note">' + esc(x.reason || 'No numbers measured yet.') + '</p>';
      else {{
        const rate = x.sent ? Math.round(100 * x.answered / x.sent) + '%' : '—';
        h += '<div class="nums"><div class="num"><b>' + fmt(x.sent) + '</b><span>sent · ' + esc(x.window) + '</span></div>'
          + '<div class="num"><b>' + fmt(x.answered) + '</b><span>came back</span></div>'
          + '<div class="num"><b>' + rate + '</b><span>answer rate</span></div></div>'
          + '<p class="note">' + esc(x.what) + '.</p>';
      }}
    }} else {{
      const rows = x.rows || [];
      if (!rows.length) h += '<p class="note">' + esc(x.reason || 'Nobody in this roost yet.') + '</p>';
      else h += '<div style="overflow-x:auto"><table><tr><th>Name</th><th>From</th><th>Stage</th><th>Contracts</th><th>Paid</th></tr>'
        + rows.map(r => '<tr><td>' + esc(r.name) + '</td><td>' + esc(r.hunt) + '</td><td>' + esc(r.stage) + '</td><td>'
          + fmt(r.contracts) + '</td><td>' + esc(r.paid) + '</td></tr>').join('') + '</table></div>';
    }}
    box.innerHTML = h;
  }} catch (e) {{ box.innerHTML = '<p class="note">Live numbers unavailable: ' + esc(e.message) + '</p>'; }}
}})();
</script>
</body></html>
"""


def pages() -> dict:
    cfg = load()
    return {ln.get("eagle_page", f"/lane/{ln['id']}"): page(cfg, ln) for ln in cfg["lanes"]}


def dw():
    s = importlib.util.spec_from_file_location("dw", os.path.join(HERE, "deploy-worker.py"))
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def main(a):
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        return 2
    if a[0] == "--self-test":
        cfg, bad = load(), []
        for ln in cfg["lanes"]:
            p = page(cfg, ln)
            if f'"key": "{ln["data_key"]}"' not in p or "<title>" not in p:
                bad.append(ln["id"])
        evil = dict(cfg["lanes"][0], name="<script>x</script>")
        if "<script>x</script>" in page(cfg, evil):
            bad.append("unescaped name")
        print("lane_pages self-test " + ("FAIL " + ", ".join(bad) if bad else f"ok ({len(cfg['lanes'])} lanes)"))
        return 1 if bad else 0
    if a[0] == "--build":
        os.makedirs(a[1], exist_ok=True)
        for path, body in pages().items():
            open(os.path.join(a[1], path.rsplit("/", 1)[-1] + ".html"), "w").write(body)
            print(path)
        return 0
    m = dw()
    tok, acct = m.creds()
    handler, assets, types, settings = m.live(tok, acct)
    want = pages()
    if a[0] == "--live":
        bad = [p for p, b in want.items() if assets.get(p) != b or not types.get(p, "").startswith("text/html")]
        print("lane pages live: " + ("FAIL, stale or missing: " + " ".join(bad) if bad else f"PASS ({len(want)} lanes)"))
        return 1 if bad else 0
    if a[0] == "--deploy":
        for p, b in want.items():
            print(f"{p}: {len(assets.get(p, ''))} -> {len(b)} chars")
            assets[p], types[p] = b, "text/html"
        print(f"deployed eagle-eye: {m.upload(tok, acct, m.build(handler, assets, types), settings)}")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

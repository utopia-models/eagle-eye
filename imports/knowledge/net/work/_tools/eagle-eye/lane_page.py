#!/usr/bin/env python3
"""lane_page.py HOME_JS OUT: Eagle Eye's lane page, /hunt/<id> and /roost/<id> (knowledge#13617).

One page (`lane.html`) serves every lane; the Worker answers /hunt/* and /roost/* with it (person/handler.js). This
fills its LANES block from the home page's own PIPES + DOORS (horus's live home-live.js), so a lane renamed or re-doored
on the home page is the same on its page. The numbers come live from /data.json and /lanes.json (feed.py).

    python3 lane_page.py home-live.js lane.out.html
    python3 lane_page.py home-live.js lane.out.html jobs-app/dist/lane-app.html   # the React page (knowledge#14769)
    python3 deploy-worker.py --handler person/handler.js /lane.html=lane.out.html
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def lanes(js: str) -> dict:
    pipes = js[js.index("const PIPES = ["):js.index("];", js.index("const PIPES = ["))]
    doors = json.loads(re.search(r"const DOORS = (\{.*?\});\n", js, re.S).group(1))
    out = {}
    for m in re.finditer(r"\{id:'([^']+)', ring:(\d)[^}]*?(?:hk|rk):'([^']+)', name:'([^']+)'", pipes):
        _id, ring, key, name = m.groups()
        d = doors.get(key) or doors.get(_id) or {}
        out[key] = {"name": name, "side": "hunt" if ring == "0" else "roost",
                    "door": {k: d[k] for k in ("agent", "kind", "url") if d.get(k)}}
    if len(out) < 3:
        raise SystemExit(f"PIPES parse found {len(out)} lanes: home-live.js shape changed")
    return out


def build(js: str) -> str:
    page = open(os.path.join(HERE, "lane.html")).read()
    a, b = page.index("const LANES = {};"), page.index("// LANES:END")
    return page[:a] + "const LANES = " + json.dumps(lanes(js), ensure_ascii=False) + ";\n" + page[b:]


def build_app(js: str, app_html: str) -> str:
    """knowledge#14769: fill `window.__LANES__` in the built React lane page (jobs-app `lane-app.html`)."""
    if "window.__LANES__={};" not in app_html:
        raise SystemExit("lane-app.html has no window.__LANES__={}; placeholder")
    return app_html.replace("window.__LANES__={};", "window.__LANES__=" + json.dumps(lanes(js), ensure_ascii=False) + ";")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[3].endswith(".html"):   # lane_page.py HOME_JS OUT --app is not used; HOME_JS OUT APP_HTML
        open(sys.argv[2], "w").write(build_app(open(sys.argv[1]).read(), open(sys.argv[3]).read()))
        print("ok app", list(lanes(open(sys.argv[1]).read())))
        sys.exit(0)
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    out = build(open(sys.argv[1]).read())
    open(sys.argv[2], "w").write(out)
    print("ok", len(out), list(lanes(open(sys.argv[1]).read())))

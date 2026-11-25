#!/usr/bin/env python3
"""desc_reader.py JOB_ID [--out DIR]: read one PUBLIC Upwork job page logged-out in vsl's own headful Chrome (Xvfb, profile ~/.config/vsl-chrome-head; never the Upwork seat)
and write <out>/<~id>.json in the job-description desk format {job,title,link,ok,why,desc,read_at,source}. A private/closed listing -> ok:false with the page's own words, never a guess.
Run on Ra under xvfb-run. One page load per call; the caller spaces calls 4-9 min apart."""
import json, re, sys, time, argparse
from pathlib import Path
from playwright.sync_api import sync_playwright
ap = argparse.ArgumentParser(); ap.add_argument("job"); ap.add_argument("--out", default="/var/tmp/vsl-descriptions"); a = ap.parse_args()
jid = a.job if a.job.startswith("~") else "~" + a.job
Path(a.out).mkdir(parents=True, exist_ok=True)
url = f"https://www.upwork.com/jobs/{jid}"
res = {"job": jid, "link": url, "ok": False, "why": None, "desc": "", "title": "", "read_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "source": "vsl-desc-reader (logged-out, own profile)"}
with sync_playwright() as p:
    b = p.chromium.launch_persistent_context(str(Path.home() / ".config/vsl-chrome-head"), executable_path="/usr/bin/google-chrome", headless=False,
                                             viewport={"width": 1400, "height": 1000}, args=["--disable-blink-features=AutomationControlled"])
    try:
        pg = b.new_page(); pg.goto(url, wait_until="domcontentloaded", timeout=60000); pg.wait_for_timeout(4000)
        res["title"] = pg.title()
        body = pg.inner_text("body")
        if re.search(r"private listing|no longer available|job (has been )?(closed|removed)|Sorry, you have been blocked", body, re.I):
            res["why"] = "page says: " + re.search(r"(This job is a private listing|no longer available|job (has been )?(closed|removed)|Sorry, you have been blocked)", body, re.I).group(0)
        else:
            m = re.search(r"Summary\s*(.*?)(?:\n\s*(?:Skills and Expertise|About the client|Activity on this job)\b)", body, re.S)
            h1 = ""
            try: h1 = pg.inner_text("h1").strip()
            except Exception: pass
            desc = (m.group(1).strip() if m else "")
            if len(desc) > 200:
                res.update(ok=True, title=h1 or res["title"], desc=f"{h1}\n\nSummary\n{desc}\n")
            else:
                res["why"] = "page loaded but no description block found (%d chars)" % len(desc)
    except Exception as e:
        res["why"] = f"{type(e).__name__}: {str(e)[:120]}"
    finally:
        b.close()
out = Path(a.out) / f"{jid}.json"; out.write_text(json.dumps(res, indent=1)); print(json.dumps({k: res[k] for k in ("job", "ok", "why", "title")}), len(res["desc"]), "chars ->", out)

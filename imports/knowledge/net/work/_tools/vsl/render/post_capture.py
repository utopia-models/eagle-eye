#!/usr/bin/env python3
"""post_capture.py JOB_URL OUT.png : full-page capture (1580 wide) of the PUBLIC Upwork job page, logged-out, in vsl's own headful Chrome (run under xvfb-run).
Exit 0 = real page captured; exit 2 = private/closed/blocked/too short (caller falls back to the clean text card). Never the Upwork seat."""
import re, sys
from playwright.sync_api import sync_playwright
url, out = sys.argv[1], sys.argv[2]
from pathlib import Path
with sync_playwright() as p:
    b = p.chromium.launch_persistent_context(str(Path.home() / ".config/vsl-chrome-head"), executable_path="/usr/bin/google-chrome", headless=False,
                                             viewport={"width": 1580, "height": 984}, args=["--disable-blink-features=AutomationControlled"])
    try:
        pg = b.new_page(); pg.goto(url, wait_until="domcontentloaded", timeout=60000); pg.wait_for_timeout(5000)
        body = pg.inner_text("body")
        if re.search(r"private listing|no longer available|job (has been )?(closed|removed)|Sorry, you have been blocked|Log in to continue", body, re.I) or len(body) < 1500:
            print("not capturable:", body[:80].replace("\n", " ")); sys.exit(2)
        for sel in ("[data-test='cookie-banner']", "#onetrust-banner-sdk", "[id*=cookie]"):
            try: pg.evaluate("s => document.querySelectorAll(s).forEach(e => e.remove())", sel)
            except Exception: pass
        h = pg.evaluate("""() => { const t = [...document.querySelectorAll('h1,h2,h3,h4,section,div')].find(e => /^(Explore similar jobs|How it works)/i.test((e.innerText||'').trim()) && e.getBoundingClientRect().height < 400);
            return t ? Math.round(t.getBoundingClientRect().top + window.scrollY) : 0 }""")
        full = pg.evaluate("document.documentElement.scrollHeight")
        hh = h if h and h > 600 else full                          # stop the capture where Upwork's own 'similar jobs' / marketing blocks begin
        pg.screenshot(path=out, full_page=True, clip={"x": 0, "y": 0, "width": 1565, "height": hh}); print("captured", out, hh, "of", full)
    finally:
        b.close()

#!/usr/bin/env python3
"""repair_tabs.py [--dry] [--apply]: (no flag = refuses; --help prints this, never runs) one pass over every hunts/upwork/<slug> package: tabs.txt -> the two pages that really load
(<slug>-mvp/mvp/ and <slug>-diagram/mvp/), short titles on the published copies, then GET each URL and report the status.
Run as the user that owns the hunts and public folders (upwork). Exit 1 when any tab still does not return 200."""
import re, ssl, sys, urllib.request
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "vsl" / "takeflow")); sys.path.insert(0, str(HERE))
import tab_titles, gates, yaml
CFG = yaml.safe_load((HERE.parents[1] / "vsl" / "oneshot-auto.yaml").read_text())
BASE = "https://ra.tail4016d7.ts.net:8450/hunts"
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE


def status(u):
    try:
        return urllib.request.urlopen(u, timeout=15, context=CTX).status
    except Exception as e:  # noqa: BLE001
        return getattr(e, "code", 0)


def main(dry):
    bad = fixed = 0
    for d in sorted(Path(CFG["hunts_dir"]).glob("up-*")):
        slug = d.name
        urls = [f"{BASE}/{slug}-mvp/mvp/", f"{BASE}/{slug}-diagram/mvp/"]
        if not (gates.RA_PUBLIC / f"{slug}-mvp" / "mvp" / "index.html").is_file():
            print(f"SKIP {slug}: not published"); continue
        tt = d / "tabs.txt"
        if not tt.is_file() or tt.read_text().split() != urls:
            fixed += 1
            if not dry:
                try: tt.write_text("\n".join(urls) + "\n")
                except OSError as e: print(f"CANNOT WRITE {tt}: {e}"); bad += 1; continue
        if not dry:
            T = re.compile(r"<title>(.*?)</title>", re.S | re.I)
            pub_app = gates.RA_PUBLIC / f"{slug}-mvp" / "mvp" / "index.html"
            def title(f):
                m = T.search(f.read_text(errors="replace")) if f.is_file() else None
                return m.group(1).strip() if m else ""
            have = title(pub_app)
            new_app = have if have and have != "Shadcn Admin" else title(d / "mvp" / "index.html")   # never downgrade a title someone already set
            for f, new in ((pub_app, new_app), (gates.RA_PUBLIC / f"{slug}-diagram" / "mvp" / "index.html", "Architecture")):
                if new and new != "Shadcn Admin": tab_titles.set_title(f, new, False)
        codes = [status(u) for u in urls]
        bad += any(c != 200 for c in codes)
        print(f"{'ok  ' if all(c == 200 for c in codes) else 'FAIL'} {slug} {codes}")
    print(f"repaired tabs.txt on {fixed}; tabs not 200: {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument("--dry", action="store_true"); ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if not (a.dry or a.apply):
        ap.error("say --dry (read-only report) or --apply (rewrite)")
    sys.exit(main(a.dry))

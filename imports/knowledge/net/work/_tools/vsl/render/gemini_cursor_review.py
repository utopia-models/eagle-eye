#!/usr/bin/env python3
"""gemini_cursor_review.py MP4 [--out FILE.json] [--min-score 8]: Gemini video understanding grades the cursor and scroll motion of a capture
(knowledge#18869 item 6). Key: Infisical utopia GEMINI_API_KEY (via `cred`, never printed). Writes `<mp4>.cursor-review.json` beside the MP4 and
exits 1 when the human score is below --min-score or any robotic moment is flagged; capture_browser.py re-captures until it exits 0."""
import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from human_motion import GEMINI_RUBRIC

API = "https://generativelanguage.googleapis.com"
MODEL = "gemini-flash-latest"


def _req(url, data=None, headers=None, method=None):
    r = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(r, timeout=300) as f:
            return f.read(), dict(f.headers)
    except urllib.error.HTTPError as e:   # name the API's own reason (never the URL: it carries the key)
        raise SystemExit(f"gemini HTTP {e.code}: {e.read()[:300].decode('utf8', 'replace')}")


def review(mp4, key):
    raw = Path(mp4).read_bytes()
    _, h = _req(f"{API}/upload/v1beta/files?key={key}", json.dumps({"file": {"display_name": Path(mp4).name}}).encode(),
                {"X-Goog-Upload-Protocol": "resumable", "X-Goog-Upload-Command": "start", "X-Goog-Upload-Header-Content-Length": str(len(raw)),
                 "X-Goog-Upload-Header-Content-Type": "video/mp4", "Content-Type": "application/json"}, "POST")
    up = {k.lower(): v for k, v in h.items()}["x-goog-upload-url"]
    b, _ = _req(up, raw, {"X-Goog-Upload-Offset": "0", "X-Goog-Upload-Command": "upload, finalize"}, "POST")
    f = json.loads(b)["file"]
    while f.get("state") == "PROCESSING":
        time.sleep(3)
        f = json.loads(_req(f"{API}/v1beta/{f['name']}?key={key}")[0])
    body = {"contents": [{"parts": [{"file_data": {"mime_type": "video/mp4", "file_uri": f["uri"]}}, {"text": GEMINI_RUBRIC}]}],
            "generationConfig": {"response_mime_type": "application/json", "temperature": 0}}
    b, _ = _req(f"{API}/v1beta/models/{MODEL}:generateContent?key={key}", json.dumps(body).encode(), {"Content-Type": "application/json"}, "POST")
    return json.loads(json.loads(b)["candidates"][0]["content"]["parts"][0]["text"])


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("mp4")
    ap.add_argument("--out")
    ap.add_argument("--min-score", type=float, default=8)
    a = ap.parse_args(argv)
    key = subprocess.run(["cred", "get", "utopia", "GEMINI_API_KEY"], capture_output=True, text=True, check=True).stdout.strip()
    res = review(a.mp4, key)
    out = Path(a.out or str(a.mp4) + ".cursor-review.json")
    out.write_text(json.dumps(res, indent=1) + "\n")
    ok = float(res.get("human_score", 0)) >= a.min_score and not res.get("robotic_moments")
    print(json.dumps({"file": str(out), "human_score": res.get("human_score"), "flagged": len(res.get("robotic_moments") or []), "pass": ok}))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

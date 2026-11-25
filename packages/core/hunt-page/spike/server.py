#!/usr/bin/env python3
"""THROWAWAY SPIKE server: static public/ + POST /api/ask (claude -p over one lane's data)."""
import json, os, re, shutil, subprocess, sys, threading, urllib.error
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

HERE = os.path.dirname(os.path.abspath(__file__))
PUB = os.path.join(HERE, "public")
HOST, PORT = sys.argv[1] if len(sys.argv) > 1 else "100.127.249.81", int(sys.argv[2]) if len(sys.argv) > 2 else 8797
CLAUDE = shutil.which("claude") or "/usr/local/bin/claude"
ASK_LOCK = threading.Semaphore(2)  # Ra has ~1-2 GB free: at most two claude -p at once


PEOPLE = {p["id"] for p in json.load(open(os.path.join(PUB, "people", "index.json")))}


def lane_context(lane_id, person="tyler"):
    if person not in PEOPLE:
        return None, None, {}
    snap = json.load(open(os.path.join(PUB, "people", person + ".json")))
    for group in ("hunts", "roosts"):
        for lane in snap[group]:
            if lane["id"] == lane_id:
                return group, lane, snap
    return None, None, snap


class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=PUB, **k)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    def _take(self, method):
        """knowledge#18939: /api/take -> the upwork user's take_api (loopback :8817): the hunt page's FULL VSL / INTRO VSL tap."""
        import urllib.request
        body = self.rfile.read(int(self.headers.get("Content-Length", 0) or 0)) if method == "POST" else None
        q = self.path.partition("?")[2]
        try:
            req = urllib.request.Request("http://127.0.0.1:8817/take" + ("?" + q if q else ""), data=body, method=method, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return self._json(r.status, json.loads(r.read()))
        except urllib.error.HTTPError as e:
            return self._json(e.code, json.loads(e.read() or b"{}"))
        except Exception as e:
            return self._json(502, {"error": f"take api down: {type(e).__name__}"})

    def do_GET(self):
        if self.path.split("?")[0] == "/api/take":
            return self._take("GET")
        path = self.path.split("?")[0].strip("/")
        if path == "":
            pass
        if path in PEOPLE:
            self.path = "/index.html"
        # SPA fallback for a built app (Tyler/Eagle 11-22: Top reloads a deep route like /mvp/apps and got 'Error response 404'): an unknown,
        # extension-less path under /hunts/<slug>-mvp/mvp/ serves that app's index.html so a reload on any client route works.
        m = re.match(r"^(hunts/[A-Za-z0-9_-]+-mvp/mvp)/(.+)$", path)
        if m and "." not in m.group(2).rsplit("/", 1)[-1] and not os.path.exists(self.translate_path("/" + path)):
            self.path = "/" + m.group(1) + "/index.html"
        if path.endswith((".mp4", ".wav")) and self.headers.get("Range"):
            return self._range(path)
        return super().do_GET()

    def _range(self, path):
        """Byte ranges for the take player (public/hunts/<slug>/take.mp4): Safari will not play a video without them."""
        f = os.path.realpath(os.path.join(PUB, path))
        if not f.startswith(PUB + os.sep) or not os.path.isfile(f):
            return self.send_error(404)
        size = os.path.getsize(f)
        try:
            a, b = self.headers["Range"].replace("bytes=", "").split(",")[0].split("-")
            start = int(a) if a else max(0, size - int(b))
            end = min(size - 1, int(b) if a and b else size - 1)
        except ValueError:
            return self.send_error(416)
        if start > end:
            return self.send_error(416)
        self.send_response(206)
        self.send_header("Content-Type", "video/mp4" if f.endswith(".mp4") else "audio/wav")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        with open(f, "rb") as fh:
            fh.seek(start)
            left = end - start + 1
            while left > 0:
                chunk = fh.read(min(1 << 16, left))
                if not chunk:
                    break
                self.wfile.write(chunk)
                left -= len(chunk)

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path == "/api/take":
            return self._take("POST")
        if self.path != "/api/ask":
            return self._json(404, {"error": "not found"})
        try:
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0) or b"{}")
        except Exception:
            return self._json(400, {"error": "bad json"})
        q = (req.get("q") or "").strip()[:500]
        group, lane, snap = lane_context(req.get("lane", ""), req.get("person", "tyler"))
        if not q or not lane:
            return self._json(400, {"error": "need q and lane"})
        if not os.path.exists(CLAUDE):
            return self._json(200, {"answer": None, "note": "ask wiring comes in the build"})
        prompt = (
            "You answer questions about one lane of Eagle Eye, a personal networking machine "
            "(hunts go out to people and companies; roosts are the people who came back). "
            f"This is {snap.get('display')}'s '{lane['name']}' {group[:-1]}. Data copy taken {snap['copy_at']} ({snap['copy_where']}). "
            "Answer ONLY from the JSON below, in 1-3 short plain sentences, with exact numbers. "
            "If the data does not hold the answer, say what is missing.\n\n"
            f"QUESTION: {q}\n\nLANE JSON:\n{json.dumps(lane)[:30000]}"
        )
        if not ASK_LOCK.acquire(timeout=5):
            return self._json(200, {"answer": None, "note": "busy: another question is running, try again in a moment"})
        try:
            r = subprocess.run([CLAUDE, "-p", prompt, "--model", "haiku", "--setting-sources", "", "--strict-mcp-config", "--no-session-persistence", "--tools", ""], capture_output=True, text=True, timeout=90,
                               cwd="/var/tmp")
            ans = (r.stdout or "").strip()
            if r.returncode != 0 or not ans:
                return self._json(200, {"answer": None, "note": "ask wiring comes in the build (claude -p failed on Ra: " + (r.stderr or "")[-160:] + ")"})
            return self._json(200, {"answer": ans})
        except subprocess.TimeoutExpired:
            return self._json(200, {"answer": None, "note": "no answer in 90 s; ask wiring comes in the build"})
        finally:
            ASK_LOCK.release()


if __name__ == "__main__":
    print(f"eagle-eye spike on http://{HOST}:{PORT}/", flush=True)
    ThreadingHTTPServer((HOST, PORT), H).serve_forever()

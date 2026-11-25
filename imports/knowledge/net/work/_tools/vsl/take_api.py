#!/usr/bin/env python3
"""take_api.py: the hunt page's one tap (knowledge#18939). Loopback HTTP over oneshot_auto.take_over / hunt_state, run as the `upwork` user on Ra
(systemd/vsl-take-api.service) beside oneshot-auto-serve; eagle-ui's server.py proxies /api/take to it.
  GET  /take?job=<slug | trailing digits of the job id>          -> hunt_state: {state, label, send_at, take, by, script_loaded_at, ...}
  POST /take {"job": ..., "take": "full"|"intro", "voice": bool} -> take_over: stops the intro countdown, claims, loads the script into Vizier
Stdlib only. The claim touches the same job record the 20 s tick reads, so the timer stops at once, not at the next tick."""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oneshot_auto as oa  # noqa: E402


class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *a):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % a))

    def _json(self, code, doc):
        b = json.dumps(doc).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path != "/take":
            return self._json(404, {"error": "not found"})
        tok = (parse_qs(u.query).get("job") or [""])[0]
        return self._json(200, oa.hunt_state(tok) if tok else {"found": False})

    def do_POST(self):
        if urlparse(self.path).path != "/take":
            return self._json(404, {"error": "not found"})
        try:
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0) or b"{}")
            take = req.get("take", "full")
            if take not in ("full", "intro"):
                return self._json(400, {"error": "take must be full or intro"})
            return self._json(200, oa.take_over(str(req.get("job", "")), take, voice=bool(req.get("voice"))))
        except ValueError as e:
            return self._json(404, {"error": str(e)})
        except Exception as e:  # noqa: BLE001  one bad request never takes the service down
            return self._json(500, {"error": f"{type(e).__name__}: {e}"[:200]})


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8799
    print(f"take-api on 127.0.0.1:{port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()

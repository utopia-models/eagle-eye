"""vsl_ready.py: Ready is refused unless gates pass and the Architect approved this script version (knowledge#15168)."""
import io, json, sys, tempfile, threading, unittest
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import vsl_ready  # noqa: E402

GOOD = (HERE / "golden" / "templates" / "ai_automation.take.md").read_text()   # a client-first take (Signals block, their words first)
BAD = (HERE / "golden" / "v13_ai_automation.md").read_text()


def serve(text, refusals, approver="architect"):
    sha = "abc123"
    docs = {"/approval": {"sha": sha, "gates": {"6a": {"pass": True}}, "approval": {"status": "approved", "approver": approver, "at": 1},
                          "ready": {"ok": not refusals, "refusals": refusals}},
            "/state": {"speaker_script": {"sha": sha, "text": text}}}

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            b = json.dumps(docs[self.path]).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b)
        def log_message(self, *a): pass
    s = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, f"http://127.0.0.1:{s.server_port}"


def run(text, refusals):
    s, url = serve(text, refusals)
    out = tempfile.mkdtemp()
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = vsl_ready.main(["--url", url, "--out", out])
    s.shutdown()
    return rc, buf.getvalue(), out


class Ready(unittest.TestCase):
    def test_passes_when_gates_pass_and_approved(self):
        rc, out, d = run(GOOD, [])
        self.assertEqual(rc, 0, out)
        rec = json.loads((Path(d) / "abc123.json").read_text())
        self.assertEqual(rec["approver"], "architect")

    def test_ready_without_approval(self):
        rc, out, d = run(GOOD, ["approval: this script version is not approved"])
        self.assertEqual(rc, 0, out); self.assertTrue(list(Path(d).glob("*.json")))

    def test_refuses_failing_gate_even_if_report_says_pass(self):
        rc, out, _ = run(BAD, [])
        self.assertEqual(rc, 1); self.assertIn("gate 6a failed (rechecked live)", out)

    def test_names_the_failing_report_gate(self):
        rc, out, _ = run(GOOD, ["gate 6b failed: claim 3 has no fact id"])
        self.assertEqual(rc, 1); self.assertIn("gate 6b failed", out)

    def test_unreachable_is_refused(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = vsl_ready.main(["--url", "http://127.0.0.1:9"])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()

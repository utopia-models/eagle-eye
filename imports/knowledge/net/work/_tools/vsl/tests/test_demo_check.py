"""demo_check.py + the runner wiring: a demo page that is the architecture diagram fails the package (Tyler 2026-11-22 6:20 AM ET)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import demo_check as D  # noqa: E402
import oneshot_runner as R  # noqa: E402


class StaticChecks(unittest.TestCase):
    def test_iframe_of_the_diagram_fails(self):
        html = '<iframe src="architecture/architecture.html" title="AI chief of staff architecture"></iframe>'
        rs = D.static_reasons(html)
        self.assertTrue(any("iframe" in r for r in rs) and any("architecture page" in r for r in rs), rs)

    def test_redirects_fail(self):
        self.assertTrue(D.static_reasons('<meta http-equiv="refresh" content="0;url=architecture/architecture.html">'))
        self.assertTrue(D.static_reasons('<script>location.href="architecture/architecture.html"</script>'))

    def test_a_real_page_passes(self):
        self.assertEqual(D.static_reasons("<main><button>Run morning briefing</button><pre>1196 orders kept</pre></main>"), [])

    def test_word_overlap(self):
        self.assertEqual(D.overlap(["architecture", "agent"], ["architecture", "agent"]), 1.0)
        self.assertLess(D.overlap(["run", "briefing", "approve"], ["architecture", "agent", "memory"]), D.WORDS_MIN)

    def test_hash_distance(self):
        self.assertEqual(D.hamming("0" * 64, "0" * 64), 0)
        self.assertEqual(D.hamming("0" * 64, "1" * 12 + "0" * 52), 12)
        self.assertEqual(D.hamming("01", "0"), 64)   # unequal lengths never count as the same picture


class RunnerWiring(unittest.TestCase):
    def test_findings_name_the_failing_page(self):
        calls = []

        def checker(url, arch):
            calls.append((url, arch))
            return {"reasons": ["demo screenshot is the diagram (perceptual hash distance 3 < 12)"]}
        f = R.demo_findings("https://ra.example/hunts/job-1/mvp/", "job-1", checker)
        self.assertTrue(f and f[0].startswith("https://ra.example/hunts/job-1/mvp/: demo screenshot is the diagram"), f)
        self.assertEqual(calls[0][1], "https://ra.example/hunts/job-1/demo/architecture/architecture.html")

    def test_a_passing_page_adds_no_finding(self):
        self.assertEqual(R.demo_findings("https://ra.example/hunts/job-1/mvp/", "job-1", lambda u, a: {"reasons": []}), [])


class GateWiring(unittest.TestCase):
    def test_a_failing_gate_stops_the_package(self):
        bad = lambda pkg: {"blocking": [{"id": 1, "name": "Real app", "why": ["demo page holds an iframe"]}], "ready": False}
        r = R.run_gates(Path("."), bad)
        self.assertFalse(r["pass"])
        self.assertEqual(r["findings"], ["gate 1 Real app: demo page holds an iframe"])

    def test_passing_gates_pass(self):
        r = R.run_gates(Path("."), lambda pkg: {"blocking": [], "ready": True})
        self.assertTrue(r["pass"] and r["ready"])

    def test_a_crash_fails_never_passes(self):
        def boom(pkg):
            raise RuntimeError("probe down")
        r = R.run_gates(Path("."), boom)
        self.assertFalse(r["pass"])
        self.assertIn("gates crashed", r["findings"][0])


if __name__ == "__main__":
    unittest.main()

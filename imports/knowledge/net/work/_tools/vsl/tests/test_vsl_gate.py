"""Golden tests for the professional-copy gate and the script pipeline.  Run: python3 -m unittest discover -s net/work/_tools/vsl/tests"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import script_check  # noqa: E402
import vsl_copy  # noqa: E402
import vsl_script  # noqa: E402

os.environ.setdefault("VSL_JUDGE", "off")   # these tests grade the mechanical gate; the judge has its own test file
G = HERE / "golden"
WEAK = ("# x\n## 1 · Opener (10 s)\n[horus] Diagram.\nSo basically we built a bunch of amazing helpers that are super good at invoices. "
        "This is a first version, and I think it could maybe help whoever runs this job.\n")


def gold(n):
    return (G / n).read_text()


class Copy(unittest.TestCase):
    def test_old_openers_fail(self):
        for n, needle in [("v9_ai_automation.md", "helpers"), ("v12_ai_automation.md", "for whoever runs this job"),
                          ("v13_ai_automation.md", "for whoever runs this job")]:
            rs = script_check.check(gold(n), asset=True, copy=True)
            self.assertTrue(any(needle in r.lower() for r in rs), (n, rs))

    def test_professional_rewrite_passes(self):
        rs = script_check.check(gold("v14_ai_automation.md"), asset=True, copy=True)
        self.assertTrue(rs and all(any(k in r for k in ("contraction", "question", "closing")) for r in rs), rs)   # v14 was professional; the no-contraction and closing rules came after
        self.assertEqual(script_check.check(gold("templates/ai_automation.take.md"), asset=True, copy=True), [])

    def test_tylers_words_each_fail(self):
        for w in ["helpers", "first version", "for whoever runs this job", "basically", "amazing", "super", "a bunch of"]:
            body = f"# x\n## 1 · A (10 s)\n[horus] cue\nThe queue retries each failed API call, and the audit log records it with {w} detail.\n"
            self.assertTrue(any("banned" in r for r in vsl_copy.check_copy(body, vale=False)[0]), w)

    def test_speakability(self):
        long = "word " * 40
        rs = vsl_copy.check_copy(f"# x\n## 1 · A (10 s)\n[horus] c\n{long}.\n", vale=False)[0]
        self.assertTrue(any("speak" in r for r in rs))
        self.assertTrue(any("technical" in r for r in rs))

    def test_weak_paragraph(self):
        rs = vsl_copy.check_copy(WEAK, vale=False)[0]
        self.assertGreaterEqual(sum("banned" in r for r in rs), 5)

    def test_vale_blocks_when_present(self):
        if not vsl_copy.find_vale():
            self.skipTest("no vale binary")
        rs = vsl_copy.check_copy(WEAK)[0]
        self.assertTrue(any(r.startswith("vale Spoken.Banned") for r in rs))


class Pipeline(unittest.TestCase):
    def test_rewrite_converges(self):
        good = gold("templates/ai_automation.take.md")
        with tempfile.TemporaryDirectory() as d:
            brief = Path(d) / "brief.yaml"
            brief.write_text("job: {title: t}\ncapabilities: [queue]\n")
            calls = []

            def model(p):
                calls.append(p)
                return good if "Return only the full rewritten script" in p else "notes\n"
            rc, found = vsl_script.rewrite(brief, Path(d) / "o.md", start=G / "v13_ai_automation.md", model=model)
            self.assertEqual((rc, found), (0, []))
            self.assertEqual(len(calls), 2)  # one critic, one rewrite
            self.assertEqual((Path(d) / "o.md").read_text(), good)

    def test_rewrite_gives_up_with_findings(self):
        with tempfile.TemporaryDirectory() as d:
            brief = Path(d) / "brief.yaml"
            brief.write_text("job: {title: t}\n")
            rc, found = vsl_script.rewrite(brief, Path(d) / "o.md", start=G / "v9_ai_automation.md", model=lambda p: gold("v9_ai_automation.md"))
            self.assertEqual(rc, 1)
            self.assertTrue(found)


if __name__ == "__main__":
    unittest.main()

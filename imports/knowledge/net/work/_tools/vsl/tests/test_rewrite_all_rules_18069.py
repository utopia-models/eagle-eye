"""knowledge#18069: E3/E9 are rewritten like E4/E6/E8/E10 (5 rounds), each finding becomes a per-rule instruction, and the reviewer/writer get the FULL post."""
import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import oneshot_auto as O, script_authoring as SA, upwork_rules as U


class T(unittest.TestCase):
    def test_every_e_rule_in_the_issue_is_rewritable_for_five_rounds(self):
        for r in ("E3", "E4", "E6", "E8", "E9", "E10"):
            self.assertIn(r, U.REWRITABLE)
        self.assertEqual((U.MAX_PASSES, SA.MAX_LOOPS), (5, 5))

    def test_findings_become_instructions(self):
        out = SA.fix_instructions([{"why": "E3: result row 2: no source"}, {"why": "E9: a list of UI labels"}, {"why": "E3: again"}])
        self.assertIn("source: {post:", out)
        self.assertIn("UI labels", out)
        self.assertEqual(out.count("E3 ="), 1)
        self.assertEqual(SA.fix_instructions([{"why": "REVIEW: x"}]), "")

    def test_full_post_beats_the_feed_snippet(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "post.md").write_text("The whole post, " * 100)
            self.assertTrue(O.full_post({"slug": "x", "text": "snippet"}, d).startswith("The whole post"))
            self.assertEqual(O.full_post({"slug": "x", "text": "snippet"}, Path(d) / "none"), "snippet")


if __name__ == "__main__":
    unittest.main()


class YamlGuard(unittest.TestCase):
    def test_broken_yaml_is_rolled_back_and_retried(self):
        d = Path(tempfile.mkdtemp()); (d / "script-source.yaml").write_text("a: 1\n")
        calls = []
        orig = SA._write_once
        def fake(pkg, jt, failing, model="sonnet"):
            calls.append(failing)
            (Path(pkg) / "script-source.yaml").write_text("a: b: c\n" if len(calls) == 1 else "a: 2\n")
        SA._write_once = fake
        try:
            SA.write(d, "post", [{"why": "E4: x", "row": "r", "file": "f"}])
        finally:
            SA._write_once = orig
        self.assertEqual((d / "script-source.yaml").read_text(), "a: 2\n")
        self.assertEqual(len(calls), 2)
        self.assertIn("unparseable", calls[1][-1]["why"])


class Repair(unittest.TestCase):
    def test_colon_row_is_quoted_and_loads(self):
        import yaml
        bad = "sections:\n- lines:\n  - say: Here's the check: every move, 'ok' # fine\n  - say: plain row\n"
        with self.assertRaises(yaml.YAMLError):
            yaml.safe_load(bad)
        f = Path(tempfile.mkdtemp()) / "s.yaml"; f.write_text(bad)
        src = U.load_source(f)
        self.assertEqual(src["sections"][0]["lines"][0]["say"], "Here's the check: every move, 'ok' # fine")
        self.assertEqual(yaml.safe_load(f.read_text()), src)

"""Variant tests (knowledge#16076): per-variant length, closing and Eagle Eye, and the one pipeline command.
Run: python3 -m unittest net/work/_tools/vsl/tests/test_vsl_variants.py"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
os.environ["VSL_JUDGE"] = "off"
import script_check  # noqa: E402
import vsl_pipeline  # noqa: E402
from test_vsl_16020_replay import script, NEXT  # noqa: E402


class Variants(unittest.TestCase):
    def test_340s_upwork_fails_170s_passes(self):
        self.assertTrue(any("length" in r for r in script_check.check(script(secs=325), variant="upwork-job")))
        self.assertEqual(script_check.check(script(secs=155), asset=True, variant="upwork-job"), [])

    def test_upwork_ceiling_is_3_min_youtube_5(self):
        s = script(secs=235)
        self.assertTrue(any("length" in r for r in script_check.check(s, variant="upwork-generic")))
        self.assertEqual(script_check.check(s, variant="youtube"), [])

    def test_eagle_eye_fails_upwork_only(self):
        s = script(body="Eagle Eye tracks every listing.")
        for v in ("upwork-job", "upwork-generic"):
            self.assertTrue(any("eagle eye" in r for r in script_check.check(s, variant=v)), v)
        self.assertEqual(script_check.check(s, variant="eagle-eye"), [])
        self.assertFalse(any("eagle eye" in r for r in script_check.check(s, variant="company")))

    def test_eagle_eye_in_a_cue_also_fails(self):
        s = script().replace("Here's the demo I built for your post.", "Here's the demo; (Horus) opens Eagle Eye")
        self.assertTrue(any("eagle eye" in r for r in script_check.check(s, variant="upwork-job")))

    def test_youtube_has_no_closing_rule(self):
        s = script(closing="Thanks for watching.")
        self.assertTrue(any("closing" in r for r in script_check.check(s, variant="upwork-job")))
        self.assertFalse(any("closing" in r for r in script_check.check(s, variant="youtube")))

    def test_unknown_variant_raises(self):
        with self.assertRaises(KeyError):
            script_check.check(script(), variant="nope")


def clean(secs=155, body="It reads the mail through IMAP, writes each invoice to Postgres, and the audit log records every approval."):
    """A client-first script (the pipeline gate is client-first, #16829 follow-up): a Signals block, their words first, seconds labels
    that match the words read at 2.5 a second."""
    pad = "Your invoice arrives in your inbox, and you see it in your approval queue before anything runs. "
    words = int(secs * 2.5)
    filler = (pad * (words // len(pad.split()) + 1)).split()[:max(0, words - 90)]
    return ("# video: x\n## Signals\n- Channel: job board\n- Phrases:\n  - \"an invoice bot for our inbox\"\n"
            "  - \"every approval in an audit log\"\n  - \"nothing sent without a person\"\n- Outcome: \"an invoice bot for our inbox\"\n"
            "\n## Do not say\n- a price\n"
            f"## 1 · Hook ({secs} s)\n[horus] Your post on screen.\nYou asked for an invoice bot for our inbox.\n"
            f"You wrote every approval in an audit log, and nothing sent without a person.\n{body}\n" + " ".join(filler) + "\n"
            f"(Horus) Here is your demo, on sample data.\n{NEXT}\n")


class Pipeline(unittest.TestCase):
    def setUp(self):
        import vsl_script
        self._old = vsl_script._ref_paths
        vsl_script._ref_paths = lambda brief: ["net/work/vsl/scripts/ref.md"]

    def tearDown(self):
        import vsl_script
        vsl_script._ref_paths = self._old

    def run_pipeline(self, variant, text, model_script, kind="job"):
        d = Path(tempfile.mkdtemp())
        (d / "in.md").write_text(text)
        ids = "abcdef"
        spec = {"title": "T", "stack": "generic", "groups": [{"id": "g", "label": "G"}],
                "nodes": [{"id": i, "label": f"N {i}", "sub": "x", "kind": "default", "group": "g"} for i in ids],
                "edges": [{"from": ids[k], "to": ids[k + 1], "label": "r"} for k in range(5)], "order": list(ids)}
        doc = vsl_pipeline.run(variant, str(d / "in.md") if kind == "job" else None, str(d / "in.md") if kind == "target" else None,
                               d / "out", model=lambda t: model_script, gen=lambda t: (spec, None))
        return d / "out", doc

    def test_emits_all_six_and_passes(self):
        out, doc = self.run_pipeline("upwork-job", "We need an invoice bot.", clean())
        for f in ("brief.yaml", "diagram.spec.json", "demo.md", "script.md", "cues.md", "qc.json"):
            self.assertTrue((out / f).is_file(), f)
        self.assertTrue(json.loads((out / "qc.json").read_text())["pass"], doc)

    def test_eagle_eye_script_fails_qc(self):
        out, doc = self.run_pipeline("upwork-job", "We need an invoice bot.", clean(body="Eagle Eye tracks every listing through IMAP, Postgres and an audit log."))
        self.assertTrue(doc["eagle_eye_hits"])

    def test_340s_fails_qc_170s_passes(self):
        self.assertFalse(self.run_pipeline("upwork-job", "x", clean(325))[1]["pass"])
        self.assertTrue(self.run_pipeline("upwork-job", "x", clean(155))[1]["pass"])

    def test_missing_input_is_a_hard_stop(self):
        with self.assertRaises(SystemExit):
            vsl_pipeline.run("upwork-job", None, "t.md", tempfile.mkdtemp())


if __name__ == "__main__":
    unittest.main()

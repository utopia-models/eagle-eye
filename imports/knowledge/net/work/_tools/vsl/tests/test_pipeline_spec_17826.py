"""knowledge#17826: the pipeline spec and the code agree (lint), the lint FAILS on a handler with no stage and a stage with no handler,
the dispatch refuses an unregistered stage, and the auto-send engine's self-test holds (45/30/0, claim, 4 h full mode, 30 min fallback)."""
import copy
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import pipeline_spec as P  # noqa: E402


class Spec(unittest.TestCase):
    def test_repo_is_clean(self):
        self.assertEqual(P.lint(), [])

    def test_handler_without_stage_fails(self):
        h = dict(P.code_handlers(), extra="mark_stage")
        self.assertTrue(any("has no stage" in x for x in P.lint(handlers=h)))

    def test_stage_without_handler_fails(self):
        h = {k: v for k, v in P.code_handlers().items() if k != "diagram"}
        self.assertTrue(any("upwork.diagram: stage has no handler" in x for x in P.lint(handlers=h)))

    def test_missing_function_fails(self):
        specs = copy.deepcopy(P.load_all())
        specs["upwork"]["stages"][0]["handler"] = "_tools/vsl/oneshot_auto.py:nope_not_here"
        self.assertTrue(any("nope_not_here" in x for x in P.lint(specs=specs, handlers=P.code_handlers())))

    def test_unknown_owner_fails(self):
        specs = copy.deepcopy(P.load_all())
        specs["startup"]["stages"][0]["owner"] = "ghost"
        self.assertTrue(any("ghost" in x for x in P.lint(specs=specs)))

    def test_feed_has_handler_links(self):
        for pl in P.feed()["pipelines"]:
            for s in pl["stages"]:
                self.assertTrue((P.WORK / s["handler_url"].split("net/work/")[1]).is_file())

    def test_dispatch_refuses_unregistered(self):
        import oneshot_auto
        with self.assertRaises(KeyError):
            oneshot_auto.dispatch("bogus")


class AutoSend(unittest.TestCase):
    def test_self_test(self):
        r = subprocess.run([sys.executable, str(HERE / "autosend.py"), "selftest"], capture_output=True, text=True, timeout=60)
        self.assertIn("self-test PASS", r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()

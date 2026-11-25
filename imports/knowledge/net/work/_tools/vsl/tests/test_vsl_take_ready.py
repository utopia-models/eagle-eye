"""vsl_take_ready: replay fixtures; each bad screen fails, naming its gate (knowledge#16072)."""
import io, json, sys, unittest
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import vsl_take_ready as t  # noqa: E402

FX = HERE / "fixtures" / "take_ready"


def run(name):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = t.main([str(FX / f"{name}.json")])
    return rc, buf.getvalue()


class TakeReady(unittest.TestCase):
    def test_good_passes(self):
        self.assertEqual(run("good")[0], 0)

    def test_clipped_diagram(self):
        rc, o = run("clipped_diagram"); self.assertEqual(rc, 1); self.assertIn("diagram: clipped", o)

    def test_sign_in_screen(self):
        rc, o = run("sign_in"); self.assertEqual(rc, 1); self.assertIn("sign-in screen", o)

    def test_obs_minimised(self):
        rc, o = run("obs_minimised"); self.assertEqual(rc, 1); self.assertIn("not full screen", o)

    def test_output_inactive(self):
        rc, o = run("output_inactive"); self.assertEqual(rc, 1); self.assertIn("outputActive", o)

    def test_frozen_diagram(self):
        r = json.loads((FX / "good.json").read_text()); r["diagram"]["frame_hashes"] = ["a", "a"]
        self.assertTrue(any("not moving" in x for x in t.decide(r)))

    def test_stale_dryrun_blocks(self):
        r = json.loads((FX / "good.json").read_text()); r["dryrun_fresh"] = False
        (FX / "_stale.json").write_text(json.dumps(r))
        try:
            rc, out = run("_stale")
        finally:
            (FX / "_stale.json").unlink()
        self.assertEqual(rc, 1); self.assertIn("dry run", out)

    def test_unread_is_refusal(self):
        self.assertEqual(len(t.decide({})), 4)

    def test_failed_demo_check(self):
        r = json.loads((FX / "good.json").read_text()); r["demo"]["checks"]["health"] = False
        self.assertTrue(any("check health" in x for x in t.decide(r)))


if __name__ == "__main__":
    unittest.main()

"""knowledge#18647: how job 3307's intro VSL was made, and the two defects the system now closes.
1. the intro template says "so that you can get <outcome>" and the writer's slot began with "get": "get get the app ready to scale".
2. the Ra renderer (render/build_intro.py) rendered a package whose job was `blocked` (E4 refused): it now refuses unless --allow-unready."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import script_rules  # noqa: E402


class GetGet(unittest.TestCase):
    def fill(self, outcome):
        src = {"intro_slots": {"role": "Technical Lead / CTO", "thing": "AI styling app", "outcome": outcome}, "sections": [{"lines": ["x"]}]}
        self.assertEqual(script_rules.fill_intro(src), [])
        return " ".join(src["sections"][0]["lines"])

    def test_leading_get_is_not_doubled(self):
        for o in ("get the app ready to scale", "to get the app ready to scale", "Get the app ready to scale"):
            t = self.fill(o)
            self.assertNotIn("get get", t.lower())
            self.assertIn("so that you can get the app ready to scale.", t)

    def test_plain_outcome_untouched(self):
        self.assertIn("so that you can get one clear queue.", self.fill("one clear queue"))


class RendererRefusesUnready(unittest.TestCase):
    def test_unknown_job_state_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            pkg = Path(d) / "up-no-such-job-0000"
            pkg.mkdir()
            r = subprocess.run([sys.executable, str(HERE / "render/build_intro.py"), str(pkg), "t0000", "--out", d + "/o"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 4, r.stderr)
            self.assertIn("not READY", r.stderr)


if __name__ == "__main__":
    unittest.main()

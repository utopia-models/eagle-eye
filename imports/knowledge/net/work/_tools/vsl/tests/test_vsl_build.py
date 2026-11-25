"""The build stamp (knowledge#15137): a take script typed from nothing is refused; one the pipeline built passes the stamp gate.
Run: python3 -m unittest discover -s net/work/_tools/vsl/tests"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
sys.path.insert(0, str(TOOLS))
import vsl_build  # noqa: E402

G = HERE / "golden" / "templates"
BRIEF = TOOLS / "templates" / "examples" / "ai-automation.brief.yaml"
ENV = dict(os.environ, VSL_JUDGE="off")


def run(*a):
    return subprocess.run([sys.executable, "-I", str(TOOLS / "vsl_script.py"), *a], capture_output=True, text=True, env=ENV)


class Build(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.d, True)

    def test_script_typed_from_nothing_is_refused(self):   # fails on main (no vsl_build at all), passes with the stamp gate
        s = self.d / "from-scratch.md"
        shutil.copy(G / "ai_automation.take.md", s)
        rs = vsl_build.check(s)
        self.assertTrue(rs and "no from-scratch.build.yaml" in rs[0], rs)
        r = subprocess.run([sys.executable, "-I", str(TOOLS / "script_check.py"), "--asset", str(s)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("build:", r.stdout)

    def test_pipeline_output_is_stamped_and_edits_unstamp_it(self):
        out = self.d / "take.md"
        r = run("new", "x", "--brief", str(BRIEF), "--template", "take", "--out", str(out))
        self.assertTrue(out.exists(), r.stderr)
        self.assertEqual(vsl_build.check(out), [])
        out.write_text(out.read_text() + "\nAn extra line.\n")
        self.assertTrue(any("changed after" in x for x in vsl_build.check(out)))

    def test_a_stamp_with_no_origin_is_refused(self):
        s = self.d / "t.md"
        s.write_text("# x\n")
        vsl_build.write(s, "vsl_script.new", [], [])
        self.assertTrue(any("no template and no reference" in x for x in vsl_build.check(s)))
        self.assertEqual(run("stamp", str(s)).returncode, 1)


if __name__ == "__main__":
    unittest.main()

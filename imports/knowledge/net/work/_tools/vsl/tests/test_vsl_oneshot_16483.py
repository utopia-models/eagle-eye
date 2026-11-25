import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import vsl_oneshot as O  # noqa: E402

SCRIPT = "# T\n## 1 · Open (10 s)\n[horus] show the diagram\nI am Tyler. You hire.\nIt reads files.\n## 2 · Demo (20 s)\n[horus] switch tab\nLive run.\n"


class OneShot(unittest.TestCase):
    def test_eagle_from_script(self):
        with tempfile.TemporaryDirectory() as d:
            s = Path(d) / "script.md"
            s.write_text(SCRIPT)
            out, doc = O.run("eagle", Path(d) / "o" / "eagle.md", script=s)
            self.assertIsNone(doc)
            self.assertIn("| C1 | It reads files. | 4 | switch tab |", out.read_text())

    def test_speaker_and_eagle_via_pipeline(self):
        def fake(variant, job, target, outdir, slug):
            (Path(outdir) / "script.md").write_text(SCRIPT)
            (Path(outdir) / "horus-script.md").write_text("EAGLE")
            return {"pass": True}
        with tempfile.TemporaryDirectory() as d:
            sp, _ = O.run("speaker", Path(d) / "s.md", variant="v", job="j", pipeline=fake)
            ea, _ = O.run("eagle", Path(d) / "e.md", variant="v", job="j", pipeline=fake)
            self.assertEqual(sp.read_text(), SCRIPT)
            self.assertEqual(ea.read_text(), "EAGLE")

    def test_missing_input_is_hard_stop(self):
        with self.assertRaises(SystemExit):
            O.run("speaker", "/tmp/x-oneshot.md")


if __name__ == "__main__":
    unittest.main()

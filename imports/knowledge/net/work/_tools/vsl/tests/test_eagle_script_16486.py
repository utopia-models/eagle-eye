import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import vsl_cue_lint_bridge as B  # noqa: E402
import vsl_jobs  # noqa: E402
import vsl_pipeline as P  # noqa: E402

SCRIPT = """# T
## 1 · Open (10 s)
[horus] show the diagram
I am Tyler Youk. You are hiring for a data pipeline.
It reads your files.
## 2 · Demo (20 s)
[horus] switch to the demo tab
Here is the live run of your system.
"""


class EagleScript(unittest.TestCase):
    def test_cue_table_from_speaker_script(self):
        h = P.make_horus_script(SCRIPT, "x")
        self.assertEqual(B.lint(h), [])
        self.assertIn("| C1 | It reads your files. | 4 | switch to the demo tab |", h)
        self.assertIn("(take ends)", h)

    def test_stage_loads_both_scripts(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            pkg = Path(d)
            loaded = []

            def pipeline(*a):
                out = a[3]
                out.mkdir(parents=True, exist_ok=True)
                (out / "script.md").write_text(SCRIPT)
                (out / "horus-script.md").write_text(P.make_horus_script(SCRIPT, "x"))
                return {"pass": True}
            job = {"key": "k1", "slug": "x", "source": "s", "title": "t"}
            ok, _ = vsl_jobs.stage(job, Path(d) / "jobs", pkg, pipeline=pipeline,
                                   loader=lambda s, p: loaded.append((s, p.name)) or (True, "ok"), ledger=Path(d) / "l.jsonl")
            self.assertTrue(ok)
            self.assertEqual(loaded, [("x", "script.md"), ("x-horus-script", "horus-script.md")])


if __name__ == "__main__":
    unittest.main()

"""vsl_jobs.py (knowledge#16293): the selftest is the suite; this runs it under unittest discover."""
import subprocess, sys, unittest
from pathlib import Path


class VslJobs(unittest.TestCase):
    def test_selftest(self):
        r = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / "vsl_jobs.py"), "--selftest"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("checks passed", r.stdout)


if __name__ == "__main__":
    unittest.main()

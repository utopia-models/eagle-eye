"""knowledge#18939: FULL VSL on a hunt stops the intro countdown and loads the job's full script into Vizier; INTRO puts it back on the clock."""
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))


class TakeOver(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        os.environ["ONESHOT_AUTO_DIR"] = self.d + "/state"
        os.environ["ONESHOT_PKG_ROOT"] = self.d + "/pkg"
        import importlib
        import oneshot_auto as A
        self.A = importlib.reload(A)
        self.slug = "acme-1"
        ready = self.A.iso(self.A.now())
        self.A.save_job({"slug": self.slug, "job": "~0123456789012345678", "title": "Acme", "state": "ready", "fit": "high", "t": {"ready": ready}, "events": []})
        (self.A.PKG_ROOT / self.slug).mkdir(parents=True)
        (self.A.PKG_ROOT / self.slug / "entire-script.md").write_text("[Tyler] hello\n")

    def test_full_claims_stops_countdown_and_loads_script(self):
        A = self.A
        self.assertEqual(A.hunt_state("5678")["state"], "waiting")        # trailing digits resolve the job; the intro clock runs
        calls = []
        A.load_full_script.__globals__["VIZIER_PUT"] = Path("/nonexistent")  # the real put must not run here
        orig = A.load_full_script
        A.load_full_script = lambda slug, put=None: (calls.append(slug), orig(slug, put=lambda p: subprocess.CompletedProcess([], 0, "put x -> speaker-script sha=abc123 in 40 ms\n", "")))[1]
        t0 = time.time()
        r = A.take_over("5678", "full", voice=False)
        self.assertLess(time.time() - t0, 5)
        self.assertEqual(r["state"], "claimed")                            # countdown stopped
        self.assertEqual(r["take"], "full")
        self.assertEqual(r["script_sha"], "abc123")
        self.assertTrue(r["script_loaded_at"])
        self.assertEqual(calls, [self.slug])
        self.assertEqual(A.due_intros(), [])
        r = A.take_over("5678", "intro")                                   # back on the auto-send clock
        self.assertEqual(r["state"], "waiting")
        self.assertEqual(r["take"], "intro")

    def test_voice_claim_opens_full_mode_and_marks_voice(self):
        A = self.A
        orig = A.load_full_script
        A.load_full_script = lambda slug, put=None: orig(slug, put=lambda p: subprocess.CompletedProcess([], 0, "sha=def456", ""))
        r = A.take_over(self.slug, "full", voice=True)
        self.assertEqual((r["by"], r["claim_by"]), ("voice", "voice"))
        self.assertIsNotNone(A.read_full_mode())

    def test_missing_script_still_claims(self):
        A = self.A
        (A.PKG_ROOT / self.slug / "entire-script.md").unlink()
        r = A.take_over(self.slug, "full")
        self.assertEqual(r["state"], "claimed")
        self.assertFalse(r["did"]["claim"]["script"]["ok"])

    def test_unknown_job_raises(self):
        with self.assertRaises(ValueError):
            self.A.take_over("99999999", "full")


if __name__ == "__main__":
    unittest.main()

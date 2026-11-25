"""#18869: human motion model, stage ledger, contract has no AI-voice line."""
import math
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE / "render"))
import human_motion as hm  # noqa: E402
import oneshot_runner as OR  # noqa: E402
import script_rules  # noqa: E402


class T(unittest.TestCase):
    def test_path_is_curved_and_ends_on_target(self):
        p = hm.bezier_path(0, 0, 800, 300, 40)
        dev = max(abs(300 * x - 800 * y) / math.hypot(800, 300) for x, y in p)
        self.assertGreater(dev, 5)
        self.assertAlmostEqual(p[-1][0], 800, delta=4)

    def test_fitts_time_grows_with_distance(self):
        self.assertLess(sum(hm.fitts_ms(100) for _ in range(50)), sum(hm.fitts_ms(1500) for _ in range(50)))

    def test_ledger_reads_the_run(self):
        run = {"signal_at": "2026-11-24T10:00:00Z", "mp4_at": "2026-11-24T10:09:30Z", "stages": {"scripts": {"s": 120.0}}}
        self.assertTrue(OR.ledger(run)["within_limit"])
        run["mp4_at"] = "2026-11-24T10:11:00Z"
        self.assertFalse(OR.ledger(run)["within_limit"])
        self.assertIsNone(OR.ledger({"signal_at": "2026-11-24T10:00:00Z"})["within_limit"])

    def test_stage_accumulates(self):
        run = {}
        with OR.stage(run, "x"): pass
        with OR.stage(run, "x"): pass
        self.assertIn("s", run["stages"]["x"])

    def test_contract_intro_never_names_the_voice(self):
        r = script_rules.rules()
        for k in ("intro_full", "intro_auto"):
            self.assertNotIn("AI voice", r[k])


if __name__ == "__main__":
    unittest.main()

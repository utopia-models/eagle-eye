"""Gates 6 (orb) and 7 (sync) are decided by takeflow/preflight.py from the package files, with no recorded take (chief #15729, Tyler 2026-11-22 18:24Z)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gates  # noqa: E402

PF = {"orb": {"pass": True, "why": "corr 0.7"}, "sync": {"pass": False, "why": "7 browser steps for 11 AI rows"}, "tabs": {"pass": True, "why": "ok"}}


class PreflightGates(unittest.TestCase):
    def test_a_passing_check_is_a_pass(self):
        g = gates.preflight_gate(6, "Orb", "orb", "x", PF)
        self.assertEqual((g["id"], g["status"], g["why"]), (6, "pass", []))

    def test_a_failing_check_fails_with_the_preflight_reason(self):
        g = gates.preflight_gate(7, "Sync", "sync", "x", PF)
        self.assertEqual(g["status"], "fail")
        self.assertIn("7 browser steps for 11 AI rows", g["why"][0])

    def test_a_preflight_that_cannot_run_is_pending_never_a_pass(self):
        g = gates.preflight_gate(6, "Orb", "orb", "x", {"error": "timeout"})
        self.assertEqual(g["status"], "pending")
        self.assertIn("did not run", g["why"][0])

    def test_a_missing_check_fails(self):
        self.assertEqual(gates.preflight_gate(7, "Sync", "sync", "x", {"orb": PF["orb"]})["status"], "fail")

    def test_orb_and_sync_failures_never_block_ready_or_the_script_auto_fix(self):
        out = [gates.res(3, "Script", ["row too long"]), gates.res(6, "Orb", ["no narration wav"]), gates.res(7, "Sync", ["0 AI rows"]), gates.res(9, "Readiness", ["x"])]
        self.assertEqual([g["id"] for g in gates.blocking_gates(out)], [3, 9])

    def test_preflight_runner_error_is_reported(self):
        def boom(*a, **k):
            raise OSError("no python")
        self.assertIn("error", gates.preflight("x", runner=boom))


if __name__ == "__main__":
    unittest.main()

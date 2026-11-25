"""Replay tests for Tyler's 2026-11-21 card: client-first VSLs (script_check.py).
Run: python3 -m unittest net/work/_tools/vsl/tests/test_client_first_replay.py
The Lanam text is READ ONLY test data; nothing here records, sends or touches anything for Lanam/Adam.
 1. the current Lanam tyler-script (graded against the client's signals) fails opener, coverage, ratio, questions
 2. a client-first fixture passes
 3. each of the new rules fails a one-line break of the fixture (and passes the fixture)"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import script_check  # noqa: E402

FIX = (HERE / "fixtures/client_first/lanam_client_first.md").read_text()
LANAM = (HERE.parents[2] / "vsl/lanam/tyler-script.md").read_text()
SIG = script_check.parse_signals(FIX)


def has(rs, word):
    return any(r.startswith(word) for r in rs)


class ClientFirst(unittest.TestCase):
    def test_fixture_passes(self):
        self.assertEqual(script_check.check(FIX), [])

    def test_current_lanam_script_fails(self):
        rs = script_check.check(LANAM, signals=SIG, client_first=True)
        for k in ("opener", "coverage", "ratio", "questions"):
            self.assertTrue(has(rs, k), (k, rs))

    def test_lanam_without_signals_fails(self):
        self.assertTrue(has(script_check.check(LANAM, client_first=True), "signals"))

    def test_opener_must_be_a_client_phrase(self):
        s = FIX.replace("Adam, you asked for one web app that shows live data from every platform.",
                        "Adam, it is Tyler, and here is what I will walk you through.")
        s = s.replace("You asked for an AI assistant for the CEO inside the dashboard that knows the state of the business and answers questions.",
                      "Here is how it goes.")
        self.assertTrue(has(script_check.check(s), "opener"))

    def test_coverage(self):
        s = "\n".join(l for l in FIX.splitlines() if not l.startswith(("You wrote that", "This is the CEO view", "Your post says",
                                                                         "You asked for a full", "You asked for an AI")))
        self.assertTrue(has(script_check.check(s), "coverage"))

    def test_ratio(self):
        s = FIX.replace("Ask the assistant who owes you the most and how late, and it answers from your data, read-only.",
                        "I made the assistant, my design reads my data, and I tuned my prompts, my tests, my logs and my queue.")
        self.assertTrue(has(script_check.check(s), "ratio"))

    def test_every_client_question_answered(self):
        s = FIX.replace("You asked for a rough estimate of the first milestone: three weeks, with a demo at the end of each week.",
                        "The first milestone has a demo at the end of each stage.")
        self.assertTrue(has(script_check.check(s), "questions"))

    def test_capability_first_framing(self):
        s = FIX.replace("Close and QuickBooks use the same OAuth sync pattern, so your first sync is not new ground.",
                        "We can do any integration you need for your business.")
        self.assertTrue(has(script_check.check(s), "capability"))

    def test_public_copy_look_at_us_pattern(self):
        s = FIX.replace("Every step lands in the activity log: who did what, and when.",
                        "Every step lands in the log, and my agents run 40 activities a day for your business.")
        self.assertTrue(has(script_check.check(s), "capability"))

    def test_outline_is_optional_but_still_checkable(self):
        self.assertEqual(script_check.check(FIX), [])
        self.assertTrue(has(script_check.check(FIX, outline=True), "outline"))

    def test_clients_own_words_pass_the_banned_list(self):
        quoted = FIX.replace('  - "a full activity log and approvals for sensitive actions"\n',
                             '  - "a full activity log and approvals for sensitive actions"\n  - "an AI agent that reads our books"\n')
        quoted = quoted.replace("You asked for a full activity log", "You asked for an AI agent that reads our books, and a full activity log")
        self.assertEqual(script_check.check(quoted), [])
        # the same word is still banned when the client never said it
        self.assertTrue(any("agent" in r for r in script_check.check(FIX.replace("Your manager reads", "My agent reads"))))

    def test_next_step_may_be_a_live_walkthrough(self):
        s = FIX.replace("The next build is the Close and QuickBooks sync, and I can start it the day you reply.",
                        "Fifteen minutes, live, on your own Close and QuickBooks accounts.")
        self.assertEqual(script_check.check(s), [])

    def test_seconds_labels_match_words(self):
        s = FIX.replace("(15 s)", "(60 s)")
        self.assertTrue(has(script_check.check(s), "length"))

    def test_unfilled_placeholder_fails(self):
        self.assertTrue(has(script_check.check(FIX.replace("Adam,", "<first name>,", 1)), "placeholder"))


if __name__ == "__main__":
    unittest.main()

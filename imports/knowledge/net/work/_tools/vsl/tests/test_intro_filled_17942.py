"""knowledge#17942: the intro is FILLED from writer slots (E0 by construction) and E4/E6/E10 are rewritten (3 passes) instead of blocking."""
import sys
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))
import script_rules  # noqa: E402
import upwork_rules as U  # noqa: E402
import test_upwork_rules_17592 as T  # noqa: E402

SLOTS = {"role": "a Zendesk lead", "thing": "triage queue", "outcome": "one clear queue"}


def with_slots(slots, mut=None):
    def m(s):
        s["intro_slots"] = slots
        s["sections"][0]["lines"] = ["placeholder"]
        if mut:
            mut(s)
    return T.pkg(m)


class Filled(unittest.TestCase):
    def test_new_wording_in_contract(self):
        self.assertIn("a software architecture diagram behind it", script_rules.rules()["intro_full"])
        self.assertIn("a software architecture diagram behind it", script_rules.rules()["intro_auto"])

    def test_e0_passes_filled_with_and_without_name(self):
        for slots in (SLOTS, dict(SLOTS, name="Dana")):
            d = with_slots(slots)
            self.assertNotIn("E0", {x["rule"] for x in U.check(d)})
        self.assertTrue(script_rules.intro_full("Dana", "r", "t", "o").startswith("Hi Dana, I'm Tyler"))
        self.assertTrue(script_rules.intro_full("", "r", "t", "o").startswith("Hi, I'm Tyler"))

    def test_auto_cluster_fills(self):
        d = with_slots({"cluster": "Zendesk support"})
        self.assertNotIn("E0", {x["rule"] for x in U.check(d)})
        U.fill_file(d)
        self.assertIn("your Zendesk support post, so I made you a working version and a software architecture diagram behind it",
                      " ".join(yaml.safe_load((d / "script-source.yaml").read_text())["sections"][0]["lines"]))

    def test_filled_intro_rows_fit_the_prompter(self):
        # gate 3 blocked 1339/1291/8891 on Ra 2026-11-24: the filled intro was ONE 52-55-word row (prompter: 15 words, 2 sentences)
        import script_rules as SR
        line = SR.intro_full("Ana", "a developer for RFQs semantic search and weighted matching", "SAM.gov solicitation ranker",
                             "see how well each solicitation matches each criterion")
        rows = SR.split_rows(line)
        self.assertEqual(" ".join(rows), line)
        self.assertTrue(all(len(r.split()) <= 15 for r in rows), rows)
        self.assertFalse(any(r.split()[-1].lower() in SR.BREAK_BEFORE for r in rows), rows)

    def test_missing_slot_named(self):
        d = with_slots({"role": "x"})
        self.assertTrue(any(x["rule"] == "E0" and "thing" in x["why"] for x in U.check(d)))

    def test_old_wording_authored_is_refused(self):
        def m(s): s["sections"][0]["lines"] = [T.INTRO.replace("a software architecture diagram", "the diagram")]
        self.assertIn("E0", {x["rule"] for x in U.check(T.pkg(m))})


def edit_rows(d, fn):
    p = d / "script-source.yaml"
    s = yaml.safe_load(p.read_text())
    for sec in s["sections"][1:]:
        sec["lines"] = [fn(l) for l in sec["lines"]]
    p.write_text(yaml.safe_dump(s))


class Rewrite(unittest.TestCase):
    def test_long_row_split_and_passes(self):
        long = "Here's the Zendesk queue, all sorted for you, and every ticket shows its status, so you never guess by hand today."
        d = T.pkg(lambda s: s["sections"][1]["lines"].__setitem__(3, long))
        self.assertIn("E6", {x["rule"] for x in U.check(d)})
        calls = []
        def rw(pkg, fails):
            calls.append(fails)
            edit_rows(pkg, lambda l: "Here's the Zendesk queue, all sorted for you." if l == long else l)
        fails, used = U.rewrite_loop(d, rw)
        self.assertEqual((fails, used), ([], 1))

    def test_grade_row_simplified(self):
        hard = "Zendesk ticket categorization necessitates comprehensive organizational heterogeneity."
        d = T.pkg(lambda s: s["sections"][1]["lines"].__setitem__(4, hard))
        self.assertTrue({"E4"} <= {x["rule"] for x in U.check(d)})
        fails, used = U.rewrite_loop(d, lambda pkg, f: edit_rows(pkg, lambda l: "Nothing about a refund leaves without your yes." if l == hard else l))
        self.assertEqual(fails, [])

    def test_short_beat_padded_from_post(self):
        d = T.pkg(lambda s: s["sections"][2]["lines"].__delitem__(slice(1, 4)))
        self.assertIn("E10", {x["rule"] for x in U.check(d)})
        def pad(pkg, f):
            p = pkg / "script-source.yaml"
            s = yaml.safe_load(p.read_text())
            s["sections"][2]["lines"][1:1] = T.DIAGRAM[1:4]
            p.write_text(yaml.safe_dump(s))
        fails, used = U.rewrite_loop(d, pad)
        self.assertEqual((fails, used), ([], 1))

    def test_pass_three_failure_blocks_naming_row_and_rule(self):
        long = "Here's the Zendesk queue, all sorted for you, and every ticket shows its status, so you never guess by hand today."
        d = T.pkg(lambda s: s["sections"][1]["lines"].__setitem__(3, long))
        n = []
        fails, used = U.rewrite_loop(d, lambda p, f: n.append(1))
        self.assertEqual((used, len(n)), (U.MAX_PASSES, U.MAX_PASSES))
        self.assertTrue(any(x["rule"] == "E6" and (x["row"] or "").startswith("Here's the Zendesk") for x in fails))

    def test_non_rewritable_rule_is_not_looped(self):
        import script_rules as SR
        def m(s): s["sections"][2]["lines"].insert(0, SR.rules()["close_line"])   # E11 'the close line appears more than once': never rewritten
        n = []
        fails, used = U.rewrite_loop(T.pkg(m), lambda p, f: n.append(1))
        self.assertEqual((used, n), (0, []))
        self.assertTrue(fails and any(x["rule"] not in U.REWRITABLE for x in fails), fails)


if __name__ == "__main__":
    unittest.main()

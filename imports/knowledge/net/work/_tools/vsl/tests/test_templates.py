"""Golden tests: template library, reference retrieval.  Run: python3 -m unittest discover -s net/work/_tools/vsl/tests"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import script_check  # noqa: E402
import vsl_copy  # noqa: E402
import vsl_ref  # noqa: E402
import vsl_script  # noqa: E402
import vsl_template  # noqa: E402

G = HERE / "golden"
BRIEF = HERE.parent / "templates/examples/ai-automation.brief.yaml"


def brief():
    return vsl_script.load_yaml(BRIEF)


class Templates(unittest.TestCase):
    def test_take_matches_golden_and_passes_gate(self):
        out = vsl_template.take(brief(), BRIEF.parent)
        self.assertEqual(out, (G / "templates/ai_automation.take.md").read_text())
        self.assertEqual(vsl_script.gate(out), [])

    def test_each_template_is_professional(self):
        for t in vsl_template.TEMPLATES:
            text = " ".join(vsl_template.render(brief(), t, BRIEF.parent))
            self.assertNotRegex(text, vsl_copy.CONTRACTION, t)
            for p in vsl_copy.BANNED:
                self.assertNotRegex(text, "(?i)" + p, (t, p))

    def test_hook_opens_on_their_words(self):
        o = vsl_template.render(brief(), "hook")
        self.assertEqual(o[0], "Sam, you asked for AI agents that handle invoicing and email.")
        self.assertEqual(vsl_template.render({**brief(), "take": {}}, "hook")[0], "You asked for AI agents that handle invoicing and email.")

    def test_missing_required_slot_is_an_error_not_a_guess(self):
        b = brief()
        del b["take"]["flow"]
        with self.assertRaises(vsl_template.MissingSlot) as cm:
            vsl_template.render(b, "flow")
        self.assertIn("take.flow", str(cm.exception))

    def test_fewer_than_three_client_phrases_is_an_error(self):
        b = brief()
        b["signals"]["phrases"] = b["signals"]["phrases"][:2]
        with self.assertRaises(vsl_template.MissingSlot) as cm:
            vsl_template.render(b, "signals")
        self.assertIn("signals.phrases", str(cm.exception))

    def test_a_question_without_an_answer_is_an_error(self):
        b = brief()
        del b["signals"]["questions"][0]["answer"]
        with self.assertRaises(vsl_template.MissingSlot) as cm:
            vsl_template.take(b, BRIEF.parent)
        self.assertIn("answer", str(cm.exception))

    def test_old_openers_fail_template_openers_pass(self):
        for n in ("v9_ai_automation.md", "v12_ai_automation.md", "v13_ai_automation.md"):
            self.assertTrue(script_check.check((G / n).read_text(), asset=True, copy=True), n)
        old = ("# x\n## 1 · A (10 s)\n[horus] cue\nI just built this for you. For whoever runs this job, this is a first version "
               "with a few helpers; I'm happy to walk through the queue, the API and the audit log.\n")
        rs = vsl_copy.check_copy(old, vale=False)[0]
        for needle in ("helpers", "first version", "for whoever runs this job", "contraction"):
            self.assertTrue(any(needle in r.lower() for r in rs), (needle, rs))
        self.assertIn(r"\bI just built (?:this|it) for you\b", vsl_copy.BANNED)
        self.assertTrue(any("contraction" in r for r in rs))
        self.assertEqual(vsl_script.gate(vsl_template.take(brief(), BRIEF.parent)), [])

    def test_new_template_cli(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "take.md"
            rc = vsl_script.main(["new", "x", "--brief", str(BRIEF), "--template", "take", "--reference", "--out", str(out)])
            self.assertEqual(rc, 0)
            self.assertTrue((Path(d) / "references.md").exists())
            self.assertIn("## Signals", out.read_text())

    def test_contraction_regex(self):
        for w in ("I'm", "You're", "I'll", "I'd", "don't", "it's", "wasn't", "I've"):
            self.assertRegex(w, vsl_copy.CONTRACTION)
        self.assertNotRegex("Tyler's script", vsl_copy.CONTRACTION)


class Closing(unittest.TestCase):
    GOOD = (G / "templates/ai_automation.take.md").read_text()
    NEXT = "The next build is the QuickBooks and Gmail integration behind this same approval gate, and I can start it the day you reply."

    def gate(self, text):
        return script_check.check(text, asset=True, copy=True, client_first=True)

    def test_statement_closing_passes_without_reply_here(self):
        self.assertNotIn("Reply here", self.GOOD)
        self.assertEqual(self.gate(self.GOOD), [])

    def test_reply_here_is_refused_and_names_the_line(self):
        rs = self.gate(self.GOOD + "Reply here and I will send the next build.\n")
        self.assertTrue(any(r.startswith("closing: 'Reply here'") and "Reply here and I will send" in r for r in rs), rs)

    def test_question_is_refused_and_names_the_line(self):
        rs = self.gate(self.GOOD.replace("Every action", "Which company should I test against? Every action"))
        self.assertTrue(any(r.startswith("question:") and "Which company should I test against?" in r for r in rs), rs)

    def test_exactly_one_next_step_statement(self):
        none = self.gate(self.GOOD.replace(self.NEXT, "Every step is logged."))
        self.assertTrue(any("0 next-step statements" in r for r in none), none)
        two = self.gate(self.GOOD.replace(self.NEXT, self.NEXT + " The next step is a second one."))
        self.assertTrue(any("2 next-step statements" in r for r in two), two)

    def test_next_step_is_the_last_sentence(self):
        rs = self.gate(self.GOOD.replace(self.NEXT, self.NEXT + " The audit log shows who approved it."))
        self.assertTrue(any("must be the last spoken sentence" in r for r in rs), rs)

    def test_word_limit_and_contractions_kept(self):
        self.assertTrue(any("750" in r for r in self.gate(self.GOOD.replace("Sam, you asked for", "Sam, you asked for " + "word " * 800 + ". You asked for"))))
        self.assertTrue(any("contraction" in r for r in self.gate(self.GOOD.replace("I built this", "I've built this"))))


OLD_OPENER = "going through your whole"          # the seller-first opener, removed 2026-11-21
OLD_BUILT = "I designed and built a working implementation"


class ClientFirstMigration(unittest.TestCase):
    """Replay of the gap left by #16829: take, outline and Ready used the seller-first opener and did not grade client-first."""

    def take(self):
        return vsl_template.take(brief(), BRIEF.parent)

    def test_generated_script_passes_the_client_first_check(self):
        t = self.take()
        self.assertEqual(script_check.check(t, asset=True, copy=True, client_first=True), [])
        self.assertEqual(vsl_script.gate(t), [])

    def test_beats_are_saraevs_order(self):
        titles = [l.split("·", 1)[1].rsplit("(", 1)[0].strip() for l in self.take().splitlines() if l.startswith("## ") and l[3].isdigit()]
        self.assertEqual(titles, ["Hook: what they asked for", "Their problem, back to them", "Their flow, shown",
                                  "One line of proof", "One next step"])
        self.assertIn("## Signals", self.take())

    def test_old_opener_never_appears_in_generated_output(self):
        import vsl_slot
        out = [self.take(), vsl_slot.outline("Acme", "upwork", first_name="Ada"), vsl_slot.outline("Acme", "cold")]
        out += [" ".join(vsl_template.render(brief(), t, BRIEF.parent)) for t in vsl_template.TEMPLATES]
        for o in out:
            self.assertNotIn(OLD_OPENER, o)
            self.assertNotIn(OLD_BUILT, o)
            self.assertNotIn("I am Tyler Youk", o)

    def test_legacy_opener_path_is_gone(self):
        self.assertFalse(hasattr(script_check, "OPENER"))
        self.assertEqual([p.name for p in vsl_template.TDIR.glob("opening.v*.yaml")], [])
        legacy = ("# x\n## 1 · Opener (5 s)\n[horus] Their post.\nI'm going through your whole post right now.\n")
        self.assertFalse(any(r.startswith("opener") for r in script_check.check(legacy, client_first=False)))

    def test_outline_has_the_same_beats_and_is_refused_until_filled(self):
        import vsl_slot
        o = vsl_slot.outline("Acme", "upwork", first_name="Ada")
        for title in [x[0] for x in vsl_template.outline_beats()]:
            self.assertIn(title, o)
        self.assertIn("## Signals", o)
        self.assertIn("Ada, you asked for", o)
        rs = script_check.check(o, client_first=True)
        self.assertTrue(any(r.startswith("placeholder") for r in rs), rs)

    def test_ready_runs_client_first(self):
        import vsl_ready
        self.assertEqual(vsl_ready.decide({"ready": {"refusals": []}}, self.take()), [])
        legacy = (G / "v14_ai_automation.md").read_text()
        rs = vsl_ready.decide({"ready": {"refusals": []}}, legacy)
        self.assertTrue(any("signals: no `## Signals` block" in r for r in rs), rs)
        sellerfirst = self.take().replace("Sam, you asked for AI agents that handle invoicing and email.\nYou wrote a human approving every step.\nYou also wrote nothing executes until a person approves.", "I am Tyler Youk and I will walk you through it.\nHere is the plan.\nThen the demo.")
        self.assertTrue(any("opener" in r for r in vsl_ready.decide({"ready": {"refusals": []}}, sellerfirst)))


class Rate(unittest.TestCase):
    PHRASES = ["bidding low", "bid low", "low bid", "discount", "cheap", "affordable rate", "my rate", "for a lower price",
               "I know I am", "I understand that we are"]

    def test_each_phrase_fails_with_the_message_and_the_line(self):
        for w in self.PHRASES:
            body = f"# x\n## 1 · A (10 s)\n[horus] cue\nThe queue retries each failed API call, and {w} the audit log records it.\n"
            rs = vsl_copy.check_copy(body, vale=False)[0]
            self.assertTrue(any("rate/apology language: price belongs in the bid field, not the video" in r and "The queue retries" in r
                                for r in rs), (w, rs))

    def test_golden_take_is_clean(self):
        self.assertFalse([r for r in vsl_copy.check_copy((G / "templates/ai_automation.take.md").read_text(), vale=False)[0] if "rate/apology" in r])

    def test_vale_style_has_the_same_phrases(self):
        y = (HERE.parent / "vale/styles/Spoken/Rate.yml").read_text()
        for w in self.PHRASES:
            self.assertIn(w.replace("discount", "discount\\w*").replace("cheap", "cheap\\w*") if w in ("discount", "cheap") else w, y)


class Reference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ["VSL_REF_DB"] = str(Path(cls.tmp.name) / "i.sqlite")
        vsl_ref.build()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_ai_automation_brief_retrieves_accepted_opener(self):
        paths = [h["path"] for h in vsl_ref.search(vsl_ref.brief_text(brief()), 5)]
        self.assertIn("vsl/ai-automation/tyler-script.md", paths)
        self.assertIn("_tools/vsl/tests/golden/v14_ai_automation.md", paths)

    def test_rejected_scripts_never_retrieved(self):
        paths = [h["path"] for h in vsl_ref.search("helpers invoicing email agent approval whoever runs this job", 20)]
        self.assertFalse([p for p in paths if p.endswith(("v9_ai_automation.md", "v12_ai_automation.md", "v13_ai_automation.md"))])

    def test_provenance_and_corpus(self):
        md, hits = vsl_ref.references_md(brief(), 3)
        self.assertIn("status: accepted", md)
        self.assertIn("source: net/work/", md)
        total, rows = vsl_ref.stats()
        self.assertGreaterEqual(total, 40)
        ex = [h for h in vsl_ref.search("demo script API walkthrough", 10) if h["kind"] == "exemplar"]
        self.assertTrue(all(h["source_url"].startswith("http") and h["licence"] for h in ex))

    def test_draft_prompt_carries_references(self):
        seen = []
        with tempfile.TemporaryDirectory() as d:
            b = Path(d) / "b.yaml"
            b.write_text(BRIEF.read_text())
            good = (G / "templates/ai_automation.take.md").read_text()
            vsl_script.rewrite(b, Path(d) / "o.md", model=lambda p: (seen.append(p), good)[1])
        self.assertTrue(any("Reference 1:" in p for p in seen))


if __name__ == "__main__":
    unittest.main()

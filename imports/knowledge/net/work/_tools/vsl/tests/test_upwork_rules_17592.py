"""upwork_rules E1-E5 (knowledge#17592): a passing package, one refusal test per rule, nothing written on refusal, delivered-time fill."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import gen_scripts  # noqa: E402
import upwork_rules as U  # noqa: E402

POST = ("We need a Zendesk ticket triage system that routes refund requests to Stripe and escalates chargebacks to the finance lead. "
        "Our team loses hours each day sorting tickets by hand. We want one clear queue and fast answers for every customer.")
INTRO = ("Hi, I'm Tyler Youk with Utopia Models. I noticed your post for a Zendesk lead, so I made you a working triage queue "
         "and a software architecture diagram behind it, so that you can get one clear queue.")
CLOSE = ("This is a perfect match for what you posted. Reply to my proposal so we can schedule a quick call and solve this for you right away.")
APP = ["Here's the Zendesk queue, all sorted for you.", "A refund ticket arrives. It goes to Stripe with one click.",
       "A chargeback ticket arrives. It reaches the finance lead at once.", "You see the status of each ticket, so you never guess by hand.",
       "Nothing about a refund leaves without your yes."]
DIAGRAM = ["Each Zendesk ticket enters one triage queue.", "Refund requests route to Stripe, and a person approves them.",
           "Chargebacks go up to your finance lead with a note.", "Each choice is logged, so you can check any ticket.", CLOSE]


def src():
    app = ["Your Zendesk ticket queue opens on a refund request.",
           "It routes to Stripe with one click.",
           {"say": "Your team no longer loses hours each day sorting tickets by hand.", "outcome": True, "source": {"post": "Our team loses hours each day sorting tickets by hand"}}]
    app += APP
    return {"slug": "t", "title": "t", "urls": {"app": "http://a", "diagram": "http://d"}, "handoff": "My voice agent will walk you through it.",
            "sections": [{"id": "intro", "heading": "Intro", "cue": "none", "lines": [INTRO]},
                         {"id": "app", "heading": "The working app", "cue": "tab 1", "lines": app},
                         {"id": "diagram", "heading": "The diagram", "cue": "tab 2", "lines": list(DIAGRAM)}]}


def pkg(mut=None):
    d = Path(tempfile.mkdtemp())
    s = src()
    if mut:
        mut(s)
    (d / "script-source.yaml").write_text(yaml.safe_dump(s))
    (d / "post.md").write_text(POST)
    return d


def rules(d, delivered=False):
    return {x["rule"] for x in U.check(d, delivered)}


class T(unittest.TestCase):
    def test_row_without_say_is_a_named_failure_not_a_keyerror(self):
        def m(s):
            s["sections"][1]["lines"].append({"outcome": True})
        r = U.check(pkg(m))
        self.assertEqual([x["rule"] for x in r], ["rows"])
        self.assertEqual(U.say({"outcome": True}), "")

    def test_pass(self):
        self.assertEqual(U.check(pkg()), [])

    def test_e0_intro_full_matches_with_and_without_a_name(self):
        for intro in (INTRO, INTRO.replace("Hi,", "Hi Dana,")):
            def m(s, intro=intro): s["sections"][0]["lines"] = [intro]
            self.assertNotIn("E0", rules(pkg(m)))

    def test_e0_intro_auto_library_shape_matches(self):
        auto = "Hi, I'm Tyler Youk with Utopia Models. I noticed your Zendesk support post, so I made you a working version and a software architecture diagram behind it."
        def m(s): s["sections"][0]["lines"] = [auto]
        self.assertNotIn("E0", rules(pkg(m)))

    def test_e0_intro_split_over_rows_still_matches(self):
        a, b = INTRO.split(". ", 1)
        def m(s): s["sections"][0]["lines"] = [a + ".", b]
        self.assertNotIn("E0", rules(pkg(m)))

    def test_e0_mismatches_are_refused(self):
        for bad in ("Hi Dana, I recorded a short video for you (attached) that walks through your ticket triage and a working version I built for it.",   # the LETTER line is not the intro
                    "Hi, I'm Tyler Youk, founding engineer at Utopia Models.",
                    INTRO.replace("Utopia Models", "Utopia")):
            def m(s, bad=bad): s["sections"][0]["lines"] = [bad]
            self.assertIn("E0", rules(pkg(m)), bad)

    def test_e11_close_line_present_missing_reworded(self):
        self.assertNotIn("E11", rules(pkg()))
        def missing(s): s["sections"][2]["lines"].pop()
        self.assertIn("E11", rules(pkg(missing)))
        def reworded(s): s["sections"][2]["lines"][-1] = CLOSE.replace("quick call", "short call")
        self.assertIn("E11", rules(pkg(reworded)))
        def not_last(s): s["sections"][2]["lines"].append("Each ticket keeps its own Zendesk log entry.")
        self.assertIn("E11", rules(pkg(not_last)))
        def twice(s): s["sections"][2]["lines"].insert(0, CLOSE)
        self.assertIn("E11", rules(pkg(twice)))

    def test_close_line_is_exempt_from_row_caps_but_nothing_else_is(self):
        self.assertEqual({x["rule"] for x in U.check(pkg()) if x["row"] and "perfect match" in x["row"]}, set())

    def test_e14_first_ai_row_must_name_their_job(self):   # #18869 item 2: no hook, straight into THEIR job
        def m(s): s["sections"][1]["lines"][0] = {"say": "Hi, I read your post about tickets today."}
        self.assertIn("E14", rules(pkg(m)))
        def m2(s): s["sections"][1]["lines"][0] = {"say": "Here is a vast galaxy of opportunity."}
        self.assertIn("E14", rules(pkg(m2)))

    def test_e13_ai_row_restating_the_intro_is_refused(self):
        for bad in ("I noticed your Zendesk ticket queue needs help,", "I'm Tyler Youk, and this is your Zendesk ticket queue.",
                    "So I made you a working triage queue and a software architecture diagram behind it."):
            def m(s, bad=bad): s["sections"][1]["lines"][0] = {"say": bad}
            self.assertIn("E13", rules(pkg(m)), bad)

    def test_e12_no_line_names_the_voice_as_ai(self):
        for bad in ("The rest of this video is my AI voice.", "This walkthrough is my AI voice, so you get it today.", "My cloned voice will show your Zendesk ticket queue."):
            def m(s, bad=bad): s["sections"][1]["lines"][0] = {"say": bad}
            self.assertIn("E12", rules(pkg(m)), bad)
        def intro(s): s["sections"][0]["lines"] = [INTRO + " The rest of this video is my AI voice."]
        self.assertIn("E12", rules(pkg(intro)))
        self.assertNotIn("E12", rules(pkg()))   # a post that says "AI engineer" is not the voice naming itself

    def test_e3_no_source(self):
        def m(s): s["sections"][1]["lines"][2].pop("source")
        self.assertIn("E3", rules(pkg(m)))

    def test_e3_bad_quote(self):
        def m(s): s["sections"][1]["lines"][2]["source"] = {"post": "made up quote not in the post"}
        self.assertIn("E3", rules(pkg(m)))

    def test_e3_number_needs_source(self):
        def m(s): s["sections"][1]["lines"][3] = "It cuts review time by 40 percent for your tickets."
        self.assertIn("E3", rules(pkg(m)))

    def test_e4_grade(self):
        def m(s): s["sections"][1]["lines"][3] = "Operational interoperability considerations necessitate comprehensive infrastructure rationalization."
        self.assertIn("E4", rules(pkg(m)))

    def test_e7_one_claim_per_sentence(self):
        def m(s): s["sections"][1]["lines"][3] = "Here's the Zendesk queue and every refund ticket is sorted and sent to Stripe and logged."
        self.assertIn("E7", rules(pkg(m)))

    def test_e8_a_row_that_fits_any_job_is_refused(self):
        def m(s): s["sections"][1]["lines"][3] = "It saves you time and it's easy to use."
        self.assertIn("E8", rules(pkg(m)))

    def test_e9_no_ui_label_list(self):
        def m(s): s["sections"][1]["lines"][3] = "You see Operations Command, Build Backlog, Integrations on the Zendesk page."
        self.assertIn("E9", rules(pkg(m)))

    def test_e10_beat_word_ranges_come_from_the_contract(self):
        def m(s): s["sections"][2]["lines"] = ["Zendesk tickets enter one queue."]
        self.assertIn("E10", rules(pkg(m)))

    def test_pending_slots_are_neither_pass_nor_crash(self):
        import script_rules
        self.assertEqual(script_rules.pending_slots(), {})   # v12 (fm:18825): every held slot is filled
        self.assertEqual(U.check(pkg()), [])

    def test_e6_no_question_no_ask_no_close(self):
        def q(s): s["sections"][2]["lines"].append("Would you like a short plan?")
        self.assertIn("E6", rules(pkg(q)))
        def ask(s): s["sections"][2]["lines"].append({"say": "Tell me more here.", "ask": True})
        self.assertIn("E6", rules(pkg(ask)))

    def test_e6_contractions_required(self):
        def m(s):
            for sec in s["sections"]:
                sec["lines"] = [(l if isinstance(l, dict) else l.replace("Here's", "Here is").replace("it's", "it is").replace("I'm", "I am")) for l in sec["lines"]]
        def m2(s):
            m(s)
            s["sections"][1]["lines"][3] = "Each refund goes to Stripe with one click for you."
        self.assertIn("E6", rules(pkg(m2)))

    def test_e6_duration(self):
        def m(s): s["sections"][1]["lines"] = s["sections"][1]["lines"][:1]; s["sections"][2]["lines"] = s["sections"][2]["lines"][-2:]
        self.assertTrue(any("need 45" in x["why"] for x in U.check(pkg(m))))

    def test_refusal_writes_nothing(self):
        def m(s): s["sections"][1]["lines"][2].pop("source")
        d = pkg(m)
        with self.assertRaises(U.Refused):
            gen_scripts.generate(d, upwork=True)
        self.assertFalse((d / "entire-script.md").exists())

    def test_cli_exit_nonzero(self):
        def m(s): s["sections"][1]["lines"][2].pop("source")
        r = subprocess.run([sys.executable, str(HERE / "gen_scripts.py"), str(pkg(m)), "--upwork"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertIn("REFUSED E3", r.stdout)


class Fixture9263(unittest.TestCase):
    """Acceptance: the 9263 post (job-post.txt, the only copy of the post in the repo) yields a script that passes the contract gate."""
    def test_9263_fixture_passes(self):
        self.assertEqual(U.check(HERE / "tests" / "fixtures" / "upwork-9263-e1e5"), [])


if __name__ == "__main__":
    unittest.main()

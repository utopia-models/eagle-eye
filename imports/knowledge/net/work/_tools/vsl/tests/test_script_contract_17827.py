"""knowledge#17827: the contract is the one source of the Upwork script rules; the author prompt and the gates are generated from it and a
change to the contract makes them move together (or this test fails). Also: the reviewer cannot crash on a str and blocks READY, and a READY
package that fails today's rules is demoted (package 4462)."""
import copy
import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(Path(__file__).parent))
WORK = HERE.parents[1]
os.environ.setdefault("ONESHOT_AUTO_DIR", tempfile.mkdtemp())
os.environ.setdefault("ONESHOT_PKG_ROOT", tempfile.mkdtemp())
import script_rules  # noqa: E402
import script_authoring as SA  # noqa: E402
import upwork_rules as U  # noqa: E402
import oneshot_auto as OA  # noqa: E402
import test_upwork_rules_17592 as T  # noqa: E402

PROMPTS = ["oneshot-auto-prompt.md", "oneshot-auto-prompt-copy.md", "oneshot-auto-prompt-terminal.md"]


def reload_with(contract_path):
    script_rules.CONTRACT = contract_path
    importlib.reload(U)
    importlib.reload(SA)


class Agree(unittest.TestCase):
    def tearDown(self):
        script_rules.CONTRACT = WORK / "vsl/contract/upwork.yaml"
        importlib.reload(U)
        importlib.reload(SA)

    def test_gate_constants_are_the_contracts(self):
        r = script_rules.rules()
        self.assertEqual((U.MAX_GRADE, U.WPS, (U.MIN_S, U.MAX_S)), (float(r["max_grade"]), r["words_per_s"], tuple(r["total_s"])))
        self.assertEqual((SA.MAX_ROW_WORDS, SA.MIN_ROW_WORDS, SA.FULL_FLOOR_WORDS), (r["max_row_words"], r["min_row_words"], r["floor_words_entire"]))

    def test_prompt_states_what_the_gates_enforce(self):
        r, p = script_rules.rules(), script_rules.prompt_rules()
        self.assertIn(r["close_line"], p)         # v12: the prompt carries the verbatim close line and the intro shape
        self.assertIn("I'm Tyler Youk with Utopia Models. I noticed your post for [role]", p)
        self.assertNotIn("I recorded a short video", p)
        self.assertIn(f"at most {r['max_sentence_words']} words", p)
        self.assertIn(f"app {r['beat_words']['app'][0]}-{r['beat_words']['app'][1]}", p)
        self.assertIn(r["first_ai_line"], p)
        self.assertIn(f"{r['min_row_words']} to {r['max_row_words']} words", p)
        self.assertIn("contractions are required", p)
        self.assertEqual(r["contractions"], "required")   # gate and prompt read the same key
        self.assertNotIn("I am never", p)
        self.assertNotIn("founding engineer", p)

    def test_hook_is_the_first_ai_line_and_the_prompt_states_its_window(self):
        r = script_rules.rules()
        self.assertEqual(r["hook"]["line"], "first_ai_line")
        self.assertTrue(r["hook"]["bespoke"])
        lo, hi = r["hook"]["window_s"]
        self.assertIn(f"within {lo} to {hi} seconds", script_rules.prompt_rules())

    def test_every_prompt_file_is_generated_not_hand_copied(self):
        for f in PROMPTS:
            t = (WORK / "vsl" / f).read_text()
            self.assertIn("{RULES}", t, f)
            self.assertIn("{SOURCES}", t, f)
            for dead in ("I am\" never", "founding engineer", "no possessive or contraction apostrophes", "at most 15 words"):
                self.assertNotIn(dead, t, f"{f} still hand-states: {dead}")

    def test_rendered_copy_prompt_carries_rules_sources_and_the_fazio_line(self):
        out = OA.render_prompt({"mvp_type": "copy", "text": "JOB", "slug": "s"}, "/w")
        self.assertIn("This is a perfect match for what you posted.", out)
        self.assertIn("I noticed", out)
        for src in ("S7", "S18", "S10", "Polymarket", "6495", "7536"):
            self.assertIn(src, out)
        self.assertNotIn("{RULES}", out)
        self.assertNotIn("{SOURCES}", out)

    def test_changing_the_contract_moves_prompt_and_gates_together(self):
        c = yaml.safe_load((WORK / "vsl/contract/upwork.yaml").read_text())
        c["script"]["max_row_words"] = 9
        c["script"]["contractions"] = "none"
        f = Path(tempfile.mkdtemp()) / "upwork.yaml"
        f.write_text(yaml.safe_dump(c))
        reload_with(f)
        self.assertIn("6 to 9 words", script_rules.prompt_rules())
        self.assertIn("no contractions", script_rules.prompt_rules())
        self.assertEqual(U.MAX_GRADE, 6.0)
        d = T.pkg()
        why = " ".join(x["why"] for x in U.check(d))
        self.assertIn("max 9", why)                       # the gate follows the contract to 9
        self.assertEqual(SA.MAX_ROW_WORDS, 9)

    def test_letter_lines_and_the_filled_slots(self):
        r = script_rules.rules()
        self.assertEqual(r["letter_line1"], "Hi {name}, I recorded a short video for you (attached) that walks through your {ask} and a working version I built for it.")
        self.assertEqual(r["letter_line2"], "so that you can get {outcome}")
        self.assertEqual(r["letter_close"], "Happy to answer any questions.")
        self.assertEqual(script_rules.pending_slots(), {})
        self.assertEqual(r["stop_rule"], "close_line")
        self.assertNotIn("stop_rule_pending", script_rules.contract()["script"])
        self.assertEqual(r["intro_opener"], {"per_job": "intro.full", "library": "intro.auto"})
        self.assertTrue(r["close_line"].startswith("This is a perfect match for what you posted. Reply to my proposal"))

    def test_letter_generator_writes_l1_l2_close(self):
        lines = script_rules.letter("Dana", "ticket triage", "faster answers").split("\n")
        self.assertEqual(lines, ["Hi Dana, I recorded a short video for you (attached) that walks through your ticket triage and a working version I built for it.",
                                 "so that you can get faster answers", "Happy to answer any questions."])
        self.assertTrue(script_rules.letter(None, "x", "y").startswith("Hi, I recorded"))   # no name in post.md: "Hi,"

    def test_intro_name_and_no_name(self):
        self.assertTrue(script_rules.intro_full("Dana", "a role", "app", "an outcome").startswith("Hi Dana, I'm Tyler Youk with Utopia Models."))
        self.assertTrue(script_rules.intro_full(None, "a role", "app", "an outcome").startswith("Hi, I'm Tyler Youk with Utopia Models."))
        self.assertNotIn("[", script_rules.intro_auto("support"))
        self.assertNotIn("{", script_rules.intro_full(None, "a role", "app", "an outcome"))

    def test_length_and_beat_words_are_contract_values(self):
        c = yaml.safe_load((WORK / "vsl/contract/upwork.yaml").read_text())
        self.assertEqual(c["length"]["total"], [45, 70])   # Fazio S18:30 (fm:18807)
        self.assertEqual(set(c["script"]["beat_words"]), {"hook", "app", "diagram"})
        self.assertEqual(U.R["beat_words"], c["script"]["beat_words"])

    def test_a_held_slot_is_pending_not_enforced(self):
        c = yaml.safe_load((WORK / "vsl/contract/upwork.yaml").read_text())
        c["script"]["close_line"] = {"pending": "fm:1"}
        c["intro"]["full"] = {"pending": "fm:1"}
        f = Path(tempfile.mkdtemp()) / "upwork.yaml"
        f.write_text(yaml.safe_dump(c))
        reload_with(f)
        self.assertEqual(set(script_rules.pending_slots()), {"script.close_line", "intro.full"})
        self.assertNotIn("E11", {x["rule"] for x in U.check(T.pkg())})

    def test_retired_unsourced_lines_are_gone(self):
        self.assertIsNone(script_rules.rules()["self_title"])
        ex = (WORK / "vsl/oneshot-auto-examples/script-source.yaml").read_text()
        self.assertNotIn("founding engineer", ex)

    def test_sources_pack_cites_real_files(self):
        t = script_rules.sources_text()
        for rel in ("linked-google/1URDbBlASf95Z2o9Hu23_AtNQq5555CzNJJqw6IO0yBs.md", "linked-google/1ae7bad2IVGzvUFtE5D6bM4fiQ6iyQWyKTJLXBQ770V0.md", "linked-gamma/auq3p2y0tdcqffq.md"):
            self.assertIn(rel, t)
            self.assertTrue((WORK / "offers/fazio/text" / rel).is_file(), rel)
        self.assertTrue((WORK / "upwork/letters/2026-11-09-polymarket-mm-bot.txt").is_file())
        self.assertTrue((WORK / "vsl/scripts/6495-v1.md").is_file())


class Reviewer(unittest.TestCase):
    def test_a_str_item_does_not_crash(self):
        rows = SA.parse_review('["Row one is generic", {"row": "r2", "why": "wrong post"}]')
        self.assertEqual([r["row"] for r in rows], ["Row one is generic", "r2"])

    def test_unparseable_reply_raises_so_the_caller_blocks(self):
        with self.assertRaises(ValueError):
            SA.parse_review("looks fine to me")
        with self.assertRaises(ValueError):
            SA.parse_review("[1, 2]")

    def test_script_check_blocks_on_a_reviewer_crash_and_on_a_failing_review(self):
        d = T.pkg()
        j = {"slug": "x", "text": T.POST}
        (d / "post.md").write_text(T.POST)
        def boom(p, t): raise RuntimeError("'str' object has no attribute 'get'")
        r = OA.script_check_loop(j, d, {}, {"review": boom})
        # the deterministic check may already fail (no take files); either way READY is blocked and a reason is named
        self.assertFalse(r["pass"])
        self.assertTrue(r["failing_rows"])

    def test_reviewer_crash_is_named_when_everything_else_passes(self):
        d = T.pkg()
        import gen_scripts
        gen_scripts.generate(d)
        (d / "post.md").write_text(T.POST)
        import script_authoring
        orig = script_authoring.check_package
        script_authoring.check_package = lambda *a, **k: []
        try:
            def boom(p, t): raise RuntimeError("boom")
            r = OA.script_check_loop({"slug": "x", "text": T.POST}, d, {}, {"review": boom})
            self.assertFalse(r["pass"])
            self.assertIn("reviewer did not run", r["failing_rows"][0]["why"])
            ok = OA.script_check_loop({"slug": "x", "text": T.POST}, d, {}, {"review": lambda p, t: []})
            self.assertTrue(ok["pass"])
        finally:
            script_authoring.check_package = orig


class Package4462(unittest.TestCase):
    def test_a_ready_package_that_fails_e1_is_demoted_with_stamps_cleared(self):
        slug = "up-4462"
        pkg = OA.PKG_ROOT / slug
        pkg.mkdir(parents=True, exist_ok=True)
        s = T.src()
        s["sections"][1]["lines"][0] = {"say": "I read your Senior AI/ML Engineer post."}   # the live 4462 shape: no "I noticed"
        (pkg / "script-source.yaml").write_text(yaml.safe_dump(s))
        (pkg / "post.md").write_text(T.POST)
        j = {"slug": slug, "state": "ready", "text": T.POST, "t": {"scripts_gates": "2026-11-23T10:00:00Z", "ready": "2026-11-23T10:05:00Z"}}
        OA.save_job(j)
        self.assertTrue(OA.recheck_ready(j))
        j2 = OA.load_job(slug)
        self.assertEqual(j2["state"], "blocked")
        self.assertTrue("E14" in j2["blocked_by"] or "E8" in j2["blocked_by"])   # #18869: the S7 hook (E1) is gone; the first AI row must name their job (E14)
        self.assertNotIn("ready", j2["t"])
        self.assertNotIn("scripts_gates", j2["t"])

    def test_a_passing_ready_package_is_left_alone(self):
        slug = "up-ok"
        pkg = OA.PKG_ROOT / slug
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "script-source.yaml").write_text(yaml.safe_dump(T.src()))
        (pkg / "post.md").write_text(T.POST)
        j = {"slug": slug, "state": "ready", "text": T.POST, "t": {"ready": "x"}}
        OA.save_job(j)
        self.assertFalse(OA.recheck_ready(j))
        self.assertEqual(OA.load_job(slug)["state"], "ready")


class Regen(unittest.TestCase):
    def _pkg(self, slug, bad=False):
        pkg = OA.PKG_ROOT / slug
        pkg.mkdir(parents=True, exist_ok=True)
        s = T.src()
        if bad:
            s["sections"][1]["lines"][3] = "It saves you time and it's easy to use."
        (pkg / "script-source.yaml").write_text(yaml.safe_dump(s))
        (pkg / "post.md").write_text(T.POST)
        return pkg

    def test_regenerates_failing_rows_then_is_idempotent(self):
        pkg = self._pkg("up-regen-1", bad=True)
        def writer(p, t, failing):
            self.assertIn("E8", failing[0]["why"])
            (Path(p) / "script-source.yaml").write_text(yaml.safe_dump(T.src()))
        OA.save_job({"slug": "up-regen-1", "state": "ready", "text": T.POST, "t": {"ready": "x"}})
        r = OA.regen(pkg, {"write": writer})
        self.assertEqual(r["action"], "regenerated")
        self.assertTrue((pkg / "entire-script.md").is_file())
        before = (pkg / "entire-script.md").read_bytes()
        r2 = OA.regen(pkg, {"write": lambda *a: self.fail("writer must not run on a passing package")})
        self.assertEqual(r2["action"], "noop")
        self.assertEqual((pkg / "entire-script.md").read_bytes(), before)

    def test_refuses_a_recorded_or_sent_package(self):
        for stage in ("recorded", "vsl_sent"):
            slug = f"up-regen-{stage}"
            pkg = self._pkg(slug, bad=True)
            OA.save_job({"slug": slug, "state": "ready", "text": T.POST, "t": {stage: "2026-11-24T01:00:00Z"}})
            src_before = (pkg / "script-source.yaml").read_bytes()
            r = OA.regen(pkg, {"write": lambda *a: self.fail("must not rewrite")})
            self.assertEqual(r["action"], "refused")
            self.assertIn(stage, r["why"])
            self.assertEqual((pkg / "script-source.yaml").read_bytes(), src_before)

    def test_refuses_when_the_writer_cannot_fix_it(self):
        pkg = self._pkg("up-regen-stuck", bad=True)
        r = OA.regen(pkg, {"write": lambda *a: None})
        self.assertEqual(r["action"], "refused")
        self.assertTrue(r["failing_rows"])


if __name__ == "__main__":
    unittest.main()

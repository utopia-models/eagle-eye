"""E6's row-word cap is for a row Tyler reads aloud; the AI voice's S7 hook (E1) is exempt (0062 regen, 2026-11-24): capping
it squeezed the blanks to "this" and E1 failed. Every other row is still capped."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_upwork_rules_17592 import U, pkg  # noqa: E402

S7_ONE_ROW = ("I noticed your team loses hours each day sorting tickets by hand, so I made you a Zendesk queue that sorts them, "
              "so that you can answer faster.")


def one_row_s7(s):
    app = s["sections"][1]["lines"]
    app[0:3] = [{"say": S7_ONE_ROW, "outcome": True, "source": {"post": "Our team loses hours each day sorting tickets by hand"}}]


def test_a_one_row_s7_hook_over_14_words_passes_e6():
    rows = [x for x in U.check(pkg(one_row_s7)) if x["rule"] == "E6" and x["row"] and x["row"].startswith("I noticed")]
    assert rows == []


def test_any_other_long_row_is_still_capped():
    def long_row(s):
        one_row_s7(s)
        s["sections"][1]["lines"].append("You see every single refund and every chargeback ticket sorted into its own lane right away today.")
    rows = [x for x in U.check(pkg(long_row)) if x["rule"] == "E6" and x["row"] and x["row"].startswith("You see every")]
    assert rows and "max" in rows[0]["why"]


def test_the_s7_hook_is_exempt_from_e4_its_noticed_blank_is_the_posts_own_words():
    def hard_s7(s):
        s["sections"][1]["lines"][0:3] = [{"say": "I noticed your organization's procurement solicitation evaluation methodology, so I made you "
                                           "a prioritization dashboard, so that you can answer faster.", "outcome": True,
                                           "source": {"post": "Our team loses hours each day sorting tickets by hand"}}]
    rows = [x for x in U.check(pkg(hard_s7)) if x["rule"] == "E4" and x["row"] and x["row"].startswith("I noticed")]
    assert rows == []


def test_any_other_hard_row_still_fails_e4():
    def hard_row(s):
        one_row_s7(s)
        s["sections"][1]["lines"].append("Organizational procurement methodology prioritization evaluation.")
    rows = [x for x in U.check(pkg(hard_row)) if x["rule"] == "E4" and x["row"] and x["row"].startswith("Organizational")]
    assert rows


def test_an_s7_line_past_the_hook_ceiling_fails_e1_so_regen_authors_a_new_triple():
    # 2046 regen 2026-11-24: an 81-word S7 line passed E1 and held the video at 94 s, because only E1 makes regen re-author it
    def long_s7(s):
        s["sections"][1]["lines"][0:3] = [{"say": "I noticed your team loses hours each day sorting tickets by hand, so I made you a first version of your "
                                           "Zendesk queue that pulls in every ticket and its attachments and sorts them by team and by urgency, so that you "
                                           "can answer faster and see right away which tickets need a person.", "outcome": True,
                                           "source": {"post": "Our team loses hours each day sorting tickets by hand"}}]
    rows = [x for x in U.check(pkg(long_s7)) if x["rule"] == "E1" and "the hook is" in x["why"]]
    assert rows


def test_rendered_rows_fit_the_prompter_and_the_close_line_stays_whole_in_the_source():
    import gen_scripts, script_rules
    src = {"handoff": "x", "sections": [{"heading": "Intro", "cue": "c", "lines": ["Hi, I'm Tyler Youk with Utopia Models. I noticed your post for a "
            "developer, so I made you a working app and a software architecture diagram behind it."]},
           {"heading": "D", "cue": "c", "lines": [script_rules.rules()["close_line"]]}]}
    out = [l for l in gen_scripts.render(src, "entire").splitlines() if l and not l.startswith(("##", "[browser]"))]
    assert all(len(l.split()) <= script_rules.rules()["max_row_words"] for l in out), out
    assert " ".join(out).endswith(script_rules.rules()["close_line"])


def test_a_cut_close_line_is_restored_verbatim():
    import script_rules
    src = {"sections": [{"lines": ["a"]}, {"lines": ["x", "This is a perfect match for what you posted. Reply to my proposal."]}]}
    assert U.fix_close(src) and src["sections"][-1]["lines"][-1] == script_rules.rules()["close_line"]


def test_a_post_ending_on_a_details_line_or_list_item_is_complete():
    import post_integrity as PI
    body = "We need a Django backend developer to build our booking API and its admin screens for clinics. " * 15
    assert PI.post_complete(body + "\nDuration: More than 6 months") == []
    assert PI.post_complete(body + "\n- Onboarding and your first project") == []
    assert PI.post_complete(body + "\nand then we") != []


def test_contract_rows_are_the_intro_card_and_the_close_line_halves():
    import script_rules
    intro = script_rules.split_rows(script_rules.intro_full("Ana", "a Django developer", "booking API", "bookings that never double up"))
    close = script_rules.split_rows(script_rules.rules()["close_line"], 14)
    secs = [{"heading": "Intro", "rows": intro}, {"heading": "App", "rows": ["You open bookings and see each clinic."] + close}]
    own = script_rules.contract_rows(secs)
    assert set(intro) <= own and set(close) <= own and "You open bookings and see each clinic." not in own


def test_reviewer_findings_on_contract_rows_and_headings_are_dropped():
    import script_authoring as SA
    own = ["Hi, I'm Tyler Youk with Utopia Models.", "The rest of this video is my AI voice."]
    fails = [{"row": "Hi, I'm Tyler Youk with Utopia Models.", "why": "generic"}, {"row": "## [Tyler] Intro (19 s)", "why": "x"},
             {"row": "The rest of this video is my AI voice.", "why": "about us"}, {"row": "I click Conversion Batches.", "why": "tour"}]
    assert [x["row"] for x in SA.drop_fixed(fails, own)] == ["I click Conversion Batches."]

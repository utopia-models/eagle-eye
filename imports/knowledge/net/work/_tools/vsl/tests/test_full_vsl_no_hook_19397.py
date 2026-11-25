"""fm:19397 (Tyler-adopted 2026-11-24): a FULL VSL drops the AI-voice hook; the 'noticed' blank reads as a phrase; reviewer findings are rewritten."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import upwork_rules as U  # noqa: E402
import s7_hook as H  # noqa: E402

HOOK = "I noticed your team loses hours each day sorting tickets by hand, so I made you a Zendesk queue, so that you can answer faster."


def src(slots):
    return {"intro_slots": slots, "sections": [{"lines": ["{intro}"]}, {"lines": [HOOK, "You open the queue and see every ticket."]}]}


def test_hook_follows_only_the_library_intro():
    assert not U.hook_applies(src({"role": "a dev", "thing": "queue", "outcome": "speed"}))
    assert U.hook_applies(src({"cluster": "Zendesk support"}))


def test_full_vsl_hook_row_is_stripped_and_auto_keeps_it():
    full = src({"role": "a dev", "thing": "queue", "outcome": "speed"})
    assert U.strip_hook(full) and full["sections"][1]["lines"] == ["You open the queue and see every ticket."]
    auto = src({"cluster": "Zendesk support"})
    assert not U.strip_hook(auto) and auto["sections"][1]["lines"][0] == HOOK


def test_noticed_must_read_as_a_phrase_not_a_raw_fragment():
    post = "We need help scale our core systems and keep tenants apart."
    bad = {"noticed": "help scale our core systems", "made": "a tenant-safe backend", "outcome": "grow without outages"}
    good = dict(bad, noticed="your team needs help scale our core systems")
    assert any("phrase about them" in w for w in H.validate(bad, post))
    assert not any("phrase about them" in w for w in H.validate(good, post))

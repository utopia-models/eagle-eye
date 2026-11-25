"""knowledge#18249: a failing gate is an advisory, never a stop; the sender holds only on closed/private or a missing MP4."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import intro_sender  # noqa: E402
import oneshot_auto as O  # noqa: E402


def test_live_config_is_advisory():
    assert O.gates_advisory(O.cfg()) is True
    assert O.gates_advisory({"autosend": {}}) is False


def test_advise_replaces_per_stage():
    j = {}
    O.advise(j, "script_check", "a")
    O.advise(j, "script_check", "b")
    O.advise(j, "rehearsal", "c")
    assert [(a["stage"], a["why"]) for a in j["advisories"]] == [("script_check", "b"), ("rehearsal", "c")]


def test_sender_selftest():
    assert intro_sender.selftest()

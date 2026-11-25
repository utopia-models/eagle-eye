"""knowledge#18233/#18574: a fixable script-gate refusal (E0/E3/E4/E8) goes back to the author worker (max 2 re-runs) before the job blocks."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import oneshot_auto as O  # noqa: E402
import upwork_rules  # noqa: E402

E3 = "E3: result row 6: no source (source: {post: '<quote>'} or {artifact: '<file>'})"


def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(O, "STATE", tmp_path / "state")
    monkeypatch.setattr(O, "PKG_ROOT", tmp_path / "pkg")
    monkeypatch.setattr(O, "push_eagle", lambda j: None)
    monkeypatch.setattr(O, "save_job", lambda j: None)
    monkeypatch.setattr(O, "meter_stage", lambda j, s: None)
    (tmp_path / "state").mkdir()
    pkg = tmp_path / "pkg" / "up-x-1"
    pkg.mkdir(parents=True)
    return pkg


def job():
    return {"slug": "up-x-1", "text": "post", "t": {}, "mvp_type": "copy"}


def steps_for(calls, fix_on):
    def author(j, w, c):
        calls.append(j.get("_repair"))
        for f in ("architecture.yaml", "script-source.yaml", "copied_from.json"):
            (w / f).write_text("{}")
    return author


def test_fixed_on_retry(tmp_path, monkeypatch):
    pkg = setup(tmp_path, monkeypatch)
    calls, j = [], job()
    author = steps_for(calls, 1)

    def gates(j, p):
        if not calls:
            raise upwork_rules.Refused([{"rule": "E3", "row": 6, "why": E3[4:]}])
        return {"gates": [], "ready": True, "blocking": []}
    steps = {"author": author, "gates": gates}
    out = O.with_author_repair(j, pkg, {}, steps, lambda: steps["gates"](j, pkg), lambda d: "")
    assert out["ready"] and len(calls) == 1
    assert "E3" in calls[0] and "_repair" not in j
    assert [a["stage"] for a in j["attempts"]] == ["author_repair"]


def test_never_fixed_blocks_after_exactly_two_repairs(tmp_path, monkeypatch):
    pkg = setup(tmp_path, monkeypatch)
    calls, j = [], job()
    steps = {"author": steps_for(calls, 0)}
    bad = {"pass": False, "failing_rows": [{"file": "script-source.yaml", "row": 6, "why": E3}]}
    n = []

    def sc():
        n.append(1)
        return bad
    res = O.with_author_repair(j, pkg, {}, steps, sc, lambda d: "" if d["pass"] else "; ".join(x["why"] for x in d["failing_rows"]))
    assert res is bad and len(calls) == 2 and len(n) == 3          # first run + one re-check per repair
    assert len(j["attempts"]) == 2 and all(a["stage"] == "author_repair" and "E3" in a["error"] for a in j["attempts"])


def test_unfixable_not_retried(tmp_path, monkeypatch):
    pkg = setup(tmp_path, monkeypatch)
    calls, j = [], job()
    steps = {"author": steps_for(calls, 0)}
    bad = {"pass": False, "failing_rows": [{"file": "x", "row": None, "why": "script_check: input: post.md missing"}]}
    res = O.with_author_repair(j, pkg, {}, steps, lambda: bad, lambda d: d["failing_rows"][0]["why"])
    assert res is bad and calls == [] and "attempts" not in j
    assert not O.repairable("E4: input: post.md missing") and O.repairable("E8: would fit a different job") and not O.repairable("49 words, floor 240")


def test_whole_build_blocks_with_last_message(tmp_path, monkeypatch):
    pkg = setup(tmp_path, monkeypatch)
    calls = []
    j = job()
    monkeypatch.setattr(O, "load_job", lambda slug: j)
    good = {"author": steps_for(calls, 0), "app": lambda j, w: True, "diagram": lambda j, w: None,
            "gates": lambda j, w: (_ for _ in ()).throw(upwork_rules.Refused([{"rule": "E3", "row": 6, "why": "result row 6: no source"}])),
            "script_check": lambda j, w, c: {"pass": True, "failing_rows": []}, "rehearsal": lambda j, w, c: {"pass": True},
            "deliver": lambda s, p, c: {}}
    out = O._run_job("up-x-1", good, {"rehearsal": {"required": False}})
    assert out["state"] == "blocked" and "no source" in out["blocked_by"]
    assert len(calls) == 3 and calls[0] is None and all(calls[1:])   # initial author + exactly 2 repairs


E10 = "E10: app section is 43 words, beat range 50-80"


def test_e10_fixed_on_retry_and_prompt_has_numbers(tmp_path, monkeypatch):
    pkg = setup(tmp_path, monkeypatch)
    calls, j = [], job()
    seen = []

    def author(j, w, c):
        seen.append(O.render_prompt(dict(j, mvp_type="copy"), w))
        steps_for(calls, 1)(j, w, c)

    def gates(j, p):
        if not calls:
            raise upwork_rules.Refused([{"rule": "E10", "row": None, "why": "app section is 43 words, beat range 50-80"}])
        return {"ready": True}
    steps = {"author": author, "gates": gates}
    assert O.with_author_repair(j, pkg, {}, steps, lambda: gates(j, pkg), lambda d: "")["ready"]
    assert "43 words, beat range 50-80" in seen[0] and len(calls) == 1


def test_e10_never_fixed_blocks_after_two(tmp_path, monkeypatch):
    pkg = setup(tmp_path, monkeypatch)
    calls, j = [], job()
    steps = {"author": steps_for(calls, 0)}

    def gates():
        raise upwork_rules.Refused([{"rule": "E10", "row": None, "why": "app section is 43 words, beat range 50-80"}])
    try:
        O.with_author_repair(j, pkg, {}, steps, gates, lambda d: "")
        assert False
    except upwork_rules.Refused as e:
        assert E10 in str(e)
    assert len(calls) == 2 and len(j["attempts"]) == 2


def test_every_enforce_rule_classified():
    for r in ("E0", "E1", "E3", "E4", "E6", "E7", "E8", "E9", "E10", "E11"):
        assert O.repairable(f"{r}: x")
    assert not O.repairable("input: post.md missing: every claim") and not O.repairable("build exceeded 10 min and was killed") and not O.repairable("KeyError: 'say'")

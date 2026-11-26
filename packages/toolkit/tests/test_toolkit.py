import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

TOOLKIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLKIT))
import kit  # noqa: E402
import onboard  # noqa: E402
import quote_check  # noqa: E402
import rails  # noqa: E402
import systems  # noqa: E402

sys.path.insert(0, str(kit.REPO / "library"))
import library_index  # noqa: E402

CATALOG = systems.load_all()


def test_both_one_shots_exist_and_cite_kit_ids():
    for name in ("upwork-oneshot", "founder-oneshot"):
        assert not systems.problems(name, CATALOG[name])
        assert any(ref.startswith("kit:") for ref in systems.cited(CATALOG[name]))


def test_every_quote_is_in_its_cited_file():
    count, failures = quote_check.check()
    assert failures == [] and count > 0


@pytest.mark.parametrize("quote", [
    {"cite": "lib:playbooks/upwork-oneshot", "text": "a line nobody wrote"},
    {"cite": "lib:playbooks/upwork-oneshot", "text": ""},
    {"cite": "lib:playbooks/founder-oneshot", "text": "The offer is one thing."},   # real line, uncited file
])
def test_a_bad_quote_fails(tmp_path, quote):
    folder = tmp_path / "upwork-oneshot"
    folder.mkdir()
    (folder / "system.json").write_text(json.dumps(CATALOG["upwork-oneshot"] | {"quotes": [quote]}))
    assert quote_check.check(tmp_path)[1]


@pytest.mark.parametrize("ref", ["kit:nope", "lib:../LICENSE", "kit:../playbooks/upwork-oneshot", "playbooks/x"])
def test_ids_that_name_nothing_or_escape_are_refused(ref):
    with pytest.raises(KeyError):
        kit.resolve(ref)


def test_ee_kit_points_at_another_checkout(tmp_path, monkeypatch):
    (tmp_path / "kit").mkdir()
    (tmp_path / "kit" / "a.md").write_text("pinned copy")
    monkeypatch.setenv("EE_KIT", str(tmp_path))
    assert kit.read("kit:a") == "pinned copy"


def test_reader_takes_only_named_files_and_drops_secrets(tmp_path):
    (tmp_path / "README.md").write_text("We build dashboards.\nAPI_KEY=abc123\n")
    (tmp_path / "customers.csv").write_text("a,b")
    (tmp_path / ".env").write_text("X=1")
    (tmp_path / "about.md").symlink_to(tmp_path / ".env")
    assert onboard.read_business(tmp_path) == [("README.md", "We build dashboards.")]


def fake_ai(basis):
    def run(prompt):
        if prompt.startswith("Work out"):
            return json.dumps({"business": "dashboards", "system": "upwork-oneshot", "basis": basis})
        return "draft"
    return run


@pytest.mark.parametrize("flag,ai,basis,by", [
    ("hormozi", "max", "hormozi", "you"), (None, "max", "max", "ai"), (None, "bogus", "ours", "default")])
def test_basis_is_yours_then_the_ais_then_ours(flag, ai, basis, by):
    p = onboard.infer([("README.md", "x")], CATALOG, basis=flag, run=fake_ai(ai))
    assert (p["basis"], p["basis_chosen_by"]) == (basis, by)


def test_a_bad_ai_answer_is_retried_once():
    answers = iter(['{"business": "cut off', 'Sure: {"system": "upwork-oneshot"} done {'])
    assert onboard.infer([("README.md", "x")], CATALOG, run=lambda _: next(answers))["system"] == "upwork-oneshot"


def test_run_drafts_what_it_can_and_holds_the_send(tmp_path):
    system = CATALOG["upwork-oneshot"]
    profile = onboard.infer([("README.md", "x")], CATALOG, run=fake_ai("ours"))
    rows = onboard.run_system(system, profile, tmp_path, {}, run=fake_ai("ours"), say=lambda _: None)
    state = {r["stage"]: r["state"] for r in rows}
    assert state == {"offer": "ready", "targets": "ready", "demo-plan": "waiting", "script": "waiting",
                     "letter": "waiting", "send": "held"}
    lane = json.loads((tmp_path / "feed.json").read_text())["hunts"]["job_boards"]
    assert lane["sent"] is None and lane["status"] == "empty" and "no sender" in lane["reason"]


def test_a_broken_rail_holds(tmp_path):
    (tmp_path / "rails").mkdir()
    (tmp_path / "rails" / "x.py").write_text("raise ValueError('boom')")
    assert "rail failed" in rails.holds("s", "send", config=tmp_path)[0]


def test_nothing_to_read_runs_nothing(tmp_path):
    assert onboard.main(["--dir", str(tmp_path), "--data", str(tmp_path / "live")]) == 1
    assert not (tmp_path / "live").exists()


def test_library_search_is_fts5_and_finds_the_kit():
    hits = library_index.search(library_index.load(kit.REPO / "library"), "value equation", 20)
    assert any(h["path"].startswith("kit/") for h in hits)
    assert library_index.search(library_index.load(kit.REPO / "library"), "zzzzqqq") == []


def test_public_tree_has_no_personal_email_or_member_link():
    files = subprocess.run(["git", "ls-files"], cwd=kit.REPO, capture_output=True, text=True, check=True).stdout.split("\n")
    email = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}")
    allowed = re.compile(r"@example\.|\.example\b|noreply@|^(hello|privacy)@eagleeye\.sh")
    member = re.compile(r"https?://learn\.clientascension\.com|skool\.com/[^\s/)]+/classroom")
    bad = []
    for name in filter(None, files):
        if name.startswith(("site/vendor/", "assets/")) or "/vendor/" in name or name.endswith("package-lock.json"):
            continue
        p = kit.REPO / name
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
        bad += [f"{name}: email" for m in email.findall(text) if not allowed.search(m)]
        bad += [f"{name}: member link" for _ in member.findall(text)]
    assert bad == []

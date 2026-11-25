#!/usr/bin/env python3
"""script_authoring.py: the authored-stage script check and the writer/reviewer loop (knowledge#17210, axis D).
Tyler 11-22: 9263's script was ~49 s and generic. Nothing self-reports ready: `run_loop` writes <pkg>/script-check.json = {pass, loops, failing_rows}
and the package is not READY unless it passes. Failing rows go back to the writer, at most MAX_LOOPS times.
Mechanical rules (check_package):
  floor     Full (entire-script.md): >= FULL_FLOOR_WORDS spoken words (180 words); Intro (intro-script.md): the intro window
            (contract intro max_words) for the [Tyler] Intro, and the body (AI voice) rows >= BODY_FLOOR_WORDS
  specific  every app/diagram row must carry a term only THIS job has (a content word from the job post or the package's own labels not
            found in GENERIC_VOCAB); a row that could be pasted into another job fails
  banned    no 'Agent Chief', 'Agent Upwork', '24-7 agents' lines
  spoken    rows are 6-14 words; Tyler's rows use contractions (I'm, it's) and at least one is present per file (knowledge#17441 supersedes the 11-18 no-contractions rule)
Reviewer pass: agent fleet-doctrine:copy-reviewer against the job post (`review`, injectable); writer pass: write-as-tyler skill (`write`, injectable).
Neither check blocks Tyler from recording a package he chooses."""
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

import script_rules   # the contract's script: block is the one source of every number below (knowledge#17827)

FULL_FLOOR_WORDS = script_rules.rules()["floor_words_entire"]   # Tyler 2026-11-22 22:55 / knowledge#17441: 240 padded the script; ~180 words is 90-100 s at his pace
_R = script_rules.rules()
MAX_ROW_WORDS = _R["max_row_words"]
MIN_ROW_WORDS = _R["min_row_words"]
BODY_FLOOR_WORDS = script_rules.rules()["body_floor_words"]
MAX_LOOPS = 5
BANNED = [r"\bagent\s+(?:chief|upwork)\b", r"\b24\s*[-/ ]?\s*7\s+agents?\b", r"\b24\s*[-/ ]?\s*7\b.*\bagents?\b"]
CONTRACTION = re.compile(r"\b\w+['’](?:m|ll|ve|re|d)\b|\bI['’]m\b", re.I)
STOP = set("""a an and are as at be by for from has have i in is it its me my of on or our so that the their them then there this to up we with you your
am will can do does did not no yes into over than too very just also here now what when which who how why each every one two three four more most
see show shows showing look looks click clicks open opens next first last then tab page screen app diagram voice agent walk walks through""".split())
GENERIC_VOCAB = set("""workflow workflows automation automate automated system systems process processes data tool tools dashboard dashboards pipeline pipelines
build built builds working work works model models queue queues step steps task tasks report reports result results business team client customer
customers request requests approval approvals review reviews log logs track tracks tracking flow flows save saves saved time cost costs""".split())


def words(t):
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9'’-]*", t)


def sections(text):
    secs, cur = [], None
    for ln in text.splitlines():
        m = re.match(r"^## \[(Tyler|AI voice)\] (.+?)(?: \(\d+ s\))?$", ln)
        if m:
            cur = {"tag": m.group(1), "heading": m.group(2), "rows": []}
            secs.append(cur)
        elif cur is not None and ln.strip() and not ln.startswith("[browser]"):
            cur["rows"].append(ln.strip())
    return secs


def job_terms(job_text, pkg):
    """Terms specific to this job: content words of the post and of the package's own labels, minus generic vocabulary."""
    src = job_text
    for f in ("architecture.yaml", "config.json", "script-source.yaml"):
        p = Path(pkg) / f
        if p.is_file() and f != "script-source.yaml":
            src += " " + p.read_text()
    out = {w.lower() for w in words(src) if len(w) > 3}
    return out - STOP - GENERIC_VOCAB


def row_is_specific(row, terms):
    """A row is specific when it carries a term only this job has (post or package label, not generic vocabulary) or a number."""
    return bool({w.lower() for w in words(row)} & terms) or bool(re.search(r"\d", row))


def check_package(pkg, job_text, intro_max_words=None):
    """-> list of {file, row, why}; empty = pass. A `row` of None is a whole-file failure."""
    pkg = Path(pkg)
    fails = []
    terms = job_terms(job_text, pkg)
    import post_integrity   # knowledge#17487: gates 1-3 (complete post, seeded data quoted from it, claims quoted from it)
    post_file = pkg / "post.md"
    post = post_file.read_text() if post_file.is_file() else job_text
    if post_file.is_file() and post.strip() != (job_text or "").strip():
        fails.append({"file": "post.md", "row": None, "why": "the job record's text is not the hand-read post.md"})
    for why in (post_integrity.post_complete(post) if post_file.is_file() else []):   # no post.md: intake already refused a truncated feed excerpt
        fails.append({"file": "post.md", "row": None, "why": why})
    seed = pkg / "seed-sources.json"
    if seed.is_file():
        for why in post_integrity.seeded_reasons(json.loads(seed.read_text()), post):
            fails.append({"file": "seed-sources.json", "row": None, "why": why})
    cues_f = pkg / "cues.md"
    for fname, take in (("entire-script.md", "entire"), ("intro-script.md", "intro")):
        f = pkg / fname
        if not f.is_file():
            fails.append({"file": fname, "row": None, "why": "missing"})
            continue
        text = f.read_text()
        secs = sections(text)
        own = script_rules.contract_rows(secs)   # the contract's intro and close rows: Tyler's card, never graded as authored rows
        spoken = [r for s in secs for r in s["rows"]]
        n = sum(len(words(r)) for r in spoken)
        if take == "entire" and n < FULL_FLOOR_WORDS:
            fails.append({"file": fname, "row": None, "why": f"{n} words, floor {FULL_FLOOR_WORDS} (~90 s)"})
        if take == "intro":
            body = sum(len(words(r)) for s in secs if s["tag"] == "AI voice" for r in s["rows"])
            if body < BODY_FLOOR_WORDS:
                fails.append({"file": fname, "row": None, "why": f"AI voice body is {body} words, floor {BODY_FLOOR_WORDS}"})
            intro = [r for s in secs[:1] for r in s["rows"]]
            iw = sum(len(words(r)) for r in intro)
            if intro_max_words and iw > intro_max_words and not all(r.strip() in own for r in intro):
                fails.append({"file": fname, "row": intro[0][:60], "why": f"intro is {iw} words, window max {intro_max_words}"})
        for s in secs:
            for r in s["rows"]:
                for pat in BANNED:
                    if re.search(pat, r, re.I):
                        fails.append({"file": fname, "row": r[:60], "why": "agent talk (Agent Chief / Agent Upwork / 24-7 agents)"})
                if r.strip() in own:
                    continue
                n_r = len(words(r))
                if n_r > MAX_ROW_WORDS:
                    fails.append({"file": fname, "row": r[:60], "why": f"row of {n_r} words, max {MAX_ROW_WORDS}: split it (he reads it aloud)"})
                if s["heading"].lower() != "intro" and not row_is_specific(r, terms):
                    fails.append({"file": fname, "row": r[:60], "why": "could be pasted into another job: names nothing from this post or this app"})
        for why in post_integrity.claims_reasons(text, cues_f.read_text() if cues_f.is_file() else "", post, skip=own):
            fails.append({"file": fname, "row": None, "why": why})
        if not any(CONTRACTION.search(r) for r in spoken):
            fails.append({"file": fname, "row": None, "why": "no contraction anywhere: write the way he talks (I'm, it's, here's)"})
    seen, out = set(), []
    for x in fails:   # entire and intro share rows: report each failing row once
        k = (x["row"], x["why"])
        if k not in seen:
            seen.add(k); out.append(x)
    return out


def _claude(prompt, model, work, timeout=900):
    r = subprocess.run(["claude", "-p", prompt, "--model", model, "--permission-mode", "acceptEdits", "--allowedTools", "Read", "Write", "Edit", "--add-dir", str(work)],
                       capture_output=True, text=True, timeout=timeout, cwd=str(work))
    if r.returncode:
        raise RuntimeError(f"claude worker failed: {(r.stderr or r.stdout)[-200:]}")
    return r.stdout


FIX_HOW = {   # knowledge#18069: each failing check's finding becomes an instruction to the writer, who rewrites only that row
    "E3": "E3 = a result/number row has no source. Either add `source: {post: '<an exact quote, 2+ words, copied from the JOB POST>'}` to that row (make the row a dict with `say:` and `source:`), or DROP the claim: say what the app shows, with no number or outcome.",
    "E4": "E4 = reading grade too high. Rewrite to grade <= 7: words of one or two syllables, rows under 12 words, no stacked clauses.",
    "E6": "E6 = the row (or the whole video) is outside its word band. Trim or split to the band the finding names; never pad with filler.",
    "E7": "E7 = more than one claim in a sentence. Split it into short sentences with one claim each.",
    "E8": "E8 = the row names nothing from the post. Rewrite it around one of the post's own nouns (listed below).",
    "E9": "E9 = a list of UI labels. Replace the list with what the client sees or gets, in one plain sentence.",
    "E10": "E10 = the section is outside its beat word range. Trim or add plain rows from the post's own words to land inside the range the finding names.",
}


def fix_instructions(failing):
    """One instruction line per rule that appears in the failing rows."""
    seen = []
    for x in failing:
        m = re.match(r"\s*(E\d+)\b", str(x.get("why", "")))
        if m and m.group(1) in FIX_HOW and m.group(1) not in seen:
            seen.append(m.group(1))
    return "\n".join(FIX_HOW[k] for k in seen)


def write(pkg, job_text, failing, model="sonnet", attempts=3):
    """Run the writer; a pass that leaves script-source.yaml unparseable (an unquoted colon crashed 7567, 8891 and 2046 on Ra, 2026-11-24) is rolled back
    to the pre-pass file and re-run with the parse error as an instruction, up to `attempts` times; still broken -> the original file stays (knowledge#18069)."""
    sy = Path(pkg) / "script-source.yaml"
    snap = sy.read_text() if sy.is_file() else None
    extra = []
    for _ in range(attempts):
        _write_once(pkg, job_text, failing + extra, model)
        if snap is None:
            return
        try:
            yaml.safe_load(sy.read_text())
            return
        except yaml.YAMLError as e:
            try:   # first the deterministic repair (quote the colon rows); only a file it cannot save is rolled back
                import upwork_rules
                upwork_rules.load_source(sy)
                return
            except yaml.YAMLError:
                pass
            sy.write_text(snap)
            extra = [{"file": "script-source.yaml", "row": None, "why": f"YAML: your last edit made the file unparseable ({str(e)[:120]!r}). Wrap every row that holds a colon, quote or # in double quotes."}]


def _write_once(pkg, job_text, failing, model="sonnet"):
    """Writer pass: the write-as-tyler skill (fleet-doctrine:write-as-tyler) rewrites ONLY the failing rows of script-source.yaml."""
    import s7_hook
    nouns = ", ".join(s7_hook.distinctive_nouns(job_text))
    if any("E8" in str(x.get("why")) for x in failing):
        gold_n = f"\nE8: every app/diagram row you rewrite MUST use one of the post's own nouns: {nouns}."
    else:
        gold_n = ""
    how = fix_instructions(failing)
    gold_n += ("\nHOW TO FIX EACH RULE:\n" + how) if how else ""
    gold = "The golden example is a ~190-word Full script (the rewritten 9263 entire-script.md): specific to the post, 12-15 s diagram, no agent talk, rows 6-14 words with contractions."
    _claude(f"Use the fleet-doctrine:write-as-tyler skill. Edit {pkg}/script-source.yaml only. Fix exactly these failing rows and change nothing else; "
            f"keep the same sections, `do` steps and hand-off. {gold}\nTHE CONTRACT RULES (the rows must satisfy all of them):\n{script_rules.prompt_rules()}\nFAILING ROWS:\n" + "\n".join(f"- {x['file']}: {x['row'] or '(whole file)'}: {x['why']}" for x in failing)
            + gold_n + f"\nThe first AI-voice row (the I-noticed line) is filled by code: do not touch it.\nJOB POST:\n{job_text}", model, pkg)


def review(pkg, job_text, model="sonnet", timeout=600):
    """Reviewer pass: agent fleet-doctrine:copy-reviewer against the job post. -> failing rows [{file,row,why}]."""
    # the contract's own rows (Tyler's intro card, the verbatim close line) are fixed words: the reviewer judged them generic and blocked
    # every v13 package (1339/1291/8891/7567 on Ra, 2026-11-24), and no rewrite may change them. Named as fixed, and filtered after.
    own = sorted(script_rules.contract_rows(sections((Path(pkg) / "entire-script.md").read_text()))) if (Path(pkg) / "entire-script.md").is_file() else []
    fixed = ("\nTHESE ROWS ARE FIXED CONTRACT WORDING (Tyler's own card and close line). Never list them, never judge them:\n" + "\n".join(own) + "\n") if own else ""
    out = _claude(f"Use the fleet-doctrine:copy-reviewer agent. Review {pkg}/entire-script.md against this job post (audience: the client deciding in 60 s). "
                  "Reply with ONLY a JSON list of {\"row\": <first 60 chars of the row>, \"why\": <reason>} for rows that are generic, wrong for this post, or not specific; [] if none. "
                  "Headings (## ...) and [browser] cues are stage directions, not rows." + fixed + "\n"
                  f"JOB POST:\n{job_text}", model, pkg, timeout=timeout)
    return drop_fixed(parse_review(out), own)


def drop_fixed(fails, own):
    """Reviewer findings on a heading, a cue or a contract row are dropped: those words are not the writer's to change."""
    keep = []
    for x in fails:
        r = (x.get("row") or "").strip()
        if r.startswith(("#", "[browser]")) or (r and any(o.startswith(r[:60]) or r.startswith(o[:60]) for o in own)):
            continue
        keep.append(x)
    return keep


def parse_review(out):
    """The reviewer's reply -> failing rows. A reply that is not a JSON list, or holds a non-object item, RAISES (the caller blocks READY):
    it used to crash on a bare string ('str' object has no attribute 'get') and swallow ValueError into 'no failures' (knowledge#17827)."""
    m = re.search(r"\[.*\]", out or "", re.S)
    if not m:
        raise ValueError("reviewer reply holds no JSON list")
    items = json.loads(m.group(0))
    rows = []
    for x in items:
        if isinstance(x, str):
            rows.append({"file": "entire-script.md", "row": x[:60], "why": "reviewer flagged this row"})
        elif isinstance(x, dict):
            rows.append({"file": "entire-script.md", "row": x.get("row"), "why": x.get("why", "reviewer")})
        else:
            raise ValueError(f"reviewer item is {type(x).__name__}, want object or string")
    return rows


def run_loop(pkg, job_text, regenerate, steps=None, intro_max_words=None, model="sonnet"):
    """check -> reviewer -> writer with the failing rows -> regenerate the take files; max MAX_LOOPS writer passes. Writes script-check.json."""
    steps = steps or {}
    pkg = Path(pkg)
    wr = steps.get("write") or (lambda p, t, f: write(p, t, f, model))
    rv = steps.get("review") or (lambda p, t: review(p, t, model))
    loops, fails = 0, []
    while True:
        fails = check_package(pkg, job_text, intro_max_words)
        if not fails:
            try:
                fails = rv(pkg, job_text)
            except Exception as e:  # noqa: BLE001  the reviewer being down is a named non-pass, never a fill
                fails = [{"file": "entire-script.md", "row": None, "why": f"reviewer did not run: {str(e)[:100]}"}]
                break
        if not fails or loops >= MAX_LOOPS:
            break
        wr(pkg, job_text, fails)
        regenerate(pkg)
        loops += 1
    doc = {"pass": not fails, "loops": loops, "failing_rows": fails}
    (pkg / "script-check.json").write_text(json.dumps(doc, indent=1) + "\n")
    return doc


if __name__ == "__main__":
    p = Path(sys.argv[1])
    post = Path(sys.argv[2]).read_text() if len(sys.argv) > 2 else ""
    f = check_package(p, post)
    print(json.dumps(f, indent=1))
    sys.exit(1 if f else 0)

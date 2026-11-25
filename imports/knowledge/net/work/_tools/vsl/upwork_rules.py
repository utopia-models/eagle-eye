#!/usr/bin/env python3
"""upwork_rules.py: the Upwork script gate, GENERATED from vsl/contract/upwork.yaml `script:` via script_rules (knowledge#17592, rewritten #17827).
The generator REFUSES (exit non-zero, no script file written) when any rule fails. Input: <pkg>/script-source.yaml + <pkg>/post.md.
  E0 opener  the intro section reads as the contract's intro.full (per-job take) or intro.auto (library intro) shape, e.g. "Hi, I'm Tyler Youk with Utopia Models. I noticed your post for <role>, so I made you a working <thing> and a software architecture diagram behind it, so that you can get <outcome>.." (the LETTER's line 1 is not the intro)
  E1 intro   the FIRST AI-voice row (first row of the section after the intro) reads "I noticed <...>, so I made you <...>, so that you can <...>" (Fazio S7); the noticed blank carries >= noticed_run_words consecutive words of post.md
  E3 source  every outcome/result row, and every row with a number, carries `source: {post: "<exact quote from post.md>"}` or `{artifact: "<file in the package>"}`
  E4 grade   every row reads at Flesch-Kincaid grade <= contract max_grade
  E11 close  the last AI-voice row is the contract's close_line, verbatim (and the close line is nowhere else)
  E6 shape   contractions present, no question mark, no ask/close row, rows min..max words, total seconds inside the contract's total at words_per_s
  (E2 outcome-on-row-3 and E5 ask+close+times RETIRED #17827: unsourced / contradicted the contract's no-close, no-question rule.)
Line shape in script-source.yaml: a string, or {say, do?, outcome?, result?, source?}.
CLI: upwork_rules.py <pkg> [--delivered]   exit 1 + the named rules on stdout when any fails."""
import re
import sys
from pathlib import Path

import yaml

import script_rules
from script_authoring import GENERIC_VOCAB, STOP

R = script_rules.rules()
MAX_GRADE = float(R["max_grade"])
WPS = R["words_per_s"]        # the contract's pace (length.words_per_s), one value for every gate
MIN_S, MAX_S = R["total_s"]
CONTRACTION = re.compile(r"\b\w+['\u2019](?:m|ll|ve|re|d|s|t)\b", re.I)
INTRO_RE = re.compile(r"\bI noticed\b(?P<n>.+?),?\s+so I made you\b(?P<b>.+?),?\s+so that you can\b(?P<y>.+)", re.I | re.S)
TIME_RE = re.compile(r"\b(?:mon|tues?|wednes|thurs?|fri|satur|sun)day\b.{0,20}?\b\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)", re.I)
PLACEHOLDER = re.compile(r"\{[^}]*\}|\[[^\]]*\]|\bTBD\b|\bXX\b|<[^>]+>")


class Refused(Exception):
    def __init__(self, fails):
        self.fails = fails
        super().__init__("; ".join(f"{f['rule']}: {f['why']}" for f in fails))


def say(l):
    return l if isinstance(l, str) else (l.get("say") or "")   # a row with no `say` is reported by check() (rule "rows"), never a KeyError


def rows(src):
    return [l if isinstance(l, dict) else {"say": l} for s in src["sections"] for l in s["lines"]]


def toks(t):
    return re.findall(r"[a-z0-9']+", t.lower().replace("’", "'"))


def syllables(w):
    w = re.sub(r"[^a-z]", "", w.lower())
    if not w:
        return 1
    n = len(re.findall(r"[aeiouy]+", w))
    if w.endswith("e") and not w.endswith(("le", "ee")) and n > 1:
        n -= 1
    if w.endswith("es") or w.endswith("ed"):
        if n > 1 and not re.search(r"[td]ed$|[sxz]es$|[cg]es$|[sc]hes$", w):
            n -= 1
    return max(1, n)


def grade(row, own=frozenset()):
    """Flesch-Kincaid grade of one row (a row is one sentence-ish line). `own` = the post's own words (lower-case): the client's own
    names (PgBouncer, solicitation, Dentrix) count as one syllable. E4 asks for plain words, E8 and the reviewer ask for THEIR words,
    and grading their words as hard words made the two fight (1291/7567 on Ra, 2026-11-24: every specific rewrite failed E4)."""
    ws = re.findall(r"[A-Za-z0-9][A-Za-z0-9'’]*", row)
    if not ws:
        return 0.0
    sents = max(1, len(re.findall(r"[.!?]+(?:\s|$)", row)))
    syl = sum(1 if w.lower() in own else (syllables(w) if not w.isdigit() else 2) for w in ws)
    return 0.39 * len(ws) / sents + 11.8 * syl / len(ws) - 15.59


def has_run(blank, post, n=3):
    b, p = toks(blank), " ".join(toks(post))
    return any(" ".join(b[i:i + n]) in p for i in range(len(b) - n + 1))


def intro_ok(intro_rows):
    """The intro section, joined, matches intro.full or intro.auto."""
    t = " ".join(x.strip() for x in intro_rows)
    return any(rx.match(t) for _, rx in script_rules.intro_matchers())


def exempt(r, intro_pass=False, intro_rows=()):
    """A verbatim contract row (the matched intro, the close line) is Tyler's card: no row/grade/sentence caps."""
    t = say(r).strip()
    return script_rules.is_close(t) or (intro_pass and t in {x.strip() for x in intro_rows})


NOTICED_STARTS = {"your", "you", "you're", "that", "how"}   # the 'I noticed' blank reads as a phrase about them (fm:19397), never a raw post fragment


def hook_applies(src):
    """The AI-voice hook (E1, Fazio S7) follows only the take types the contract lists (hook.takes, v14: [auto]). The take is read from the
    intro the writer chose: intro_slots {cluster} = the library intro (auto), {role, thing, outcome} = the full intro. No slots = auto."""
    takes = (R.get("hook") or {}).get("takes") or ["auto", "full"]
    sl = src.get("intro_slots") if isinstance(src, dict) else None
    kind = "full" if isinstance(sl, dict) and not sl.get("cluster") and sl.get("role") else "auto"
    return kind in takes


def strip_hook(src):
    """A full VSL carries no hook row: remove the S7 rows at the head of the first AI-voice section. -> True when changed."""
    if hook_applies(src) or len(src.get("sections") or []) < 2:
        return False
    lines = src["sections"][1]["lines"]
    for k in (1, 2, 3):
        if len(lines) > k and INTRO_RE.search(" ".join(say(x) for x in lines[:k])):
            src["sections"][1]["lines"] = lines[k:]
            return True
    return False


def repair_yaml_text(text):
    """A writer row like `- say: Here's the check: every move` is invalid YAML (a second colon). Quote every unquoted `say:` / `- say:` value that holds ': '
    or ' #'; -> repaired text (knowledge#18069: 7567, 8891, 2046 on Ra were stuck on exactly this)."""
    out = []
    for ln in text.splitlines():
        m = re.match(r"^(\s*(?:- )?say:\s+)(?![\"'|>\[{])(.+?)\s*$", ln)
        if m and (": " in m.group(2) or " #" in m.group(2)):
            ln = m.group(1) + '"' + m.group(2).replace("\\", "\\\\").replace('"', '\\"') + '"'
        out.append(ln)
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def load_source(path):
    """yaml.safe_load that repairs (and rewrites) a file the writer left with unquoted colons."""
    path = Path(path)
    try:
        return yaml.safe_load(path.read_text())
    except yaml.YAMLError:
        fixed = repair_yaml_text(path.read_text())
        src = yaml.safe_load(fixed)   # still broken -> raises, the caller names it
        path.write_text(fixed)
        return src


def check(pkg, delivered=False):
    """-> [{rule, row, why}]; empty = pass."""
    pkg = Path(pkg)
    f = []
    sy = pkg / "script-source.yaml"
    pf = pkg / "post.md"
    if not sy.is_file():
        return [{"rule": "input", "row": None, "why": "script-source.yaml missing"}]
    if not pf.is_file():
        return [{"rule": "input", "row": None, "why": "post.md missing: every claim and the E1 blanks quote it"}]
    src, post = load_source(sy), pf.read_text()
    bad = [i + 1 for i, l in enumerate(l for s_ in src["sections"] for l in s_["lines"]) if isinstance(l, dict) and not isinstance(l.get("say"), str)]
    if bad:
        return [{"rule": "rows", "row": None, "why": f"row(s) {bad[:8]} have no `say` text: every row is a string or a mapping with a `say` key"}]
    post_words = frozenset(w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9'’]*", post) if len(w) > 3)
    for why in script_rules.fill_intro(src):   # #17942: the intro is filled from the writer's slots, so E0 passes by construction
        f.append({"rule": "E0", "row": None, "why": why})
    R_ = rows(src)
    spoken = [say(r) for r in R_]
    intro_rows = [say(l) for l in src["sections"][0]["lines"]]
    body_rows = [l for s in src["sections"][1:] for l in s["lines"]]
    # E0: the live intro opens with the letter's line 1
    pend = script_rules.pending_slots()
    intro_pass = False
    if "intro.full" in pend or "intro.auto" in pend:
        pass   # a held intro slot: not yet set, neither a pass nor a crash; script_rules.pending_slots() names it
    else:
        intro_pass = intro_ok(intro_rows)
        if not intro_pass:
            f.append({"rule": "E0", "row": intro_rows[0][:60] if intro_rows else None,
                      "why": "the intro must read as intro.full: " + R["intro_full"] + "  (or intro.auto: " + R["intro_auto"] + ")"})
    # E11: the last AI-voice row is the close line, verbatim
    if not script_rules.is_pending(R["close_line"]):
        last = say(body_rows[-1]).strip() if body_rows else ""
        if not script_rules.is_close(last):
            f.append({"rule": "E11", "row": last[:60] or None, "why": "the last AI-voice row must be the close line, verbatim: " + R["close_line"]})
        if sum(1 for t in spoken if script_rules.is_close(t)) > 1:
            f.append({"rule": "E11", "row": None, "why": "the close line appears more than once"})
    # E1: first AI-voice row is the S7 line (it may continue on the next row: join two). Gated on take type (contract hook.takes, v14):
    # a FULL VSL (intro.full) has no hook, its intro already says "I noticed your post..., so I made you..." (fm:19397)
    if hook_applies(src):
        first_ai = " ".join(say(l) for l in body_rows[:3])   # the S7 line is long: it may be split over up to three rows
        m = INTRO_RE.search(first_ai)
        if not m:
            f.append({"rule": "E1", "row": say(body_rows[0])[:60] if body_rows else None, "why": 'the first AI-voice row must read "I noticed ..., so I made you ..., so that you can ..."'})
        else:
            if (toks(m["n"]) or [""])[0].lower() not in NOTICED_STARTS:
                f.append({"rule": "E1", "row": None, "why": f"the 'I noticed' blank must read as a phrase about them (start: {', '.join(sorted(NOTICED_STARTS))}), not a raw post fragment"})
            if not has_run(m["n"], post, R["noticed_run_words"]):
                f.append({"rule": "E1", "row": None, "why": f"the 'I noticed' blank has no {R['noticed_run_words']} consecutive words from post.md (use the post's own words)"})
            if len(toks(m["b"])) < 2 or len(toks(m["y"])) < 2:
                f.append({"rule": "E1", "row": None, "why": "the 'so I made you' / 'so that you can' blanks are empty"})
            # the hook beat's range (beat_words.hook) is E1's, not E10's: the S7 line is code-filled from a triple (s7_hook), so only a new
            # triple fixes its length, and E1 is what makes regen author one (2046 regen 2026-11-24: an 81-word line kept the video at 94 s)
            hlo, hhi = R["beat_words"]["hook"]
            hn = len(toks(m.group(0)))
            if not hlo <= hn <= hhi:
                f.append({"rule": "E1", "row": None, "why": f"the S7 line is {hn} words, the hook is {hlo}-{hhi}"})
    # E3
    for i, r in enumerate(R_):
        if r.get("outcome") or r.get("result") or re.search(r"\d", say(r)):
            s = r.get("source") or {}
            q, a = s.get("post"), s.get("artifact")
            if q and " ".join(toks(q)) in " ".join(toks(post)) and len(toks(q)) >= 2:
                continue
            if a and (pkg / a).is_file():
                continue
            why = "no source" if not s else ("post quote not found in post.md" if q else "artifact file not found in the package")
            f.append({"rule": "E3", "row": say(r)[:60], "why": f"result row {i + 1}: {why} (source: {{post: '<quote>'}} or {{artifact: '<file>'}})"})
    # The S7 line's rows (E1, up to three): its "I noticed" blank must be >= noticed_run_words consecutive words of the post, so the
    # post's own reading level rides in it; E4 grading it is a rule fighting E1 (2046 regen 2026-11-24: S7 rows at grade 13-20 after
    # three writer passes, nova). Exempt from E4 and from E6's row-word cap; E7 already exempts it from the sentence cap.
    s7_rows = {say(l) for l in body_rows[:3]} if INTRO_RE.search(" ".join(say(l) for l in body_rows[:3])) else set()
    # E4 (the contract's verbatim opener is exempt: it is Tyler's card, no rewording)
    for r in R_:
        if exempt(r, intro_pass, intro_rows) or say(r) in s7_rows:
            continue
        g = grade(say(r), post_words)
        if g > MAX_GRADE:
            f.append({"rule": "E4", "row": say(r)[:60], "why": f"grade {g:.1f}, max {MAX_GRADE:g}: shorter words, shorter row"})
    # E6: shape from the contract. The S7 rows are exempt from the row-word cap only: the S7 line is the hook (contract hook: 18-30
    # words), and capping it squeezed its blanks to "this" so E1 failed (0062 regen, 2026-11-24, nova).
    for r in R_:
        s_ = say(r)
        if exempt(r, intro_pass, intro_rows):
            continue
        if R["questions"] == "forbidden" and "?" in s_:
            f.append({"rule": "E6", "row": s_[:60], "why": "no question mark in the video"})
        if r.get("ask") or r.get("close"):
            f.append({"rule": "E6", "row": s_[:60], "why": "no ask or call-time row of its own: the only close is the contract close_line (the take ends on it)"})
        n = len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'\u2019]*", s_))
        if n > R["max_row_words"] and s_ not in s7_rows:
            f.append({"rule": "E6", "row": s_[:60], "why": f"{n} words, max {R['max_row_words']}"})
    if R["contractions"] == "required" and not any(CONTRACTION.search(t) for t in spoken):
        f.append({"rule": "E6", "row": None, "why": "no contraction anywhere: write the way he talks (I'm, it's)"})
    for t in spoken:
        if PLACEHOLDER.search(t):
            f.append({"rule": "E6", "row": t[:60], "why": "placeholder in the script"})
    f += check_thesis(src, post, body_rows)
    f += check_voice_and_intro(src, post, intro_rows, body_rows)
    secs = round(sum(len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'\u2019]*", t)) for t in spoken) / WPS)
    if not MIN_S <= secs <= MAX_S:
        f.append({"rule": "E6", "row": None, "why": f"{secs} s at {WPS} words/s, need {MIN_S}-{MAX_S} s"})
    return f


AI_VOICE = re.compile(r"\bAI[- ]?(?:generated )?voice\b|\b(?:synthetic|cloned?|artificial) voice\b|\bvoice (?:agent|clone|model)\b|\bso you get it today\b|\bwalkthrough is my\b", re.I)
INTRO_ECHO = re.compile(r"\bI'?m Tyler\b|\bTyler Youk\b|\bUtopia Models\b|\bI noticed\b|\bso I made you\b|\bsoftware architecture diagram behind it\b", re.I)


def check_voice_and_intro(src, post, intro_rows, body_rows):
    """#18869 items 1+2 (Tyler 2026-11-24). E12: no spoken line (intro or body) names the voice as AI or a clone. E13: no AI row restates Tyler's
    intro (his identity, 'I noticed', 'so I made you', or a 4-word run of his intro). E14: the FIRST AI row names a concrete item from the post
    (a 2-word run of post.md that is not already in his intro), so it jumps straight into their job."""
    f = []
    for t in [*intro_rows, *(say(l) for l in body_rows)]:
        if AI_VOICE.search(t):
            f.append({"rule": "E12", "row": t[:60], "why": "a spoken line names the voice as AI or a clone: no disclosure (Tyler card 11-24), say nothing about the voice"})
    it = toks(" ".join(intro_rows))
    intro_4 = {" ".join(it[i:i + 4]) for i in range(len(it) - 3)}
    for l in body_rows:
        t = say(l)
        if script_rules.is_close(t):
            continue
        bt = toks(t)
        if INTRO_ECHO.search(t) or any(" ".join(bt[i:i + 4]) in intro_4 for i in range(len(bt) - 3)):
            f.append({"rule": "E13", "row": t[:60], "why": "restates Tyler's intro: the AI voice starts at THEIR job, it never says who he is, 'I noticed' or 'so I made you'"})
    if body_rows:
        first = toks(say(body_rows[0]))
        pt, intro_txt = toks(post), " ".join(it)
        ok = any(" ".join(first[i:i + 2]) in " ".join(pt) and " ".join(first[i:i + 2]) not in intro_txt and not set(first[i:i + 2]) <= STOP
                 for i in range(len(first) - 1))
        if not ok:
            f.append({"rule": "E14", "row": say(body_rows[0])[:60], "why": "the first AI row must name a concrete item from the job post (2+ consecutive words of post.md), straight into THEIR job"})
    return f


SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
LABEL_ITEM = r"[A-Z][\w-]*(?: [A-Z][\w-]*){0,2}"
LABEL_LIST = re.compile(rf"(?:\b{LABEL_ITEM}, ){{2,}}(?:and )?{LABEL_ITEM}")


def nwords(t):
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'\u2019]*", t))


def check_thesis(src, post, body_rows):
    """The thesis checker rules (fm:18762, contract script.checker_rules): E7 one claim per sentence, E8 client nouns / no generic sentence, E9 no UI-label list,
    E10 beat word ranges. The I-noticed line (E1) is exempt from the sentence cap; the held close/intro slots are skipped (pending)."""
    f = []
    cap = R["max_sentence_words"]
    first = say(body_rows[0]) if body_rows else ""
    terms = {w for w in toks(post) if len(w) > 3} - STOP - GENERIC_VOCAB
    first_ai = [say(l) for l in body_rows[:3] if INTRO_RE.search(" ".join(say(x) for x in body_rows[:3]))]
    for s in src["sections"][1:]:
        for l in s["lines"]:
            r = l if isinstance(l, dict) else {"say": l}
            t = say(r)
            if script_rules.is_close(t):
                continue
            if t not in first_ai:
                for sent in SENT_SPLIT.split(t.strip()):
                    if nwords(sent) > cap:
                        f.append({"rule": "E7", "row": sent[:60], "why": f"{nwords(sent)} words in one sentence, max {cap}: one claim per sentence"})
            if t in first_ai:
                continue
            if LABEL_LIST.search(t[1:]) and not re.search(r"\bfor\b", t):
                f.append({"rule": "E9", "row": t[:60], "why": "a list of UI labels: say what the client sees or gets, not the panel names"})
            if not ({w for w in toks(t)} & terms) and not re.search(r"\d", t) and not r.get("source"):
                f.append({"rule": "E8", "row": t[:60], "why": "would fit a different job: names nothing from this post (use the client's own nouns)"})
    bw = R["beat_words"]
    for sec in src["sections"][1:]:
        key = sec["id"] if sec["id"] in ("app", "diagram") else None
        if key:
            n = sum(nwords(say(l)) for l in sec["lines"] if not script_rules.is_close(say(l)))
            lo, hi = bw[key]
            if key == "app":
                hk = sum(nwords(say(l)) for l in sec["lines"][:3] if INTRO_RE.search(" ".join(say(x) for x in sec["lines"][:3])))
                n -= hk
            if not lo <= n <= hi:
                f.append({"rule": "E10", "row": None, "why": f"{sec['id']} section is {n} words, beat range {lo}-{hi}"})
    return f


REWRITABLE = ("E12", "E13", "E14", "E3", "E4", "E6", "E7", "E8", "E9", "E10")   # E8 (fm:19397): a row naming nothing from the post goes back to the writer with the post's nouns   # a row's grade, a row's words, a sentence's words (E7 is the same long-row defect), a beat's words: handed back to the writer, never an instant block
MAX_PASSES = 5   # knowledge#18069: the check must FIX, up to 5 rounds (3 left 1291/7567/1339/8891 failing on one row each)


def fill_file(pkg):
    """Write the filled intro into script-source.yaml (when it carries intro_slots) so every later reader sees the contract wording. -> problems."""
    sy = Path(pkg) / "script-source.yaml"
    if not sy.is_file():
        return []
    src = load_source(sy)
    if not isinstance(src, dict):
        return []
    why, dirty = [], fix_close(src)
    dirty = strip_hook(src) or dirty
    if src.get("intro_slots"):
        why = script_rules.fill_intro(src)
        dirty = dirty or not why
    if dirty:
        sy.write_text(yaml.safe_dump(src, sort_keys=False, allow_unicode=True, width=1000))
    return why


def fix_close(src):
    """The close line is code, like the intro: the writer cut it to 'Reply to my proposal.' (1435 on Ra, 2026-11-24), so the last row
    of the last section is set to the contract's close_line verbatim when it reads as a reworded close. -> True when changed."""
    c = R["close_line"]
    secs = src.get("sections") or []
    if script_rules.is_pending(c) or not secs or not secs[-1].get("lines"):
        return False
    lines = secs[-1]["lines"]
    last = say(lines[-1]).strip()
    if script_rules.is_close(last):
        return False
    head = " ".join(c.split()[:5]).lower()
    if " ".join(last.split()[:5]).lower() == head or "reply to my proposal" in last.lower():
        lines[-1] = c if isinstance(lines[-1], str) else dict(lines[-1], say=c)
    elif not any(script_rules.is_close(say(x)) for s_ in secs for x in s_.get("lines") or []):
        lines.append(c)
    else:
        return False
    return True


def rewrite_loop(pkg, rewriter, passes=MAX_PASSES):
    """#17942: rewrite, don't block. On E4/E6/E10 the failing rows go back to `rewriter(pkg, fails)` (it edits script-source.yaml: split a long
    sentence, simplify words, pad or trim a beat from the post's own words), then the check runs again, up to `passes` times. Other rules are
    never rewritten here. -> (remaining fails, passes used). Blocks (non-empty) only when the last pass still fails, naming row and rule."""
    fill_file(pkg)
    fails = check(pkg)
    used = 0
    while fails and used < passes and all(x["rule"] in REWRITABLE for x in fails):
        rewriter(pkg, fails)
        used += 1
        fill_file(pkg)
        fails = check(pkg)
    return fails, used


def claude_rewriter(job_text, model="sonnet"):
    """The default rewriter: the same write-as-tyler pass script_authoring uses, aimed at exactly the failing rows."""
    import script_authoring
    return lambda pkg, fails: script_authoring.write(
        pkg, job_text, [{"file": "script-source.yaml", "row": x["row"], "why": f"{x['rule']}: {x['why']}"} for x in fails], model)


def enforce(pkg, delivered=False):
    fails = check(pkg, delivered)
    if fails:
        raise Refused(fails)


if __name__ == "__main__":
    out = check(sys.argv[1], "--delivered" in sys.argv)
    for x in out:
        print(f"REFUSED {x['rule']}: {x['why']}" + (f"  [{x['row']}]" if x["row"] else ""))
    print("PASS E0 E1 E3 E4 E6 E11" if not out else f"{len(out)} failure(s)")
    sys.exit(1 if out else 0)

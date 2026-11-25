#!/usr/bin/env python3
"""s7_hook.py: the Fazio S7 hook is assembled by code, never written free-text (knowledge#17941, after 0062 regen 2026-11-24).
The contract's script.first_ai_line is the template ("I noticed {ask}, so I made you {app}, so that you can {outcome}."). The model returns a JSON
triple {noticed, made, outcome}; the code validates `noticed` (>= noticed_run_words consecutive words copied from post.md) and fills the template, so
the writer can never break the fixed sentence. A bad triple retries the triple only (MAX_LOOPS)."""
import json
import re
from collections import Counter

import script_rules
import script_authoring as SA
import upwork_rules as U

KEYS = ("noticed", "made", "outcome")
NOTICED_STARTS = U.NOTICED_STARTS


def _clean(s):
    return re.sub(r"\s+", " ", str(s or "")).strip().strip(",.;:!?").strip()


def validate(t, post):
    """-> list of reasons the triple is refused; empty = good."""
    if not isinstance(t, dict):
        return ["the reply is not a JSON object {noticed, made, outcome}"]
    why = []
    v = {k: _clean(t.get(k)) for k in KEYS}
    n = script_rules.rules()["noticed_run_words"]
    # the blank must READ after "I noticed": "I noticed help scale our core systems" (1291, 2026-11-24) was a raw post fragment.
    # It opens like a phrase about them ("your ...", "that you ...", "you ...", "how ..."), then quotes the post.
    first = (v["noticed"].split() or [""])[0].lower()
    if first not in NOTICED_STARTS:
        why.append(f"`noticed` must read after 'I noticed' as a phrase about them, starting with one of {', '.join(sorted(NOTICED_STARTS))} "
                   "(e.g. 'your post needs <their words>'), never a raw fragment of the post")
    if not U.has_run(v["noticed"], post, n):
        why.append(f"`noticed` has no {n} consecutive words copied from post.md: copy the client's own words")
    for k in ("made", "outcome"):
        if len(U.toks(v[k])) < 2:
            why.append(f"`{k}` is empty or one word")
    # the hook beat's word range from the contract (beat_words.hook): an 81-word triple made 2046 run 87 s and starved the app beat,
    # and no row rewrite can trim it because the code re-applies the triple after every writer pass (2046 regen 2026-11-24, nova)
    lo, hi = script_rules.rules()["beat_words"]["hook"]
    if not why:
        n_w = len(U.toks(fill(v)))
        if not lo <= n_w <= hi:
            why.append(f"the filled line is {n_w} words, the hook is {lo}-{hi}: {'shorten' if n_w > hi else 'lengthen'} `made` and `outcome`")
    for k in KEYS:
        if "?" in str(t.get(k) or "") or re.search(r"\bso (?:I made you|that you can)\b|\bI noticed\b", v[k], re.I):
            why.append(f"`{k}` repeats the template's own words or holds a question mark")
    return why


def parse(out):
    m = re.search(r"\{.*\}", out or "", re.S)
    if not m:
        raise ValueError("reply holds no JSON object")
    return json.loads(m.group(0))


def fill(t):
    """The three blanks -> the contract line, exactly."""
    v = {k: _clean(t[k]) for k in KEYS}
    return script_rules.rules()["first_ai_line"].format(ask=v["noticed"], app=v["made"], outcome=v["outcome"])


def rows_for(line):
    """The S7 line as up to three spoken rows (split at the template's commas); joined with a space they read back as the line."""
    m = U.INTRO_RE.search(line)
    return [f"I noticed{m['n']},", f"so I made you{m['b']},", f"so that you can{m['y']}"] if m else [line]


def apply(src, line, k=None):
    """`k` = how many head rows are the S7 rows when known (a re-apply after the writer: len(rows_for(line))). Replace the S7 row(s) at the head of the first AI-voice section with `line`; return src. Rows keep their type (str or {say:})."""
    lines = src["sections"][1]["lines"]
    if k is None:   # first fill: the S7 rows are the shortest head that reads as the line, else just the first row
        k = 1
        for i in range(1, min(3, len(lines)) + 1):
            if U.INTRO_RE.search(" ".join(U.say(x) for x in lines[:i])):
                k = i
                break
    proto = lines[0]
    new = [{"say": r} if isinstance(proto, dict) else r for r in rows_for(line)]
    src["sections"][1]["lines"] = new + lines[k:]
    return src


def author(post, ask_model, loops=max(SA.MAX_LOOPS, U.MAX_PASSES)):
    """-> (triple, []) or (None, reasons). ask_model(prompt)->str is the model call; retries the triple only."""
    why = []
    for _ in range(max(1, loops)):
        p = ("Reply with ONLY a JSON object {\"noticed\": ..., \"made\": ..., \"outcome\": ...} that fills the blanks of: "
             + script_rules.rules()["first_ai_line"] + "\n- noticed: a phrase that reads right after 'I noticed', starting with 'your', 'that you', 'you' or 'how' (e.g. 'your team needs <their words>'), holding what the client asked for COPIED word for word from the post "
             f"(at least {script_rules.rules()['noticed_run_words']} consecutive words of the post)\n- made: what we built for them, in the client's nouns\n"
             "- outcome: their outcome in their words. Plain words, no question marks, never repeat the template's own words.\n"
             f"- the whole filled line is {script_rules.rules()['beat_words']['hook'][0]}-{script_rules.rules()['beat_words']['hook'][1]} words: "
             "noticed 4-8 words, made 3-6 words, outcome 3-6 words."
             + ("\nYOUR LAST TRY WAS REFUSED: " + "; ".join(why) if why else "") + "\nPOST:\n" + post)
        try:
            t = parse(ask_model(p))
        except Exception as e:  # noqa: BLE001  a bad reply is a refused triple, retried
            why = [f"unreadable reply: {str(e)[:80]}"]
            continue
        why = validate(t, post)
        if not why:
            return {k: _clean(t[k]) for k in KEYS}, []
    return None, why


def distinctive_nouns(post, n=12):
    """The post's most frequent non-stopword content words (the E8 rewrite must use one per app/diagram row)."""
    ws = [w.lower() for w in SA.words(post) if len(w) > 3 and not w.isdigit()]
    c = Counter(w for w in ws if w not in SA.STOP and w not in SA.GENERIC_VOCAB)
    return [w for w, _ in c.most_common(n)]

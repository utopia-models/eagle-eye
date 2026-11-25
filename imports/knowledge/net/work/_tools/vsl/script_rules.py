#!/usr/bin/env python3
"""script_rules.py: the Upwork script-writing rules, read from vsl/contract/upwork.yaml `script:` (knowledge#17827).
The contract is the one source. The author prompt (prompt_rules), upwork_rules and script_authoring all read THIS module, so they cannot
disagree; vsl/contract/tests/../_tools/vsl/tests/test_script_contract_17827.py fails when one does."""
import copy
import re
from pathlib import Path

import yaml

WORK = Path(__file__).resolve().parents[2]            # net/work
CONTRACT = WORK / "vsl" / "contract" / "upwork.yaml"


_CACHE = {}


def contract():
    """Parsed once per (path, mtime): every row check reads the contract, and re-parsing it each time made one package check take ~5 s."""
    key = (str(CONTRACT), CONTRACT.stat().st_mtime_ns)
    if _CACHE.get("key") != key:
        _CACHE["key"], _CACHE["doc"] = key, yaml.safe_load(CONTRACT.read_text())
    return copy.deepcopy(_CACHE["doc"])


def rules():
    c = contract()
    s = dict(c["script"])
    s["words_per_s"] = c["length"]["words_per_s"]
    s["total_s"] = tuple(c["length"]["total"])
    s["intro_max_words"] = c["intro"]["max_words"]
    s["intro_full"], s["intro_auto"] = c["intro"]["full"], c["intro"]["auto"]
    return s


def is_pending(slot):
    """A contract slot held for a pending decision is {pending: <ref>}. The checker treats it as 'not yet set': neither a pass nor a crash."""
    return isinstance(slot, dict) and "pending" in slot


def pending_slots():
    """-> {name: ref} of every slot still held (a {pending: <ref>} value). None are held since v12 (fm:18825); the mechanism stays for the next hold."""
    c = contract()
    cand = {"script.close_line": c["script"].get("close_line"), "script.intro_opener": c["script"].get("intro_opener"),
            "intro.auto": c["intro"].get("auto"), "intro.full": c["intro"].get("full")}
    return {k: v["pending"] for k, v in cand.items() if is_pending(v)}


def _fill(template, **kw):
    """Fill {name}-style slots; an absent/empty name drops "Hi {name}," to "Hi,"."""
    t = template
    if not kw.get("name"):
        t = t.replace(" {name}", "")
    return t.format(**{k: v for k, v in kw.items() if v is not None})


def intro_full(name, role, thing, outcome):
    """The per-job live intro (contract intro.full): {name} only when post.md shows it, else it starts "Hi,"."""
    t = rules()["intro_full"]
    if is_pending(t):
        raise ValueError(f"intro.full is pending {t['pending']}")
    t = t.replace("[role]", role).replace("[thing]", thing).replace("[their outcome]", outcome)
    return _fill(t, name=name)


def intro_auto(cluster):
    """The reusable library intro (contract intro.auto): no name, no job brackets."""
    t = rules()["intro_auto"]
    if is_pending(t):
        raise ValueError(f"intro.auto is pending {t['pending']}")
    return t.replace("[cluster]", cluster)


def fill_intro(src):
    """knowledge#17942: the intro is FILLED, never authored. The writer returns only `intro_slots` in script-source.yaml:
    {name?, role, thing, outcome} (per job) or {cluster} (library). This sets the intro section to the contract template filled with them,
    so E0 passes by construction. Returns a list of problems (empty = filled or nothing to fill)."""
    slots = src.get("intro_slots")
    if not slots:
        return []
    clean = lambda v: re.sub(r"[{}\[\]]", "", str(v or "")).strip().rstrip(".,")
    sl = {k: clean(v) for k, v in slots.items()}
    if sl.get("outcome"):   # the template already says "so that you can get ...": a slot that starts with "get" printed "get get" (job 3307, knowledge#18647)
        sl["outcome"] = re.sub(r"^(?:to\s+)?get\s+", "", sl["outcome"], flags=re.I)
    need = ["cluster"] if sl.get("cluster") else ["role", "thing", "outcome"]
    miss = [k for k in need if not sl.get(k)]
    if miss:
        return [f"intro_slots is missing {', '.join(miss)}"]
    line = intro_auto(sl["cluster"]) if sl.get("cluster") else intro_full(sl.get("name"), sl["role"], sl["thing"], sl["outcome"])
    src["sections"][0]["lines"] = split_rows(line)
    return []


BREAK_BEFORE = {"and", "so", "with", "for", "to", "that", "which", "behind"}


def _break(w, max_words):
    """An over-long phrase breaks before the joining word nearest its middle (a prompter row reads as a phrase), else at the word limit."""
    if len(w) <= max_words:
        return [" ".join(w)]
    cands = [i for i in range(1, len(w)) if w[i].lower() in BREAK_BEFORE and i <= max_words and len(w) - i <= max_words]
    i = min(cands, key=lambda k: abs(k - len(w) / 2)) if cands else max_words
    return [" ".join(w[:i])] + _break(w[i:], max_words)


def split_rows(line, max_words=15, max_sents=2):
    """The prompter allows max_words_per_row words and max_sentences_per_row sentences per row. Split the filled intro at sentence ends,
    then at commas, packing greedily; a chunk still too long breaks at the word limit. Rows joined with a space equal the template (E0 joins them)."""
    try:
        pr = contract()["prompter"]
        max_words, max_sents = min(max_words, pr["max_words_per_row"]), min(max_sents, pr["max_sentences_per_row"])
    except Exception:  # noqa: BLE001
        pass
    chunks = []
    for s in re.split(r"(?<=[.!?])\s+", line.strip()):
        for part in re.split(r"(?<=,)\s+", s):
            chunks += _break(part.split(), max_words)
    rows, cur = [], ""
    for c in chunks:
        trial = (cur + " " + c).strip()
        if cur and (len(trial.split()) > max_words or len(re.split(r"(?<=[.!?])\s+", trial)) > max_sents):
            rows.append(cur)
            cur = c
        else:
            cur = trial
    if cur:
        rows.append(cur)
    return rows


def opener(name, ask):
    """Kept for old callers: the LETTER's line 1 is not the intro (intro_full is)."""
    return _fill(rules()["letter_line1"], name=name, ask=ask)


def letter(name, ask, outcome):
    """The proposal letter: L1 + L2 + close (Tyler's cards via fm:18716 / fm:18825), one line each. L2 carries their outcome in their words."""
    r = rules()
    for k in ("letter_line1", "letter_line2", "letter_close"):
        if is_pending(r[k]):
            raise ValueError(f"{k} is pending {r[k]['pending']}")
    return "\n".join([_fill(r["letter_line1"], name=name, ask=ask), _fill(r["letter_line2"], outcome=outcome), r["letter_close"]])


def template_re(template):
    """A contract template -> a compiled regex: every [slot] is a wildcard, " {name}" is an optional name ("Hi, I'm" and "Hi Dana, I'm" both match),
    any other {slot} is a wildcard, the rest is literal (whitespace-tolerant, case-insensitive)."""
    t = template.replace(" {name}", "\x00")
    parts = re.split(r"(\x00|\{[^}]*\}|\[[^\]]*\])", t)
    out = []
    for p in parts:
        if p == "\x00":
            out.append(r"(?:\s+[^,.]{1,40}?)?")
        elif p[:1] in "{[" and p[-1:] in "}]" and len(p) > 1:
            out.append(r".+?")
        else:
            out.append(re.escape(p).replace(r"\ ", r"\s+"))
    return re.compile(r"^\s*" + "".join(out) + r"\s*$", re.I | re.S)


def intro_matchers():
    """-> [(name, regex)] for the live intro shapes: intro_full (per job) and intro_auto (library). A still-pending shape is skipped."""
    r = rules()
    return [(n, template_re(r[n])) for n in ("intro_full", "intro_auto") if not is_pending(r[n])]


def contract_rows(sections):
    """sections: [{heading, rows}] of a RENDERED script (rows split at render). -> the set of rows that are the contract's own words: the intro
    section when it joins to intro.full/intro.auto (Tyler's card, E0), and every row that is part of the verbatim close line. No authored-row
    check (specificity, claims, row caps) applies to them (2026-11-24: the close line's halves read as 'names nothing from this post')."""
    out = set()
    c = " ".join(rules()["close_line"].split())
    for i, s in enumerate(sections):
        rows = [r.strip() for r in s["rows"]]
        if i == 0 and any(rx.match(" ".join(rows)) or rx.match(" ".join(rows[:-1])) for _, rx in intro_matchers()):
            out.update(rows)
        if not is_pending(rules()["close_line"]):
            out.update(r for r in rows if r and " ".join(r.split()) in c)
    return out


def is_close(text):
    """True when `text` IS the contract's close line, verbatim (whitespace-normalised)."""
    c = rules()["close_line"]
    return (not is_pending(c)) and " ".join(text.split()) == " ".join(c.split())


def sources_text():
    """The sources pack the contract names, concatenated: what the author is fed."""
    return "\n\n".join((WORK / p).read_text() for p in rules()["sources"])


def prompt_rules():
    """The rules block of the author prompt, GENERATED from the contract."""
    r = rules()
    return "\n".join([
        f"- every spoken row: {r['min_row_words']} to {r['max_row_words']} words, plain words, one idea, Flesch-Kincaid grade {r['max_grade']} or lower.",
        "- write the way Tyler talks: contractions are required (I'm, it's, here's). Never write 'I am' for 'I'm'." if r["contractions"] == "required" else "- no contractions.",
        "- no question marks anywhere (the letter carries the one question)." if r["questions"] == "forbidden" else "",
        (f"- no ask row, no call times of your own. The LAST row of the diagram section is EXACTLY this close line, no rewording: {r['close_line']}" if not is_pending(r["close_line"])
         else "- no close row, no ask row, no call times: the take ends on the last diagram line.") if r["close"] != "none" else "- no close row, no ask row, no call times: the take ends on the last diagram line.",
        (f"- the intro's wording is held: write the intro section as ONE row that names the client's ask in their own words and nothing else. Do not write the letter line as the intro."
         if is_pending(r["intro_full"]) else f"- the intro (the first section) is FILLED BY CODE, never written by you. Put `intro_slots: {{name: <only if post.md shows it>, role: <their role>, thing: <the working thing, in their words>, outcome: <their outcome, in their words>}}` at the top level of script-source.yaml (a library intro takes `intro_slots: {{cluster: <plain words>}}`) and leave the intro section's lines as one placeholder string. The code fills this template: {r['intro_full']} Library: {r['intro_auto']}"),
        f"- one claim per sentence, at most {r['max_sentence_words']} words (the I-noticed line aside). Use the client's own nouns. A number only if the post or the screen shows it. Delete any sentence that would fit a different job. Never list UI labels. Add no feature the post did not ask for.",
        f"- beat sizes in words: hook {r['beat_words']['hook'][0]}-{r['beat_words']['hook'][1]}, app {r['beat_words']['app'][0]}-{r['beat_words']['app'][1]} (3 actions, each: you do X, you see Y), diagram {r['beat_words']['diagram'][0]}-{r['beat_words']['diagram'][1]} (the flow, where a human approves or a failure is caught, the named tools).",
        f"- the FIRST AI-voice row (first row of the app section) is the Fazio S7 line: {r['first_ai_line']} The 'I noticed' blank carries at least {r['noticed_run_words']} consecutive words of the post.",
        f"- the hook: nothing comes between the hand-off and that first AI row; it starts within {r['hook']['window_s'][0]} to {r['hook']['window_s'][1]} seconds of the hand-off and uses the client's own words, never a reused line.",
        "- do not give Tyler a job title or company role; say nothing about who he is beyond his name." if not r["self_title"] else f"- Tyler's title: {r['self_title']}",
        f"- the whole script is {r['total_s'][0]} to {r['total_s'][1]} seconds at {r['words_per_s']} words a second; the entire take holds at least {r['floor_words_entire']} words.",
        "- no price, rate or milestone; no link; never the words sample, first version, mock, VSL; no 'agent' or 'agents' unless the client wrote it.",
    ])


if __name__ == "__main__":
    print(prompt_rules())

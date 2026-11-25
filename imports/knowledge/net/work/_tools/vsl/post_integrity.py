#!/usr/bin/env python3
"""post_integrity.py: the package integrity gates (knowledge#17487, the 9263 regression).

9263's builder authored the script AND seeded the MVP from a 521-char post cut off at "The ass", then invented two client failures
("clicks Cancel instead of Submit", "loses the session when a page times out") that two recorded takes said to the client as his own words.

  1. post_complete(text)            refuse to build or author from a post under MIN_POST_CHARS, ending mid-word, or with no final sentence end
  2. seeded_reasons(items, post)    every seeded /tasks, chat or issue row carries a `source:` quote and that quote is verbatim in the post
  3. claims_reasons(script, cues, post)  every script row that claims something about the post has a row in the cues file whose
                                    quote is found verbatim in the post; otherwise a failure naming the row number

  post_integrity.py post FILE | seed SEED.json POST | claims SCRIPT CUES POST | --self-test      exit 0 = PASS
Seed file shape: [{"title": "...", "source": "<quote from post.md>"}, ...] (seed-sources.json beside the package).
stdlib only."""
import json
import re
import sys
from pathlib import Path

MIN_POST_CHARS = 1200
CLAIM = re.compile(r"\byour post\b|\byou (?:want|need|asked|said|wrote|mention(?:ed)?)\b|\bright now (?:it|they|your)\b|\bthe failures from your post\b|"
                   r"\bin your post\b|\byour (?:brief|posting|job post)\b", re.I)
SENT_END = ".!?"


def norm(s):
    """Quote matching ignores case, markdown emphasis, curly quotes, dashes and whitespace, nothing else."""
    s = str(s).replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    s = re.sub(r"[*_`#>]", "", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def in_post(quote, post):
    q = norm(quote).strip(" .,;:\"'")
    return len(q) >= 8 and q in norm(post)


def post_complete(text):
    """-> reasons the stored post is not the whole post (empty = complete)."""
    t = (text or "").rstrip()
    why = []
    if len(t) < MIN_POST_CHARS:
        why.append(f"post is {len(t)} chars, under {MIN_POST_CHARS}: a truncated feed excerpt, not the post (read the real post.md)")
    core = re.sub(r"[\s*_`\"'”’)\]]+$", "", t)
    last = t.splitlines()[-1].strip() if t else ""
    # a real Upwork post often ends on its details block ("Duration: More than 6 months") or a bullet list, with no full stop
    # (1291 and 8891 on Ra, 2026-11-24): a complete 'Key: value' line or list item is a legal end
    if re.match(r"^[A-Z][\w /&()-]{1,40}:\s+\S.*$", last) or re.match(r"^\s*(?:[-*•]|\d+[.)])\s+\S", last):
        return why
    if core and core[-1].isalnum():
        why.append(f"post ends mid-word or mid-sentence: ...{t[-40:]!r}")
    elif core and core[-1] not in SENT_END + ":":
        why.append(f"post has no final sentence end: ...{t[-40:]!r}")
    elif core and core[-1] == ":":
        why.append(f"post ends on a colon, the list after it is cut off: ...{t[-40:]!r}")
    return why


def seeded_reasons(items, post):
    """items: [{title, source}]. Every seeded title needs a source quote found verbatim in the post, and any id-like token in the title
    (RLY-1050: letters-digits, or a bare number) must itself appear in the post. -> reasons."""
    why = []
    for i, it in enumerate(items or [], 1):
        title = str((it or {}).get("title", "")).strip()
        src = str((it or {}).get("source", "")).strip()
        if not src:
            why.append(f"seed {i} {title[:40]!r}: no `source:` quote from the post")
        elif not in_post(src, post):
            why.append(f"seed {i} {title[:40]!r}: source quote {src[:50]!r} is not in the post")
        for tok in re.findall(r"\b[A-Za-z]*-?\d[\w-]*\b", title):
            if norm(tok) not in norm(post):
                why.append(f"seed {i} {title[:40]!r}: {tok!r} is not in the post (an invented id)")
    return why


def spoken_rows(script):
    """The rows read aloud, numbered from 1: every line that is not a heading, a comment or a bullet note (the cues file's row numbers)."""
    rows = []
    for l in script.splitlines():
        s = l.strip()
        if not s or s.startswith(("#", "<!--", "- ", "[", "|")):
            continue
        rows.append(s)
    return rows


def cue_table(cues):
    """-> [(set_of_row_numbers, script_says, [quotes])] from the `| row | script says | quote | cue |` table."""
    out = []
    for l in cues.splitlines():
        if not l.startswith("|"):
            continue
        cells = [c.strip() for c in l.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        m = re.fullmatch(r"(\d+)(?:\s*-\s*(\d+))?", cells[0])
        if not m:
            continue
        a, b = int(m.group(1)), int(m.group(2) or m.group(1))
        out.append((set(range(a, b + 1)), cells[1], re.findall(r'"([^"]+)"', cells[2])))
    return out


def claims_reasons(script, cues, post, skip=()):
    """Every claim row (CLAIM patterns) needs a cues row for its number whose quote is verbatim in the post. -> reasons naming the row."""
    table = cue_table(cues or "")
    why = []
    for n, row in enumerate(spoken_rows(script), 1):
        if not CLAIM.search(row) or row.strip() in skip:   # skip = the contract's own rows (intro card, close line)
            continue
        mine = [t for t in table if n in t[0]]
        if not mine:
            why.append(f"row {n} claims something about the post with no quote in the cues file: {row[:70]!r}")
        elif not any(in_post(q, post) for t in mine for q in t[2]):
            why.append(f"row {n} claim has no quote found verbatim in post.md: {row[:70]!r}")
    return why


def selftest():
    full = ("Project Overview. " + "We run a property company and built Relay, which includes an AI assistant that employees use every day. " * 12).strip()
    cut = "# Senior AI Agent Engineer ## Project Overview We operate a U.S.-based property management company and have developed Relay. The ass"
    post = full + " Prevent skipped steps, incorrect actions, and incomplete tasks. Improve browser automation and error recovery."
    script = "Hi, I'm Tyler.\nI read your post about Relay.\nYou want it to prevent skipped steps.\nYou want it to clicks Cancel instead of Submit.\nI built a demo.\n"
    cues = ('| row | says | quote | cue |\n|---|---|---|---|\n| 2 | I read your post about Relay. | "includes an AI assistant" | tab 1 |\n'
            '| 3 | You want it to prevent skipped steps. | "Prevent skipped steps, incorrect actions" | tab 1 |\n'
            '| 4 | You want it to clicks Cancel instead of Submit. | "clicks Cancel instead of Submit" | tab 1 |\n')
    ok = [post_complete(post) == [],
          any("under" in r for r in post_complete(cut)),                      # 9263's old text fails gate 1
          any("mid-word" in r for r in post_complete(post + " The ass")),
          any("final sentence" in r for r in post_complete(post + " and then -")),
          seeded_reasons([{"title": "Prevent skipped steps", "source": "Prevent skipped steps, incorrect actions"}], post) == [],
          any("no `source:`" in r for r in seeded_reasons([{"title": "RLY-1050 Cancel vs Submit"}], post)),   # the old RLY-1050 title fails gate 2
          any("RLY-1050" in r for r in seeded_reasons([{"title": "RLY-1050 Cancel vs Submit", "source": "Prevent skipped steps"}], post)),
          any("not in the post" in r for r in seeded_reasons([{"title": "Cancel", "source": "clicks Cancel instead of Submit"}], post)),
          claims_reasons(script.replace("You want it to clicks Cancel instead of Submit.\n", ""), cues, post) == [],
          any(r.startswith("row 4") for r in claims_reasons(script, cues, post)),                              # the invented claim names its row
          any(r.startswith("row 3") for r in claims_reasons(script, "", post))]
    print("self-test", "PASS" if all(ok) else f"FAIL {ok}")
    return 0 if all(ok) else 1


def main(argv):
    if argv[:1] == ["--self-test"]:
        return selftest()
    rd = lambda p: Path(p).read_text()  # noqa: E731
    if len(argv) == 2 and argv[0] == "post":
        rs = post_complete(rd(argv[1]))
    elif len(argv) == 3 and argv[0] == "seed":
        rs = seeded_reasons(json.loads(rd(argv[1])), rd(argv[2]))
    elif len(argv) == 4 and argv[0] == "claims":
        rs = claims_reasons(rd(argv[1]), rd(argv[2]), rd(argv[3]))
    else:
        print(__doc__)
        return 2
    print("FAIL" if rs else "PASS")
    for r in rs:
        print("   ", r)
    return 1 if rs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

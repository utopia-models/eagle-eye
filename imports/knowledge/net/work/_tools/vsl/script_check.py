#!/usr/bin/env python3
"""script_check.py: every VSL script follows the Mohamed-win template (net/work/upwork/RULES.md § H, knowledge#14508).

  script_check.py [FILE ...]      default: every *.md in net/work/vsl/scripts/   exit 0 = PASS, 1 = a script fails
  script_check.py --self-test
  --variant V  grade against a variant's bounds (vsl_variants.py: upwork-job 180 s and no Eagle Eye, youtube 300 s, ...)
  --asset  an asset take (no fixed opener; adds the professional-copy stage)   --copy  add that stage to any file   --no-copy  skip it
  No claim gate: Tyler 2026-11-18 13:35 MT, "I don't want any gates on claims" (knowledge#16020); the fact-ledger gate was deleted.

CLIENT-FIRST (Tyler, card 2026-11-21): every script is built backwards from what the client signals; our work appears only as
proof of their result. Beat order is copied from Nick Saraev's job-post Looms (see generic-agency-script.md `copied_from:`), not from our
own wins. A script carrying a `## Signals` block (or passed `signals=`) is graded client-first; `script_check.py FILE` always is:
  signals     a `## Signals` block with at least 3 verbatim client phrases
  opener      one verbatim client phrase in the first two spoken lines (the quoted phrase on screen is the proof a person read it)
  coverage    at least half of the listed client phrases are used in the spoken text
  ratio       you/your : I/my/we at least 2 : 1
  questions   every question under `Questions:` is answered (content-word overlap, or all words after `=>`)
  capability  no "we can do" / capability-first framing, and none of public-copy-check.py's look-at-us patterns
  length      the seconds labels match words / 2.5 within 15 percent
  banned      the banned-word list yields to the client's own words (a word quoted in Signals is allowed)
  outline     optional: only checked with outline=True / `<!-- outline: on -->`
The old seller-first opener ("I'm going through your whole post right now") is gone; vsl_template take, vsl_slot outline and vsl_ready
all build or grade client-first. A script with no client (youtube, eagle-eye variants) skips the client rules.
So a script (a file without `-context` in its name) must have:
  demo     a screen cue (`[horus]` or `(Horus)` line; `[horus]`/`(Horus)` still accepted as aliases) that shows THEIR demo, never the OCC
  length   numbered parts whose `(N s)` add up to 300 s (5 min, the YouTube ceiling) or less, and at most 750 spoken words (2.5 words a second);
           Upwork VSLs are 2-3 min by Tyler's rule, a per-variant bound is a build item (knowledge#16020)
  closing  exactly one closing next-step statement ("The next build is X behind this same approval gate, and I can start it the day you
           reply."), no question mark in any spoken line, no "reply here" ask (Tyler 2026-11-17 12:48 AM: every lost proposal used one)
  never    no agent/fleet/OCC talk in a spoken line; nowhere in the file "team of AI agents" or "setup call"
A `-context.md` file (read by Tyler, never on the prompter) only has to be free of the two banned lines.
stdlib only.
"""
import importlib.util
import math
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "vsl" / "scripts"
# One closing next-step statement: a sentence saying what is built next or that work can start.
NEXT_STEP = re.compile(r"\b(?:the next (?:build|step|module)\b|I (?:can|will) (?:start|begin)|(?:fifteen|15)[- ]minutes?\b.*\blive\b)", re.I)
REPLY_ASK = re.compile(r"\breply (?:here|to (?:this|my))\b|\bsend (?:me )?a message\b|\bget in touch\b", re.I)
MAX_S, MAX_WORDS = 300, 750   # Tyler 2026-11-18: Upwork 2-3 min, YouTube up to 5; the 90 s cap is gone (knowledge#16020)
BANNED_ANYWHERE = [r"team of (?:ai )?agents", r"setup call"]
BANNED_SPOKEN = [r"\bagents?\b", r"\bOCC\b", r"\bfleet\b", r"\bmy own setup\b",
                 r"\bbook (?:a|the)\b", r"\bmessage me\b", r"\bget on a call\b"]
PART = re.compile(r"^## \d+\s*·.*?\((\d+)\s*s\)", re.M)
CUE = re.compile(r"^\s*(?:\[(?:horus|horus)\]|\((?:Horus|Horus)\))", re.I)   # [horus]/(Horus): the pre-rename alias


def spoken(text):
    """Lines Tyler says: inside numbered parts, not a `[horus]` action, a list item or a comment. `(Horus)` lines are
    spoken (Tyler skips the marker)."""
    out, inpart = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            inpart = bool(re.match(r"## \d", line))
            continue
        s = line.strip()
        if not inpart or not s or s.startswith(("[", "-", "<!--", ">")):
            continue
        out.append(re.sub(r"^\((?:Horus|Horus)\)\s*", "", s, flags=re.I))
    return out


OUTLINE_WORDS = 25   # ~10 s at 2.5 words a second (Tyler 2026-11-17, knowledge#15018)
OUTLINE = [("diagram", re.compile(r"\b(?:architecture )?diagram\b", re.I)), ("demo", re.compile(r"\bdemo\b", re.I)),
           ("next step", re.compile(r"\bwhat I (?:will )?build next\b|\bnext (?:build|step|module)\b", re.I))]


def outline_reasons(lines):
    """Every demo VSL names its outline in the first ~10 s, in order: the architecture diagram, the demo, the next step."""
    head = " ".join(" ".join(lines).split()[:OUTLINE_WORDS])
    at = [(n, m.start()) for n, p in OUTLINE for m in [p.search(head)] if m]
    if [n for n, _ in at] != [n for n, _ in OUTLINE] or [i for _, i in at] != sorted(i for _, i in at):
        return [f"outline: the first {OUTLINE_WORDS} spoken words (~10 s) must name the diagram, then the demo, then the next step, in that order "
                "(e.g. 'I will show an architecture diagram, then a demo, then what I build next.')"]
    return []


# ---------------------------------------------------------------- client-first (Tyler 2026-11-21)
COVERAGE_MIN, RATIO_MIN, LABEL_TOL, MIN_PHRASES = 0.5, 2.0, 0.15, 3
YOU = re.compile(r"\b(?:you|your|yours|yourself|you're|you'd|you'll|you've)\b", re.I)
ME = re.compile(r"\b(?:i|i'm|i'll|i've|i'd|my|me|mine|myself|we|we're|we'll|we've|our|ours|us)\b", re.I)
CAPABILITY = [(r"\bwe can (?:do|build|help|handle|deliver)\b", '"we can do" capability framing'),
              (r"\bwe (?:specialize|specialise|offer|provide|are experts?)\b", "capability-first framing"),
              (r"\bI (?:specialize|specialise) in\b", "capability-first framing"),
              (r"\bour (?:team|expertise|capabilities|services|experience)\b", "capability-first framing"),
              (r"\bI can do (?:anything|everything|all)\b", "capability-first framing")]
STOP = set("the a an and or of to in on for with is are was were be been it this that these those your you my me i we our at as by from "
           "which what who how when where why do does did can could would should will have has had not no yes any about into over "
           "than then so if but they their them his her its own one more".split())


def norm(s):
    return " ".join(re.sub(r"[^a-z0-9' ]+", " ", s.lower().replace("’", "'")).split())


def grams(s, n=3):
    w = norm(s).split()
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


def parse_signals(text):
    """The `## Signals` block -> {key: [strings]} (keys lower-case: phrases, outcome, fear, deadline, stack, budget, questions,
    last message, channel); None when the file has no block. A quoted string is taken whole; an unquoted value is the line text.
    A question may end `=> word, word`: those words must all be spoken."""
    m = re.search(r"^## Signals\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m:
        return None
    out, key = {}, None
    for line in m.group(1).splitlines():
        top = re.match(r"^- ([A-Za-z][A-Za-z ]*?):\s*(.*)$", line)
        sub = re.match(r"^\s+-\s+(.*)$", line)
        if top:
            key, rest = top.group(1).lower(), top.group(2).strip()
            out.setdefault(key, [])
            if rest:
                out[key] += re.findall(r"[\"“](.+?)[\"”]", rest) or [rest]
        elif sub and key:
            rest = sub.group(1).strip()
            if key == "questions":
                out[key].append(rest)
            else:
                out[key] += re.findall(r"[\"“](.+?)[\"”]", rest) or [rest]
    return out


def _lookalike():
    """public-copy-check.py's LOOK_AT_US patterns (our own setup as the subject); [] if the file is not beside this repo."""
    try:
        f = Path(__file__).resolve().parents[4] / "_infra" / "scripts" / "public-copy-check.py"
        sp = importlib.util.spec_from_file_location("public_copy_check", f)
        mod = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(mod)
        return list(mod.LOOK_AT_US)
    except Exception:
        return []


def client_text(sig):
    return " ".join(x for k, v in sig.items() if k != "questions" for x in v) + " " + " ".join(sig.get("questions", []))


def client_reasons(text, lines, sig, asset=False):
    rs = []
    phrases = sig.get("phrases", [])
    if len(phrases) < MIN_PHRASES:
        rs.append(f"signals: {len(phrases)} verbatim client phrases under `Phrases:` (need {MIN_PHRASES}+, quoted from the post)")
    body = norm(" ".join(lines))
    head = norm(" ".join(lines[:2]))
    if phrases and not any(norm(p) in head for p in phrases if len(norm(p).split()) >= 3):
        rs.append("opener: none of the client's verbatim phrases is in the first two spoken lines; open on what they asked for, in their words")
    if phrases:
        spoken_grams = grams(body)

        def used(p):
            g = grams(p)
            return norm(p) in body or (g and len(g & spoken_grams) / len(g) >= 0.6)
        n = sum(1 for p in phrases if used(p))
        if n / len(phrases) < COVERAGE_MIN:
            rs.append(f"coverage: {n} of {len(phrases)} client phrases are spoken (< {int(COVERAGE_MIN * 100)}%); use their words, not ours")
    you, me = len(YOU.findall(" ".join(lines))), len(ME.findall(" ".join(lines)))
    if (me and you / me < RATIO_MIN) or (not me and not you):
        rs.append(f"ratio: you/your {you} : I/my/we {me} is under {RATIO_MIN:g} : 1; the script is about us, not them")
    for q in sig.get("questions", []):
        q, _, key = q.partition("=>")
        q = q.strip().strip("\"“”")
        if key.strip():
            ok = all(norm(k) in body for k in key.split(",") if k.strip())
        else:
            cw = {w for w in norm(q).split() if w not in STOP and len(w) > 2}
            ok = (not cw) or len(cw & set(body.split())) / len(cw) >= 0.5
        if not ok:
            rs.append(f"questions: the client's question is not answered in the script: {q[:80]!r}")
    for l in lines:
        for p, why in CAPABILITY:
            if re.search(p, l, re.I):
                rs.append(f"capability: {why}: {l[:70]!r}")
    ct = client_text(sig)
    for p, why in _lookalike():
        if re.search(p, ct, re.I):
            continue
        for l in lines:
            if re.search(p, l, re.I):
                rs.append(f"capability: {why}: {l[:70]!r}")
    for l in lines:
        if re.search(r"<[^>]+>", l):
            rs.append(f"placeholder: unfilled <...> in a spoken line: {l[:70]!r}")
    secs, words = sum(int(s) for s in PART.findall(text)), sum(len(l.split()) for l in lines)
    if secs and abs(words / 2.5 - secs) / secs > LABEL_TOL:
        rs.append(f"length: parts are labelled {secs} s but {words} words read in {words / 2.5:.0f} s (> {int(LABEL_TOL * 100)}% apart)")
    return rs


def check(text, context=False, asset=False, copy=False, variant=None, signals=None, client_first=None, outline=None):
    """-> list of reasons; empty = PASS. `variant` (vsl_variants.py) swaps in that variant's length bound, closing rule and Eagle Eye ban."""
    var = None
    if variant:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import vsl_variants
        var = vsl_variants.get(variant)
        max_s, max_words = var["max_s"], vsl_variants.max_words(variant)
    else:
        max_s, max_words = MAX_S, MAX_WORDS
    sig = signals if signals is not None else parse_signals(text)
    if client_first is None:
        client_first = sig is not None
    if client_first and sig is None:
        sig = {}
    ct = client_text(sig) if sig else ""
    allow = lambda p: bool(ct) and re.search(p, ct, re.I)   # the client's own words pass the banned list
    rs = [f"banned line: /{p}/" for p in BANNED_ANYWHERE if re.search(p, text, re.I) and not allow(p)]
    if client_first and not sig:
        rs.append("signals: no `## Signals` block (exact client phrases, outcome, fear, deadline, stack, budget, questions, last message)")
    if var:
        rs += vsl_variants.eagle_reasons(text, variant)
    if context:
        return rs
    lines = spoken(text)
    if client_first:
        if sig:
            rs += client_reasons(text, lines, sig, asset)
    if outline or "<!-- outline: on -->" in text:
        rs += outline_reasons(lines)
    cues = [l for l in text.splitlines() if CUE.match(l)]
    cue_re = r"\bdemo\b|first build|what I built" + (r"|\b(?:your|their|his|her|post|milestone|list|repo|site|brief)\b" if client_first else "")
    if not any(re.search(cue_re, c, re.I) for c in cues):
        rs.append("demo: no [horus]/(Horus) cue shows their demo" if not client_first else "demo: no cue shows a client-named artifact (their post, their list, their demo)")
    if any(re.search(r"\bOCC\b", c) for c in cues):
        rs.append("demo: a cue shows the OCC")
    secs = [int(s) for s in PART.findall(text)]
    if not secs:
        rs.append("length: no numbered part carries its seconds, e.g. '## 1 · Opener (5 s)'")
    elif sum(secs) > max_s:
        rs.append(f"length: parts add up to {sum(secs)} s (> {max_s} s)")
    words = sum(len(l.split()) for l in lines)
    if words > max_words:
        rs.append(f"length: {words} spoken words (> {max_words}, about {max_s} s)")
    for l in lines:
        if "?" in l:
            rs.append(f"question: no question mark in a spoken line, close with a statement: {l[:80]!r}")
        m = REPLY_ASK.search(l) if not (var and var["closing"] == "none") else None
        if m:
            rs.append(f"closing: '{m.group(0)}' is a reply ask; state the next build instead: {l[:80]!r}")
    last = []
    for l in lines:
        last += [x for x in re.split(r"(?<=[.!])\s+", l) if x.strip()]
    steps = [x for x in last if NEXT_STEP.search(x)]
    if var and var["closing"] == "none":
        pass
    elif len(steps) != 1:
        rs.append(f"closing: {len(steps)} next-step statements (exactly one): " + (" | ".join(x[:60] for x in steps) or
                  "add 'The next build is <module> behind this same approval gate, and I can start it the day you reply.'"))
    elif last and steps[0] != last[-1]:
        rs.append(f"closing: the next-step statement must be the last spoken sentence, not: {last[-1][:80]!r}")
    for l in lines:
        for p in (BANNED_SPOKEN[1:] if asset else BANNED_SPOKEN):
            if re.search(p, l, re.I) and not allow(p):
                rs.append(f"spoken /{p}/: {l[:70]!r}")
    if copy:   # the professional-copy stage (vsl_copy.py): banned phrases, speakability, technical register, Vale
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import vsl_copy
        rs += vsl_copy.check_copy(text)[0]
    return rs


# PLAIN SPEECH (Tyler 2026-11-22 7:38 "short sentences, no conjunction chains, client-first, one idea per line"; contract `style:`).
# Sources: digital.gov plain-language guide ("split a long idea so each one is the subject of its own sentence"); the Oxford Guide to
# Plain English / GOV.UK average of ~15 words (max ~25) as cited by the readability-guidelines wiki and the PRISM guide (average <= 15);
# Sendspark / Nutshell / Close video-prospecting guides (hook in the first 5 s, intro videos 30-45 s, one call to action).
MAX_SENT_WORDS = 20      # a spoken sentence; the cited guidance averages 15 and caps at 25
MAX_JOINERS = 1          # clause joiners in one sentence: ", and" / ", but" / ", so" / ", which" / because / while / although
JOINER = re.compile(r",\s*(?:and|but|so|which)\b|\b(?:because|while|although)\b", re.I)
INTRO_MAX_WORDS = 45     # ~15 s at the contract's 2.75 words a second (intro 10-21 s)


def sentences(line):
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+", line.strip()) if x.strip()]


def plain_notes(lines):
    """Advisory (never blocks a full script): one idea per line, short sentences, no conjunction chains."""
    notes = []
    for ln in lines:
        ss = sentences(ln)
        if len(ss) > 1:
            notes.append(f"one idea per line: {len(ss)} sentences on one line: '{ln[:60]}'")
        for x in ss:
            n = len(x.split())
            if n > MAX_SENT_WORDS:
                notes.append(f"sentence of {n} words (max {MAX_SENT_WORDS}): '{x[:60]}'")
            if len(JOINER.findall(x)) > MAX_JOINERS:
                notes.append(f"conjunction chain: '{x[:60]}'")
    return notes


def intro_reasons(text, title=None):
    """Blocking grade for an intro-line.md (Tyler's live ~15 s): plain speech, names their job, hands off to the voice, nothing else."""
    body = " ".join(l.strip() for l in text.splitlines() if l.strip() and not l.startswith(("#", "<!--", ">")))
    rs = []
    n = len(body.split())
    if n > INTRO_MAX_WORDS:
        rs.append(f"intro: {n} words, max {INTRO_MAX_WORDS} (about 15 s)")
    if not re.search(r"\bTyler Youk\b", body):
        rs.append("intro: says his name, Tyler Youk")
    norm_t = lambda x: x.lower().replace("&", "and")
    if title and not re.search(re.escape(norm_t(title).split(" for ")[0].split(" | ")[0].strip()), norm_t(body)):
        rs.append(f"intro: names their job ({title.split(' | ')[0][:50]})")
    if not re.search(r"\bdiagram\b", body, re.I) or not re.search(r"\b(?:MVP|working version)\b", body, re.I):
        rs.append("intro: says it has an architecture diagram and an MVP (or working version) ready")
    if not re.search(r"\bmy voice agent\b", body, re.I):
        rs.append("intro: hands off to the voice ('my voice agent will walk you through it', the approved words)")
    for p, why in ((r"\?", "no question"), (r"\$\s?\d|\bprice\b|\brate\b|\bper hour\b", "no price"), (r"https?://|www\.|@\w", "no link or handle"),
                   (r"\b(?:sample|first version)\b", "never 'sample' or 'first version'")):
        if re.search(p, body, re.I):
            rs.append(f"intro: {why}")
    lines = [l.strip() for l in text.splitlines() if l.strip() and not l.startswith(("#", "<!--", ">"))]
    rs += [f"intro: {x}" for x in plain_notes(lines)]
    return rs


def vsl_variants_closing_none(variant):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import vsl_variants
    return vsl_variants.get(variant)["closing"] == "none"


def claim_gate(f, post_arg=None):
    """knowledge#17487: a row that claims something about the post needs a quote in <stem>.cues.md found verbatim in the post.
    Runs when the script has a cues sidecar or --post is given. The post: --post FILE, or the `hunts/upwork/<slug>/post.md` the cues header names."""
    import post_integrity
    cues = f.with_name(f.stem + ".cues.md")
    if not cues.is_file() and not post_arg:
        return []
    ctext = cues.read_text() if cues.is_file() else ""
    post = Path(post_arg) if post_arg else None
    if post is None:
        m = re.search(r"hunts/upwork/([\w.-]+)/post\.md", ctext)
        cfg = SCRIPTS.parent / "oneshot-auto.yaml"
        hd = re.search(r"^hunts_dir:\s*(\S+)", cfg.read_text(), re.M) if cfg.is_file() else None
        if m and hd and (Path(hd.group(1)) / m.group(1) / "post.md").is_file():
            post = Path(hd.group(1)) / m.group(1) / "post.md"
    if post is None or not post.is_file():
        return ["claims: post.md not found (pass --post FILE); every claim about the post must quote it"]
    return post_integrity.claims_reasons(f.read_text(), ctext, post.read_text())


def files(args):
    return [Path(a) for a in args] if args else sorted(SCRIPTS.glob("*.md"))


def main(argv):
    if argv[:1] == ["--self-test"]:
        return selftest()
    variant = argv[argv.index("--variant") + 1] if "--variant" in argv else None
    if variant:
        argv = [a for i, a in enumerate(argv) if a != "--variant" and (i == 0 or argv[i - 1] != "--variant")]
    post_arg = argv[argv.index("--post") + 1] if "--post" in argv else None
    if post_arg:
        argv = [a for i, a in enumerate(argv) if a != "--post" and (i == 0 or argv[i - 1] != "--post")]
    asset = "--asset" in argv
    copy = (asset or "--copy" in argv) and "--no-copy" not in argv   # take scripts (--asset) always get the copy stage
    intro = "--intro" in argv
    argv = [a for a in argv if a not in ("--asset", "--copy", "--no-copy", "--intro")]
    bad = 0
    if intro:   # script_check.py --intro FILE [--title "their job title"]: grade intro-line.md files, blocking
        title = argv.pop(argv.index("--title") + 1) if "--title" in argv else None
        argv = [a for a in argv if a != "--title"]
        for f in map(Path, argv):
            rs = intro_reasons(f.read_text(), title)
            print(("FAIL" if rs else "PASS"), f)
            for r in rs:
                print("   ", r)
            bad += bool(rs)
        return 1 if bad else 0
    for f in files(argv):
        cf = None if (variant and vsl_variants_closing_none(variant)) else True   # the CLI grades client-first; youtube/eagle-eye have no client
        rs = check(f.read_text(), context="-context" in f.name, asset=asset, copy=copy, variant=variant, client_first=cf)
        if asset and "-context" not in f.name:
            import vsl_build   # the build stamp: a script typed from nothing is refused, knowledge#15137
            rs += vsl_build.check(f)
        rs += claim_gate(f, post_arg)
        print(("FAIL" if rs else "PASS"), f)
        for r in rs:
            print("   ", r)
        if "-context" not in f.name:   # advisory plain-speech notes: never fail a script
            for r in plain_notes(spoken(f.read_text()))[:5]:
                print("    note:", r)
        bad += bool(rs)
    print(f"{bad} failing" if bad else "PASS")
    return 1 if bad else 0


def selftest():
    good = (f"# 90-second video: x\n## Do not say\n- a price\n## 1 · Opener (5 s)\n[horus] Their post.\nHi, it's Tyler. "
            f"I read your whole post.\nI will show an architecture diagram, then a demo, then what I build next.\n## 2 · Your demo (60 s)\n(Horus) Here's the demo I built for your post.\nIt reads the mail.\n"
            f"## 3 · Next step (10 s)\nThe next build is the invoice module behind this same approval gate, and I can start it the day you reply.\n")
    ok = [check(good) == [],
                    any("demo" in r for r in check(good.replace("Here's the demo I built for your post.", "Here's the OCC."))),
          any("length" in r for r in check(good.replace("(60 s)", "(300 s)"))),
          any("closing" in r for r in check(good.replace("The next build is the invoice module behind this same approval gate, and I can start it the day you reply.", "Reply here and I'll send the next build."))),
          any("question" in r for r in check(good.replace("It reads the mail.", "Which inbox?"))),
          any("banned" in r for r in check(good + "- Say a team of AI agents.\n")),
          any("spoken" in r for r in check(good.replace("It reads the mail.", "My agents read the mail."))),
          check("We'll book a setup call.", context=True) != [],
          check("Sample members only.", context=True) == [],
          any("outline" in r for r in check(good.replace("then a demo, then what I build next", "then more"), outline=True)),
          any("outline" in r for r in check(good.replace("an architecture diagram, then a demo", "a demo, then an architecture diagram"), outline=True)),
          not any("outline" in r for r in check(good.replace("then a demo, then what I build next", "then more"))),
          check(good.replace("[horus]", "[horus]").replace("(Horus)", "(Horus)")) == []]
    good_intro = "Hi, I'm Tyler Youk.\nI read your AI Automation Architect post.\nI have an architecture diagram and an MVP ready for your AI chief of staff.\nMy voice agent will walk you through it.\nI'm just here to introduce it.\n"
    ok += [intro_reasons(good_intro, "AI Automation Architect | Build My OS") == [],
           any("max" in r for r in intro_reasons(good_intro + "word " * 40)),
           any("question" in r for r in intro_reasons(good_intro + "Ready?")),
           any("voice" in r for r in intro_reasons(good_intro.replace("My voice agent will walk you through it.", "I will walk you through it."))),
           any("conjunction" in r for r in plain_notes(["I built it, and it runs, and it logs, which helps."])),
           any("max" in r for r in plain_notes(["word " * 21 + "end."])),
           plain_notes(["I read your post."]) == []]
    print("self-test", "PASS" if all(ok) else f"FAIL {ok}")
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

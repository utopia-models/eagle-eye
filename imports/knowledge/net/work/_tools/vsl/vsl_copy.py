#!/usr/bin/env python3
"""vsl_copy.py: the 'professional copy' stage of the VSL gate (Tyler 2026-11-17: the scripts read 'very unprofessional and non-technical').

  vsl_copy.py FILE... [--require-vale]     exit 0 = PASS, 1 = findings      (script_check.py calls check_copy() too)

Three layers, strongest first:
  1 banned    a regex list, seeded with Tyler's words (BANNED below), plus any contraction (CONTRACTION). Hard fail.
  2 speak     the script is READ ALOUD by an engineer: no spoken sentence over MAX_SENT words, mean sentence length
              at most MAX_MEAN, no sentence that strings five or more clauses, and at least MIN_TECH concrete technical
              terms (a pitch to engineers names the mechanism). Hard fail.
  3 vale      the Vale prose linter (MIT, https://vale.sh) over the spoken text with vale/.vale.ini: our Spoken style plus
              Google, Microsoft, write-good, proselint, alex rules. Spoken.* errors fail; every other alert is advice,
              printed but never failing (a passive like 'is marked failed' is correct engineering prose). Skipped with a
              note when no binary is found (VALE_BIN, then PATH, then ~/dev/utopia-models/_wt-copyskill-tools/vale/vale);
              --require-vale fails then.
Stages 1 and 2 are stdlib only, so the gate never depends on a download.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VALE_INI = HERE / "vale" / ".vale.ini"

# Tyler's list first; the rest are the same register (filler, hype, hedge).
BANNED = [r"\bI just built (?:this|it) for you\b", r"\bhelpers?\b", r"\bfirst version\b", r"\bfor whoever runs this job\b", r"\bbasically\b", r"\bamazing\b",
          r"\bsuper\b", r"\ba bunch of\b", r"\bawesome\b", r"\bgame[- ]chang\w+", r"\bcutting[- ]edge\b",
          r"\bliterally\b", r"\bkind of\b", r"\bsort of\b", r"\bpretty much\b", r"\band stuff\b", r"\bthings like that\b",
          r"\bI think\b", r"\bseems like\b", r"\bhey guys\b", r"\bcool\b", r"\bgonna\b", r"\bwanna\b"]
# Tyler 2026-11-17 1:28 AM: price lives in the bid field, never in the video; saying it announces a discount and frames the price as an apology.
RATE = [r"\bbidding low\b", r"\bbid low\b", r"\blow bid\b", r"\bdiscount\w*", r"\bcheap\w*", r"\baffordable rate\b", r"\bmy rate\b",
        r"\bfor a lower price\b", r"\bI know I am\b", r"\bI understand that we are\b"]
RATE_MSG = "rate/apology language: price belongs in the bid field, not the video"
# Tyler 2026-11-17 12:26 AM: a spoken take has no contractions ("I am", never "I'm"). A possessive ("Tyler's") is not one.
CONTRACTION = re.compile(r"\b(?:\w+n['\u2019]t|\w+['\u2019](?:re|ve|ll|m|d)|(?:it|that|there|here|what|let|who|he|she|how|where|when)['\u2019]s)\b", re.I)
MAX_SENT, MAX_MEAN, MIN_TECH = 28, 20, 3
TECH = re.compile(r"\b(?:api|apis|queue|webhook|schema|database|ledger|log|audit|retry|retries|deterministic|idempotent|"
                  r"endpoint|pipeline|parser|extract\w*|route\w*|tool calling|tunnel|sandbox|cron|batch|latency|throughput|"
                  r"validat\w+|reconcil\w+|approval gate|human-in-the-loop|llm|claude|json|sql|postgres|python|next\.js|"
                  r"quickbooks|gmail|oauth|rate limit\w*|dedup\w*|checkpoint\w*|timeout|fail(?:s|ed|ure)?|resum\w+)\b", re.I)


def spoken_text(text):
    """The lines Tyler reads, via script_check.spoken (numbered parts, no cues, no list items)."""
    sys.path.insert(0, str(HERE))
    import script_check
    return script_check.spoken(text)


def sentences(lines):
    out = []
    for l in lines:
        out += [s.strip() for s in re.split(r"(?<=[.?!])\s+", l) if s.strip()]
    return out


def find_vale():
    for c in (os.environ.get("VALE_BIN"), shutil.which("vale"),
              str(Path.home() / "dev/utopia-models/_wt-copyskill-tools/vale/vale")):
        if c and Path(c).exists():
            return c
    return None


def run_vale(lines):
    """-> (errors, advice, note). Runs Vale on the spoken lines written to a temp .md next to the config."""
    vale = find_vale()
    if not vale:
        return [], [], "vale: no binary (set VALE_BIN); stages 1 and 2 ran"
    if not (VALE_INI.parent / "styles" / "Google").exists():
        subprocess.run([vale, "--config", str(VALE_INI), "sync"], capture_output=True, cwd=VALE_INI.parent)
    tmp = VALE_INI.parent / f".spoken-{os.getpid()}.md"
    tmp.write_text("\n\n".join(lines) + "\n")
    try:
        p = subprocess.run([vale, "--config", str(VALE_INI), "--output", "JSON", str(tmp)],
                           capture_output=True, text=True, cwd=VALE_INI.parent)
        data = json.loads(p.stdout or "{}")
    except Exception as e:
        return [], [], f"vale: could not run ({e})"
    finally:
        tmp.unlink(missing_ok=True)
    errs, adv = [], []
    for alerts in data.values():
        for a in alerts:
            msg = f"vale {a['Check']}: {a['Message']} (line {a['Line']}: '{a['Match']}')"
            (errs if a["Check"].startswith("Spoken.") and a["Severity"] == "error" else adv).append(msg)
    return errs, adv, ""


def check_copy(text, vale=True, require_vale=False):
    """-> (reasons, advice). Empty reasons = PASS."""
    lines = spoken_text(text)
    rs, adv = [], []
    for l in lines:
        for p in BANNED:
            m = re.search(p, l, re.I)
            if m:
                rs.append(f"copy banned '{m.group(0)}': {l[:70]!r}")
    for l in lines:
        for p in RATE:
            m = re.search(p, l, re.I)
            if m:
                rs.append(f"copy {RATE_MSG}: '{m.group(0)}' in {l[:70]!r}")
    for l in lines:
        for m in CONTRACTION.finditer(l):
            rs.append(f"copy contraction '{m.group(0)}': write it out ({l[:60]!r})")
    sents = sentences(lines)
    lens = [len(s.split()) for s in sents]
    for s, n in zip(sents, lens):
        clauses = len(re.findall(r",|\band\b", s)) + 1
        if n > MAX_SENT:
            rs.append(f"speak: {n}-word sentence (> {MAX_SENT}), split it: {s[:60]!r}")
        elif clauses >= 6:
            rs.append(f"speak: {clauses} clauses in one breath: {s[:60]!r}")
    if lens and sum(lens) / len(lens) > MAX_MEAN:
        rs.append(f"speak: mean sentence {sum(lens) / len(lens):.1f} words (> {MAX_MEAN})")
    tech = {m.group(0).lower() for l in lines for m in TECH.finditer(l)}
    if lines and len(tech) < MIN_TECH:
        rs.append(f"technical: only {len(tech)} concrete technical terms {sorted(tech)}, need {MIN_TECH}; name the mechanism")
    if vale and lines:
        e, a, note = run_vale(lines)
        rs += e
        adv += a
        if note:
            (rs if require_vale else adv).append(note)
    return rs, adv


def main(argv):
    req = "--require-vale" in argv
    bad = 0
    for p in [a for a in argv if not a.startswith("--")]:
        rs, adv = check_copy(Path(p).read_text(), require_vale=req)
        print(("FAIL" if rs else "PASS"), p)
        for r in rs:
            print("   ", r)
        for a in adv:
            print("    advice:", a)
        bad += bool(rs)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""vsl_judge.py: the autonomous rubric judge, reference match and its calibration gate (Part of #15166).

  vsl_judge.py compare A.md B.md          rubric scores of both scripts, run in BOTH orderings (position bias cancelled)
  vsl_judge.py judge DRAFT.md [-k 1]      the draft against the nearest exemplar(s): verdict + per-beat reference-match table
  vsl_judge.py match DRAFT.md [-k 2]      the reference-match table only (no model call)
  vsl_judge.py calibrate                  rank every known (good, rejected) pair from the corpus labels; exit 0 only at the pass bar

Judge = a second `claude -p` call (VSL_LLM_CMD) with prompts/judge.md: four criteria (persuasion, professionalism, specificity, terminology)
per beat, 1-5. A score is the mean over both orderings, so a script that wins only when shown first scores a tie.
The judge becomes a gate when `calibrate` passes: PASS_BAR of the good-vs-rejected pairs must rank correctly in BOTH orderings, with at
least MIN_PAIRS pairs. Pairs and labels are derived by vsl_labels.py from proposals.db and the copy gate, never labelled by hand.
"""
import difflib
from concurrent.futures import ThreadPoolExecutor
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]
sys.path.insert(0, str(HERE))
import script_check  # noqa: E402
import vsl_labels  # noqa: E402
import vsl_ref  # noqa: E402

CRITERIA = ("persuasion", "professionalism", "specificity", "terminology")
PASS_BAR = 0.85          # share of known pairs ranked correctly in both orderings: with 4 pairs that is all of them
MIN_PAIRS = 3
GOOD, BAD = ("accepted", "won"), ("rejected",)
HEAD = re.compile(r"^## (\d+)\s*·\s*(.+?)\s*(?:\((\d+)\s*s\))?\s*$", re.M)


def beats(text):
    """-> [{n, name, seconds, spoken}] for each numbered part; the spoken text only (cues and notes dropped)."""
    out, cur = [], None
    for line in text.splitlines():
        m = HEAD.match(line)
        if m:
            cur = {"n": int(m.group(1)), "name": m.group(2).strip(), "seconds": int(m.group(3) or 0), "lines": []}
            out.append(cur)
        elif line.startswith("## "):
            cur = None
        elif cur is not None:
            s = line.strip()
            if s and not s.startswith(("[", "-", "<!--", ">")):
                cur["lines"].append(re.sub(r"^\((?:Horus|Horus)\)\s*", "", s, flags=re.I))
    return [{"n": b["n"], "name": b["name"], "seconds": b["seconds"], "spoken": " ".join(b["lines"])} for b in out]


def body_of(path):
    return vsl_ref.front(Path(path).read_text(errors="replace"))[1]


def llm(text):
    p = subprocess.run(os.environ.get("VSL_LLM_CMD", "claude -p").split(), input=text, capture_output=True, text=True, timeout=600)
    if p.returncode:
        raise RuntimeError(f"model command failed: {p.stderr[:200]}")
    return p.stdout.strip()


def prompt(a, b, names):
    t = re.sub(r"<!--.*?-->\n?", "", (HERE / "prompts/judge.md").read_text())
    render = lambda bs: "\n".join(f"[{x['name']}] {x['spoken']}" for x in bs)  # noqa: E731
    return t.format(a=render(a), b=render(b), beats=", ".join(names))


def parse(raw):
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError("judge returned no JSON: " + raw[:120])
    d = json.loads(m.group(0))
    total = lambda rows: sum(sum(int(r[c]) for c in CRITERIA) for r in rows) / max(len(rows), 1)  # noqa: E731
    return total(d["a"]), total(d["b"]), d.get("why", ""), d


def score_pair(x, y, model=llm):
    """-> (mean score of x, mean score of y, detail). x and y are beat lists. Both orderings are run; the model sees each script in
    both the A and the B slot, so a position preference cancels."""
    names = [b["name"] for b in x]
    xa, yb, why1, _ = parse(model(prompt(x, y, names)))
    yb2, xb, why2, _ = parse(model(prompt(y, x, names)))
    return (xa + xb) / 2, (yb + yb2) / 2, {"x_first": (xa, yb), "y_first": (xb, yb2), "why": [why1, why2]}


def wins_both(x, y, model=llm):
    """True only when x outscores y in each ordering separately (the acceptance: higher in both orderings)."""
    names = [b["name"] for b in x]
    with ThreadPoolExecutor(2) as ex:
        f1, f2 = ex.submit(model, prompt(x, y, names)), ex.submit(model, prompt(y, x, names))
        a1, b1, _, _ = parse(f1.result())
        b2, a2, _, _ = parse(f2.result())
    return a1 > b1 and a2 > b2, {"x_first": (a1, b1), "y_first": (a2, b2)}


def exemplars(text, k=2):
    """Nearest exemplars: accepted/won/exemplar scripts, by BM25 over the draft's spoken text. The draft itself (identical spoken text) is skipped."""
    spoken = " ".join(script_check.spoken(text)) or text
    own = " ".join(b["spoken"] for b in beats(text))
    out = []
    for h in vsl_ref.search(spoken, k + 4):
        if " ".join(b["spoken"] for b in beats(body_of(WORK / h["path"]))) != own:
            out.append(h)
    return out[:k]


def match_table(text, k=2):
    """Per draft beat: the closest beat of each top-k exemplar (token overlap), its provenance and a word diff. -> (rows, hits)."""
    hits = exemplars(text, k)
    draft = beats(text)
    rows = []
    for h in hits:
        eb = beats(body_of(WORK / h["path"]))
        src = h["source_url"] or f"net/work/{h['path']}"
        for b in draft:
            toks = set(re.findall(r"[a-z0-9]+", b["spoken"].lower()))
            best, sim = None, 0.0
            for e in eb:
                et = set(re.findall(r"[a-z0-9]+", e["spoken"].lower()))
                s = len(toks & et) / max(len(toks | et), 1)
                if s > sim or best is None:
                    best, sim = e, s
            diff = ""
            if best:
                sm = difflib.SequenceMatcher(None, b["spoken"].split(), best["spoken"].split())
                diff = f"shared {round(sm.ratio() * 100)}% of words; draft {len(b['spoken'].split())}w vs exemplar {len(best['spoken'].split())}w"
            rows.append({"beat": b["name"], "exemplar": h["path"], "exemplar_beat": best["name"] if best else "(none)", "overlap": round(sim, 2),
                         "diff": diff, "status": h["status"], "source": src})
    return rows, hits


def print_table(rows):
    print(f"{'draft beat':26} {'exemplar beat':26} {'sim':>4}  status      exemplar (provenance)")
    for r in rows:
        print(f"{r['beat'][:26]:26} {r['exemplar_beat'][:26]:26} {r['overlap']:4.2f}  {r['status']:11} {r['exemplar']}  <{r['source']}>")
        print(f"{'':26}   diff: {r['diff']}")


def known_pairs():
    """(good_path, bad_path) for every accepted/won script against every rejected script of the same family (golden vN_<job> files share one
    job; other pairs are not comparable), derived from the labels."""
    lab = vsl_labels.merged_status()
    good = [r for r, v in lab.items() if v.get("status") in GOOD and (WORK / r).is_file() and "/exemplars/" not in r and beats(body_of(WORK / r))]
    bad = [r for r, v in lab.items() if v.get("status") in BAD and (WORK / r).is_file() and beats(body_of(WORK / r))]
    fam = lambda r: re.sub(r"^v\d+_", "", Path(r).name) if re.match(r"v\d+_", Path(r).name) else None  # noqa: E731
    return [(g, b) for g in good for b in bad if fam(g) and fam(g) == fam(b)]


def calibrate(model=llm):
    pairs = known_pairs()

    def one(p):
        ok, d = wins_both(beats(body_of(WORK / p[0])), beats(body_of(WORK / p[1])), model)
        return p[0], p[1], ok, d
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(one, pairs))
    right = sum(1 for r in res if r[2])
    rate = right / len(res) if res else 0.0
    return rate, res


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    cmd, a = argv[0], argv[1:]
    k = int(a[a.index("-k") + 1]) if "-k" in a else 2
    if cmd == "compare":
        x, y = beats(body_of(a[0])), beats(body_of(a[1]))
        sx, sy, d = score_pair(x, y)
        print(f"{a[0]}: {sx:.2f}\n{a[1]}: {sy:.2f}\n{d}")
        return 0
    if cmd == "match":
        rows, _ = match_table(Path(a[0]).read_text(), k)
        print_table(rows)
        return 0
    if cmd == "judge":
        text = Path(a[0]).read_text()
        rows, hits = match_table(text, k)
        print_table(rows)
        draft = beats(text)
        lost = 0
        for h in hits:
            ex = beats(body_of(WORK / h["path"]))
            if not ex:
                continue
            ok, d = wins_both(draft, ex)
            print(f"judge vs {h['path']}: draft {'wins' if ok else 'does not win'} both orderings {d}")
            lost += 0 if ok else 1
        return 1 if lost else 0
    if cmd == "calibrate":
        rate, res = calibrate()
        for g, b, ok, d in res:
            print(("RIGHT" if ok else "WRONG"), g, ">", b, d)
        passed = len(res) >= MIN_PAIRS and rate >= PASS_BAR
        print(f"{rate:.0%} of {len(res)} pairs ranked right in both orderings (bar {PASS_BAR:.0%}, min {MIN_PAIRS} pairs): {'PASS, the judge may gate' if passed else 'FAIL, the judge stays advisory'}")
        return 0 if passed else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

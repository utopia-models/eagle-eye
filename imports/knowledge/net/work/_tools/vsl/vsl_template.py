#!/usr/bin/env python3
"""vsl_template.py: fill the client-first templates in templates/ from a brief's `signals:` and `take:` blocks (Part of #14969).

  vsl_template.py BRIEF [--template signals|hook|problem|flow|proof|next|take]

Client-first (Tyler, card 2026-11-21; beat order copied from Nick Saraev's job-post Looms): a `## Signals` block with the client's verbatim
phrases, then five beats written out of it: hook, their problem back to them, their flow shown, one line of proof, one next step.
A template never invents: a required slot with no value raises MissingSlot naming the slot and the brief path to set.
`take` assembles the Signals block and the numbered parts (`## N · Title (S s)` + `[horus]` cue + spoken lines) that the gate reads;
each part's seconds are its spoken words / 2.5, so the labels always match what script_check measures.
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TDIR = HERE / "templates"
BEATS = ["hook", "problem", "flow", "proof", "next"]
TEMPLATES = ["signals"] + BEATS
WORDS_PER_S = 2.5


class MissingSlot(Exception):
    pass


def _yaml(path):
    import yaml
    return yaml.safe_load(Path(path).read_text())


def load(tid):
    """The newest version of template `tid`."""
    files = sorted(TDIR.glob(f"{tid}.v*.yaml"), key=lambda p: int(re.search(r"\.v(\d+)\.yaml", p.name).group(1)))
    if not files:
        raise FileNotFoundError(f"no template {tid}")
    return _yaml(files[-1])


def dig(d, path):
    for k in path.split("."):
        if isinstance(d, list) and k.isdigit() and int(k) < len(d):
            d = d[int(k)]
        elif isinstance(d, dict) and k in d:
            d = d[k]
        else:
            return None
    return d if d not in ("", [], None) else None


def clean(v):
    return re.sub(r"\s+", " ", str(v)).strip().rstrip(".?!")


def values(t, brief):
    """-> {slot: value}; a required slot with no value raises MissingSlot."""
    vals = {k: dig(brief, s["from"]) if dig(brief, s["from"]) is not None else s.get("default") for k, s in t.get("slots", {}).items()}
    for k, s in t.get("slots", {}).items():
        if s.get("required") and vals[k] is None:
            raise MissingSlot(f"{t['id']}: slot '{k}' is required: set brief {s['from']}")
    return vals


def _fmt(text, vals):
    return text.format(**{k: clean(v) if not isinstance(v, (list, dict)) else v for k, v in vals.items()})


def _alt(alts, vals):
    """First alternative whose slots are all filled, else None."""
    for a in alts:
        if all(vals.get(n) is not None for n in re.findall(r"{(\w+)}", a)):
            return _fmt(a, vals)
    return None


def render(brief, tid, base=None):
    """-> the spoken lines of one beat. `signals` renders the Signals block instead."""
    if tid == "signals":
        return signals_block(brief)
    t = load(tid)
    vals = values(t, brief)
    out = []
    for ln in t["lines"]:
        if isinstance(ln, dict):   # {each: slot, text: [lines per item]}
            for item in vals.get(ln["each"]) or []:
                item = item if isinstance(item, dict) else {"item": item}
                out += [_fmt(x, {**vals, **item}) for x in ln["text"]]
        else:
            s = _alt(ln, vals)
            if s:
                out.append(s)
    return out


def questions(brief):
    qs = dig(brief, "signals.questions") or []
    for q in qs:
        for k in ("q", "ask", "answer"):
            if not q.get(k):
                raise MissingSlot(f"signals: every question needs q, ask and answer: set brief signals.questions[].{k} (the checker refuses an unanswered question)")
    return qs


def signals_block(brief):
    t = load("signals")
    vals = values(t, brief)
    if len(vals["phrases"]) < t["min_phrases"]:
        raise MissingSlot(f"signals: {len(vals['phrases'])} phrases, need {t['min_phrases']}+: set brief signals.phrases")
    q = lambda x: f'"{clean(x)}"'   # noqa: E731
    out = ["## Signals", f"- Channel: {vals['channel']}", "- Phrases:"] + [f"  - {q(p)}" for p in vals["phrases"]]
    out.append(f"- Outcome: {q(vals['outcome'])}")
    for key, name in (("fear", "Fear"), ("deadline", "Deadline"), ("stack", "Stack"), ("budget", "Budget")):
        if vals[key]:
            out.append(f"- {name}: " + (q(vals[key]) if key == "fear" else clean(vals[key])))
    qs = questions(brief)
    if qs:
        out.append("- Questions:")
        out += [f"  - {q(x['q'])}" + (f" => {', '.join(str(k) for k in x['keys'])}" if x.get("keys") else "") for x in qs]
    if vals["last_message"]:
        out.append(f"- Last message: {q(vals['last_message'])}")
    out += ["", "## Do not say"] + [f"- {x}" for x in t["do_not_say"]]
    return out


def outline_beats(first_name=None):
    """-> [(title, seconds, cue, outline lines)] for each beat: the same five parts take() fills, with <...> where the brief's value goes."""
    out = []
    for tid in BEATS:
        t = load(tid)
        p = t["part"]
        lines = [x.replace("<First name>", first_name) if first_name else x for x in t["outline"]]
        out.append((p["title"], p["seconds"], re.sub(r"{(\w+)}", "<their \\1>", p["cue"]), lines))
    return out


def take(brief, base=None):
    """The whole take: the Signals block, then five numbered parts. -> markdown the gate reads."""
    title = dig(brief, "job.title") or "take"
    sig = signals_block(brief)
    out = [f"# {title}: client-first take (vsl_template.py, templates v{max(load(t)['version'] for t in TEMPLATES)}). [horus] lines are cues, never read.",
           f"copied_from: {load('signals')['copied_from']}", ""] + sig + [""]
    for i, tid in enumerate(BEATS, 1):
        t = load(tid)
        lines = render(brief, tid, base)
        words = sum(len(l.split()) for l in lines)
        secs = max(1, round(words / WORDS_PER_S))
        vals = values(t, brief)
        cue = _fmt(dig(brief, f"take.cue.{tid}") or t["part"]["cue"], vals)
        out += [f"## {i} · {t['part']['title']} ({secs} s)", f"[horus] {cue}", *lines, ""]
    return "\n".join(out)


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    brief = _yaml(argv[0])
    tid = argv[argv.index("--template") + 1] if "--template" in argv else "take"
    base = Path(argv[0]).resolve().parent
    try:
        print(take(brief, base) if tid == "take" else "\n".join(render(brief, tid, base)))
    except MissingSlot as e:
        print(f"missing slot: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

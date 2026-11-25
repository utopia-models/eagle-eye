#!/usr/bin/env python3
"""vsl_variants.py: what differs between VSL variants, in one table (knowledge#16076, spec wi/work/research/vsl-redesign-2026-11-18.md §2, §7 B6).

  vsl_variants.py            list the variants
Everything else (diagram first, demo second, next step third, one take, QA) is common. Four things differ:
  max_s        the length bound, seconds (Tyler 2026-11-18: Upwork 2-3 min, YouTube up to 5)
  closing      "next-step" = exactly one closing next-step statement as the last spoken sentence; "none" = no closing rule (YouTube)
  eagle_eye    may a spoken line or cue name Eagle Eye (Tyler 2026-11-15: not in Upwork VSLs; only the Eagle Eye overview is about it)
  demo_source  where the demo's nouns come from
stdlib only.
"""
import re
import sys

VARIANTS = {
    "upwork-job":     {"max_s": 180, "closing": "next-step", "eagle_eye": False, "demo_source": "job post", "input": "job"},
    "upwork-generic": {"max_s": 180, "closing": "next-step", "eagle_eye": False, "demo_source": "category skeleton", "input": "job"},
    "company":        {"max_s": 180, "closing": "next-step", "eagle_eye": True, "demo_source": "company site", "input": "target"},
    "youtube":        {"max_s": 300, "closing": "none", "eagle_eye": True, "demo_source": "the ask", "input": "target"},
    "eagle-eye":      {"max_s": 300, "closing": "none", "eagle_eye": True, "demo_source": "Eagle Eye", "input": "target"},
}
WORDS_PER_S = 2.5
EAGLE = re.compile(r"\beagle[\s_-]*eye\b", re.I)


def get(name):
    if name not in VARIANTS:
        raise KeyError(f"unknown variant {name!r}; one of {', '.join(VARIANTS)}")
    return VARIANTS[name]


def max_words(name):
    return int(get(name)["max_s"] * WORDS_PER_S)


def eagle_reasons(text, name):
    """Eagle Eye named anywhere in a script of a variant that bans it -> one reason per line."""
    if get(name)["eagle_eye"]:
        return []
    return [f"eagle eye: {name} never names Eagle Eye (Tyler 2026-11-15): {l.strip()[:80]!r}"
            for l in text.splitlines() if EAGLE.search(l)]


def main(argv):
    for n, v in VARIANTS.items():
        print(f"{n:15} max {v['max_s']:>3} s  closing {v['closing']:9} eagle_eye {str(v['eagle_eye']):5} demo from {v['demo_source']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

---
id: prompt.copy-reviewer
title: Copy reviewer - judge a script or message against its real source
kind: prompt
version: 1.0.0
tags: [copy, review, judge, vsl, letter]
inputs: [draft, source, audience]
outputs: [verdicts_and_rewrites]
model_hints: {tier: mid, temperature: 0}
license: Apache-2.0
---
You are a senior technical editor. Read the draft as {{audience}} would hear it.

Score each beat 1 to 10 on: persuasion (moves the reader one step closer to replying), professionalism (plain, no slang, no hedging), specificity (names the mechanism, number or step), terminology (the practitioner's terms, used correctly). Use the full range; when two beats differ in wording their scores differ.
Penalties: addressing the reader as a stranger in the third person (-3 professionalism); slang, filler, hype, hedges (-3); a wordy bridge ("What I built is ... for exactly that") costs persuasion; a loose restatement of a mechanism scores below the concrete verb version.

Then:
1. Name every beat the SOURCE has that the draft lacks or reorders, and every place the draft is less specific than the source.
2. List the five weakest sentences: what the reader would not believe or would find vague, and the exact fact from the source that replaces it.
3. Give a line-level rewrite for each, copied from the source's wording, never invented.

Judge the text only; ignore length. Return ONE JSON object: {"beats": [{"beat", "persuasion", "professionalism", "specificity", "terminology"}], "weakest": [{"line", "problem", "replacement"}], "missing_from_source": [..], "why": "one sentence"}.

DRAFT:
{{draft}}

SOURCE:
{{source}}

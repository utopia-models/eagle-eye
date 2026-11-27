---
id: prompt.vsl-script-writer
title: VSL script writer - the spoken script of a short engineer video
kind: prompt
version: 2.0.0
tags: [vsl, video, script, upwork]
inputs: [brief, post, speaker]
outputs: [script_markdown]
model_hints: {tier: mid, temperature: 0.7}
license: Apache-2.0
---
You write the spoken script of a short video from an engineer to the person who posted a technical job.
The speaker is a working engineer: {{speaker}}. The audience is another engineer or a technical hiring manager.

Register: precise, plain, first person singular, spoken. Contractions required (I'm, it's, here's, I'll). No hype, no filler, no hedging.
Name the mechanism (queue, retry, approval gate, audit log, deterministic code versus model) and the numbers from the brief.
Use only facts in the brief. Never invent a capability, a metric or a client.

Shape:
- One row, one idea, 6 to 16 words. Name the stack once, not in every row.
- Start the demo on the most valuable screen. Walk one workflow from their post; leave out any term you could not explain (research/technical-buyer-outreach.md).
- Name one failure and what the system does about it. Say a number only when the brief gives it from the build.
- Never read a UI label, tab name or button text aloud: say what the thing does.
- Open by saying what you noticed in THEIR post, using their own words, then what you made, then what they get ("I noticed ..., so I made you ..., so that you can ...").
- 45 to 75 seconds at 2.4 words a second (about 110 to 180 words). Do not pad to reach it.
- Never use: "I just built this for you", "first version", "for whoever runs this job", basically, amazing, super, "a bunch of", "I think", "seems like".
- No question and no price in the video; the terms live in the message that carries it.

Output Markdown: numbered parts `## N - Name (S s)`, a cue line first in each part (what is on screen), then the spoken rows.

BRIEF:
{{brief}}

THEIR POST:
{{post}}

Check the result with copy-rules/video-script.yaml (`copy_lint.py video-script script.md`) and revise until it passes.

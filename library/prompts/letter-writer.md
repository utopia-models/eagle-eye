---
id: prompt.letter-writer
title: Letter writer - the cover letter that carries a video and a demo
kind: prompt
version: 1.0.0
tags: [upwork, letter, proposal, cover-letter]
inputs: [post, deliverable, price, signer]
outputs: [letter_text]
model_hints: {tier: mid, temperature: 0.6}
license: Apache-2.0
---
Write a cover letter for the job post below. It is short, in the first person, and says what will be delivered in the client's own words.

Line 1 says you made them a short video (attached) walking through their exact ask and a working version you built for it.
Line 2 says what they get: "so that you can <their outcome, in their words>".
Then one or two plain lines of proof from the facts below (a result with its number, never a claim without one), the price, and one closing line ("Happy to answer any questions.").
Sign as {{signer}}.

Rules:
- Say what they want to hear: no caveat, no "I can't", no "not sure", no "new to me", no "above your budget", no volunteered fact that could disqualify the letter.
- Price {{price}}, under the client's stated budget when they state one.
- The video is attached as a file. Before a contract, no link, email, phone, chat handle or off-platform payment word (copy-rules/upwork-circumvention.yaml).
- Their words, not ours: reuse the post's nouns and verbs. Nothing in it should fit another job.

JOB POST:
{{post}}

WHAT WAS BUILT:
{{deliverable}}

Lint with `copy_lint.py letter-caveats letter.md` and `copy_lint.py upwork-circumvention letter.md`; both must PASS.

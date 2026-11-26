---
id: playbook.upwork-oneshot
title: Upwork one-shot - answer a job post with a letter, a demo and a video
kind: playbook
version: 1.0.0
tags: [upwork, oneshot, vsl, proposal, freelance]
diataxis: how-to
inputs: [job_post]
outputs: [sent_proposal]
license: Apache-2.0
---
# Upwork one-shot: a letter, a working demo and a video for one job post

**Goal:** reply to a fresh, fit job post within the first hour with a package no other bidder sends: a short letter, a working version of what they asked for, and a 45 to 70 second video that walks through it.

## 1. Pick the post (standards)
- Open and fresh: under about 20 proposals, payment verified, no interview or offer already out. Early replies win (research/vsl-speed.md).
- The fleet can deliver it. Do not filter to one technology; filter to "can this be shown working in a day".
- The hunt runs on a schedule you set; nothing automated touches the Upwork pages themselves (see step 6).

## 2. Build the demo (templates, research/ui-libraries.md)
1. Read the post. Write the problem statement in their words.
2. Plan the screens with `prompts/mvp-planner.md` and seed realistic data taken from the post.
3. Build with the stack in research/ui-libraries.md; capture at 60 fps, text 16 px or larger, 3-5 regions per screen.
4. Draw the architecture behind it: boxes named for the real parts, so an engineer can judge it.

## 3. Write and review the script
- `prompts/vsl-script-writer.md`, then `copy_lint.py video-script script.md`, then `prompts/copy-reviewer.md` against the post.
- Shape: opener "I noticed ..., so I made you ..., so that you can ..." then tab 1 their post, tab 2 the working app, tab 3 the diagram. One claim per sentence, their words, nothing that fits another job.
- Length 45-70 s. No question, no price, no link spoken.

## 4. Record or render, then review
- Either the founder records the live intro and an AI voice speaks the body, or the whole video is rendered. Pick on the spot; a reusable intro per job type exists for the fast path.
- Run `prompts/video-reviewer.md` (a video-understanding model). Retake on any high-severity mismatch between what is said and what is shown.

## 5. Write the letter
`prompts/letter-writer.md`. Line 1 says you made a video for them (attached). Price under their stated budget, with one line saying you are building the profile. Lint with `letter-caveats` and `upwork-circumvention`; both PASS before anything is typed.

## 6. Send like a person
- One actor, one browser session, real pointer and keyboard at human pace, one proposal at a time. No scripted clicks, no polling at fixed intervals, no bursts of page loads: accounts are flagged for exactly this.
- Attach the MP4 as a file; never a link before a contract.

## 7. After the send
- Log the proposal (job key, price, send time) in the ledger the day it is sent.
- Replies get an answer the same hour. The first call is booked through the platform's own meeting tool.
- Review weekly: sent, viewed, replied, calls held, signed. The metric that matters is calls held per week.

## Standards that never bend
- Before a contract: no email, phone, outside link, chat app or off-platform payment word (copy-rules/upwork-circumvention.yaml). Terms: research/upwork-contract-terms.md.
- A letter volunteers nothing that could disqualify it (copy-rules/letter-caveats.yaml).
- Every claim in the video and letter traces to the post or to a built artifact.

## Example (shape only)
> Hi, I recorded a short video for you (attached) that walks through your RFQ-search request and a working version I built for it. so that you can get quotes in one list instead of ten inboxes. ... Happy to answer any questions.

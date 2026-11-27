---
id: prompt.mvp-planner
title: MVP planner - the beats.json for a per-job demo video
kind: prompt
version: 1.0.1
tags: [mvp, demo, video, beats, motion]
inputs: [post, stack_choice, seed_data]
outputs: [beats_json]
model_hints: {tier: high}
license: Apache-2.0
---
Plan the demo app a viewer sees in a 45 to 75 second video, as `beats.json`: an ordered list of screens and moves.

Each beat: `{ "id", "screen", "regions": [3-5 named regions], "data": "realistic seeded rows taken from the post", "motion": "<pattern id from research/demo-motion-patterns.md>", "hold_s": 1.5, "say": "<the spoken row it matches>" }`.

Rules (research/ui-libraries.md, research/demo-motion-patterns.md):
- Text at least 16 px. 3 to 5 regions per screen. One thing moving at a time. Hold each end state 1.5 s.
- Data is realistic and comes from the post (their product, their nouns). Never lorem ipsum, never a placeholder.
- Pick components from the named libraries in research/ui-libraries.md; do not hand-write layout CSS.
- Beat 1 shows their post (scroll and highlight the line you are answering), the middle beats show the working thing, the last shows the architecture diagram behind it.
- Every beat's `say` is the matching row of the script; the picture shows what the row names.

POST:
{{post}}
STACK: {{stack_choice}}
SEED DATA: {{seed_data}}

Output only valid JSON.

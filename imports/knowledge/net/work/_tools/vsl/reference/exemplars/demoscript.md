---
source_url: https://github.com/mgosha/demoscript
licence: MIT
retrieved: 2026-11-17
kind: exemplar
client_type: developer or API buyer
role: engineer presenting an API or CLI
stack: YAML demo files; REST, shell, GraphQL, database steps
seconds: unstated
status: reference
---
## Beat sheet
1. Welcome slide: states what the demo shows and for whom (about 5-8s); frames the claim.
2. Setup or context slide: names the system or API under test (about 8s); orients the viewer.
3. Live call step: a real REST or shell call runs and the output is shown (about 15-20s); evidence the system responds.
4. Saved-value step: a value from the first response is stored and reused (about 10s); shows the pieces chain together.
5. Code or config snippet with the key lines highlighted (about 10s); shows how little integration takes.
6. Assertion step: a pass or fail check on the result (about 8s); turns the demo into verifiable proof.
7. Closing slide: summarises the outcome using the values captured earlier (about 8-10s); sets up the next step.

Timings above are my estimates for a spoken adaptation; the source gives none (it names only a 2s default pause between steps).

## What to copy
- Chain steps so each later claim reuses data the demo already produced.
- Use an explicit pass or fail check as the proof beat.
- Bracket the live steps with a short opening slide and closing slide.

## What not to copy
- The tool's step-type vocabulary as spoken content; it describes file format, not narration.
- Branching choices and gotos; a 90-second video is linear.

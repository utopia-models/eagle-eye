# VSL template library (Part of #14969)

Client-first (Tyler, card 2026-11-21; beat order copied from Nick Saraev's job-post Looms, see `vsl/scripts/generic-agency-script.md`).
Slot-based, versioned (`<id>.v<N>.yaml`), no contractions, speakable. A template never invents a fact: every slot is read from the
brief's `signals:` and `take:` blocks and a missing required slot is an error naming the brief path, never a guess.

| template | what it says | slots |
|---|---|---|
| `signals` | the `## Signals` block and `## Do not say`: their verbatim phrases, outcome, fear, stack, questions with answers | signals.* |
| `hook` | what they asked for, in their words (their first name if known) | signals.phrases.0-2, take.first_name |
| `problem` | their problem back to them: fear, outcome, more of their phrases, their stack | signals.fear, outcome, phrases.3-7, stack |
| `flow` | their artifact running on sample data, step by step in their terms | take.artifact, take.flow |
| `proof` | each of their questions answered, then one true line of past work | signals.questions[].ask/answer, take.proof |
| `next` | their milestones, then one next-step statement as the last sentence | take.milestones, take.next_build |

Each part's seconds label is its spoken words / 2.5, so `script_check.py`'s length rule always holds. Each template also carries `outline:`
lines, which `vsl_slot.py outline` uses: the same beats with `<...>` where their words go.

```bash
vsl_script.py new SLUG --brief examples/ai-automation.brief.yaml --template hook    # prints one beat
vsl_script.py new SLUG --brief examples/ai-automation.brief.yaml --template take --out take.md   # Signals + all parts, then the gate
vsl_script.py new SLUG --brief B.yaml --template take --reference   # also writes references.md (top-k of our own scripts)
```
The output is graded by the same gate as every script (`vsl_script.py check`, client-first). Golden: `tests/golden/templates/`.
Never: "helpers", "first version", "for whoever runs this job", "I just built this for you", a contraction, a "we can do" line, or the
old seller-first opener ("I am Tyler Youk ... I designed and built a working implementation").

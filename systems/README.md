# Systems

A System is a one-shot motion that runs a real operator's playbook. `systems/<id>/system.json` declares:

| field | meaning |
|---|---|
| `copies` | the library ids it copies (`lib:` and `kit:`, see `library/kit/README.md`) |
| `basis` | whose way it runs: `ours` is the default; the user may say `fazio`, `hormozi` or `max`; if they say nothing, the AI picks |
| `defaults` | every setting it needs, so nobody is asked anything |
| `stages` | in order; `needs` names an input it waits for; `outward: true` goes through `packages/toolkit/rails.py` |
| `rails` | which safety rails are fixed is still open |
| `quotes` | lines quoted from the cited files; the build fails if one is not there |

Run one: `python3 packages/toolkit/onboard.py --dir <your business folder>`. Today it drafts the offer and targeting
at once, drafts the per-job stages when given the input (`--input job_post=post.txt`), and holds every send: no job
source or sender ships in this repository yet.

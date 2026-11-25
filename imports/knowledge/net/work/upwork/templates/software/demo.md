# Demo skeleton: Software engineering

For the 5-minute apply (knowledge#14753). `mail_watch.py` pings upwork with this file when a fresh `software` alert
lands; the letter is [letter.txt](letter.txt) (Mohamed shape, `letter_lint.py` PASS). The full pipeline is
`net/subprocesses/interactive/upwork-vsl-apply.md`; this file is the part that changes by category.

**The first version:** his repo forked, the bug reproduced in a failing test (or the new command stubbed), then green.
**Stack:** his language and test runner as the repo pins them (`pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`).
**Where it runs:** our own Linux server, `~/dev/prospects/<slug>/`, against his real data or a copy shaped like it. Never
his production, never a key of his before hire.

## The build (first version, target 20-30 min)

1. `gh repo fork <his repo> --clone` into `~/dev/prospects/<slug>/` (or `git clone` a public one); read README, the build file and the module his post names.
2. Reproduce: one failing test that states his bug or his feature in his words (`test_<his_words>`).
3. Make it pass on a branch; run the full suite; note the commit sha.
4. Record the terminal: failing test → the diff → the suite green.

## The diagram (`net/work/vsl/<slug>/diagram.json`, `net/work/vsl/_studio/render.py <slug>`)

Every box says `from <his repo/tool>` or `NEW` (Tyler, 11-09: *"make it more clear ... what each repo does"*):
- his repo `from <repo>`
- the module he named `from <repo>`
- the failing test `NEW`
- the fix / new command `NEW`
- CI job `NEW`

## The video (RULES.md rule 27)

Opens within 5 s on one verbatim phrase from his post, quoted on screen (the proof a person read it; the video never announces it), then shows the red test, the diff, the green suite, in his repo. Intro ≤ 90 s,
one CTA: *"Reply here and I'll send the next build."* Export H.264/AAC < 25 MB and attach it. Tyler records it live
when he is online; while he is away the build and the letter are ready and the send waits (the 07:00Z card: send only
while he is online).

## Send checklist

- [ ] his post read whole; every repo/tool he named opened (`REPOS.md` with the sha)
- [ ] the first version runs; the recording shows it running
- [ ] `letter.txt` filled: every `{{...}}` replaced with his words, bid under the low end of his budget
- [ ] `letter_lint.py <letter>` PASS and `voice.py check --agent horus --channel upwork --proposal` PASS
- [ ] MP4 + diagram PNG attached (never a link); `proposals.py sent` + `ledger.py add video_sent` the same minute

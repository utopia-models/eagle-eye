# Demo skeleton: Data

For the 5-minute apply (knowledge#14753). `mail_watch.py` pings upwork with this file when a fresh `data` alert
lands; the letter is [letter.txt](letter.txt) (Mohamed shape, `letter_lint.py` PASS). The full pipeline is
`net/subprocesses/interactive/upwork-vsl-apply.md`; this file is the part that changes by category.

**The first version:** one real run of his first source into his target, with the row count on screen.
**Stack:** Python (`httpx` / Playwright for a scrape, `pandas` or plain SQL), landing in what he named: Postgres, BigQuery or a Google Sheet.
**Where it runs:** our own Linux server, `~/dev/prospects/<slug>/`, against his real data or a copy shaped like it. Never
his production, never a key of his before hire.

## The build (first version, target 20-30 min)

1. Pull a sample from his first source (public page, his sample CSV, or the API he named) into `~/dev/prospects/<slug>/raw/`.
2. Write the transform with his rules (columns, dedupe, units) and a test per rule.
3. Load into his target type (local Postgres or a scratch Sheet) and print the counts: read, kept, dropped and why.
4. Wrap it as a systemd timer unit (don't enable it) so the schedule is shown, not described.

## The diagram (`net/work/vsl/<slug>/diagram.json`, `net/work/vsl/_studio/render.py <slug>`)

Every box says `from <his repo/tool>` or `NEW` (Tyler, 11-09: *"make it more clear ... what each repo does"*):
- his source(s) `from <site/API>`
- extract `NEW`
- transform + rules `NEW`
- his target `from <db/sheet>`
- schedule + failure alert `NEW`

## The video (RULES.md rule 27)

Opens within 5 s on one verbatim phrase from his post, quoted on screen (the proof a person read it; the video never announces it), then shows the run, the counts, and the rows in his target with his column names. Intro ≤ 90 s,
one CTA: *"Reply here and I'll send the next build."* Export H.264/AAC < 25 MB and attach it. Tyler records it live
when he is online; while he is away the build and the letter are ready and the send waits (the 07:00Z card: send only
while he is online).

## Send checklist

- [ ] his post read whole; every repo/tool he named opened (`REPOS.md` with the sha)
- [ ] the first version runs; the recording shows it running
- [ ] `letter.txt` filled: every `{{...}}` replaced with his words, bid under the low end of his budget
- [ ] `letter_lint.py <letter>` PASS and `voice.py check --agent horus --channel upwork --proposal` PASS
- [ ] MP4 + diagram PNG attached (never a link); `proposals.py sent` + `ledger.py add video_sent` the same minute

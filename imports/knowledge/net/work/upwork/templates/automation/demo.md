# Demo skeleton: Automation

For the 5-minute apply (knowledge#14753). `mail_watch.py` pings upwork with this file when a fresh `automation` alert
lands; the letter is [letter.txt](letter.txt) (Mohamed shape, `letter_lint.py` PASS). The full pipeline is
`net/subprocesses/interactive/upwork-vsl-apply.md`; this file is the part that changes by category.

**The first version:** his trigger firing once end to end into a copy of his sheet / CRM / inbox.
**Stack:** what he named: n8n (self-hosted), Apps Script, Make/Zapier (rebuilt in n8n for the demo when we hold no account), or Python.
**Where it runs:** our own Linux server, `~/dev/prospects/<slug>/`, against his real data or a copy shaped like it. Never
his production, never a key of his before hire.

## The build (first version, target 20-30 min)

1. Make a scratch copy of his target (a Google Sheet under the fleet's workspace, an n8n workflow) with his column names.
2. Build the trigger → steps → write, using his sample records; every rule he wrote is one step.
3. Fire it 3 times, including one bad record, and show where the bad one goes.
4. Export the workflow JSON / script into the prospect folder.

## The diagram (`net/work/vsl/<slug>/diagram.json`, `net/work/vsl/_studio/render.py <slug>`)

Every box says `from <his repo/tool>` or `NEW` (Tyler, 11-09: *"make it more clear ... what each repo does"*):
- trigger `from <app>`
- steps / rules `NEW`
- his target `from <sheet/CRM>`
- error path + alert `NEW`

## The video (RULES.md rule 27)

Opens within 5 s on one verbatim phrase from his post, quoted on screen (the proof a person read it; the video never announces it), then shows a record going in at the trigger and arriving in his sheet / CRM, and the bad one caught. Intro ≤ 90 s,
one CTA: *"Reply here and I'll send the next build."* Export H.264/AAC < 25 MB and attach it. Tyler records it live
when he is online; while he is away the build and the letter are ready and the send waits (the 07:00Z card: send only
while he is online).

## Send checklist

- [ ] his post read whole; every repo/tool he named opened (`REPOS.md` with the sha)
- [ ] the first version runs; the recording shows it running
- [ ] `letter.txt` filled: every `{{...}}` replaced with his words, bid under the low end of his budget
- [ ] `letter_lint.py <letter>` PASS and `voice.py check --agent horus --channel upwork --proposal` PASS
- [ ] MP4 + diagram PNG attached (never a link); `proposals.py sent` + `ledger.py add video_sent` the same minute

# Demo skeleton: Web and backend

For the 5-minute apply (knowledge#14753). `mail_watch.py` pings upwork with this file when a fresh `web-backend` alert
lands; the letter is [letter.txt](letter.txt) (Mohamed shape, `letter_lint.py` PASS). The full pipeline is
`net/subprocesses/interactive/upwork-vsl-apply.md`; this file is the part that changes by category.

**The first version:** the first 2-3 endpoints or pages he named, running against seed data shaped like his.
**Stack:** FastAPI + Postgres, or Next.js + Supabase/Postgres, or whatever framework the post names (his wins).
**Where it runs:** our own Linux server, `~/dev/prospects/<slug>/`, against his real data or a copy shaped like it. Never
his production, never a key of his before hire.

## The build (first version, target 20-30 min)

1. Scaffold in `~/dev/prospects/<slug>/`: `uv init` + FastAPI, or `pnpm create next-app`, matching his stack.
2. Model the entities his post names (`schema.sql` or the ORM model) and seed 10-20 rows shaped like his data.
3. Build the endpoints/pages he named first; his third-party (Stripe, auth, webhooks) in test mode only.
4. Run it on the server (`uvicorn` / `pnpm dev`) and hit it with `curl` / a browser for the recording.

## The diagram (`net/work/vsl/<slug>/diagram.json`, `net/work/vsl/_studio/render.py <slug>`)

Every box says `from <his repo/tool>` or `NEW` (Tyler, 11-09: *"make it more clear ... what each repo does"*):
- client (browser / his app)
- API `NEW` (his framework)
- Postgres `NEW` (his entities)
- his third-party `from <service>`
- deploy: Docker + systemd `NEW`

## The video (RULES.md rule 27)

Opens within 5 s on one verbatim phrase from his post, quoted on screen (the proof a person read it; the video never announces it), then shows a request going through his endpoint and the row landing in his table. Intro ≤ 90 s,
one CTA: *"Reply here and I'll send the next build."* Export H.264/AAC < 25 MB and attach it. Tyler records it live
when he is online; while he is away the build and the letter are ready and the send waits (the 07:00Z card: send only
while he is online).

## Send checklist

- [ ] his post read whole; every repo/tool he named opened (`REPOS.md` with the sha)
- [ ] the first version runs; the recording shows it running
- [ ] `letter.txt` filled: every `{{...}}` replaced with his words, bid under the low end of his budget
- [ ] `letter_lint.py <letter>` PASS and `voice.py check --agent horus --channel upwork --proposal` PASS
- [ ] MP4 + diagram PNG attached (never a link); `proposals.py sent` + `ledger.py add video_sent` the same minute

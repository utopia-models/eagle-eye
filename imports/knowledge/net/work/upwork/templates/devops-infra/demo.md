# Demo skeleton: DevOps and infrastructure

For the 5-minute apply (knowledge#14753). `mail_watch.py` pings upwork with this file when a fresh `devops-infra` alert
lands; the letter is [letter.txt](letter.txt) (Mohamed shape, `letter_lint.py` PASS). The full pipeline is
`net/subprocesses/interactive/upwork-vsl-apply.md`; this file is the part that changes by category.

**The first version:** his service standing up from code on our server, plus the pipeline or the alert he asked for.
**Stack:** Docker / compose, Ansible or Terraform (whichever he named), GitHub Actions for CI, Prometheus + Alertmanager or his monitoring.
**Where it runs:** our own Linux server, `~/dev/prospects/<slug>/`, against his real data or a copy shaped like it. Never
his production, never a key of his before hire.

## The build (first version, target 20-30 min)

1. Write the IaC in `~/dev/prospects/<slug>/` for what he described (compose file, playbook or `main.tf` against a local provider).
2. Bring it up on the server (`docker compose up -d`, `ansible-playbook -i localhost,`) and tear it down once, so the rebuild is proven.
3. Add the CI workflow file he needs and run it once (`act` or a scratch repo).
4. Wire the one alert he named and fire it on purpose (`systemd-run --user -E FLEET_NOTIFY=off ...` for a throwaway failing unit).

## The diagram (`net/work/vsl/<slug>/diagram.json`, `net/work/vsl/_studio/render.py <slug>`)

Every box says `from <his repo/tool>` or `NEW` (Tyler, 11-09: *"make it more clear ... what each repo does"*):
- his app `from <repo>`
- container / VM `NEW`
- IaC `NEW`
- CI pipeline `NEW`
- monitoring + alert `NEW`
- his cloud `from <provider>`

## The video (RULES.md rule 27)

Opens within 5 s on one verbatim phrase from his post, quoted on screen (the proof a person read it; the video never announces it), then shows one command rebuilding the box, the pipeline green, the alert firing. Intro ≤ 90 s,
one CTA: *"Reply here and I'll send the next build."* Export H.264/AAC < 25 MB and attach it. Tyler records it live
when he is online; while he is away the build and the letter are ready and the send waits (the 07:00Z card: send only
while he is online).

## Send checklist

- [ ] his post read whole; every repo/tool he named opened (`REPOS.md` with the sha)
- [ ] the first version runs; the recording shows it running
- [ ] `letter.txt` filled: every `{{...}}` replaced with his words, bid under the low end of his budget
- [ ] `letter_lint.py <letter>` PASS and `voice.py check --agent horus --channel upwork --proposal` PASS
- [ ] MP4 + diagram PNG attached (never a link); `proposals.py sent` + `ledger.py add video_sent` the same minute

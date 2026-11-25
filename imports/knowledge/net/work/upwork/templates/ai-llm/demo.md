# Demo skeleton: AI and LLM

For the 5-minute apply (knowledge#14753). `mail_watch.py` pings upwork with this file when a fresh `ai-llm` alert
lands; the letter is [letter.txt](letter.txt) (Mohamed shape, `letter_lint.py` PASS). The full pipeline is
`net/subprocesses/interactive/upwork-vsl-apply.md`; this file is the part that changes by category.

**The first version:** the agent or retrieval step answering 5-10 of his own example questions, with the eval scored.
**Stack:** Python + the model he named (Claude via the fleet's `claude -p` for the build; his API key only after hire), a small vector index (sqlite-vec / pgvector) when it is RAG.
**Where it runs:** our own Linux server, `~/dev/prospects/<slug>/`, against his real data or a copy shaped like it. Never
his production, never a key of his before hire.

## The build (first version, target 20-30 min)

1. Put his examples (post text, sample docs, the FAQ or tickets he linked) in `~/dev/prospects/<slug>/data/`.
2. Write `eval.jsonl`: 10 of his questions with the answer his post implies; the score prints as N/10.
3. Build the smallest loop that answers: retrieve → prompt → answer (or tool call → result) on his data.
4. Run the eval, keep the score honest on screen, fix the worst miss once.

## The diagram (`net/work/vsl/<slug>/diagram.json`, `net/work/vsl/_studio/render.py <slug>`)

Every box says `from <his repo/tool>` or `NEW` (Tyler, 11-09: *"make it more clear ... what each repo does"*):
- his data `from <source>`
- index / retrieval `NEW`
- the model `from <provider>`
- tools he named `from <api>`
- eval set `NEW`
- UI or channel `NEW`

## The video (RULES.md rule 27)

Opens within 5 s on one verbatim phrase from his post, quoted on screen (the proof a person read it; the video never announces it), then shows his question in, the answer out, and the eval score. Intro ≤ 90 s,
one CTA: *"Reply here and I'll send the next build."* Export H.264/AAC < 25 MB and attach it. Tyler records it live
when he is online; while he is away the build and the letter are ready and the send waits (the 07:00Z card: send only
while he is online).

## Send checklist

- [ ] his post read whole; every repo/tool he named opened (`REPOS.md` with the sha)
- [ ] the first version runs; the recording shows it running
- [ ] `letter.txt` filled: every `{{...}}` replaced with his words, bid under the low end of his budget
- [ ] `letter_lint.py <letter>` PASS and `voice.py check --agent horus --channel upwork --proposal` PASS
- [ ] MP4 + diagram PNG attached (never a link); `proposals.py sent` + `ledger.py add video_sent` the same minute

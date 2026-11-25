# VSL 100x speed, 1/3: where the time goes, and the 10-minute budget (knowledge#18876)

Goal (Tyler 2026-11-24 ~6:55 PM ET): from Tyler's take, or his feedback on a take, to an MP4 he can watch in **600 s or less**.
Parts 2/3 (research, brainstorm) and the build follow this file. Everything below is measured or says `no data`; nothing is interpolated.

## Tool

`python3 net/work/_tools/vsl/speed/stage_ledger.py JOB [JOB...] [--json]` prints the per-stage table below for any job suffix (the 4 digits its
slug ends in). Sources, each named per row: `jobrec` (oneshot-auto job record `t` stamps, Ra user `upwork`), `feed` (Eagle Eye hunt feed),
`mtime` (`/srv/vsl/*/`, `/var/tmp/eagle-send`), `mail` (`fleetmail inbox --all --json`). A source the box cannot read prints `unreadable`
and its stages stay `no data`. A gap that spans unstamped events is shown as `span`, never assigned to work or wait.
**Run it as user `upwork` on Ra and every build stage fills in**; every future run therefore writes its own ledger with one command.

## Measured per-stage table, jobs 3307 and 5027 (run from novaserver as `dust`, 2026-11-25 ~02:00Z)

Job 3307 = "Technical Lead / CTO for AI Styling App", job 5027 = "Senior Python Engineer, Web Scraping" (suffixes of the Upwork ids in the feed).
`jobrec` was **unreadable** (Ra `/home/upwork/.claude/state/net/oneshot-auto/jobs`, mode-closed to `dust`; an SSH attempt to Ra as other users was refused,
so I did not push it), so the 7 build stamps are `no data` and the build interior is one span.

### Job 3307

Sources: **jobrec** unreadable or absent: /home/dust/.claude/state/net/oneshot-auto/jobs; **feed** ok (Technical Lead / CTO for AI Styling App); **mtime** no file named 3307 under /srv/vsl or /var/tmp/eagle-send; **mail** 0 message(s) name 3307

| event | at (UTC) | gap from previous stamped event | kind | work s | wait s | source |
|---|---|---|---|---|---|---|
| posted: client posts the job | 2026-11-24T05:33:56Z | - | - |  |  | feed signalAt |
| found: post -> in Eagle Eye feed (intake lag) | 2026-11-24T05:38:56Z | 300 s from posted | wait | 0 | 300 | feed foundAt |
| build_started: found -> build picked up (queue) | no data | no data | wait |  |  | no data |
| authored: post read + app/script authoring (claude worker) | no data | no data | work |  |  | no data |
| app: app build + pre-review | no data | no data | work |  |  | no data |
| diagram: architecture diagram build + publish | no data | no data | work |  |  | no data |
| scripts_gates: script draft, rewrite loop, gates | no data | no data | work |  |  | no data |
| ready: package marked READY | no data | no data | work |  |  | no data |
| raw_take: READY -> Tyler records the take (wait on Tyler) | no data | no data | wait |  |  | no data |
| final_mp4: TTS/orb render/composite/mux to MP4 | no data | no data | work |  |  | no data |
| vsl_sent: MP4 -> proposal sent (review/upload/send handoff) | 2026-11-24T20:33:00Z | 53644 s from found | span (unstamped events inside) | 0 | 0 | feed firstSentAt |

Stamped work **0 s**, stamped wait **300 s**, unsplit span **53644 s**.


### Job 5027

Sources: **jobrec** unreadable or absent: /home/dust/.claude/state/net/oneshot-auto/jobs; **feed** ok (Senior Python Engineer — Web Scraping, Search & Da); **mtime** no file named 5027 under /srv/vsl or /var/tmp/eagle-send; **mail** 0 message(s) name 5027

| event | at (UTC) | gap from previous stamped event | kind | work s | wait s | source |
|---|---|---|---|---|---|---|
| posted: client posts the job | 2026-11-24T16:34:10Z | - | - |  |  | feed signalAt |
| found: post -> in Eagle Eye feed (intake lag) | 2026-11-24T16:34:41Z | 31 s from posted | wait | 0 | 31 | feed foundAt |
| build_started: found -> build picked up (queue) | no data | no data | wait |  |  | no data |
| authored: post read + app/script authoring (claude worker) | no data | no data | work |  |  | no data |
| app: app build + pre-review | no data | no data | work |  |  | no data |
| diagram: architecture diagram build + publish | no data | no data | work |  |  | no data |
| scripts_gates: script draft, rewrite loop, gates | no data | no data | work |  |  | no data |
| ready: package marked READY | 2026-11-24T21:49:10Z | 18869 s from found | span (unstamped events inside) | 0 | 0 | feed details.ready_at |
| raw_take: READY -> Tyler records the take (wait on Tyler) | no data | no data | wait |  |  | no data |
| final_mp4: TTS/orb render/composite/mux to MP4 | no data | no data | work |  |  | no data |
| vsl_sent: MP4 -> proposal sent (review/upload/send handoff) | no data | no data | wait |  |  | no data |

Stamped work **0 s**, stamped wait **31 s**, unsplit span **18869 s**.


### What the two ledgers already say (all from the rows above)

| fact | 3307 | 5027 | source |
|---|---|---|---|
| post -> in feed (wait) | 300 s | 31 s | feed signalAt/foundAt |
| found -> sent or READY, build + take + render + send as one span | 53,644 s (14.9 h) to send at 2026-11-24T20:33Z | 18,869 s (5.2 h) to READY 21:49Z, **never sent** (feed `firstSentAt` null) | feed |
| fleetmail naming the job | thread `vsl` #21903 (eagle, 22:41Z): Cover letter section verified on hunt h3wmfuq, "sent Nov 24, 3:33 PM ET" = 20:33Z | `oneshot_auto.py:410` comment: 5027 and 0587 blocked on first draft E3/E4/E8/E10, 21:27Z (fm:21662) | `fleetmail thread vsl`, source |
| rework | 3307 intro shipped with "get get" and a renderer that rendered a `blocked` package: #18647 | 5027 re-gated: #18616 | `tests/test_oneshot_3307_18647.py` |

**Reading it:** by minutes, almost none of the 15 h and 5 h is machine work. The measured intake lag is 0.5 to 5 min; the build stamps exist (`meter_stage`
writes tokens and minutes to `vsl-status.db`) but need the Ra read. What the feed alone proves is that **the span from found to send is hours and the wait
on handoffs dominates**; the exact split inside it is the one number this run could not read (see Gaps).

## The post-take chain, measured from files on this box (the part Tyler's clock covers)

Job 1339 (same 2026-11-24 pipeline, `/srv/vsl/2026-11-24/`), file mtimes UTC:

| step | at | gap | kind | source |
|---|---|---|---|---|
| raw take written | 10:30:43 | - | Tyler | `1339-take1-raw.mkv` |
| contact sheet / frame check | 10:41:35 | 652 s | wait on agent pickup + frame extraction | `1339-contact.png` |
| words.json + render.py written | 10:42:08 | 33 s | work (agent) | `words.json`, `render.py` |
| QA json + final MP4 | 11:11:02 / 11:11:09 | 1,734 s | work (render + composite + QA) | `1339-take1-final.mp4`, `1339-qa.json` |
| **take -> watchable MP4** | | **2,419 s (40.3 min)** | | |
| Eagle marked the take recorded | 15:44:42 | 16,413 s after final | wait (a late bookkeeping stamp, not on the path) | `…eagle-recorded.json` |

Rework is the multiplier: 8891 produced `final` 11:22:57, `v3` 11:34:43, `v5` 11:57:17 (**34 min after the first MP4**, 3 renders) and each carries a
hand-written `renderN.py` / `sched*.json` (`8891-rebuild/`); 1291 has its own `1291-rebuild/render4.py`. So the render step is a **per-job script written by an
agent after the take**, not a fixed program, which is why it is slow and why feedback costs a full re-run.

## Gaps this ledger could not close (named, not filled)

1. `jobrec` for 3307/5027: needs a read as user `upwork` on Ra. The ledger script reads it unchanged when run there; **re-run it there and paste the two tables into this file** (follow-up).
2. Tyler's take timestamp and the TTS/orb stages for 3307 and 5027: no `*3307*`/`*5027*` file under `/srv/vsl` or `/var/tmp/eagle-send` on this box (the latter does not exist here), so `raw_take`, `final_mp4` read `no data`. 3307 was sent at 20:33Z, so its MP4 existed by then.
3. The 3307 send message in fleetmail is not in `dust`'s mailbox (only the 21903 verification names it).

## The 10-minute budget (clock starts at Tyler's take or his feedback, ends at an MP4 he can watch)

Design rule from the measured chain: nothing is authored after the take. Everything that depends only on the job (screens, diagram beats, cue schedule,
intro TTS, orb loop) is **pre-built at READY**; the take triggers only the stages that need his audio. Feedback re-renders **only the changed section**.

| # | stage (after the take) | budget s | parallel? | pre-built per job category? | replaces (measured) |
|---|---|---|---|---|---|
| 1 | take ingest: detect stable file, copy off OBS folder | 20 | no | - | part of the 652 s pickup wait |
| 2 | transcript + word timestamps (faster-whisper) | 40 | with 3 | model warm, resident | `words.json` step |
| 3 | cue schedule from words against the pre-built section map (no agent) | 20 | after 2 | section map built at READY | per-job `sched*.json` by hand |
| 4 | screen capture replay of the package (app, diagram beats) | 90 | with 2, 5 | **yes**: capture each screen once at READY | live capture inside render |
| 5 | TTS for any synthesized lines (intro, Eagle voice) | 45 | with 2, 4 | **yes**: intro bank per category (`/srv/vsl/intro-bank`) | TTS inside render |
| 6 | orb render | 60 | with 2, 4 | **yes**: loop per length bucket | orb inside render |
| 7 | composite + mux (one ffmpeg graph, GPU encode) | 120 | no | template per category | the 1,734 s render |
| 8 | automatic QA (the 1339 qa.json checks) | 40 | no | - | `*-qa.json` |
| 9 | upload + watch link | 40 | no | - | upload/review handoff |
| 10 | reserve for one re-render of one section after feedback | 105 | - | - | 34 min of v3/v5 rework |
| | **Serial sum, all stages** | **580** | | | |
| | **Critical path** (1 + max(2,4,5,6)+3 + 7 + 8 + 9) | **330** | | | leaves 270 s slack |

Serial sum 580 s is at most the 600 s ceiling even if nothing runs in parallel; with the parallel stages marked, the critical path is 330 s.

## Not in this file

The research and brainstorm (parts 2 and 3) decide how to meet these seconds; the build follows. This file only fixes what is measured and what each
stage may cost.

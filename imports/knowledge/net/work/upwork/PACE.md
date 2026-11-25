# Upwork pace and ownership: why horus was faster, and what the upwork agent does now (knowledge#13797)

Tyler, 2026-11-15 1:25 PM MT: *"When Horus was working on Upwork, he was moving a lot faster. Why? Is it because we
don't want too many proposals submitted at once? Is it because we want to drive it like a human?"* And 2:09 PM: *"we
no longer have agent Polymarket, which should be migrated over to Upwork."*

## Why horus was faster (measured 2026-11-15 ~20:30Z)

| | horus, 2026-11-01..09 | upwork, 2026-11-15 (to 20:30Z) |
|---|---|---|
| proposals sent | **34 in 9 days: 3.8/day** (4,4,1,4,6,4,2,4,5; best day 6) | **3** (15:58Z, 18:46Z, 19:00Z) |
| post → send | median **19 min** (p25 11 min, n=32) | not recorded |
| what woke it | an RSS poller of upwork.com (`received` rows, source `rss`) feeding detect/apply workers every few minutes | **nothing**: it moves only when a fleetmail lands |
| how it clicked | script (CDP; `attended: false` on most rows) | by hand on desk-upwork, real pointer and keys |
| what else held the seat | the NET pipeline, separately | Mohamed's live-trading day: 23 `message_sent` rows |

Probes: `ledger.jsonl` `proposal_sent` rows grouped by UTC day; `proposals.db` `sent_at`; the upwork session's
transcript, whose only user turns today are fleetmail deliveries and `/reload-plugins`.

**So it was neither a deliberate throttle nor the human-like driving.** Horus was fast because a script polled the
site and clicked for it, which is exactly what the 2026-11-11 Trust & Safety warning ended (POLICY.md § 4, RULES 13-16;
11-10..11-14 were ~0 bids). The upwork agent inherited the hand seat and none of a wake source: the cutover moved the
seat, the keys and the ledger, but `upwork-mail.timer` / `upwork-score.timer` never moved (design.md items 6-7), and no
replacement for the banned poller existed. Each bid itself takes a person-pace **8 m 49 s** end to end (the 19:00Z
pass), so the hand seat is not the bottleneck; idle time between prompts is.

## The pace (decided)

`net/work/_tools/upwork/bid_pace.py`, run by `upwork-bid-pace.timer` under the upwork user, is the wake source. It
never touches upwork.com: it counts the day's sends from `proposals.db` + the ledger and fleetmails the agent
`Bidding pass N` on thread `upwork-pace`. The agent then searches and bids by hand (RULES 13), so nothing loads an
Upwork page on a fixed interval.

### Numbers (each is a measurement, not a precaution)

| constant | value | measured from |
|---|---|---|
| `FLOOR` | 6 sends/day | horus's best pre-switchover day (11-05); its mean 3.8/day, so 6 clears the acceptance with margin |
| `CEILING` | 12 sends/day | 12 × ~9 min ≈ 1.8 h of hand seat time: one person's day of bidding, not a mill. Connects: 536 left at ~26/bid today, so Connects run out before the ceiling does |
| `PASS_GAP_MIN` | 30 min (+0-5 min timer jitter) | horus's median post→send was 19 min; a pass every ~30-40 min keeps us inside the first hour of most posts |
| `SEND_GAP_MIN` | 12 min | one bid end to end = 8 m 49 s; two submits never land closer than a person could make them |
| `WINDOW` | 07:00-23:00 in Tyler's calendar zone (read live) | a person is at the desk; the day moves with him to Cairo |
| unread pass | skip | a pass still undelivered (session busy with a client) is never stacked behind |

Order inside every pass: an unread client room first (Mohamed's outranks every bid) → one hand search, newest first →
1-2 proposals through `voice.py check` → `proposals.py sent` the same minute. A held seat (stream share, a live client
call) skips the pass; the next comes on its own.

## Ownership: one agent for acquisition and delivery (decided)

**`upwork` owns all Upwork work, client acquisition and delivery, in the registry.** The `polymarket` agent and its unix
user are deleted entirely (knowledge#18297, Tyler card 2026-11-24 ~14:00Z); Mohamed's bot stays on pmbot1, untouched. upwork
owns the pmbot1 reads: as the upwork user on novaserver with `/home/upwork/.ssh/pmbot_deploy` (`sudo -iu upwork`; read-only,
`mohamed_status.py` / `pmbot_watch.py`). Heavy build work runs as a worker the upwork agent starts in its own home (`~/pmbot`,
repo `utopia-models/polymarket-mm-bot`); the worker drafts, never messages the client, and answers only to upwork. One voice to
the client, one owner on the board, one session on the seat (RULES 16 still holds: helpers never touch upwork.com).

Why not keep two agents: Tyler's words (above); and the 11-15 day showed the cost of the split, every client answer
relayed polymarket → upwork by fleetmail. Why not move the units to the upwork user now: moving a unit is a stop and a
start, and Mohamed's bot was live-trading real money on 2026-11-15 (ledger `message_sent` "Real trading on" 13:38Z,
the 24 h small live run proposed 18:37Z). **This change deployed and restarted nothing**: no unit stopped, no session
killed, nothing pushed to pmbot1. A unit move, if it is ever worth it, happens after M2 is accepted and outside a live
session.

## What changed (knowledge#13797)

- `bid_pace.py` + `upwork-bid-pace.{service,timer}` (installed under the upwork user).
- `wi/registry/organization.yaml`: `upwork` owns acquisition + delivery; `polymarket` `status: retired`.
- `net/work/specs/polymarket-mm-bot/m2/live-runbook.md` names upwork; `lanes.yaml` and `components.yaml` follow.
- RULES.md § F (pace) and § G (delivery), loaded by the upwork agent every session.

## The 5-minute apply clock (knowledge#14750)

Tyler said it twice (2026-11-17): apply to every software / AI / infrastructure engineering job within five minutes of posting.
Detection was already minute-fast (`upwork-mail.timer` → `mail_watch.py` → `criteria.yaml` → `upwork-package` ping); nothing timed
the other half. `net/work/_tools/upwork/apply_clock.py`, run by `upwork-apply-clock.timer` (every 30 s, as `upwork`, outside the
session), fleetmails the agent at 3 min and 5 min when a matched job has no `proposal_sent`, naming what `upwork_gate` refuses or
advises. `apply_clock.py report` prints measured alert→send minutes. Install as `upwork` on Nova: copy the two unit files to
`~/.config/systemd/user/`, `daemon-reload`, `enable --now upwork-apply-clock.timer`. Test: `python3 test_apply_clock.py`.

# Proposal templates

**Every proposal is the Mohamed shape: letter + custom demo + VSL. Nothing else is sent.**

Tyler, 2026-11-17 06:49Z: *"We either send proposals based on exactly what we sent to Mohamed, literally exactly what we
sent. So let's template Mohamed since that worked."* And: *"only template Mohamed... whatever proposal we sent out for
Mohamed actually worked. And we did a VSL for him. So template whatever we did for Mohamed."*

Why: 53 proposals, 0 replies, 1 hire. The hire is Mohamed Talat (Polymarket, contract 113036261, $200 against a $300-450
budget). What he got: a letter in his own words, a live build on our server, an intro video + a technical video, a
diagram, a price under budget, and three setup questions. What the other 52 got: generic proof, no video, an opener
about us. Mohamed's words: *"your live audit and demo video give me full confidence in your capabilities."*

| file | what |
|---|---|
| [mohamed.md](mohamed.md) | the verbatim letter, its shape with `{{placeholders}}`, the VSL that went with it, and the #14741 rules |
| `<category>/letter.txt` | the Mohamed shape pre-filled for one category (proof line, setup questions); `letter_lint.py` PASS as committed |
| `<category>/demo.md` | the first-version build, diagram boxes, video and send checklist for that category |

Categories (knowledge#14753, the 5-minute apply): [software](software/) · [web-backend](web-backend/) · [data](data/) ·
[ai-llm](ai-llm/) · [devops-infra](devops-infra/) · [automation](automation/). `test_mail_watch.py` fails if a
category loses a file or its letter stops passing `letter_lint.py`.

## The 5-minute apply (knowledge#14753), superseded 2026-11-17

Tyler: "The Upwork agent shouldn't be applying unless I'm there ready to do the VSL." A match now makes the job's
`net/work/vsl/<slug>/stage.json` skeleton and asks the upwork agent (thread `upwork-package`) to WRITE THE PACKAGE; the
send is refused until demo + recorded VSL + his go (RULES 32, `upwork_gate.py`). The matcher reads `criteria.yaml`. The
steps below are the history; the "send within 5 minutes" part no longer applies.

### How the alert reached the agent (history)

Tyler, 2026-11-17 06:53Z: *"apply within 5 minutes of any software, AI or infra post"*; continuous, no daily cap, fit
check only; proposals send only while he is online (queue while away). Upwork is never polled (RULES.md 13-16, 21), so
the trigger is Upwork's own job-alert mail in dev@:

1. **Alerts.** Upwork mails `New job alert: <title>` from `Upwork's no-reply address` for each saved search with email
   alerts on. The upwork agent keeps one saved search per category in the seat's Chrome, by hand: `software engineer`,
   `python backend api`, `data engineering scraping`, `ai llm agent`, `devops kubernetes aws`, `automation n8n zapier`
   (sort newest, payment verified), each with **email alerts on**.
2. **Ping.** `mail_watch.py` (`upwork-mail.timer`, every minute, as `upwork` on Nova) classifies each alert
   (`category()`: title + skills; a sales, admin or marketing title never pings) and, when the mail is under 15 min old,
   fleetmails upwork on thread `upwork-apply`: title, budget, client line, job key, and this category's letter + demo.
   Probe it end to end with a mail whose subject is `New job alert: [fleet-test] <title>` from `Upwork's no-reply address`
   (pinged as TEST, never a ledger row).
3. **Apply.** The upwork agent reads the job by hand, builds the first version from `demo.md`, fills `letter.txt`,
   and sends when Tyler is online to record the VSL.

## The one rule for choosing

There is no choice. Every engineering job (hunt = any engineering job, not only AI) gets:

1. the repos/tools in the post read, and a first version built and running on our server against his real data;
2. a VSL recorded over his post and that demo (≤ 90 s intro, opens on one verbatim phrase from his post),
   reviewed, exported < 25 MB;
3. the letter in the Mohamed shape: sentence 1 says what was built, his spec in his words, one proof line, "I've
   started a live build", the "I'm building my Upwork profile ... so I'm bidding $N" line with N UNDER his budget and
   the agency line beside it, 2-3 setup questions, `Tyler Youk, Utopia Models, Inc.`;
4. the MP4 and the diagram attached (never a link); `voice.py check --agent horus --channel upwork --proposal` PASS;
   `proposals.py sent` + `ledger.py add video_sent` the same minute.

A post we cannot build a demo for in the time we have is skipped, not sent with a lesser letter.

Pipeline: `net/subprocesses/interactive/upwork-vsl-apply.md`. Rules: `net/work/upwork/RULES.md` § H (rules 26-28).

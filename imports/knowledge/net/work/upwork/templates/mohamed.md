# The Mohamed proposal (the one that won)

Sent 2026-11-09 04:57 MT (12:12Z), Upwork proposal 2119764881329815553, job ~022119411955037540136 (Polymarket
market-making bot, Mohamed Talat). Budget $300-450; bid $200. Result: contract 113036261. His words back: *"your live
audit and demo video give me full confidence in your capabilities."* Of 53 proposals this is the one hire; the rest got
0 replies. Source: `net/work/upwork/letters/2026-11-09-polymarket-mm-bot.txt` (commits 9f88c3683, 36252c888), win
review `RULES.md` § H (knowledge#14508), VSL review `net/work/vsl/reviews/2026-11-10-polymarket-vsl-1-2.md`.

Tyler, 2026-11-17 06:49Z: *"We either send proposals based on exactly what we sent to Mohamed, literally exactly what we
sent. So let's template Mohamed since that worked."* And: *"only template Mohamed... we did a VSL for him. So template
whatever we did for Mohamed."*

## The letter, verbatim (as sent)

```
Hey, I created an intro video for you at clients.tyleryouk.com/polymarket-mm-bot . It's currently 4:57 a.m. and I am recording more videos that go deeper into the technical implementation of your bot.

In the intro video, I walk through your post, both repos, and how I'd merge them. poly-maker stays the engine. nexosdata's logit A-S math replaces its quote step, and the AS guard moves into poly-maker's reconciler as a live cancel, since in nexosdata it only runs inside the simulator. The 0.97 rule is a check before every order: if a buy would break it, that side stops and holds to settlement.

Polymarket's CLOB is new to me. In 2022 I wrote Python listeners for Solana events, and today I run async WebSocket services in production.

I've started a live build: poly-maker's engine in paper mode against the real 5m and 15m markets on my own Linux server, the nexosdata quote math ported behind unit tests, and a Binance WebSocket feeding fair value. It goes on the same page as soon as paper mode runs.

I'm building my Upwork profile, and with the depth I have in open-source integration and Python backends I can deliver this efficiently, so I'm bidding $200.

When we get on a call, I'll have several questions for you. A few examples:
- I'd ship it as a Docker container under systemd, set up by an Ansible playbook so the box rebuilds in one command. How do you deploy to your EC2 instance today?
- Is config.json a must, or is poly-maker's TOML fine if the dashboard edits it?
- Which wallet: a plain EOA, a Gnosis Safe, or a Polymarket deposit wallet?
```

One line was cut by Tyler the same morning before this version was filed as "sent": *"Although I use AI for nearly
everything, this is not AI generated."* It stays cut (a self-disqualifying line).

## Shape

Line by line, what each piece does, with `{{placeholders}}` for the client-specific parts. The shape drops exactly ONE
line of the sent letter: **"Polymarket's CLOB is new to me."** (Tyler's no-self-disqualifying rule). Everything else
carries over. Two later rules change the first paragraph and both win over the 11-09 wording: no link to our own pages
(RULES.md A2, since the 2026-11-11 circumvention warning; the video and diagram ride as proposal attachments) and the
proposal opens with what was built for this client (RULES.md rule 26; `presend_check.py --proposal` blocks anything else).

```
Hey, I built a first version of your {{thing, in the post's words}} for this post and recorded a short video of it; it's attached. {{one aside at most: the hour, or "I'm recording more videos that go deeper into {{his thing}}"}}.

In the video I walk through your post, {{the repos/links/tools his post names}}, and how I'd {{merge/build/fix}} them. {{3-4 sentences: his spec restated in HIS terms. Name each repo or tool he named; say what it keeps doing and what changes. Quote his own rule or number back to him ("The 0.97 rule is a check before every order: if a buy would break it, that side stops and holds to settlement.").}}

{{DROPPED: "Polymarket's CLOB is new to me."}} In {{year}} I wrote {{specific, dated work in his domain}}, and today I run {{his stack}} in production.

I've started a live build: {{what is running right now, on my own Linux server, against his real data/markets}}, {{the next piece, behind unit tests}}, and {{the third piece}}. {{What arrives next and when.}}

I'm building my Upwork profile, and with the depth I have in {{his domain}} and {{his language/backend}} I can deliver this efficiently, so I'm bidding ${{fixed post: under the LOW end of his budget; hourly post: 10 an hour (rule 35)}}. I run Utopia Models, Inc., an engineering agency.

When we get on a call, I'll have several questions for you. A few examples:
- I'd ship it as a Docker container under systemd, set up by an Ansible playbook so the box rebuilds in one command. How do you deploy to your {{his host}} today?
- {{Config/format question that shows I read his repo}}
- {{Account/wallet/credential question that only his setup can answer}}

The next build is {{the module named in the video}}, and I can start it the day you reply.

Tyler Youk, Utopia Models, Inc.
```

What each paragraph does:

1. **Opener**: what was built for him, and that there is a video of it (the "live audit" he quoted back). A real person
   read the post. The 4:57 a.m. line is allowed as one aside, never as the opener.
2. **His spec in his words**: every repo, rule and number from the post named back to him. This is the paragraph he
   answered point by point. No "I think", no "assuming".
3. **One proof line**: dated, specific, his stack. One sentence, never a resume. The sentence before it in the sent
   letter, *"Polymarket's CLOB is new to me."*, is the ONE line the shape drops; the proof half stays.
4. **"I've started a live build"**: what runs now, what comes next. The demo is the outcome made visible.
5. **The price, under budget**: *"I'm building my Upwork profile, and with the depth I have in ... I can deliver this
   efficiently, so I'm bidding $200"* is the allowed under-budget line, kept as written: it gives him the reason the
   price is low without arguing about rate. The rule-18 agency line sits beside it, never as sentence 1.
6. **2-3 setup questions**: deploy, config, accounts. Each one proves the repo was read and gives him a reason to reply.
   This is the one ask: the call. The Docker/systemd/Ansible deploy line is kept word for word.
7. **The one CTA**: the VSL's last spoken sentence is the next-build statement (`script_check.py` closing rule: a statement,
   no question mark, no "reply here"); the letter's last line before the signature says the same sentence, so both close on one thing.
8. **Signature**: `Tyler Youk, Utopia Models, Inc.` (Mohamed's existing room keeps "Tyler" for continuity).

## VSL

What Mohamed got, and what every proposal carries now.

**On the page when the letter went out (04:57 MT, 11-09):**

- **VSL 1, the intro** (≈5:33, 1,011 words; OBS `VSL` profile on Tyler's laptop: display capture of the client page +
  eMeet camera bottom-right; unscripted on the hormozi-vsl beats). Opens: *"I wanted to create this video just so you
  know that I'm a real person. I'm going through your entire proposal right now."* Then: his post on screen, both repos
  opened and read aloud ("this repo opened up the same time as this posting, are you the ones behind it?"), how they
  merge, the deployment question (Ubuntu EC2 in Ireland, Ansible, how secrets get injected), and the next step:
  *"I'm planning to start implementing this and have a demo."*
- **The architecture diagram** (`net/work/vsl/polymarket-mm-bot/diagram.json` → `polymarket-mm-bot-architecture.svg`):
  both repos with their stacks, every box `from <repo>` or `NEW`. Attached to the proposal as the PNG poster frame.
- **The client page** `clients.tyleryouk.com/polymarket-mm-bot` (`new-prospect.sh`; `entries.json`: detail, post
  verbatim, company research, bid, vsls). Linked then; attachments now (A2).

**Recorded the same sitting, before he replied:** **VSL 2, the technical walkthrough** (593 words): per-repo stack,
storage, risk rules, secrets, deployment. His hire quote names both: *"your live audit and demo video"*. After contract,
the M2 walkthrough MP4 (4:04, `m2-walkthrough.mp4`) was attached in his room on 11-13: proof MP4 attachments go through.

**The take for every new proposal** (RULES.md rule 27, from the 11-10 review of VSL 1 and 2):

- opens within 5 s on one verbatim phrase from his post, over his post on screen (the real-person hook is the quoted phrase, never an announcement);
- shows THEIR demo running (the "live build" paragraph made visible), never our dashboards;
- names their stack and every repo/tool from the post; say what I'd do, then ask one question back (no "I think",
  "I'm assuming", "seems like");
- no apology, no price talk, no employer, no agents or automation, no "if it's not the best";
- intro ≤ 90 s (VSL 1 ran 5½ min; cut the time-of-day/working-out open). The technical video may run long;
- one CTA: "Reply here and I'll send the next build.";
- export H.264/AAC, faststart, loudnorm, < 25 MB; attach the MP4 to the proposal (never a link); if the post has no
  attachment field it goes in the room after he replies. Review against `net/work/vsl/reviews/TEMPLATE.md` before
  send; log `ledger.py add video_sent`.

Pipeline: `net/subprocesses/interactive/upwork-vsl-apply.md` (job → repos read → client page + diagram → record →
publish + review → proposal with attachments → ledger). First run 95 min; target 30.

## Letter and VSL are one pitch (knowledge#14521, researched 2026-11-18)

The letter and the video are read in sequence by the same person, so they carry the same thesis and never repeat each other.
Evidence for each rule is in [proposal-vsl-coordination.md](../proposal-vsl-coordination.md).

| letter | video | rule |
|---|---|---|
| first 200 characters: what was built for him + "video attached" | opens in 5 s on a phrase quoted from his post | the two openers say the same fact in two media: a real person read the post and built for it |
| paragraph 2: his spec in his words | opener's one-sentence spec + the 3 beats | the SAME nouns and numbers in both; the video shows what the letter names |
| "It runs under 90 seconds: your post, the first build running, and one question for you." | those exact three beats, in that order | the letter promises the video's order; a viewer knows what to expect |
| setup question 1 | the same fact as a spoken STATEMENT ("I'll match how you deploy to X.") before the close; a spoken line never carries a question mark | the video answers the letter's first question with a plan |
| last line "The next build is ..., and I can start it the day you reply." | last spoken sentence, same words | one CTA |
| the diagram attached | the diagram on screen in beat 3 | same boxes, same names; each box `from <repo>` or `NEW` |

## Rules (knowledge#14741, Tyler 2026-11-17)

1. **The letter says what the client wants to hear.** His outcome, his words, his stack. Nothing about us he did not ask for.
2. **No "honest", no self-disqualifying line.** Not "this is not AI generated" (cut 11-09), not "Polymarket's CLOB is new to me" (the one line the shape drops), not "I'd make more as a corporate engineer". No apology anywhere. "I'm building my Upwork profile ... so I'm bidding $200" is allowed: it is the under-budget line, not a disqualifier.
3. **Agency voice**: first person, "I", as Tyler. "I run Utopia Models, Inc., an engineering agency" once, beside the price, never as sentence 1. Never name an agent, the fleet, or how the work gets done.
4. **Price UNDER the stated budget**: at or under the low end of his range (hourly: at or under the low end of his rate). Mohamed: $200 against $300-450.
5. **A custom demo + VSL attached before send.** No demo running, no video reviewed = no send. Attachments, never links (A2).
6. **Hunt = any engineering job.** Not only AI/automation posts. The shape fits any build with something to show.
7. Sentence 1 says what was built for this client; `voice.py check --agent horus --channel upwork --proposal` must PASS; log `proposals.py sent` the same minute.

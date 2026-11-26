# Eagle Eye feed (knowledge#13151)

> **Home: `packages/core` of utopia-models/eagle-eye** (moved out of knowledge `net/work/_tools/eagle-eye`, knowledge#19365). Per-deployment
> config (people, sender, mailboxes, prospect logos and stills) is the private overlay `utopia-models/eagle-eye-utopia`, checked out at
> `$EE_CONFIG` (`/srv/eagle-eye/config`; read through `eeconf.py`); runtime data is `$EE_DATA` (`/srv/eagle-eye/data`), never git. The feed on Ra
> runs from a clone of this repo: `bash packages/core/install.sh`. Code that reads knowledge's data stores finds the checkout at `$EAGLE_KB`.

The numbers behind https://eagle.utopiamodels.ai: every Hunt's `{sent, answered}` and every Roost's rows, measured
live from the stores, or an honest empty state that names the store. Spec: `net/work/specs/eagle-eye-data/spec.md`.

| file | runs where | what |
|---|---|---|
| `feed.py` | novaserver, as horus (piped over ssh) | reads the stores read-only, prints one JSON object; `--self-test` is offline |
| `refresh-data.py` | Ra, `~horus/dev/eagle-eye` | runs `feed.py` over ssh, writes `data.json` + `cold-apps.json` atomically; a failed measure writes nothing |
| `push-kv.sh` | Ra, unit `eagle-eye-feed.service` (horus `--user`, lingering) | every 30 s: measure, then PUT `data` + `cold-apps` + `lanes` into KV `eagle-eye-data` |
| `install.sh` | novaserver | copies the three files + the unit to Ra and restarts it |
| `deploy-worker.py` | novaserver | puts named page files (e.g. `/home-v2c.js`) into the LIVE `eagle-eye` Worker, keeping every other asset, the handler and the KV binding (knowledge#13174) |
| `v2_layout.py` · `oss_build.py` | novaserver | live `home-live.js` → the v2 page (`/v2.html`) → the open-source build (knowledge#13617) |
| `lane.html` · `lane_page.py` | novaserver | the lane pages `/hunt/<key>`, `/roost/<key>`: last 24 h, by company, target tiers, from `/lanes.json` (KV `lanes`, `feed.py` `lanes_detail`) (knowledge#13617) |
| `jobs-app/src/LanePage.tsx` · `lane-app.html` (knowledge#14769) | build with `npm ci && npx vite build`; fill lanes with `lane_page.py HOME_JS OUT dist/lane-app.html`; deploy the result as `/lane.html` (keep the live Upwork redirect line) | the generic lane page (`/hunt/in_person`, `/roost/*`, `/hunt/cold_apps` totals) rebuilt from shadcn Table/Sheet/Tabs/Badge, Tremor Raw Tracker (the 30-day sand river) + BarList, `motion`, `@number-flow/react`; rows peek into a Sheet (hash = open row), a sand ring per row's stage. Regenerated 2026-11-18 with the text command line (knowledge#16132): it POSTs same-origin `/phrase`, which the Worker does not yet relay to the ears gateway (tailnet+bearer only), so the page says "text line not connected" until it does. Deployed to the Worker 2026-11-25 (old page kept as `/lane-legacy.html`), but the Worker has no hostname and is superseded as a surface by `hunt-page/` (the live `eagle.utopiamodels.ai`; decision in `net/work/specs/14769-eagle-eye-pages/plan.md`, knowledge#19333) |
| `jobs-app/` · `upwork-jobs.html` | build anywhere with node (`npm ci && npx vite build`), deploy via `deploy-worker.py` | the Upwork jobs page `/hunt/upwork` (2026-11-17, Tyler via fleetmail 8687): React + shadcn Table/Badge/Sheet + Magic UI ShimmerButton from the registries, reading `/upwork.json` (`matches` + `applied`); deploy `dist/index.html` as `/upwork-jobs.html`, `dist/upwork-jobs.{js,css}`, and patch the LIVE `/lane.html` with a redirect line for `/hunt/upwork` (`?old=1` keeps the old table). The git `lane.html` differs from live, so never deploy it whole. `upwork-jobs.html` (vanilla) is the superseded first draft |
| `lane.html` · `apps.html` NEXT + VSL SENT | the same pages | every row on every hunt and roost page (companies, Upwork jobs/proposals/contracts, Social's people, In person's events, each cold application) carries its VSL-sent state (feed.py's per-company `vsls`) and a next action: the lane's own written next step when its store has one (pipeline.jsonl `next_step`), else a rule over the row's stage, replies, VSLs and age (`nextAction()` in lane.html, `appNext()` in apps.html; 5-day follow-up) (knowledge#14131) |
| `upwork_feed.py` · `upwork-eagle-feed.{service,timer}` · `upwork-badge.js` | novaserver, upwork `--user` timer, every 5 min | the Upwork lane: dev@ job alert mail + the upwork agent's ledger and proposals.db → KV `upwork` → `/upwork.json`; `lane.html` renders `/hunt/upwork` as the APPLIED jobs only (knowledge#14455: `applied`, newest send first, no counts; each row its next action, VSL yes/no, demo yes/no; a row opens the proposal drawer: text sent, bid, Connects, job post, client, dates, VSL, demo; knowledge#14741: the drawer opens on THESIS, the letter in three lines (Wants / Shown / Price, `letter_lint.thesis()`) + its lint verdict; deploy the page only after the upwork clone runs the new `upwork_feed.py`, or the live page has no `applied`), `upwork-badge.js` puts the count on the home Upwork eye; the Worker's `/data.json` takes the Upwork hunt's numbers from it (knowledge#14038) |
| `network_here.py` · `test_network_here.py` · `../linkedin/li_people.py` | novaserver (horus, inside the apps build; sekhmet `li-people.timer`) | YOUR NETWORK HERE in the Cold Apps drawer (knowledge#14278; the same ask refiled as #14277, ask 111, closed as a duplicate): `network_at(company)` joins the roster, the CRM (Twenty, owners tyler/atlas) and the LinkedIn 1st/2nd-degree lookups the human seat reads (`li-people`, read only, <=24 companies a day, newest application first from `/var/lib/net-network/queue.json`); cache `/var/lib/net-network/at/<key>.json`, daily. Probe: `sudo cat /var/lib/net-network/li/lookups.jsonl \| tail` |
| `phone-check.mjs` | anywhere with the site-audit Playwright | the gate before any home-page deploy (knowledge#14223, #14253): no overlap, nothing off the page, no sideways scroll and an unstretched canvas at 360/390/411/412 px (Chromium mobile + WebKit); the phone eye read from its own pixels: iris w/h 0.98-1.02, lids within 3% of the 1440 desktop eye's w/h, lids spanning 85-92% of the width; and the 1440x900 + 960x1080 layout box-for-box identical to live, each box keyed by what it is (`--desk-allow <regex>` names boxes a change was asked to move). `node phone-check.mjs --asset /home-v2.js=<built> --asset /who.js=who.js --asset /upwork-badge.js=upwork-badge.js` |
| `apps_feed.py` `campaign()` | novaserver, as horus (inside apps-push.py) | each Cold Apps company's campaign: people, step states, VSL slots, built from the campaign ledger + `net/work/outreach/campaign-steps.json`; adding a step or a VSL is a data change (`net/work/_tools/campaigns/README.md`) |
| `person_feed.py` · `person/` | novaserver, win `--user` timer | one person's ledger Sheet, or else their desk's apply store → KV `p/<person>`; the Worker's `/p/<person>` route + a person's pages (`person/install.sh`) (knowledge#14129) |
| `person/onboard-texts.sh` | novaserver, a one-shot win timer | texts each person their `/p/<person>` link from the RAW line, proves it from `fleetmail today`, reports on the issue (knowledge#14129) |
| `handler-dev.js` · `who.js` | the LIVE `eagle-eye` Worker handler + the person switcher it injects into `/` and every lane page | the person switcher (the admin and each person) (knowledge#14128): `?p=<person>` or the picker sets cookie `ee_p`; for anyone but Tyler, `/data.json` and `/lanes.json` are built only from that person's KV `apps/<person>` + `p/<person>`, and every lane with no store of theirs is an honest empty state. the non-admin people sign in through Access and are pinned to their own (no picker, Tyler's desks and feeds 403). Their old links `/p/<person>` and `/p/<person>` redirect to that home (knowledge#14303: the old pages read a ledger Sheet and showed 0 sent); every lane names their own agent (claire-scout, milli-scout). Pat signs in as osmanmaowia@gmail.example or osman@osmankhalid.example. Deploy: `deploy-worker.py --handler handler-dev.js /who.js=who.js` |
| `campaigns.html` · `handler-dev.js` `/campaigns` | the LIVE Worker; `deploy-worker.py` | every campaign, person and step on one page, from `/apps.json` `companies[k].campaign` (knowledge#15269, ask 113): per-step rollup, filter, nothing paged. The header's `data-rows` is the count of (person, step) rows the page drew, equal to the sum over the feed. Public demo: the same page in github.com/utopia-models/eagle-eye (`campaigns.html` + made-up `demo/campaigns.json`). |
| `pwa/` · `handler-dev.js` (PUB, serve, app, webpush, notifyAll) | the LIVE Worker; `deploy-worker.py --pwa` | the installable Android app, a stopgap until the store app (knowledge#14243, #14249): `/manifest.webmanifest`, `/sw.js` (offline page + push display, caches nothing private), `/pwa.js` (registers it; inside the installed app asks for notifications once on the first tap, no control on the page), icons from the eye mark. Those files plus `/favicon.*` are public through the Access bypass app "Eagle Eye · app files"; every other request needs Access's JWT. Push: VAPID (Worker secrets `VAPID_JWK`/`VAPID_PUBLIC` = Infisical fleet-infra `EAGLE_VAPID_PRIVATE_JWK`/`EAGLE_VAPID_PUBLIC_KEY`), subscriptions KV `push/subs/<person>` (the signed-in person only), a 1-minute cron diffs each person's replies + booked interviews/calls (KV `push/seen/<person>`) and pushes only new ones. Test: `POST /push/test`. Store app (knowledge#14268): the same `pushTo` also sends to KV `push/app/<person>` (written by eagle-eye-api `/v1/push/register`) through FCM HTTP v1, Worker secret `FCM_SA` (= Infisical fleet-infra `GOOGLE_SA_JSON_B64`, decoded); an iPhone's APNs token is exchanged by iid batchImport and works once Firebase holds an APNs key. Who is who is KV `people`, shared with eagle-eye-api (no inline map). Offline test: `node test_fcm_push.mjs` |
| `lane.html` ARCHITECTURE · `feed.py` `pipelines_feed` · KV `pipelines` · `/pipelines.json` | the LIVE Worker; `deploy-worker.py /lane.html=…` + `handler-dev.js` | the one-shot architecture diagram (knowledge#17952, ask 3202): the ARCHITECTURE button on `/hunt/upwork`, and a click on any row's stage strip, opens the diagrams drawn from `_infra/occ-feeds/pipelines.json` (wi/registry/pipelines.yaml), nothing hard-coded; the clicked stage is highlighted. Probe: `curl -s <eagle>/pipelines.json \| jq '.pipelines\|map(.id)'` behind Access. knowledge#17946: each Upwork stage box also shows a live count and a STUCK marker from `/upwork.json` (stages with no feed say so); `node test_arch_replay.mjs` replays an added and a renamed stage through `archHtml` with no edit to the page |
| `studio.html` · `push-kv.sh` (studio join) | asset `/studio` in the LIVE Worker (`deploy-worker.py /studio=studio.html`) | **the Studio panel** (knowledge#14747): every VSL from Kitsu, read only: client → video → task states, script versions, takes (Kitsu revisions with take-review's score and URL verdict), feedback newest first (Kitsu timecodes as chips), the deliverable. `push-kv.sh` runs `vsl studio feed` every 4th cycle and joins it into KV `lanes` as `.studio`, so the page reads `/lanes.json` and the handler is unchanged. Component `wi/components/vsl-studio.md` |
| `person/yusuf.html` · `person/yusuf-empty.json` | `/p/yusuf` + KV `p/yusuf` | Yusuf's page (knowledge#14243), fed by his agent temp-6a (#13806); until it writes a feed, KV holds the honest empty state in `yusuf-empty.json` |
| `phone-check.mjs` in the deploy | `deploy-worker.py` | any deploy that changes `/home-v2.js`, `/who.js`, `/upwork-badge.js` or `/pwa.js` runs phone-check with them swapped in first; a FAIL uploads nothing (knowledge#14243) |
| `phrases.html` | the LIVE Worker asset `/phrases` (`deploy-worker.py /phrases=phrases.html`) | the Eagle phrase cheat sheet (knowledge#16048): one screen, big type, generated from voice-v3 `phrases.tsv` by `phrases_page.py`; component `wi/components/eagle-phrases.md`. Regenerated 2026-11-18 with the text command line (knowledge#16132): it POSTs same-origin `/phrase`, which the Worker does not yet relay to the ears gateway (tailnet+bearer only), so the page says "text line not connected" until it does. Not yet deployed by the PR that added it |

Probe it, never trust a number written here:

    ssh pharaoh@ra 'sudo -u eagle XDG_RUNTIME_DIR=/run/user/$(id -u eagle) journalctl --user -u eagle-eye-feed -n 5 -o cat'
    curl -s -H "CF-Access-Client-Id: …" -H "CF-Access-Client-Secret: …" https://eagle.utopiamodels.ai/data.json | jq '.updated, .hunts'

## Sources (each hunt/roost carries its own `source`, `status`, and `reason` when empty)

- **upwork** — the upwork agent's `/home/upwork/.claude/state/net/upwork/ledger.jsonl` (`proposal_sent`, `client_reply`), all time;
  horus reads it through `setfacl -m u:horus:x /home/upwork` (knowledge#14154: horus's own copy stopped at the 11-15 cutover,
  which left the Upwork page "quiet for a day" over a 3 h old reply). Probe: `sudo -u eagle tail -1 /home/upwork/.claude/state/net/upwork/ledger.jsonl`.
  **Jobs have two intakes, and only one runs all day** (knowledge#14154): Upwork mails at most 5 "New job alert" mails a
  day, all between ~00:00 and ~06:30 UTC (5–11:30 PM MT; exactly 5 every day 2026-11-07..16), which `mail_watch.py` turns
  into `job_read` rows within the minute. Every other hour a job reaches the ledger only when the upwork agent reads one
  on its desk and logs it (`ledger.py add job_read`, SKILL.md "read and rank"). So an empty morning is the desk not
  logging reads, never the watcher. `/upwork.json` `intake` and the jobs header on `/hunt/upwork` say which; every
  `job_read` row is also on the lane's activity feed (kind `job read`). Probe: `sudo -u upwork bash -c 'grep job_read
  ~/.claude/state/net/upwork/ledger.jsonl | tail -3'`.
- **cold_apps** — net-funnel's `jobFunnel` window (applications.db + dev@ inbox), so sent and answered share one base;
  `sent_total` is applications.db all time.
- **linkedin** — `net/work/outreach/linkedin-log.csv` (hand-sent) + the worker's lane ledger
  `~sekhmet/.local/state/net-linkedin/ledger.jsonl` when horus can read it (`status: partial` until then).
- **cold_email** — horus's outreach store `emails.jsonl` / `replies.jsonl` (one first touch per thread) + the
  campaign and audience ledgers under `net/work/outreach/`. SalesBlaster has no API: it counts once `audience-c.jsonl` exists.
- **in_person** — `~horus/.claude/state/sf/events.jsonl`; until attendance is recorded it shows events found + events in the next 7 days (`labels`).
- **roosts.clients** — `_infra/occ-feeds/clients.json` (clients + prospects); also `clients[]`/`paid_total` for the
  marketplace page's client table.
- **roosts.network** — the network roster `~atlas/.claude/state/sf/network/roster.json` (atlas builds it; horus network-roster.timer retired 2026-11-19) (knowledge#14132): everyone Tyler
  knows from his sender@example.com Google Contacts (the only address book; dev@ unlinked 2026-11-16), his 1:1
  WhatsApp chats (tyler-wa) and LinkedIn, one row per person with every channel (`text · whatsapp · email · linkedin`);
  `people`, `in_contacts` and `channels` count them. Only a row with `referral_ok` (a tyler@ card) gets a referral ask.
  Built hourly by `net/work/_tools/outreach/roster.py build` (horus's `network-roster.timer`,
  `net/work/horus/network-roster/install.sh`). Recruiters and hiring teams are companies, not his network: they stay on
  the cold apps / cold email lanes. Without the roster file the roost falls back to `pipeline.jsonl` + `linkedin-log.csv`
  + `personal-network/*.md`. Probe: `sudo -u eagle jq '.people, .channels, .sources' ~atlas/.claude/state/sf/network/roster.json`.
  The page `/roost/network` renders those roster rows BY PERSON (most recent conversation first, a WhatsApp JID or bare
  number shown as "unsaved number", NEXT = the referral ask only for a `referral_ok` row) and its last-24-h list from each
  person's last 1:1 message; `lanes_feed.network` (recruiter stage changes) is used only when no roster exists (knowledge#14240).
- **roosts.social** — one row per person who wrote in on YouTube/X/Instagram/TikTok (`~rahman/.claude/state/rahman/inbox.jsonl`,
  read by horus through an ACL on novaserver); `youtube` = channel metrics from rahman's `state.json`.
- **latest** — every hunt and roost carries `latest` {ts, co, kind, what}: its newest event at or before now, any age (knowledge#13746).

## The page (knowledge#13174, #13207)

**The home page since 2026-11-16 (knowledge#14253, Tyler on the RAW Pixel):** hunts are Upwork, Cold apps and In person; roosts
are Clients and Network (LinkedIn and cold email fold into Cold apps; Social is off for now: `/hunt/linkedin`, `/hunt/cold_email`,
`/lane/linkedin`, `/lane/cold-email` land on `/hunt/cold_apps`, `/roost/social` and `/lane/social` on `/`). A hunt row has no
count. Tyler's roosts are the Clients row alone, its count and nothing else (knowledge#14261: no Network row, no latest line; `v2_layout.py` drops `network` for Tyler's view only, a person's Network roost stays). Hovering the eye shows nothing. On a phone the eye is the desktop eye at ~88% of the width and the page scrolls to it.
The feed (`feed.py`) still measures every lane: the cold-app campaign panels read LinkedIn and email from it.

`/` loads **`/home-v2.js`** since 2026-11-15 (knowledge#13746): `v2_layout.py` builds it from `/home-live.js`, so an edit to
`home-live.js` needs `v2_layout.py` + a redeploy of `/home-v2.js` to reach `/` (read `/` itself: `curl … /` shows the `<script src>`).
`/home-v2c.js` is an earlier variant.
Both sources are horus's files in `~horus/dev/eagle-eye/` on Ra (not in git). Every lane's desk chip in `/home-live.js`
reads the generated `DOORS` block (each lane's agent and its door, from lanes.yaml `agent`/`desk`/`view`). Doors are relative paths
(`/go/<lane>`, `/view/<lane>`) that the Worker proxies to desk-view through desks.utopiamodels.ai, so they open off the tailnet (knowledge#14131):

    python3 net/work/_tools/eagle_hunts.py --patch-doors home-live.js home-live.js   # regenerate the block in place
    python3 packages/core/deploy-worker.py /home-live.js=home-live.js
    python3 net/work/_tools/eagle_hunts.py --live-doors                              # PASS = every chip matches lanes.yaml

The doors themselves are `_infra/desks/desk-view.py` on novaserver (`wi/components/desks.md` § GO TO THE DESK).

`home-v2c.js`: Its `PIPES` list is generated from
`net/work/pipeline/lanes.yaml` (`python3 net/work/_tools/eagle_hunts.py --js`): each lane carries `feed` (its key under
`hunts`/`roosts` above) and, when the lane has a desk, `desk` (the desk's URL, shown as GO TO THE DESK). A hunt's glyph
draws sent as its outer ring and came back as its inner ring; a roost's hover card is the table name · hunt · stage ·
contracts · paid. Deploy a changed file and check it:

    python3 packages/core/deploy-worker.py /home-v2c.js=<local copy of home-v2c.js>
    python3 net/work/_tools/eagle_hunts.py --live

## Pricing (decided 2026-11-17, Tyler + purser as CFO)
Nothing is free. Early users are grandfathered early users, and the last discounted ones. Every NEW client pays one of:
- **A:** $1,000 setup + $600/mo all-in. We run the server and AI (cost about $250/mo, about $350 margin for heavy-usage months).
- **B:** $500 setup + $500/mo maintenance + server and AI usage passed through at cost (about $750/mo at today's cost).

Setup is due before work starts; monthly is billed in advance. No discounts, friends included. Basis: our real cost is about $250/mo per user. The $500/mo floor is Tyler's (05:48Z). Purser set the final price as CFO (fleetmail #7378); it isn't benchmarked against market comps yet.

**a person's roosts, In Person and facts (knowledge#14295, #14303):** `person_feed.py` builds KV `p/<person>` from their own stores. **Clients** = employers that answered (interview, offer or rejection) from their ledger or apply store; **Network** = the people their agent works at their companies, from their campaign ledger (`campaign.py --person`: found, connect sent, connected, DM sent, replied); **In Person** = `candidates/<id>/in_person.jsonl`, written by `in_person_find.py` (Luma place pages, filtered by each person's `PROFILES`; `eagle-eye-in-person.timer` every 6 h) and shown as the In Person hunt and lane; **facts to ask** = what their desk is blocked on (`blocked_missing_fact`, newest ground truth), shown as a panel on the applications page. The per-company campaign panel (app, connect, DM, reply) is the existing `apps.html` drawer reading their own ledger. Luma has no Santa Barbara place page, so a person's events come from the DC/Fairfax page until another source is added; an empty list says so. Probes: `python3 person_feed.py --self-test`, `python3 in_person_find.py --self-test`; live: `python3 person_feed.py osman | jq '.hunts.in_person, .facts'`.

## The product site, eagleeye.sh (knowledge#14308)

The open-source Eagle Eye's landing page lives in `github.com/utopia-models/eagle-eye` `site/` (Cloudflare Worker
`eagleeye-site`), not in this folder. Tyler's "same magic feel as live.utopiamodels.ai and utopiamodels.ai" (ask 128)
and "the real eagle eye instead of that logo eye" (ask 127) were built there by eagle-eye PR #5 (the real
`home-v2.js` eye over the Utopia sites' OGL sand renderer) and PR #6 (Horus as nav/footer logo and favicon). Probe
the result, never trust this line: open `https://eagleeye.sh` and `https://utopiamodels.ai` side by side in headless
Playwright; both are gold sand on ink with a WebGL canvas.

**2026-11-25 (knowledge#14769):** the `eagle-eye` Worker is bound to no hostname (probe: `GET accounts/<id>/workers/domains` lists only `eagle-api` and `dev.eagle`; `.../scripts/eagle-eye/subdomain` enabled=false), so every `deploy-worker.py` page, `/lane.html` included, is unreachable by Tyler. `curl -H CF-Access… https://eagle.utopiamodels.ai/data.json` is a Ra python 404.

## The One-shot system chip opens the architecture (knowledge#17946)

The live `eagle.utopiamodels.ai` is NOT the `eagle-eye` Worker: the tunnel sends it to Ra `:8797`, `server.py` serving
`/home/architect/dev/utopia-models/_shots/stream-vsl/eagle-eye-spike/public` (not in git). #17975's `lane.html` diagram therefore never reached the
hunt list or hunt detail chips. `opt/arch.js` (click on any `[data-oss-system]` opens a full-screen diagram from `/pipelines.json`; the chip
reads "Upwork", never "Upwork Entire VSL") is installed by `sudo python3 opt/patch_live.py <that public dir> opt/arch.js _infra/occ-feeds/pipelines.json`
on Ra (idempotent, backs each file up). Test: `node opt/test_arch.mjs`. Probe the origin: `ssh pharaoh@ra 'sudo ss -ltnp | grep :8797'`.

### One-shot view with provenance and THE OFFER (knowledge#18326)

The chip now opens the row's one-shot pipeline with the row's stage highlighted; clicking a stage shows its inputs, generator, checks and output
(`inputs/generator/checks/output` on each stage in `wi/registry/pipelines.yaml`; a stage without them says "source not recorded"). Founder and
job-post rows show `One-shot system: Founder 14-Day Build` (pipeline `founder`, ending in THE OFFER). The OFFER panel reads `/offer.json`, built by
`OFFER_SRC=<MAX-FOUNDER-PACKAGE-FINAL.md> python3 _infra/scripts/offer-feed.py` into `_infra/occ-feeds/offer.json`. Install (Ra, root):
`python3 opt/patch_live.py <public-dir> opt/arch.js _infra/occ-feeds/pipelines.json _infra/occ-feeds/offer.json`. Test: `node opt/test_arch.mjs`.

Live install (2026-11-24, knowledge#17946): `ssh pharaoh@ra` has passwordless sudo and reaches the architect's `eagle-eye-spike/public`; copy the four files to a temp dir there and run `sudo -n python3 patch_live.py <public-dir> arch.js pipelines.json offer.json`. Verified in WebKit against the Ra origin: the hunt-row chip reads "Upwork", a click opens the 9-stage full-screen diagram from `/pipelines.json`.

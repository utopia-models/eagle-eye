---
id: research.plugin-architecture
title: Core plus systems - how a small open core hosts outreach systems as plugins
kind: research
version: 1.0.0
tags: [architecture,plugin,eagle-eye,overlay,license]
date: 2026-11-24
license: CC-BY-4.0
---
# Make Eagle Eye a core plus systems

**Build Eagle Eye as a small Apache-2.0 core that owns hunts, sources, the event ledger and a "System" runner. Each outreach motion (upwork-oneshot, cold-apply-campaign, founder-oneshot) is a folder with a manifest and typed stages. Everything private lives in a separate overlay repo plus a runtime data directory, and the repo refuses to start if its data directory sits inside the checkout.** The public `utopia-models/eagle-eye` repo is already Apache-2.0 (its LICENSE file opens "Apache License, Version 2.0" and its package.json says `Apache-2.0`), so it is the right home. It is a small static viewer today (86 files, about 2.2k lines), while the real server, `eagle-eye-v2`, is a separate repo with no remote. Roughly 45 to 55k lines of reusable core and kit code (my estimate from the counts) sit in the private `knowledge` repo and still carry Utopia paths, hosts and 32 distinct embedded email addresses (local measurement, `knowledge/net/work/_tools/{vsl,eagle-eye,upwork}`). The license conflict is smaller than it looks. The AGPL-3.0 label is only a `package.json` field; there is no LICENSE file, and all 20 commits are authored by the org's own agent accounts. The server's dependencies (hono, drizzle-orm, pg, pg-boss, zod) are permissive. I recommend relicensing the server to Apache-2.0 at import, with the owner's own commit and no outside consent needed. The contract below borrows the strongest parts of Grafana, Home Assistant, Windmill, Trigger.dev and Temporal. In short: a required host-compatibility range, a declared config and secret schema, ordered stages with JSON-Schema I/O, a host-owned retry policy, and a host-minted idempotency key that must reach the outbound call. Before the public repo takes any imported history, treat it as irreversible. Extract by allowlist and scan, or fall back to a squashed snapshot.

## What exists today and where it cuts

The code lives in at least six places, so the migration is a re-pointing exercise and not a rename. From local measurements of this box on 2026-11-24:

- **Viewer:** the public repo `eagle-eye` holds a static JS viewer, `adapters/csv_feed.py`, `docs/FEED.md` and the eagleeye.sh site.
- **Server:** the `eagle-eye-v2` server (about 100 files, 9.3k lines; Hono, drizzle, pg-boss; migrations 0001 to 0013; `send/` with hunt_send, upwork_reply, followups and stuck_alarm) is byte-identical to `knowledge/net/work/_tools/eagle-eye/hunt-page/v2`. It has 20 commits, no remote and a dirty working tree (modified `app.ts`, `events.ts`, `feed.ts`, `viewer.ts`; untracked `stuck.ts` and tests). That dirty state is the version that runs.
- **Production feeds and pages:** a third lineage lives under `knowledge/.../_tools/eagle-eye` (Python feeds, jobs-app, pwa, Cloudflare KV push). A fourth is a drifted non-git copy at `/home/eagle/dev/eagle-eye`. The funding, investor and oneshot hunt loops run from a fifth place, `_shots/stream-vsl/hunts/*/agent`.
- **One-shot pipeline:** `_tools/vsl` is about 18.7k lines, with `oneshot_auto.py` at 2,005 lines importing about 25 sibling modules. It actually runs from `/home/upwork/oneshot/kb-v2`, a branch clone of knowledge.
- **Cold-apply:** the `apply.py` family is about 14k lines plus ATS drivers, `jobs/sekhmet_campaigns.py` (671 lines, "every application opens a campaign at its company") and `campaigns/` and `outreach/`. It ran as unix user `horus` on novaserver.

Hardcoded paths are the real coupling. `/srv/vsl` appears in 38 code and unit files, `/var/tmp/eagle-send` in 8, `/home/upwork/oneshot` in 8, and tailnet IPs in 19. Utopia identity is not limited to data. It sits in code as mailboxes, `*.utopiamodels.ai` routes, Tyler's voice rules and one-shot decisions, and migrations such as `0002_seed_tyler` and `0013_upwork_entire_vsl_default`.

I classify the code into five buckets. **Core** is the hunt, roost and event model, the feed schema, ingest and SSE, follow-up and stuck alarms, `autosend.py`'s pure decision logic and `gates.py`. **Kit** is shared tools that systems import: render and mux, the capture browser, seat drivers (`desk`, `humanseat`), `letter_lint`, `ledger`, `crm`, take-flow and `eagle_emit`. **Systems** are the three motions. **Plugins** are sources (aggregator boards, ATS pollers, upwork triage) and senders (`intro_sender`, `upwork_reply`, `network_send`, the SalesBlaster CSV export). **Overlay and data** are CRM, calls, candidate ground truth, resumes, letters, per-company `facts.yaml`, `send/state`, `/srv/vsl` (3.3G) and `/home/upwork/oneshot` (13G). Data never moves into git. The knowledge repo is private with a 2.2G `.git`, so every extraction must be a new-repo allowlist export, never an in-place filter.

## The System contract

The market survey gives the shape of a campaign: a campaign owns steps and stop rules, an enrollment holds `(lead x campaign, current_step, state, reason, timestamps)`, and events record sent, reply and bounce. State enums converge on pending, active, paused, stopped or finished, and failed, with a separate reason field so a manual pause differs from a system stop ([Outreach data dictionary](https://developers.outreach.io/data-sharing/data-dictionary-v1/sequence-states); [Smartlead lead statuses](https://helpcenter.smartlead.ai/en/articles/106-what-do-lead-statuses-mean-in-a-campaign.md)). Three consequences follow. A **hunt is the enrollment**, so state and stop flags live on the hunt and not on the System. A System is a versioned template, which is the playbook idea in [11x's docs](https://docs.11x.ai/alice/overview). **Reply detection is a hunt-level kill switch in core**, not a per-System feature. [Instantly's stop_on_reply and stop_for_company flags](https://developer.instantly.ai/guides/webhook-events) show why company-wide stop must be core. Assets such as the VSL are an async stage that writes `url` and `status` onto the hunt. Downstream message stages gate on `asset=ready`, as in Smartlead's "Stopped: missing data" ([Smartlead](https://helpcenter.smartlead.ai/en/articles/106-what-do-lead-statuses-mean-in-a-campaign.md)).

On manifests, only Grafana and Home Assistant make compatibility a required field. Grafana requires `dependencies.grafanaDependency` as a semver range, and Home Assistant exact-pins requirements and separates hard `dependencies` from soft `after_dependencies` ([Grafana plugin.json](https://grafana.com/developers/plugin-tools/reference/plugin-json); [HA manifest](https://contributors.home-assistant.io/core/integrations/manifest/)). Windmill's OpenFlow is the closest model for staged pipelines: unique module ids, `results.<id>` references, `skip_if`, `suspend` for approval and a `failure_module` ([OpenFlow](https://www.windmill.dev/docs/openflow)). The recommended manifest is `system.yaml`:

```yaml
id: upwork-oneshot            # immutable, matches folder
name: Upwork one-shot (proposal + VSL)
version: 1.4.0                # system semver; major = needs migrate()
contract: ">=1 <2"            # host compat range (Grafana-style, required)
owners: [vsl]                 # CODEOWNERS key
side_effect_class: outbound_irreversible   # local | outbound_reversible | outbound_irreversible (HA iot_class idea)
applies_to: { hunt_kinds: [upwork_job], roost_kinds: [] }
config_schema: schemas/config.schema.json  # per-hunt-overridable JSON Schema
secrets: [UPWORK_SEAT, GMAIL_SEND, R2_KEY]  # key NAMES; host resolves and injects only these
requires:
  kit: [render/v1, capture/v1, voice/v1, letter_lint/v1]   # versioned block ids, additive-only
  sources: [upwork-feed/v1]
  senders: [upwork-reply/v1]
  optional: [vsl-studio/v1]             # soft dependency
stages:
  - id: triage
    run: stages/triage.py:run
    in: schemas/triage.in.json
    out: schemas/triage.out.json
    retry: { max_attempts: 3, backoff: exponential, base_s: 5, non_retryable: [NoFit, PolicyBlock] }
    timeout_s: 60
    reversible: true
  - id: build_asset          # async: queued -> rendering -> ready | failed
    run: stages/build_asset.py:run
    skip_if: "hunt.fit < 0.4"
    timeout_s: 3600
    reversible: true
  - id: verify
    run: stages/verify.py:run   # acceptance gates; fail = hold, never send
  - id: approve
    suspend: { until: [human_ok, timer_expired], timer_by_fit: { high: 45m, mid: 30m, low: 0 } }
  - id: send
    run: stages/send.py:run
    reversible: false
    idempotency: required       # host passes idempotency_key; stage must forward it
    retry: { max_attempts: 2, non_retryable: [AlreadySent, Rejected] }
  - id: follow_up
    run: stages/follow_up.py:run
    schedule: { steps: [{ after: 3d }, { after: 7d }], stop_on: [reply, bounce, meeting] }
events:
  emits: [stage.started, stage.progress, stage.succeeded, stage.failed, asset.ready, sent, reply.classified]
  consumes: [reply.received, hunt.stopped]
lifecycle: { validate_config: hooks.py:validate, setup: hooks.py:setup, teardown: hooks.py:teardown, migrate: hooks.py:migrate }
```

The stage interface has one rule: **a stage is a pure-ish function `run(ctx, input) -> output | raise`**. `ctx` carries `hunt`, a `config` slice validated at boot, a `secrets` getter limited to the declared names, a per-System namespaced `store`, `emit(event)`, `kit` handles, `idempotency_key` and `attempt`. Input and output are JSON Schema validated at every stage boundary, on both entry and exit. Windmill leaves validation off by default and Trigger.dev validates twice ([Windmill](https://www.windmill.dev/docs/core_concepts/json_schema_and_parsing); [Trigger.dev schemaTask](https://trigger.dev/docs/tasks/schemaTask)), and for irreversible sends the strict end of that range is the safe one. The stage output is merged into the hunt as `results.<stage_id>` and persisted before the next stage starts, so a crash resumes at the first incomplete stage.

Retries and idempotency are owned by the host, as in Temporal and Trigger.dev. Policy is declared per stage with non-retryable error types ([Temporal retry policies](https://docs.temporal.io/encyclopedia/retry-policies); [Trigger.dev tasks](https://trigger.dev/docs/tasks/overview)). The host mints `idempotency_key = sha256(system_id, hunt_id, stage_id, content_hash)` and the stage must pass it to the outbound call and to the sent-ledger. Trigger.dev's semantics are the right ones to copy: **a failed run clears the key and a success keeps it**, so a send never happens twice and a failure can retry ([Trigger.dev idempotency](https://trigger.dev/docs/idempotency)). Dedup at trigger time is not enough for send, because the key must reach the mail or Upwork call itself. `reversible: false` stages never auto-retry after an ambiguous outcome such as a timeout after the request left. They go to `held` for a read-back check, which fits the repo's existing "read back before you claim" rule. Medusa's per-step compensation is the only undo contract surveyed, and almost nothing here can be compensated, so the flag stands in for it ([Medusa workflows](https://docs.medusajs.com/learn/fundamentals/workflows)).

Roosts need no new machinery. A roost is a second target source plus a roost-level default System list, and the same contract applies. The hunt record stores `{system_id, system_version, config_overrides}`. This is the Home Assistant blueprint pattern, an independent instance that stays linked to its template ([HA blueprints](https://www.home-assistant.io/docs/blueprint/)). The picker lists installed Systems filtered by `applies_to`, renders a form from `config_schema` and stores only overrides, in the n8n sub-workflow style ([n8n Execute Workflow](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.executeworkflow/)). Version rules follow Home Assistant. A minor bump is additive with defaults. A major bump runs `migrate()` before setup. A hunt pinned to a newer major than the installed System refuses to run and does not guess ([HA config entries](https://contributors.home-assistant.io/core/integrations/config-entries/)).

How the three Systems map onto the contract:

| System | Source | Assets | Send | Follow-up | Reuse |
|---|---|---|---|---|---|
| upwork-oneshot | upwork-feed (triage, job-desc) | intro or full VSL, proposal text | upwork-reply, intro_sender | timers by fit, claim plus fallback | `autosend` state machine, `gates`, `acceptance` |
| cold-apply-campaign | ATS and aggregator pollers | tailored resume variant, answers | ATS drivers (workday, ashby, smartrecruiters) | per-company campaign: harvest people, SalesBlaster CSV or mail | `apply_store`, `sekhmet_campaigns` join logic |
| founder-oneshot | funding and founder hunts | founder VSL, page | hunt_send, network_send | followups.py | contract yamls, `startup.yaml` pipeline |

Two other candidates use cold-apply-campaign. They are candidates with their own ground truth under `net/work/apply/candidates/`, so they are overlay data selected into the System's config. They do not become code branches.

## Isolation, config and the private overlay

On isolation, n8n calls its same-uid in-process runner insecure by design and deprecates it, and its external mode passes only an allowlist of env vars to runners ([n8n task runners](https://docs.n8n.io/hosting/configuration/task-runners/)). Grafana runs backends as subprocesses over gRPC so a crash does not take down the host ([Grafana backend plugins](https://grafana.com/developers/plugin-tools/key-concepts/backend-plugins/)). Activepieces' privileged process sandbox "should never share a node with unrelated workloads" ([Activepieces sandboxing](https://www.activepieces.com/docs/install/architecture/sandboxing)). For a team whose Systems are first-party or agent-written and reviewed in PRs, the practical choice is a **subprocess per stage run with a scrubbed environment containing only the declared secrets**, as n8n does. It gives crash isolation and a typed boundary that agents can edit against. Containers or isolates are only worth adding if third-party Systems arrive.

Config follows Backstage's layering: committed defaults, then the overlay config, then a gitignored local layer, then env, with objects deep-merging and arrays replacing ([Backstage config](https://backstage.io/docs/conf/writing/)). Backstage's silent `undefined` for a missing secret is the thing not to copy. **Eagle Eye fails at boot when a declared secret cannot be resolved.** Secrets are `${infisical:project/KEY}` references resolved at start, and a System sees only the names in its manifest. The load order is `examples/config` defaults, then `$EE_CONFIG/*.yaml`, then `$EE_CONFIG/local/*.yaml`, then env. The three directories are `EE_CONFIG` (overlay checkout), `EE_DATA` (ledgers, caches, sqlite) and `EE_MEDIA` (takes, renders, outbox). Startup aborts if `EE_DATA` or `EE_MEDIA` resolve inside the repo checkout.

The overlay is a private repo, `utopia-models/eagle-eye-utopia`, checked out at `/srv/eagle-eye/config`. None of the surveyed open-source projects use an overlay repo (they use a gitignored local file or data directory); here it is justified because hunts, copy and CRM mapping need review history and must sync across the Ra and novaserver boxes. It holds the real hunt definitions, intros and letters, brand voice, candidate ground truth, per-company facts, CRM, an `overlay/systems/` folder for private Systems and a `boxes/<host>.yaml` that picks which units run where. A private System is discovered from `$EE_CONFIG/systems/` the way Home Assistant discovers custom components. Fleet-specific glue (fleetmail, Kitsu verbs, the tyler-wa outbox) is implemented there behind the SDK interfaces, so the public core imports nothing from the fleet. Rendered media, voice WAVs and ledgers stay out of git entirely, with a backup to a private bucket.

## Repo layout, agents, testing and CI

The tree keeps the earlier pass's `apps/`, `packages/`, `plugins/`, `deploy/`, `examples/` split but changes one concept: what the earlier pass called plugins and oneshot packages become **Systems and kit**, because the System is the unit users pick. The shape is `apps/` (api, hunt-ui, pwa, worker, site), `packages/` (core, sdk, kit with render, capture, voice, copy-lint and seats, plus a conformance test kit), `systems/<id>/` with `system.yaml`, `stages/`, `schemas/`, `tests/` and `fixtures/`, `plugins/` for sources and senders, `deploy/` (systemd templates, `install.sh`, optional docker), `docs/` with `docs/decisions/`, `examples/config/` (a complete fake deployment a stranger can run), `AGENTS.md`/`CLAUDE.md`, `CODEOWNERS` and `.github/workflows/`. Mixed Python and TypeScript stay as pnpm and uv workspaces behind one Makefile, which is the same pragmatic shape as the LangGraph and Cal.com templates. The earlier pass reached this layout from a survey of ten projects, for example `apps/` plus `packages/` plus one folder per integration. There is one boundary rule, enforced by a lint in CI. A System imports only `sdk`, `kit/*/vN` and its own folder, and never another System or an app. Core imports no System.

Agents (eagle, vsl) work as **Claude Code sessions in git worktrees**, one per issue, never in the release checkout. They change a System through a narrow loop: edit stage code or `system.yaml`, run `make test SYSTEM=<id>`, which runs the conformance suite and the System's own tests offline against fixtures, then open a PR with `Closes #N`. `AGENTS.md` carries the loop and the contract summary, and a `new-system` scaffold command produces a passing skeleton so agents never start from a blank file. Ownership follows CODEOWNERS: vsl owns `systems/upwork-oneshot` and `packages/kit/{render,capture,voice}`, eagle owns hunts, sources and `apps/`, and the Architect owns `deploy/`, `.github/`, `sdk` and the overlay structure. Per the fleet merge rule nothing gates main, except that the secret scan stops a merge. A real build failure is fixed and never overridden.

The conformance suite is the key testing asset. Home Assistant uses committed snapshots, with the caveat that they do not replace functional tests ([HA snapshot testing](https://developers.home-assistant.io/blog/2023/02/20/snapshot-testing/)). n8n runs a linter plus a package scanner in CI ([n8n verification](https://docs.n8n.io/integrations/creating-nodes/build/reference/verification-guidelines)). Combined, `runContract(system)` checks that the manifest validates, example config validates, each stage's I/O schemas accept the fixtures, a second run with the same idempotency key makes no second outbound call, a failed run clears the key, no network is touched without a recorded fixture, and a `reversible: false` stage refuses to auto-retry after an ambiguous result. The `autosend.py` countdown, claim and fallback logic is already stdlib-pure and covered by the 56 existing vsl tests (3,403 lines), so those port as the System's golden tests. CI has four lanes: lint plus the boundary and literal-path grep (no `/srv/`, `/home/` or IP literals outside `deploy/`), unit plus conformance, a gitleaks and trufflehog scan, and a Playwright WebKit end-to-end run of `examples/config` at phone and desktop widths. I did not find a recorded-HTTP library source-verified in the research (nock, MSW or Polly are tooling choices, not findings), so the harness's choice is open. Fixtures must be synthetic. Real-data replays live in the overlay.

## License resolution and migration order

The AGPL conflict resolves in favor of Apache-2.0. The server is at `AGPL-3.0` only in `package.json`; no LICENSE file exists, and every commit is by the org's agent accounts (3 `kxagent`, 17 `utopia-models-fleet[bot]`). No outside contributor holds copyright, so the owner can relicense unilaterally. Every runtime dependency is permissive, so nothing in the tree forces copyleft. Keep Apache-2.0 because the public repo and eagleeye.sh already promise it, because the moat (hunts, face and voice, client data, operation) stays in the overlay, and because the AGPL projects surveyed (Cal.com, Dub, Plane, Twenty) use it to protect hosted SaaS, which is not this product. n8n's fair-code license is not OSI-open and needs a CLA. The cost-free hedge is a DCO sign-off and an `NOTICE` with a trademark line for "Eagle Eye" and "Utopia Models", and the PostHog `ee/` directory model remains available if monetization ever arrives. The relicense commit lands first, in the server's own history, before any extraction, with the `package.json` field changed and an Apache LICENSE file added. If any copied third-party AGPL code turns up in the scan, it is rewritten or removed, but nothing in the inventory suggests it exists. I could not verify that from the research, since the notes did not scan license headers in file bodies, so the import step includes a license-header grep.

The migration order (each step reversible until the cut-over) is below.

1. **Freeze and commit:** commit the dirty `eagle-eye-v2` tree, because knowledge's copy already contains that uncommitted state, and give it a remote.
2. **Classify:** run a script that tags every file in the three knowledge subtrees plus v2 as `public`, `overlay`, `data` or `delete`. Anything with a person's name or email, a client id, `*.jsonl`, `crm/`, `calls/`, `agency/`, `one-shot/runs` or real letters goes to overlay or data. The untracked `evwt/` mirror, `__pycache__`, `spike/` and superseded HTML variants are deleted.
3. **Extract with an allowlist, not a denylist:** use `git filter-repo --paths-from-file` with path renames into the new tree and `--replace-text` for identities, then run gitleaks and trufflehog over all history. Any hit goes back into the replace file and the extraction restarts. If history cannot be proven clean, import a **single squashed snapshot** that records the source commit. The public repo already exists, so a leak is permanent. Apply the same extraction to the overlay repo.
4. **Parameterize:** replace hardcoded paths (`/srv/vsl`, `/var/tmp/eagle-send`, `/home/upwork/oneshot`, `~/.claude/state`) with the `EE_*` loader, move the seeded migrations (`0002_seed_tyler`, `0009` to `0013`) into overlay config, and gate it with the literal-path grep in CI. `wi/registry/pipeline-paths.yaml` and `oneshot-auto.yaml` already centralize some paths and are the natural seams.
5. **Wrap, then split:** wrap each of the three motions in a `system.yaml` first. Start with upwork-oneshot, since `autosend` and `gates` are already pure, then cold-apply, which is the largest (the 14k-line `apply.py` is classified here by name and docstring only, not by reading its body), then founder. Split stage code from the monoliths only where a seam exists. Do not rewrite for elegance.
6. **Run side by side:** install on Ra and novaserver, run old and new in dry-run for one hunt cycle, and compare with `acceptance.py` and the golden tests as the oracle.
7. **Re-point and delete:** re-point the 215 files in knowledge that reference the old paths, swap the units, install an updated checkout for user `upwork` and for eagle's clones, and prove each unit with `mechanism-liveness.sh` on every box. Then `git rm` the three subtrees and delete the stale copies, leaving no `archive/`.
8. **Stranger test:** only then announce, after a fresh VM runs `curl eagleeye.sh/install | sh` with the example config and renders sample data.

## Conclusion

The main change from the earlier pass is where the seam sits. The earlier proposal split packages by capability (oneshot, hunts, sender and source plugins). The research argues for splitting by motion: a System is the unit people choose, versioned and tested as a whole, and what it shares is a thin, versioned kit. Per-enrollment state, reply kill-switches and the idempotency key belong in core, where the market tools also put them. A System owns only its stages, schemas and copy rules. That placement makes roosts nearly free, because a roost is another source with its own default System list.

Two items remain open. The research did not verify any recorded-HTTP test tool, any per-step evidence pattern in competing products (none documents it, so per-claim source links are a possible differentiator) or the generic share of `apply.py`. The contract's `contract: ">=1 <2"` range is a starting rule that Eagle Eye will need to exercise on a first real major bump. For the license, the only judgment call is whether to keep the DCO or add a CLA if outside contributors ever appear, and the permissive default keeps both options open.

needs_tyler: none
input_not_gate: none. License relicensing is the owner's own act; third-party header scan and apply.py body review are execution steps in the migration.

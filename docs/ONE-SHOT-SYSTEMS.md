# The one-shot systems (resource pack)

Eagle Eye ships with the Utopia Models one-shot systems as a resource pack: the Upwork proposal rules and templates
and the founder video ("VSL") tooling the agency runs on, for you to adapt toward your own goals.

## What is in this release

`imports/knowledge/net/work/` is an allowlist-built, gitleaks-clean snapshot:

| path | what it is |
|---|---|
| `upwork/RULES.md`, `POLICY.md`, `PACE.md` | how proposals are written, what is allowed, how fast to send |
| `upwork/templates/<category>/` | per-category proposal templates and demo scripts |
| `_tools/vsl/` | the video one-shot tooling (script, render, review helpers) |

Status: this is a staging snapshot. Paths and hosts inside still reflect the original deployment; the move into
`systems/upwork-oneshot` and `packages/kit` with a config loader (`EE_CONFIG`, `EE_DATA`, `EE_MEDIA`) is tracked in
utopia-models/knowledge#19366. Until then, treat the files as reference you copy and edit.

## Install

```bash
git clone https://github.com/utopia-models/eagle-eye && cd eagle-eye
cp -r imports/knowledge/net/work/upwork ./my-upwork      # rules + templates, yours to edit
cp -r imports/knowledge/net/work/_tools/vsl ./my-vsl     # video tooling
```

1. Read `my-upwork/RULES.md` and `POLICY.md`, then edit them to your offer and voice.
2. Pick a template under `my-upwork/templates/` and replace the example details with your own.
3. Point your agents' ledger at Eagle Eye with `adapters/csv_feed.py` (see the main README) so each proposal sent
   and each reply shows on the screen.
4. Check any script path or address in `my-vsl/` before running it: replace hardcoded values with your own.

Do not commit your own credentials or client data; run `scripts/pii-grep.sh` and gitleaks before pushing.

# Eagle Eye hunt page: source in git (knowledge#18540)

https://eagle.utopiamodels.ai is served from Ra by `eagle-ui.service` (architect `--user`): `server.py 100.127.249.81 8797` in
`~architect/dev/utopia-models/_shots/stream-vsl/eagle-eye-spike/`, static `public/`, proxying `/api/feed` from `eagle-server.service`
(Hono, `~architect/dev/utopia-models/eagle-eye-v2`, `src/feed.ts`). This directory is that source; edit HERE, ship with `deploy.sh`.

| here | on Ra | what |
|---|---|---|
| `ui/` | `eagle-eye-spike/public/` | index.html + `opt/` (detail.js = hunt detail drawer, roosts.js, intro.js, arch.js, css) + assets/fonts/vendor/icons/logos |
| `spike/` | `eagle-eye-spike/` | `server.py`, `live_refresh.py`, `tools/layout-check.py` |
| `v2/` | `eagle-eye-v2/` | `src/feed.ts` (the `/api/feed` rows: timeline, demo state, file), `src/events.ts`, send/, deploy/ units |

Not in git (generated or media, never overwritten by deploy): Ra `public/hunts/<slug>/` (take.mp4, mvp), `public/v/`, `public/oneshot/`, `public/people/`, `offer.json`, `pipelines.json`.

Deploy (from any clone, Ra or novaserver): `bash packages/core/hunt-page/deploy.sh [ui|spike|v2|all] [--dry-run]`. ui is live at once; spike/v2 restart their unit.
Gate before shipping UI: on Ra `~/.local/share/fleet-playwright/bin/python tools/layout-check.py` must print PASS.

Stage budgets (knowledge#18576): `v2/src/stuck.ts` (`BUDGET_H`) sets how long a row may wait after each step; `/api/feed` `timelines[id].stuck` carries the flag, `detail.js` shows it, `v2/send/stuck_alarm.py` (+ `deploy/eagle-stuck-alarm.{service,timer}`) fleetmails thread `eagle-stuck`. Review and plan: `net/work/specs/18576-eagle-eye-legacy-review/plan.md`.

Take over a hunt (knowledge#18939): the drawer's "Take over" card (`detail.js`) has FULL VSL / INTRO VSL. It calls `/api/take` (spike `server.py` proxy) -> `net/work/_tools/vsl/take_api.py` (system unit `vsl/systemd/vsl-take-api.service`, loopback :8817, user `upwork`) -> `oneshot_auto.take_over`: pick + claim (stops the intro countdown) + `vizier-put.sh` of the package's `entire-script.md`. Voice ("full VSL on this one" / "I'm on") goes `eagle_verbs job.claim` -> `oneshot_auto.py claim <slug> voice`, which now loads the script too. The intro timer needs no separate unit: `oneshot-auto-serve` `tick()` runs `due_intros()` (autosend.py) every 20 s. Probe: `curl -s '127.0.0.1:8817/take?job=<digits>'` on Ra. Test: `python3 -m unittest net/work/_tools/vsl/tests/test_take_over_18939.py`.

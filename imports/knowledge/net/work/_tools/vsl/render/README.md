# render/: the Ra renderer for an intro VSL (versioned here by knowledge#18647)

Until 2026-11-24 these files existed only in `/home/vsl/render/` on Ra: untracked, untested, edited in place by the `vsl` agent. Every sent intro VSL
(including job 3307's `3307-intro-v2.mp4`) came from them, not from the gated pipeline. They are copied here unchanged except `build_intro.py`
(READY check + `package_ready` in its json). Deploy: copy `render/*` to `/home/vsl/render/` on Ra (the two diverge otherwise).

`build_intro.py PKG TAG [--intro clip.mkv] [--voice-dir DIR] [--allow-unready]` -> Kokoro or clone-voice rows, `render4.py` (Playwright capture with the human cursor),
`vsl_frame.py` (browser frame, three tabs, orb), mux. `post_capture.py` screenshots the real Upwork post.

## How job 3307 was made (read live on Ra 2026-11-24, the evidence for knowledge#18647)
| step | what happened | system or hand |
|---|---|---|
| 05:40Z | feed row -> job record `up-technical-lead-cto-for-ai-styling-3307` | system |
| 06:25Z | app (shadcn-admin copy) + diagram built; `pick.json` says shadcn-admin while the job record's `library` says atomic-crm | system |
| 06:28Z / 07:05Z | `scripts_and_gates` refused twice: `post.md missing`, then `E4 grade` on four rows -> job `blocked`, no `ready` stamp, ever | system (correct) |
| 11:56Z (inferred: no job-record event; the files carry that mtime) | `intro-script.md` / `entire-script.md` / `action-script.json` written anyway (no `--upwork`, so `upwork_rules.enforce` never ran). They carry "get get", contractions the contract forbids in print but E6 requires live, a 19 s Tyler intro (contract 8-22), and the canned close | hand |
| 18:35Z | `/home/vsl/render/build_intro.py` rendered `3307-intro.mp4` (48.3 s, "clone voice") from those scripts; no QA, no gate, no job-state read | hand, untracked renderer |
| 20:28-20:33Z | Upwork agent submitted it (`arm: manual`, `attended: true`), ledger `vsl_sent` | hand |

So: the one-shot system is implemented and its gates work (they refused 3307); the intro/full switch exists (`autosend.py`, `oneshot_auto pick`). What was missing was
**one path from READY package to rendered file to send**: the renderer lived outside git, did not read the job state, and `proposals.py sent` did not either.
The "good" VSLs were produced by the same hand path, which is why they were not repeatable.

## What changed (knowledge#18647)
- `script_rules.fill_intro`: an outcome slot that begins with "get" no longer prints "get get" (test `tests/test_oneshot_3307_18647.py`).
- `render/build_intro.py` refuses a package whose job is not `ready` (exit 4); `--allow-unready` renders and records `package_ready: false` + the reason in the json.
- `proposals.py sent --vsl` prints a WARNING (advisory, never a refusal: no gates) when the job's package is not `ready`.

## knowledge#18734: the VERIFY gate (read this before sending anything)
`intro_verify.py` measures the FINAL mp4 (frames + audio) against contract `verify:`; `oneshot_auto tick` runs it on every due intro, and `intro_sender` sends ONLY a file whose
`<package>/verify.json` passed for that exact sha256 (a failure mails chief the failing checks). Replay fixture: `tests/fixtures/3307-intro-v2.lowrate.mp4` fails it on tabs, post-first,
orb, cropped diagram and loudness. The builder must write `<package>/intro-meta.json` with `handoff_s` (seconds where Tyler's intro ends); without it loudness-match fails closed.
This directory is the tracked renderer; `/home/vsl/render` on Ra is to be deleted once `render/*` is deployed there (the vsl agent owns Ra; not reachable from the dust account).

## capture_browser.py (knowledge#18869 item 7) — Eagle's seat capture, now in git
Moved from Ra's `/var/tmp/eagle-send/capture/` (copy it back there to run; it needs `/opt/vsl-follow/desk_human`, so it only runs on Ra as `eagle`).
Real https tabs only: the public `https://www.upwork.com/jobs/~<id>` page (logged-out; the Upwork account session is never cloned onto the capture seat, upwork-seat-guard rule),
and `https://oneshot.utopiamodels.ai/<tag>/{app,diagram}/` — a Cloudflare Worker (`../demo-site/`, `bash publish.sh` syncs Ra's `/var/tmp/eagle-send/demo/`). Chrome is launched at
`--force-device-scale-factor=1`, profile Preferences turn sign-in off (no "Sign in to Chrome?" chip), and the ffmpeg crop is skipped when the output is already 1920x1080.
`--review` runs `gemini_cursor_review.py` on the result. A seat flock (`.seat.lock`) serialises captures.
**Not proven end to end (2026-11-25):** two test runs recorded another session's windows (Russell/govbids Chrome in profile-tyler was live on the same seat), so no clean 3307 frame exists yet.
Run it only when `ps -u eagle -o args | grep user-data-dir` shows no other Chrome, and check frames 0:03 / 0:20 before a re-render. Ra's router resolver negative-caches a brand-new hostname for 30 min (SOA minimum 1800).

## knowledge#18908: capture lives on vsl's OWN seat (desk-vsl on Ra), no longer Eagle's
Tyler 2026-11-24 (cards): vsl owns the video end to end; Eagle keeps the laptop and Vizier only. Built and measured 2026-11-24:
- Seat: `desk-create vsl vsl ra --human --cdp-port 9241 --no-session` (unix user `desk-vsl` uid 1019, own headless sway `HEADLESS-1` 2560x1368, deskd
  socket `/run/deskd-desk-vsl/deskd.sock`; `/etc/desks/vsl.env` has `DESKD_OWNER=desk-vsl` because deskd refuses input from anyone but its owner).
- Run: `capture_as_vsl.sh <capture_browser args>` as user `vsl` (sudo rule `/etc/sudoers.d/vsl-capture`, NOPASSWD for that one script as desk-vsl). Files live in
  `/home/desk-vsl/capture/` (copy `render/capture_browser.py capture_as_vsl.sh human_motion.py gemini_cursor_review.py` there; chown desk-vsl:vsl). Seat env defaults to the vsl desk
  (`CAPTURE_SEAT_UID=1019`, `CAPTURE_OUT=HEADLESS-1`, `CAPTURE_DIR`); Eagle's old seat is `CAPTURE_SEAT_UID=1005 CAPTURE_OUT=HEADLESS-2 CAPTURE_OUT_X=1280`.
- Three bugs found by looking at the frames, fixed here: (1) `swaymsg exec "google-chrome ... --disable-features=A,B ..."` — sway splits its command on `,`, so Chrome started with
  NO urls (a bare New Tab was recorded); Chrome is now started with Popen. (2) the pid match picked a helper process so the window was never placed; the seat is dedicated, so
  `[app_id="google-chrome"]`, with the rect read back until it is at 0,0 1920x1080 (`--window-size` flag too). (3) wf-recorder writes frames only on damage, so a still page gave a
  4.6 s file for 15 s of shot; `tpad=stop_mode=clone` fills the tail and `-g` records exactly the 1920x1080 region.
- Measured: `capture_as_vsl.sh --tag t18908 ... --intro 4` -> 1920x1080, 15.000 s (asked 15.0), three real tabs (upwork.com page, MVP, Architecture), real cursor, nothing cropped.
- NOT done here (named, not hidden): the end-to-end acceptance (a fresh post to a SENT proposal with no hand-off) was not run; it needs the vsl session to call
  `capture_as_vsl.sh` from its pipeline and Upwork's send click, and runs after Russell's offer (#18845) is out.

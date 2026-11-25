#!/bin/bash
# install.sh — put the Eagle Eye feed on Ra from git (knowledge#19365). Run from any box that reaches Ra:
#   bash packages/core/install.sh
# Ra's eagle user runs the feed from a CLONE of utopia-models/eagle-eye (WorkingDirectory = ~/dev/eagle-eye/packages/core),
# reads per-deployment config from the private overlay clone at /srv/eagle-eye/config (utopia-models/eagle-eye-utopia),
# and writes runtime data to /srv/eagle-eye/data. Re-running updates both clones to origin/main and restarts the unit.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
ssh -o BatchMode=yes pharaoh@ra '
  set -e
  sudo install -d -o eagle -g eagle -m 0755 /srv/eagle-eye /srv/eagle-eye/data /srv/eagle-eye/media
  as_eagle() { sudo -u eagle -H env XDG_RUNTIME_DIR=/run/user/$(id -u eagle) "$@"; }
  clone() { # clone <url> <dir>: clone once, then fast-forward to origin/main
    if [ -d "$2/.git" ]; then as_eagle git -C "$2" fetch -q origin && as_eagle git -C "$2" merge -q --ff-only origin/main
    else as_eagle git clone -q "$1" "$2"; fi; }
  clone https://github.com/utopia-models/eagle-eye ~eagle/dev/eagle-eye
  clone https://github.com/utopia-models/eagle-eye-utopia /srv/eagle-eye/config
  as_eagle install -D -m 0644 ~eagle/dev/eagle-eye/packages/core/eagle-eye-feed.service ~eagle/.config/systemd/user/eagle-eye-feed.service
  as_eagle systemctl --user daemon-reload
  as_eagle systemctl --user enable eagle-eye-feed.service
  as_eagle systemctl --user restart eagle-eye-feed.service
  as_eagle systemctl --user --no-pager status eagle-eye-feed.service | head -5'

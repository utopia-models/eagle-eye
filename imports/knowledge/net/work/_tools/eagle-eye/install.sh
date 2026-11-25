#!/bin/bash
# install.sh — deploy the Eagle Eye feed to Ra as horus (knowledge#13151). Run from novaserver:
#   bash net/work/_tools/eagle-eye/install.sh
# Copies feed.py, refresh-data.py, push-kv.sh into ~horus/dev/eagle-eye and (re)starts eagle-eye-feed.service.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
tar -C "$here" -cf - feed.py apps_feed.py network_here.py apps-push.py refresh-data.py push-kv.sh eagle-eye-feed.service | ssh -o BatchMode=yes pharaoh@ra '
  set -e; d=$(mktemp -d); tar -xf - -C "$d"
  sudo install -o horus -g horus -m 0644 "$d/feed.py" "$d/apps_feed.py" "$d/network_here.py" ~horus/dev/eagle-eye/
  sudo install -o horus -g horus -m 0755 "$d/refresh-data.py" "$d/apps-push.py" "$d/push-kv.sh" ~horus/dev/eagle-eye/
  sudo install -o horus -g horus -m 0644 -D "$d/eagle-eye-feed.service" ~horus/.config/systemd/user/eagle-eye-feed.service
  rm -rf "$d"
  u=$(id -u eagle)
  sudo -u eagle XDG_RUNTIME_DIR=/run/user/$u systemctl --user daemon-reload
  sudo -u eagle XDG_RUNTIME_DIR=/run/user/$u systemctl --user enable eagle-eye-feed.service
  sudo -u eagle XDG_RUNTIME_DIR=/run/user/$u systemctl --user restart eagle-eye-feed.service
  sudo -u eagle XDG_RUNTIME_DIR=/run/user/$u systemctl --user --no-pager status eagle-eye-feed.service | head -5'

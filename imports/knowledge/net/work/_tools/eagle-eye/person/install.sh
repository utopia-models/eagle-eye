#!/usr/bin/env bash
# install.sh: put the per-person Eagle Eye feed on this box as a --user timer (knowledge#13617).
# Copies the scripts to ~/.local/share/eagle-eye-person/ (its own copy: never run from the shared ~/dev clone, which
# sits on other runs' branches) and (re)starts eagle-eye-person-feed.timer. Re-run after a merge changes either file.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
dst="$HOME/.local/share/eagle-eye-person"
mkdir -p "$dst/client-desk" "$HOME/.config/systemd/user"
install -m 0755 "$here/../person_feed.py" "$here/../in_person_find.py" "$dst/"
# the In Person finder reads Luma with a real browser: its own venv, the shared playwright browsers (knowledge#14303)
[ -x "$dst/venv/bin/python" ] || { python3 -m venv "$dst/venv" && "$dst/venv/bin/pip" install -q playwright; }
install -m 0644 "$here/../../client-desk/client_desk.py" "$here/../../client-desk/clients.json" "$dst/client-desk/"
install -m 0644 "$here/eagle-eye-person-feed.service" "$here/eagle-eye-person-feed.timer" "$here"/eagle-eye-in-person.{service,timer} "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user enable --now eagle-eye-person-feed.timer eagle-eye-in-person.timer
systemctl --user start eagle-eye-person-feed.service
systemctl --user --no-pager status eagle-eye-person-feed.service | sed -n 1,8p

#!/usr/bin/env bash
# capture_as_vsl.sh ARGS... : run capture_browser.py on vsl's OWN capture seat (desk-vsl on Ra, knowledge#18908).
# Called by the vsl user; it re-runs itself as desk-vsl through sudo (rule in /etc/sudoers.d/vsl-capture) because the sway
# socket and deskd belong to desk-vsl. No fleetmail, no Eagle: vsl -> this -> MP4 in /srv/vsl.
set -euo pipefail
D=/home/desk-vsl/capture
if [ "$(id -un)" != desk-vsl ]; then exec sudo -n -u desk-vsl "$D/capture_as_vsl.sh" "$@"; fi
cd "$D"; exec /opt/vsl-follow/venv/bin/python "$D/capture_browser.py" "$@"

#!/usr/bin/env bash
# Ship the Eagle Eye hunt page (eagle.utopiamodels.ai) from this git checkout to Ra, where it is served (knowledge#18540).
# Run from any clone, on Ra or on novaserver (masters reach Ra as architect@100.127.249.81, passwordless sudo):
#   bash net/work/_tools/eagle-eye/hunt-page/deploy.sh [ui|spike|v2|all] [--dry-run]       default: all
# Permissions: claim() chowns any target file this tree overwrites to architect first (one sudo chown), so rsync itself runs unprivileged.
# ui    -> RA:~architect/dev/utopia-models/_shots/stream-vsl/eagle-eye-spike/public/   (static; live at once, no restart)
# spike -> RA:.../eagle-eye-spike/ (server.py, live_refresh.py, tools)                  restarts eagle-ui.service
# v2    -> RA:~architect/dev/utopia-models/eagle-eye-v2/ (src = /api/feed, send, deploy)    restarts eagle-server.service
# Only source is synced: hunts/, v/, oneshot/, people/, offer.json, pipelines.json on Ra are generated data and never touched (no --delete).
set -euo pipefail
what=${1:-all}; dry=; [ "${2:-}" = --dry-run ] && dry=--dry-run
here=$(cd "$(dirname "$0")" && pwd)
RA=architect@100.127.249.81
ROOT=/home/architect/dev/utopia-models
SPIKE=$ROOT/_shots/stream-vsl/eagle-eye-spike
if [ "$(hostname -s)" = "ra" ] || [ -d "$SPIKE/public" ] && [ "$(id -un)" = architect ]; then
  rs() { rsync -rlt --inplace $dry "$@"; }; tgt() { echo "$1"; }
  sh_ra() { bash -c "$1"; }
else
  rs() { rsync -rlt --inplace -e "ssh -o BatchMode=yes" $dry "$@"; }; tgt() { echo "$RA:$1"; }
  sh_ra() { ssh -o BatchMode=yes $RA "$1"; }
fi
# A deploy writes as architect; a file a service or a root run once created there (index.html left eagle-owned, a root sync) refuses the write.
# claim() chowns to architect exactly the target files this source tree would overwrite, so the sync never needs "sudo rsync" and never touches generated data.
claim() { # claim <source dir> <target dir on Ra>
  local rel; rel=$(cd "$1" && find . -type f ! -name '*.bak*' ! -path '*/node_modules/*' ! -path '*/__pycache__/*' ! -path '*/.git/*' ! -path '*/state/*' | sed 's|^\./||' | tr '\n' ' ')
  if [ -z "$dry" ]; then sh_ra "cd '$2' 2>/dev/null && for f in $rel; do [ -e \"\$f\" ] && [ \"\$(stat -c %U \"\$f\")\" != architect ] && sudo -n chown architect:architect \"\$f\"; done; true"; fi
}
X=(--exclude='*.bak*' --exclude=__pycache__ --exclude=node_modules --exclude=state --exclude=.git)
do_ui()    { claim "$here/ui" $SPIKE/public; rs "${X[@]}" "$here/ui/" "$(tgt $SPIKE/public/)"; }
do_spike() { claim "$here/spike" $SPIKE; rs "${X[@]}" --exclude=README.md "$here/spike/" "$(tgt $SPIKE/)";
             if [ -z "$dry" ]; then sh_ra "XDG_RUNTIME_DIR=/run/user/\$(id -u) systemctl --user restart eagle-ui.service"; fi; }
do_v2()    { claim "$here/v2" $ROOT/eagle-eye-v2; rs "${X[@]}" "$here/v2/" "$(tgt $ROOT/eagle-eye-v2/)";
             if [ -z "$dry" ]; then sh_ra "XDG_RUNTIME_DIR=/run/user/\$(id -u) systemctl --user restart eagle-server.service"; fi; }
case $what in ui) do_ui;; spike) do_spike;; v2) do_v2;; all) do_ui; do_spike; do_v2;; *) echo "usage: $0 [ui|spike|v2|all] [--dry-run]"; exit 2;; esac
echo "deployed: $what"

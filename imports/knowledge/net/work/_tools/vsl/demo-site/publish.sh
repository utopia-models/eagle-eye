#!/usr/bin/env bash
# publish.sh: sync Ra's /var/tmp/eagle-send/demo/<tag>/{app,diagram} to https://oneshot.utopiamodels.ai/<tag>/{app,diagram}/ (knowledge#18869 item 7).
# Needs: ssh root@ra, node/npx, cred. Rebuilds dist from the whole Ra demo dir, so every earlier tag stays up.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; dist="$here/dist"
rm -rf "$dist"; mkdir -p "$dist"
rsync -a --exclude '.*' root@ra:/var/tmp/eagle-send/demo/ "$dist/"
printf '/*\n  X-Robots-Tag: noindex, nofollow\n' > "$dist/_headers"
cd "$here"
CLOUDFLARE_API_TOKEN="$(cred get fleet-infra CF_API_TOKEN_UTOPIA)" npx --yes wrangler@4 deploy
for d in "$dist"/*/; do t="$(basename "$d")"; for p in app diagram; do
  [ -d "$d$p" ] && printf '%s %s\n' "$(curl -s -o /dev/null -w '%{http_code}' "https://oneshot.utopiamodels.ai/$t/$p/")" "https://oneshot.utopiamodels.ai/$t/$p/"; done; done

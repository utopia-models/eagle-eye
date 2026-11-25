#!/bin/bash
# push-kv.sh (Ra, ~horus/dev/eagle-eye) — the Eagle Eye feed loop (knowledge#13151): every 30 s, measure
# (refresh-data.py -> data.json + cold-apps.json) and PUT both into the eagle-eye Worker's KV
# (namespace eagle-eye-data, keys `data`, `cold-apps` and `lanes` (the lane pages, knowledge#13617)) behind https://eagle.utopiamodels.ai,
# then apps-push.py puts KV `apps` + `apps/<person>` (the applications section).
# Run by the user unit eagle-eye-feed.service. Source of truth: utopia-models/eagle-eye packages/core/.
# A failed measurement pushes nothing (the KV keeps the last good copy); every cycle logs one line to the journal.
set -u
cd "$(dirname "$(readlink -f "$0")")" || exit 1
# Runtime output (data.json, lanes.json ...) lives in /srv/eagle-eye/data, never in the git checkout (knowledge#19365).
D=${EE_DATA:-/srv/eagle-eye/data}; mkdir -p "$D" || exit 1; export EE_DATA="$D"
NS=d97b9be8758d4ede805c0bf9c6d2e68c
INTERVAL=${EAGLE_INTERVAL:-30}
T=$(cred get fleet-infra CF_API_TOKEN_UTOPIA); AID=$(cred get fleet-infra CF_ACCOUNT_ID_UTOPIA)
[ -n "$T" ] && [ -n "$AID" ] || { echo "push-kv: CF token or account id missing from cred" >&2; exit 1; }
put() {  # put <kv key> <file>  -> prints the HTTP code
  curl -s -m 20 -o /dev/null -w '%{http_code}' -X PUT -H "Authorization: Bearer $T" --data-binary @"$2" \
    "https://api.cloudflare.com/client/v4/accounts/$AID/storage/kv/namespaces/$NS/values/$1"
}
# The Studio page (/studio, knowledge#14747) reads `.studio` of KV `lanes`: `vsl studio feed` (Kitsu on this box) every
# STUDIO_EVERY-th cycle (2 min), joined into the lanes copy that is PUT. A failed read keeps the last good studio.json.
STUDIO_EVERY=${EAGLE_STUDIO_EVERY:-4}; n=0
studio() {  # sets LP (the lanes file to PUT); never in a $( ) subshell, or n never counts
  if [ $((n % STUDIO_EVERY)) = 0 ] && timeout 90 vsl studio feed > "$D/studio.json.new" 2>/dev/null && jq -e .clients "$D/studio.json.new" >/dev/null 2>&1; then
    mv "$D/studio.json.new" "$D/studio.json"; else rm -f "$D/studio.json.new"; fi
  n=$((n + 1))
  if [ -s "$D/lanes.json" ] && [ -s "$D/studio.json" ] && jq --slurpfile s "$D/studio.json" '.studio = $s[0]' "$D/lanes.json" > "$D/lanes.put.json" 2>/dev/null; then
    LP="$D/lanes.put.json"; else LP="$D/lanes.json"; fi
}
while true; do
  if m=$(python3 ./refresh-data.py "$D/data.json" "$D/cold-apps.json" "$D/lanes.json" 2>&1); then
    studio
    echo "$(date -u +%FT%TZ) measured $m · kv data=$(put data "$D/data.json") cold-apps=$(put cold-apps "$D/cold-apps.json") pipelines=$( [ -s "$D/pipelines.json" ] && put pipelines "$D/pipelines.json" || echo none) lanes=$( [ -s "$LP" ] && put lanes "$LP" || echo none)$( [ "$LP" = "$D/lanes.put.json" ] && echo ' +studio')"
    # the applications section (KV apps, apps/<person>): its own build, so a failure there never holds the home feed
    a=$(CF_TOKEN="$T" CF_ACCOUNT="$AID" timeout 120 python3 ./apps-push.py --push 2>&1 | awk '{print $2"="$NF}' | tr '\n' ' ')
    echo "$(date -u +%FT%TZ) apps ${a:-none}"
  else
    echo "$(date -u +%FT%TZ) MEASURE FAILED, nothing pushed: ${m: -300}" >&2
  fi
  sleep "$INTERVAL"
done

#!/usr/bin/env bash
# vsl-intake.sh — Tyler drops a recording in Drive; this publishes it (net/subprocesses/interactive/vsl.md §3).
#
#   bash net/work/_tools/vsl/vsl-intake.sh [project-slug]      # no slug = every project folder in the inbox
#
# The inbox is Drive manifest key raw.work-vsl.inputs: one sub-folder per project slug, one file per VSL.
# For each video there that has no published copy yet in raw.work-vsl.final/<slug>/<stem>.mp4, it:
#   1 pulls the file from Drive
#   2 runs vsl-publish.sh  (transcode → probe → captions → R2 → verify; prints the object URLs)
#   3 files the published mp4 + vtt + the URL record (<stem>.json) in raw.work-vsl.final/<slug>/
# and prints one JSON line per published VSL. Idempotent: a second run publishes nothing new.
# The page swap (the feed entry's `vsl` field) is the work-site's, #11434 — this prints what to point it at.
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(git -C "$HERE" rev-parse --show-toplevel)
ONLY=${1:-}
DTOK=${DTOK:-$(bash ~/.claude/scripts/google-workspace.sh token 2>/dev/null)}
[ ${#DTOK} -gt 20 ] || { echo "no Drive token (google-workspace.sh token)" >&2; exit 2; }
INBOX=$(bash "$REPO/_infra/scripts/drive-resolve.sh" raw.work-vsl.inputs)
FINAL=$(bash "$REPO/_infra/scripts/drive-resolve.sh" raw.work-vsl.final)
API=https://www.googleapis.com/drive/v3/files
say() { printf '[vsl-intake] %s\n' "$*" >&2; }
ls_q() { curl -fsS -G -H "Authorization: Bearer $DTOK" "$API" --data-urlencode "q=$1 and trashed=false" \
  -d supportsAllDrives=true -d includeItemsFromAllDrives=true -d pageSize=200 -d 'fields=files(id,name,mimeType,size)'; }
folder() {  # parent name -> id (created if missing)
  local id; id=$(ls_q "'$1' in parents and name='$2' and mimeType='application/vnd.google-apps.folder'" | jq -r '.files[0].id // empty')
  [ -n "$id" ] || id=$(curl -fsS -X POST -H "Authorization: Bearer $DTOK" -H 'content-type: application/json' \
    "$API?supportsAllDrives=true&fields=id" -d "$(jq -cn --arg n "$2" --arg p "$1" '{name:$n,mimeType:"application/vnd.google-apps.folder",parents:[$p]}')" | jq -r .id)
  echo "$id"
}
upload() {  # local-file parent name mime
  local loc
  loc=$(curl -fsS -D - -o /dev/null -X POST -H "Authorization: Bearer $DTOK" -H 'content-type: application/json; charset=UTF-8' \
    -H "X-Upload-Content-Type: $4" "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&supportsAllDrives=true" \
    -d "$(jq -cn --arg n "$3" --arg p "$2" '{name:$n,parents:[$p]}')" | grep -i '^location:' | cut -d' ' -f2- | tr -d '\r')
  curl -fsS -X PUT -H "Content-Type: $4" --upload-file "$1" "$loc" | jq -r .id
}

FOLDERS=$(ls_q "'$INBOX' in parents and mimeType='application/vnd.google-apps.folder'" | jq -r '.files[] | "\(.id)\t\(.name)"')
[ -n "$FOLDERS" ] || { say "inbox has no project folders"; exit 0; }
n=0
while IFS=$'\t' read -r FID SLUG; do
  [ -z "$ONLY" ] || [ "$SLUG" = "$ONLY" ] || continue
  DEST=""
  while IFS=$'\t' read -r VID NAME; do
    [ -n "$VID" ] || continue
    STEM=${NAME%.*}
    DEST=${DEST:-$(folder "$FINAL" "$SLUG")}
    if [ -n "$(ls_q "'$DEST' in parents and name='$STEM.mp4'" | jq -r '.files[0].id // empty')" ]; then
      say "$SLUG/$NAME: already published — skip"; continue
    fi
    W=$(mktemp -d "${TMPDIR:-/tmp}/vsl-intake.XXXXXX"); trap 'rm -rf "$W"' EXIT
    say "$SLUG/$NAME: pull from Drive"
    curl -fsS -H "Authorization: Bearer $DTOK" "$API/$VID?alt=media&supportsAllDrives=true" -o "$W/in"
    mkdir "$W/out"
    REC=$(VSL_OUTDIR="$W/out" bash "$HERE/vsl-publish.sh" "$W/in" "$SLUG")
    echo "$REC" > "$W/out/rec.json"
    upload "$W/out/video.mp4" "$DEST" "$STEM.mp4" video/mp4 >/dev/null
    upload "$W/out/captions.vtt" "$DEST" "$STEM.vtt" text/vtt >/dev/null
    upload "$W/out/rec.json" "$DEST" "$STEM.json" application/json >/dev/null
    say "$SLUG/$NAME: filed in 02_final/$SLUG/"
    echo "$REC"; n=$((n + 1))
    rm -rf "$W"; trap - EXIT
  done < <(ls_q "'$FID' in parents and mimeType contains 'video/'" | jq -r '.files[] | "\(.id)\t\(.name)"')
done <<<"$FOLDERS"
say "published $n"

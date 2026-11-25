#!/usr/bin/env bash
# Push the SENT rows of the Upwork ledger (vsl_sent / video_sent only: no proposals, no client replies) from novaserver
# to Ra, where vsl-archive.service reads them as EAGLE_UPWORK_LEDGER (knowledge#16475). Runs on novaserver as a user
# timer; the ledger dir is upwork-only, so the read goes through sudo. Fails loud: an unreadable ledger leaves the old copy
# in place and vsl_archive prints "Sent: unknown", never a fake zero.
set -euo pipefail
SRC=${UPWORK_LEDGER:-/home/upwork/.claude/state/net/upwork/ledger.jsonl}
DEST=${RA_LEDGER_DEST:-eagle@100.127.249.81}
DIR='.local/share/vsl-archive'
tmp=$(mktemp); trap 'rm -f "$tmp"' EXIT
sudo -n grep -E '"event": ?"(vsl_sent|video_sent)"' "$SRC" > "$tmp" || [ $? -eq 1 ]   # grep rc 1 = no match, still a valid empty copy
ssh -o BatchMode=yes -o ConnectTimeout=10 "$DEST" "mkdir -p $DIR && cat > $DIR/upwork-ledger.jsonl.new && mv $DIR/upwork-ledger.jsonl.new $DIR/upwork-ledger.jsonl" < "$tmp"
echo "synced $(wc -l < "$tmp") sent rows -> $DEST:$DIR/upwork-ledger.jsonl"

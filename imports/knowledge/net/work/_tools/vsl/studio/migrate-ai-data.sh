#!/usr/bin/env bash
# Record #1 in Kitsu: the ai-data VSL of 2026-11-16/17 (knowledge#14747; horus's brief § 6). Run from novaserver in a
# knowledge checkout; it acts on Ra as horus through the `vsl` studio verbs. Refuses to run twice (the takes would
# double); `--force` skips that check.
#   bash net/work/_tools/vsl/studio/migrate-ai-data.sh [--force]
# STUDIO_PY overrides the verb runner (default: `vsl`, i.e. fleet-plugins skills/vsl/vsl.py on Ra).
set -euo pipefail
RA=${STUDIO_HOST:-root@ra}
VSL=${STUDIO_PY:-vsl}
KB=$(git rev-parse --show-toplevel)
DAY=/srv/vsl/2026-11-16
STAGE=/var/tmp/studio-migrate-ai-data   # Ra's /tmp is tmpfs (RAM); stage on disk

run() { ssh -o BatchMode=yes "$RA" "sudo -u eagle -H $VSL $(printf '%q ' "$@")"; }

if [ "${1:-}" != --force ] && ssh -o BatchMode=yes "$RA" "sudo -u eagle -H $VSL studio feed ai-data" | jq -e '.clients[0].videos[0].takes | length > 0' >/dev/null 2>&1; then
  echo "migrate: ai-data already has takes in Kitsu; nothing done (--force to add them again)"; exit 0
fi

# Script versions: every committed version of vsl-90s-script.md (git is the version history), then v6 in Fountain.
ssh -o BatchMode=yes "$RA" "rm -rf $STAGE && install -d -o horus -g horus $STAGE"
i=0
while read -r sha when subject; do
  i=$((i + 1))
  git -C "$KB" show "$sha:net/work/vsl/ai-data/vsl-90s-script.md" | ssh -o BatchMode=yes "$RA" "sudo -u eagle tee $STAGE/vsl-90s-script.$i.md >/dev/null"
  echo "$sha|$(date -u -d "$when" +%Y-%m-%dT%H:%M:%S)|$subject" | ssh -o BatchMode=yes "$RA" "sudo -u eagle tee $STAGE/v$i.meta >/dev/null"
done < <(git -C "$KB" log --reverse --format='%h %aI %s' -- net/work/vsl/ai-data/vsl-90s-script.md)
ssh -o BatchMode=yes "$RA" "sudo -u eagle tee $STAGE/vsl-90s-script.fountain >/dev/null" < "$KB/net/work/vsl/ai-data/vsl-90s-script.fountain"

run new ai-data --video vsl-90s --title "Upwork AI Data Engineer post (Azure Databricks, Python & MCP), job 022122386398617111601"
for n in $(seq 1 "$i"); do
  meta=$(ssh -o BatchMode=yes "$RA" "cat $STAGE/v$n.meta"); sha=${meta%%|*}; rest=${meta#*|}; when=${rest%%|*}; subject=${rest#*|}
  run script ai-data "$STAGE/vsl-90s-script.$n.md" --video vsl-90s --by horus --when "$when" --note "knowledge $sha: $subject"
done
run script ai-data "$STAGE/vsl-90s-script.fountain" --video vsl-90s --by horus --when 2026-11-17T07:10:00 \
  --note "the same v6 in Fountain, cues from cues.json as [[horus: ...]] notes (knowledge#14747)"

# Takes. Times are UTC; Ra's clock is America/Denver (-07:00).
run note ai-data --video vsl-90s --by horus --when 2026-11-17T01:43:40 \
  "takes 1 and 2 of the first session (driver up 2026-11-17 01:41:07Z and 01:43:19Z) have no video file: lost. The 23:22 MT recording was first saved as eddie-take3.mp4, then renamed by hand to ai-data-take1.mp4 over that take1; take 2 was stopped on 'Horus, you're not recording'. Kitsu revision 1 below is the 23:22 recording, revision 2 is left empty, revision 3 is take 3."
run take "$DAY/ai-data-take1.mp4" --video vsl-90s --when 2026-11-17T06:23:43
run take "$DAY/ai-data-take3.mp4" --video vsl-90s --when 2026-11-17T06:37:21
run take "$DAY/ai-data-take4.mp4" --video vsl-90s --when 2026-11-17T06:43:05 \
  --by horus --note "take 4 = take 3 cut at 76.4 s (after 'I appreciate it', before the bio and the second CTA): the send candidate"

# The notes: ai-data-take1.notes.md, line by line, verbatim, at their own times; Tyler's own words as his.
run note ai-data-take1 --video vsl-90s --by tyler --when 2026-11-17T06:33:00 \
  "the terminal in the bottom half 'kind of looks a little cut off'"
run note ai-data-take1 --video vsl-90s --by horus --when 2026-11-17T06:33:30 \
  "Tyler on ai-data-take1: the terminal in the bottom half 'kind of looks a little cut off'. Cause: demo call JSON (~40 lines) taller than the 450 px pane, top scrolls away; camera box over the pane's right side. Fix for take 2: compact output (summary lines, not raw JSON), foot font ~16pt, pane 560 px, diagram 550 px."
run note ai-data-take1 --video vsl-90s --by horus --when 2026-11-17T06:34:00 \
  "Tyler asks: terminal whole left, diagram whole right? Horus: diagram is landscape (~1900x550), a half shrinks it; proposal = two full-screen shots, diagram then terminal, switched on his words."
run note ai-data-take1 --video vsl-90s --by horus --when 2026-11-17T06:36:00 \
  "take 2 plan agreed by Tyler ('do it again', 'be assertive'): two full-screen shots, diagram (con 186) then terminal (foot vsl-term 14pt, con 190) on 'a partner asks'; cues2 watcher armed; mic 35%."
run note ai-data-take3 --video vsl-90s --by horus --when 2026-11-17T06:37:30 \
  "take3 recorded (11:34:25-11:36:28 PM, ~123 s): diagram walked, cut to terminal on 'a partner asks' (01:35:13), call 2 at 01:35:22; tail added bio + second CTA ('book a call via the Upwork chat'); over 100 s -> trim after 'send the next build'. Tyler 06:37Z: Vizier red record button must not exist as a feature at all (third time)."
run note ai-data-take3 --video vsl-90s --by tyler --when 2026-11-17T06:37:45 \
  "Vizier red record button must not exist as a feature at all (third time)."
run note ai-data-take4 --video vsl-90s --by horus --when 2026-11-17T06:43:30 \
  "ai-data-take4.mp4 = take3 cut at 76.4 s (after 'I appreciate it', before the bio + second CTA); the send candidate."

# The deliverable, on Review.
run studio deliver ai-data --video vsl-90s --when 2026-11-17T06:45:00 \
  "ai-data-take4-upwork.mp4 (12.4 MB, vsl export) is in the Upwork outbox on Nova: /srv/upwork-vsl/outbox/2026-11-17/~022122386398617111601--ai-data.mp4 (06:45Z). ai-data-take1-upwork.mp4 (15.0 MB) kept. Sent to the client: not recorded yet."
ssh -o BatchMode=yes "$RA" "rm -rf $STAGE"
ssh -o BatchMode=yes "$RA" "sudo -u eagle -H $VSL studio status ai-data"

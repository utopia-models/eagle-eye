#!/usr/bin/env bash
# onboard-texts.sh: text each person their own Eagle Eye link from the RAW line, once, then prove it from the
# fleetmail actions ledger and report on the issue (knowledge#14129).
#
#   onboard-texts.sh ISSUE PERSON:AGENT [PERSON:AGENT ...]     e.g. 14129 claire:claire-scout osman:milli-scout
#
# Each person's number is read at send time from their agent's box config (~AGENT/.claude/state/AGENT/config.json
# `.sms`, never git); the body is <dir>/text-<person>.txt (DIR defaults to this script's directory). The body passes
# voice.py check in that agent's voice before it goes. `phone text` sends exactly once (the gateway answers a repeat
# with the first send's state). When every person's send is in `fleetmail today`, the script ticks the plan box
# through a merged PR that closes ISSUE; any failure exits non-zero, so the unit's OnFailure files it on the board.
# Run it as a one-shot timer outside quiet hours (22:00-07:00 America/Denver):
#   systemd-run --user -u eagle-eye-onboard --on-calendar='2026-11-16 16:30:00 UTC' -E KB=<worktree> -E DIR=<spec dir> \
#     -- bash <worktree>/net/work/_tools/eagle-eye/person/onboard-texts.sh 14129 claire:claire-scout osman:milli-scout
set -uo pipefail
issue="$1"; shift
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
dir="${DIR:-$here}"
KB="${KB:?KB=<a knowledge checkout holding wi/work/_tools/voice/voice.py>}"
repo=utopia-models/knowledge
topic=eagle-eye-onboard
report="" fail=0

for pa in "$@"; do
  person="${pa%%:*}" agent="${pa##*:}"
  Name="${person^}"
  num=$(sudo -n jq -r .sms "/home/$agent/.claude/state/$agent/config.json" 2>/dev/null)
  body="$dir/text-$person.txt"
  if [[ ! "$num" =~ ^\+[0-9]{10,15}$ || ! -s "$body" ]]; then
    report+="- ⛔ $Name: no number in $agent's config or no body $body"$'\n'; fail=1; continue
  fi
  aud=client; [[ "$person" == claire ]] && aud=family
  if ! chk=$(python3 "$KB/wi/work/_tools/voice/voice.py" check --agent "$agent" --channel sms --to "$num" \
               --name "$Name" --audience "$aud" "$body" 2>&1); then
    report+="- ⛔ $Name: voice check refused the text: $(tail -3 <<<"$chk" | tr '\n' ' ')"$'\n'; fail=1; continue
  fi
  out=$(phone text "$num" - --topic "$topic" --contact "$Name" --until delivered --wait 30 < "$body" 2>&1); rc=$?
  rcpt=$(grep -o 'RECEIPT.*' <<<"$out" | head -1)
  report+="- $Name ($agent's thread, ****${num: -4}): \`phone text\` rc=$rc \`${rcpt:-no receipt}\`"$'\n'
  [[ $rc -eq 0 || $rc -eq 3 ]] || fail=1   # 3 = queued, delivery not confirmed yet: the ledger check decides
done

sleep 20
ledger=$(fleetmail today --json 2>/dev/null)
for pa in "$@"; do
  person="${pa%%:*}" agent="${pa##*:}"
  num=$(sudo -n jq -r .sms "/home/$agent/.claude/state/$agent/config.json" 2>/dev/null)
  row=$(jq -c --arg n "$num" --arg t "$topic" '[.[] | select((.topic|contains($t)) and (.subjects|index($n)))][0]
        | if . then {actor, channel, topic, n, last_ts} else empty end' <<<"$ledger")
  if [[ -n "$row" ]]; then report+="- ledger ✔ ${person^}: \`$row\`"$'\n'; else report+="- ledger ⛔ ${person^}: no $topic row"$'\n'; fail=1; fi
done

msg="Eagle Eye onboarding texts (\`onboard-texts.sh\`, $(date -u +%FT%TZ)):"$'\n\n'"$report"$'\n'"Ledger: \`fleetmail today --json\`, rows with topic containing \`$topic\`."
gh api "repos/$repo/issues/$issue/comments" -f body="$msg" >/dev/null || fail=1
[[ $fail -eq 0 ]] || { echo "$msg"; exit 1; }

# Both sends are in the ledger: tick the plan box through a PR that closes the issue (REST only: GraphQL runs out).
plan=net/work/specs/${issue}-eagle-eye-oss-onboard/plan.md
cur=$(gh api "repos/$repo/contents/$plan?ref=main") || exit 1
sha=$(jq -r .sha <<<"$cur"); text=$(jq -r .content <<<"$cur" | base64 -d)
new=$(sed 's/^- \[ \] Texts sent and in the fleetmail ledger/- [x] Texts sent and in the fleetmail ledger (see the onboarding comment on the issue)/' <<<"$text")
[[ "$new" != "$text" ]] || { echo "plan box already ticked or missing"; exit 1; }
br="eagle-eye-onboard-$issue-done"
base=$(gh api "repos/$repo/git/ref/heads/main" --jq .object.sha) || exit 1
gh api "repos/$repo/git/refs" -f ref="refs/heads/$br" -f sha="$base" >/dev/null || exit 1
gh api -X PUT "repos/$repo/contents/$plan" -f message="eagle-eye onboarding: texts delivered and in the ledger (knowledge#$issue)" \
  -f content="$(base64 -w0 <<<"$new")" -f sha="$sha" -f branch="$br" >/dev/null || exit 1
pr=$(gh api "repos/$repo/pulls" -f title="eagle-eye onboarding: texts delivered (knowledge#$issue)" -f head="$br" -f base=main \
  -f body="Closes #$issue"$'\n\n'"The onboarding texts are in the fleetmail ledger; evidence is the comment \`onboard-texts.sh\` posted on the issue." --jq .number) || exit 1
gh api -X PUT "repos/$repo/pulls/$pr/merge" -f merge_method=squash >/dev/null || exit 1
gh api -X DELETE "repos/$repo/git/refs/heads/$br" >/dev/null 2>&1 || true
echo "merged #$pr"
# KB_REMOVE=1: KB is a worktree made for this one run; take it away now that nothing needs it.
[[ -n "${KB_REMOVE:-}" ]] && git -C "$KB" worktree remove --force "$KB"
exit 0

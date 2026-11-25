#!/usr/bin/env bash
# lint-no-vercel.sh — Vercel is retired (knowledge#19515; Tyler 2026-11-25: "retire and completely get rid of vercel ...
# for some reason vercel keeps coming back"). Looks only at what a diff ADDS, so history and removals pass.
# Self-contained: every fleet repo carries a byte-identical copy beside .github/workflows/no-vercel.yml.
# Flags: (1) an added/renamed vercel.json or .vercel/ file, in any path
#        (2) an added deploy step: the CLI, the API host, a Vercel token, or a Vercel GitHub Action
#        (3) an added mention in doctrine an agent reads: CLAUDE.md, AGENTS.md, .claude/, skills, rules, process, components
#   lint-no-vercel.sh [<diff-range>]   default origin/main...HEAD
set -u
range=${1:-origin/main...HEAD}
self='(^|/)((test-)?lint-no-vercel\.sh|no-vercel\.yml)$'
history='^_rules/cases/'
doctrine='(^|/)(CLAUDE|AGENTS|SKILL)\.md$|(^|/)\.claude/|^(_rules|_process|skills|rules)/|(^|/)(components|subprocesses|doctrine)/.*\.md$'
# Files that can deploy something. Prose and lockfiles are not deploy steps.
runnable='(^\.github/(workflows|actions)/|\.(sh|bash|py|mjs|cjs|js|ts|tf|service|timer|toml)$|(^|/)(package\.json|Makefile|Dockerfile)$)'
deploy='(?i)(\bvercel\s+(deploy|build|pull|link|promote|alias|env)\b|\bvercel\s+--(prod|token|yes)\b|\b(npx|dlx|bunx)\s+(--yes\s+|-y\s+)?vercel(@|\s|$)|npm\s+(i|install)\s+(-g|--global)\s+vercel\b|api\.vercel\.com|VERCEL_(TOKEN|ORG_ID|PROJECT_ID|DEPLOY_HOOK)|uses:\s*\S*vercel)'
bad=0
files=$(git -c core.quotePath=false diff --name-only --no-renames --diff-filter=A "$range" --) || { echo "no-vercel: cannot diff $range"; exit 2; }
while IFS= read -r f; do
  [[ $f =~ (^|/)vercel\.json$|(^|/)\.vercel(/|$) ]] && { echo "$f: new Vercel config. Vercel is retired: deploy on Cloudflare (wrangler.jsonc)."; bad=1; }
done <<<"$files"
diff=$(git -c core.quotePath=false diff -U0 "$range" --) || exit 2
f="" n=0
while IFS= read -r line; do
  case "$line" in
    'diff --git '*) f="";;
    '+++ b/'*) [ -z "$f" ] && { f=${line#+++ b/}; f=${f%$'\t'}; continue; };;
    '@@'*) n=${line#*+}; n=${n%%[ ,]*}; continue;;
  esac
  [[ $line == +* && -n $f ]] || continue
  [[ $line == '+++ '* && $n == 0 ]] && continue
  if ! [[ $f =~ $self || $f =~ $history ]] && [[ ${line,,} == *vercel* ]]; then
    if [[ $f =~ $doctrine ]]; then echo "$f:$n: doctrine mentions Vercel, which is retired (say Cloudflare): ${line:1:140}"; bad=1
    elif [[ $f =~ $runnable ]] && grep -qP -- "$deploy" <<<"${line:1}"; then echo "$f:$n: new Vercel deploy step (use wrangler): ${line:1:140}"; bad=1; fi
  fi
  n=$((n+1))
done <<<"$diff"
[ $bad = 0 ] && echo "no-vercel: clean ($range)"
exit $bad

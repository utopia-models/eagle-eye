#!/usr/bin/env bash
# Replay test (knowledge#19515): builds a throwaway repo and asserts what the lint flags and passes.
set -u
L="$(cd "$(dirname "$0")" && pwd)/lint-no-vercel.sh"
d=$(mktemp -d); trap 'rm -rf "$d"' EXIT; cd "$d" || exit 2
g() { git -c user.email=t@t -c user.name=t -c commit.gpgsign=false -c core.hooksPath=/dev/null "$@"; }
g init -q; mkdir -p _rules; printf 'Deploy on vercel.\n' > _rules/old.md; echo '{}' > vercel.json; g add -A; g commit -qm base
fail=0
try() { # try <want-exit> <path> <content>
  g checkout -qf --detach HEAD >/dev/null 2>&1; base=$(g rev-parse HEAD)
  mkdir -p "$(dirname "$2")"; printf '%s\n' "$3" > "$2"; g add -A; g commit -qm c
  out=$(bash "$L" "$base...HEAD"); rc=$?
  [ "$rc" = "$1" ] || { echo "FAIL: want $1 got $rc for $2: $3"; echo "$out"; fail=1; }
  g reset -q --hard "$base"
}
try 1 site/vercel.json '{"cleanUrls":true}'
try 1 .vercel/project.json '{}'
try 1 .github/workflows/d.yml '      - run: npx vercel --prod'
try 1 .github/workflows/e.yml '      - uses: amondnet/vercel-action@v25'
try 1 scripts/d.sh 'curl https://api.vercel.com/v9/projects'
try 1 scripts/e.sh 'T=$VERCEL_TOKEN'
try 1 CLAUDE.md 'The site deploys on Vercel.'
try 1 wi/components/x.md 'Hosted on VERCEL'
try 1 _rules/new.md '++ vercel'
try 0 _rules/cases/2026-11/c.md 'vercel came back'
try 0 net/company/notes.md 'Vercel is hiring a Next.js engineer'
try 0 package-lock.json '"node_modules/@vercel/og": {}'
try 0 app/page.tsx 'import { track } from "x"; // vercel.live toolbar'
try 0 components/Hero.tsx '// vercel toolbar is gone'
try 0 wi/components/y.md 'Hosted on Cloudflare'
# removing the old file and the old line is never a hit
base=$(g rev-parse HEAD); g rm -q vercel.json _rules/old.md; g commit -qm rm
bash "$L" "$base...HEAD" >/dev/null || { echo "FAIL: removal flagged"; fail=1; }
[ $fail = 0 ] && echo "PASS"; exit $fail

#!/usr/bin/env bash
# Fails if the tree holds a phone number, a personal email, or a private-config name. Vendor libraries are skipped.
set -u
bad=0
files=$(git ls-files | grep -v -E '^(site/vendor/|assets/|docs/.*\.png$)')
chk(){ out=$(echo "$files" | xargs grep -n -I -E "$2" 2>/dev/null | grep -v -E "$3" || true); [ -n "$out" ] && { echo "PII/private match ($1):"; echo "$out"; bad=1; }; }
chk phone '(\+?1[-. ])?\(?[0-9]{3}\)?[-. ][0-9]{3}[-. ][0-9]{4}' 'zzzzz'
chk email '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}' '(@example\.|\.example(\b|\.)|noreply@|hello@eagleeye\.sh|privacy@eagleeye\.sh)'
chk private-names '(/p/(tyler|claire|osman)|eagle\.utopiamodels\.ai/p/|\bOsman\b|\bClaire\b)' 'site/vercel.json'
exit $bad

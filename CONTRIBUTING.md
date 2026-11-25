# Contributing to Eagle Eye

Issues and pull requests are welcome.

1. Fork, then branch from `main`.
2. Run the app (`python3 -m http.server 8000`) and, for any layout change, `npm i && npx playwright install chromium webkit firefox && npm run check`.
3. Keep it dependency-free: the app is static HTML, CSS and JS with no build step.
4. Never commit real data, credentials or personal details. The `guard` workflow runs gitleaks over full history and a PII grep (`scripts/pii-grep.sh`); both must pass.
5. Open a PR describing what changed and why. Squash merges only.

By contributing you agree your work is released under the [MIT License](LICENSE).

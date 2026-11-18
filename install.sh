#!/bin/sh
# Eagle Eye installer.
#
#   curl -fsSL eagleeye.sh/install | sh
#
# Downloads Eagle Eye into ./eagle-eye and serves it on http://localhost:8000 with python3.
# Running it again updates the app files and keeps your config.js.
#
#   EAGLE_EYE_DIR=path     where to install            (default: ./eagle-eye)
#   EAGLE_EYE_PORT=8000    port for the local server   (default: 8000)
#   EAGLE_EYE_REF=main     branch or tag to install    (default: main)
#   EAGLE_EYE_NO_SERVE=1   install only, do not start the server
#
# Licensed under the MIT License. Source: https://github.com/utopia-models/eagle-eye
set -eu

main() {
  repo="utopia-models/eagle-eye"
  ref="${EAGLE_EYE_REF:-main}"
  dir="${EAGLE_EYE_DIR:-eagle-eye}"
  port="${EAGLE_EYE_PORT:-8000}"
  url="https://codeload.github.com/${repo}/tar.gz/${ref}"

  say "Eagle Eye: one eye on every agent."

  need tar
  tmp="$(mktemp -d 2>/dev/null || mktemp -d -t eagle-eye)"
  trap 'rm -rf "$tmp"' EXIT INT TERM

  say "Downloading ${repo}@${ref}"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$url" -o "$tmp/src.tgz"
  elif command -v wget >/dev/null 2>&1; then
    wget -qO "$tmp/src.tgz" "$url"
  else
    die "needs curl or wget"
  fi
  mkdir "$tmp/src"
  tar -xzf "$tmp/src.tgz" -C "$tmp/src" --strip-components=1
  # the landing page and the layout checker are not part of the app
  rm -rf "$tmp/src/site" "$tmp/src/scripts" "$tmp/src/install.sh"

  if [ -f "$dir/eagle-eye.js" ]; then
    say "Updating ${dir} (your config.js is kept)"
    if [ -f "$dir/config.js" ]; then rm -f "$tmp/src/config.js"; fi
  elif [ -e "$dir" ] && [ -n "$(ls -A "$dir" 2>/dev/null)" ]; then
    die "${dir} exists and is not an Eagle Eye install; set EAGLE_EYE_DIR to another folder"
  else
    say "Installing into ${dir}"
  fi
  mkdir -p "$dir"
  cp -R "$tmp/src/." "$dir/"
  rm -rf "$tmp"
  trap - EXIT INT TERM

  say "Installed. The demo feed is ${dir}/demo/data.json; point 'feed' in ${dir}/config.js at your own."
  say "Feed format: https://github.com/${repo}/blob/main/docs/FEED.md"

  if [ -n "${EAGLE_EYE_NO_SERVE:-}" ]; then
    say "Start it with: cd ${dir} && python3 -m http.server ${port}"
    return 0
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    say "python3 not found. Serve ${dir} with any static server, e.g.: cd ${dir} && npx serve ."
    return 0
  fi
  # first free port from EAGLE_EYE_PORT upward
  tries=0
  while ! python3 -c "import socket,sys; s=socket.socket(); s.bind(('127.0.0.1', int(sys.argv[1])))" "$port" 2>/dev/null; do
    tries=$((tries + 1)); [ "$tries" -lt 20 ] || die "no free port from ${EAGLE_EYE_PORT:-8000} up; set EAGLE_EYE_PORT"
    port=$((port + 1))
  done
  say "Serving on http://localhost:${port}  (Ctrl-C to stop)"
  cd "$dir"
  exec python3 -m http.server "$port" --bind 127.0.0.1
}

say() { printf '\033[38;2;217;179;91m▲\033[0m %s\n' "$*"; }
die() { printf 'eagle-eye: %s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "needs $1"; }

main "$@"

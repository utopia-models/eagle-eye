#!/usr/bin/env bash
# vsl-publish.sh — one recorded VSL -> H.264 faststart + WebVTT captions -> R2, verified (vsl.md §3.2–3.5).
#
#   bash net/work/_tools/vsl/vsl-publish.sh <input-video> <project-slug> [YYYY-MM-DD] [poster.webp]
#
# Prints, last, one JSON line: {"slug","date","video","captions","poster"?} with the public object URLs.
# The feed entry (work.tyleryouk.com data file, #11434) points at those URLs; nothing else on the page changes.
#
# Each step is verified before the next (vsl.md "each verified before the next"):
#   transcode  ffmpeg libx264 high/yuv420p crf20 slow + aac 160k + faststart, ≤1080p, his cut kept as is
#   probe      ffprobe: h264 + aac; top-level `moov` atom before `mdat` (faststart really happened)
#   captions   vsl-captions.py (faster-whisper large-v3-turbo int8) in the whisper venv
#   upload     R2 bucket `work-vsl`, key <slug>/<date>/{video.mp4,captions.vtt,poster.webp}
#   verify     every URL: 200 · video `206` on a Range request · Content-Type video/mp4 / text/vtt
#
# Env (all optional):
#   VSL_WHISPER_PY   python with faster_whisper   (default: nova's comms-ingest whisper venv, run via sudo -u nova)
#   VSL_BUCKET       R2 bucket                    (default: work-vsl)
#   VSL_PUBLIC_BASE  public base URL of the bucket (default: read from the bucket's managed r2.dev domain)
#   VSL_OUTDIR       also copy the final video.mp4 + captions.vtt here (vsl-intake.sh files them in Drive 02_final)
#   VSL_KEEP=1       keep the work dir
set -euo pipefail

IN=${1:?input video}; SLUG=${2:?project slug}; DATE=${3:-$(date -u +%F)}; POSTER=${4:-}
[[ $SLUG =~ ^[a-z0-9][a-z0-9-]*$ ]] || { echo "slug must be [a-z0-9-]: $SLUG" >&2; exit 2; }
[[ $DATE =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || { echo "date must be YYYY-MM-DD: $DATE" >&2; exit 2; }
[ -r "$IN" ] || { echo "cannot read $IN" >&2; exit 2; }
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
BUCKET=${VSL_BUCKET:-work-vsl}
NOVA_PY=/home/nova/.claude/private/comms-ingest/whisper-venv/bin/python
# TODO (Tyler 2026-11-24): move to vsl-owned venv, nova not in the chain. NOVA_PY stays only as the last fallback where /opt/voice-v3/venv is absent.
VOICE_PY=/opt/voice-v3/venv/bin/python   # Ra: exists, executable, imports faster_whisper (checked 2026-11-24)

WORK=$(mktemp -d "${TMPDIR:-/tmp}/vsl-publish.XXXXXX")
[ "${VSL_KEEP:-}" = 1 ] || trap 'rm -rf "$WORK"' EXIT
chmod 755 "$WORK"   # the captions step may run as another unix user (nova) and must read the mp4
say() { printf '[vsl-publish] %s\n' "$*" >&2; }

# ── 1 transcode ─────────────────────────────────────────────────────────────────────────────────────────
OUT="$WORK/video.mp4"
say "transcode → H.264 high / AAC 160k / faststart, ≤1080p"
ffmpeg -nostdin -loglevel error -y -i "$IN" \
  -vf "scale='if(gt(ih,1080),-2,iw)':'if(gt(ih,1080),1080,ih)'" \
  -c:v libx264 -profile:v high -pix_fmt yuv420p -crf 20 -preset slow \
  -c:a aac -b:a 160k -movflags +faststart "$OUT"
chmod 644 "$OUT"

# ── 2 probe ─────────────────────────────────────────────────────────────────────────────────────────────
V=$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,height -of csv=p=0 "$OUT")
A=$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of csv=p=0 "$OUT")
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT")
ORDER=$(python3 - "$OUT" <<'PY'
import struct, sys
f = open(sys.argv[1], "rb"); seen = []
while True:
    h = f.read(8)
    if len(h) < 8: break
    size, kind = struct.unpack(">I4s", h); kind = kind.decode("latin-1")
    if size == 1: size = struct.unpack(">Q", f.read(8))[0]; f.seek(size - 16, 1)
    elif size == 0: seen.append(kind); break
    else: f.seek(size - 8, 1)
    seen.append(kind)
print(" ".join(seen))
PY
)
say "probe: video=$V audio=$A duration=${DUR}s atoms=[$ORDER]"
[[ $V == h264,* ]] || { say "FAIL: video stream is not h264 ($V)"; exit 1; }
[ "$A" = aac ] || { say "FAIL: audio stream is not aac ($A)"; exit 1; }
python3 -c "import sys;a=sys.argv[1].split();sys.exit(0 if 'moov' in a and 'mdat' in a and a.index('moov')<a.index('mdat') else 1)" "$ORDER" \
  || { say "FAIL: moov is not before mdat — not faststart"; exit 1; }

# ── 3 captions ──────────────────────────────────────────────────────────────────────────────────────────
VTT="$WORK/captions.vtt"
if [ -n "${VSL_WHISPER_PY:-}" ]; then
  RUN=("$VSL_WHISPER_PY")
elif [ -x "$VOICE_PY" ] && "$VOICE_PY" -c "import faster_whisper" 2>/dev/null; then
  RUN=("$VOICE_PY")
elif [ -x "$NOVA_PY" ]; then
  RUN=("$NOVA_PY")
else
  RUN=(sudo -n -u nova "$NOVA_PY")
fi
say "captions: faster-whisper large-v3-turbo int8 (${RUN[*]})"
# the captions writer may be another user: let it write into WORK, then take the file back
chmod 777 "$WORK"
cp "$HERE/vsl-captions.py" "$WORK/vsl-captions.py"; chmod 644 "$WORK/vsl-captions.py"   # the other user cannot read this clone
( cd "$WORK" && "${RUN[@]}" "$WORK/vsl-captions.py" "$OUT" "$VTT" )
chmod 755 "$WORK"
head -1 "$VTT" | grep -qx WEBVTT || { say "FAIL: $VTT is not WebVTT"; exit 1; }
CUES=$(grep -c -- '-->' "$VTT")
say "captions: $CUES cues"

# ── 4 upload ────────────────────────────────────────────────────────────────────────────────────────────
export RCLONE_CONFIG_R2_TYPE=s3 RCLONE_CONFIG_R2_PROVIDER=Cloudflare RCLONE_CONFIG_R2_NO_CHECK_BUCKET=true RCLONE_CONFIG_R2_NO_HEAD=true  # rclone 1.60 re-HEADs with ?versionId=, which R2 answers 501; step 5 verifies the public URLs instead
RCLONE_CONFIG_R2_ACCESS_KEY_ID=$(cred get fleet-infra R2_ACCESS_KEY_ID_UTOPIA); export RCLONE_CONFIG_R2_ACCESS_KEY_ID
RCLONE_CONFIG_R2_SECRET_ACCESS_KEY=$(cred get fleet-infra R2_SECRET_ACCESS_KEY_UTOPIA); export RCLONE_CONFIG_R2_SECRET_ACCESS_KEY
RCLONE_CONFIG_R2_ENDPOINT=$(cred get fleet-infra R2_S3_ENDPOINT_UTOPIA); export RCLONE_CONFIG_R2_ENDPOINT
[ ${#RCLONE_CONFIG_R2_ACCESS_KEY_ID} -gt 0 ] && [ ${#RCLONE_CONFIG_R2_SECRET_ACCESS_KEY} -gt 0 ] || { say "FAIL: R2 keys empty in Infisical"; exit 1; }
if [ -z "${VSL_PUBLIC_BASE:-}" ]; then
  T=$(cred get fleet-infra CF_API_TOKEN_UTOPIA); ACC=$(cred get fleet-infra CF_ACCOUNT_ID_UTOPIA)
  D=$(curl -fsS -H "Authorization: Bearer $T" "https://api.cloudflare.com/client/v4/accounts/$ACC/r2/buckets/$BUCKET/domains/managed" | jq -r 'select(.result.enabled) | .result.domain')
  [ -n "$D" ] || { say "FAIL: bucket $BUCKET has no public domain; set VSL_PUBLIC_BASE"; exit 1; }
  VSL_PUBLIC_BASE="https://$D"
fi
KEY="$SLUG/$DATE"
up() { rclone copyto --quiet --header-upload "Content-Type: $3" --header-upload "Cache-Control: public, max-age=31536000, immutable" "$1" "r2:$BUCKET/$KEY/$2"; }
say "upload → r2:$BUCKET/$KEY/"
up "$OUT" video.mp4 video/mp4
up "$VTT" captions.vtt "text/vtt; charset=utf-8"
[ -n "$POSTER" ] && up "$POSTER" poster.webp image/webp

# ── 5 verify the public objects ─────────────────────────────────────────────────────────────────────────
check() {  # url expected-content-type-prefix
  local h code ct
  h=$(curl -sS -o /dev/null -D - "$1"); code=$(sed -n '1s/^HTTP\/[0-9.]* \([0-9]*\).*/\1/p' <<<"$h")
  ct=$(grep -i '^content-type:' <<<"$h" | tail -1 | cut -d' ' -f2- | tr -d '\r')
  say "verify $1 → $code $ct"
  [ "$code" = 200 ] && [[ $ct == "$2"* ]] || { say "FAIL: $1"; return 1; }
}
U="$VSL_PUBLIC_BASE/$KEY"
for i in 1 2 3 4 5; do curl -fsS -o /dev/null "$U/video.mp4" && break; sleep 3; done
check "$U/video.mp4" video/mp4
check "$U/captions.vtt" text/vtt
[ -n "$POSTER" ] && check "$U/poster.webp" image/webp
R=$(curl -sS -o /dev/null -w '%{http_code} %{size_download}' -H 'Range: bytes=0-1023' "$U/video.mp4")
say "verify Range bytes=0-1023 → $R"
[ "${R%% *}" = 206 ] && [ "${R##* }" = 1024 ] || { say "FAIL: no byte-range support"; exit 1; }

[ -n "${VSL_OUTDIR:-}" ] && cp "$OUT" "$VTT" "$VSL_OUTDIR"/
jq -cn --arg slug "$SLUG" --arg date "$DATE" --arg v "$U/video.mp4" --arg c "$U/captions.vtt" \
  --arg p "$([ -n "$POSTER" ] && echo "$U/poster.webp")" --arg d "$DUR" --argjson cues "$CUES" \
  '{slug:$slug,date:$date,video:$v,captions:$c,duration_s:($d|tonumber),cues:$cues} + (if $p=="" then {} else {poster:$p} end)'

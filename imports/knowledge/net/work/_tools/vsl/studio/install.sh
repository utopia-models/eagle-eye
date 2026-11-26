#!/usr/bin/env bash
# Kitsu + Zou on Ra, native (knowledge#14747). Run from novaserver as any fleet account that reads Infisical fleet-infra:
#   bash net/work/_tools/vsl/studio/install.sh            # install or upgrade, idempotent
#   bash net/work/_tools/vsl/studio/install.sh verify     # PASS/FAIL each piece, changes nothing
# Follows cgwire/kitsu-developer-documentation docs/self-hosting/setup.md (the Docker image is test-only), with three
# changes: Python 3.12 comes from uv (Ra is Ubuntu 26.04, Python 3.14; zou wants >=3.11,<3.15 and its wheels lag),
# nginx listens on 127.0.0.1:8820 only, and `tailscale serve` publishes it on the tailnet at https://ra.tail4016d7.ts.net:8451,
# which the Cloudflare tunnel fronts as studio.utopiamodels.ai behind Access (cloudflare.sh).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
RA=${STUDIO_HOST:-root@ra}
G=~/.claude/scripts/infisical-get.sh
MODE=${1:-install}

if [ "$MODE" = verify ]; then
  ssh -o BatchMode=yes "$RA" bash -s <<'EOF'
ok() { echo "PASS $1"; }; no() { echo "FAIL $1"; FAILED=1; }
FAILED=0
for u in postgresql redis-server nginx zou zou-events; do systemctl is-active -q $u && ok "$u active" || no "$u active"; done
curl -sf http://127.0.0.1:5000/ | grep -q '"api"' && ok "zou api answers on :5000" || no "zou api answers on :5000"
curl -sf http://127.0.0.1:8820/api/ | grep -q '"api"' && ok "nginx /api on :8820" || no "nginx /api on :8820"
curl -sf http://127.0.0.1:8820/ | grep -qi '<title>kitsu' && ok "kitsu ui on :8820" || no "kitsu ui on :8820"
tailscale serve status 2>/dev/null | grep -A1 ':8451' | grep -q 127.0.0.1:8820 && ok "tailscale serve :8451 -> :8820" || no "tailscale serve :8451"
/opt/studio/venv/bin/python -c 'import gazu' 2>/dev/null && ok "gazu in /opt/studio/venv" || no "gazu in /opt/studio/venv"
[ "$(stat -c '%U %a' /home/eagle/.config/studio/credentials 2>/dev/null)" = "horus 600" ] && ok "horus's Kitsu login file" || no "horus's Kitsu login file"
exit $FAILED
EOF
  exit $?
fi

DBP=$(bash $G fleet-infra KITSU_DB_PASSWORD prod); SK=$(bash $G fleet-infra KITSU_SECRET_KEY prod)
AE=$(bash $G fleet-infra KITSU_ADMIN_EMAIL prod); AP=$(bash $G fleet-infra KITSU_ADMIN_PASSWORD prod)
TP=$(bash $G fleet-infra KITSU_TYLER_PASSWORD prod)   # Tyler's own Kitsu login (tyler@example.com), for the UI
[ ${#DBP} -ge 16 ] && [ ${#SK} -ge 16 ] && [ ${#AP} -ge 16 ] && [ ${#TP} -ge 16 ] && [ -n "$AE" ] || { echo "install: Kitsu secrets missing in Infisical fleet-infra" >&2; exit 1; }

scp -q "$HERE/nginx-studio.conf" "$HERE/zou.service" "$HERE/zou-events.service" "$RA:/tmp/"
# Secrets ride stdin, never argv.
printf 'DBP=%q\nSK=%q\nAE=%q\nAP=%q\nTP=%q\n' "$DBP" "$SK" "$AE" "$AP" "$TP" | ssh -o BatchMode=yes "$RA" 'umask 077; cat > /root/.studio-install.env'
ssh -o BatchMode=yes "$RA" bash -s <<'EOF'
set -euo pipefail
. /root/.studio-install.env; rm -f /root/.studio-install.env
export DEBIAN_FRONTEND=noninteractive
apt-get install -y -q postgresql redis-server nginx xmlsec1 ffmpeg >/dev/null
rm -f /etc/nginx/sites-enabled/default
command -v uv >/dev/null || install -m 0755 /home/eagle/.local/bin/uv /usr/local/bin/uv

id zou >/dev/null 2>&1 || useradd --system --home /opt/zou --shell /usr/sbin/nologin zou
mkdir -p /opt/zou/{backups,previews,tmp,logs,python} /etc/zou /opt/kitsu
chown zou: /opt/zou/backups /opt/zou/logs; chown -R zou:www-data /opt/zou/previews /opt/zou/tmp

export UV_PYTHON_INSTALL_DIR=/opt/zou/python
[ -x /opt/zou/zouenv/bin/python ] || uv venv -q --python 3.12 /opt/zou/zouenv
uv pip install -q --python /opt/zou/zouenv/bin/python --upgrade zou
chmod -R a+rX /opt/zou/python /opt/zou/zouenv
# The client the `vsl` studio verbs use (fleet-plugins skills/vsl/studio.py re-execs into it).
mkdir -p /opt/studio
[ -x /opt/studio/venv/bin/python ] || uv venv -q --python 3.12 /opt/studio/venv
uv pip install -q --python /opt/studio/venv/bin/python --upgrade gazu
chmod -R a+rX /opt/studio
# horus drives Kitsu as the admin account (the studio bot); its login sits in horus's home, 0600, never in git.
install -d -o horus -g horus -m 0700 /home/eagle/.config/studio
printf 'STUDIO_EMAIL=%s\nSTUDIO_PASSWORD=%s\n' "$AE" "$AP" > /home/eagle/.config/studio/credentials
chown horus:horus /home/eagle/.config/studio/credentials; chmod 0600 /home/eagle/.config/studio/credentials

# Postgres: role zou owns db zoudb; password from Infisical, re-set on every run so a rotation lands.
sudo -u postgres psql -qtAc "select 1 from pg_roles where rolname='zou'" | grep -q 1 || sudo -u postgres psql -qc "create role zou login"
sudo -u postgres psql -q -v p="$DBP" <<<"alter role zou with password :'p';"
sudo -u postgres psql -qtAc "select 1 from pg_database where datname='zoudb'" | grep -q 1 || sudo -u postgres createdb -O zou zoudb

umask 027
cat > /etc/zou/zou.env <<ENV
DB_HOST=127.0.0.1
DB_USERNAME=zou
DB_PASSWORD=$DBP
DB_DATABASE=zoudb
KV_HOST=127.0.0.1
PREVIEW_FOLDER=/opt/zou/previews
TMP_DIR=/opt/zou/tmp
SECRET_KEY=$SK
INDEXER_HOST=
ENV
chgrp zou /etc/zou/zou.env; chmod 0640 /etc/zou/zou.env
umask 022
cat > /etc/zou/gunicorn.py <<'PY'
accesslog = "/opt/zou/logs/gunicorn_access.log"
errorlog = "/opt/zou/logs/gunicorn_error.log"
workers = 2
worker_class = "gevent"
PY
cat > /etc/zou/gunicorn-events.py <<'PY'
accesslog = "/opt/zou/logs/gunicorn_events_access.log"
errorlog = "/opt/zou/logs/gunicorn_events_error.log"
workers = 1
worker_class = "geventwebsocket.gunicorn.workers.GeventWebSocketWorker"
PY

zou() { sudo -u zou bash -c 'set -a; . /etc/zou/zou.env; set +a; cd /opt/zou; exec /opt/zou/zouenv/bin/zou "$@"' zou "$@"; }
zou upgrade-db >/dev/null 2>&1 || zou init-db
zou init-data >/dev/null
zou create-admin --password "$AP" "$AE" >/dev/null 2>&1 || true   # exists already on a re-run
zou create-admin --password "$TP" tyler@example.com >/dev/null 2>&1 || zou change-password tyler@example.com --password "$TP" >/dev/null

# Kitsu UI: the latest release build.
VER=$(curl -sfL https://api.github.com/repos/cgwire/kitsu/releases/latest | sed -n 's/.*"tag_name": *"v\{0,1\}\([^"]*\)".*/\1/p' | head -1)
if [ -n "$VER" ] && [ "$(cat /opt/kitsu/VERSION 2>/dev/null)" != "$VER" ]; then
  curl -sfL -o /tmp/kitsu.tgz "https://github.com/cgwire/kitsu/releases/download/v$VER/kitsu-$VER.tgz"
  rm -rf /opt/kitsu/dist.new && mkdir -p /opt/kitsu/dist.new && tar xzf /tmp/kitsu.tgz -C /opt/kitsu/dist.new
  rm -rf /opt/kitsu/dist && mv /opt/kitsu/dist.new /opt/kitsu/dist && echo "$VER" > /opt/kitsu/VERSION && rm -f /tmp/kitsu.tgz
fi

install -m 0644 /tmp/zou.service /tmp/zou-events.service /etc/systemd/system/
install -m 0644 /tmp/nginx-studio.conf /etc/nginx/sites-available/studio
ln -sf /etc/nginx/sites-available/studio /etc/nginx/sites-enabled/studio
rm -f /tmp/zou.service /tmp/zou-events.service /tmp/nginx-studio.conf
systemctl daemon-reload
systemctl enable -q postgresql redis-server nginx zou zou-events
systemctl restart zou zou-events
nginx -t -q && systemctl reload nginx
tailscale serve --bg --https=8451 http://127.0.0.1:8820 >/dev/null
echo "installed: zou $(/opt/zou/zouenv/bin/pip show zou 2>/dev/null | awk '/^Version/{print $2}' || /opt/zou/zouenv/bin/python -c 'import zou;print(zou.__version__)') · kitsu $(cat /opt/kitsu/VERSION)"
EOF
sleep 4
exec bash "$0" verify

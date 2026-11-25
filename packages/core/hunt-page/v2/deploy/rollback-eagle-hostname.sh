#!/usr/bin/env bash
# One-step rollback of the 2026-11-22 promote: eagle.utopiamodels.ai back to the OLD Eagle Eye Worker (eagle-eye),
# dev.eagle.utopiamodels.ai back to the OLD preview Worker (eagle-dev), tunnel ra-demos ingress back to absa + hooks.
# Before the promote: both hostnames were Worker custom domains (eagle-eye / eagle-dev, AAAA 100:: managed by Workers).
# After the promote: eagle. = proxied CNAME -> tunnel ra-demos (042826eb) -> Ra :8797 UI, /api /rest /v /healthz -> :8798;
#                    dev.eagle. = Worker custom domain -> eagle-dev-redirect (302 to eagle.). Access apps untouched.
set -euo pipefail
G=~/.claude/scripts/infisical-get.sh
T=$(bash $G fleet-infra CF_API_TOKEN_UTOPIA prod); A=$(bash $G fleet-infra CF_ACCOUNT_ID_UTOPIA prod)
Z=9519ae058988535a737e845353ce13cf; TUN=042826eb-8712-4d0f-a12e-9a3d091f302c
api() { curl -s -H "Authorization: Bearer $T" -H "Content-Type: application/json" "$@"; }
for id in $(api "https://api.cloudflare.com/client/v4/zones/$Z/dns_records?name=eagle.utopiamodels.ai&type=CNAME" | jq -r '.result[].id'); do
  api -X DELETE "https://api.cloudflare.com/client/v4/zones/$Z/dns_records/$id" | jq -c '{cname_deleted:.success}'; done
for pair in "eagle.utopiamodels.ai:eagle-eye" "dev.eagle.utopiamodels.ai:eagle-dev"; do
  h=${pair%%:*}; svc=${pair##*:}
  api -X PUT "https://api.cloudflare.com/client/v4/accounts/$A/workers/domains" \
    --data "{\"zone_id\":\"$Z\",\"hostname\":\"$h\",\"service\":\"$svc\",\"environment\":\"production\"}" | jq -c "{host:\"$h\",worker:\"$svc\",ok:.success,errors}"
done
api -X PUT "https://api.cloudflare.com/client/v4/accounts/$A/cfd_tunnel/$TUN/configurations" \
  --data '{"config":{"ingress":[{"service":"http://127.0.0.1:8851","hostname":"absa.utopiamodels.ai"},{"service":"http://127.0.0.1:8861","hostname":"hooks.utopiamodels.ai"},{"service":"http_status:404"}],"warp-routing":{"enabled":false}}}' | jq -c '{ingress_restored:.success}'

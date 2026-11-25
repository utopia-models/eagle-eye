import { createHash, randomBytes } from "node:crypto";
import { asOwner } from "./db.ts";

export type Actor = { source: "AGENT" | "API" | "IMPORT" | "MANUAL" | "SYSTEM" | "WEBHOOK"; name: string; api_key_id?: string };
export type ApiKey = { id: string; workspaceId: string; name: string; actorKind: string; scopes: string[] };

export const sha256 = (s: string | Buffer) => createHash("sha256").update(s).digest();

/** Mint a per-agent token. Only sha256(token) is stored; the token is returned once. */
export async function mintKey(o: { workspace: string; name: string; actorKind?: string; scopes: string[]; ttlSeconds: number }) {
  const token = "ee_" + randomBytes(24).toString("base64url");
  const row = await asOwner(async tx => (await tx.query(
    `insert into api_keys (workspace_id, name, actor_kind, token_sha256, scopes, expires_at)
     select id, $2, $3, $4, $5, now() + make_interval(secs => $6) from workspaces where slug = $1 and deleted_at is null
     returning id, expires_at`,
    [o.workspace, o.name, o.actorKind || "agent_backend", sha256(token), o.scopes, o.ttlSeconds])).rows[0]);
  if (!row) throw new Error(`no workspace ${o.workspace}`);
  return { token, id: row.id as string, expiresAt: row.expires_at as Date };
}

export async function revokeKey(id: string) {
  await asOwner(tx => tx.query("update api_keys set revoked_at = now() where id = $1", [id]));
}

/** Resolve a bearer token to its key row; expired or revoked keys resolve to null. */
export async function resolveKey(token: string): Promise<ApiKey | null> {
  if (!token || token.length > 200) return null;
  return asOwner(async tx => {
    const r = (await tx.query(
      `update api_keys set last_used_at = now()
       where token_sha256 = $1 and revoked_at is null and expires_at > now()
       returning id, workspace_id, name, actor_kind, scopes`, [sha256(token)])).rows[0];
    return r ? { id: r.id, workspaceId: r.workspace_id, name: r.name, actorKind: r.actor_kind, scopes: r.scopes } : null;
  });
}

/** Scope grammar: "<resource>:read" | "<resource>:write" | "<resource>:*" | "*". write implies read. */
export function allowed(scopes: string[], resource: string, mode: "read" | "write") {
  return scopes.some(s => s === "*" || s === `${resource}:*` || s === `${resource}:${mode}` || (mode === "read" && s === `${resource}:write`));
}

export const actorOf = (k: ApiKey): Actor => ({ source: k.actorKind === "integration" ? "WEBHOOK" : "AGENT", name: k.name, api_key_id: k.id });

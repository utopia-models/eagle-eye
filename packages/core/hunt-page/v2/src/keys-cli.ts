// eagle key mint <name> --scopes huntItems:write,people:write [--ttl 3600] [--workspace tyler] [--kind agent_backend]
// eagle key revoke <id>
// The token is printed once, to stdout, for the caller to put in Infisical (infisical-set.sh reads STDIN).
import { mintKey, revokeKey } from "./keys.ts";
import { pool } from "./db.ts";

const [cmd, arg] = process.argv.slice(2);
const opt = (k: string, d?: string) => { const i = process.argv.indexOf("--" + k); return i > 0 ? process.argv[i + 1] : d; };

try {
  if (cmd === "mint" && arg) {
    const k = await mintKey({ workspace: opt("workspace", "tyler")!, name: arg, actorKind: opt("kind", "agent_backend"),
      scopes: (opt("scopes", "") || "").split(",").filter(Boolean), ttlSeconds: Number(opt("ttl", String(90 * 86400))) });
    process.stderr.write(`minted key ${k.id} (${arg}), expires ${k.expiresAt.toISOString()}\n`);
    process.stdout.write(k.token);
  } else if (cmd === "revoke" && arg) {
    await revokeKey(arg);
    process.stderr.write(`revoked ${arg}\n`);
  } else {
    process.stderr.write("usage: key mint <name> --scopes a:write,b:read [--ttl s] [--workspace slug] [--kind k] | key revoke <id>\n");
    process.exitCode = 2;
  }
} finally {
  await pool.end();
}

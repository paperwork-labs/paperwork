import { sql, ensureSecretsTable } from "@/lib/db";

type SecretRow = {
  id: string;
  name: string;
  service: string;
  location: string;
  description: string | null;
  expires_at: string | null;
  last_rotated_at: string | null;
  created_at: string;
  updated_at: string;
};

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "—";
  try {
    return new Intl.DateTimeFormat("en-US", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(dateStr));
  } catch {
    return "—";
  }
}

function daysUntil(dateStr: string | null): number | null {
  if (!dateStr) return null;
  try {
    const diff = new Date(dateStr).getTime() - Date.now();
    return Math.floor(diff / (1000 * 60 * 60 * 24));
  } catch {
    return null;
  }
}

function truncate(str: string | null, maxLen: number): string {
  if (!str) return "—";
  if (str.length <= maxLen) return str;
  return str.slice(0, maxLen) + "…";
}

function groupByService(secrets: SecretRow[]): Map<string, SecretRow[]> {
  const map = new Map<string, SecretRow[]>();
  for (const s of secrets) {
    const list = map.get(s.service) ?? [];
    list.push(s);
    map.set(s.service, list);
  }
  return map;
}

export default async function SecretsPage() {
  let dbError: string | null = null;
  let secrets: SecretRow[] = [];

  try {
    if (!process.env.DATABASE_URL) {
      dbError = "Database not configured";
    } else {
      await ensureSecretsTable();
      const db = sql();
      const rows = await db`
        SELECT id, name, service, location, description, expires_at, last_rotated_at, created_at, updated_at
        FROM secrets
        ORDER BY service, name
      `;
      secrets = rows as SecretRow[];
    }
  } catch (err) {
    dbError = err instanceof Error ? err.message : "Database not configured";
  }

  if (dbError) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-semibold tracking-tight">Secrets Vault</h1>
        <p className="text-zinc-400">
          Encrypted secrets across all services. Values stored with AES-256-GCM in Neon PostgreSQL.
        </p>
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-rose-300">Database not configured</p>
          <p className="mt-2 text-sm text-zinc-400">
            Set DATABASE_URL in your environment to view and manage secrets.
          </p>
        </div>
      </div>
    );
  }

  const now = Date.now();
  const sixtyDays = 60 * 24 * 60 * 60 * 1000;

  const expiringSoon = secrets.filter((s) => {
    if (!s.expires_at) return false;
    const exp = new Date(s.expires_at).getTime();
    return exp - now <= sixtyDays && exp > now;
  });

  const servicesCount = new Set(secrets.map((s) => s.service)).size;
  const grouped = groupByService(secrets);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Secrets Vault</h1>
        <p className="text-zinc-400">
          Encrypted secrets across all services. Values stored with AES-256-GCM in Neon PostgreSQL.
        </p>
      </div>

      <section className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Total secrets</p>
          <p className="mt-2 text-2xl font-semibold text-zinc-100">{secrets.length}</p>
        </div>
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Expiring soon</p>
          <p className={`mt-2 text-2xl font-semibold ${expiringSoon.length > 0 ? "text-amber-300" : "text-emerald-300"}`}>
            {expiringSoon.length}
          </p>
          <p className="text-sm text-zinc-400">within 60 days</p>
        </div>
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="text-xs uppercase tracking-wide text-zinc-400">Services covered</p>
          <p className="mt-2 text-2xl font-semibold text-zinc-100">{servicesCount}</p>
        </div>
      </section>

      {expiringSoon.length > 0 && (
        <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="mb-3 text-sm font-medium text-zinc-200">Expiry alerts</p>
          <div className="space-y-2">
            {expiringSoon.map((s) => {
              const days = daysUntil(s.expires_at);
              const critical = days !== null && days < 30;
              return (
                <div
                  key={s.id}
                  className={`rounded-md bg-zinc-800/60 px-3 py-3 text-sm ${critical ? "text-rose-300" : "text-amber-300"}`}
                >
                  <span className="font-medium">{s.name}</span>
                  <span className="mx-2 text-zinc-500">•</span>
                  <span className="text-zinc-400">{s.service}</span>
                  <span className="mx-2 text-zinc-500">•</span>
                  <span>
                    {days !== null ? (days <= 0 ? "expired" : `${days} days until expiry`) : "—"}
                  </span>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {secrets.length === 0 ? (
        <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
          <p className="mb-3 text-sm font-medium text-zinc-200">No secrets yet</p>
          <p className="text-sm text-zinc-400">
            Add secrets via the API. Example:
          </p>
          <pre className="mt-3 overflow-x-auto rounded-md bg-zinc-800/60 px-3 py-3 text-xs text-zinc-300">
{`curl -X POST "$STUDIO_URL/api/secrets" \\
  -H "Authorization: Bearer $SECRETS_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{"name": "MY_SECRET", "value": "secret-value", "service": "my-service"}'`}
          </pre>
        </section>
      ) : (
        <section className="space-y-6">
          {Array.from(grouped.entries()).map(([service, serviceSecrets]) => (
            <div key={service} className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
              <p className="mb-3 text-sm font-medium text-zinc-200">{service}</p>
              <div className="space-y-2">
                {serviceSecrets.map((s) => (
                  <div
                    key={s.id}
                    className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-md bg-zinc-800/60 px-3 py-3 text-sm"
                  >
                    <span className="font-medium text-zinc-100">{s.name}</span>
                    <span className="text-zinc-500">{s.location || "—"}</span>
                    <span className="text-zinc-400">{truncate(s.description, 60)}</span>
                    <span className="text-zinc-500 text-xs">expires: {formatDate(s.expires_at)}</span>
                    <span className="text-zinc-500 text-xs">rotated: {formatDate(s.last_rotated_at)}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </section>
      )}

      <section className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-5">
        <p className="mb-3 text-sm font-medium text-zinc-200">Secrets API</p>
        <p className="mb-3 text-sm text-zinc-400">
          Auth: <code className="rounded bg-zinc-800 px-1.5 py-0.5">Authorization: Bearer &lt;SECRETS_API_KEY&gt;</code>{" "}
          or Basic Auth
        </p>
        <div className="space-y-2 text-sm text-zinc-300">
          <div className="rounded-md bg-zinc-800/60 px-3 py-3">
            <code>GET /api/secrets</code> — List all (no values)
          </div>
          <div className="rounded-md bg-zinc-800/60 px-3 py-3">
            <code>POST /api/secrets</code> — Create or update
          </div>
          <div className="rounded-md bg-zinc-800/60 px-3 py-3">
            <code>GET /api/secrets/:id</code> — Get decrypted value
          </div>
          <div className="rounded-md bg-zinc-800/60 px-3 py-3">
            <code>GET /api/secrets/export</code> — Export as .env
          </div>
        </div>
      </section>
    </div>
  );
}

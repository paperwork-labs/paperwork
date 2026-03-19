import { sql, ensureSecretsTable } from "@/lib/db";
import SecretsClient from "./secrets-client";

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
        <h1 className="bg-gradient-to-r from-zinc-200 to-zinc-400 bg-clip-text text-2xl font-semibold tracking-tight text-transparent">
          Secrets Vault
        </h1>
        <div className="rounded-xl border border-rose-800/40 bg-rose-950/20 p-5">
          <p className="text-rose-300">Database not configured</p>
          <p className="mt-2 text-sm text-zinc-400">
            Set DATABASE_URL in your environment to view and manage secrets.
          </p>
        </div>
      </div>
    );
  }

  const apiKey = process.env.SECRETS_API_KEY || "";

  return <SecretsClient secrets={secrets} apiKey={apiKey} />;
}

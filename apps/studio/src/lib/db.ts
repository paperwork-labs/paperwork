import { neon } from "@neondatabase/serverless";

function getDbUrl() {
  const url = process.env.DATABASE_URL || process.env.DATABASE_URL_UNPOOLED;
  if (!url) throw new Error("DATABASE_URL is not configured");
  return url;
}

export function sql() {
  return neon(getDbUrl());
}

export async function ensureSecretsTable() {
  const db = sql();
  await db`CREATE EXTENSION IF NOT EXISTS pgcrypto`;
  await db`
    CREATE TABLE IF NOT EXISTS secrets (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      name TEXT NOT NULL UNIQUE,
      encrypted_value TEXT NOT NULL,
      iv TEXT NOT NULL,
      auth_tag TEXT NOT NULL,
      service TEXT NOT NULL,
      location TEXT NOT NULL DEFAULT '',
      description TEXT DEFAULT '',
      expires_at TIMESTAMPTZ,
      last_rotated_at TIMESTAMPTZ,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
  `;
}

export async function ensureSecretIntakesTable() {
  await ensureSecretsTable();
  const db = sql();
  await db`
    CREATE TABLE IF NOT EXISTS secret_intakes (
      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      intake_token TEXT UNIQUE NOT NULL,
      secret_name TEXT NOT NULL,
      service TEXT NOT NULL,
      description TEXT,
      expected_prefix TEXT,
      status TEXT NOT NULL DEFAULT 'pending',
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      expires_at TIMESTAMPTZ NOT NULL,
      received_at TIMESTAMPTZ,
      received_by_email TEXT,
      received_from_ip TEXT,
      upserted_secret_id UUID REFERENCES secrets(id),
      created_by TEXT NOT NULL DEFAULT 'agent',
      CONSTRAINT status_valid CHECK (status IN ('pending','received','expired','cancelled'))
    )
  `;
  await db`CREATE INDEX IF NOT EXISTS secret_intakes_token_idx ON secret_intakes(intake_token)`;
  await db`CREATE INDEX IF NOT EXISTS secret_intakes_status_idx ON secret_intakes(status, expires_at)`;
}

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

import { NextRequest, NextResponse } from "next/server";
import { sql, ensureSecretsTable } from "@/lib/db";
import { encrypt } from "@/lib/crypto";
import { authenticateSecretsRequest } from "@/lib/secrets-auth";

export async function GET(request: NextRequest) {
  const auth = authenticateSecretsRequest(request);
  if (!auth.ok) return auth.response;

  try {
    await ensureSecretsTable();
    const db = sql();
    const rows = await db`
      SELECT id, name, service, location, description, expires_at, last_rotated_at, created_at, updated_at
      FROM secrets
      ORDER BY service, name
    `;

    return NextResponse.json({ success: true, data: rows });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ success: false, error: message }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  const auth = authenticateSecretsRequest(request);
  if (!auth.ok) return auth.response;

  try {
    const body = await request.json();
    const { name, value, service, location, description, expires_at } = body;

    if (!name || !value || !service) {
      return NextResponse.json(
        { success: false, error: "name, value, and service are required" },
        { status: 400 },
      );
    }

    await ensureSecretsTable();
    const db = sql();
    const { encrypted, iv, authTag } = encrypt(value);

    const rows = await db`
      INSERT INTO secrets (name, encrypted_value, iv, auth_tag, service, location, description, expires_at)
      VALUES (${name}, ${encrypted}, ${iv}, ${authTag}, ${service}, ${location || ""}, ${description || ""}, ${expires_at || null})
      ON CONFLICT (name) DO UPDATE SET
        encrypted_value = EXCLUDED.encrypted_value,
        iv = EXCLUDED.iv,
        auth_tag = EXCLUDED.auth_tag,
        service = EXCLUDED.service,
        location = COALESCE(EXCLUDED.location, secrets.location),
        description = COALESCE(EXCLUDED.description, secrets.description),
        expires_at = COALESCE(EXCLUDED.expires_at, secrets.expires_at),
        last_rotated_at = now(),
        updated_at = now()
      RETURNING id, name, service, location, description, expires_at, last_rotated_at, created_at, updated_at
    `;

    return NextResponse.json({ success: true, data: rows[0] }, { status: 201 });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ success: false, error: message }, { status: 500 });
  }
}

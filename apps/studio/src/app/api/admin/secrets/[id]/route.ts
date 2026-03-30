import { NextRequest, NextResponse } from "next/server";
import { sql, ensureSecretsTable } from "@/lib/db";
import { decrypt } from "@/lib/crypto";
import { authenticateSecretsRequest } from "@/lib/secrets-auth";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const auth = authenticateSecretsRequest(request);
  if (!auth.ok) return auth.response;

  try {
    const { id } = await params;
    if (!UUID_RE.test(id)) {
      return NextResponse.json({ success: false, error: "Invalid secret ID format" }, { status: 400 });
    }
    await ensureSecretsTable();
    const db = sql();

    const rows = await db`
      SELECT id, name, encrypted_value, iv, auth_tag, service, location, description, expires_at, last_rotated_at
      FROM secrets
      WHERE id = ${id}::uuid
    `;

    if (rows.length === 0) {
      return NextResponse.json({ success: false, error: "Secret not found" }, { status: 404 });
    }

    const row = rows[0];
    const value = decrypt(
      row.encrypted_value as string,
      row.iv as string,
      row.auth_tag as string,
    );

    return NextResponse.json({
      success: true,
      data: {
        id: row.id,
        name: row.name,
        value,
        service: row.service,
        location: row.location,
        description: row.description,
        expires_at: row.expires_at,
        last_rotated_at: row.last_rotated_at,
      },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ success: false, error: message }, { status: 500 });
  }
}

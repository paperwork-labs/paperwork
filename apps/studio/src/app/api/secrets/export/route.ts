import { NextRequest, NextResponse } from "next/server";
import { sql, ensureSecretsTable } from "@/lib/db";
import { decrypt } from "@/lib/crypto";
import { authenticateSecretsRequest } from "@/lib/secrets-auth";

export async function GET(request: NextRequest) {
  const auth = authenticateSecretsRequest(request);
  if (!auth.ok) return auth.response;

  try {
    await ensureSecretsTable();
    const db = sql();
    const rows = await db`
      SELECT name, encrypted_value, iv, auth_tag, service, location, description, expires_at
      FROM secrets
      ORDER BY service, name
    `;

    let currentService = "";
    const lines: string[] = [
      "# Paperwork Labs — Secrets Export",
      `# Generated: ${new Date().toISOString()}`,
      "# DO NOT COMMIT THIS FILE",
      "",
    ];

    for (const row of rows) {
      if (row.service !== currentService) {
        currentService = row.service as string;
        lines.push(`# === ${(currentService as string).toUpperCase()} ===`);
      }

      const value = decrypt(
        row.encrypted_value as string,
        row.iv as string,
        row.auth_tag as string,
      );

      if (row.description) {
        lines.push(`# ${row.description}`);
      }
      if (row.location) {
        lines.push(`# Location: ${row.location}`);
      }
      if (row.expires_at) {
        lines.push(`# Expires: ${new Date(row.expires_at as string).toISOString().split("T")[0]}`);
      }
      lines.push(`${row.name}=${value}`);
      lines.push("");
    }

    return new NextResponse(lines.join("\n"), {
      headers: {
        "Content-Type": "text/plain; charset=utf-8",
        "Content-Disposition": 'attachment; filename=".env.secrets"',
      },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ success: false, error: message }, { status: 500 });
  }
}

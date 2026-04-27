import { NextRequest, NextResponse } from "next/server";
import { sql, ensureSecretIntakesTable } from "@/lib/db";
import { authenticateSecretsRequest } from "@/lib/secrets-auth";

type IntakeRow = {
  secret_name: string;
  status: string;
  expires_at: string;
  received_at: string | null;
};

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ token: string }> },
) {
  const auth = authenticateSecretsRequest(request);
  if (!auth.ok) return auth.response;

  try {
    const { token } = await params;
    if (!token || token.length < 16) {
      return NextResponse.json({ success: false, error: "Invalid intake" }, { status: 404 });
    }

    await ensureSecretIntakesTable();
    const db = sql();

    await db`
      UPDATE secret_intakes
      SET status = 'expired'
      WHERE intake_token = ${token}
        AND status = 'pending'
        AND expires_at <= now()
    `;

    const rows = await db`
      SELECT secret_name, status, expires_at, received_at
      FROM secret_intakes
      WHERE intake_token = ${token}
    `;

    if (rows.length === 0) {
      return NextResponse.json({ success: false, error: "Intake not found" }, { status: 404 });
    }

    const row = rows[0] as IntakeRow;
    let status = row.status;

    if (status === "pending") {
      const expiresAt = new Date(row.expires_at).getTime();
      if (Number.isFinite(expiresAt) && expiresAt <= Date.now()) {
        status = "expired";
      }
    }

    const payload: {
      success: true;
      status: string;
      secret_name: string;
      received_at?: string;
    } = {
      success: true,
      status,
      secret_name: row.secret_name,
    };

    if (row.received_at && status === "received") {
      payload.received_at = row.received_at;
    }

    return NextResponse.json(payload);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ success: false, error: message }, { status: 500 });
  }
}

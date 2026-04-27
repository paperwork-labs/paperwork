import { NextResponse } from "next/server";
import { sql, ensureSecretIntakesTable } from "@/lib/db";

type IntakeRow = {
  secret_name: string;
  service: string;
  description: string | null;
  expected_prefix: string | null;
  status: string;
  expires_at: string;
};

async function markPendingPastExpiry(db: ReturnType<typeof sql>, token: string): Promise<void> {
  await db`
    UPDATE secret_intakes
    SET status = 'expired'
    WHERE intake_token = ${token}
      AND status = 'pending'
      AND expires_at <= now()
  `;
}

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ token: string }> },
) {
  try {
    const { token } = await params;
    if (!token || token.length < 16) {
      return NextResponse.json({ success: false, error: "Invalid intake" }, { status: 404 });
    }

    await ensureSecretIntakesTable();
    const db = sql();
    await markPendingPastExpiry(db, token);

    const rows = await db`
      SELECT secret_name, service, description, expected_prefix, status, expires_at
      FROM secret_intakes
      WHERE intake_token = ${token}
    `;

    if (rows.length === 0) {
      return NextResponse.json({ success: false, error: "Intake not found" }, { status: 404 });
    }

    const row = rows[0] as IntakeRow;
    if (row.status !== "pending") {
      return NextResponse.json({ success: false, error: "Intake is no longer available" }, { status: 410 });
    }

    return NextResponse.json({
      success: true,
      data: {
        secret_name: row.secret_name,
        service: row.service,
        description: row.description,
        expected_prefix: row.expected_prefix,
        status: row.status,
        expires_at: row.expires_at,
      },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ success: false, error: message }, { status: 500 });
  }
}

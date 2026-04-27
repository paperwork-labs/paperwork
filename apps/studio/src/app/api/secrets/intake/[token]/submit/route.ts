import { currentUser } from "@clerk/nextjs/server";
import { NextRequest, NextResponse } from "next/server";
import { sql, ensureSecretIntakesTable } from "@/lib/db";
import { encrypt } from "@/lib/crypto";
import { isAdminClerkEmail } from "@/lib/admin-emails";

type IntakeRow = {
  id: string;
  secret_name: string;
  service: string;
  description: string | null;
  expected_prefix: string | null;
  status: string;
  expires_at: string;
};

type SubmitBody = { value?: string };

function clientIp(request: NextRequest): string | null {
  const forwarded = request.headers.get("x-forwarded-for");
  if (forwarded) {
    const first = forwarded.split(",")[0]?.trim();
    return first || null;
  }
  return request.headers.get("x-real-ip");
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ token: string }> },
) {
  const user = await currentUser();
  const primaryEmail =
    user?.primaryEmailAddress?.emailAddress ?? user?.emailAddresses?.[0]?.emailAddress;

  if (!user || !primaryEmail || !isAdminClerkEmail(primaryEmail)) {
    return NextResponse.json({ success: false, error: "Forbidden" }, { status: 403 });
  }

  try {
    const { token } = await params;
    if (!token || token.length < 16) {
      return NextResponse.json({ success: false, error: "Invalid intake" }, { status: 404 });
    }

    const body = (await request.json()) as SubmitBody;
    const value = body.value;
    if (typeof value !== "string") {
      return NextResponse.json({ success: false, error: "value is required" }, { status: 400 });
    }
    const trimmed = value.trim();
    if (!trimmed) {
      return NextResponse.json({ success: false, error: "value is required" }, { status: 400 });
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

    const intakeRows = await db`
      SELECT id, secret_name, service, description, expected_prefix, status, expires_at
      FROM secret_intakes
      WHERE intake_token = ${token}
    `;

    if (intakeRows.length === 0) {
      return NextResponse.json({ success: false, error: "Intake not found" }, { status: 404 });
    }

    const intake = intakeRows[0] as IntakeRow;

    if (intake.status === "received") {
      return NextResponse.json({ success: false, error: "Intake already completed" }, { status: 409 });
    }

    if (intake.status !== "pending") {
      return NextResponse.json({ success: false, error: "Intake is no longer available" }, { status: 410 });
    }

    const expiresAt = new Date(intake.expires_at).getTime();
    if (!Number.isFinite(expiresAt) || expiresAt <= Date.now()) {
      await db`
        UPDATE secret_intakes SET status = 'expired' WHERE id = ${intake.id}::uuid
      `;
      return NextResponse.json({ success: false, error: "Intake has expired" }, { status: 410 });
    }

    if (intake.expected_prefix && !trimmed.startsWith(intake.expected_prefix)) {
      const hint =
        trimmed.length <= 8 ? "(too short to show)" : `${trimmed.slice(0, 8)}...`;
      return NextResponse.json(
        {
          success: false,
          error: `value must start with expected prefix (submitted value begins: ${hint})`,
        },
        { status: 400 },
      );
    }

    const { encrypted, iv, authTag } = encrypt(trimmed);
    const location = "";
    const desc = intake.description ?? "";

    const secretRows = await db`
      INSERT INTO secrets (name, encrypted_value, iv, auth_tag, service, location, description, expires_at)
      VALUES (
        ${intake.secret_name},
        ${encrypted},
        ${iv},
        ${authTag},
        ${intake.service},
        ${location},
        ${desc},
        ${null}
      )
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
      RETURNING id
    `;

    const secretId = (secretRows[0] as { id: string }).id;
    const ip = clientIp(request);

    await db`
      UPDATE secret_intakes
      SET
        status = 'received',
        received_at = now(),
        received_by_email = ${primaryEmail},
        received_from_ip = ${ip},
        upserted_secret_id = ${secretId}::uuid
      WHERE id = ${intake.id}::uuid AND status = 'pending'
    `;

    const verify = await db`
      SELECT status FROM secret_intakes WHERE id = ${intake.id}::uuid
    `;
    const finalStatus = (verify[0] as { status: string } | undefined)?.status;
    if (finalStatus !== "received") {
      return NextResponse.json({ success: false, error: "Intake could not be completed" }, { status: 409 });
    }

    return NextResponse.json({ success: true, ok: true, secret_name: intake.secret_name });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ success: false, error: message }, { status: 500 });
  }
}

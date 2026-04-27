import { NextRequest, NextResponse } from "next/server";
import { sql, ensureSecretIntakesTable } from "@/lib/db";
import { generateIntakeToken } from "@/lib/intake-token";
import { authenticateSecretsRequest } from "@/lib/secrets-auth";
import { getStudioPublicOrigin } from "@/lib/studio-public-url";

const NAME_PATTERN = /^[A-Z_][A-Z0-9_]*$/;

type CreateBody = {
  name?: string;
  service?: string;
  description?: string;
  expected_prefix?: string;
  expires_in_minutes?: number;
};

function isUniqueViolation(err: unknown): boolean {
  if (err && typeof err === "object" && "code" in err) {
    return (err as { code: string }).code === "23505";
  }
  const msg = err instanceof Error ? err.message : "";
  return msg.includes("23505") || msg.toLowerCase().includes("unique");
}

export async function POST(request: NextRequest) {
  const auth = authenticateSecretsRequest(request);
  if (!auth.ok) return auth.response;

  try {
    const body = (await request.json()) as CreateBody;
    const { name, service, description, expected_prefix } = body;
    let expiresIn = body.expires_in_minutes;

    if (!name || !service) {
      return NextResponse.json({ success: false, error: "name and service are required" }, { status: 400 });
    }

    if (!NAME_PATTERN.test(name)) {
      return NextResponse.json(
        {
          success: false,
          error: "name must be uppercase with underscores (e.g. MY_SECRET_KEY)",
        },
        { status: 400 },
      );
    }

    if (expiresIn === undefined || expiresIn === null) {
      expiresIn = 30;
    }
    if (typeof expiresIn !== "number" || !Number.isFinite(expiresIn) || expiresIn < 1) {
      return NextResponse.json(
        { success: false, error: "expires_in_minutes must be a positive number" },
        { status: 400 },
      );
    }
    const expiresClamped = Math.min(Math.floor(expiresIn), 1440);

    await ensureSecretIntakesTable();
    const db = sql();

    await db`
      UPDATE secret_intakes
      SET status = 'expired'
      WHERE secret_name = ${name}
        AND status = 'pending'
        AND expires_at < now()
    `;

    const desc = description ?? null;
    const prefix = expected_prefix ?? null;
    const expiresAtIso = new Date(Date.now() + expiresClamped * 60 * 1000).toISOString();

    const MAX_TRIES = 10;
    let lastErr: unknown;
    for (let attempt = 0; attempt < MAX_TRIES; attempt++) {
      const token = generateIntakeToken();
      try {
        const rows = await db`
          INSERT INTO secret_intakes (
            intake_token,
            secret_name,
            service,
            description,
            expected_prefix,
            status,
            expires_at,
            created_by
          )
          VALUES (
            ${token},
            ${name},
            ${service},
            ${desc},
            ${prefix},
            'pending',
            ${expiresAtIso}::timestamptz,
            'agent'
          )
          RETURNING intake_token, expires_at
        `;
        const row = rows[0] as { intake_token: string; expires_at: string };
        const origin = getStudioPublicOrigin();
        const intakeUrl = `${origin}/admin/secrets/intake/${row.intake_token}`;
        return NextResponse.json({
          success: true,
          token: row.intake_token,
          intake_url: intakeUrl,
          expires_at: row.expires_at,
        });
      } catch (err) {
        lastErr = err;
        if (isUniqueViolation(err)) {
          continue;
        }
        throw err;
      }
    }

    const message = lastErr instanceof Error ? lastErr.message : "Could not allocate intake token";
    return NextResponse.json({ success: false, error: message }, { status: 500 });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ success: false, error: message }, { status: 500 });
  }
}

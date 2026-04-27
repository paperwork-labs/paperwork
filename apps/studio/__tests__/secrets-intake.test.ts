import { describe, it, expect, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";

const dbQueue: unknown[] = [];

vi.mock("@/lib/db", () => ({
  ensureSecretIntakesTable: vi.fn().mockResolvedValue(undefined),
  ensureSecretsTable: vi.fn().mockResolvedValue(undefined),
  sql: () => async (_strings: TemplateStringsArray, ..._values: unknown[]) => {
    if (dbQueue.length === 0) {
      throw new Error("db mock queue empty");
    }
    const next = dbQueue.shift();
    if (typeof next === "function") {
      return (next as () => unknown)();
    }
    return next;
  },
}));

vi.mock("@/lib/crypto", () => ({
  encrypt: vi.fn(() => ({
    encrypted: "enc",
    iv: "ivb64",
    authTag: "atb64",
  })),
}));

vi.mock("@/lib/secrets-auth", () => ({
  authenticateSecretsRequest: vi.fn(() => ({ ok: true as const })),
}));

const mockCurrentUser = vi.fn();
vi.mock("@clerk/nextjs/server", () => ({
  currentUser: () => mockCurrentUser(),
}));

describe("secret intake", () => {
  beforeEach(() => {
    dbQueue.length = 0;
    vi.clearAllMocks();
    process.env.ADMIN_EMAILS = "founder@example.com";
    mockCurrentUser.mockResolvedValue({
      primaryEmailAddress: { emailAddress: "founder@example.com" },
      emailAddresses: [{ emailAddress: "founder@example.com" }],
    });
  });

  it("create intake returns url fields", async () => {
    const { POST } = await import("@/app/api/secrets/intake/route");
    dbQueue.push([]); // purge stale
    dbQueue.push([
      {
        intake_token: "ABCDEFGHJKLMNOPQRSTUVWXYZ234",
        expires_at: "2026-01-01T00:00:00.000Z",
      },
    ]);

    const req = new NextRequest("http://localhost/api/secrets/intake", {
      method: "POST",
      body: JSON.stringify({
        name: "CLERK_SECRET_KEY",
        service: "clerk",
        description: "rotate",
        expected_prefix: "sk_live_",
        expires_in_minutes: 30,
      }),
    });

    const res = await POST(req);
    expect(res.status).toBe(200);
    const json = (await res.json()) as {
      success: boolean;
      token: string;
      intake_url: string;
      expires_at: string;
    };
    expect(json.success).toBe(true);
    expect(json.token).toContain("ABCDE");
    expect(json.intake_url).toContain("/admin/secrets/intake/");
    expect(json.expires_at).toBeTruthy();
  });

  it("submit valid value then status is received", async () => {
    const { POST: submit } = await import("@/app/api/secrets/intake/[token]/submit/route");
    const intakeId = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
    const pendingRow = {
      id: intakeId,
      secret_name: "CLERK_SECRET_KEY",
      service: "clerk",
      description: "rotate",
      expected_prefix: "sk_live_",
      status: "pending",
      expires_at: new Date(Date.now() + 60_000).toISOString(),
    };

    dbQueue.push([]); // expire sweep
    dbQueue.push([pendingRow]); // select intake
    dbQueue.push([{ id: "11111111-1111-1111-1111-111111111111" }]); // upsert secret
    dbQueue.push([]); // update intake
    dbQueue.push([{ status: "received" }]); // verify

    const req = new NextRequest("http://localhost/api/secrets/intake/tok/submit", {
      method: "POST",
      body: JSON.stringify({ value: "sk_live_abc123" }),
    });

    const res = await submit(req, { params: Promise.resolve({ token: "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" }) });
    expect(res.status).toBe(200);
    const json = (await res.json()) as { success: boolean; ok?: boolean; secret_name?: string };
    expect(json.success).toBe(true);
    expect(json.ok).toBe(true);
    expect(json.secret_name).toBe("CLERK_SECRET_KEY");
  });

  it("submit with wrong prefix returns 400", async () => {
    const { POST: submit } = await import("@/app/api/secrets/intake/[token]/submit/route");
    const intakeId = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
    dbQueue.push([]);
    dbQueue.push([
      {
        id: intakeId,
        secret_name: "X",
        service: "clerk",
        description: null,
        expected_prefix: "sk_live_",
        status: "pending",
        expires_at: new Date(Date.now() + 60_000).toISOString(),
      },
    ]);

    const req = new NextRequest("http://localhost/api/x", {
      method: "POST",
      body: JSON.stringify({ value: "wrong_prefix" }),
    });
    const res = await submit(req, { params: Promise.resolve({ token: "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" }) });
    expect(res.status).toBe(400);
  });

  it("submit after expiry returns 410", async () => {
    const { POST: submit } = await import("@/app/api/secrets/intake/[token]/submit/route");
    const intakeId = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
    dbQueue.push([]);
    dbQueue.push([
      {
        id: intakeId,
        secret_name: "X",
        service: "clerk",
        description: null,
        expected_prefix: null,
        status: "pending",
        expires_at: new Date(Date.now() - 60_000).toISOString(),
      },
    ]);
    dbQueue.push([]); // mark intake expired

    const req = new NextRequest("http://localhost/api/x", {
      method: "POST",
      body: JSON.stringify({ value: "sk_live_x" }),
    });
    const res = await submit(req, { params: Promise.resolve({ token: "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" }) });
    expect(res.status).toBe(410);
  });

  it("submit twice returns 409", async () => {
    const { POST: submit } = await import("@/app/api/secrets/intake/[token]/submit/route");
    const intakeId = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
    dbQueue.push([]);
    dbQueue.push([
      {
        id: intakeId,
        secret_name: "X",
        service: "clerk",
        description: null,
        expected_prefix: null,
        status: "received",
        expires_at: new Date(Date.now() + 60_000).toISOString(),
      },
    ]);

    const req = new NextRequest("http://localhost/api/x", {
      method: "POST",
      body: JSON.stringify({ value: "anything" }),
    });
    const res = await submit(req, { params: Promise.resolve({ token: "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" }) });
    expect(res.status).toBe(409);
  });

  it("non-admin Clerk session returns 403", async () => {
    const { POST: submit } = await import("@/app/api/secrets/intake/[token]/submit/route");
    mockCurrentUser.mockResolvedValue({
      primaryEmailAddress: { emailAddress: "other@example.com" },
      emailAddresses: [{ emailAddress: "other@example.com" }],
    });

    const req = new NextRequest("http://localhost/api/x", {
      method: "POST",
      body: JSON.stringify({ value: "sk_live_x" }),
    });
    const res = await submit(req, { params: Promise.resolve({ token: "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" }) });
    expect(res.status).toBe(403);
  });
});

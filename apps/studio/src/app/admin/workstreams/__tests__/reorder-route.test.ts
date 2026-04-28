import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import { POST } from "../../../api/admin/workstreams/reorder/route";

describe("POST /api/admin/workstreams/reorder", () => {
  const fetchBackup = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = fetchBackup;
    delete process.env.NEXT_PUBLIC_WORKSTREAMS_REORDER_ENABLED;
    delete process.env.BRAIN_API_URL;
    delete process.env.BRAIN_INTERNAL_TOKEN;
  });

  it("returns 503 when feature flag is off", async () => {
    delete process.env.NEXT_PUBLIC_WORKSTREAMS_REORDER_ENABLED;

    const req = new Request("http://localhost/api/admin/workstreams/reorder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ordered_ids: ["WS-01-vercel-install-canon"] }),
    });

    const res = await POST(req);
    expect(res.status).toBe(503);
    const json = (await res.json()) as { error?: string };
    expect(json.error).toMatch(/feature flag/i);
  });

  it("proxies to Brain when flag on and env configured", async () => {
    process.env.NEXT_PUBLIC_WORKSTREAMS_REORDER_ENABLED = "true";
    process.env.BRAIN_API_URL = "https://brain.test";
    process.env.BRAIN_INTERNAL_TOKEN = "internal-token";

    global.fetch = vi.fn(async () =>
      Response.json({ queued: true }, { status: 202 }),
    );

    const req = new Request("http://localhost/api/admin/workstreams/reorder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ordered_ids: ["WS-02-a", "WS-01-b"],
      }),
    });

    const res = await POST(req);
    expect(res.status).toBe(202);
    expect(fetch).toHaveBeenCalledWith(
      "https://brain.test/api/v1/workstreams/reorder",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer internal-token",
        }),
      }),
    );
    const json = await res.json();
    expect(json).toEqual({ queued: true });
  });
});

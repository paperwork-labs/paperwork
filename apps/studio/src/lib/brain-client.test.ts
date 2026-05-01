import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { BrainClient, BrainClientError } from "./brain-client";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const FAKE_ROOT = "https://brain.test/api/v1";
const FAKE_SECRET = "test-secret-42";

function envelope<T>(data: T) {
  return { success: true, data };
}

function errorEnvelope(msg: string) {
  return { success: false, error: msg };
}

function mockFetch(body: unknown, status = 200) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("BrainClient", () => {
  let client: BrainClient;

  beforeEach(() => {
    client = new BrainClient(FAKE_ROOT, FAKE_SECRET);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ----- fromEnv ----------------------------------------------------------

  describe("fromEnv", () => {
    it("returns null when BRAIN_API_URL is not set", () => {
      delete process.env.BRAIN_API_URL;
      delete process.env.BRAIN_API_SECRET;
      expect(BrainClient.fromEnv()).toBeNull();
    });

    it("returns a BrainClient when env vars are set", () => {
      process.env.BRAIN_API_URL = "https://brain.example.com";
      process.env.BRAIN_API_SECRET = "s3cret";
      const c = BrainClient.fromEnv();
      expect(c).toBeInstanceOf(BrainClient);
      delete process.env.BRAIN_API_URL;
      delete process.env.BRAIN_API_SECRET;
    });
  });

  // ----- getOperatingScore ------------------------------------------------

  describe("getOperatingScore", () => {
    it("returns unwrapped operating score data", async () => {
      const payload = {
        overall_score: 72,
        max_score: 100,
        computed_at: "2026-04-30T00:00:00Z",
        pillars: [
          {
            pillar_id: "autonomy",
            label: "Autonomy",
            score: 8,
            max_score: 10,
            findings: [],
          },
        ],
      };
      globalThis.fetch = mockFetch(envelope(payload));

      const result = await client.getOperatingScore();

      expect(result.overall_score).toBe(72);
      expect(result.pillars).toHaveLength(1);
      expect(result.pillars[0].pillar_id).toBe("autonomy");

      expect(globalThis.fetch).toHaveBeenCalledWith(
        `${FAKE_ROOT}/admin/operating-score`,
        expect.objectContaining({
          headers: { "X-Brain-Secret": FAKE_SECRET },
        }),
      );
    });

    it("throws BrainClientError on HTTP 500", async () => {
      globalThis.fetch = mockFetch("internal error", 500);

      await expect(client.getOperatingScore()).rejects.toThrow(
        BrainClientError,
      );
    });

    it("throws BrainClientError when envelope success=false", async () => {
      globalThis.fetch = mockFetch(errorEnvelope("score not computed yet"));

      await expect(client.getOperatingScore()).rejects.toThrow(
        BrainClientError,
      );
      await expect(client.getOperatingScore()).rejects.toThrow(
        /score not computed yet/,
      );
    });
  });

  // ----- getDispatchLog ---------------------------------------------------

  describe("getDispatchLog", () => {
    it("passes limit and since as query params", async () => {
      const payload = { dispatches: [], count: 0 };
      globalThis.fetch = mockFetch(envelope(payload));

      await client.getDispatchLog(50, "2026-04-01T00:00:00Z");

      const calledUrl = (globalThis.fetch as ReturnType<typeof vi.fn>).mock
        .calls[0][0] as string;
      expect(calledUrl).toContain("limit=50");
      expect(calledUrl).toContain("since=2026-04-01T00%3A00%3A00Z");
    });

    it("returns dispatch entries", async () => {
      const payload = {
        dispatches: [
          { dispatched_at: "2026-04-30T12:00:00Z", persona_slug: "engineering" },
        ],
        count: 1,
      };
      globalThis.fetch = mockFetch(envelope(payload));

      const result = await client.getDispatchLog();
      expect(result.dispatches).toHaveLength(1);
      expect(result.count).toBe(1);
    });
  });

  // ----- getProbeResults --------------------------------------------------

  describe("getProbeResults", () => {
    it("calls probes/health with product filter", async () => {
      const payload = { results: [], checked_at: null };
      globalThis.fetch = mockFetch(envelope(payload));

      await client.getProbeResults("filefree");

      const calledUrl = (globalThis.fetch as ReturnType<typeof vi.fn>).mock
        .calls[0][0] as string;
      expect(calledUrl).toContain("/probes/health");
      expect(calledUrl).toContain("product=filefree");
    });

    it("returns probe rows", async () => {
      const payload = {
        results: [
          { cuj_id: "login", name: "Login flow", status: "pass", last_run_at: null },
        ],
        checked_at: "2026-04-30T10:00:00Z",
      };
      globalThis.fetch = mockFetch(envelope(payload));

      const result = await client.getProbeResults();
      expect(result.results).toHaveLength(1);
      expect(result.results[0].status).toBe("pass");
    });
  });

  // ----- getPersonas ------------------------------------------------------

  describe("getPersonas", () => {
    it("returns persona specs", async () => {
      const payload = {
        personas: [
          {
            persona_id: "engineering",
            name: "Staff Engineer",
            description: "Tech lead",
            model: "claude-sonnet-4-20250514",
            routing_active: true,
          },
        ],
      };
      globalThis.fetch = mockFetch(envelope(payload));

      const result = await client.getPersonas();
      expect(result.personas).toHaveLength(1);
      expect(result.personas[0].persona_id).toBe("engineering");
    });
  });

  // ----- Network errors ---------------------------------------------------

  describe("network errors", () => {
    it("wraps fetch failures as BrainClientError with status 0", async () => {
      globalThis.fetch = vi
        .fn()
        .mockRejectedValue(new Error("ECONNREFUSED"));

      const err = await client
        .getOperatingScore()
        .catch((e: unknown) => e as BrainClientError);
      expect(err).toBeInstanceOf(BrainClientError);
      expect(err.status).toBe(0);
      expect(err.message).toContain("ECONNREFUSED");
    });
  });

  // ----- Invalid JSON -----------------------------------------------------

  describe("invalid JSON", () => {
    it("throws BrainClientError for unparseable response body", async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: () => Promise.reject(new SyntaxError("Unexpected token")),
        text: () => Promise.resolve("not json"),
      });

      await expect(client.getPersonas()).rejects.toThrow(BrainClientError);
      await expect(
        client.getPersonas().catch((e: BrainClientError) => e.message),
      ).resolves.toContain("invalid JSON");
    });
  });
});

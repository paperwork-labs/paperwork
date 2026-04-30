import { afterEach, describe, expect, it, vi } from "vitest";

import { captureError, initObservability } from "../src/index";

async function flushMicrotasks(): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0));
}

describe("@paperwork/observability", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("posts captured errors to Brain with the configured auth token", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, statusText: "OK" });
    vi.stubGlobal("fetch", fetchMock);

    initObservability({
      product: "studio",
      brainUrl: "https://brain.test/",
      brainToken: "test-token",
      env: "production",
    });
    captureError(new Error("boom"), {
      context: { route: "/admin" },
      user: { id: "user_1" },
    });
    await flushMicrotasks();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      "https://brain.test/v1/errors/ingest",
      expect.objectContaining({
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer test-token",
        },
      }),
    );
    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body).toMatchObject({
      product: "studio",
      env: "production",
      message: "boom",
      severity: "error",
      context: {
        route: "/admin",
        user: { id: "user_1" },
      },
    });
    expect(body.stack).toContain("boom");
  });

  it("maps development captures to preview before posting", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, statusText: "OK" });
    vi.stubGlobal("fetch", fetchMock);

    initObservability({
      product: "studio",
      brainUrl: "https://brain.test",
      brainToken: "test-token",
      env: "development",
    });
    captureError("string failure");
    await flushMicrotasks();

    const body = JSON.parse(fetchMock.mock.calls[0][1].body);
    expect(body.env).toBe("preview");
    expect(body.message).toBe("string failure");
  });

  it("logs capture transport failures without throwing", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error("network down"));
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    vi.stubGlobal("fetch", fetchMock);

    initObservability({
      product: "studio",
      brainUrl: "https://brain.test",
      brainToken: "test-token",
      env: "preview",
    });

    expect(() => captureError("safe failure")).not.toThrow();
    await flushMicrotasks();
    expect(consoleError).toHaveBeenCalledWith(
      "@paperwork/observability failed to capture error.",
      expect.any(Error),
    );
  });
});

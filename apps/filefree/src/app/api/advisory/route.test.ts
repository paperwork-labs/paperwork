import { beforeEach, describe, expect, it, vi } from "vitest";

const { generateTextMock, openaiMock } = vi.hoisted(() => ({
  generateTextMock: vi.fn(),
  openaiMock: vi.fn(() => "mock-model"),
}));

vi.mock("ai", () => ({
  generateText: generateTextMock,
}));

vi.mock("@ai-sdk/openai", () => ({
  openai: openaiMock,
}));

import { POST } from "./route";

async function callPost(prompt?: string, cookie = "session=test") {
  return POST(
    new Request("http://localhost/api/advisory", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        cookie,
      },
      body: JSON.stringify({ prompt }),
    })
  );
}

describe("advisory route", () => {
  beforeEach(() => {
    generateTextMock.mockReset();
    openaiMock.mockClear();
    process.env.OPENAI_API_KEY = "test-key";
    (process.env as Record<string, string>).NODE_ENV = "test";
  });

  it("returns 401 when session cookie is missing", async () => {
    (process.env as Record<string, string>).NODE_ENV = "production";
    const response = await callPost("hello", "");
    expect(response.status).toBe(401);
  });

  it("returns 400 for missing prompt", async () => {
    const response = await callPost("");
    expect(response.status).toBe(400);
    const body = await response.json();
    expect(body.error).toContain("Prompt is required");
  });

  it("returns 503 when OPENAI_API_KEY is missing", async () => {
    delete process.env.OPENAI_API_KEY;
    const response = await callPost("hello");
    expect(response.status).toBe(503);
  });

  it("returns 429 when provider quota is exceeded", async () => {
    generateTextMock.mockRejectedValueOnce(new Error("insufficient_quota"));
    const response = await callPost("hello");
    expect(response.status).toBe(429);
  });

  it("returns 500 generic message for unexpected errors", async () => {
    generateTextMock.mockRejectedValueOnce(new Error("provider blew up"));
    const response = await callPost("hello");
    expect(response.status).toBe(500);
    const body = await response.json();
    expect(body.error).toBe(
      "Advisory is temporarily unavailable. Please try again shortly."
    );
  });

  it("returns 200 with advisory text on success", async () => {
    generateTextMock.mockResolvedValueOnce({ text: "Use standard deduction." });
    const response = await callPost("How should I handle this?");
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.success).toBe(true);
    expect(body.data.text).toBe("Use standard deduction.");
  });
});

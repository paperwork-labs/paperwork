import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  computeFreshness,
  computeReadTime,
  docKindToHubCategory,
} from "./doc-metadata";

describe("computeReadTime", () => {
  it("returns 0 when there are no words", () => {
    expect(computeReadTime(0)).toBe(0);
    expect(computeReadTime(-1)).toBe(0);
  });

  it("uses 200 wpm and rounds up", () => {
    expect(computeReadTime(1)).toBe(1);
    expect(computeReadTime(200)).toBe(1);
    expect(computeReadTime(201)).toBe(2);
    expect(computeReadTime(400)).toBe(2);
  });
});

describe("computeFreshness", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-01T12:00:00.000Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns unknown when lastReviewed is missing or blank", () => {
    expect(computeFreshness(null)).toBe("unknown");
    expect(computeFreshness("")).toBe("unknown");
    expect(computeFreshness("   ")).toBe("unknown");
  });

  it("returns unknown for invalid dates", () => {
    expect(computeFreshness("nope")).toBe("unknown");
  });

  it("returns fresh when under 60 days", () => {
    expect(computeFreshness("2026-04-03")).toBe("fresh");
    expect(computeFreshness("2026-05-10")).toBe("fresh");
  });

  it("returns aging at 60 days through 180 days", () => {
    expect(computeFreshness("2026-04-02")).toBe("aging");
    expect(computeFreshness("2026-03-01")).toBe("aging");
    expect(computeFreshness("2025-12-15")).toBe("aging");
  });

  it("returns stale beyond 180 days", () => {
    expect(computeFreshness("2025-09-01")).toBe("stale");
  });
});

describe("docKindToHubCategory", () => {
  it("maps known kinds and triages the rest", () => {
    expect(docKindToHubCategory(null)).toBe("uncategorized");
    expect(docKindToHubCategory("")).toBe("uncategorized");
    expect(docKindToHubCategory("philosophy")).toBe("philosophy");
    expect(docKindToHubCategory("architecture")).toBe("architecture");
    expect(docKindToHubCategory("plan")).toBe("strategy");
    expect(docKindToHubCategory("sprint")).toBe("strategy");
    expect(docKindToHubCategory("runbook")).toBe("runbook");
    expect(docKindToHubCategory("template")).toBe("playbook");
    expect(docKindToHubCategory("decision")).toBe("decision-log");
    expect(docKindToHubCategory("reference")).toBe("uncategorized");
  });
});

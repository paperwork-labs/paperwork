/**
 * StatusTracker must stay aligned with `can_transition` in
 * apis/launchfree/app/routes/filing_status.py.
 */

import { describe, it, expect } from "vitest";
import { StatusTracker, type FilingStatus } from "../status/tracker.js";

const ALL_STATUSES: FilingStatus[] = [
  "draft",
  "pending_payment",
  "payment_complete",
  "submitting",
  "submitted",
  "processing",
  "confirmed",
  "failed",
  "requires_manual",
];

/**
 * Mirror `can_transition` in apis/launchfree/app/routes/filing_status.py.
 * Update both when changing the state machine.
 */
function pythonMirrorCanTransition(from: string, to: string): boolean {
  const STATUS_ALIASES: Record<string, string> = { documents_ready: "draft" };
  const TERMINAL = new Set(["confirmed"]);
  const ALLOWED: Record<string, ReadonlySet<string>> = {
    draft: new Set([
      "pending_payment",
      "submitting",
      "failed",
      "requires_manual",
    ]),
    pending_payment: new Set(["payment_complete", "failed", "draft"]),
    payment_complete: new Set(["submitting", "failed", "requires_manual"]),
    submitting: new Set(["submitted", "failed", "requires_manual"]),
    submitted: new Set([
      "processing",
      "confirmed",
      "failed",
      "requires_manual",
    ]),
    processing: new Set(["confirmed", "failed", "requires_manual"]),
    confirmed: new Set(),
    failed: new Set(["draft", "pending_payment"]),
    requires_manual: new Set(["draft", "confirmed", "failed"]),
  };

  if (from === to) {
    return false;
  }
  const fromEffective = STATUS_ALIASES[from] ?? from;
  if (TERMINAL.has(fromEffective)) {
    return false;
  }
  const allowed = ALLOWED[fromEffective];
  if (!allowed) {
    return false;
  }
  return allowed.has(to);
}

describe("StatusTracker", () => {
  it("matches Python can_transition for every canonical pair", () => {
    for (const from of ALL_STATUSES) {
      for (const to of ALL_STATUSES) {
        expect(
          StatusTracker.canTransition(from, to),
          `${from} -> ${to}`,
        ).toBe(pythonMirrorCanTransition(from, to));
      }
    }
  });

  it("Python alias documents_ready behaves like draft for outbound transitions", () => {
    for (const to of ALL_STATUSES) {
      expect(pythonMirrorCanTransition("documents_ready", to)).toBe(
        pythonMirrorCanTransition("draft", to),
      );
    }
  });

  it("allows valid transitions via transition()", () => {
    const t = new StatusTracker("1");
    expect(t.getStatus()).toBe("draft");
    t.transition("pending_payment");
    expect(t.getStatus()).toBe("pending_payment");
    t.transition("payment_complete");
    t.transition("submitting");
    t.transition("submitted");
    t.transition("confirmed");
    expect(t.getStatus()).toBe("confirmed");
  });

  it("throws on invalid transitions", () => {
    const t = new StatusTracker("1");
    expect(() => t.transition("payment_complete")).toThrow(
      /Invalid filing status transition/,
    );
  });

  it("throws when transitioning from terminal confirmed", () => {
    const t = new StatusTracker("1", { currentStatus: "confirmed" });
    expect(() => t.transition("failed")).toThrow(
      /Invalid filing status transition/,
    );
  });

  it("rejects same-status transitions", () => {
    expect(StatusTracker.canTransition("draft", "draft")).toBe(false);
    const t = new StatusTracker("1");
    expect(() => t.transition("draft")).toThrow(/Invalid filing status transition/);
  });
});

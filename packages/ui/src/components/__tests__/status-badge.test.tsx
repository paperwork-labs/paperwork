import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import { StatusBadge, type StatusTone } from "../status-badge";

const ALL_TONES: StatusTone[] = [
  "urgency-critical",
  "urgency-high",
  "urgency-normal",
  "urgency-info",
  "expense-pending",
  "expense-approved",
  "expense-reimbursed",
  "expense-flagged",
  "expense-rejected",
  "audit-finding-error",
  "audit-finding-warn",
  "audit-finding-info",
  "strategy-active",
  "strategy-paused",
  "strategy-draft",
  "strategy-stopped",
  "strategy-archived",
];

describe("StatusBadge", () => {
  it.each(ALL_TONES)("renders tone %s", (tone) => {
    const { getByRole } = render(<StatusBadge tone={tone}>{tone}</StatusBadge>);
    expect(getByRole("status")).toHaveTextContent(tone);
  });

  it("applies custom className", () => {
    const { getByRole } = render(
      <StatusBadge tone="strategy-draft" className="extra-class">
        draft
      </StatusBadge>,
    );
    expect(getByRole("status")).toHaveClass("extra-class");
  });
});

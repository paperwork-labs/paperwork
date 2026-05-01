import { describe, expect, it } from "vitest";
import type { ParsedInboundEmail } from "../types.js";
import { emailBodyText, extractDueDate } from "../parser.js";

function minimalEmail(overrides: Partial<ParsedInboundEmail>): ParsedInboundEmail {
  return {
    messageId: "m",
    threadId: "t",
    from: { address: "x@y.com" },
    to: [],
    subject: "",
    date: new Date(0),
    attachments: [],
    rawHeaders: {},
    ...overrides,
  };
}

describe("parser resilience (no client graph)", () => {
  it("emailBodyText handles long `<` runs without throwing", () => {
    const junk = "<".repeat(60_000);
    const text = emailBodyText(minimalEmail({ html: junk }));
    expect(text.length).toBe(60_000);
  });

  it("extractDueDate returns undefined on whitespace-only tail after due", () => {
    expect(extractDueDate(`due${" ".repeat(80_000)}`)).toBeUndefined();
  });

  it("extractDueDate still parses common due date phrasings", () => {
    expect(extractDueDate("Due Date: 01/15/2026")?.getFullYear()).toBe(2026);
    expect(extractDueDate("due 01/15/2026")?.getMonth()).toBe(0);
    expect(extractDueDate("Due Date:\nJanuary 15, 2026")).toBeDefined();
  });
});

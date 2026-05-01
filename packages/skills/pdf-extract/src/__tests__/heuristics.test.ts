import { describe, expect, it } from "vitest";
import { classifyAsInvoice } from "../heuristics";

const doc = (text: string) => ({
  format: "pdf" as const,
  text,
});

describe("classifyAsInvoice heuristics", () => {
  it("extracts due, total, invoice #, issue date on a normal block", () => {
    const text = [
      "Bill From   Acme Corp",
      "",
      "Invoice INV-009",
      "",
      "Invoice Date: 2026-01-05",
      "",
      "Due: 2026-02-01",
      "",
      "Total $123.45",
    ].join("\n");

    const c = classifyAsInvoice(doc(text));
    expect(c.vendor).toContain("Acme");
    expect(c.invoiceNumber).toMatch(/INV-009/i);
    expect(c.amount?.value).toBe(123.45);
    expect(c.issueDate?.getUTCFullYear()).toBe(2026);
    expect(c.dueDate?.getUTCMonth()).toBe(1);
    expect(c.confidence).toBeGreaterThan(0);
  });

  it("completes on pathological whitespace without throwing", () => {
    const gap = " ".repeat(80_000);
    const text = `due${gap}invoice date:${gap}2026-03-01${gap}total${gap}$10.00`;
    const c = classifyAsInvoice(doc(text));
    expect(c).toBeDefined();
    // Bounded spacing skips absurd same-line gaps; regression is hang-free completion.
    expect(Number.isFinite(c.confidence)).toBe(true);
  });
});

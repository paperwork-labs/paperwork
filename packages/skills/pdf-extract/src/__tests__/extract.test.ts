import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { extractImage, extractPdf, classifyAsInvoice } from "../index";
import type { ExtractedDocument } from "../types";

const here = dirname(fileURLToPath(import.meta.url));
const fixturePdf = readFileSync(
  join(here, "__fixtures__/sample-invoice.pdf"),
);

describe("extractPdf", () => {
  it("returns text and page count from fixture PDF", async () => {
    const doc = await extractPdf(fixturePdf);
    expect(doc.format).toBe("pdf");
    expect(doc.pageCount).toBeGreaterThanOrEqual(1);
    expect(doc.text.trim().length).toBeGreaterThan(0);
    expect(doc.pages?.length).toBeGreaterThanOrEqual(1);
  });
});

describe("extractImage", () => {
  it("throws a clear message until OCR is supported", async () => {
    await expect(
      extractImage(Buffer.from("fake"), "image/png"),
    ).rejects.toThrow(/OCR not yet supported/);
  });
});

describe("classifyAsInvoice", () => {
  const sampleBody = `
Bill from: Acme Supplies LLC

Invoice #: INV-2024-001

Total: $199.50

Payment due: 2026-03-15
`;

  function docFromText(text: string): ExtractedDocument {
    return { format: "unknown", text };
  }

  it("extracts vendor, invoice number, amount, and due date", () => {
    const c = classifyAsInvoice(docFromText(sampleBody));
    expect(c.vendor).toContain("Acme");
    expect(c.invoiceNumber).toBe("INV-2024-001");
    expect(c.amount).toEqual({ value: 199.5, currency: "USD" });
    expect(c.dueDate?.toISOString().slice(0, 10)).toBe("2026-03-15");
    expect(c.confidence).toBe(1);
  });

  it("computes confidence from detected fields (of four)", () => {
    const partial = classifyAsInvoice(
      docFromText("Bill from: Solo Vendor\nInvoice #: SOLO-1\n"),
    );
    expect(partial.vendor).toContain("Solo Vendor");
    expect(partial.invoiceNumber).toBe("SOLO-1");
    expect(partial.amount).toBeUndefined();
    expect(partial.dueDate).toBeUndefined();
    expect(partial.confidence).toBe(0.5);
  });

  it("finishes on large noisy bodies without polynomial-regex slowdown", () => {
    const noise = `${"A".repeat(99_900)}\nBill from: Co\nInvoice #: OK\n`;
    const c = classifyAsInvoice(docFromText(noise));
    expect(c.vendor).toContain("Co");
    expect(c.invoiceNumber).toBe("OK");
  });

  it("finishes when lines contain huge TAB runs near invoice markers", () => {
    const tabs = "\t".repeat(60_000);
    const body = `due${tabs}\ntotal${tabs}$50\nBill from: Q\nInvoice #: I\n`;
    const c = classifyAsInvoice(docFromText(body));
    expect(c.vendor).toContain("Q");
    expect(c.invoiceNumber).toBe("I");
    expect(c.amount).toEqual({ value: 50, currency: "USD" });
  });
});

import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { GmailInboundClient } from "../client.js";
import {
  buildInvoiceSignals,
  extractAmount,
  extractDueDate,
  parseRawMime,
} from "../parser.js";

const dir = path.dirname(fileURLToPath(import.meta.url));

describe("mailparser fixtures", () => {
  it("extracts PDF attachment with filename, content type, and size", async () => {
    const raw = readFileSync(path.join(dir, "__fixtures__", "sample-invoice.eml"));
    const email = await parseRawMime("gmail-msg-1", "gmail-thread-1", raw);
    const pdf = email.attachments.find((a) => a.filename === "invoice.pdf");
    expect(pdf).toBeDefined();
    expect(pdf!.contentType).toMatch(/pdf/i);
    expect(pdf!.size).toBeGreaterThan(0);
    expect(pdf!.content.length).toBe(pdf!.size);
    expect(pdf!.content.subarray(0, 5).toString()).toBe("%PDF-");
  });

  it("extracts subject, from, and to", async () => {
    const raw = readFileSync(path.join(dir, "__fixtures__", "sample-invoice.eml"));
    const email = await parseRawMime("m", "t", raw);
    expect(email.subject).toContain("Invoice");
    expect(email.from.address).toBe("vendor@example.com");
    expect(email.from.name).toMatch(/Acme/);
    expect(email.to.some((x) => x.address === "billing@paperworklabs.com")).toBe(true);
  });

  it("detects invoice heuristics, vendor domain, amount, and due date", async () => {
    const raw = readFileSync(path.join(dir, "__fixtures__", "sample-invoice.eml"));
    const email = await parseRawMime("m", "t", raw);
    const signals = buildInvoiceSignals(email, { knownVendorDomains: ["example.com"] });
    expect(signals.looksLikeInvoice).toBe(true);
    expect(signals.fromKnownVendor).toBe("example.com");
    expect(signals.detectedAmount).toEqual({ value: 1234.56, currency: "USD" });
    expect(signals.detectedDueDate).toBeDefined();
    expect(signals.detectedDueDate!.getFullYear()).toBe(2026);
    expect(signals.detectedDueDate!.getMonth()).toBe(0);
    expect(signals.detectedDueDate!.getDate()).toBe(15);
  });

  it("classifyAsInvoice matches parser signals via client config", async () => {
    const raw = readFileSync(path.join(dir, "__fixtures__", "sample-invoice.eml"));
    const email = await parseRawMime("mid", "tid", raw);
    const client = new GmailInboundClient({
      clientId: "test",
      clientSecret: "test",
      redirectUri: "http://localhost/oauth",
      knownVendorDomains: ["example.com"],
    });
    const candidate = client.classifyAsInvoice(email);
    expect(candidate.signals.looksLikeInvoice).toBe(true);
    expect(candidate.signals.detectedAmount?.value).toBe(1234.56);
  });
});

describe("amount and date extraction", () => {
  it("parses USD-prefixed amounts", () => {
    expect(extractAmount("Total USD 1234.56 today")).toEqual({
      value: 1234.56,
      currency: "USD",
    });
  });

  it("parses ISO due dates in body", () => {
    const d = extractDueDate("Please pay by 2026-03-01");
    expect(d).toBeDefined();
    expect(d!.toISOString().startsWith("2026-03-01")).toBe(true);
  });
});

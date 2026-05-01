import { simpleParser } from "mailparser";
import type { AddressObject } from "mailparser";
import type {
  InboundCandidate,
  ParsedAttachment,
  ParsedInboundEmail,
} from "./types.js";

function flattenAddresses(addr: AddressObject | AddressObject[] | undefined): {
  name?: string;
  address: string;
}[] {
  if (!addr) return [];
  const list = Array.isArray(addr) ? addr : [addr];
  const out: { name?: string; address: string }[] = [];
  for (const a of list) {
    for (const v of a.value ?? []) {
      const address = v.address?.trim();
      if (address) {
        out.push({
          name: v.name?.trim() || undefined,
          address,
        });
      }
    }
  }
  return out;
}

function headersToRecord(
  headers: ParsedMailHeadersLike
): Record<string, string> {
  const rawHeaders: Record<string, string> = {};
  if (!headers || typeof headers.forEach !== "function") {
    return rawHeaders;
  }
  headers.forEach((value, key) => {
    if (value === undefined || value === null) return;
    if (typeof value === "string") {
      rawHeaders[key] = value;
      return;
    }
    if (typeof value === "object" && "value" in value && value.value !== undefined) {
      rawHeaders[key] = String(value.value);
      return;
    }
    rawHeaders[key] = String(value);
  });
  return rawHeaders;
}

type ParsedMailHeadersLike = {
  forEach(
    cb: (value: unknown, key: string) => void
  ): void;
};

export async function parseRawMime(
  messageId: string,
  threadId: string,
  raw: Buffer | string
): Promise<ParsedInboundEmail> {
  const parsed = await simpleParser(raw);
  const fromList = flattenAddresses(parsed.from);
  const from =
    fromList[0] ??
    ({
      address: "unknown@invalid",
    } as ParsedInboundEmail["from"]);

  const attachments: ParsedAttachment[] = (parsed.attachments ?? []).map(
    (a) => ({
      filename: a.filename?.trim() || "attachment",
      contentType: a.contentType?.split(";")[0]?.trim() || "application/octet-stream",
      size: a.size ?? (Buffer.isBuffer(a.content) ? a.content.length : 0),
      content: Buffer.isBuffer(a.content) ? a.content : Buffer.from(a.content ?? []),
    })
  );

  const date =
    parsed.date instanceof Date && !Number.isNaN(parsed.date.getTime())
      ? parsed.date
      : new Date();

  return {
    messageId,
    threadId,
    from,
    to: flattenAddresses(parsed.to),
    subject: parsed.subject?.trim() ?? "",
    date,
    text: parsed.text?.trim() || undefined,
    html: typeof parsed.html === "string" ? parsed.html : undefined,
    attachments,
    rawHeaders: headersToRecord(parsed.headers as ParsedMailHeadersLike),
  };
}

export function decodeGmailRawBase64(raw: string): Buffer {
  const b64 = raw.replace(/-/g, "+").replace(/_/g, "/");
  return Buffer.from(b64, "base64");
}

const INVOICE_KEYWORD_RE = /\b(invoice|receipt|bill)\b/i;

export function emailBodyText(email: ParsedInboundEmail): string {
  const chunks: string[] = [];
  if (email.text) chunks.push(email.text);
  if (email.html) {
    chunks.push(email.html.replace(/<[^>]+>/g, " "));
  }
  return chunks.join("\n").replace(/\s+/g, " ").trim();
}

export function hasPdfAttachment(email: ParsedInboundEmail): boolean {
  return email.attachments.some(
    (a) =>
      a.contentType.toLowerCase().includes("pdf") ||
      a.filename.toLowerCase().endsWith(".pdf")
  );
}

export function extractAmount(text: string): { value: number; currency: string } | undefined {
  const dollar = text.match(/\$\s*([\d,]+(?:\.\d{1,2})?)/);
  if (dollar) {
    const value = Number.parseFloat(dollar[1]!.replace(/,/g, ""));
    if (!Number.isNaN(value)) {
      return { value, currency: "USD" };
    }
  }

  const usd = text.match(/USD\s*([\d,]+(?:\.\d{1,2})?)/i);
  if (usd) {
    const value = Number.parseFloat(usd[1]!.replace(/,/g, ""));
    if (!Number.isNaN(value)) {
      return { value, currency: "USD" };
    }
  }

  return undefined;
}

function parseDateCandidate(raw: string): Date | undefined {
  const trimmed = raw.trim();
  const iso = trimmed.match(/^(\d{4}-\d{2}-\d{2})/);
  if (iso) {
    const d = new Date(`${iso[1]}T12:00:00.000Z`);
    if (!Number.isNaN(d.getTime())) return d;
  }

  const mdy = trimmed.match(/^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$/);
  if (mdy) {
    const m = Number.parseInt(mdy[1]!, 10);
    const day = Number.parseInt(mdy[2]!, 10);
    const y = Number.parseInt(mdy[3]!, 10);
    const d = new Date(y, m - 1, day);
    if (!Number.isNaN(d.getTime())) return d;
  }

  const tried = new Date(trimmed);
  if (!Number.isNaN(tried.getTime())) return tried;

  return undefined;
}

export function extractDueDate(text: string): Date | undefined {
  const dueLabeled = text.match(
    /due(?:\s*date)?[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})/i
  );
  if (dueLabeled?.[1]) {
    const d = parseDateCandidate(dueLabeled[1]);
    if (d) return d;
  }

  const iso = text.match(/\b(\d{4}-\d{2}-\d{2})\b/);
  if (iso?.[1]) {
    const d = parseDateCandidate(iso[1]);
    if (d) return d;
  }

  return undefined;
}

export function matchKnownVendor(
  fromAddress: string,
  domains: string[] | undefined
): string | undefined {
  if (!domains?.length) return undefined;
  const at = fromAddress.lastIndexOf("@");
  if (at < 0) return undefined;
  const host = fromAddress.slice(at + 1).toLowerCase();
  for (const d of domains) {
    const dom = d.toLowerCase().replace(/^@/, "");
    if (host === dom || host.endsWith(`.${dom}`)) {
      return dom;
    }
  }
  return undefined;
}

export function buildInvoiceSignals(
  email: ParsedInboundEmail,
  opts?: { knownVendorDomains?: string[] }
): InboundCandidate["signals"] {
  const body = emailBodyText(email);
  const keywordHit = INVOICE_KEYWORD_RE.test(body);
  const pdf = hasPdfAttachment(email);

  return {
    looksLikeInvoice: pdf && keywordHit,
    fromKnownVendor: matchKnownVendor(
      email.from.address,
      opts?.knownVendorDomains
    ),
    detectedAmount: extractAmount(body),
    detectedDueDate: extractDueDate(body),
  };
}

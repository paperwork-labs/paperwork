import type { ExtractedDocument, InvoiceCandidate } from "./types";

const MONTH_NAMES = [
  "january",
  "february",
  "march",
  "april",
  "may",
  "june",
  "july",
  "august",
  "september",
  "october",
  "november",
  "december",
] as const;

const MONTH_ABBR = [
  "jan",
  "feb",
  "mar",
  "apr",
  "may",
  "jun",
  "jul",
  "aug",
  "sep",
  "sept",
  "oct",
  "nov",
  "dec",
] as const;

function monthIndex(token: string): number | undefined {
  const t = token.toLowerCase();
  const long = MONTH_NAMES.indexOf(t as (typeof MONTH_NAMES)[number]);
  if (long >= 0) return long;
  const short = MONTH_ABBR.indexOf(t as (typeof MONTH_ABBR)[number]);
  if (short >= 0) return short;
  return undefined;
}

function parseNumericDate(y: string, m: string, d: string): Date | undefined {
  const year = Number(y.length === 2 ? `20${y}` : y);
  const month = Number(m) - 1;
  const day = Number(d);
  if (
    !Number.isFinite(year) ||
    !Number.isFinite(month) ||
    !Number.isFinite(day) ||
    month < 0 ||
    month > 11
  ) {
    return undefined;
  }
  const dt = new Date(Date.UTC(year, month, day));
  if (Number.isNaN(dt.getTime())) return undefined;
  return dt;
}

/** Tries common numeric and short month patterns anywhere in a chunk of text. */
function parseDateFromChunk(chunk: string): Date | undefined {
  const trimmed = chunk.trim();

  const iso = trimmed.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$/);
  if (iso) {
    const d = parseNumericDate(iso[1]!, iso[2]!, iso[3]!);
    if (d) return d;
  }

  const dmy = trimmed.match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})$/);
  if (dmy) {
    const d = parseNumericDate(dmy[3]!, dmy[1]!, dmy[2]!);
    if (d) return d;
  }

  const monthFirst = trimmed.match(
    /^([A-Za-z]{3,12})[ \t]+(\d{1,2}),?[ \t]+(\d{4})$/,
  );
  if (monthFirst) {
    const mi = monthIndex(monthFirst[1]!);
    if (mi === undefined) return undefined;
    const day = Number(monthFirst[2]);
    const year = Number(monthFirst[3]);
    if (!Number.isFinite(day) || !Number.isFinite(year)) return undefined;
    const dt = new Date(Date.UTC(year, mi, day));
    return Number.isNaN(dt.getTime()) ? undefined : dt;
  }

  const dayFirst = trimmed.match(
    /^(\d{1,2})[ \t]+([A-Za-z]{3,12}),?[ \t]+(\d{4})$/,
  );
  if (dayFirst) {
    const mi = monthIndex(dayFirst[2]!);
    if (mi === undefined) return undefined;
    const day = Number(dayFirst[1]);
    const year = Number(dayFirst[3]);
    if (!Number.isFinite(day) || !Number.isFinite(year)) return undefined;
    const dt = new Date(Date.UTC(year, mi, day));
    return Number.isNaN(dt.getTime()) ? undefined : dt;
  }

  return undefined;
}

/** Bounded whitespace avoids polynomial backtracking on long TAB runs (CodeQL js/polynomial-redos). */
const DUE_LINE_RE =
  /^[ \t]{0,96}(?:due|payment[ \t]{1,96}due|due[ \t]{1,96}by)[ \t]{0,96}[:.]?[ \t]{0,96}([^\r\n]{1,512})$/gim;

function extractDueDate(text: string): Date | undefined {
  let best: Date | undefined;
  DUE_LINE_RE.lastIndex = 0;
  for (const m of text.matchAll(DUE_LINE_RE)) {
    const rest = m[1]?.trim() ?? "";
    const isoInline = rest.match(
      /(\d{1,4}[-/]\d{1,2}[-/]\d{1,4}|[A-Za-z]{3,12}[ \t]{1,96}\d{1,2},?[ \t]{1,96}\d{4}|\d{1,2}[ \t]{1,96}[A-Za-z]{3,12},?[ \t]{1,96}\d{4})/,
    );
    const chunk = isoInline?.[0] ?? rest;
    const d = parseDateFromChunk(chunk);
    if (d && (!best || d.getTime() > best.getTime())) best = d;
  }
  return best;
}

const INVOICE_NO_RE =
  /\b(?:invoice|inv)[ \t]{0,96}#?[ \t]{0,96}[:.]?[ \t]{0,96}([A-Z0-9-]{1,48})\b/gi;

function extractInvoiceNumber(text: string): string | undefined {
  INVOICE_NO_RE.lastIndex = 0;
  for (const m of text.matchAll(INVOICE_NO_RE)) {
    const id = m[1]?.trim();
    if (id) return id;
  }
  return undefined;
}

const BILL_FROM_RE =
  /bill[ \t]{1,96}from[ \t]{0,96}[:.]?[ \t]{0,96}([^\n]{1,400})/i;

function extractVendor(text: string): string | undefined {
  const bill = text.match(BILL_FROM_RE);
  if (bill?.[1]) return bill[1].trim();

  const lines = text.split(/\r?\n/).map((l) => l.trim());
  for (const line of lines) {
    if (!line) continue;
    if (/^(invoice|inv)\b/i.test(line)) continue;
    if (line.length > 120) continue;
    return line;
  }
  return undefined;
}

function parseMoneyAmount(raw: string): number {
  return Number.parseFloat(raw.replace(/,/g, ""));
}

type MoneyHit = { value: number; currency: string; score: number };

function scoreLineForTotal(line: string): number {
  const lower = line.toLowerCase();
  if (/total|amount[ \t]{0,96}due|balance[ \t]{0,96}due/.test(lower))
    return 3;
  if (/subtotal/.test(lower)) return 1;
  return 0;
}

function collectMoneyHits(text: string): MoneyHit[] {
  const hits: MoneyHit[] = [];
  const lines = text.split(/\r?\n/);

  for (const line of lines) {
    const ls = scoreLineForTotal(line);

    for (const m of line.matchAll(
      /\$[ \t]{0,96}(\d+(?:,\d{3})*(?:\.\d{1,2})?)/g,
    )) {
      const value = parseMoneyAmount(m[1]!);
      if (Number.isFinite(value)) {
        hits.push({ value, currency: "USD", score: ls + 1 });
      }
    }

    for (const m of line.matchAll(
      /USD[ \t]{0,96}(\d+(?:,\d{3})*(?:\.\d{1,2})?)/gi,
    )) {
      const value = parseMoneyAmount(m[1]!);
      if (Number.isFinite(value)) {
        hits.push({ value, currency: "USD", score: ls + 1 });
      }
    }

    for (const m of line.matchAll(
      /(?:total|amount[ \t]{0,96}due|balance[ \t]{0,96}due)[ \t]{0,96}[:.]?[ \t]{0,96}\$?[ \t]{0,96}(\d+(?:,\d{3})*(?:\.\d{1,2})?)/gi,
    )) {
      const value = parseMoneyAmount(m[1]!);
      if (Number.isFinite(value)) {
        hits.push({ value, currency: "USD", score: ls + 2 });
      }
    }
  }

  return hits;
}

function extractPrimaryAmount(text: string): { value: number; currency: string } | undefined {
  const hits = collectMoneyHits(text);
  if (!hits.length) return undefined;

  const highScore = hits.filter((h) => h.score >= 3);
  const pick = highScore.length
    ? highScore.reduce((a, b) => (a.value >= b.value ? a : b))
    : hits.reduce((a, b) => (a.value >= b.value ? a : b));

  return { value: pick.value, currency: pick.currency };
}

const ISSUE_DATE_RE =
  /\b(?:invoice[ \t]{0,96}date|date[ \t]{0,96}issued|issued[ \t]{0,96}on)[ \t]{0,96}[:.]?[ \t]{0,96}(\d{1,4}[-/]\d{1,2}[-/]\d{1,4}|[A-Za-z]{3,12}[ \t]{1,96}\d{1,2},?[ \t]{1,96}\d{4}|\d{1,2}[ \t]{1,96}[A-Za-z]{3,12},?[ \t]{1,96}\d{4})/i;

function extractIssueDate(text: string): Date | undefined {
  const m = text.match(ISSUE_DATE_RE);
  if (!m?.[1]) return undefined;
  return parseDateFromChunk(m[1].trim());
}

export function classifyAsInvoice(doc: ExtractedDocument): InvoiceCandidate {
  const text = doc.text ?? "";
  const vendor = extractVendor(text);
  const invoiceNumber = extractInvoiceNumber(text);
  const amount = extractPrimaryAmount(text);
  const dueDate = extractDueDate(text);
  const issueDate = extractIssueDate(text);

  let fields = 0;
  if (vendor) fields += 1;
  if (invoiceNumber) fields += 1;
  if (amount) fields += 1;
  if (dueDate) fields += 1;

  return {
    vendor,
    invoiceNumber,
    amount,
    dueDate,
    issueDate,
    confidence: fields / 4,
  };
}

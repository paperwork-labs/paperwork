import type { ExtractedDocument } from "./types";

type PdfParseFn = (
  data: Buffer,
  options?: object,
) => Promise<{
  numpages: number;
  text: string;
  info?: Record<string, unknown>;
}>;

function parsePdfMetaDate(raw: unknown): Date | undefined {
  if (typeof raw !== "string") return undefined;
  const compact = raw.replace(/^D:/, "").replace(/[Z+'"].*$/, "");
  const y = compact.slice(0, 4);
  const mo = compact.slice(4, 6);
  const d = compact.slice(6, 8);
  if (y.length !== 4 || mo.length !== 2 || d.length !== 2) return undefined;
  const year = Number(y);
  const month = Number(mo);
  const day = Number(d);
  if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day))
    return undefined;
  return new Date(Date.UTC(year, month - 1, day));
}

function metadataFromPdfInfo(
  info: Record<string, unknown> | undefined,
): ExtractedDocument["metadata"] {
  if (!info || typeof info !== "object") return undefined;

  const meta: NonNullable<ExtractedDocument["metadata"]> = {};

  if (typeof info.Title === "string" && info.Title.trim()) {
    meta.title = info.Title.trim();
  }
  if (typeof info.Author === "string" && info.Author.trim()) {
    meta.author = info.Author.trim();
  }
  if (typeof info.Creator === "string" && info.Creator.trim()) {
    meta.creator = info.Creator.trim();
  }

  const created = parsePdfMetaDate(info.CreationDate);
  if (created) meta.creationDate = created;

  const normalizedKeys = new Set([
    "Title",
    "Author",
    "Creator",
    "CreationDate",
  ]);
  for (const [k, v] of Object.entries(info)) {
    if (normalizedKeys.has(k)) continue;
    meta[k] = v;
  }

  return Object.keys(meta).length ? meta : undefined;
}

function splitPages(fullText: string, pageCount: number): string[] {
  if (fullText.includes("\f")) {
    return fullText.split("\f").map((p) => p.trim());
  }
  if (pageCount <= 1) {
    return [fullText.trim()];
  }
  return [fullText.trim()];
}

export async function extractPdf(buffer: Buffer): Promise<ExtractedDocument> {
  const mod = await import("pdf-parse/lib/pdf-parse.js");
  const pdfParse = mod.default as PdfParseFn;
  const result = await pdfParse(buffer);

  const text = result.text ?? "";
  const pageCount = result.numpages;
  const pages = splitPages(text, pageCount);

  return {
    format: "pdf",
    pageCount,
    text,
    pages,
    metadata: metadataFromPdfInfo(result.info),
  };
}

export async function extractImage(
  buffer: Buffer,
  contentType: string,
): Promise<ExtractedDocument> {
  void buffer;
  void contentType;
  throw new Error("OCR not yet supported");
}

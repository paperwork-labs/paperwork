export type EmailAttachment = {
  filename: string;
  mimeType: string;
  size: number;
  content: Uint8Array;
};

export type InboundEmail = {
  id: string;
  from: string;
  to: string[];
  subject: string;
  body: string;
  attachments: EmailAttachment[];
  receivedAt: Date;
};

export type EmailKind = "invoice" | "receipt" | "statement" | "other";

type RawHeaderMap = Map<string, string>;

function toText(raw: string | Uint8Array): string {
  if (typeof raw === "string") return raw;
  return new TextDecoder("utf-8", { fatal: false }).decode(raw);
}

function decodeQuotedPrintable(chunk: string): string {
  return chunk.replace(/=\r?\n/g, "").replace(/=([0-9A-F]{2})/gi, (_, h) =>
    String.fromCharCode(Number.parseInt(h, 16)),
  );
}

function decodeBase64ToBytes(segment: string): Uint8Array {
  const trimmed = segment.replace(/\s+/g, "");
  if (typeof atob === "function") {
    const bin = atob(trimmed);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }
  const g = globalThis as unknown as {
    Buffer?: { from(data: string, encoding: string): { length: number; [i: number]: number } };
  };
  if (g.Buffer?.from) {
    const buf = g.Buffer.from(trimmed, "base64");
    const out = new Uint8Array(buf.length);
    for (let i = 0; i < buf.length; i++) out[i] = buf[i]!;
    return out;
  }
  throw new Error("Base64 decoding requires atob or globalThis.Buffer");
}

/** Split raw RFC822/MIME-ish message into headers and body (first blank line boundary). */
function splitHeadersBody(rawText: string): { headersText: string; body: string } {
  const delim = /\r?\n\r?\n/;
  const idx = rawText.search(delim);
  if (idx === -1) return { headersText: rawText, body: "" };
  const m = rawText.match(delim);
  const nlLen = m?.[0]?.length ?? 2;
  return {
    headersText: rawText.slice(0, idx),
    body: rawText.slice(idx + nlLen),
  };
}

function unfoldHeaders(headersText: string): RawHeaderMap {
  const unfolded = headersText.replace(/\r?\n[ \t]+/g, " ");
  const map: RawHeaderMap = new Map();
  for (const line of unfolded.split(/\r?\n/)) {
    const c = line.indexOf(":");
    if (c === -1) continue;
    const k = line.slice(0, c).trim().toLowerCase();
    const v = line.slice(c + 1).trim();
    map.set(k, v);
  }
  return map;
}

function parseAddressHeader(value: string | undefined): string {
  if (!value?.trim()) return "";
  const angle = /<([^>]+)>/.exec(value);
  return (angle?.[1]?.trim() || value.trim()).replace(/^"|"$/g, "");
}

function parseToList(value: string | undefined): string[] {
  if (!value?.trim()) return [];
  return value
    .split(",")
    .map((p) => parseAddressHeader(p.trim()))
    .filter(Boolean);
}

function parseDateHeader(value: string | undefined, fallback: Date): Date {
  if (!value) return fallback;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? fallback : d;
}

function getBoundary(contentType: string | undefined): string | undefined {
  if (!contentType) return undefined;
  const m = /boundary\s*=\s*("?)([^";\s]+)\1/i.exec(contentType);
  return m?.[2];
}

function stripCharset(text: string): string {
  return text.replace(/^charset="?[^";\s]+"?/i, "").trim();
}

function decodePartBody(
  body: string,
  encoding: string | undefined,
  mimeType: string,
): { text?: string; bytes?: Uint8Array } {
  const enc = (encoding || "7bit").toLowerCase();
  const isText = /^text\//i.test(mimeType) || mimeType === "message/rfc822";

  if (enc === "base64") {
    const bytes = decodeBase64ToBytes(body);
    if (isText) return { text: new TextDecoder("utf-8", { fatal: false }).decode(bytes) };
    return { bytes };
  }
  if (enc === "quoted-printable" && isText)
    return { text: decodeQuotedPrintable(body) };
  if (isText) return { text: body };
  return { bytes: new TextEncoder().encode(body) };
}

function parseMultipartAttachments(
  body: string,
  boundary: string,
): { textBody: string; attachments: EmailAttachment[] } {
  const sep = `--${boundary}`;
  const parts = body.split(sep).map((p) => p.replace(/^\r?\n/, "").trim());
  const attachments: EmailAttachment[] = [];
  let textBody = "";

  for (const part of parts) {
    if (part === "" || part === "--") continue;
    const { headersText, body: partBody } = splitHeadersBody(part);
    const h = unfoldHeaders(headersText);
    const cd = h.get("content-disposition") || "";
    const ct = stripCharset(h.get("content-type") || "text/plain");
    const cte = h.get("content-transfer-encoding") || undefined;
    const nameMatch =
      /filename\s*=\s*("?)([^";\n]+)\1/i.exec(cd) ||
      /name\s*=\s*("?)([^";\n]+)\1/i.exec(h.get("content-type") || "");
    const filename = nameMatch?.[2]?.trim() || "unnamed";
    const isAttachment = /attachment/i.test(cd);
    const decoded = decodePartBody(partBody, cte, ct);

    if (isAttachment && decoded.bytes) {
      attachments.push({
        filename,
        mimeType: ct.split(";")[0]?.trim() || "application/octet-stream",
        size: decoded.bytes.byteLength,
        content: decoded.bytes,
      });
    } else if (decoded.text && /^text\/plain/i.test(ct) && !isAttachment) {
      textBody = textBody ? `${textBody}\n${decoded.text}` : decoded.text;
    } else if (isAttachment && decoded.text) {
      const bytes = new TextEncoder().encode(decoded.text);
      attachments.push({
        filename,
        mimeType: ct.split(";")[0]?.trim() || "text/plain",
        size: bytes.byteLength,
        content: bytes,
      });
    }
  }

  return { textBody, attachments };
}

export class EmailProcessor {
  parseRawEmail(raw: string | Uint8Array): InboundEmail {
    const rawText = toText(raw);
    const now = new Date();
    const { headersText, body } = splitHeadersBody(rawText);
    const h = unfoldHeaders(headersText);

    const id =
      h.get("message-id")?.replace(/^<|>$/g, "") ||
      `local-${now.getTime()}-${Math.random().toString(36).slice(2, 10)}`;
    const from = parseAddressHeader(h.get("from"));
    const to = parseToList(h.get("to"));
    const subject = h.get("subject") || "";
    const contentType = h.get("content-type");
    const boundary = getBoundary(contentType);

    let plainBody = body;
    let attachments: EmailAttachment[] = [];

    if (boundary && /multipart\//i.test(contentType || "")) {
      const parsed = parseMultipartAttachments(body, boundary);
      plainBody = parsed.textBody || plainBody;
      attachments = parsed.attachments;
    } else {
      const cte = h.get("content-transfer-encoding");
      const ct = stripCharset(contentType || "text/plain");
      const dec = decodePartBody(body, cte, ct);
      plainBody = dec.text ?? "";
    }

    return {
      id,
      from,
      to,
      subject,
      body: plainBody,
      attachments,
      receivedAt: parseDateHeader(h.get("date"), now),
    };
  }

  extractAttachments(email: InboundEmail): EmailAttachment[] {
    return [...email.attachments];
  }

  classifyEmail(email: InboundEmail): EmailKind {
    const hay = `${email.subject}\n${email.body}`.toLowerCase();
    if (/\binvoice\b|payment due|amount due|net\s*30/i.test(hay)) return "invoice";
    if (/\breceipt\b|thank you for your purchase|order confirmation/i.test(hay))
      return "receipt";
    if (/\bstatement\b|account summary|balance due|period ending/i.test(hay))
      return "statement";
    return "other";
  }
}

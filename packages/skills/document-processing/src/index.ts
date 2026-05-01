/** Line item on an invoice. */
export interface LineItem {
  description: string;
  quantity: number;
  unitPrice: number;
  total: number;
}

/** Structured fields extracted from an invoice document. */
export interface InvoiceFields {
  vendor: string;
  amount: number;
  currency: string;
  date: string;
  dueDate: string;
  lineItems: LineItem[];
}

/** Result returned by document parsing methods. */
export interface ParseResult {
  text: string;
  pageCount: number;
}

/**
 * Parses PDF and image documents and extracts structured invoice data.
 *
 * This is a skeleton implementation — concrete OCR / PDF parsing
 * libraries (e.g. pdf-parse, tesseract.js) should be wired in
 * once the dependency strategy is finalised.
 */
export class DocumentParser {
  /**
   * Extract text content from a PDF buffer.
   */
  async parsePdf(buffer: Buffer): Promise<ParseResult> {
    if (!buffer || buffer.length === 0) {
      throw new Error("parsePdf: received empty buffer");
    }

    // TODO: integrate a PDF parsing library (e.g. pdf-parse)
    return { text: "", pageCount: 0 };
  }

  /**
   * Extract text content from an image buffer via OCR.
   */
  async parseImage(buffer: Buffer): Promise<ParseResult> {
    if (!buffer || buffer.length === 0) {
      throw new Error("parseImage: received empty buffer");
    }

    // TODO: integrate an OCR library (e.g. tesseract.js)
    return { text: "", pageCount: 1 };
  }

  /**
   * Extract structured invoice fields from raw text.
   */
  extractInvoiceFields(text: string): InvoiceFields {
    if (!text) {
      throw new Error("extractInvoiceFields: received empty text");
    }

    // TODO: implement field extraction logic (regex / LLM-based)
    return {
      vendor: "",
      amount: 0,
      currency: "USD",
      date: "",
      dueDate: "",
      lineItems: [],
    };
  }
}

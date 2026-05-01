export type ExtractedDocument = {
  format: "pdf" | "image" | "unknown";
  pageCount?: number;
  text: string;
  pages?: string[];
  metadata?: {
    title?: string;
    author?: string;
    creator?: string;
    creationDate?: Date;
    [k: string]: unknown;
  };
};

export type InvoiceCandidate = {
  vendor?: string;
  invoiceNumber?: string;
  amount?: { value: number; currency: string };
  dueDate?: Date;
  issueDate?: Date;
  lineItems?: Array<{
    description: string;
    amount?: { value: number; currency: string };
  }>;
  confidence: number;
};

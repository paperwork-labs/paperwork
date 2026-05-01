export type OAuthTokens = {
  accessToken: string;
  refreshToken: string;
  expiresAt: number; // ms epoch
  scope: string[];
};

export type GmailInboundConfig = {
  clientId: string;
  clientSecret: string;
  redirectUri: string;
  scopes?: string[]; // default: ["https://www.googleapis.com/auth/gmail.readonly"]
  /** Allowlist of vendor domains for `fromKnownVendor` (no leading @). */
  knownVendorDomains?: string[];
};

export type ParsedAttachment = {
  filename: string;
  contentType: string;
  size: number;
  content: Buffer;
};

export type ParsedInboundEmail = {
  messageId: string;
  threadId: string;
  from: { name?: string; address: string };
  to: { name?: string; address: string }[];
  subject: string;
  date: Date;
  text?: string;
  html?: string;
  attachments: ParsedAttachment[];
  rawHeaders: Record<string, string>;
};

export type InboundCandidate = {
  email: ParsedInboundEmail;
  // Heuristic-based extraction signals
  signals: {
    looksLikeInvoice: boolean; // attachment is PDF + body contains "invoice"|"receipt"|"bill"
    fromKnownVendor?: string; // matched a vendor domain
    detectedAmount?: { value: number; currency: string };
    detectedDueDate?: Date;
  };
};

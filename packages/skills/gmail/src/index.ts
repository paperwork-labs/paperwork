import type { gmail_v1 } from "googleapis";

export type GmailMessage = gmail_v1.Schema$Message;
export type GmailMessageList = gmail_v1.Schema$ListMessagesResponse;

export interface ParsedInvoice {
  vendor: string | null;
  amount: number | null;
  currency: string | null;
  dueDate: string | null;
  invoiceNumber: string | null;
  rawText: string;
}

export interface GmailClientConfig {
  credentials: {
    clientId: string;
    clientSecret: string;
    refreshToken: string;
  };
}

export class GmailClient {
  private config: GmailClientConfig;

  constructor(config: GmailClientConfig) {
    this.config = config;
  }

  async connect(): Promise<void> {
    // TODO: Initialize googleapis OAuth2 client and verify connection
    void this.config;
    throw new Error("Not implemented");
  }

  async listMessages(query: string): Promise<GmailMessageList> {
    // TODO: Use gmail.users.messages.list with query filter
    // Example query: "from:billing@ subject:invoice"
    void query;
    throw new Error("Not implemented");
  }

  async getMessage(id: string): Promise<GmailMessage> {
    // TODO: Use gmail.users.messages.get with full format
    void id;
    throw new Error("Not implemented");
  }

  async parseInvoice(message: GmailMessage): Promise<ParsedInvoice> {
    // TODO: Extract invoice details from email body/attachments
    // Will use LLM for parsing unstructured invoice data
    void message;
    throw new Error("Not implemented");
  }
}

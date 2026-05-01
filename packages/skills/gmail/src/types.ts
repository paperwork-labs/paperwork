import type { gmail_v1 } from "googleapis";

export interface GmailCredentials {
  clientId: string;
  clientSecret: string;
  redirectUri: string;
}

export interface GmailTokens {
  accessToken: string;
  refreshToken?: string;
  expiryDate?: number;
}

export interface GmailClientConfig {
  credentials: GmailCredentials;
  tokens?: GmailTokens;
}

export interface MessageListOptions {
  query?: string;
  maxResults?: number;
  pageToken?: string;
  labelIds?: string[];
  includeSpamTrash?: boolean;
}

export interface MessageListResult {
  messages: gmail_v1.Schema$Message[];
  nextPageToken?: string;
  resultSizeEstimate?: number;
}

export interface MessageGetOptions {
  format?: "minimal" | "full" | "raw" | "metadata";
  metadataHeaders?: string[];
}

export interface AttachmentInfo {
  attachmentId: string;
  filename: string;
  mimeType: string;
  size: number;
}

export interface AttachmentData extends AttachmentInfo {
  data: Buffer;
}

export interface LabelInfo {
  id: string;
  name: string;
  type: "system" | "user";
  messageListVisibility?: string;
  labelListVisibility?: string;
}

export interface SendMessageOptions {
  to: string | string[];
  cc?: string | string[];
  bcc?: string | string[];
  subject: string;
  body: string;
  isHtml?: boolean;
  attachments?: Array<{
    filename: string;
    mimeType: string;
    data: Buffer;
  }>;
  threadId?: string;
  inReplyTo?: string;
  references?: string[];
}

export interface SendMessageResult {
  id: string;
  threadId: string;
  labelIds: string[];
}

export { GmailClient, createGmailClient } from "./client.js";
export { GmailLabels, SYSTEM_LABELS, type SystemLabel } from "./labels.js";
export {
  GmailAttachments,
  extractInlineImages,
  getMessageBody,
  getMessageHeaders,
} from "./attachments.js";
export type {
  GmailCredentials,
  GmailTokens,
  GmailClientConfig,
  MessageListOptions,
  MessageListResult,
  MessageGetOptions,
  AttachmentInfo,
  AttachmentData,
  LabelInfo,
  SendMessageOptions,
  SendMessageResult,
} from "./types.js";

export const GMAIL_SCOPES = {
  READONLY: "https://www.googleapis.com/auth/gmail.readonly",
  SEND: "https://www.googleapis.com/auth/gmail.send",
  COMPOSE: "https://www.googleapis.com/auth/gmail.compose",
  MODIFY: "https://www.googleapis.com/auth/gmail.modify",
  LABELS: "https://www.googleapis.com/auth/gmail.labels",
  FULL_ACCESS: "https://mail.google.com/",
} as const;

export type GmailScope = (typeof GMAIL_SCOPES)[keyof typeof GMAIL_SCOPES];

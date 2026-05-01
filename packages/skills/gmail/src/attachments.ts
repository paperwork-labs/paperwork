import { google, gmail_v1 } from "googleapis";
import type { AttachmentInfo, AttachmentData } from "./types.js";

export class GmailAttachments {
  private gmail: gmail_v1.Gmail;

  constructor(auth: ReturnType<typeof google.auth.OAuth2>) {
    this.gmail = google.gmail({ version: "v1", auth });
  }

  extractAttachmentInfo(message: gmail_v1.Schema$Message): AttachmentInfo[] {
    const attachments: AttachmentInfo[] = [];

    const processPayload = (payload: gmail_v1.Schema$MessagePart | undefined): void => {
      if (!payload) return;

      if (payload.filename && payload.body?.attachmentId) {
        attachments.push({
          attachmentId: payload.body.attachmentId,
          filename: payload.filename,
          mimeType: payload.mimeType ?? "application/octet-stream",
          size: payload.body.size ?? 0,
        });
      }

      if (payload.parts) {
        for (const part of payload.parts) {
          processPayload(part);
        }
      }
    };

    processPayload(message.payload);
    return attachments;
  }

  async getAttachment(
    messageId: string,
    attachmentId: string,
    attachmentInfo: AttachmentInfo
  ): Promise<AttachmentData> {
    const response = await this.gmail.users.messages.attachments.get({
      userId: "me",
      messageId,
      id: attachmentId,
    });

    const data = response.data.data ?? "";
    const buffer = Buffer.from(data, "base64");

    return {
      ...attachmentInfo,
      data: buffer,
    };
  }

  async getAllAttachments(
    messageId: string,
    message: gmail_v1.Schema$Message
  ): Promise<AttachmentData[]> {
    const attachmentInfos = this.extractAttachmentInfo(message);
    const attachments: AttachmentData[] = [];

    for (const info of attachmentInfos) {
      const attachment = await this.getAttachment(messageId, info.attachmentId, info);
      attachments.push(attachment);
    }

    return attachments;
  }
}

export function extractInlineImages(message: gmail_v1.Schema$Message): Array<{
  contentId: string;
  mimeType: string;
  data: string;
}> {
  const images: Array<{ contentId: string; mimeType: string; data: string }> = [];

  const processPayload = (payload: gmail_v1.Schema$MessagePart | undefined): void => {
    if (!payload) return;

    const contentIdHeader = payload.headers?.find(
      (h) => h.name?.toLowerCase() === "content-id"
    );

    if (
      contentIdHeader &&
      payload.body?.data &&
      payload.mimeType?.startsWith("image/")
    ) {
      images.push({
        contentId: contentIdHeader.value ?? "",
        mimeType: payload.mimeType,
        data: payload.body.data,
      });
    }

    if (payload.parts) {
      for (const part of payload.parts) {
        processPayload(part);
      }
    }
  };

  processPayload(message.payload);
  return images;
}

export function getMessageBody(message: gmail_v1.Schema$Message): {
  plain?: string;
  html?: string;
} {
  const result: { plain?: string; html?: string } = {};

  const processPayload = (payload: gmail_v1.Schema$MessagePart | undefined): void => {
    if (!payload) return;

    if (payload.mimeType === "text/plain" && payload.body?.data) {
      result.plain = Buffer.from(payload.body.data, "base64").toString("utf-8");
    }

    if (payload.mimeType === "text/html" && payload.body?.data) {
      result.html = Buffer.from(payload.body.data, "base64").toString("utf-8");
    }

    if (payload.parts) {
      for (const part of payload.parts) {
        processPayload(part);
      }
    }
  };

  processPayload(message.payload);
  return result;
}

export function getMessageHeaders(
  message: gmail_v1.Schema$Message
): Record<string, string> {
  const headers: Record<string, string> = {};

  for (const header of message.payload?.headers ?? []) {
    if (header.name && header.value) {
      headers[header.name] = header.value;
    }
  }

  return headers;
}

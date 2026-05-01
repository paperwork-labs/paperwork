import { google, gmail_v1 } from "googleapis";
import type { LabelInfo } from "./types.js";

export class GmailLabels {
  private gmail: gmail_v1.Gmail;

  constructor(auth: ReturnType<typeof google.auth.OAuth2>) {
    this.gmail = google.gmail({ version: "v1", auth });
  }

  async listLabels(): Promise<LabelInfo[]> {
    const response = await this.gmail.users.labels.list({
      userId: "me",
    });

    return (response.data.labels ?? []).map((label) => ({
      id: label.id ?? "",
      name: label.name ?? "",
      type: label.type === "system" ? "system" : "user",
      messageListVisibility: label.messageListVisibility ?? undefined,
      labelListVisibility: label.labelListVisibility ?? undefined,
    }));
  }

  async getLabel(labelId: string): Promise<LabelInfo | null> {
    const response = await this.gmail.users.labels.get({
      userId: "me",
      id: labelId,
    });

    if (!response.data) return null;

    return {
      id: response.data.id ?? "",
      name: response.data.name ?? "",
      type: response.data.type === "system" ? "system" : "user",
      messageListVisibility: response.data.messageListVisibility ?? undefined,
      labelListVisibility: response.data.labelListVisibility ?? undefined,
    };
  }

  async createLabel(
    name: string,
    options: {
      messageListVisibility?: "show" | "hide";
      labelListVisibility?: "labelShow" | "labelShowIfUnread" | "labelHide";
      textColor?: string;
      backgroundColor?: string;
    } = {}
  ): Promise<LabelInfo> {
    const response = await this.gmail.users.labels.create({
      userId: "me",
      requestBody: {
        name,
        messageListVisibility: options.messageListVisibility,
        labelListVisibility: options.labelListVisibility,
        color: options.textColor && options.backgroundColor
          ? {
              textColor: options.textColor,
              backgroundColor: options.backgroundColor,
            }
          : undefined,
      },
    });

    return {
      id: response.data.id ?? "",
      name: response.data.name ?? "",
      type: "user",
      messageListVisibility: response.data.messageListVisibility ?? undefined,
      labelListVisibility: response.data.labelListVisibility ?? undefined,
    };
  }

  async updateLabel(
    labelId: string,
    updates: {
      name?: string;
      messageListVisibility?: "show" | "hide";
      labelListVisibility?: "labelShow" | "labelShowIfUnread" | "labelHide";
      textColor?: string;
      backgroundColor?: string;
    }
  ): Promise<LabelInfo> {
    const response = await this.gmail.users.labels.update({
      userId: "me",
      id: labelId,
      requestBody: {
        name: updates.name,
        messageListVisibility: updates.messageListVisibility,
        labelListVisibility: updates.labelListVisibility,
        color: updates.textColor && updates.backgroundColor
          ? {
              textColor: updates.textColor,
              backgroundColor: updates.backgroundColor,
            }
          : undefined,
      },
    });

    return {
      id: response.data.id ?? "",
      name: response.data.name ?? "",
      type: "user",
      messageListVisibility: response.data.messageListVisibility ?? undefined,
      labelListVisibility: response.data.labelListVisibility ?? undefined,
    };
  }

  async deleteLabel(labelId: string): Promise<void> {
    await this.gmail.users.labels.delete({
      userId: "me",
      id: labelId,
    });
  }
}

export const SYSTEM_LABELS = {
  INBOX: "INBOX",
  SENT: "SENT",
  DRAFT: "DRAFT",
  SPAM: "SPAM",
  TRASH: "TRASH",
  UNREAD: "UNREAD",
  STARRED: "STARRED",
  IMPORTANT: "IMPORTANT",
  CATEGORY_PERSONAL: "CATEGORY_PERSONAL",
  CATEGORY_SOCIAL: "CATEGORY_SOCIAL",
  CATEGORY_PROMOTIONS: "CATEGORY_PROMOTIONS",
  CATEGORY_UPDATES: "CATEGORY_UPDATES",
  CATEGORY_FORUMS: "CATEGORY_FORUMS",
} as const;

export type SystemLabel = (typeof SYSTEM_LABELS)[keyof typeof SYSTEM_LABELS];

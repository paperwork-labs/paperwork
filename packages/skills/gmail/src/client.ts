import { google, gmail_v1 } from "googleapis";
import type {
  GmailClientConfig,
  GmailTokens,
  MessageListOptions,
  MessageListResult,
  MessageGetOptions,
  SendMessageOptions,
  SendMessageResult,
} from "./types.js";

export class GmailClient {
  private gmail: gmail_v1.Gmail;
  private oauth2Client: ReturnType<typeof google.auth.OAuth2>;

  constructor(config: GmailClientConfig) {
    this.oauth2Client = new google.auth.OAuth2(
      config.credentials.clientId,
      config.credentials.clientSecret,
      config.credentials.redirectUri
    );

    if (config.tokens) {
      this.setTokens(config.tokens);
    }

    this.gmail = google.gmail({ version: "v1", auth: this.oauth2Client });
  }

  setTokens(tokens: GmailTokens): void {
    this.oauth2Client.setCredentials({
      access_token: tokens.accessToken,
      refresh_token: tokens.refreshToken,
      expiry_date: tokens.expiryDate,
    });
  }

  getAuthUrl(scopes: string[]): string {
    return this.oauth2Client.generateAuthUrl({
      access_type: "offline",
      scope: scopes,
      prompt: "consent",
    });
  }

  async exchangeCodeForTokens(code: string): Promise<GmailTokens> {
    const { tokens } = await this.oauth2Client.getToken(code);
    this.oauth2Client.setCredentials(tokens);

    return {
      accessToken: tokens.access_token ?? "",
      refreshToken: tokens.refresh_token ?? undefined,
      expiryDate: tokens.expiry_date ?? undefined,
    };
  }

  async listMessages(options: MessageListOptions = {}): Promise<MessageListResult> {
    const response = await this.gmail.users.messages.list({
      userId: "me",
      q: options.query,
      maxResults: options.maxResults ?? 10,
      pageToken: options.pageToken,
      labelIds: options.labelIds,
      includeSpamTrash: options.includeSpamTrash ?? false,
    });

    const messageIds = response.data.messages ?? [];
    const messages: gmail_v1.Schema$Message[] = [];

    for (const msg of messageIds) {
      if (msg.id) {
        const fullMessage = await this.getMessage(msg.id);
        if (fullMessage) {
          messages.push(fullMessage);
        }
      }
    }

    return {
      messages,
      nextPageToken: response.data.nextPageToken ?? undefined,
      resultSizeEstimate: response.data.resultSizeEstimate ?? undefined,
    };
  }

  async getMessage(
    messageId: string,
    options: MessageGetOptions = {}
  ): Promise<gmail_v1.Schema$Message | null> {
    const response = await this.gmail.users.messages.get({
      userId: "me",
      id: messageId,
      format: options.format ?? "full",
      metadataHeaders: options.metadataHeaders,
    });

    return response.data;
  }

  async sendMessage(options: SendMessageOptions): Promise<SendMessageResult> {
    const toAddresses = Array.isArray(options.to) ? options.to.join(", ") : options.to;
    const ccAddresses = options.cc
      ? Array.isArray(options.cc)
        ? options.cc.join(", ")
        : options.cc
      : undefined;
    const bccAddresses = options.bcc
      ? Array.isArray(options.bcc)
        ? options.bcc.join(", ")
        : options.bcc
      : undefined;

    let emailContent = [
      "To: " + toAddresses,
      "Subject: " + options.subject,
      "Content-Type: " + (options.isHtml ? "text/html" : "text/plain") + "; charset=utf-8",
    ];

    if (ccAddresses) {
      emailContent.push("Cc: " + ccAddresses);
    }
    if (bccAddresses) {
      emailContent.push("Bcc: " + bccAddresses);
    }
    if (options.inReplyTo) {
      emailContent.push("In-Reply-To: " + options.inReplyTo);
    }
    if (options.references?.length) {
      emailContent.push("References: " + options.references.join(" "));
    }

    emailContent.push("", options.body);

    const rawMessage = Buffer.from(emailContent.join("\r\n"))
      .toString("base64")
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/g, "");

    const response = await this.gmail.users.messages.send({
      userId: "me",
      requestBody: {
        raw: rawMessage,
        threadId: options.threadId,
      },
    });

    return {
      id: response.data.id ?? "",
      threadId: response.data.threadId ?? "",
      labelIds: response.data.labelIds ?? [],
    };
  }

  async trashMessage(messageId: string): Promise<void> {
    await this.gmail.users.messages.trash({
      userId: "me",
      id: messageId,
    });
  }

  async untrashMessage(messageId: string): Promise<void> {
    await this.gmail.users.messages.untrash({
      userId: "me",
      id: messageId,
    });
  }

  async deleteMessage(messageId: string): Promise<void> {
    await this.gmail.users.messages.delete({
      userId: "me",
      id: messageId,
    });
  }

  async modifyLabels(
    messageId: string,
    addLabelIds: string[],
    removeLabelIds: string[]
  ): Promise<void> {
    await this.gmail.users.messages.modify({
      userId: "me",
      id: messageId,
      requestBody: {
        addLabelIds,
        removeLabelIds,
      },
    });
  }

  async markAsRead(messageId: string): Promise<void> {
    await this.modifyLabels(messageId, [], ["UNREAD"]);
  }

  async markAsUnread(messageId: string): Promise<void> {
    await this.modifyLabels(messageId, ["UNREAD"], []);
  }

  async getProfile(): Promise<{ emailAddress: string; messagesTotal: number; threadsTotal: number }> {
    const response = await this.gmail.users.getProfile({
      userId: "me",
    });

    return {
      emailAddress: response.data.emailAddress ?? "",
      messagesTotal: response.data.messagesTotal ?? 0,
      threadsTotal: response.data.threadsTotal ?? 0,
    };
  }
}

export function createGmailClient(config: GmailClientConfig): GmailClient {
  return new GmailClient(config);
}

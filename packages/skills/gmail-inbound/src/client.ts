import { google } from "googleapis";
import type { GmailInboundConfig, InboundCandidate, OAuthTokens, ParsedInboundEmail } from "./types.js";
import * as oauth from "./oauth.js";
import { buildInvoiceSignals, decodeGmailRawBase64, parseRawMime } from "./parser.js";

const DEFAULT_LIST_QUERY = "is:unread label:billing";
const PROCESSED_LABEL_NAME = "billing/processed";

export class GmailInboundClient {
  private readonly config: GmailInboundConfig;

  constructor(config: GmailInboundConfig) {
    this.config = config;
  }

  buildAuthorizeUrl(state?: string): string {
    return oauth.buildAuthorizeUrl(this.config, state);
  }

  exchangeCode(code: string): Promise<OAuthTokens> {
    return oauth.exchangeCode(this.config, code);
  }

  refreshTokens(refreshToken: string): Promise<OAuthTokens> {
    return oauth.refreshTokens(this.config, refreshToken);
  }

  private createAuth(tokens: OAuthTokens) {
    const client = oauth.createOAuth2Client(this.config);
    client.setCredentials({
      access_token: tokens.accessToken,
      refresh_token: tokens.refreshToken,
      expiry_date: tokens.expiresAt,
    });
    return client;
  }

  async list(
    tokens: OAuthTokens,
    opts?: { query?: string; maxResults?: number }
  ): Promise<ParsedInboundEmail[]> {
    const auth = this.createAuth(tokens);
    const gmail = google.gmail({ version: "v1", auth });
    const query = opts?.query ?? DEFAULT_LIST_QUERY;
    const maxResults = opts?.maxResults ?? 25;

    const listRes = await gmail.users.messages.list({
      userId: "me",
      q: query,
      maxResults,
    });

    const ids = listRes.data.messages ?? [];
    const out: ParsedInboundEmail[] = [];

    for (const m of ids) {
      if (!m.id) continue;
      const full = await gmail.users.messages.get({
        userId: "me",
        id: m.id,
        format: "raw",
      });
      const raw = full.data.raw;
      if (!raw) continue;
      const mime = decodeGmailRawBase64(raw);
      const threadId = full.data.threadId ?? "";
      const parsed = await parseRawMime(m.id, threadId, mime);
      out.push(parsed);
    }

    return out;
  }

  classifyAsInvoice(email: ParsedInboundEmail): InboundCandidate {
    return {
      email,
      signals: buildInvoiceSignals(email, {
        knownVendorDomains: this.config.knownVendorDomains,
      }),
    };
  }

  async markProcessed(tokens: OAuthTokens, messageId: string): Promise<void> {
    const auth = this.createAuth(tokens);
    const gmail = google.gmail({ version: "v1", auth });

    const labelsRes = await gmail.users.labels.list({ userId: "me" });
    let processedId = labelsRes.data.labels?.find(
      (l) => l.name === PROCESSED_LABEL_NAME
    )?.id;

    if (!processedId) {
      const created = await gmail.users.labels.create({
        userId: "me",
        requestBody: {
          name: PROCESSED_LABEL_NAME,
          labelListVisibility: "labelShow",
          messageListVisibility: "show",
        },
      });
      processedId = created.data.id ?? undefined;
    }

    if (!processedId) {
      throw new Error(`Failed to create or resolve label: ${PROCESSED_LABEL_NAME}`);
    }

    await gmail.users.messages.modify({
      userId: "me",
      id: messageId,
      requestBody: {
        addLabelIds: [processedId],
        removeLabelIds: ["UNREAD"],
      },
    });
  }
}

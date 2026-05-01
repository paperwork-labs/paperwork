import { google } from "googleapis";
import type { GmailInboundConfig, OAuthTokens } from "./types.js";

export const DEFAULT_GMAIL_INBOUND_SCOPES = [
  "https://www.googleapis.com/auth/gmail.readonly",
] as const;

type GmailOAuth2Client = InstanceType<typeof google.auth.OAuth2>;

export function createOAuth2Client(config: GmailInboundConfig): GmailOAuth2Client {
  return new google.auth.OAuth2(config.clientId, config.clientSecret, config.redirectUri);
}

function normalizeScopes(config: GmailInboundConfig): string[] {
  if (config.scopes?.length) {
    return [...config.scopes];
  }
  return [...DEFAULT_GMAIL_INBOUND_SCOPES];
}

function scopeStringToArray(scope: string | null | undefined): string[] {
  if (!scope) return [];
  return String(scope)
    .split(/\s+/u)
    .map((s) => s.trim())
    .filter(Boolean);
}

type GoogleAuthCredentials = {
  access_token?: string | null;
  refresh_token?: string | null;
  expiry_date?: number | null;
  scope?: string | null;
};

function credentialsToTokens(
  creds: GoogleAuthCredentials,
  fallbackRefreshToken?: string
): OAuthTokens {
  const scope = scopeStringToArray(creds.scope);
  return {
    accessToken: creds.access_token ?? "",
    refreshToken: creds.refresh_token ?? fallbackRefreshToken ?? "",
    expiresAt: creds.expiry_date ?? Date.now() + 3_600_000,
    scope,
  };
}

export function buildAuthorizeUrl(config: GmailInboundConfig, state?: string): string {
  const oauth2 = createOAuth2Client(config);
  return oauth2.generateAuthUrl({
    access_type: "offline",
    scope: normalizeScopes(config),
    prompt: "consent",
    ...(state !== undefined ? { state } : {}),
  });
}

export async function exchangeCode(
  config: GmailInboundConfig,
  code: string
): Promise<OAuthTokens> {
  const oauth2 = createOAuth2Client(config);
  const { tokens } = await oauth2.getToken(code);
  oauth2.setCredentials(tokens);

  return credentialsToTokens(tokens);
}

export async function refreshTokens(
  config: GmailInboundConfig,
  refreshToken: string
): Promise<OAuthTokens> {
  const oauth2 = createOAuth2Client(config);
  oauth2.setCredentials({ refresh_token: refreshToken });
  const { credentials } = await oauth2.refreshAccessToken();
  oauth2.setCredentials(credentials);

  return credentialsToTokens(credentials, refreshToken);
}
